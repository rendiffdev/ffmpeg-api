#!/usr/bin/env python3
"""
Basic cache functionality test without external dependencies
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_cache_service_basic():
    """Test basic cache service functionality."""
    print("🔧 Testing cache service basic functionality...")
    
    try:
        from api.cache import CacheService, CacheKeyBuilder, CacheStats
        
        # Test CacheKeyBuilder
        key = CacheKeyBuilder.build_key("test", "data")
        assert key == "rendiff:test:data"
        
        job_key = CacheKeyBuilder.job_key("job-123")
        assert job_key == "rendiff:job:job-123"
        
        hash_key = CacheKeyBuilder.hash_key("test data")
        assert len(hash_key) == 16
        
        print("✅ Cache key building works correctly")
        
        # Test CacheStats
        stats = CacheStats()
        assert stats.hit_rate == 0.0
        
        stats.hits = 7
        stats.misses = 3
        assert stats.hit_rate == 70.0
        
        stats_dict = stats.to_dict()
        assert stats_dict["hits"] == 7
        assert stats_dict["hit_rate"] == 70.0
        
        print("✅ Cache statistics work correctly")
        
        # Test CacheService (fallback mode)
        cache = CacheService()
        
        # Should start disconnected (using fallback cache)
        assert not cache.connected
        
        # Test basic operations
        await cache.set("test_key", "test_value")
        value = await cache.get("test_key")
        assert value == "test_value"
        
        # Test cache miss
        missing = await cache.get("missing_key")
        assert missing is None
        
        # Test exists
        assert await cache.exists("test_key") is True
        assert await cache.exists("missing_key") is False
        
        # Test delete
        success = await cache.delete("test_key")
        assert success is True
        assert await cache.get("test_key") is None
        
        print("✅ Cache service basic operations work correctly")
        
        # Test increment
        result = await cache.increment("counter")
        assert result == 1
        
        result = await cache.increment("counter", 5)
        assert result == 6
        
        value = await cache.get("counter")
        assert value == 6
        
        print("✅ Cache increment operations work correctly")
        
        # Test pattern deletion
        await cache.set("test:1", "value1")
        await cache.set("test:2", "value2")
        await cache.set("other:1", "value3")
        
        count = await cache.delete_pattern("test:*")
        assert count == 2
        
        assert await cache.get("test:1") is None
        assert await cache.get("test:2") is None
        assert await cache.get("other:1") == "value3"
        
        print("✅ Cache pattern deletion works correctly")
        
        # Test statistics
        stats = await cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "fallback_cache_size" in stats
        
        print("✅ Cache statistics collection works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache service test failed: {e}")
        return False

async def test_cache_decorators():
    """Test cache decorators basic functionality."""
    print("🎭 Testing cache decorators...")
    
    try:
        from api.decorators import cache_function, CacheKeyBuilder
        
        # Test basic function caching (mock cache service)
        call_count = 0
        
        class MockCacheService:
            def __init__(self):
                self.cache = {}
            
            async def get(self, key):
                return self.cache.get(key)
            
            async def set(self, key, value, ttl=None, cache_type=None):
                self.cache[key] = value
                return True
        
        # Replace cache service with mock
        import api.decorators
        original_cache_service = api.decorators.cache_service
        api.decorators.cache_service = MockCacheService()
        
        try:
            @cache_function(ttl=60)
            async def expensive_function(x, y):
                nonlocal call_count
                call_count += 1
                return x + y
            
            # First call should execute function
            result1 = await expensive_function(1, 2)
            assert result1 == 3
            assert call_count == 1
            
            # Second call should use cache
            result2 = await expensive_function(1, 2)
            assert result2 == 3
            assert call_count == 1  # Function not called again
            
            print("✅ Function caching decorator works correctly")
            
        finally:
            # Restore original cache service
            api.decorators.cache_service = original_cache_service
        
        return True
        
    except Exception as e:
        print(f"❌ Cache decorators test failed: {e}")
        return False

async def test_cache_utilities():
    """Test cache utility functions."""
    print("🛠️ Testing cache utilities...")
    
    try:
        from api.decorators import (
            skip_on_post_request, skip_on_authenticated_request, 
            skip_if_no_cache_header
        )
        
        # Mock request objects
        class MockRequest:
            def __init__(self, method="GET", headers=None):
                self.method = method
                self.headers = headers or {}
        
        # Test skip conditions
        post_request = MockRequest("POST")
        get_request = MockRequest("GET")
        
        assert skip_on_post_request(post_request) is True
        assert skip_on_post_request(get_request) is False
        
        auth_request = MockRequest(headers={"authorization": "Bearer token"})
        no_auth_request = MockRequest()
        
        assert skip_on_authenticated_request(auth_request) is True
        assert skip_on_authenticated_request(no_auth_request) is False
        
        no_cache_request = MockRequest(headers={"cache-control": "no-cache"})
        cache_request = MockRequest()
        
        assert skip_if_no_cache_header(no_cache_request) is True
        assert skip_if_no_cache_header(cache_request) is False
        
        print("✅ Cache skip conditions work correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache utilities test failed: {e}")
        return False

async def test_cache_ttl_behavior():
    """Test cache TTL behavior with fallback cache."""
    print("⏰ Testing cache TTL behavior...")
    
    try:
        from api.cache import CacheService
        import asyncio
        
        cache = CacheService()
        
        # Set with short TTL (1 second)
        await cache.set("expiring_key", "value", ttl=1)
        
        # Should be available immediately
        value = await cache.get("expiring_key")
        assert value == "value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired in fallback cache
        value = await cache.get("expiring_key")
        assert value is None
        
        print("✅ Cache TTL behavior works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache TTL test failed: {e}")
        return False

async def test_cache_data_types():
    """Test caching of different data types."""
    print("📊 Testing cache data type handling...")
    
    try:
        from api.cache import CacheService
        
        cache = CacheService()
        
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
            await cache.set(key, value)
            retrieved = await cache.get(key)
            assert retrieved == value, f"Failed for {key}: {value} != {retrieved}"
        
        print("✅ Cache data type handling works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache data types test failed: {e}")
        return False

async def main():
    """Run all cache tests."""
    print("🧪 Basic Cache Functionality Tests")
    print("=" * 60)
    
    tests = [
        test_cache_service_basic,
        test_cache_decorators,
        test_cache_utilities,
        test_cache_ttl_behavior,
        test_cache_data_types,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Add spacing
    
    print("=" * 60)
    print("CACHE TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("🎉 All cache tests passed!")
        return 0
    else:
        success_rate = (passed / (passed + failed)) * 100
        print(f"Success rate: {success_rate:.1f}%")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)