"""
Jobs endpoint v2 - Using repository pattern and service layer
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.dependencies import get_db, get_current_user
from api.models.job import Job, JobStatus, JobResponse, JobListResponse
from api.models.api_key import ApiKeyUser
from api.services.job_service import JobService
from api.utils.error_handlers import NotFoundError, ValidationError

logger = structlog.get_logger()
router = APIRouter()


@router.get("/v2/jobs", response_model=JobListResponse)
async def list_jobs_v2(
    status: Optional[JobStatus] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> JobListResponse:
    """
    List jobs using service layer (v2 endpoint demonstrating repository pattern).
    """
    user, api_key = user_data
    job_service = JobService()
    
    try:
        # Get jobs using service layer
        if status:
            jobs = await job_service.get_jobs_by_status(db, status, per_page)
        else:
            jobs = await job_service.get_jobs_by_user(db, user.id, per_page)
        
        # Filter to user's jobs if not admin
        if not user.is_admin:
            jobs = [job for job in jobs if job.user_id == user.id]
        
        # Convert to response format
        job_responses = [
            JobResponse(
                id=job.id,
                filename=job.filename,
                status=job.status,
                conversion_type=job.conversion_type,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
                output_url=job.output_url,
                error_message=job.error_message,
                user_id=job.user_id
            ) for job in jobs
        ]
        
        return JobListResponse(
            jobs=job_responses,
            total=len(job_responses),
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        logger.error("Failed to list jobs", error=str(e), user_id=user.id)
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs")


@router.get("/v2/jobs/{job_id}", response_model=JobResponse)
async def get_job_v2(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> JobResponse:
    """
    Get job by ID using service layer (v2 endpoint).
    """
    user, api_key = user_data
    job_service = JobService()
    
    try:
        job = await job_service.get_job(db, job_id)
        
        # Check permissions
        if not user.is_admin and job.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return JobResponse(
            id=job.id,
            filename=job.filename,
            status=job.status,
            conversion_type=job.conversion_type,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            output_url=job.output_url,
            error_message=job.error_message,
            user_id=job.user_id
        )
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        logger.error("Failed to get job", error=str(e), job_id=job_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve job")


@router.get("/v2/jobs/search")
async def search_jobs_v2(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
):
    """
    Search jobs using service layer (v2 endpoint).
    """
    user, api_key = user_data
    job_service = JobService()
    
    try:
        jobs = await job_service.search_jobs(db, query, limit)
        
        # Filter to user's jobs if not admin
        if not user.is_admin:
            jobs = [job for job in jobs if job.user_id == user.id]
        
        job_responses = [
            JobResponse(
                id=job.id,
                filename=job.filename,
                status=job.status,
                conversion_type=job.conversion_type,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
                output_url=job.output_url,
                error_message=job.error_message,
                user_id=job.user_id
            ) for job in jobs
        ]
        
        return {
            "query": query,
            "results": job_responses,
            "count": len(job_responses)
        }
        
    except Exception as e:
        logger.error("Failed to search jobs", error=str(e), query=query)
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/v2/jobs/stats")
async def get_job_stats_v2(
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
):
    """
    Get job statistics using service layer (v2 endpoint).
    """
    user, api_key = user_data
    job_service = JobService()
    
    try:
        # Get stats for user's jobs (or all jobs if admin)
        user_id = None if user.is_admin else user.id
        stats = await job_service.get_job_statistics(db, user_id)
        
        return {
            "user_id": user_id,
            "is_admin": user.is_admin,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error("Failed to get job statistics", error=str(e), user_id=user.id)
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")