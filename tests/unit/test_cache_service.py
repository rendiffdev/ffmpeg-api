"""
Tests for cache service functionality
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from api.cache import CacheService, CacheKeyBuilder, CacheStats


class TestCacheKeyBuilder:
    """Test cache key building utilities."""
    
    def test_build_key_basic(self):
        """Test basic key building."""
        key = CacheKeyBuilder.build_key("test", "data")
        assert key == "rendiff:test:data"
    
    def test_build_key_with_prefix(self):
        """Test key building with custom prefix."""
        key = CacheKeyBuilder.build_key("test", "data", prefix="custom")
        assert key == "custom:test:data"
    
    def test_build_key_sanitization(self):
        """Test key sanitization of invalid characters."""
        key = CacheKeyBuilder.build_key("test:data", "with spaces")
        assert key == "rendiff:test_data:with_spaces"
    
    def test_hash_key_string(self):
        """Test hash key generation from string."""
        hash1 = CacheKeyBuilder.hash_key("test string")
        hash2 = CacheKeyBuilder.hash_key("test string")
        hash3 = CacheKeyBuilder.hash_key("different string")
        
        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 16
    
    def test_hash_key_dict(self):
        """Test hash key generation from dictionary."""
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}  # Different order
        data3 = {"a": 1, "b": 3}  # Different value
        
        hash1 = CacheKeyBuilder.hash_key(data1)
        hash2 = CacheKeyBuilder.hash_key(data2)
        hash3 = CacheKeyBuilder.hash_key(data3)
        
        assert hash1 == hash2  # Order shouldn't matter
        assert hash1 != hash3
    
    def test_specialized_key_builders(self):
        """Test specialized key builder methods."""
        # Job key
        job_key = CacheKeyBuilder.job_key("job-123")
        assert job_key == "rendiff:job:job-123"
        
        # API key validation
        api_key = CacheKeyBuilder.api_key_validation_key("test-key")
        assert api_key.startswith("rendiff:auth:api_key:")
        
        # Storage config
        storage_key = CacheKeyBuilder.storage_config_key("s3")
        assert storage_key == "rendiff:storage:config:s3"
        
        # Video analysis
        analysis_key = CacheKeyBuilder.video_analysis_key("/path/to/video.mp4", "complexity")
        assert analysis_key.startswith("rendiff:analysis:complexity:")
        
        # Rate limiting
        rate_key = CacheKeyBuilder.rate_limit_key("user-123", "hourly")
        assert rate_key == "rendiff:ratelimit:user-123:hourly"


class TestCacheStats:
    """Test cache statistics functionality."""
    
    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0
        assert stats.deletes == 0
        assert stats.errors == 0
        assert stats.hit_rate == 0.0
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats()
        
        # No operations yet
        assert stats.hit_rate == 0.0
        
        # Add some hits and misses
        stats.hits = 70
        stats.misses = 30
        assert stats.hit_rate == 70.0
        
        # Only hits
        stats.hits = 100
        stats.misses = 0
        assert stats.hit_rate == 100.0
        
        # Only misses
        stats.hits = 0
        stats.misses = 100
        assert stats.hit_rate == 0.0
    
    def test_to_dict(self):
        """Test stats dictionary conversion."""
        stats = CacheStats()
        stats.hits = 10
        stats.misses = 5
        stats.sets = 8
        stats.deletes = 2
        stats.errors = 1
        
        data = stats.to_dict()
        
        assert data["hits"] == 10
        assert data["misses"] == 5
        assert data["sets"] == 8
        assert data["deletes"] == 2
        assert data["errors"] == 1
        assert data["hit_rate"] == round(10/15 * 100, 2)
        assert data["total_operations"] == 26


class TestCacheService:
    """Test cache service functionality."""
    
    @pytest.fixture
    def cache_service(self):
        """Create cache service instance."""
        return CacheService()
    
    @pytest.mark.asyncio
    async def test_fallback_cache_basic_operations(self, cache_service):
        """Test basic cache operations with fallback cache."""
        # Service starts disconnected, should use fallback
        assert not cache_service.connected
        
        # Test set and get
        await cache_service.set("test_key", "test_value")
        value = await cache_service.get("test_key")
        assert value == "test_value"
        assert cache_service.stats.sets == 1
        assert cache_service.stats.hits == 1
        
        # Test cache miss
        missing = await cache_service.get("missing_key")
        assert missing is None
        assert cache_service.stats.misses == 1
    
    @pytest.mark.asyncio
    async def test_fallback_cache_ttl(self, cache_service):
        """Test TTL handling in fallback cache."""
        # Set with very short TTL
        await cache_service.set("expiring_key", "value", ttl=1)
        
        # Should be available immediately
        value = await cache_service.get("expiring_key")
        assert value == "value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        value = await cache_service.get("expiring_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_fallback_cache_cleanup(self, cache_service):
        """Test fallback cache cleanup."""
        # Add multiple items
        for i in range(10):
            await cache_service.set(f"key_{i}", f"value_{i}")
        
        assert len(cache_service.fallback_cache) == 10
        
        # Add expired items
        await cache_service.set("expired", "value", ttl=1)
        await asyncio.sleep(1.1)
        
        # Trigger cleanup by adding new item
        await cache_service.set("new_key", "new_value")
        
        # Expired item should be cleaned up
        assert "expired" not in cache_service.fallback_cache
    
    @pytest.mark.asyncio
    async def test_fallback_cache_size_limit(self, cache_service):
        """Test fallback cache size limiting."""
        # Set a small max size for testing
        cache_service.max_fallback_size = 5
        
        # Add more items than the limit
        for i in range(10):
            await cache_service.set(f"key_{i}", f"value_{i}")
        
        # Should not exceed max size
        assert len(cache_service.fallback_cache) <= cache_service.max_fallback_size
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_service):
        """Test cache deletion."""
        # Set and verify
        await cache_service.set("delete_me", "value")
        assert await cache_service.get("delete_me") == "value"
        
        # Delete and verify
        success = await cache_service.delete("delete_me")
        assert success
        assert await cache_service.get("delete_me") is None
        assert cache_service.stats.deletes == 1
    
    @pytest.mark.asyncio
    async def test_cache_exists(self, cache_service):
        """Test cache key existence check."""
        # Non-existent key
        assert not await cache_service.exists("non_existent")
        
        # Set and check
        await cache_service.set("existing_key", "value")
        assert await cache_service.exists("existing_key")
        
        # Delete and check
        await cache_service.delete("existing_key")
        assert not await cache_service.exists("existing_key")
    
    @pytest.mark.asyncio
    async def test_cache_increment(self, cache_service):
        """Test cache increment operations."""
        # Increment non-existent key
        result = await cache_service.increment("counter")
        assert result == 1
        
        # Increment existing key
        result = await cache_service.increment("counter", 5)
        assert result == 6
        
        # Verify final value
        value = await cache_service.get("counter")
        assert value == 6
    
    @pytest.mark.asyncio
    async def test_cache_delete_pattern(self, cache_service):
        """Test pattern-based deletion."""
        # Set multiple keys with pattern
        await cache_service.set("test:1", "value1")
        await cache_service.set("test:2", "value2")
        await cache_service.set("other:1", "value3")
        
        # Delete by pattern
        count = await cache_service.delete_pattern("test:*")
        assert count == 2
        
        # Verify deletion
        assert await cache_service.get("test:1") is None
        assert await cache_service.get("test:2") is None
        assert await cache_service.get("other:1") == "value3"
    
    @pytest.mark.asyncio
    async def test_cache_serialization(self, cache_service):
        """Test caching of different data types."""
        test_data = [
            ("string", "test string"),
            ("integer", 42),
            ("float", 3.14),
            ("boolean", True),
            ("list", [1, 2, 3]),
            ("dict", {"key": "value", "nested": {"a": 1}}),
            ("none", None),
        ]
        
        for key, value in test_data:
            await cache_service.set(key, value)
            retrieved = await cache_service.get(key)
            assert retrieved == value, f"Failed for {key}: {value}"
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_service):
        """Test cache statistics collection."""
        # Perform various operations
        await cache_service.set("key1", "value1")
        await cache_service.set("key2", "value2")
        await cache_service.get("key1")  # hit
        await cache_service.get("key1")  # hit
        await cache_service.get("missing")  # miss
        await cache_service.delete("key1")
        
        stats = await cache_service.get_stats()
        
        assert stats["hits"] >= 2
        assert stats["misses"] >= 1
        assert stats["sets"] >= 2
        assert stats["deletes"] >= 1
        assert "hit_rate" in stats
        assert "fallback_cache_size" in stats
    
    @pytest.mark.asyncio
    async def test_cache_clear_all(self, cache_service):
        """Test clearing all cache entries."""
        # Add some data
        await cache_service.set("key1", "value1")
        await cache_service.set("key2", "value2")
        
        # Verify data exists
        assert await cache_service.get("key1") == "value1"
        assert await cache_service.get("key2") == "value2"
        
        # Clear all
        success = await cache_service.clear_all()
        assert success
        
        # Verify data is gone
        assert await cache_service.get("key1") is None
        assert await cache_service.get("key2") is None
    
    @pytest.mark.asyncio
    @patch('api.cache.redis')
    async def test_redis_initialization_success(self, mock_redis, cache_service):
        """Test successful Redis initialization."""
        # Mock Redis client
        mock_client = AsyncMock()
        mock_redis.from_url.return_value = mock_client
        mock_client.ping.return_value = True
        
        success = await cache_service.initialize()
        
        assert success
        assert cache_service.connected
        assert cache_service.redis_client == mock_client
        mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('api.cache.redis')
    async def test_redis_initialization_failure(self, mock_redis, cache_service):
        """Test Redis initialization failure."""
        # Mock Redis connection failure
        mock_redis.from_url.side_effect = Exception("Connection failed")
        
        success = await cache_service.initialize()
        
        assert not success
        assert not cache_service.connected
        assert cache_service.redis_client is None
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_service):
        """Test cache error handling."""
        # Mock a method to raise an exception
        original_get = cache_service.get
        
        async def failing_get(key):
            if key == "error_key":
                raise Exception("Simulated error")
            return await original_get(key)
        
        cache_service.get = failing_get
        
        # Should handle error gracefully
        result = await cache_service.get("error_key")
        assert result is None
        
        # Normal operation should still work
        await cache_service.set("normal_key", "value")
        result = await cache_service.get("normal_key")
        assert result == "value"


class TestCacheIntegration:
    """Integration tests for cache functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_service_lifecycle(self):
        """Test complete cache service lifecycle."""
        cache = CacheService()
        
        try:
            # Initialize
            await cache.initialize()
            
            # Test operations
            await cache.set("lifecycle_test", {"data": "value"})
            result = await cache.get("lifecycle_test")
            assert result == {"data": "value"}
            
            # Test stats
            stats = await cache.get_stats()
            assert stats["sets"] >= 1
            assert stats["hits"] >= 1
            
        finally:
            # Cleanup
            await cache.cleanup()
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test concurrent cache operations."""
        cache = CacheService()
        
        try:
            await cache.initialize()
            
            # Concurrent sets
            async def set_data(index):
                await cache.set(f"concurrent_{index}", f"value_{index}")
                return await cache.get(f"concurrent_{index}")
            
            # Run multiple operations concurrently
            tasks = [set_data(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            # Verify all operations succeeded
            for i, result in enumerate(results):
                assert result == f"value_{i}"
            
        finally:
            await cache.cleanup()
    
    @pytest.mark.asyncio
    async def test_cache_with_different_ttls(self):
        """Test cache behavior with different TTL values."""
        cache = CacheService()
        
        try:
            await cache.initialize()
            
            # Set items with different TTLs
            await cache.set("short_ttl", "value1", ttl=1)
            await cache.set("long_ttl", "value2", ttl=10)
            await cache.set("no_ttl", "value3")
            
            # All should be available immediately
            assert await cache.get("short_ttl") == "value1"
            assert await cache.get("long_ttl") == "value2"
            assert await cache.get("no_ttl") == "value3"
            
            # Wait for short TTL to expire
            await asyncio.sleep(1.1)
            
            # Check expiration
            assert await cache.get("short_ttl") is None
            assert await cache.get("long_ttl") == "value2"
            assert await cache.get("no_ttl") == "value3"
            
        finally:
            await cache.cleanup()