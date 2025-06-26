"""Progress tracking utilities"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.config import settings
from api.models.job import Job, JobStatus

logger = structlog.get_logger()

# Database setup for progress updates
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )
else:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ProgressTracker:
    """Tracks job processing progress with real-time updates."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.last_update = datetime.utcnow()
        self.update_interval = 2.0  # Update every 2 seconds
        self.last_percentage = 0.0
        
    async def update(self, percentage: float, stage: str, message: str, 
                    stats: Optional[Dict[str, Any]] = None):
        """Update job progress in database and emit events."""
        try:
            # Throttle updates to avoid database spam
            now = datetime.utcnow()
            time_since_last = (now - self.last_update).total_seconds()
            
            # Always update for major stage changes or completion
            force_update = (
                percentage >= 100.0 or 
                abs(percentage - self.last_percentage) >= 5.0 or
                time_since_last >= self.update_interval
            )
            
            if not force_update:
                return
            
            db = SessionLocal()
            try:
                job = db.query(Job).filter(Job.id == self.job_id).first()
                if job:
                    job.progress = min(100.0, max(0.0, percentage))
                    job.current_stage = stage
                    job.status_message = message
                    job.updated_at = now
                    
                    # Update processing stats if provided
                    if stats:
                        processing_stats = job.processing_stats or {}
                        processing_stats.update({
                            'current_frame': stats.get('frame'),
                            'fps': stats.get('fps'),
                            'bitrate': stats.get('bitrate'),
                            'speed': stats.get('speed'),
                            'time_processed': stats.get('time'),
                            'last_update': now.isoformat()
                        })
                        job.processing_stats = processing_stats
                    
                    db.commit()
                    
                    # Log progress update
                    logger.info(
                        "Progress updated",
                        job_id=self.job_id,
                        stage=stage,
                        percentage=percentage,
                        message=message,
                        stats=stats
                    )
                    
                    self.last_update = now
                    self.last_percentage = percentage
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(
                "Failed to update progress",
                job_id=self.job_id,
                error=str(e)
            )
    
    async def ffmpeg_callback(self, stats: Dict[str, Any]):
        """Handle FFmpeg progress callback."""
        try:
            percentage = stats.get('percentage', 0.0)
            stage = "processing"
            
            # Create detailed message from stats
            message_parts = []
            if 'frame' in stats:
                message_parts.append(f"Frame {stats['frame']}")
            if 'fps' in stats:
                message_parts.append(f"FPS {stats['fps']:.1f}")
            if 'speed' in stats:
                message_parts.append(f"Speed {stats['speed']:.1f}x")
            if 'bitrate' in stats:
                message_parts.append(f"Bitrate {stats['bitrate']:.1f}kbps")
            
            message = " | ".join(message_parts) if message_parts else "Processing video"
            
            await self.update(percentage, stage, message, stats)
            
        except Exception as e:
            logger.error(
                "FFmpeg callback failed",
                job_id=self.job_id,
                error=str(e),
                stats=stats
            )
    
    async def set_stage(self, stage: str, message: str, percentage: Optional[float] = None):
        """Set processing stage with optional percentage."""
        if percentage is None:
            percentage = self.last_percentage
        await self.update(percentage, stage, message)
    
    async def complete(self, message: str = "Processing completed"):
        """Mark job as completed."""
        await self.update(100.0, "completed", message)
    
    async def error(self, error_message: str):
        """Mark job as failed with error."""
        try:
            db = SessionLocal()
            try:
                job = db.query(Job).filter(Job.id == self.job_id).first()
                if job:
                    job.status = JobStatus.FAILED
                    job.error_message = error_message
                    job.current_stage = "failed"
                    job.status_message = error_message
                    job.updated_at = datetime.utcnow()
                    db.commit()
                    
                    logger.error(
                        "Job marked as failed",
                        job_id=self.job_id,
                        error=error_message
                    )
            finally:
                db.close()
                
        except Exception as e:
            logger.error(
                "Failed to mark job as failed",
                job_id=self.job_id,
                error=str(e)
            )