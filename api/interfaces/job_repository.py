"""Job repository interface."""

from abc import abstractmethod
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepositoryInterface
from api.models.job import Job, JobStatus


class JobRepositoryInterface(BaseRepositoryInterface[Job]):
    """Job repository interface with job-specific operations."""
    
    @abstractmethod
    async def get_by_status(self, session: AsyncSession, status: JobStatus, limit: int = 100) -> List[Job]:
        """Get jobs by status."""
        pass
    
    @abstractmethod
    async def get_by_user_id(self, session: AsyncSession, user_id: str, limit: int = 100) -> List[Job]:
        """Get jobs by user ID."""
        pass
    
    @abstractmethod
    async def update_status(self, session: AsyncSession, job_id: str, status: JobStatus, **kwargs) -> Optional[Job]:
        """Update job status."""
        pass
    
    @abstractmethod
    async def get_pending_jobs(self, session: AsyncSession, limit: int = 100) -> List[Job]:
        """Get jobs pending processing."""
        pass
    
    @abstractmethod
    async def get_jobs_by_date_range(self, session: AsyncSession, start_date: str, end_date: str) -> List[Job]:
        """Get jobs within date range."""
        pass
    
    @abstractmethod
    async def get_failed_jobs(self, session: AsyncSession, limit: int = 100) -> List[Job]:
        """Get failed jobs for retry."""
        pass
    
    @abstractmethod
    async def search_jobs(self, session: AsyncSession, query: str, limit: int = 100) -> List[Job]:
        """Search jobs by filename or metadata."""
        pass