"""
Distributed locking implementation using Redis for critical sections
"""
import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional
import structlog

logger = structlog.get_logger()

class LockAcquisitionError(Exception):
    """Raised when lock cannot be acquired."""
    pass

class LockReleaseError(Exception):
    """Raised when lock cannot be released."""
    pass

class DistributedLock:
    """Redis-based distributed lock implementation."""
    
    def __init__(self, redis_client, key: str, timeout: int = 30, retry_delay: float = 0.1):
        self.redis_client = redis_client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.lock_value = None
        self.acquired = False
    
    async def acquire(self, blocking: bool = True, timeout: Optional[int] = None) -> bool:
        """
        Acquire distributed lock.
        
        Args:
            blocking: If True, wait for lock. If False, return immediately.
            timeout: Max time to wait for lock (None = use default)
        
        Returns:
            True if lock acquired, False otherwise
        """
        if self.acquired:
            logger.warning(f"Lock {self.key} already acquired by this instance")
            return True
        
        self.lock_value = str(uuid.uuid4())
        lock_timeout = timeout or self.timeout
        start_time = time.time()
        
        while True:
            try:
                # Try to acquire lock with expiration
                result = await self.redis_client.set(
                    self.key,
                    self.lock_value,
                    ex=lock_timeout,
                    nx=True  # Only set if key doesn't exist
                )
                
                if result:
                    self.acquired = True
                    logger.debug(f"Acquired distributed lock: {self.key}")
                    return True
                
                if not blocking:
                    logger.debug(f"Failed to acquire non-blocking lock: {self.key}")
                    return False
                
                # Check timeout
                if time.time() - start_time >= lock_timeout:
                    logger.warning(f"Lock acquisition timeout: {self.key}")
                    raise LockAcquisitionError(f"Timeout acquiring lock: {self.key}")
                
                # Wait before retry
                await asyncio.sleep(self.retry_delay)
                
            except Exception as e:
                if isinstance(e, LockAcquisitionError):
                    raise
                logger.error(f"Error acquiring lock {self.key}: {e}")
                raise LockAcquisitionError(f"Failed to acquire lock {self.key}: {e}")
    
    async def release(self) -> bool:
        """
        Release distributed lock.
        
        Returns:
            True if lock released, False if lock wasn't held by this instance
        """
        if not self.acquired or not self.lock_value:
            logger.warning(f"Attempting to release unacquired lock: {self.key}")
            return False
        
        try:
            # Use Lua script for atomic compare-and-delete
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            
            result = await self.redis_client.eval(lua_script, 1, self.key, self.lock_value)
            
            if result:
                self.acquired = False
                self.lock_value = None
                logger.debug(f"Released distributed lock: {self.key}")
                return True
            else:
                logger.warning(f"Lock {self.key} was not held by this instance or expired")
                return False
                
        except Exception as e:
            logger.error(f"Error releasing lock {self.key}: {e}")
            raise LockReleaseError(f"Failed to release lock {self.key}: {e}")
    
    async def extend(self, additional_time: int) -> bool:
        """
        Extend lock expiration time.
        
        Args:
            additional_time: Seconds to add to expiration
            
        Returns:
            True if extended, False otherwise
        """
        if not self.acquired or not self.lock_value:
            logger.warning(f"Cannot extend unacquired lock: {self.key}")
            return False
        
        try:
            # Use Lua script for atomic check-and-extend
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            
            result = await self.redis_client.eval(
                lua_script, 1, self.key, self.lock_value, additional_time
            )
            
            if result:
                logger.debug(f"Extended lock {self.key} by {additional_time}s")
                return True
            else:
                logger.warning(f"Cannot extend lock {self.key}, not held by this instance")
                return False
                
        except Exception as e:
            logger.error(f"Error extending lock {self.key}: {e}")
            return False
    
    async def is_locked(self) -> bool:
        """Check if lock exists (by any instance)."""
        try:
            result = await self.redis_client.exists(self.key)
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking lock {self.key}: {e}")
            return False
    
    async def get_ttl(self) -> int:
        """Get remaining TTL of lock in seconds."""
        try:
            ttl = await self.redis_client.ttl(self.key)
            return ttl if ttl >= 0 else 0
        except Exception as e:
            logger.error(f"Error getting TTL for lock {self.key}: {e}")
            return 0
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.release()


class DistributedLockManager:
    """Manager for distributed locks."""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.active_locks = {}
    
    def get_lock(
        self, 
        key: str, 
        timeout: int = 30, 
        retry_delay: float = 0.1
    ) -> DistributedLock:
        """Get a distributed lock instance."""
        return DistributedLock(
            self.redis_client, 
            key, 
            timeout=timeout, 
            retry_delay=retry_delay
        )
    
    @asynccontextmanager
    async def lock(
        self, 
        key: str, 
        timeout: int = 30,
        blocking: bool = True,
        retry_delay: float = 0.1
    ):
        """Context manager for acquiring and releasing locks."""
        lock = self.get_lock(key, timeout=timeout, retry_delay=retry_delay)
        
        try:
            acquired = await lock.acquire(blocking=blocking, timeout=timeout)
            if not acquired:
                raise LockAcquisitionError(f"Could not acquire lock: {key}")
            yield lock
        finally:
            await lock.release()
    
    async def cleanup_expired_locks(self, pattern: str = "lock:*"):
        """Clean up any orphaned locks (for maintenance)."""
        try:
            keys = await self.redis_client.keys(pattern)
            cleaned = 0
            
            for key in keys:
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # No expiration set
                    await self.redis_client.delete(key)
                    cleaned += 1
                    logger.info(f"Cleaned up orphaned lock: {key}")
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} orphaned locks")
                
        except Exception as e:
            logger.error(f"Error during lock cleanup: {e}")

# Usage functions
async def get_redis_client():
    """Get Redis client for distributed locking."""
    import redis.asyncio as redis
    from api.config import settings
    
    return redis.from_url(settings.VALKEY_URL)

async def create_lock_manager():
    """Create distributed lock manager."""
    redis_client = await get_redis_client()
    return DistributedLockManager(redis_client)