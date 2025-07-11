"""
Batch processing service
"""
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import asyncio
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from api.models.batch import (
    BatchJob, BatchJobCreate, BatchJobUpdate, BatchJobStats, 
    BatchJobProgress, BatchStatus
)
from api.models.job import Job, JobStatus
from api.services.job_service import JobService
from api.utils.error_handlers import NotFoundError, ValidationError

logger = structlog.get_logger()


class BatchService:
    """Service for managing batch operations."""
    
    def __init__(self):
        self.job_service = JobService()
    
    async def create_batch_job(
        self,
        session: AsyncSession,
        batch_request: BatchJobCreate,
        user_id: str,
        api_key_id: str = None
    ) -> BatchJob:
        """Create a new batch job."""
        try:
            # Validate files list
            if not batch_request.files:
                raise ValidationError("At least one file must be provided")
            
            if len(batch_request.files) > 1000:
                raise ValidationError("Maximum 1000 files allowed per batch")
            
            # Create batch job
            batch_job = BatchJob(
                name=batch_request.name,
                description=batch_request.description,
                user_id=user_id,
                api_key_id=api_key_id,
                total_jobs=len(batch_request.files),
                max_concurrent_jobs=batch_request.max_concurrent_jobs,
                priority=batch_request.priority,
                input_settings=batch_request.input_settings or {},
                metadata=batch_request.metadata or {},
                max_retries=batch_request.max_retries,
                status=BatchStatus.PENDING
            )
            
            session.add(batch_job)
            await session.flush()
            await session.refresh(batch_job)
            
            # Create individual jobs for each file
            individual_jobs = []
            for i, file_info in enumerate(batch_request.files):
                job_data = {
                    'filename': file_info.get('filename'),
                    'user_id': user_id,
                    'conversion_type': file_info.get('conversion_type', 'auto'),
                    'batch_job_id': batch_job.id,
                    'priority': batch_request.priority,
                    'metadata': {
                        'batch_index': i,
                        'batch_total': len(batch_request.files),
                        **file_info.get('metadata', {}),
                        **batch_request.input_settings
                    }
                }
                
                # Merge file-specific settings with batch settings
                if 'input_url' in file_info:
                    job_data['input_url'] = file_info['input_url']
                if 'output_settings' in file_info:
                    job_data['output_settings'] = file_info['output_settings']
                
                individual_job = await self.job_service.create_job(session, **job_data)
                individual_jobs.append(individual_job)
            
            await session.commit()
            
            logger.info(
                "Batch job created",
                batch_id=str(batch_job.id),
                user_id=user_id,
                total_jobs=len(individual_jobs)
            )
            
            return batch_job
            
        except Exception as e:
            await session.rollback()
            logger.error("Failed to create batch job", error=str(e))
            raise
    
    async def get_batch_job(self, session: AsyncSession, batch_id: str) -> BatchJob:
        """Get batch job by ID."""
        stmt = select(BatchJob).where(BatchJob.id == batch_id)
        result = await session.execute(stmt)
        batch_job = result.scalar_one_or_none()
        
        if not batch_job:
            raise NotFoundError(f"Batch job {batch_id} not found")
        
        return batch_job
    
    async def list_batch_jobs(
        self,
        session: AsyncSession,
        user_id: str = None,
        status: BatchStatus = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[BatchJob], int]:
        """List batch jobs with filtering and pagination."""
        # Build query
        query = select(BatchJob)
        count_query = select(func.count(BatchJob.id))
        
        # Apply filters
        conditions = []
        if user_id:
            conditions.append(BatchJob.user_id == user_id)
        if status:
            conditions.append(BatchJob.status == status)
        
        if conditions:
            filter_condition = and_(*conditions)
            query = query.where(filter_condition)
            count_query = count_query.where(filter_condition)
        
        # Get total count
        total_result = await session.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination and ordering
        offset = (page - 1) * per_page
        query = query.order_by(BatchJob.created_at.desc()).offset(offset).limit(per_page)
        
        # Execute query
        result = await session.execute(query)
        batches = list(result.scalars().all())
        
        return batches, total
    
    async def update_batch_job(
        self,
        session: AsyncSession,
        batch_id: str,
        update_request: BatchJobUpdate
    ) -> BatchJob:
        """Update batch job."""
        batch_job = await self.get_batch_job(session, batch_id)
        
        # Check if batch can be updated
        if batch_job.is_complete:
            raise ValidationError("Cannot update completed batch job")
        
        # Update fields
        if update_request.name is not None:
            batch_job.name = update_request.name
        if update_request.description is not None:
            batch_job.description = update_request.description
        if update_request.priority is not None:
            batch_job.priority = update_request.priority
        if update_request.max_concurrent_jobs is not None:
            batch_job.max_concurrent_jobs = update_request.max_concurrent_jobs
        if update_request.status is not None:
            batch_job.status = update_request.status
        if update_request.metadata is not None:
            batch_job.metadata = update_request.metadata
        
        batch_job.updated_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(batch_job)
        
        return batch_job
    
    async def cancel_batch_job(self, session: AsyncSession, batch_id: str) -> BatchJob:
        """Cancel a batch job."""
        batch_job = await self.get_batch_job(session, batch_id)
        
        if batch_job.is_complete:
            raise ValidationError("Cannot cancel completed batch job")
        
        # Update status
        batch_job.status = BatchStatus.CANCELLED
        batch_job.completed_at = datetime.utcnow()
        batch_job.updated_at = datetime.utcnow()
        
        # Cancel all pending/processing individual jobs
        stmt = select(Job).where(
            and_(
                Job.batch_job_id == batch_id,
                Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
            )
        )
        result = await session.execute(stmt)
        jobs_to_cancel = result.scalars().all()
        
        for job in jobs_to_cancel:
            await self.job_service.update_job_status(
                session,
                job.id,
                JobStatus.CANCELLED,
                error_message="Batch job cancelled"
            )
        
        await session.commit()
        await session.refresh(batch_job)
        
        logger.info(
            "Batch job cancelled",
            batch_id=batch_id,
            cancelled_jobs=len(jobs_to_cancel)
        )
        
        return batch_job
    
    async def get_batch_progress(
        self,
        session: AsyncSession,
        batch_id: str,
        user_id: str = None
    ) -> BatchJobProgress:
        """Get real-time progress of a batch job."""
        batch_job = await self.get_batch_job(session, batch_id)
        
        # Check permissions
        if user_id and batch_job.user_id != user_id:
            raise NotFoundError("Batch job not found")
        
        # Get current job counts
        stmt = select(
            func.count(Job.id).filter(Job.status == JobStatus.COMPLETED).label('completed'),
            func.count(Job.id).filter(Job.status == JobStatus.FAILED).label('failed'),
            func.count(Job.id).filter(Job.status == JobStatus.PROCESSING).label('processing'),
            func.count(Job.id).label('total')
        ).where(Job.batch_job_id == batch_id)
        
        result = await session.execute(stmt)
        counts = result.first()
        
        # Get currently processing job
        current_job_stmt = select(Job.id).where(
            and_(
                Job.batch_job_id == batch_id,
                Job.status == JobStatus.PROCESSING
            )
        ).limit(1)
        current_job_result = await session.execute(current_job_stmt)
        current_job_id = current_job_result.scalar_one_or_none()
        
        # Calculate estimated completion
        estimated_completion = None
        if batch_job.status == BatchStatus.PROCESSING and counts.processing > 0:
            # Simple estimation based on average processing time
            avg_time = timedelta(minutes=5)  # Default estimation
            remaining_jobs = batch_job.total_jobs - counts.completed - counts.failed
            estimated_completion = datetime.utcnow() + (avg_time * remaining_jobs)
        
        return BatchJobProgress(
            batch_id=batch_id,
            status=batch_job.status,
            total_jobs=batch_job.total_jobs,
            completed_jobs=counts.completed or 0,
            failed_jobs=counts.failed or 0,
            processing_jobs=counts.processing or 0,
            progress_percentage=batch_job.progress_percentage,
            current_job_id=str(current_job_id) if current_job_id else None,
            estimated_completion=estimated_completion,
            error_message=batch_job.error_message
        )
    
    async def get_batch_statistics(
        self,
        session: AsyncSession,
        user_id: str = None
    ) -> BatchJobStats:
        """Get batch processing statistics."""
        # Build base query
        base_query = select(BatchJob)
        if user_id:
            base_query = base_query.where(BatchJob.user_id == user_id)
        
        # Get status counts
        status_counts = {}
        for status in BatchStatus:
            stmt = select(func.count(BatchJob.id)).where(BatchJob.status == status)
            if user_id:
                stmt = stmt.where(BatchJob.user_id == user_id)
            result = await session.execute(stmt)
            status_counts[status.value] = result.scalar() or 0
        
        # Get total jobs in all batches
        total_jobs_stmt = select(func.sum(BatchJob.total_jobs))
        if user_id:
            total_jobs_stmt = total_jobs_stmt.where(BatchJob.user_id == user_id)
        total_jobs_result = await session.execute(total_jobs_stmt)
        total_jobs_in_batches = total_jobs_result.scalar() or 0
        
        # Calculate average jobs per batch
        total_batches = sum(status_counts.values())
        avg_jobs_per_batch = (
            total_jobs_in_batches / total_batches 
            if total_batches > 0 else 0.0
        )
        
        # Calculate average completion time for completed batches
        avg_completion_time = None
        completed_batches_stmt = select(
            func.avg(
                func.extract('epoch', BatchJob.completed_at - BatchJob.created_at) / 60
            )
        ).where(
            and_(
                BatchJob.status == BatchStatus.COMPLETED,
                BatchJob.completed_at.isnot(None)
            )
        )
        if user_id:
            completed_batches_stmt = completed_batches_stmt.where(BatchJob.user_id == user_id)
        
        avg_time_result = await session.execute(completed_batches_stmt)
        avg_completion_time = avg_time_result.scalar()
        
        # Calculate overall success rate
        completed_jobs_stmt = select(func.sum(BatchJob.completed_jobs))
        if user_id:
            completed_jobs_stmt = completed_jobs_stmt.where(BatchJob.user_id == user_id)
        completed_jobs_result = await session.execute(completed_jobs_stmt)
        total_completed_jobs = completed_jobs_result.scalar() or 0
        
        overall_success_rate = (
            (total_completed_jobs / total_jobs_in_batches * 100)
            if total_jobs_in_batches > 0 else 0.0
        )
        
        return BatchJobStats(
            total_batches=total_batches,
            pending_batches=status_counts.get('pending', 0),
            processing_batches=status_counts.get('processing', 0),
            completed_batches=status_counts.get('completed', 0),
            failed_batches=status_counts.get('failed', 0),
            total_jobs_in_batches=total_jobs_in_batches,
            avg_jobs_per_batch=avg_jobs_per_batch,
            avg_completion_time_minutes=avg_completion_time,
            overall_success_rate=overall_success_rate
        )
    
    async def start_batch_processing(self, batch_id: str):
        """Start processing a batch job (background task)."""
        # This would be implemented as a background task
        # For now, just log that processing would start
        logger.info("Batch processing started", batch_id=batch_id)
        
        # In a real implementation, this would:
        # 1. Update batch status to PROCESSING
        # 2. Schedule individual jobs based on max_concurrent_jobs
        # 3. Monitor progress and update batch status
        # 4. Handle failures and retries
    
    async def retry_failed_jobs(self, session: AsyncSession, batch_id: str):
        """Retry failed jobs in a batch."""
        batch_job = await self.get_batch_job(session, batch_id)
        
        if batch_job.retry_count >= batch_job.max_retries:
            raise ValidationError("Maximum retries exceeded for this batch")
        
        # Get failed jobs
        stmt = select(Job).where(
            and_(
                Job.batch_job_id == batch_id,
                Job.status == JobStatus.FAILED
            )
        )
        result = await session.execute(stmt)
        failed_jobs = result.scalars().all()
        
        # Reset failed jobs to pending
        retry_count = 0
        for job in failed_jobs:
            await self.job_service.update_job_status(
                session,
                job.id,
                JobStatus.PENDING,
                error_message=None,
                retry_count=job.retry_count + 1
            )
            retry_count += 1
        
        # Update batch retry count
        batch_job.retry_count += 1
        batch_job.status = BatchStatus.PROCESSING
        batch_job.updated_at = datetime.utcnow()
        
        await session.commit()
        
        logger.info(
            "Batch jobs retried",
            batch_id=batch_id,
            retried_jobs=retry_count
        )