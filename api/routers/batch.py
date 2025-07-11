"""
Batch processing endpoints
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.dependencies import get_db, get_current_user
from api.models.batch import (
    BatchJobCreate, BatchJobResponse, BatchJobUpdate, 
    BatchJobListResponse, BatchJobStats, BatchJobProgress, BatchStatus
)
from api.models.api_key import ApiKeyUser
from api.services.batch_service import BatchService
from api.utils.error_handlers import NotFoundError, ValidationError

logger = structlog.get_logger()
router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/jobs", response_model=BatchJobResponse, status_code=201)
async def create_batch_job(
    batch_request: BatchJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> BatchJobResponse:
    """
    Create a new batch job for processing multiple files.
    """
    user, api_key = user_data
    batch_service = BatchService()
    
    try:
        # Create the batch job
        batch_job = await batch_service.create_batch_job(
            db, 
            batch_request, 
            user_id=user.id,
            api_key_id=user.api_key_id
        )
        
        # Start processing in background
        background_tasks.add_task(
            batch_service.start_batch_processing,
            str(batch_job.id)
        )
        
        logger.info(
            "Batch job created",
            batch_id=str(batch_job.id),
            user_id=user.id,
            total_files=len(batch_request.files)
        )
        
        return BatchJobResponse.from_orm(batch_job)
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create batch job", error=str(e), user_id=user.id)
        raise HTTPException(status_code=500, detail="Failed to create batch job")


@router.get("/jobs", response_model=BatchJobListResponse)
async def list_batch_jobs(
    status: Optional[BatchStatus] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> BatchJobListResponse:
    """
    List batch jobs with optional filtering.
    """
    user, api_key = user_data
    batch_service = BatchService()
    
    try:
        batches, total = await batch_service.list_batch_jobs(
            db,
            user_id=user.id if not user.is_admin else None,
            status=status,
            page=page,
            per_page=per_page
        )
        
        batch_responses = [BatchJobResponse.from_orm(batch) for batch in batches]
        
        return BatchJobListResponse(
            batches=batch_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page
        )
        
    except Exception as e:
        logger.error("Failed to list batch jobs", error=str(e), user_id=user.id)
        raise HTTPException(status_code=500, detail="Failed to retrieve batch jobs")


@router.get("/jobs/{batch_id}", response_model=BatchJobResponse)
async def get_batch_job(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> BatchJobResponse:
    """
    Get batch job details by ID.
    """
    user, api_key = user_data
    batch_service = BatchService()
    
    try:
        batch_job = await batch_service.get_batch_job(db, batch_id)
        
        # Check permissions
        if not user.is_admin and batch_job.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return BatchJobResponse.from_orm(batch_job)
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Batch job not found")
    except Exception as e:
        logger.error("Failed to get batch job", error=str(e), batch_id=batch_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve batch job")


@router.put("/jobs/{batch_id}", response_model=BatchJobResponse)
async def update_batch_job(
    batch_id: str,
    update_request: BatchJobUpdate,
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> BatchJobResponse:
    """
    Update batch job settings.
    """
    user, api_key = user_data
    batch_service = BatchService()
    
    try:
        # Get existing batch job
        batch_job = await batch_service.get_batch_job(db, batch_id)
        
        # Check permissions
        if not user.is_admin and batch_job.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update the batch job
        updated_batch = await batch_service.update_batch_job(
            db, 
            batch_id, 
            update_request
        )
        
        logger.info(
            "Batch job updated",
            batch_id=batch_id,
            user_id=user.id
        )
        
        return BatchJobResponse.from_orm(updated_batch)
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Batch job not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to update batch job", error=str(e), batch_id=batch_id)
        raise HTTPException(status_code=500, detail="Failed to update batch job")


@router.delete("/jobs/{batch_id}")
async def cancel_batch_job(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
):
    """
    Cancel a batch job.
    """
    user, api_key = user_data
    batch_service = BatchService()
    
    try:
        # Get existing batch job
        batch_job = await batch_service.get_batch_job(db, batch_id)
        
        # Check permissions
        if not user.is_admin and batch_job.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Cancel the batch job
        await batch_service.cancel_batch_job(db, batch_id)
        
        logger.info(
            "Batch job cancelled",
            batch_id=batch_id,
            user_id=user.id
        )
        
        return {"message": "Batch job cancelled successfully"}
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Batch job not found")
    except Exception as e:
        logger.error("Failed to cancel batch job", error=str(e), batch_id=batch_id)
        raise HTTPException(status_code=500, detail="Failed to cancel batch job")


@router.get("/jobs/{batch_id}/progress", response_model=BatchJobProgress)
async def get_batch_progress(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> BatchJobProgress:
    """
    Get real-time progress of a batch job.
    """
    user, api_key = user_data
    batch_service = BatchService()
    
    try:
        progress = await batch_service.get_batch_progress(db, batch_id, user.id)
        return progress
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Batch job not found")
    except Exception as e:
        logger.error("Failed to get batch progress", error=str(e), batch_id=batch_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve progress")


@router.get("/stats", response_model=BatchJobStats)
async def get_batch_stats(
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
) -> BatchJobStats:
    """
    Get batch processing statistics.
    """
    user, api_key = user_data
    batch_service = BatchService()
    
    try:
        stats = await batch_service.get_batch_statistics(
            db,
            user_id=user.id if not user.is_admin else None
        )
        return stats
        
    except Exception as e:
        logger.error("Failed to get batch stats", error=str(e), user_id=user.id)
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.post("/jobs/{batch_id}/retry")
async def retry_failed_jobs(
    batch_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_data: tuple[ApiKeyUser, str] = Depends(get_current_user),
):
    """
    Retry failed jobs in a batch.
    """
    user, api_key = user_data
    batch_service = BatchService()
    
    try:
        # Get existing batch job
        batch_job = await batch_service.get_batch_job(db, batch_id)
        
        # Check permissions
        if not user.is_admin and batch_job.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Retry failed jobs in background
        background_tasks.add_task(
            batch_service.retry_failed_jobs,
            db,
            batch_id
        )
        
        logger.info(
            "Retry initiated for failed jobs",
            batch_id=batch_id,
            user_id=user.id
        )
        
        return {"message": "Retry initiated for failed jobs"}
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Batch job not found")
    except Exception as e:
        logger.error("Failed to retry batch jobs", error=str(e), batch_id=batch_id)
        raise HTTPException(status_code=500, detail="Failed to retry jobs")