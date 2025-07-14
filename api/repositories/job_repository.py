"""Job repository implementation."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime

from .base import BaseRepository
from api.interfaces.job_repository import JobRepositoryInterface
from api.models.job import Job, JobStatus


class JobRepository(BaseRepository[Job], JobRepositoryInterface):
    """Job repository implementation."""
    
    def __init__(self):
        super().__init__(Job)
    
    async def get_by_status(self, session: AsyncSession, status: JobStatus, limit: int = 100) -> List[Job]:
        """Get jobs by status."""
        stmt = select(Job).where(Job.status == status).limit(limit).order_by(Job.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_user_id(self, session: AsyncSession, user_id: str, limit: int = 100) -> List[Job]:
        """Get jobs by user ID."""
        stmt = select(Job).where(Job.user_id == user_id).limit(limit).order_by(Job.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def update_status(self, session: AsyncSession, job_id: str, status: JobStatus, **kwargs) -> Optional[Job]:
        """Update job status."""
        update_data = {"status": status, "updated_at": datetime.utcnow()}
        
        # Add specific status-related fields
        if status == JobStatus.PROCESSING:
            update_data["started_at"] = kwargs.get("started_at", datetime.utcnow())
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            update_data["completed_at"] = kwargs.get("completed_at", datetime.utcnow())
            if "error_message" in kwargs:
                update_data["error_message"] = kwargs["error_message"]
            if "output_url" in kwargs:
                update_data["output_url"] = kwargs["output_url"]
        
        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in update_data and hasattr(Job, key):
                update_data[key] = value
        
        return await self.update(session, job_id, **update_data)
    
    async def get_pending_jobs(self, session: AsyncSession, limit: int = 100) -> List[Job]:
        """Get jobs pending processing."""
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.PENDING)
            .order_by(Job.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_jobs_by_date_range(self, session: AsyncSession, start_date: str, end_date: str) -> List[Job]:
        """Get jobs within date range."""
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        stmt = (
            select(Job)
            .where(and_(Job.created_at >= start_dt, Job.created_at <= end_dt))
            .order_by(Job.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_failed_jobs(self, session: AsyncSession, limit: int = 100) -> List[Job]:
        """Get failed jobs for retry."""
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.FAILED)
            .order_by(Job.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def search_jobs(self, session: AsyncSession, query: str, limit: int = 100) -> List[Job]:
        """Search jobs by filename or metadata."""
        search_term = f"%{query}%"
        stmt = (
            select(Job)
            .where(
                or_(
                    Job.filename.ilike(search_term),
                    Job.output_filename.ilike(search_term),
                    Job.user_id.ilike(search_term)
                )
            )
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())