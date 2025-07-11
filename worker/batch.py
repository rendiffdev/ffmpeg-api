"""
Batch processing worker
"""
import asyncio
from typing import List, Optional
from datetime import datetime
import structlog

from api.models.batch import BatchJob, BatchStatus
from api.models.job import Job, JobStatus
from api.services.batch_service import BatchService
from worker.base import BaseWorkerTask

logger = structlog.get_logger()


class BatchProcessor(BaseWorkerTask):
    """Worker for processing batch jobs."""
    
    def __init__(self):
        super().__init__()
        self.batch_service = BatchService()
        self.max_concurrent_workers = 5
        self.processing_batches = set()
    
    async def process_batch_job(self, batch_id: str) -> None:
        """Process a batch job."""
        if batch_id in self.processing_batches:
            logger.info("Batch already being processed", batch_id=batch_id)
            return
        
        self.processing_batches.add(batch_id)
        
        try:
            async with self.get_database_session() as session:
                batch_job = await self.batch_service.get_batch_job(session, batch_id)
                
                if batch_job.status != BatchStatus.PENDING:
                    logger.info(
                        "Batch job not in pending status",
                        batch_id=batch_id,
                        status=batch_job.status
                    )
                    return
                
                # Update status to processing
                batch_job.status = BatchStatus.PROCESSING
                batch_job.started_at = datetime.utcnow()
                batch_job.updated_at = datetime.utcnow()
                await session.commit()
                
                logger.info(
                    "Starting batch processing",
                    batch_id=batch_id,
                    total_jobs=batch_job.total_jobs,
                    max_concurrent=batch_job.max_concurrent_jobs
                )
                
                # Process jobs in batches
                await self._process_jobs_concurrently(session, batch_job)
                
                # Update final status
                await self._update_batch_completion_status(session, batch_job)
                
        except Exception as e:
            logger.error(
                "Batch processing failed",
                batch_id=batch_id,
                error=str(e)
            )
            
            # Mark batch as failed
            try:
                async with self.get_database_session() as session:
                    batch_job = await self.batch_service.get_batch_job(session, batch_id)
                    batch_job.status = BatchStatus.FAILED
                    batch_job.error_message = str(e)
                    batch_job.completed_at = datetime.utcnow()
                    batch_job.updated_at = datetime.utcnow()
                    await session.commit()
            except Exception as cleanup_error:
                logger.error(
                    "Failed to update batch status after error",
                    batch_id=batch_id,
                    error=str(cleanup_error)
                )
        
        finally:
            self.processing_batches.discard(batch_id)
    
    async def _process_jobs_concurrently(self, session, batch_job: BatchJob) -> None:
        """Process individual jobs with concurrency limits."""
        from sqlalchemy import select, and_
        
        # Get all pending jobs for this batch
        stmt = select(Job).where(
            and_(
                Job.batch_job_id == batch_job.id,
                Job.status == JobStatus.PENDING
            )
        ).order_by(Job.created_at.asc())
        
        result = await session.execute(stmt)
        pending_jobs = list(result.scalars().all())
        
        if not pending_jobs:
            logger.info("No pending jobs found for batch", batch_id=str(batch_job.id))
            return
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(batch_job.max_concurrent_jobs)
        
        # Create tasks for all jobs
        tasks = []
        for job in pending_jobs:
            task = asyncio.create_task(
                self._process_single_job_with_semaphore(semaphore, job.id)
            )
            tasks.append(task)
        
        # Wait for all jobs to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(
            "Batch job processing completed",
            batch_id=str(batch_job.id),
            total_jobs=len(tasks)
        )
    
    async def _process_single_job_with_semaphore(self, semaphore: asyncio.Semaphore, job_id: str) -> None:
        """Process a single job with concurrency control."""
        async with semaphore:
            try:
                # Import here to avoid circular imports
                from worker.tasks import process_conversion_job
                
                logger.info("Starting job processing", job_id=job_id)
                
                # Process the individual job
                await process_conversion_job(job_id)
                
                logger.info("Job processing completed", job_id=job_id)
                
            except Exception as e:
                logger.error(
                    "Individual job processing failed",
                    job_id=job_id,
                    error=str(e)
                )
                
                # Update job status to failed
                try:
                    async with self.get_database_session() as session:
                        await self.job_service.fail_job(
                            session,
                            job_id,
                            f"Job processing failed: {str(e)}"
                        )
                except Exception as update_error:
                    logger.error(
                        "Failed to update job status after error",
                        job_id=job_id,
                        error=str(update_error)
                    )
    
    async def _update_batch_completion_status(self, session, batch_job: BatchJob) -> None:
        """Update batch job status based on individual job results."""
        from sqlalchemy import select, func, and_
        
        # Get job status counts
        stmt = select(
            func.count(Job.id).filter(Job.status == JobStatus.COMPLETED).label('completed'),
            func.count(Job.id).filter(Job.status == JobStatus.FAILED).label('failed'),
            func.count(Job.id).filter(Job.status == JobStatus.PROCESSING).label('processing'),
            func.count(Job.id).filter(Job.status == JobStatus.PENDING).label('pending')
        ).where(Job.batch_job_id == batch_job.id)
        
        result = await session.execute(stmt)
        counts = result.first()
        
        # Update batch job counters
        batch_job.completed_jobs = counts.completed or 0
        batch_job.failed_jobs = counts.failed or 0
        batch_job.processing_jobs = counts.processing or 0
        
        # Determine final status
        if counts.processing > 0 or counts.pending > 0:
            # Still has jobs in progress
            batch_job.status = BatchStatus.PROCESSING
        elif counts.failed > 0 and counts.completed == 0:
            # All jobs failed
            batch_job.status = BatchStatus.FAILED
            batch_job.completed_at = datetime.utcnow()
            batch_job.error_message = "All jobs in batch failed"
        elif counts.failed > 0:
            # Some jobs failed, some succeeded
            batch_job.status = BatchStatus.COMPLETED
            batch_job.completed_at = datetime.utcnow()
            batch_job.error_message = f"{counts.failed} out of {batch_job.total_jobs} jobs failed"
        else:
            # All jobs completed successfully
            batch_job.status = BatchStatus.COMPLETED
            batch_job.completed_at = datetime.utcnow()
            batch_job.error_message = None
        
        batch_job.updated_at = datetime.utcnow()
        await session.commit()
        
        logger.info(
            "Batch status updated",
            batch_id=str(batch_job.id),
            status=batch_job.status,
            completed=batch_job.completed_jobs,
            failed=batch_job.failed_jobs
        )
    
    async def get_pending_batches(self) -> List[BatchJob]:
        """Get all pending batch jobs."""
        async with self.get_database_session() as session:
            from sqlalchemy import select
            
            stmt = select(BatchJob).where(
                BatchJob.status == BatchStatus.PENDING
            ).order_by(BatchJob.priority.desc(), BatchJob.created_at.asc())
            
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def monitor_processing_batches(self) -> None:
        """Monitor and update processing batches."""
        async with self.get_database_session() as session:
            from sqlalchemy import select
            
            stmt = select(BatchJob).where(
                BatchJob.status == BatchStatus.PROCESSING
            )
            
            result = await session.execute(stmt)
            processing_batches = list(result.scalars().all())
            
            for batch in processing_batches:
                if str(batch.id) not in self.processing_batches:
                    # This batch is marked as processing but not in our active set
                    # Check if it actually has any processing jobs
                    await self._update_batch_completion_status(session, batch)
    
    async def run_batch_scheduler(self) -> None:
        """Main scheduler loop for batch processing."""
        logger.info("Starting batch scheduler")
        
        while True:
            try:
                # Monitor existing processing batches
                await self.monitor_processing_batches()
                
                # Get pending batches
                pending_batches = await self.get_pending_batches()
                
                # Start processing batches up to the limit
                available_slots = self.max_concurrent_workers - len(self.processing_batches)
                
                for batch in pending_batches[:available_slots]:
                    # Start processing in background
                    asyncio.create_task(self.process_batch_job(str(batch.id)))
                    await asyncio.sleep(1)  # Small delay between starts
                
                # Wait before next iteration
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error("Batch scheduler error", error=str(e))
                await asyncio.sleep(60)  # Wait longer on error


# Background task functions
async def start_batch_processing(batch_id: str) -> None:
    """Start processing a batch job (called from API)."""
    processor = BatchProcessor()
    await processor.process_batch_job(batch_id)


async def run_batch_scheduler() -> None:
    """Run the batch scheduler (called from worker main)."""
    processor = BatchProcessor()
    await processor.run_batch_scheduler()