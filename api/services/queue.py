"""
Queue service for job management
"""
from typing import Dict, Any, List, Optional
import json

import redis.asyncio as redis
from celery import Celery
import structlog

from api.config import settings

logger = structlog.get_logger()


class QueueService:
    """Service for managing job queues."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.celery_app = Celery(
            "rendiff_worker",
            broker=settings.REDIS_URL,
            backend=settings.REDIS_URL,
        )
    
    async def initialize(self) -> None:
        """Initialize queue connections."""
        self.redis_client = redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
        
        # Test connection
        await self.redis_client.ping()
        logger.info("Queue service initialized")
    
    async def cleanup(self) -> None:
        """Clean up queue connections."""
        if self.redis_client:
            await self.redis_client.close()
    
    async def enqueue_job(self, job_id: str, priority: str = "normal") -> str:
        """Add job to processing queue."""
        # Map priority to queue
        queue_map = {
            "low": "low",
            "normal": "default",
            "high": "high",
        }
        queue_name = queue_map.get(priority, "default")
        
        # Send task to Celery
        result = self.celery_app.send_task(
            "worker.process_job",
            args=[job_id],
            queue=queue_name,
            priority={"low": 1, "normal": 5, "high": 9}.get(priority, 5),
        )
        
        # Store task ID for tracking
        await self.redis_client.hset(
            f"job:{job_id}",
            mapping={
                "task_id": result.id,
                "queue": queue_name,
                "status": "queued",
            }
        )
        
        logger.info(f"Job {job_id} queued in {queue_name} with task ID {result.id}")
        return result.id
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued job."""
        # Get task info
        job_info = await self.redis_client.hgetall(f"job:{job_id}")
        if not job_info:
            return False
        
        task_id = job_info.get("task_id")
        if task_id:
            # Revoke task
            self.celery_app.control.revoke(task_id, terminate=False)
            
            # Update status
            await self.redis_client.hset(f"job:{job_id}", "status", "cancelled")
            
            logger.info(f"Job {job_id} cancelled")
            return True
        
        return False
    
    async def cancel_running_job(self, job_id: str, worker_id: str) -> bool:
        """Cancel a running job on specific worker."""
        # Send cancel signal to worker
        await self.redis_client.publish(
            f"worker:{worker_id}:cancel",
            json.dumps({"job_id": job_id})
        )
        
        logger.info(f"Cancel signal sent for job {job_id} on worker {worker_id}")
        return True
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        stats = {}
        
        for queue in ["high", "default", "low"]:
            # Get queue length
            length = await self.redis_client.llen(f"celery:queue:{queue}")
            stats[queue] = {
                "length": length,
                "active": 0,  # Would need to query active tasks
            }
        
        return stats
    
    async def get_workers_status(self) -> List[Dict[str, Any]]:
        """Get status of all workers."""
        # Get worker info from Celery
        inspect = self.celery_app.control.inspect()
        
        workers = []
        active = inspect.active()
        stats = inspect.stats()
        
        if active:
            for worker_name, tasks in active.items():
                worker_info = {
                    "name": worker_name,
                    "status": "active" if tasks else "idle",
                    "active_tasks": len(tasks),
                    "tasks": [
                        {
                            "id": task["id"],
                            "name": task["name"],
                            "args": task["args"],
                        }
                        for task in tasks
                    ],
                }
                
                # Add stats if available
                if stats and worker_name in stats:
                    worker_info["stats"] = stats[worker_name]
                
                workers.append(worker_info)
        
        return workers
    
    async def get_workers_stats(self) -> Dict[str, Any]:
        """Get aggregated worker statistics."""
        workers = await self.get_workers_status()
        
        return {
            "total": len(workers),
            "active": sum(1 for w in workers if w["status"] == "active"),
            "idle": sum(1 for w in workers if w["status"] == "idle"),
            "total_tasks": sum(w["active_tasks"] for w in workers),
        }
    
    async def get_worker_logs(self, worker_id: str, job_id: str, lines: int = 100) -> List[str]:
        """Get logs from specific worker for a job."""
        # Note: Log aggregation service integration not implemented
        # Consider implementing with ELK stack, Grafana Loki, or similar
        return [
            "Log aggregation not configured",
            "Use 'docker-compose logs worker' to view worker logs",
            f"Job ID: {job_id}",
            f"Worker ID: {worker_id}",
        ]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check queue service health."""
        try:
            # Check Redis connection
            await self.redis_client.ping()
            
            # Get queue stats
            stats = await self.get_queue_stats()
            
            return {
                "status": "healthy",
                "type": "valkey",
                "queues": stats,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }