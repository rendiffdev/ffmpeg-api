"""
Convert endpoint - Main API for media conversion
"""
from typing import Dict, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.config import settings
from api.dependencies import get_db, require_api_key
from api.models.job import Job, JobStatus, ConvertRequest, JobCreateResponse, JobResponse
from api.services.queue import QueueService
from api.services.storage import StorageService
from api.utils.validators import validate_input_path, validate_output_path, validate_operations

logger = structlog.get_logger()
router = APIRouter()

queue_service = QueueService()
storage_service = StorageService()


@router.post("/convert", response_model=JobCreateResponse)
async def convert_media(
    request: ConvertRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
) -> JobCreateResponse:
    """
    Create a new media conversion job.
    
    This endpoint accepts various input formats and converts them based on the
    specified output parameters and operations.
    """
    try:
        # Validate request size and complexity early
        if len(request.operations) > 20:
            raise HTTPException(status_code=400, detail="Too many operations (max 20)")
        
        # Check webhook URL for SSRF if provided
        if request.webhook_url:
            from urllib.parse import urlparse
            parsed = urlparse(request.webhook_url)
            # Block internal networks
            if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0'] or \
               parsed.hostname and (parsed.hostname.startswith('192.168.') or 
                                   parsed.hostname.startswith('10.') or 
                                   parsed.hostname.startswith('172.')):
                raise HTTPException(status_code=400, detail="Invalid webhook URL")
        # Parse input/output paths
        input_path = request.input if isinstance(request.input, str) else request.input.get("path")
        output_path = request.output if isinstance(request.output, str) else request.output.get("path")
        
        # Validate paths
        input_backend, input_validated = await validate_input_path(input_path, storage_service)
        output_backend, output_validated = await validate_output_path(output_path, storage_service)
        
        # Validate operations
        operations_validated = validate_operations(request.operations)
        
        # Check concurrent job limit for this API key
        from sqlalchemy import select, func
        from api.models.job import JobStatus
        
        # Count active jobs for this API key
        active_jobs_stmt = select(func.count(Job.id)).where(
            Job.api_key == api_key,
            Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING])
        )
        result = await db.execute(active_jobs_stmt)
        active_job_count = result.scalar() or 0
        
        # Get API key model to check limits
        from api.services.api_key import APIKeyService
        api_key_model = await APIKeyService.get_api_key_by_key(db, api_key)
        max_concurrent = api_key_model.max_concurrent_jobs if api_key_model else 5  # Default limit
        
        if active_job_count >= max_concurrent:
            raise HTTPException(
                status_code=429, 
                detail=f"Concurrent job limit exceeded ({active_job_count}/{max_concurrent})"
            )
        
        # Create job record with database-managed UUID to prevent race conditions
        job = Job(
            id=uuid4(),  # Still generate UUID but let DB handle uniqueness
            status=JobStatus.QUEUED,
            priority=request.priority,
            input_path=input_validated,
            output_path=output_validated,
            options=request.options,
            operations=operations_validated,
            api_key=api_key,
            webhook_url=request.webhook_url,
            webhook_events=request.webhook_events,
        )
        
        # Add to database with flush to get the ID before commit
        db.add(job)
        await db.flush()  # This assigns the ID without committing
        
        # Now we have a guaranteed unique job ID, queue it
        job_id_str = str(job.id)
        
        # Queue the job (do this before commit in case queuing fails)
        try:
            await queue_service.enqueue_job(
                job_id=job_id_str,
                priority=request.priority,
            )
        except Exception as e:
            # If queuing fails, rollback the job creation
            await db.rollback()
            raise HTTPException(status_code=503, detail="Failed to queue job")
        
        # Now commit the transaction
        await db.commit()
        await db.refresh(job)
        
        # Log job creation
        logger.info(
            "Job created",
            job_id=str(job.id),
            input_path=input_path,
            output_path=output_path,
            operations=len(operations_validated),
        )
        
        # Prepare response
        job_response = JobResponse(
            id=job.id,
            status=job.status,
            priority=job.priority,
            progress=0.0,
            stage="queued",
            created_at=job.created_at,
            links={
                "self": f"/api/v1/jobs/{job.id}",
                "events": f"/api/v1/jobs/{job.id}/events",
                "logs": f"/api/v1/jobs/{job.id}/logs",
                "cancel": f"/api/v1/jobs/{job.id}",
            },
        )
        
        # Estimate cost/time (simplified for now)
        estimated_cost = {
            "processing_time": estimate_processing_time(request),
            "credits": 0,  # For self-hosted, no credits
        }
        
        return JobCreateResponse(
            job=job_response,
            estimated_cost=estimated_cost,
            warnings=[],
        )
        
    except ValueError as e:
        logger.error("Validation error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create job", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create job")


@router.post("/analyze", response_model=JobCreateResponse)
async def analyze_media(
    request: Dict[str, Any],
    fastapi_request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
) -> JobCreateResponse:
    """
    Analyze media file for quality metrics.
    
    This endpoint runs VMAF, PSNR, and SSIM analysis on the input media.
    """
    # Apply endpoint-specific rate limiting
    from api.utils.rate_limit import endpoint_rate_limiter
    endpoint_rate_limiter.check_rate_limit(fastapi_request, "analyze", api_key)
    # Convert to regular conversion job with analysis flag
    convert_request = ConvertRequest(
        input=request["input"],
        output=request.get("output", request["input"]),  # Output same as input for analysis
        operations=[],
        options={
            "analyze_only": True,
            "metrics": request.get("metrics", ["vmaf", "psnr", "ssim"]),
            "reference": request.get("reference"),
        },
    )
    
    return await convert_media(convert_request, BackgroundTasks(), db, api_key)


@router.post("/stream", response_model=JobCreateResponse)
async def create_stream(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
) -> JobCreateResponse:
    """
    Create adaptive streaming formats (HLS/DASH).
    
    This endpoint generates streaming-ready output from input media.
    """
    # Convert to conversion job with streaming operations
    stream_type = request.get("type", "hls")
    variants = request.get("variants", [
        {"resolution": "1080p", "bitrate": "5M"},
        {"resolution": "720p", "bitrate": "2.5M"},
        {"resolution": "480p", "bitrate": "1M"},
    ])
    
    convert_request = ConvertRequest(
        input=request["input"],
        output=request["output"],
        operations=[
            {
                "type": "stream",
                "format": stream_type,
                "variants": variants,
                "segment_duration": request.get("segment_duration", 6),
            }
        ],
        options=request.get("options", {}),
    )
    
    return await convert_media(convert_request, BackgroundTasks(), db, api_key)


@router.post("/estimate")
async def estimate_job(
    request: ConvertRequest,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
    """
    Estimate processing time and resources for a conversion job.
    
    This endpoint helps predict job duration without actually creating the job.
    """
    try:
        # Basic estimation logic
        estimated_seconds = estimate_processing_time(request)
        
        # Estimate output size
        estimated_size = estimate_output_size(request)
        
        # Resource requirements
        resources = {
            "cpu_cores": 4,
            "memory_gb": 8,
            "gpu_required": request.options.get("hardware_acceleration") == "gpu",
        }
        
        return {
            "estimated": {
                "duration_seconds": estimated_seconds,
                "output_size_bytes": estimated_size,
            },
            "resources": resources,
            "factors": {
                "complexity": calculate_complexity(request),
                "operations": len(request.operations),
            },
        }
        
    except Exception as e:
        logger.error("Estimation failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to estimate job")


def estimate_processing_time(request: ConvertRequest) -> int:
    """Estimate processing time in seconds."""
    # Simple estimation based on operations
    base_time = 60  # Base time for simple conversion
    
    # Add time for each operation
    for op in request.operations:
        if op["type"] == "stream":
            base_time *= 3  # Streaming takes longer
        elif op["type"] == "analyze":
            base_time *= 2  # Analysis is slower
        else:
            base_time += 30  # Other operations
    
    # Adjust for quality settings
    if isinstance(request.output, dict):
        quality = request.output.get("video", {}).get("quality", "medium")
        if quality == "high":
            base_time *= 2
        elif quality == "ultra":
            base_time *= 4
    
    return base_time


def estimate_output_size(request: ConvertRequest) -> int:
    """Estimate output file size in bytes."""
    # Very rough estimation
    # In production, this would be based on bitrate, duration, etc.
    return 100 * 1024 * 1024  # 100MB default


def calculate_complexity(request: ConvertRequest) -> str:
    """Calculate job complexity."""
    operations_count = len(request.operations)
    
    if operations_count == 0:
        return "simple"
    elif operations_count <= 2:
        return "moderate"
    else:
        return "complex"