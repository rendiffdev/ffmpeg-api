"""
Admin endpoints for system management
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import structlog

from api.config import settings
from api.dependencies import get_db, require_api_key
from api.models.job import Job, JobStatus
from api.services.queue import QueueService
from api.services.storage import StorageService

logger = structlog.get_logger()
router = APIRouter()

queue_service = QueueService()
storage_service = StorageService()


async def require_admin(api_key: str = Depends(require_api_key)) -> str:
    """Require admin privileges."""
    # In production, check if API key has admin role
    # For now, just check a specific key
    if api_key != "admin":  # Replace with proper admin check
        raise HTTPException(status_code=403, detail="Admin access required")
    return api_key


@router.get("/workers")
async def get_workers_status(
    admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Get status of all workers in the system.
    """
    try:
        workers = await queue_service.get_workers_status()
        
        return {
            "total_workers": len(workers),
            "workers": workers,
            "summary": {
                "active": sum(1 for w in workers if w.get("status") == "active"),
                "idle": sum(1 for w in workers if w.get("status") == "idle"),
                "offline": sum(1 for w in workers if w.get("status") == "offline"),
            },
        }
    except Exception as e:
        logger.error("Failed to get workers status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get workers status")


@router.get("/storage")
async def get_storage_status(
    admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Get status of all storage backends.
    """
    try:
        storage_status = {}
        
        for name, backend in storage_service.backends.items():
            try:
                # Get backend-specific status
                status = await backend.get_status()
                storage_status[name] = {
                    "status": "healthy",
                    "type": backend.__class__.__name__,
                    **status,
                }
            except Exception as e:
                storage_status[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
        
        return {
            "backends": storage_status,
            "default_backend": storage_service.config.get("default_backend"),
            "policies": storage_service.config.get("policies", {}),
        }
    except Exception as e:
        logger.error("Failed to get storage status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get storage status")


@router.get("/stats")
async def get_system_stats(
    period: str = Query("24h", regex=r"^(\d+[hdwm])$"),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Get system statistics for the specified period.
    """
    # Parse period
    unit = period[-1]
    value = int(period[:-1])
    
    if unit == "h":
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)
    elif unit == "w":
        delta = timedelta(weeks=value)
    elif unit == "m":
        delta = timedelta(days=value * 30)
    
    start_time = datetime.utcnow() - delta
    
    # Get job statistics
    stats_query = (
        select(
            Job.status,
            func.count(Job.id).label("count"),
            func.avg(Job.processing_time).label("avg_time"),
            func.avg(Job.vmaf_score).label("avg_vmaf"),
        )
        .where(Job.created_at >= start_time)
        .group_by(Job.status)
    )
    
    result = await db.execute(stats_query)
    job_stats = result.all()
    
    # Format statistics
    stats = {
        "period": period,
        "start_time": start_time.isoformat(),
        "jobs": {
            "total": sum(row.count for row in job_stats),
            "by_status": {row.status: row.count for row in job_stats},
            "avg_processing_time": sum(row.avg_time or 0 for row in job_stats) / len(job_stats) if job_stats else 0,
            "avg_vmaf_score": sum(row.avg_vmaf or 0 for row in job_stats if row.avg_vmaf) / sum(1 for row in job_stats if row.avg_vmaf) if any(row.avg_vmaf for row in job_stats) else None,
        },
        "queue": await queue_service.get_queue_stats(),
        "workers": await queue_service.get_workers_stats(),
    }
    
    return stats


@router.post("/cleanup")
async def cleanup_old_jobs(
    days: int = Query(7, ge=1, le=90),
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Clean up old completed jobs and their associated files.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Find old jobs
    query = select(Job).where(
        and_(
            Job.completed_at < cutoff_date,
            Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
        )
    )
    
    result = await db.execute(query)
    old_jobs = result.scalars().all()
    
    if dry_run:
        return {
            "dry_run": True,
            "jobs_to_delete": len(old_jobs),
            "cutoff_date": cutoff_date.isoformat(),
        }
    
    # Delete files and jobs
    deleted_count = 0
    errors = []
    
    for job in old_jobs:
        try:
            # Delete output file if it exists
            if job.output_path:
                backend_name, file_path = storage_service.parse_uri(job.output_path)
                backend = storage_service.backends.get(backend_name)
                if backend:
                    await backend.delete(file_path)
            
            # Delete job record
            await db.delete(job)
            deleted_count += 1
            
        except Exception as e:
            errors.append({
                "job_id": str(job.id),
                "error": str(e),
            })
    
    await db.commit()
    
    logger.info(f"Cleanup completed: {deleted_count} jobs deleted")
    
    return {
        "dry_run": False,
        "jobs_deleted": deleted_count,
        "errors": errors,
        "cutoff_date": cutoff_date.isoformat(),
    }


@router.post("/presets")
async def create_preset(
    preset: Dict[str, Any],
    admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Create a new encoding preset.
    """
    # Validate preset
    if "name" not in preset:
        raise HTTPException(status_code=400, detail="Preset name required")
    
    if "settings" not in preset:
        raise HTTPException(status_code=400, detail="Preset settings required")
    
    # Save preset (in production, save to database)
    # For now, just return success
    logger.info(f"Preset created: {preset['name']}")
    
    return {
        "message": "Preset created successfully",
        "preset": preset,
    }


@router.get("/presets")
async def list_presets() -> List[Dict[str, Any]]:
    """
    List available encoding presets.
    """
    # In production, load from database
    # For now, return built-in presets
    return [
        {
            "name": "web-1080p",
            "description": "Standard 1080p for web streaming",
            "settings": {
                "video": {
                    "codec": "h264",
                    "preset": "medium",
                    "crf": 23,
                    "resolution": "1920x1080",
                },
                "audio": {
                    "codec": "aac",
                    "bitrate": "128k",
                },
            },
        },
        {
            "name": "web-720p",
            "description": "Standard 720p for web streaming",
            "settings": {
                "video": {
                    "codec": "h264",
                    "preset": "medium",
                    "crf": 23,
                    "resolution": "1280x720",
                },
                "audio": {
                    "codec": "aac",
                    "bitrate": "128k",
                },
            },
        },
        {
            "name": "archive-high",
            "description": "High quality for archival",
            "settings": {
                "video": {
                    "codec": "h265",
                    "preset": "slow",
                    "crf": 18,
                },
                "audio": {
                    "codec": "flac",
                },
            },
        },
    ]