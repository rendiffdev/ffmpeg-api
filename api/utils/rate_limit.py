"""
Enhanced rate limiting utilities for specific endpoints
"""
import time
from typing import Dict, Optional
from fastapi import HTTPException, Request
import structlog

logger = structlog.get_logger()

class EndpointRateLimit:
    """Rate limiter for specific endpoints with higher limits."""
    
    def __init__(self):
        self.clients: Dict[str, Dict[str, any]] = {}
        self.endpoint_limits = {
            'analyze': {'calls': 100, 'period': 3600},    # 100/hour for analysis
            'stream': {'calls': 50, 'period': 3600},      # 50/hour for streaming
            'estimate': {'calls': 1000, 'period': 3600},  # 1000/hour for estimates
            'convert': {'calls': 200, 'period': 3600},    # 200/hour for conversion
        }
    
    def check_rate_limit(self, request: Request, endpoint: str, api_key: str = "anonymous") -> None:
        """Check rate limit for specific endpoint."""
        if endpoint not in self.endpoint_limits:
            return  # No limit defined
        
        limit_config = self.endpoint_limits[endpoint]
        max_calls = limit_config['calls']
        period = limit_config['period']
        
        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        client_id = f"{client_ip}:{api_key}:{endpoint}"
        
        current_time = time.time()
        
        # Clean old entries
        self.clients = {
            cid: data for cid, data in self.clients.items()
            if current_time - data["window_start"] < period
        }
        
        # Check rate limit
        if client_id in self.clients:
            client_data = self.clients[client_id]
            if current_time - client_data["window_start"] < period:
                if client_data["requests"] >= max_calls:
                    logger.warning(
                        f"Rate limit exceeded for {endpoint}",
                        client_id=client_id,
                        requests=client_data["requests"],
                        limit=max_calls
                    )
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded for {endpoint}. Max {max_calls} requests per {period//3600}h.",
                        headers={"Retry-After": str(period)}
                    )
                client_data["requests"] += 1
            else:
                # Reset window
                self.clients[client_id] = {
                    "requests": 1,
                    "window_start": current_time
                }
        else:
            # New client
            self.clients[client_id] = {
                "requests": 1,
                "window_start": current_time
            }

# Global rate limiter instance
endpoint_rate_limiter = EndpointRateLimit()

def check_endpoint_rate_limit(endpoint: str):
    """Decorator for endpoint-specific rate limiting."""
    def decorator(func):
        async def wrapper(request: Request, *args, api_key: str = "anonymous", **kwargs):
            endpoint_rate_limiter.check_rate_limit(request, endpoint, api_key)
            return await func(*args, **kwargs)
        return wrapper
    return decorator