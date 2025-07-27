"""
Performance and load tests for FFmpeg API
Tests system behavior under load and measures performance metrics
"""
import asyncio
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import pytest
import httpx
from locust import HttpUser, task, between
import psutil


class TestPerformanceMetrics:
    """Test performance characteristics and benchmarks."""
    
    @pytest.mark.asyncio
    async def test_api_response_times(self):
        """Measure API response times under normal load."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {"X-API-Key": "test-performance-key"}
            response_times = []
            
            # Measure multiple requests
            for _ in range(100):
                start_time = time.time()
                response = await client.get("/api/v1/health", headers=headers)
                end_time = time.time()
                
                if response.status_code == 200:
                    response_times.append(end_time - start_time)
            
            # Calculate statistics
            if response_times:
                avg_time = statistics.mean(response_times)
                p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
                p99_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
                
                print(f"Average response time: {avg_time:.3f}s")
                print(f"P95 response time: {p95_time:.3f}s")
                print(f"P99 response time: {p99_time:.3f}s")
                
                # Performance assertions
                assert avg_time < 0.1, f"Average response time {avg_time:.3f}s exceeds 100ms"
                assert p95_time < 0.5, f"P95 response time {p95_time:.3f}s exceeds 500ms"
                assert p99_time < 1.0, f"P99 response time {p99_time:.3f}s exceeds 1s"
    
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """Test API behavior under concurrent load."""
        async def make_request(client, semaphore):
            async with semaphore:
                headers = {"X-API-Key": "test-performance-key"}
                start_time = time.time()
                response = await client.get("/api/v1/capabilities", headers=headers)
                end_time = time.time()
                return {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200
                }
        
        # Limit concurrent connections
        semaphore = asyncio.Semaphore(50)
        
        async with httpx.AsyncClient(
            base_url="http://localhost:8000",
            timeout=30.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        ) as client:
            
            # Create 200 concurrent requests
            tasks = [make_request(client, semaphore) for _ in range(200)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_results = [r for r in results if isinstance(r, dict)]
            
            # Calculate metrics
            success_count = sum(1 for r in valid_results if r["success"])
            success_rate = success_count / len(valid_results) if valid_results else 0
            
            response_times = [r["response_time"] for r in valid_results if r["success"]]
            avg_response_time = statistics.mean(response_times) if response_times else float('inf')
            
            print(f"Success rate: {success_rate:.2%}")
            print(f"Successful requests: {success_count}/{len(valid_results)}")
            print(f"Average response time: {avg_response_time:.3f}s")
            
            # Performance assertions
            assert success_rate >= 0.95, f"Success rate {success_rate:.2%} below 95%"
            assert avg_response_time < 2.0, f"Average response time {avg_response_time:.3f}s exceeds 2s"
    
    @pytest.mark.asyncio
    async def test_job_submission_throughput(self):
        """Test job submission throughput."""
        async def submit_job(client, job_id):
            headers = {"X-API-Key": "test-performance-key"}
            request_data = {
                "input": f"/test/input_{job_id}.mp4",
                "output": f"/test/output_{job_id}.mp4",
                "operations": [{"type": "scale", "width": 720, "height": 480}]
            }
            
            start_time = time.time()
            response = await client.post("/api/v1/convert", json=request_data, headers=headers)
            end_time = time.time()
            
            return {
                "job_id": job_id,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 201
            }
        
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
            # Submit 50 jobs concurrently
            start_time = time.time()
            tasks = [submit_job(client, i) for i in range(50)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            total_time = end_time - start_time
            valid_results = [r for r in results if isinstance(r, dict)]
            successful_submissions = sum(1 for r in valid_results if r["success"])
            
            throughput = successful_submissions / total_time if total_time > 0 else 0
            
            print(f"Job submission throughput: {throughput:.2f} jobs/second")
            print(f"Successful submissions: {successful_submissions}/{len(valid_results)}")
            print(f"Total time: {total_time:.2f}s")
            
            # Throughput assertion
            assert throughput >= 5.0, f"Throughput {throughput:.2f} jobs/s below minimum of 5/s"


class TestResourceUsage:
    """Test resource consumption under load."""
    
    def test_memory_usage_under_load(self):
        """Monitor memory usage during sustained load."""
        import threading
        import requests
        
        # Monitor system resources
        memory_samples = []
        cpu_samples = []
        monitoring = True
        
        def monitor_resources():
            while monitoring:
                memory_samples.append(psutil.virtual_memory().percent)
                cpu_samples.append(psutil.cpu_percent(interval=0.1))
                time.sleep(1)
        
        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_resources)
        monitor_thread.start()
        
        try:
            # Generate sustained load
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                
                for _ in range(100):
                    future = executor.submit(
                        requests.get,
                        "http://localhost:8000/api/v1/health",
                        headers={"X-API-Key": "test-performance-key"},
                        timeout=5
                    )
                    futures.append(future)
                
                # Wait for completion
                completed = 0
                for future in futures:
                    try:
                        response = future.result(timeout=10)
                        if response.status_code == 200:
                            completed += 1
                    except Exception:
                        pass
                
                print(f"Completed requests: {completed}/{len(futures)}")
        
        finally:
            monitoring = False
            monitor_thread.join()
        
        # Analyze resource usage
        if memory_samples and cpu_samples:
            max_memory = max(memory_samples)
            avg_memory = statistics.mean(memory_samples)
            max_cpu = max(cpu_samples)
            avg_cpu = statistics.mean(cpu_samples)
            
            print(f"Memory usage - Max: {max_memory:.1f}%, Avg: {avg_memory:.1f}%")
            print(f"CPU usage - Max: {max_cpu:.1f}%, Avg: {avg_cpu:.1f}%")
            
            # Resource usage assertions
            assert max_memory < 90, f"Memory usage {max_memory:.1f}% exceeds 90%"
            assert avg_cpu < 80, f"Average CPU usage {avg_cpu:.1f}% exceeds 80%"
    
    @pytest.mark.asyncio
    async def test_database_connection_pooling(self):
        """Test database connection pool behavior under load."""
        async def make_db_intensive_request(client):
            headers = {"X-API-Key": "test-performance-key"}
            # Request that requires database access
            response = await client.get("/api/v1/jobs", headers=headers)
            return response.status_code == 200
        
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
            # Create many concurrent database requests
            tasks = [make_db_intensive_request(client) for _ in range(100)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if r is True)
            success_rate = success_count / len(results)
            
            print(f"Database request success rate: {success_rate:.2%}")
            
            # Should handle concurrent DB requests well
            assert success_rate >= 0.90, f"DB request success rate {success_rate:.2%} below 90%"


class TestScalability:
    """Test system scalability characteristics."""
    
    @pytest.mark.asyncio
    async def test_queue_handling_capacity(self):
        """Test job queue handling under high load."""
        async def submit_bulk_jobs(client, batch_size):
            headers = {"X-API-Key": "test-performance-key"}
            results = []
            
            for i in range(batch_size):
                request_data = {
                    "input": f"/test/bulk_{i}.mp4",
                    "output": f"/test/bulk_output_{i}.mp4"
                }
                
                try:
                    response = await client.post("/api/v1/convert", json=request_data, headers=headers)
                    results.append(response.status_code == 201)
                except Exception:
                    results.append(False)
            
            return results
        
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60.0) as client:
            # Submit jobs in batches
            batch_results = []
            for batch in range(5):  # 5 batches of 20 jobs each
                print(f"Submitting batch {batch + 1}/5...")
                batch_result = await submit_bulk_jobs(client, 20)
                batch_results.extend(batch_result)
                
                # Small delay between batches
                await asyncio.sleep(1)
            
            total_jobs = len(batch_results)
            successful_jobs = sum(batch_results)
            success_rate = successful_jobs / total_jobs if total_jobs > 0 else 0
            
            print(f"Queue capacity test: {successful_jobs}/{total_jobs} jobs accepted")
            print(f"Success rate: {success_rate:.2%}")
            
            # Should handle bulk job submissions
            assert success_rate >= 0.80, f"Queue acceptance rate {success_rate:.2%} below 80%"


# Locust Load Testing Classes
class APILoadTest(HttpUser):
    """Locust load test for API endpoints."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Set up test user."""
        self.headers = {"X-API-Key": "test-load-key"}
    
    @task(3)
    def test_health_check(self):
        """Health check endpoint (frequent)."""
        self.client.get("/api/v1/health", headers=self.headers)
    
    @task(2)
    def test_capabilities(self):
        """Capabilities endpoint (moderate)."""
        self.client.get("/api/v1/capabilities", headers=self.headers)
    
    @task(1)
    def test_job_listing(self):
        """Job listing endpoint (less frequent)."""
        self.client.get("/api/v1/jobs", headers=self.headers)
    
    @task(1)
    def test_job_submission(self):
        """Job submission (less frequent, more expensive)."""
        import random
        
        job_data = {
            "input": f"/test/load_test_{random.randint(1, 1000)}.mp4",
            "output": f"/test/output_{random.randint(1, 1000)}.mp4",
            "operations": [{"type": "scale", "width": 720, "height": 480}]
        }
        
        self.client.post("/api/v1/convert", json=job_data, headers=self.headers)


class WorkerLoadTest(HttpUser):
    """Locust load test focused on worker-intensive operations."""
    
    wait_time = between(2, 5)
    
    def on_start(self):
        self.headers = {"X-API-Key": "test-worker-load-key"}
    
    @task(1)
    def test_complex_conversion(self):
        """Submit complex conversion jobs."""
        import random
        
        job_data = {
            "input": f"/test/complex_{random.randint(1, 100)}.mp4",
            "output": f"/test/complex_output_{random.randint(1, 100)}.mp4",
            "operations": [
                {"type": "trim", "start": 5, "duration": 30},
                {"type": "scale", "width": 1280, "height": 720},
                {"type": "watermark", "text": f"Load Test {random.randint(1, 1000)}"}
            ],
            "options": {
                "priority": random.choice(["low", "normal", "high"]),
                "format": "mp4",
                "video_codec": "h264"
            }
        }
        
        response = self.client.post("/api/v1/convert", json=job_data, headers=self.headers)
        
        if response.status_code == 201:
            # Occasionally check job status
            if random.random() < 0.3:  # 30% chance
                job_id = response.json().get("job", {}).get("id")
                if job_id:
                    self.client.get(f"/api/v1/jobs/{job_id}", headers=self.headers)
    
    @task(1)
    def test_analysis_jobs(self):
        """Submit analysis jobs."""
        import random
        
        analysis_data = {
            "input": f"/test/analysis_{random.randint(1, 50)}.mp4",
            "metrics": ["duration", "resolution", "bitrate", "codec", "quality"]
        }
        
        self.client.post("/api/v1/analyze", json=analysis_data, headers=self.headers)


# Stress Testing
class TestStressLimits:
    """Test system behavior at stress limits."""
    
    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_maximum_concurrent_connections(self):
        """Test maximum concurrent connection handling."""
        async def make_long_request(client, delay):
            headers = {"X-API-Key": "test-stress-key"}
            # Simulate a longer-running request
            await asyncio.sleep(delay)
            response = await client.get("/api/v1/capabilities", headers=headers)
            return response.status_code
        
        async with httpx.AsyncClient(
            base_url="http://localhost:8000",
            timeout=60.0,
            limits=httpx.Limits(max_connections=500, max_keepalive_connections=100)
        ) as client:
            
            # Create many concurrent long-running requests
            tasks = [make_long_request(client, 0.1) for _ in range(300)]
            
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            successful_requests = sum(1 for r in results if r == 200)
            total_time = end_time - start_time
            
            print(f"Stress test: {successful_requests}/{len(tasks)} requests successful")
            print(f"Total time: {total_time:.2f}s")
            
            # Should handle high concurrency reasonably
            success_rate = successful_requests / len(tasks)
            assert success_rate >= 0.70, f"Stress test success rate {success_rate:.2%} below 70%"
    
    @pytest.mark.stress
    def test_memory_leak_detection(self):
        """Test for memory leaks under sustained load."""
        import gc
        import threading
        import requests
        
        # Force garbage collection
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Run sustained load
        def make_requests():
            session = requests.Session()
            headers = {"X-API-Key": "test-stress-key"}
            
            for _ in range(100):
                try:
                    response = session.get(
                        "http://localhost:8000/api/v1/health",
                        headers=headers,
                        timeout=5
                    )
                except Exception:
                    pass
        
        # Run multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_requests)
            thread.start()
            threads.append(thread)
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Force garbage collection and check memory
        gc.collect()
        time.sleep(2)  # Allow cleanup
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        memory_increase = final_memory - initial_memory
        print(f"Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB")
        print(f"Memory increase: {memory_increase:.1f}MB")
        
        # Memory increase should be reasonable
        assert memory_increase < 100, f"Memory increase {memory_increase:.1f}MB suggests possible leak"


if __name__ == "__main__":
    # Run performance tests
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "not stress"  # Exclude stress tests by default
    ])