"""
Tests for cache decorators and utilities
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from api.decorators import (
    cache_response, cache_function, cache_database_query, invalidate_cache,
    CacheManager, cache_job_data, get_cached_job_data, invalidate_job_cache,
    cache_api_key_validation, get_cached_api_key_validation,
    skip_on_post_request, skip_on_authenticated_request, skip_if_no_cache_header
)


class TestCacheDecorators:
    """Test cache decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_function_decorator(self):
        """Test function caching decorator."""
        call_count = 0
        
        @cache_function(ttl=60, cache_type="test")
        async def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.get.return_value = None  # Cache miss first time
            mock_cache.set.return_value = True
            
            # First call - should execute function
            result1 = await expensive_function(1, 2)
            assert result1 == 3
            assert call_count == 1
            
            # Mock cache hit for second call
            mock_cache.get.return_value = 3
            
            # Second call - should use cache
            result2 = await expensive_function(1, 2)
            assert result2 == 3
            assert call_count == 1  # Function not called again
            
            # Verify cache operations
            mock_cache.get.assert_called()
            mock_cache.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_cache_function_with_different_args(self):
        """Test function caching with different arguments."""
        call_count = 0
        
        @cache_function(ttl=60)
        async def test_function(a, b=None):
            nonlocal call_count
            call_count += 1
            return f"{a}_{b}"
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set.return_value = True
            
            # Different arguments should create different cache keys
            await test_function("x", b="y")
            await test_function("a", b="b")
            
            assert call_count == 2
            assert mock_cache.set.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_function_skip_condition(self):
        """Test function caching with skip condition."""
        call_count = 0
        
        def skip_if_negative(x, y):
            return x < 0 or y < 0
        
        @cache_function(ttl=60, skip_if=skip_if_negative)
        async def test_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        with patch('api.decorators.cache_service') as mock_cache:
            # Positive numbers - should cache
            await test_function(1, 2)
            mock_cache.set.assert_called()
            
            mock_cache.reset_mock()
            
            # Negative number - should skip caching
            await test_function(-1, 2)
            mock_cache.set.assert_not_called()
            mock_cache.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cache_database_query_decorator(self):
        """Test database query caching decorator."""
        query_count = 0
        
        @cache_database_query(ttl=120, cache_type="db_query")
        async def get_user_by_id(user_id):
            nonlocal query_count
            query_count += 1
            return {"id": user_id, "name": f"User {user_id}"}
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.get.return_value = None  # Cache miss
            mock_cache.set.return_value = True
            
            # First call
            result = await get_user_by_id(123)
            assert result["id"] == 123
            assert query_count == 1
            
            # Verify cache operations
            mock_cache.get.assert_called()
            mock_cache.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_invalidate_cache_decorator(self):
        """Test cache invalidation decorator."""
        @invalidate_cache(["pattern1:*", "pattern2:*"])
        async def update_data():
            return "updated"
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.delete_pattern.return_value = 5
            
            result = await update_data()
            assert result == "updated"
            
            # Should have called delete_pattern for each pattern
            assert mock_cache.delete_pattern.call_count == 2


class TestCacheResponseDecorator:
    """Test cache response decorator for FastAPI endpoints."""
    
    @pytest.mark.asyncio
    async def test_cache_response_basic(self):
        """Test basic response caching."""
        @cache_response(ttl=60, cache_type="api")
        async def mock_endpoint(request: Request):
            return {"message": "Hello World"}
        
        # Create mock request
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.query_params = {}
        mock_request.headers = {}
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.get.return_value = None  # Cache miss
            mock_cache.set.return_value = True
            
            result = await mock_endpoint(mock_request)
            assert result == {"message": "Hello World"}
            
            mock_cache.get.assert_called()
            mock_cache.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_cache_response_with_query_params(self):
        """Test response caching with query parameters."""
        @cache_response(ttl=60)
        async def mock_endpoint(request: Request):
            return {"data": "response"}
        
        # Mock request with query params
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.query_params = {"page": "1", "size": "10"}
        mock_request.headers = {}
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set.return_value = True
            
            await mock_endpoint(mock_request)
            
            # Should include query params in cache key
            cache_key = mock_cache.get.call_args[0][0]
            assert "rendiff:" in cache_key
    
    @pytest.mark.asyncio
    async def test_cache_response_skip_condition(self):
        """Test response caching with skip condition."""
        @cache_response(ttl=60, skip_if=skip_on_post_request)
        async def mock_endpoint(request: Request):
            return {"data": "response"}
        
        # POST request should skip caching
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/test"
        mock_request.query_params = {}
        
        with patch('api.decorators.cache_service') as mock_cache:
            await mock_endpoint(mock_request)
            
            # Should not call cache for POST request
            mock_cache.get.assert_not_called()
            mock_cache.set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cache_response_cache_hit(self):
        """Test response caching with cache hit."""
        @cache_response(ttl=60)
        async def mock_endpoint(request: Request):
            return {"message": "Original"}
        
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.query_params = {}
        mock_request.headers = {}
        
        with patch('api.decorators.cache_service') as mock_cache:
            # Mock cache hit
            mock_cache.get.return_value = {"message": "Cached"}
            
            result = await mock_endpoint(mock_request)
            assert result == {"message": "Cached"}
            
            # Should not call set on cache hit
            mock_cache.set.assert_not_called()


class TestCacheUtilities:
    """Test cache utility functions."""
    
    @pytest.mark.asyncio
    async def test_cache_job_data(self):
        """Test job data caching utility."""
        job_data = {
            "id": "job-123",
            "status": "completed",
            "progress": 100
        }
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.set.return_value = True
            
            result = await cache_job_data("job-123", job_data, ttl=300)
            assert result is True
            
            # Verify cache call
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args
            assert call_args[0][0] == "rendiff:job:job-123"  # cache key
            assert call_args[0][1] == job_data  # data
            assert call_args[0][2] == 300  # ttl
    
    @pytest.mark.asyncio
    async def test_get_cached_job_data(self):
        """Test getting cached job data."""
        cached_data = {"id": "job-123", "status": "processing"}
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.get.return_value = cached_data
            
            result = await get_cached_job_data("job-123")
            assert result == cached_data
            
            mock_cache.get.assert_called_once_with("rendiff:job:job-123")
    
    @pytest.mark.asyncio
    async def test_invalidate_job_cache(self):
        """Test job cache invalidation."""
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.delete_pattern.return_value = 3
            
            await invalidate_job_cache("job-123")
            
            # Should call delete_pattern for job-specific and job list patterns
            assert mock_cache.delete_pattern.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_api_key_validation_caching(self):
        """Test API key validation caching utilities."""
        user_data = {"id": "user-123", "role": "admin"}
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.set.return_value = True
            
            # Cache validation result
            await cache_api_key_validation("test-key", True, user_data)
            
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args
            cached_data = call_args[0][1]
            assert cached_data["is_valid"] is True
            assert cached_data["user_data"] == user_data
    
    @pytest.mark.asyncio
    async def test_get_cached_api_key_validation(self):
        """Test getting cached API key validation."""
        cached_result = {
            "is_valid": True,
            "user_data": {"id": "user-123"},
            "cached_at": 123456789
        }
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.get.return_value = cached_result
            
            result = await get_cached_api_key_validation("test-key")
            assert result == cached_result
            
            mock_cache.get.assert_called_once()


class TestSkipConditions:
    """Test cache skip condition functions."""
    
    def test_skip_on_post_request(self):
        """Test POST request skip condition."""
        # POST request should skip
        post_request = MagicMock(spec=Request)
        post_request.method = "POST"
        assert skip_on_post_request(post_request) is True
        
        # GET request should not skip
        get_request = MagicMock(spec=Request)
        get_request.method = "GET"
        assert skip_on_post_request(get_request) is False
    
    def test_skip_on_authenticated_request(self):
        """Test authenticated request skip condition."""
        # Request with authorization header should skip
        auth_request = MagicMock(spec=Request)
        auth_request.headers = {"authorization": "Bearer token123"}
        assert skip_on_authenticated_request(auth_request) is True
        
        # Request without authorization should not skip
        no_auth_request = MagicMock(spec=Request)
        no_auth_request.headers = {}
        assert skip_on_authenticated_request(no_auth_request) is False
    
    def test_skip_if_no_cache_header(self):
        """Test no-cache header skip condition."""
        # Request with no-cache should skip
        no_cache_request = MagicMock(spec=Request)
        no_cache_request.headers = {"cache-control": "no-cache"}
        assert skip_if_no_cache_header(no_cache_request) is True
        
        # Request without no-cache should not skip
        cache_request = MagicMock(spec=Request)
        cache_request.headers = {"cache-control": "max-age=300"}
        assert skip_if_no_cache_header(cache_request) is False
        
        # Request without cache-control should not skip
        normal_request = MagicMock(spec=Request)
        normal_request.headers = {}
        assert skip_if_no_cache_header(normal_request) is False


class TestCacheManager:
    """Test cache manager context manager."""
    
    @pytest.mark.asyncio
    async def test_cache_manager_basic(self):
        """Test basic cache manager functionality."""
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.delete_pattern.return_value = 2
            
            async with CacheManager() as manager:
                manager.queue_invalidation("pattern1:*")
                manager.queue_invalidation("pattern2:*")
            
            # Should have called delete_pattern for both patterns
            assert mock_cache.delete_pattern.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_manager_error_handling(self):
        """Test cache manager error handling."""
        with patch('api.decorators.cache_service') as mock_cache:
            # First call succeeds, second fails
            mock_cache.delete_pattern.side_effect = [3, Exception("Delete failed")]
            
            # Should not raise exception
            async with CacheManager() as manager:
                manager.queue_invalidation("pattern1:*")
                manager.queue_invalidation("pattern2:*")
            
            assert mock_cache.delete_pattern.call_count == 2


class TestCacheWarmingUtilities:
    """Test cache warming utilities."""
    
    @pytest.mark.asyncio
    async def test_warm_cache_for_popular_jobs(self):
        """Test cache warming for popular jobs."""
        from api.decorators import warm_cache_for_popular_jobs
        
        job_ids = ["job-1", "job-2", "job-3"]
        
        with patch('api.decorators.get_async_db') as mock_db:
            with patch('api.decorators.cache_job_data') as mock_cache_job:
                # Mock database session
                mock_session = AsyncMock()
                mock_db.return_value.__aenter__.return_value = mock_session
                
                # Mock jobs
                mock_jobs = []
                for job_id in job_ids:
                    mock_job = MagicMock()
                    mock_job.id = job_id
                    mock_job.status = "completed"
                    mock_job.progress = 100
                    mock_job.created_at = MagicMock()
                    mock_job.updated_at = MagicMock()
                    mock_jobs.append(mock_job)
                
                mock_session.get.side_effect = mock_jobs
                
                await warm_cache_for_popular_jobs(job_ids)
                
                # Should have cached all jobs
                assert mock_cache_job.call_count == len(job_ids)
    
    @pytest.mark.asyncio
    async def test_warm_cache_error_handling(self):
        """Test cache warming error handling."""
        from api.decorators import warm_cache_for_popular_jobs
        
        with patch('api.decorators.get_async_db') as mock_db:
            # Mock database error
            mock_db.side_effect = Exception("Database error")
            
            # Should not raise exception
            await warm_cache_for_popular_jobs(["job-1"])


class TestCacheIntegrationScenarios:
    """Test realistic cache integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_job_lifecycle_caching(self):
        """Test caching throughout job lifecycle."""
        job_id = "job-lifecycle-test"
        
        with patch('api.decorators.cache_service') as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set.return_value = True
            mock_cache.delete_pattern.return_value = 1
            
            # 1. Cache initial job data
            await cache_job_data(job_id, {"status": "queued"})
            
            # 2. Get cached job data
            await get_cached_job_data(job_id)
            
            # 3. Invalidate cache when job completes
            await invalidate_job_cache(job_id)
            
            # Verify cache operations
            assert mock_cache.set.call_count >= 1
            assert mock_cache.get.call_count >= 1
            assert mock_cache.delete_pattern.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_api_key_validation_flow(self):
        """Test API key validation caching flow."""
        api_key = "test-api-key"
        user_data = {"id": "user-123", "role": "user"}
        
        with patch('api.decorators.cache_service') as mock_cache:
            # First validation - cache miss
            mock_cache.get.return_value = None
            cached_result = await get_cached_api_key_validation(api_key)
            assert cached_result is None
            
            # Cache the validation result
            await cache_api_key_validation(api_key, True, user_data)
            
            # Second validation - cache hit
            mock_cache.get.return_value = {
                "is_valid": True,
                "user_data": user_data,
                "cached_at": 123456789
            }
            cached_result = await get_cached_api_key_validation(api_key)
            assert cached_result["is_valid"] is True
            assert cached_result["user_data"] == user_data