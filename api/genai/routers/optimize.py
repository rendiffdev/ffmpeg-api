"""
GenAI Optimization Router

Endpoints for AI-powered FFmpeg parameter optimization.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog

from ..models.optimization import (
    ParameterOptimizationRequest,
    ParameterOptimizationResponse,
    BitrateladderRequest,
    BitrateladderResponse,
    CompressionRequest,
    CompressionResponse,
)
from ..services.encoding_optimizer import EncodingOptimizerService
from ..config import genai_settings

logger = structlog.get_logger()

router = APIRouter()

# Initialize services
encoding_optimizer = EncodingOptimizerService()


@router.post(
    "/parameters",
    response_model=ParameterOptimizationResponse,
    summary="Optimize FFmpeg parameters using AI",
    description="AI-powered optimization of FFmpeg encoding parameters for optimal quality/size balance",
)
async def optimize_parameters(
    request: ParameterOptimizationRequest,
    background_tasks: BackgroundTasks,
) -> ParameterOptimizationResponse:
    """
    Optimize FFmpeg encoding parameters using AI analysis.
    
    This endpoint:
    1. Analyzes video content complexity and characteristics
    2. Uses ML models to predict optimal FFmpeg parameters
    3. Provides quality and file size predictions
    4. Returns optimized parameters for FFmpeg encoding
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting parameter optimization",
        video_path=request.video_path,
        target_quality=request.target_quality,
        optimization_mode=request.optimization_mode,
    )
    
    try:
        # Perform parameter optimization
        result = await encoding_optimizer.optimize_parameters(
            video_path=request.video_path,
            target_quality=request.target_quality,
            target_bitrate=request.target_bitrate,
            scene_data=request.scene_data,
            optimization_mode=request.optimization_mode,
        )
        
        logger.info(
            "Parameter optimization completed",
            video_path=request.video_path,
            predicted_quality=result.predicted_quality,
            confidence=result.confidence_score,
            processing_time=result.processing_time,
        )
        
        return result
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found: {request.video_path}"
        )
    except Exception as e:
        logger.error(
            "Parameter optimization failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Parameter optimization failed: {str(e)}"
        )


@router.post(
    "/bitrate-ladder",
    response_model=BitrateladderResponse,
    summary="Generate AI-optimized bitrate ladder",
    description="Generate per-title optimized bitrate ladder using AI analysis",
)
async def generate_bitrate_ladder(
    request: BitrateladderRequest,
    background_tasks: BackgroundTasks,
) -> BitrateladderResponse:
    """
    Generate AI-optimized bitrate ladder for adaptive streaming.
    
    This endpoint:
    1. Analyzes video content complexity
    2. Generates optimal bitrate steps based on content
    3. Provides quality predictions for each step
    4. Optimizes for adaptive streaming efficiency
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting bitrate ladder generation",
        video_path=request.video_path,
        min_bitrate=request.min_bitrate,
        max_bitrate=request.max_bitrate,
        steps=request.steps,
    )
    
    try:
        # Generate bitrate ladder
        result = await encoding_optimizer.generate_bitrate_ladder(
            video_path=request.video_path,
            min_bitrate=request.min_bitrate,
            max_bitrate=request.max_bitrate,
            steps=request.steps,
            resolutions=request.resolutions,
        )
        
        logger.info(
            "Bitrate ladder generation completed",
            video_path=request.video_path,
            ladder_steps=len(result.bitrate_ladder),
            optimal_step=result.optimal_step,
            processing_time=result.processing_time,
        )
        
        return result
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found: {request.video_path}"
        )
    except Exception as e:
        logger.error(
            "Bitrate ladder generation failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Bitrate ladder generation failed: {str(e)}"
        )


@router.post(
    "/compression",
    response_model=CompressionResponse,
    summary="Optimize compression settings using AI",
    description="AI-powered compression optimization for size/quality balance",
)
async def optimize_compression(
    request: CompressionRequest,
    background_tasks: BackgroundTasks,
) -> CompressionResponse:
    """
    Optimize compression settings using AI analysis.
    
    This endpoint:
    1. Analyzes video content and target constraints
    2. Uses ML models to find optimal compression settings
    3. Balances quality target with size constraints
    4. Provides compression ratio predictions
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting compression optimization",
        video_path=request.video_path,
        quality_target=request.quality_target,
        size_constraint=request.size_constraint,
    )
    
    try:
        # Perform compression optimization
        result = await encoding_optimizer.optimize_compression(
            video_path=request.video_path,
            quality_target=request.quality_target,
            size_constraint=request.size_constraint,
        )
        
        logger.info(
            "Compression optimization completed",
            video_path=request.video_path,
            predicted_quality=result.predicted_quality,
            compression_ratio=result.compression_ratio,
            processing_time=result.processing_time,
        )
        
        return result
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found: {request.video_path}"
        )
    except Exception as e:
        logger.error(
            "Compression optimization failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Compression optimization failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="GenAI Optimization Health Check",
    description="Check the health status of GenAI optimization services",
)
async def health_check():
    """Health check for GenAI optimization services."""
    
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
                "encoding_optimizer": await encoding_optimizer.health_check(),
            },
            "gpu_available": genai_settings.gpu_available,
            "models_available": genai_settings.models_available,
            "optimization_modes": ["quality", "size", "speed"],
            "supported_codecs": ["h264", "h265", "vp9", "av1"],
        }
        
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error("GenAI optimization health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            }
        )