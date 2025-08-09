"""
Circuit breaker implementation for external service resilience
"""
import asyncio
import time
from enum import Enum
from typing import Any, Callable, Optional, Type
import structlog

logger = structlog.get_logger()

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass

class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external services.
    
    Protects against cascading failures by monitoring service health
    and temporarily blocking requests when failures exceed threshold.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
        name: str = "unnamed"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.success_count = 0
        
        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        self.total_calls += 1
        
        # Check if circuit should change state
        await self._update_state()
        
        # Reject calls if circuit is open
        if self.state == CircuitState.OPEN:
            logger.warning(
                f"Circuit breaker {self.name} is OPEN, rejecting call",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )
            raise CircuitBreakerError(f"Circuit breaker {self.name} is OPEN")
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            await self._on_success()
            return result
            
        except self.expected_exception as e:
            # Record failure
            await self._on_failure()
            raise
        except Exception as e:
            # Unexpected exception, don't count as failure
            logger.error(
                f"Unexpected exception in circuit breaker {self.name}",
                error=str(e),
                exception_type=type(e).__name__
            )
            raise
    
    async def _update_state(self):
        """Update circuit breaker state based on current conditions."""
        current_time = time.time()
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if current_time - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(
                    f"Circuit breaker {self.name} entering HALF_OPEN state",
                    recovery_timeout=self.recovery_timeout
                )
        
        elif self.state == CircuitState.HALF_OPEN:
            # In half-open state, need successful call to close
            pass
    
    async def _on_success(self):
        """Handle successful call."""
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            # Close circuit after successful test
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info(
                f"Circuit breaker {self.name} closing after successful test",
                success_count=self.success_count
            )
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed call."""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during test, go back to open
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker {self.name} failed during half-open test, returning to OPEN",
                failure_count=self.failure_count
            )
        
        elif self.state == CircuitState.CLOSED:
            # Check if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker {self.name} OPENING due to failures",
                    failure_count=self.failure_count,
                    threshold=self.failure_threshold
                )
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "failure_rate": (
                self.total_failures / self.total_calls * 100 
                if self.total_calls > 0 else 0
            ),
            "last_failure_time": self.last_failure_time,
        }
    
    def reset(self):
        """Reset circuit breaker to initial state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        logger.info(f"Circuit breaker {self.name} reset to CLOSED state")


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        self.breakers = {}
    
    def get_breaker(
        self, 
        name: str, 
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                name=name
            )
        return self.breakers[name]
    
    def get_all_stats(self) -> dict:
        """Get statistics for all circuit breakers."""
        return {
            name: breaker.get_stats()
            for name, breaker in self.breakers.items()
        }
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self.breakers.values():
            breaker.reset()

# Global registry
circuit_registry = CircuitBreakerRegistry()

# Decorator for easy circuit breaker usage
def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: Type[Exception] = Exception
):
    """Decorator to apply circuit breaker to a function."""
    def decorator(func):
        breaker = circuit_registry.get_breaker(
            name, failure_threshold, recovery_timeout, expected_exception
        )
        
        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(breaker.call(func, *args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator