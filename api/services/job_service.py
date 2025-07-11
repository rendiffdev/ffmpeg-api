"""Job service using repository pattern."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import structlog

from api.repositories.job_repository import JobRepository
from api.interfaces.job_repository import JobRepositoryInterface
from api.models.job import Job, JobStatus
from api.utils.error_handlers import NotFoundError, ValidationError

logger = structlog.get_logger()


class JobService:
    """Service for managing jobs using repository pattern."""
    
    def __init__(self, job_repository: JobRepositoryInterface = None):
        self.job_repository = job_repository or JobRepository()
    
    async def create_job(self, session, **job_data) -> Job:
        """Create a new job."""
        try:
            # Validate required fields
            required_fields = ['filename', 'user_id', 'conversion_type']
            for field in required_fields:
                if field not in job_data:
                    raise ValidationError(f"Missing required field: {field}")
            
            # Set default values
            job_data.setdefault('status', JobStatus.PENDING)
            job_data.setdefault('created_at', datetime.utcnow())
            
            job = await self.job_repository.create(session, **job_data)
            
            logger.info(
                "Job created",
                job_id=job.id,
                user_id=job.user_id,
                filename=job.filename,
                conversion_type=job.conversion_type
            )
            
            return job
            
        except Exception as e:
            logger.error("Failed to create job", error=str(e), job_data=job_data)
            raise
    
    async def get_job(self, session, job_id: str) -> Job:
        """Get job by ID."""
        job = await self.job_repository.get_by_id(session, job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        return job
    
    async def get_jobs_by_user(self, session, user_id: str, limit: int = 100) -> List[Job]:
        """Get jobs for a specific user."""
        return await self.job_repository.get_by_user_id(session, user_id, limit)
    
    async def get_jobs_by_status(self, session, status: JobStatus, limit: int = 100) -> List[Job]:
        """Get jobs by status."""
        return await self.job_repository.get_by_status(session, status, limit)
    
    async def get_pending_jobs(self, session, limit: int = 100) -> List[Job]:
        """Get jobs pending processing."""
        return await self.job_repository.get_pending_jobs(session, limit)
    
    async def get_failed_jobs(self, session, limit: int = 100) -> List[Job]:
        """Get failed jobs for retry."""
        return await self.job_repository.get_failed_jobs(session, limit)
    
    async def update_job_status(
        self, 
        session, 
        job_id: str, 
        status: JobStatus, 
        **kwargs
    ) -> Job:
        """Update job status with additional metadata."""
        job = await self.job_repository.update_status(session, job_id, status, **kwargs)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        
        logger.info(
            "Job status updated",
            job_id=job_id,
            old_status=job.status,
            new_status=status,
            **{k: v for k, v in kwargs.items() if k != 'session'}
        )
        
        return job
    
    async def start_job_processing(self, session, job_id: str, worker_id: str = None) -> Job:
        """Mark job as processing."""
        return await self.update_job_status(
            session,
            job_id,
            JobStatus.PROCESSING,
            started_at=datetime.utcnow(),
            worker_id=worker_id
        )
    
    async def complete_job(
        self, 
        session, 
        job_id: str, 
        output_url: str = None,
        file_size: int = None,
        duration: float = None
    ) -> Job:
        """Mark job as completed."""
        completion_data = {
            'completed_at': datetime.utcnow(),
            'output_url': output_url,
            'output_file_size': file_size,
            'processing_duration': duration
        }
        
        return await self.update_job_status(
            session,
            job_id,
            JobStatus.COMPLETED,
            **completion_data
        )
    
    async def fail_job(
        self, 
        session, 
        job_id: str, 
        error_message: str,
        retry_count: int = None
    ) -> Job:
        """Mark job as failed."""
        failure_data = {
            'completed_at': datetime.utcnow(),
            'error_message': error_message
        }
        
        if retry_count is not None:
            failure_data['retry_count'] = retry_count
        
        return await self.update_job_status(
            session,
            job_id,
            JobStatus.FAILED,
            **failure_data
        )
    
    async def search_jobs(self, session, query: str, limit: int = 100) -> List[Job]:
        """Search jobs by filename or metadata."""
        return await self.job_repository.search_jobs(session, query, limit)
    
    async def get_jobs_by_date_range(
        self, 
        session, 
        start_date: str, 
        end_date: str
    ) -> List[Job]:
        """Get jobs within date range."""
        return await self.job_repository.get_jobs_by_date_range(session, start_date, end_date)
    
    async def get_job_statistics(self, session, user_id: str = None) -> Dict[str, Any]:
        """Get job statistics."""
        filters = {}
        if user_id:
            filters['user_id'] = user_id
        
        total_jobs = await self.job_repository.count(session, filters)
        
        stats = {
            'total_jobs': total_jobs,
            'pending_jobs': len(await self.get_jobs_by_status(session, JobStatus.PENDING)),
            'processing_jobs': len(await self.get_jobs_by_status(session, JobStatus.PROCESSING)),
            'completed_jobs': len(await self.get_jobs_by_status(session, JobStatus.COMPLETED)),
            'failed_jobs': len(await self.get_jobs_by_status(session, JobStatus.FAILED))
        }
        
        return stats
    
    async def delete_job(self, session, job_id: str) -> bool:
        """Delete a job."""
        success = await self.job_repository.delete(session, job_id)
        if success:
            logger.info("Job deleted", job_id=job_id)
        return success
    
    async def cleanup_old_jobs(
        self, 
        session, 
        days_old: int = 30,
        status_filter: JobStatus = None
    ) -> int:
        """Clean up old jobs."""
        # This is a simplified version - in a real implementation,
        # you might want to add a specific repository method for this
        cutoff_date = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
        start_date = "1970-01-01T00:00:00"
        
        old_jobs = await self.get_jobs_by_date_range(session, start_date, cutoff_date)
        
        if status_filter:
            old_jobs = [job for job in old_jobs if job.status == status_filter]
        
        deleted_count = 0
        for job in old_jobs:
            if await self.delete_job(session, job.id):
                deleted_count += 1
        
        logger.info("Old jobs cleaned up", count=deleted_count, days_old=days_old)
        return deleted_count