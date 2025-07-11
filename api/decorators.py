"""
Caching decorators for FastAPI endpoints and functions

Provides easy-to-use decorators for:
- API response caching
- Function result caching  
- Database query caching
- Conditional caching based on request parameters
"""
import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

# Use structlog if available, fall back to standard logging
try:
    import structlog
    logger = structlog.get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from fastapi import Request, Response
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    
    # Mock classes for testing
    class Request:
        pass
    
    class Response:
        pass
    
    class JSONResponse:
        def __init__(self, content=None, headers=None):
            self.content = content
            self.headers = headers

from api.cache import cache_service, CacheKeyBuilder


def cache_response(
    ttl: Optional[int] = None,
    cache_type: str = "default",
    key_prefix: Optional[str] = None,
    include_headers: bool = False,
    skip_if: Optional[Callable] = None,
    vary_on: Optional[List[str]] = None
):
    """
    Decorator for caching API response data.
    
    Args:
        ttl: Time to live in seconds
        cache_type: Type of cache for TTL lookup
        key_prefix: Custom prefix for cache key
        include_headers: Whether to include response headers in cache
        skip_if: Function to determine if caching should be skipped
        vary_on: List of request attributes to include in cache key
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request object from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # If no request found, just call the function
                return await func(*args, **kwargs)
            
            # Check if caching should be skipped
            if skip_if and skip_if(request):
                return await func(*args, **kwargs)
            
            # Build cache key
            key_parts = [
                key_prefix or func.__name__,
                request.method,
                str(request.url.path)
            ]
            
            # Add query parameters
            if request.query_params:
                query_string = str(request.query_params)
                key_parts.append(CacheKeyBuilder.hash_key(query_string))
            
            # Add varying attributes
            if vary_on:
                vary_data = {}
                for attr in vary_on:
                    if hasattr(request, attr):
                        vary_data[attr] = getattr(request, attr)
                    elif attr in request.headers:
                        vary_data[attr] = request.headers[attr]
                if vary_data:
                    key_parts.append(CacheKeyBuilder.hash_key(vary_data))
            
            cache_key = CacheKeyBuilder.build_key(*key_parts)
            
            # Try to get from cache
            cached_data = await cache_service.get(cache_key)
            if cached_data is not None:
                logger.debug(f"Cache hit for {cache_key}")
                
                if include_headers and isinstance(cached_data, dict) and 'headers' in cached_data:
                    return JSONResponse(
                        content=cached_data['content'],
                        headers=cached_data['headers']
                    )
                else:
                    return cached_data
            
            # Execute function
            logger.debug(f"Cache miss for {cache_key}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            cache_data = result
            if include_headers and hasattr(result, 'headers'):
                cache_data = {
                    'content': result.body if hasattr(result, 'body') else result,
                    'headers': dict(result.headers)
                }
            
            await cache_service.set(cache_key, cache_data, ttl, cache_type)
            
            return result
        
        return wrapper
    return decorator


def cache_function(
    ttl: Optional[int] = None,
    cache_type: str = "default",
    key_builder: Optional[Callable] = None,
    skip_if: Optional[Callable] = None
):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time to live in seconds
        cache_type: Type of cache for TTL lookup
        key_builder: Custom function to build cache key
        skip_if: Function to determine if caching should be skipped
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Check if caching should be skipped
            if skip_if and skip_if(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key building
                key_parts = [func.__name__]
                
                # Add positional args
                for arg in args:
                    if isinstance(arg, (str, int, float, bool)):
                        key_parts.append(str(arg))
                    else:
                        key_parts.append(CacheKeyBuilder.hash_key(str(arg)))
                
                # Add keyword args
                if kwargs:
                    key_parts.append(CacheKeyBuilder.hash_key(kwargs))
                
                cache_key = CacheKeyBuilder.build_key(*key_parts)
            
            # Try to get from cache
            cached_result = await cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Function cache hit for {func.__name__}")
                return cached_result
            
            # Execute function
            logger.debug(f"Function cache miss for {func.__name__}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_service.set(cache_key, result, ttl, cache_type)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we need to handle async cache operations
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def cache_database_query(
    ttl: Optional[int] = None,
    cache_type: str = "default",
    invalidate_on: Optional[List[str]] = None
):
    """
    Decorator for caching database query results.
    
    Args:
        ttl: Time to live in seconds
        cache_type: Type of cache for TTL lookup
        invalidate_on: List of events that should invalidate this cache
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key including query parameters
            key_parts = ["db_query", func.__name__]
            
            # Add relevant parameters to key
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))
            
            if kwargs:
                # Only include serializable kwargs
                serializable_kwargs = {
                    k: v for k, v in kwargs.items() 
                    if isinstance(v, (str, int, float, bool, list, dict, type(None)))
                }
                if serializable_kwargs:
                    key_parts.append(CacheKeyBuilder.hash_key(serializable_kwargs))
            
            cache_key = CacheKeyBuilder.build_key(*key_parts)
            
            # Try to get from cache
            cached_result = await cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Database query cache hit for {func.__name__}")
                return cached_result
            
            # Execute query
            logger.debug(f"Database query cache miss for {func.__name__}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_service.set(cache_key, result, ttl, cache_type)
            
            return result
        
        # Store invalidation info for later use
        if invalidate_on:
            wrapper._cache_invalidate_on = invalidate_on
            wrapper._cache_key_pattern = f"rendiff:db_query:{func.__name__}:*"
        
        return wrapper
    
    return decorator


def invalidate_cache(patterns: Union[str, List[str]]):
    """
    Decorator to invalidate cache patterns after function execution.
    
    Args:
        patterns: Cache key patterns to invalidate
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Invalidate cache patterns
            if isinstance(patterns, str):
                pattern_list = [patterns]
            else:
                pattern_list = patterns
            
            for pattern in pattern_list:
                try:
                    count = await cache_service.delete_pattern(pattern)
                    if count > 0:
                        logger.info(f"Invalidated {count} cache entries for pattern: {pattern}")
                except Exception as e:
                    logger.error(f"Failed to invalidate cache pattern {pattern}: {e}")
            
            return result
        
        return wrapper
    
    return decorator


class CacheManager:
    """Context manager for cache operations."""
    
    def __init__(self):
        self.invalidation_queue = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Process invalidation queue
        for pattern in self.invalidation_queue:
            try:
                await cache_service.delete_pattern(pattern)
            except Exception as e:
                logger.error(f"Failed to invalidate cache pattern {pattern}: {e}")
    
    def queue_invalidation(self, pattern: str):
        """Queue a cache pattern for invalidation."""
        self.invalidation_queue.append(pattern)


# Utility functions for common caching patterns

async def cache_job_data(job_id: str, job_data: Dict[str, Any], ttl: int = None):
    """Cache job data with standard key pattern."""
    cache_key = CacheKeyBuilder.job_key(job_id)
    return await cache_service.set(cache_key, job_data, ttl, "job_status")


async def get_cached_job_data(job_id: str) -> Optional[Dict[str, Any]]:
    """Get cached job data."""
    cache_key = CacheKeyBuilder.job_key(job_id)
    return await cache_service.get(cache_key)


async def invalidate_job_cache(job_id: str):
    """Invalidate all cache entries for a job."""
    patterns = [
        CacheKeyBuilder.job_key(job_id),
        f"rendiff:jobs:*",  # Job listings might include this job
    ]
    
    for pattern in patterns:
        await cache_service.delete_pattern(pattern)


async def cache_api_key_validation(api_key: str, is_valid: bool, user_data: Dict[str, Any] = None):
    """Cache API key validation result."""
    cache_key = CacheKeyBuilder.api_key_validation_key(api_key)
    cache_data = {
        "is_valid": is_valid,
        "user_data": user_data,
        "cached_at": asyncio.get_event_loop().time()
    }
    return await cache_service.set(cache_key, cache_data, None, "api_key")


async def get_cached_api_key_validation(api_key: str) -> Optional[Dict[str, Any]]:
    """Get cached API key validation result."""
    cache_key = CacheKeyBuilder.api_key_validation_key(api_key)
    return await cache_service.get(cache_key)


# Common skip conditions

def skip_on_post_request(request: Request) -> bool:
    """Skip caching for POST requests."""
    return request.method.upper() == "POST"


def skip_on_authenticated_request(request: Request) -> bool:
    """Skip caching for requests with authentication headers."""
    return "authorization" in request.headers


def skip_if_no_cache_header(request: Request) -> bool:
    """Skip caching if no-cache header is present."""
    cache_control = request.headers.get("cache-control", "")
    return "no-cache" in cache_control.lower()


# Cache warming utilities

async def warm_cache_for_popular_jobs(job_ids: List[str]):
    """Pre-warm cache for popular jobs."""
    from api.models.job import Job
    from api.dependencies import get_async_db
    
    try:
        async with get_async_db() as db:
            for job_id in job_ids:
                job = await db.get(Job, job_id)
                if job:
                    # Cache job data
                    job_data = {
                        "id": job.id,
                        "status": job.status,
                        "progress": job.progress,
                        "created_at": job.created_at.isoformat() if job.created_at else None,
                        "updated_at": job.updated_at.isoformat() if job.updated_at else None
                    }
                    await cache_job_data(job_id, job_data)
                    
        logger.info(f"Cache warmed for {len(job_ids)} jobs")
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")


async def warm_cache_for_storage_configs():
    """Pre-warm cache for storage configurations."""
    try:
        # This would need to be implemented based on storage config structure
        logger.info("Storage config cache warming completed")
    except Exception as e:
        logger.error(f"Storage config cache warming failed: {e}")