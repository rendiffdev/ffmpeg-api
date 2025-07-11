"""
Mock queue service for testing
"""
import asyncio
from typing import Dict, Any, Optional
from uuid import uuid4
from unittest.mock import AsyncMock


class MockQueueService:
    """Mock queue service for testing Celery operations."""
    
    def __init__(self):
        self.jobs = {}
        self.operation_history = []
    
    async def submit_job(
        self,
        job_type: str,
        job_data: Dict[str, Any],
        priority: str = "normal"
    ) -> str:
        """Mock job submission."""
        job_id = str(uuid4())
        
        self.jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "data": job_data,
            "priority": priority,
            "status": "queued",
            "submitted_at": "2024-07-10T12:00:00Z"
        }
        
        self.operation_history.append(("submit", job_id, job_type))
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Mock job status retrieval."""
        self.operation_history.append(("status", job_id))
        
        if job_id not in self.jobs:
            return None
        
        return {
            "id": job_id,
            "status": self.jobs[job_id]["status"],
            "progress": 0.0,
            "stage": "queued"
        }
    
    async def cancel_job(self, job_id: str) -> bool:
        """Mock job cancellation."""
        self.operation_history.append(("cancel", job_id))
        
        if job_id not in self.jobs:
            return False
        
        if self.jobs[job_id]["status"] in ["queued", "processing"]:
            self.jobs[job_id]["status"] = "cancelled"
            return True
        
        return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Mock queue statistics."""
        self.operation_history.append(("stats", None))
        
        statuses = {}
        for job in self.jobs.values():
            status = job["status"]
            statuses[status] = statuses.get(status, 0) + 1
        
        return {
            "total_jobs": len(self.jobs),
            "by_status": statuses,
            "active_workers": 2,
            "queue_lengths": {
                "high": 0,
                "normal": statuses.get("queued", 0),
                "low": 0
            }
        }
    
    def simulate_job_progress(self, job_id: str, status: str, progress: float = None):
        """Simulate job progress for testing."""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            if progress is not None:
                self.jobs[job_id]["progress"] = progress
    
    def get_operation_history(self):
        """Get operation history for testing."""
        return self.operation_history.copy()
    
    def clear_history(self):
        """Clear operation history."""
        self.operation_history.clear()
    
    def clear_jobs(self):
        """Clear all jobs."""
        self.jobs.clear()


class MockCeleryTask:
    """Mock Celery task for testing."""
    
    def __init__(self, task_id: str = None):
        self.id = task_id or str(uuid4())
        self.state = "PENDING"
        self.result = None
        self.info = {}
    
    def ready(self) -> bool:
        """Check if task is ready."""
        return self.state in ["SUCCESS", "FAILURE", "REVOKED"]
    
    def successful(self) -> bool:
        """Check if task completed successfully."""
        return self.state == "SUCCESS"
    
    def failed(self) -> bool:
        """Check if task failed."""
        return self.state == "FAILURE"
    
    def revoke(self, terminate: bool = False):
        """Revoke/cancel the task."""
        self.state = "REVOKED"
    
    def forget(self):
        """Forget the task result."""
        self.result = None
        self.info = {}


class MockCeleryApp:
    """Mock Celery application for testing."""
    
    def __init__(self):
        self.tasks = {}
        self.task_history = []
    
    def send_task(self, name: str, args: tuple = None, kwargs: dict = None, **options) -> MockCeleryTask:
        """Mock task sending."""
        task_id = str(uuid4())
        task = MockCeleryTask(task_id)
        
        self.tasks[task_id] = {
            "task": task,
            "name": name,
            "args": args or (),
            "kwargs": kwargs or {},
            "options": options
        }
        
        self.task_history.append((name, args, kwargs, options))
        return task
    
    def AsyncResult(self, task_id: str) -> MockCeleryTask:
        """Get task result."""
        if task_id in self.tasks:
            return self.tasks[task_id]["task"]
        else:
            return MockCeleryTask(task_id)
    
    def control(self):
        """Mock Celery control interface."""
        class MockControl:
            def revoke(self, task_id: str, terminate: bool = False):
                pass
            
            def active(self):
                return {"worker1": [], "worker2": []}
            
            def stats(self):
                return {
                    "worker1": {"pool": {"max-concurrency": 4}},
                    "worker2": {"pool": {"max-concurrency": 4}}
                }
        
        return MockControl()
    
    def get_task_history(self):
        """Get task submission history."""
        return self.task_history.copy()
    
    def clear_history(self):
        """Clear task history."""
        self.task_history.clear()
        self.tasks.clear()


class MockRedis:
    """Mock Redis client for testing."""
    
    def __init__(self):
        self.data = {}
        self.operation_history = []
    
    async def get(self, key: str):
        """Mock get operation."""
        self.operation_history.append(("get", key))
        return self.data.get(key)
    
    async def set(self, key: str, value: str, ex: int = None):
        """Mock set operation."""
        self.operation_history.append(("set", key, value, ex))
        self.data[key] = value
        return True
    
    async def delete(self, key: str):
        """Mock delete operation."""
        self.operation_history.append(("delete", key))
        return self.data.pop(key, None) is not None
    
    async def exists(self, key: str):
        """Mock exists check."""
        self.operation_history.append(("exists", key))
        return key in self.data
    
    async def keys(self, pattern: str = "*"):
        """Mock keys listing."""
        self.operation_history.append(("keys", pattern))
        if pattern == "*":
            return list(self.data.keys())
        # Simple pattern matching
        return [k for k in self.data.keys() if pattern.replace("*", "") in k]
    
    def get_operation_history(self):
        """Get operation history."""
        return self.operation_history.copy()
    
    def clear_history(self):
        """Clear operation history."""
        self.operation_history.clear()
    
    def clear_data(self):
        """Clear all data."""
        self.data.clear()