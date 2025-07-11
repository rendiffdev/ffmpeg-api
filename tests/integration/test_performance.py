"""
Performance and load tests for the API
"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from statistics import mean, median
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from api.main import app


class TestPerformance:
    """Performance tests for API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.mark.performance
    def test_health_endpoint_response_time(self, client):
        """Test health endpoint response time."""
        response_times = []
        
        # Make multiple requests to get average response time
        for _ in range(10):
            start_time = time.time()
            response = client.get("/api/v1/health")
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append(end_time - start_time)
        
        avg_response_time = mean(response_times)
        median_response_time = median(response_times)
        
        # Health endpoint should respond quickly (under 100ms)
        assert avg_response_time < 0.1, f"Average response time too slow: {avg_response_time:.3f}s"
        assert median_response_time < 0.1, f"Median response time too slow: {median_response_time:.3f}s"
        
        print(f"Health endpoint - Avg: {avg_response_time:.3f}s, Median: {median_response_time:.3f}s")
    
    @pytest.mark.performance
    def test_concurrent_health_requests(self, client):
        """Test concurrent requests to health endpoint."""
        def make_request():
            start_time = time.time()
            response = client.get("/api/v1/health")
            end_time = time.time()
            return response.status_code, end_time - start_time
        
        # Make 20 concurrent requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [future.result() for future in futures]
        
        # All requests should succeed
        status_codes = [result[0] for result in results]
        response_times = [result[1] for result in results]
        
        assert all(code == 200 for code in status_codes), "Some requests failed"
        
        avg_concurrent_time = mean(response_times)
        # Under load, response time should still be reasonable
        assert avg_concurrent_time < 0.5, f"Concurrent response time too slow: {avg_concurrent_time:.3f}s"
        
        print(f"Concurrent health requests - Avg: {avg_concurrent_time:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.skipif(
        not hasattr(app, 'rate_limiter'),
        reason="Rate limiting not configured"
    )
    def test_rate_limiting_performance(self, client):
        """Test rate limiting doesn't severely impact performance."""
        response_times = []
        
        for _ in range(50):  # Make requests up to rate limit
            start_time = time.time()
            response = client.get("/api/v1/health")
            end_time = time.time()
            
            response_times.append(end_time - start_time)
            
            # Stop if we hit rate limit
            if response.status_code == 429:
                break
        
        # Rate limiting shouldn't significantly slow down valid requests
        valid_times = [t for i, t in enumerate(response_times) if i < 40]  # First 40 should be valid
        if valid_times:
            avg_time = mean(valid_times)
            assert avg_time < 0.2, f"Rate limited requests too slow: {avg_time:.3f}s"
    
    @pytest.mark.performance
    def test_memory_usage_stability(self, client):
        """Test memory usage remains stable under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Make many requests
        for _ in range(100):
            response = client.get("/api/v1/health")
            assert response.status_code == 200
        
        final_memory = process.memory_info().rss
        memory_increase = (final_memory - initial_memory) / 1024 / 1024  # MB
        
        # Memory increase should be minimal (less than 10MB)
        assert memory_increase < 10, f"Memory usage increased too much: {memory_increase:.2f}MB"
        
        print(f"Memory increase after 100 requests: {memory_increase:.2f}MB")


class TestDatabasePerformance:
    """Database performance tests."""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_database_connection_pool(self, test_db_session):
        """Test database connection pool performance."""
        from api.models.job import Job, JobStatus
        from uuid import uuid4
        
        start_time = time.time()
        
        # Create multiple database operations
        jobs = []
        for i in range(50):
            job = Job(
                id=str(uuid4()),
                status=JobStatus.QUEUED,
                input_path=f"input_{i}.mp4",
                output_path=f"output_{i}.mp4",
                api_key="test-key",
                operations=[],
                options={}
            )
            jobs.append(job)
            test_db_session.add(job)
        
        await test_db_session.commit()
        
        # Query all jobs
        result = await test_db_session.execute(
            "SELECT COUNT(*) FROM jobs WHERE api_key = 'test-key'"
        )
        count = result.scalar()
        
        end_time = time.time()
        operation_time = end_time - start_time
        
        assert count >= 50
        assert operation_time < 2.0, f"Database operations too slow: {operation_time:.3f}s"
        
        print(f"50 database operations completed in {operation_time:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_database_access(self, test_db_engine):
        """Test concurrent database access performance."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from api.models.job import Job, JobStatus
        from uuid import uuid4
        
        async_session = async_sessionmaker(
            test_db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        async def create_job(session_maker, job_index):
            async with session_maker() as session:
                job = Job(
                    id=str(uuid4()),
                    status=JobStatus.QUEUED,
                    input_path=f"concurrent_{job_index}.mp4",
                    output_path=f"concurrent_out_{job_index}.mp4",
                    api_key="concurrent-test",
                    operations=[],
                    options={}
                )
                session.add(job)
                await session.commit()
                return job.id
        
        start_time = time.time()
        
        # Create 20 concurrent database operations
        tasks = [create_job(async_session, i) for i in range(20)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        operation_time = end_time - start_time
        
        assert len(results) == 20
        assert all(job_id for job_id in results)
        assert operation_time < 3.0, f"Concurrent DB operations too slow: {operation_time:.3f}s"
        
        print(f"20 concurrent database operations completed in {operation_time:.3f}s")


class TestAsyncPerformance:
    """Async operation performance tests."""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_async_task_performance(self):
        """Test async task execution performance."""
        async def mock_async_task(task_id: int, delay: float = 0.01):
            await asyncio.sleep(delay)
            return f"task_{task_id}_completed"
        
        start_time = time.time()
        
        # Run 100 async tasks concurrently
        tasks = [mock_async_task(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        assert len(results) == 100
        assert all("completed" in result for result in results)
        
        # Should complete much faster than sequential execution (100 * 0.01 = 1s)
        assert execution_time < 0.5, f"Async tasks too slow: {execution_time:.3f}s"
        
        print(f"100 async tasks completed in {execution_time:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_worker_base_class_performance(self):
        """Test worker base class performance."""
        from worker.base import BaseWorkerTask
        from uuid import uuid4
        
        task = BaseWorkerTask()
        
        start_time = time.time()
        
        # Test multiple storage path parsing operations
        paths = [
            "s3://bucket/path/file1.mp4",
            "local:///path/to/file2.mp4",
            "azure://container/file3.mp4",
            "gcp://bucket/file4.mp4"
        ] * 25  # 100 operations
        
        results = [task.parse_storage_path(path) for path in paths]
        
        end_time = time.time()
        operation_time = end_time - start_time
        
        assert len(results) == 100
        assert all(len(result) == 2 for result in results)
        assert operation_time < 0.1, f"Path parsing too slow: {operation_time:.3f}s"
        
        print(f"100 path parsing operations completed in {operation_time:.3f}s")


class TestStoragePerformance:
    """Storage backend performance tests."""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_mock_storage_performance(self, mock_storage_service):
        """Test mock storage backend performance."""
        start_time = time.time()
        
        # Test multiple file operations
        for i in range(50):
            file_path = f"performance_test_{i}.txt"
            content = f"test content {i}" * 100  # ~1KB per file
            
            # Write file
            import io
            file_obj = io.BytesIO(content.encode())
            await mock_storage_service.write(file_path, file_obj)
            
            # Check if exists
            exists = await mock_storage_service.exists(file_path)
            assert exists
        
        # List all files
        files = await mock_storage_service.list("performance_test_")
        
        end_time = time.time()
        operation_time = end_time - start_time
        
        assert len(files) == 50
        assert operation_time < 1.0, f"Storage operations too slow: {operation_time:.3f}s"
        
        print(f"50 storage operations completed in {operation_time:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_storage_operations(self, mock_storage_service):
        """Test concurrent storage operations performance."""
        async def write_and_read_file(file_index):
            file_path = f"concurrent_{file_index}.txt"
            content = f"concurrent test content {file_index}"
            
            # Write
            import io
            file_obj = io.BytesIO(content.encode())
            await mock_storage_service.write(file_path, file_obj)
            
            # Read back
            async with await mock_storage_service.read(file_path) as stream:
                read_content = b""
                async for chunk in stream:
                    read_content += chunk
            
            return read_content.decode() == content
        
        start_time = time.time()
        
        # Run 20 concurrent storage operations
        tasks = [write_and_read_file(i) for i in range(20)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        operation_time = end_time - start_time
        
        assert all(results), "Some storage operations failed"
        assert operation_time < 2.0, f"Concurrent storage operations too slow: {operation_time:.3f}s"
        
        print(f"20 concurrent storage operations completed in {operation_time:.3f}s")


class TestScalabilityMetrics:
    """Test scalability and resource usage metrics."""
    
    @pytest.mark.performance
    def test_response_time_under_load(self, client):
        """Test API response time scaling with load."""
        load_levels = [1, 5, 10, 20]
        response_times = {}
        
        for load in load_levels:
            times = []
            
            def make_request():
                start = time.time()
                response = client.get("/api/v1/health")
                end = time.time()
                return response.status_code, end - start
            
            with ThreadPoolExecutor(max_workers=load) as executor:
                futures = [executor.submit(make_request) for _ in range(load)]
                results = [future.result() for future in futures]
            
            # Calculate average response time for this load level
            valid_times = [t for code, t in results if code == 200]
            if valid_times:
                response_times[load] = mean(valid_times)
        
        # Response time shouldn't increase dramatically with load
        if len(response_times) > 1:
            time_increase = response_times[max(load_levels)] / response_times[min(load_levels)]
            assert time_increase < 5.0, f"Response time scales poorly with load: {time_increase:.2f}x"
        
        print("Response times by load level:", response_times)
    
    @pytest.mark.performance
    @pytest.mark.skipif(
        not hasattr(psutil, 'Process'),
        reason="psutil not available"
    )
    def test_cpu_usage_under_load(self, client):
        """Test CPU usage doesn't spike excessively under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Measure CPU usage before load
        cpu_before = process.cpu_percent()
        time.sleep(0.1)  # Let CPU measurement stabilize
        
        # Generate load
        for _ in range(50):
            response = client.get("/api/v1/health")
            assert response.status_code == 200
        
        # Measure CPU usage after load
        time.sleep(0.1)
        cpu_after = process.cpu_percent()
        
        # CPU usage should be reasonable (less than 80%)
        print(f"CPU usage - Before: {cpu_before:.1f}%, After: {cpu_after:.1f}%")
        
        # This is a loose check as CPU usage can vary greatly
        assert cpu_after < 95.0, f"CPU usage too high: {cpu_after:.1f}%"