"""
Cache management and monitoring endpoints
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import structlog

from api.dependencies import require_api_key
from api.cache import get_cache_service, CacheService
from api.models.api_key import ApiKeyUser
from api.dependencies import get_current_user

logger = structlog.get_logger()
router = APIRouter()


@router.get("/cache/stats", response_model=Dict[str, Any])
async def get_cache_statistics(
    cache_service: CacheService = Depends(get_cache_service),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get cache statistics and metrics.
    Requires admin privileges.
    """
    user, api_key = user_data
    
    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    try:
        stats = await cache_service.get_stats()
        return {
            "cache_statistics": stats,
            "timestamp": cache_service.stats.to_dict(),
            "redis_connected": cache_service.connected,
            "fallback_active": not cache_service.connected
        }
    except Exception as e:
        logger.error(f"Failed to get cache statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cache statistics"
        )


@router.post("/cache/clear")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="Pattern to clear (e.g., 'jobs:*'). If not provided, clears all cache."),
    cache_service: CacheService = Depends(get_cache_service),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Clear cache entries by pattern or clear all cache.
    Requires admin privileges.
    """
    user, api_key = user_data
    
    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    try:
        if pattern:
            # Clear specific pattern
            count = await cache_service.delete_pattern(f"rendiff:{pattern}")
            logger.info(f"Cleared {count} cache entries matching pattern: {pattern}")
            return {
                "message": f"Cleared {count} cache entries",
                "pattern": pattern,
                "entries_cleared": count
            }
        else:
            # Clear all cache
            success = await cache_service.clear_all()
            if success:
                logger.warning("All cache entries cleared by admin")
                return {
                    "message": "All cache entries cleared",
                    "pattern": "*",
                    "entries_cleared": "all"
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to clear cache"
                )
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.get("/cache/keys")
async def list_cache_keys(
    pattern: str = Query("*", description="Pattern to match keys (e.g., 'jobs:*')"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of keys to return"),
    cache_service: CacheService = Depends(get_cache_service),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    List cache keys matching a pattern.
    Requires admin privileges.
    """
    user, api_key = user_data
    
    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    try:
        keys = []
        
        if cache_service.redis_client and cache_service.connected:
            # Use Redis SCAN for efficient key listing
            redis_keys = await cache_service.redis_client.keys(f"rendiff:{pattern}")
            keys = redis_keys[:limit]
        else:
            # Use fallback cache
            fallback_keys = [
                key for key in cache_service.fallback_cache.keys()
                if pattern == "*" or pattern.replace("*", "") in key
            ]
            keys = fallback_keys[:limit]
        
        return {
            "keys": keys,
            "count": len(keys),
            "pattern": pattern,
            "limit": limit,
            "truncated": len(keys) == limit
        }
        
    except Exception as e:
        logger.error(f"Failed to list cache keys: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list cache keys: {str(e)}"
        )


@router.get("/cache/health")
async def cache_health_check(
    cache_service: CacheService = Depends(get_cache_service),
) -> Dict[str, Any]:
    """
    Check cache service health status.
    Public endpoint for monitoring.
    """
    try:
        # Test basic cache operations
        test_key = "health_check_test"
        test_value = "ok"
        
        # Set test value
        set_success = await cache_service.set(test_key, test_value, ttl=10)
        
        # Get test value
        retrieved_value = await cache_service.get(test_key)
        
        # Clean up test key
        await cache_service.delete(test_key)
        
        # Determine health status
        is_healthy = (
            set_success and 
            retrieved_value == test_value
        )
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "redis_connected": cache_service.connected,
            "fallback_active": not cache_service.connected,
            "test_operations": {
                "set": set_success,
                "get": retrieved_value == test_value,
                "delete": True
            }
        }
        
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {
            "status": "unhealthy",
            "redis_connected": False,
            "fallback_active": True,
            "error": str(e)
        }


@router.post("/cache/warm")
async def warm_cache(
    strategy: str = Query("popular_jobs", description="Cache warming strategy"),
    limit: Optional[int] = Query(50, ge=1, le=500, description="Number of items to warm"),
    cache_service: CacheService = Depends(get_cache_service),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Manually trigger cache warming.
    Requires admin privileges.
    """
    user, api_key = user_data
    
    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    try:
        items_warmed = 0
        
        if strategy == "popular_jobs":
            # Import here to avoid circular dependencies
            from api.decorators import warm_cache_for_popular_jobs
            from api.models.job import Job
            from api.dependencies import get_db
            from sqlalchemy import select
            
            # Get recent jobs to warm
            async for db in get_db():
                query = select(Job.id).order_by(Job.created_at.desc()).limit(limit)
                result = await db.execute(query)
                job_ids = [row[0] for row in result.fetchall()]
                
                if job_ids:
                    await warm_cache_for_popular_jobs(job_ids)
                    items_warmed = len(job_ids)
                break
        
        elif strategy == "storage_configs":
            from api.decorators import warm_cache_for_storage_configs
            await warm_cache_for_storage_configs()
            items_warmed = 1  # Number of config types warmed
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown warming strategy: {strategy}"
            )
        
        logger.info(f"Cache warming completed: {strategy}, {items_warmed} items")
        
        return {
            "message": "Cache warming completed",
            "strategy": strategy,
            "items_warmed": items_warmed,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cache warming failed: {str(e)}"
        )


@router.get("/cache/config")
async def get_cache_configuration(
    cache_service: CacheService = Depends(get_cache_service),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get current cache configuration.
    Requires admin privileges.
    """
    user, api_key = user_data
    
    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    try:
        return {
            "configuration": {
                "default_ttls": cache_service.default_ttls,
                "max_fallback_size": cache_service.max_fallback_size,
                "redis_connected": cache_service.connected,
                "fallback_cache_enabled": True,
                "supported_operations": [
                    "get", "set", "delete", "exists", 
                    "increment", "delete_pattern", "clear_all"
                ]
            },
            "current_state": {
                "fallback_cache_size": len(cache_service.fallback_cache),
                "stats": cache_service.stats.to_dict()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get cache configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cache configuration"
        )


@router.post("/cache/test")
async def test_cache_performance(
    operations: int = Query(100, ge=1, le=1000, description="Number of operations to perform"),
    cache_service: CacheService = Depends(get_cache_service),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Test cache performance with synthetic workload.
    Requires admin privileges.
    """
    user, api_key = user_data
    
    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    try:
        import time
        import asyncio
        
        # Performance test
        start_time = time.time()
        
        # Test data
        test_data = {"test": "performance", "number": 42, "list": [1, 2, 3]}
        
        # Perform set operations
        set_tasks = [
            cache_service.set(f"perf_test_{i}", test_data, ttl=60)
            for i in range(operations)
        ]
        set_results = await asyncio.gather(*set_tasks)
        set_time = time.time()
        
        # Perform get operations
        get_tasks = [
            cache_service.get(f"perf_test_{i}")
            for i in range(operations)
        ]
        get_results = await asyncio.gather(*get_tasks)
        get_time = time.time()
        
        # Cleanup
        delete_tasks = [
            cache_service.delete(f"perf_test_{i}")
            for i in range(operations)
        ]
        await asyncio.gather(*delete_tasks)
        end_time = time.time()
        
        # Calculate metrics
        total_time = end_time - start_time
        set_duration = set_time - start_time
        get_duration = get_time - set_time
        
        successful_sets = sum(1 for r in set_results if r)
        successful_gets = sum(1 for r in get_results if r == test_data)
        
        return {
            "performance_test": {
                "operations": operations,
                "total_time": round(total_time, 3),
                "set_duration": round(set_duration, 3),
                "get_duration": round(get_duration, 3),
                "successful_sets": successful_sets,
                "successful_gets": successful_gets,
                "ops_per_second": round(operations * 2 / total_time, 2),
                "cache_backend": "redis" if cache_service.connected else "fallback"
            },
            "cache_state": {
                "redis_connected": cache_service.connected,
                "fallback_cache_size": len(cache_service.fallback_cache)
            }
        }
        
    except Exception as e:
        logger.error(f"Cache performance test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Performance test failed: {str(e)}"
        )


# Add cache monitoring middleware for automatic metrics collection
async def cache_metrics_middleware(request, call_next):
    """Middleware to collect cache metrics automatically."""
    try:
        # Record request start
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Record response time
        response_time = time.time() - start_time
        
        # Log cache-related metrics if this was a cached endpoint
        if hasattr(response, 'headers') and 'X-Cache-Status' in response.headers:
            cache_status = response.headers['X-Cache-Status']
            logger.info(
                "Cache operation",
                path=request.url.path,
                method=request.method,
                cache_status=cache_status,
                response_time=response_time
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Cache metrics middleware error: {e}")
        # Don't break the request if metrics collection fails
        return await call_next(request)