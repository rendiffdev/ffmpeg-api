"""
GenAI Enhancement Router

Endpoints for AI-powered video quality enhancement.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog

from ..models.enhancement import (
    UpscaleRequest,
    UpscaleResponse,
    DenoiseRequest,
    DenoiseResponse,
    RestoreRequest,
    RestoreResponse,
)
from ..services.quality_enhancer import QualityEnhancerService
from ..config import genai_settings

logger = structlog.get_logger()

router = APIRouter()

# Initialize services
quality_enhancer = QualityEnhancerService()


@router.post(
    "/upscale",
    response_model=UpscaleResponse,
    summary="Upscale video using Real-ESRGAN",
    description="AI-powered video upscaling using Real-ESRGAN models",
)
async def upscale_video(
    request: UpscaleRequest,
    background_tasks: BackgroundTasks,
) -> UpscaleResponse:
    """
    Upscale video using Real-ESRGAN AI models.
    
    This endpoint:
    1. Processes video frames with Real-ESRGAN
    2. Upscales to the specified factor (2x, 4x, 8x)
    3. Reassembles frames into enhanced video using FFmpeg
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting video upscaling",
        video_path=request.video_path,
        scale_factor=request.scale_factor,
        model=request.model_variant,
    )
    
    try:
        # Start upscaling job
        result = await quality_enhancer.upscale_video(
            video_path=request.video_path,
            scale_factor=request.scale_factor,
            model_variant=request.model_variant,
            output_path=request.output_path,
        )
        
        logger.info(
            "Video upscaling job created",
            job_id=result.job_id,
            video_path=request.video_path,
            estimated_time=result.estimated_time,
        )
        
        return result
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found: {request.video_path}"
        )
    except Exception as e:
        logger.error(
            "Video upscaling failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Video upscaling failed: {str(e)}"
        )


@router.post(
    "/denoise",
    response_model=DenoiseResponse,
    summary="Denoise video using Real-ESRGAN",
    description="AI-powered video denoising using Real-ESRGAN models",
)
async def denoise_video(
    request: DenoiseRequest,
    background_tasks: BackgroundTasks,
) -> DenoiseResponse:
    """
    Denoise video using Real-ESRGAN AI models.
    
    This endpoint:
    1. Processes video frames with Real-ESRGAN denoising
    2. Removes noise while preserving details
    3. Reassembles frames into clean video using FFmpeg
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting video denoising",
        video_path=request.video_path,
        noise_level=request.noise_level,
        model=request.model_variant,
    )
    
    try:
        # Start denoising job
        result = await quality_enhancer.denoise_video(
            video_path=request.video_path,
            noise_level=request.noise_level,
            model_variant=request.model_variant,
            output_path=request.output_path,
        )
        
        logger.info(
            "Video denoising job created",
            job_id=result.job_id,
            video_path=request.video_path,
            estimated_time=result.estimated_time,
        )
        
        return result
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found: {request.video_path}"
        )
    except Exception as e:
        logger.error(
            "Video denoising failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Video denoising failed: {str(e)}"
        )


@router.post(
    "/restore",
    response_model=RestoreResponse,
    summary="Restore damaged video using Real-ESRGAN",
    description="AI-powered video restoration for old or damaged videos",
)
async def restore_video(
    request: RestoreRequest,
    background_tasks: BackgroundTasks,
) -> RestoreResponse:
    """
    Restore damaged or old video using Real-ESRGAN AI models.
    
    This endpoint:
    1. Processes video frames with Real-ESRGAN restoration
    2. Fixes artifacts, scratches, and quality issues
    3. Reassembles frames into restored video using FFmpeg
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting video restoration",
        video_path=request.video_path,
        restoration_strength=request.restoration_strength,
        model=request.model_variant,
    )
    
    try:
        # Start restoration job
        result = await quality_enhancer.restore_video(
            video_path=request.video_path,
            restoration_strength=request.restoration_strength,
            model_variant=request.model_variant,
            output_path=request.output_path,
        )
        
        logger.info(
            "Video restoration job created",
            job_id=result.job_id,
            video_path=request.video_path,
            estimated_time=result.estimated_time,
        )
        
        return result
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found: {request.video_path}"
        )
    except Exception as e:
        logger.error(
            "Video restoration failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Video restoration failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="GenAI Enhancement Health Check",
    description="Check the health status of GenAI enhancement services",
)
async def health_check():
    """Health check for GenAI enhancement services."""
    
    if not genai_settings.ENABLED:
        return JSONResponse(
            status_code=503,
            content={
                "status": "disabled",
                "message": "GenAI features are not enabled",
            }
        )
    
    try:
        # Check if models are loaded and services are healthy
        health_status = {
            "status": "healthy",
            "services": {
                "quality_enhancer": await quality_enhancer.health_check(),
            },
            "gpu_available": genai_settings.gpu_available,
            "models_available": genai_settings.models_available,
            "available_models": {
                "esrgan_variants": ["RealESRGAN_x4plus", "RealESRGAN_x2plus", "RealESRGAN_x8plus"],
                "upscale_factors": [2, 4, 8],
            },
        }
        
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error("GenAI enhancement health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            }
        )