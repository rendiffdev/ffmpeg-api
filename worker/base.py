"""
Base classes for worker tasks and processors to eliminate code duplication
"""
import asyncio
import tempfile
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, AsyncGenerator
import structlog

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from celery import current_task

from api.config import settings
from api.models.job import Job, JobStatus
from storage.factory import create_storage_backend
from worker.utils.progress import ProgressTracker

logger = structlog.get_logger()


class ProcessingError(Exception):
    """Custom exception for processing errors."""
    pass


class AsyncDatabaseMixin:
    """Mixin for async database operations."""
    
    _async_engine = None
    _async_session_maker = None
    _sync_engine = None
    _sync_session_maker = None
    
    @classmethod
    def _get_sync_engine(cls):
        """Get synchronous database engine (for compatibility)."""
        if cls._sync_engine is None:
            if "sqlite" in settings.DATABASE_URL:
                cls._sync_engine = create_engine(
                    settings.DATABASE_URL,
                    connect_args={"check_same_thread": False},
                    pool_pre_ping=True
                )
            else:
                cls._sync_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        return cls._sync_engine
    
    @classmethod
    def _get_sync_session_maker(cls):
        """Get synchronous session maker."""
        if cls._sync_session_maker is None:
            cls._sync_session_maker = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=cls._get_sync_engine()
            )
        return cls._sync_session_maker
    
    @classmethod
    def _get_async_engine(cls):
        """Get async database engine."""
        if cls._async_engine is None:
            # Convert sync URL to async URL
            async_url = settings.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
            if "postgresql://" in async_url:
                async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
            
            cls._async_engine = create_async_engine(
                async_url,
                pool_pre_ping=True,
                echo=settings.DEBUG
            )
        return cls._async_engine
    
    @classmethod
    def _get_async_session_maker(cls):
        """Get async session maker."""
        if cls._async_session_maker is None:
            cls._async_session_maker = async_sessionmaker(
                cls._get_async_engine(),
                class_=AsyncSession,
                expire_on_commit=False
            )
        return cls._async_session_maker
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session."""
        session_maker = self._get_async_session_maker()
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    def get_sync_session(self):
        """Get synchronous database session (for compatibility)."""
        return self._get_sync_session_maker()()


class BaseWorkerTask(AsyncDatabaseMixin):
    """Base class for all worker tasks with common functionality."""
    
    def __init__(self):
        self.job_id: Optional[str] = None
        self.progress_tracker: Optional[ProgressTracker] = None
    
    def parse_storage_path(self, path: str) -> Tuple[str, str]:
        """Parse storage path into backend name and path."""
        if "://" in path:
            parts = path.split("://", 1)
            return parts[0], parts[1]
        return "local", path
    
    async def get_job(self, job_id: str) -> Job:
        """Get job from database."""
        async with self.get_async_session() as session:
            result = await session.get(Job, job_id)
            if not result:
                raise ProcessingError(f"Job {job_id} not found")
            return result
    
    async def update_job_status(self, job_id: str, status: JobStatus, **kwargs) -> None:
        """Update job status and other fields."""
        async with self.get_async_session() as session:
            job = await session.get(Job, job_id)
            if job:
                job.status = status
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                await session.commit()
                logger.info(f"Job {job_id} status updated to {status}")
                
                # Invalidate job cache after status update
                try:
                    from api.cache import invalidate_job_cache
                    await invalidate_job_cache(job_id)
                except ImportError:
                    # Cache service not available, skip invalidation
                    pass
                except Exception as e:
                    logger.warning(f"Failed to invalidate job cache for {job_id}: {e}")
    
    def update_job_status_sync(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update job status synchronously (for compatibility)."""
        session = self.get_sync_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                for key, value in updates.items():
                    setattr(job, key, value)
                session.commit()
                logger.info(f"Job {job_id} updated: {list(updates.keys())}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update job {job_id}: {e}")
            raise
        finally:
            session.close()
    
    async def handle_job_error(self, job_id: str, error: Exception) -> None:
        """Handle job error with status update."""
        error_message = str(error)
        logger.error(f"Job {job_id} failed: {error_message}")
        
        await self.update_job_status(
            job_id, 
            JobStatus.FAILED,
            error_message=error_message,
            completed_at=datetime.utcnow()
        )
        
        # Send error webhook
        await self.send_webhook(job_id, "error", {
            "job_id": job_id,
            "status": "failed",
            "error": error_message,
        })
    
    async def send_webhook(self, job_id: str, event: str, data: Dict[str, Any]) -> None:
        """Send webhook notification."""
        try:
            # Get job to retrieve webhook URL
            job = await self.get_job(job_id)
            if not job.webhook_url:
                return
            
            # Use the webhook service for actual HTTP delivery
            from worker.webhooks import webhook_service
            
            # Add standard fields to payload
            payload = {
                "event": event,
                "timestamp": datetime.utcnow().isoformat(),
                "job_id": job_id,
                **data
            }
            
            success = await webhook_service.send_webhook(
                job_id=job_id,
                event=event,
                webhook_url=job.webhook_url,
                payload=payload,
                retry=True
            )
            
            if success:
                logger.info(f"Webhook delivered successfully: {event}", job_id=job_id)
            else:
                logger.warning(f"Webhook delivery failed: {event}", job_id=job_id)
                
        except Exception as e:
            logger.error(f"Webhook failed for job {job_id}: {e}")
    
    async def get_webhook_delivery_status(self, job_id: str) -> list:
        """Get webhook delivery status for a job."""
        try:
            from worker.webhooks import webhook_service
            return webhook_service.get_delivery_status(job_id)
        except Exception as e:
            logger.error(f"Failed to get webhook status for job {job_id}: {e}")
            return []
    
    async def cleanup_webhook_resources(self) -> None:
        """Clean up webhook service resources."""
        try:
            from worker.webhooks import webhook_service
            await webhook_service.cleanup()
            logger.info("Webhook service resources cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup webhook resources: {e}")
    
    async def create_storage_backends(self, input_path: str, output_path: str) -> Tuple[Any, Any]:
        """Create input and output storage backends."""
        # Load storage configuration
        import yaml
        with open(settings.STORAGE_CONFIG, 'r') as f:
            storage_config = yaml.safe_load(f)
        
        # Parse paths
        input_backend_name, input_relative_path = self.parse_storage_path(input_path)
        output_backend_name, output_relative_path = self.parse_storage_path(output_path)
        
        # Create backends
        input_backend = create_storage_backend(
            storage_config["backends"][input_backend_name]
        )
        output_backend = create_storage_backend(
            storage_config["backends"][output_backend_name]
        )
        
        return input_backend, output_backend
    
    async def download_file(self, backend: Any, remote_path: str, local_path: Path) -> None:
        """Download file from storage backend to local path."""
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            async with await backend.read(remote_path) as stream:
                with open(local_path, 'wb') as f:
                    async for chunk in stream:
                        f.write(chunk)
            logger.info(f"Downloaded file: {remote_path} -> {local_path}")
        except Exception as e:
            logger.error(f"Failed to download {remote_path}: {e}")
            raise ProcessingError(f"Download failed: {e}")
    
    async def upload_file(self, backend: Any, local_path: Path, remote_path: str) -> None:
        """Upload local file to storage backend."""
        try:
            with open(local_path, 'rb') as f:
                await backend.write(remote_path, f)
            logger.info(f"Uploaded file: {local_path} -> {remote_path}")
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            raise ProcessingError(f"Upload failed: {e}")
    
    async def with_temp_directory(self, prefix: str = "rendiff_"):
        """Context manager for temporary directory."""
        return tempfile.TemporaryDirectory(prefix=prefix)
    
    def set_worker_info(self, job_id: str) -> None:
        """Set worker information for the current task."""
        self.job_id = job_id
        self.progress_tracker = ProgressTracker(job_id)
    
    async def start_job_processing(self, job_id: str) -> Job:
        """Start job processing with status update."""
        await self.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            started_at=datetime.utcnow(),
            worker_id=current_task.request.hostname if current_task else "unknown"
        )
        
        job = await self.get_job(job_id)
        self.set_worker_info(job_id)
        return job
    
    async def complete_job_processing(self, job_id: str, result: Dict[str, Any]) -> None:
        """Complete job processing with status update and webhook."""
        updates = {
            "status": JobStatus.COMPLETED,
            "completed_at": datetime.utcnow(),
            "progress": 100.0
        }
        
        # Add metrics if available
        if result.get("vmaf_score"):
            updates["vmaf_score"] = result["vmaf_score"]
        if result.get("psnr_score"):
            updates["psnr_score"] = result["psnr_score"]
        
        # Calculate processing time
        job = await self.get_job(job_id)
        if job.started_at:
            updates["processing_time"] = (updates["completed_at"] - job.started_at).total_seconds()
        
        await self.update_job_status(job_id, JobStatus.COMPLETED, **updates)
        
        # Send completion webhook
        await self.send_webhook(job_id, "complete", {
            "job_id": job_id,
            "status": "completed",
            "output_path": job.output_path,
            "metrics": result.get("metrics", {}),
        })
        
        logger.info(f"Job completed: {job_id}")


class BaseProcessor(ABC):
    """Base class for all media processors."""
    
    def __init__(self):
        self.initialized = False
        self.logger = structlog.get_logger(self.__class__.__name__)
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the processor."""
        pass
    
    @abstractmethod
    async def process(
        self, 
        input_path: str, 
        output_path: str, 
        options: Dict[str, Any],
        operations: list,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Process the media file."""
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> Dict[str, list]:
        """Get supported input and output formats."""
        pass
    
    async def validate_input(self, input_path: str) -> bool:
        """Validate input file."""
        path = Path(input_path)
        if not path.exists():
            raise ProcessingError(f"Input file does not exist: {input_path}")
        if path.stat().st_size == 0:
            raise ProcessingError(f"Input file is empty: {input_path}")
        return True
    
    async def validate_output(self, output_path: str) -> bool:
        """Validate output path."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return True
    
    async def cleanup_resources(self) -> None:
        """Clean up any resources used by the processor."""
        self.logger.info("Processor cleanup completed")
    
    async def safe_process(
        self,
        input_path: str,
        output_path: str,
        options: Dict[str, Any],
        operations: list,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Process with error handling and validation."""
        try:
            # Ensure processor is initialized
            if not self.initialized:
                await self.initialize()
            
            # Validate inputs
            await self.validate_input(input_path)
            await self.validate_output(output_path)
            
            self.logger.info(
                "Processing started",
                input_path=input_path,
                output_path=output_path
            )
            
            # Process the file
            result = await self.process(
                input_path, output_path, options, operations, progress_callback
            )
            
            self.logger.info("Processing completed", result_keys=list(result.keys()))
            return result
            
        except Exception as e:
            self.logger.error("Processing failed", error=str(e))
            raise ProcessingError(f"Processing failed: {e}")
        finally:
            await self.cleanup_resources()


class TaskExecutionMixin:
    """Mixin for task execution patterns."""
    
    async def execute_with_error_handling(
        self, 
        job_id: str, 
        processing_func: callable,
        *args, 
        **kwargs
    ) -> Dict[str, Any]:
        """Execute processing function with comprehensive error handling."""
        try:
            # Start job processing
            job = await self.start_job_processing(job_id)
            
            # Execute the processing function
            result = await processing_func(job, *args, **kwargs)
            
            # Complete job processing
            await self.complete_job_processing(job_id, result)
            
            return result
            
        except Exception as e:
            # Handle job error
            await self.handle_job_error(job_id, e)
            raise
        finally:
            # Clean up webhook resources if this is the final task
            try:
                await self.cleanup_webhook_resources()
            except Exception as cleanup_error:
                logger.warning(f"Webhook cleanup failed: {cleanup_error}")