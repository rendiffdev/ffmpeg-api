"""
Redis-based caching service for the Rendiff FFmpeg API

Provides distributed caching capabilities for:
- API responses and database queries
- Configuration data and storage backend status
- Video analysis results and computation caching
- Rate limiting and session management
"""
import asyncio
import json
import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable
from functools import wraps

# Use structlog if available, fall back to standard logging
try:
    import structlog
    logger = structlog.get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    try:
        import redis
        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False

try:
    from api.config import settings
except ImportError:
    # Mock settings for testing without dependencies
    class MockSettings:
        REDIS_URL = None
        REDIS_HOST = "localhost"
        REDIS_PORT = 6379
        REDIS_DB = 0
        DEBUG = False
    
    settings = MockSettings()


class CacheKeyBuilder:
    """Utility class for building consistent cache keys."""
    
    @staticmethod
    def build_key(*parts: str, prefix: str = "rendiff") -> str:
        """Build a cache key from multiple parts."""
        clean_parts = [str(part).replace(":", "_").replace(" ", "_") for part in parts]
        return f"{prefix}:{':'.join(clean_parts)}"
    
    @staticmethod
    def hash_key(data: Union[str, dict, list]) -> str:
        """Create a hash-based key for complex data."""
        if isinstance(data, str):
            content = data
        else:
            content = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    @classmethod
    def job_key(cls, job_id: str) -> str:
        """Build cache key for job data."""
        return cls.build_key("job", job_id)
    
    @classmethod
    def job_list_key(cls, api_key: str, **filters) -> str:
        """Build cache key for job listings."""
        filter_hash = cls.hash_key(filters) if filters else "all"
        return cls.build_key("jobs", api_key, filter_hash)
    
    @classmethod
    def api_key_validation_key(cls, api_key: str) -> str:
        """Build cache key for API key validation."""
        key_hash = cls.hash_key(api_key)
        return cls.build_key("auth", "api_key", key_hash)
    
    @classmethod
    def storage_config_key(cls, backend_name: str) -> str:
        """Build cache key for storage configuration."""
        return cls.build_key("storage", "config", backend_name)
    
    @classmethod
    def video_analysis_key(cls, file_path: str, analysis_type: str) -> str:
        """Build cache key for video analysis results."""
        path_hash = cls.hash_key(file_path)
        return cls.build_key("analysis", analysis_type, path_hash)
    
    @classmethod
    def rate_limit_key(cls, identifier: str, window: str) -> str:
        """Build cache key for rate limiting."""
        return cls.build_key("ratelimit", identifier, window)


class CacheStats:
    """Cache statistics tracking."""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "hit_rate": round(self.hit_rate, 2),
            "total_operations": self.hits + self.misses + self.sets + self.deletes
        }


class CacheService:
    """Redis-based caching service with fallback to in-memory caching."""
    
    def __init__(self):
        self.redis_client: Optional[Redis] = None
        self.fallback_cache: Dict[str, tuple] = {}  # {key: (value, expires_at)}
        self.stats = CacheStats()
        self.max_fallback_size = 1000
        self.connected = False
        
        # Default TTL values (in seconds)
        self.default_ttls = {
            "job_status": 30,           # Job status lookups
            "job_list": 60,             # Job listing results
            "api_key": 300,             # API key validation
            "storage_config": 3600,     # Storage configuration
            "video_analysis": 86400,    # Video analysis results (24h)
            "rate_limit": 3600,         # Rate limiting windows
            "default": 300              # Default TTL
        }
    
    async def initialize(self) -> bool:
        """Initialize Redis connection."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using fallback in-memory cache")
            return False
        
        try:
            # Build Redis URL from settings
            redis_url = getattr(settings, 'REDIS_URL', None)
            if not redis_url:
                redis_host = getattr(settings, 'REDIS_HOST', 'localhost')
                redis_port = getattr(settings, 'REDIS_PORT', 6379)
                redis_db = getattr(settings, 'REDIS_DB', 0)
                redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
            
            self.redis_client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            logger.info("Redis cache service initialized successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using fallback cache")
            self.redis_client = None
            self.connected = False
            return False
    
    async def cleanup(self):
        """Clean up Redis connection."""
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
        self.fallback_cache.clear()
    
    def _cleanup_fallback_cache(self):
        """Clean up expired entries from fallback cache."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, (_, expires_at) in self.fallback_cache.items()
            if expires_at and expires_at < now
        ]
        for key in expired_keys:
            del self.fallback_cache[key]
        
        # Limit cache size
        if len(self.fallback_cache) > self.max_fallback_size:
            # Remove oldest entries
            sorted_items = sorted(
                self.fallback_cache.items(),
                key=lambda x: x[1][1] or datetime.max
            )
            excess_count = len(self.fallback_cache) - self.max_fallback_size
            for key, _ in sorted_items[:excess_count]:
                del self.fallback_cache[key]
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            if self.redis_client and self.connected:
                # Try Redis first
                try:
                    value = await self.redis_client.get(key)
                    if value is not None:
                        self.stats.hits += 1
                        try:
                            return json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            # Try pickle if JSON fails
                            return pickle.loads(value.encode('latin1'))
                    else:
                        self.stats.misses += 1
                        return None
                except Exception as e:
                    logger.warning(f"Redis get error for key {key}: {e}")
                    self.stats.errors += 1
                    # Fall through to fallback cache
            
            # Use fallback cache
            self._cleanup_fallback_cache()
            if key in self.fallback_cache:
                value, expires_at = self.fallback_cache[key]
                if expires_at is None or expires_at > datetime.utcnow():
                    self.stats.hits += 1
                    return value
                else:
                    del self.fallback_cache[key]
            
            self.stats.misses += 1
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.stats.errors += 1
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        cache_type: str = "default"
    ) -> bool:
        """Set value in cache."""
        try:
            if ttl is None:
                ttl = self.default_ttls.get(cache_type, self.default_ttls["default"])
            
            if self.redis_client and self.connected:
                # Try Redis first
                try:
                    # Serialize value
                    try:
                        serialized = json.dumps(value, separators=(',', ':'))
                    except (TypeError, ValueError):
                        # Use pickle for complex objects
                        serialized = pickle.dumps(value).decode('latin1')
                    
                    await self.redis_client.setex(key, ttl, serialized)
                    self.stats.sets += 1
                    return True
                except Exception as e:
                    logger.warning(f"Redis set error for key {key}: {e}")
                    self.stats.errors += 1
                    # Fall through to fallback cache
            
            # Use fallback cache
            self._cleanup_fallback_cache()
            expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl else None
            self.fallback_cache[key] = (value, expires_at)
            self.stats.sets += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self.stats.errors += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            success = False
            
            if self.redis_client and self.connected:
                try:
                    result = await self.redis_client.delete(key)
                    success = result > 0
                except Exception as e:
                    logger.warning(f"Redis delete error for key {key}: {e}")
                    self.stats.errors += 1
            
            # Also remove from fallback cache
            if key in self.fallback_cache:
                del self.fallback_cache[key]
                success = True
            
            if success:
                self.stats.deletes += 1
            
            return success
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            self.stats.errors += 1
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        try:
            count = 0
            
            if self.redis_client and self.connected:
                try:
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        count += await self.redis_client.delete(*keys)
                except Exception as e:
                    logger.warning(f"Redis delete pattern error for {pattern}: {e}")
                    self.stats.errors += 1
            
            # Also check fallback cache
            fallback_keys = [k for k in self.fallback_cache.keys() if pattern.replace('*', '') in k]
            for key in fallback_keys:
                del self.fallback_cache[key]
                count += 1
            
            self.stats.deletes += count
            return count
            
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            self.stats.errors += 1
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            if self.redis_client and self.connected:
                try:
                    return await self.redis_client.exists(key) > 0
                except Exception as e:
                    logger.warning(f"Redis exists error for key {key}: {e}")
            
            # Check fallback cache
            self._cleanup_fallback_cache()
            return key in self.fallback_cache
            
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment a numeric value in cache."""
        try:
            if self.redis_client and self.connected:
                try:
                    # Use Redis INCR for atomic operations
                    result = await self.redis_client.incrby(key, amount)
                    if ttl:
                        await self.redis_client.expire(key, ttl)
                    return result
                except Exception as e:
                    logger.warning(f"Redis increment error for key {key}: {e}")
            
            # Fallback implementation
            current = await self.get(key) or 0
            new_value = int(current) + amount
            await self.set(key, new_value, ttl)
            return new_value
            
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return amount
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self.stats.to_dict()
        stats.update({
            "redis_connected": self.connected,
            "fallback_cache_size": len(self.fallback_cache),
            "fallback_max_size": self.max_fallback_size
        })
        
        if self.redis_client and self.connected:
            try:
                redis_info = await self.redis_client.info('memory')
                stats.update({
                    "redis_memory_used": redis_info.get('used_memory_human', 'N/A'),
                    "redis_memory_peak": redis_info.get('used_memory_peak_human', 'N/A'),
                    "redis_keyspace_hits": redis_info.get('keyspace_hits', 0),
                    "redis_keyspace_misses": redis_info.get('keyspace_misses', 0)
                })
            except Exception as e:
                logger.warning(f"Could not get Redis stats: {e}")
        
        return stats
    
    async def clear_all(self) -> bool:
        """Clear all cache entries (use with caution!)."""
        try:
            success = True
            
            if self.redis_client and self.connected:
                try:
                    await self.redis_client.flushdb()
                except Exception as e:
                    logger.error(f"Redis flush error: {e}")
                    success = False
            
            self.fallback_cache.clear()
            logger.warning("Cache cleared completely")
            return success
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False


# Global cache service instance
cache_service = CacheService()


async def get_cache_service() -> CacheService:
    """Dependency injection for cache service."""
    if not cache_service.connected and cache_service.redis_client is None:
        await cache_service.initialize()
    return cache_service