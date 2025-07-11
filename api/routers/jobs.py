"""
Jobs endpoint - Job management and monitoring
"""
from typing import Optional, List
from uuid import UUID
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import structlog

from api.config import settings
from api.dependencies import get_db, get_current_user, require_api_key
from api.models.job import Job, JobStatus, JobResponse, JobListResponse, JobProgress
from api.models.api_key import ApiKeyUser
from api.services.queue import QueueService
from api.decorators import cache_response, cache_database_query, invalidate_cache, skip_on_post_request
from api.cache import CacheKeyBuilder, get_cached_job_data, cache_job_data, invalidate_job_cache

logger = structlog.get_logger()
router = APIRouter()

queue_service = QueueService()


@router.get("/jobs", response_model=JobListResponse)
@cache_response(
    ttl=60,
    cache_type="job_list",
    skip_if=skip_on_post_request,
    vary_on=["api_key", "user_role"]
)
async def list_jobs(
    status: Optional[JobStatus] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at:desc"),
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> JobListResponse:
    """
    List jobs with optional filtering and pagination.
    """
    user, api_key = user_data
    
    # Parse sort parameter
    sort_field, sort_order = sort.split(":") if ":" in sort else (sort, "asc")
    
    # Build query - for anonymous users or API key users
    if user.id == "anonymous":
        # Anonymous users see all jobs (for backward compatibility when auth is disabled)
        query = select(Job)
    else:
        # Regular users see only their own jobs (based on API key)
        if user.is_admin:
            # Admin users see all jobs
            query = select(Job)
        else:
            # Regular users see only jobs created with their API key
            # Use the raw API key for backward compatibility
            query = select(Job).where(Job.api_key == api_key)
    
    if status:
        query = query.where(Job.status == status)
    
    # Apply sorting
    order_column = getattr(Job, sort_field, Job.created_at)
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Convert to response models
    job_responses = []
    for job in jobs:
        job_response = JobResponse(
            id=job.id,
            status=job.status,
            priority=job.priority,
            progress=job.progress,
            stage=job.stage,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            eta_seconds=job.eta_seconds,
            links={
                "self": f"/api/v1/jobs/{job.id}",
                "events": f"/api/v1/jobs/{job.id}/events",
                "logs": f"/api/v1/jobs/{job.id}/logs",
            },
        )
        
        if job.status == JobStatus.FAILED:
            job_response.error = {
                "message": job.error_message,
                "details": job.error_details,
            }
        
        job_responses.append(job_response)
    
    return JobListResponse(
        jobs=job_responses,
        total=total,
        page=page,
        per_page=per_page,
        has_next=total > page * per_page,
        has_prev=page > 1,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
@cache_response(
    ttl=30,
    cache_type="job_status",
    vary_on=["api_key"]
)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
) -> JobResponse:
    """
    Get detailed information about a specific job.
    """
    # Get job from database
    job = await db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check ownership
    if job.api_key != api_key:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Build response
    response = JobResponse(
        id=job.id,
        status=job.status,
        priority=job.priority,
        progress=job.progress,
        stage=job.stage,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        eta_seconds=job.eta_seconds,
        links={
            "self": f"/api/v1/jobs/{job.id}",
            "events": f"/api/v1/jobs/{job.id}/events",
            "logs": f"/api/v1/jobs/{job.id}/logs",
            "cancel": f"/api/v1/jobs/{job.id}" if job.status in [JobStatus.QUEUED, JobStatus.PROCESSING] else None,
        },
    )
    
    # Add progress details
    if job.status == JobStatus.PROCESSING:
        response.progress_details = {
            "percentage": job.progress,
            "stage": job.stage,
            "fps": job.fps,
            "eta_seconds": job.eta_seconds,
        }
    
    # Add error details if failed
    if job.status == JobStatus.FAILED:
        response.error = {
            "message": job.error_message,
            "details": job.error_details,
            "retry_count": job.retry_count,
        }
    
    # Add quality metrics if available
    if job.vmaf_score or job.psnr_score or job.ssim_score:
        response.progress_details = response.progress_details or {}
        response.progress_details["quality"] = {}
        if job.vmaf_score:
            response.progress_details["quality"]["vmaf"] = job.vmaf_score
        if job.psnr_score:
            response.progress_details["quality"]["psnr"] = job.psnr_score
        if job.ssim_score:
            response.progress_details["quality"]["ssim"] = job.ssim_score
    
    return response


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
) -> dict:
    """
    Cancel a queued or processing job.
    """
    # Get job
    job = await db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check ownership
    if job.api_key != api_key:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if job can be cancelled
    if job.status not in [JobStatus.QUEUED, JobStatus.PROCESSING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job.status}"
        )
    
    # Cancel in queue
    if job.status == JobStatus.QUEUED:
        await queue_service.cancel_job(str(job_id))
    elif job.status == JobStatus.PROCESSING:
        # Send cancel signal to worker
        await queue_service.cancel_running_job(str(job_id), job.worker_id)
    
    # Update job status
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await db.commit()
    
    logger.info(f"Job cancelled: {job_id}")
    
    return {
        "id": str(job_id),
        "status": "cancelled",
        "message": "Job has been cancelled"
    }


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """
    Stream job progress events using Server-Sent Events.
    """
    # Verify job exists and user has access
    job = await db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.api_key != api_key:
        raise HTTPException(status_code=403, detail="Access denied")
    
    async def event_generator():
        """Generate SSE events for job progress."""
        last_progress = -1
        
        while True:
            # Refresh job from database
            await db.refresh(job)
            
            # Send progress update if changed
            if job.progress != last_progress:
                last_progress = job.progress
                
                progress_data = JobProgress(
                    percentage=job.progress,
                    stage=job.stage,
                    fps=job.fps,
                    eta_seconds=job.eta_seconds,
                )
                
                # Add quality metrics if available
                if job.vmaf_score or job.psnr_score:
                    progress_data.quality = {}
                    if job.vmaf_score:
                        progress_data.quality["vmaf"] = job.vmaf_score
                    if job.psnr_score:
                        progress_data.quality["psnr"] = job.psnr_score
                
                yield f"event: progress\ndata: {progress_data.model_dump_json()}\n\n"
            
            # Check if job completed
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                # Send final event
                final_event = {
                    "status": job.status,
                    "message": "Job completed" if job.status == JobStatus.COMPLETED else f"Job {job.status}",
                }
                
                if job.status == JobStatus.COMPLETED:
                    final_event["output_path"] = job.output_path
                    if job.output_metadata:
                        final_event["output_size"] = job.output_metadata.get("size")
                elif job.status == JobStatus.FAILED:
                    final_event["error"] = job.error_message
                
                yield f"event: {job.status.lower()}\ndata: {json.dumps(final_event)}\n\n"
                break
            
            # Wait before next check
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(
    job_id: UUID,
    lines: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
) -> dict:
    """
    Get FFmpeg processing logs for a job.
    """
    # Get job
    job = await db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check ownership
    if job.api_key != api_key:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get logs from worker or storage
    # In production, this would fetch from a log aggregation service
    logs = []
    
    if job.status == JobStatus.PROCESSING and job.worker_id:
        # Get live logs from worker
        logs = await queue_service.get_worker_logs(job.worker_id, str(job_id), lines)
    else:
        # Get stored logs
        # This is a placeholder - implement actual log storage
        logs = [
            f"Job {job_id} - Status: {job.status}",
            f"Created: {job.created_at}",
            f"Started: {job.started_at}",
            f"Completed: {job.completed_at}",
        ]
        
        if job.error_message:
            logs.append(f"Error: {job.error_message}")
    
    return {
        "job_id": str(job_id),
        "lines": len(logs),
        "logs": logs,
    }


# End of file