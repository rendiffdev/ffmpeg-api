"""
GenAI Pipeline Router

Endpoints for combined AI-powered video processing pipelines.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from ..config import genai_settings
from ..services.pipeline_service import PipelineService

logger = structlog.get_logger()

router = APIRouter()

# Initialize services
pipeline_service = PipelineService()


class SmartEncodeRequest(BaseModel):
    """Request model for smart encoding pipeline."""
    
    video_path: str = Field(..., description="Path to the input video file")
    quality_preset: str = Field(default="high", description="Quality preset: low, medium, high, ultra")
    optimization_level: int = Field(default=2, ge=1, le=3, description="Optimization level (1-3)")
    output_path: Optional[str] = Field(None, description="Output path (auto-generated if not provided)")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "quality_preset": "high",
                "optimization_level": 2,
                "output_path": "/path/to/output.mp4"
            }
        }


class SmartEncodeResponse(BaseModel):
    """Response model for smart encoding pipeline."""
    
    job_id: str = Field(..., description="Job ID for tracking progress")
    input_path: str = Field(..., description="Input video path")
    output_path: str = Field(..., description="Output video path")
    quality_preset: str = Field(..., description="Applied quality preset")
    optimization_level: int = Field(..., description="Applied optimization level")
    estimated_time: float = Field(..., description="Estimated processing time in seconds")
    pipeline_steps: List[str] = Field(..., description="List of pipeline steps to be executed")
    status: str = Field(default="queued", description="Job status")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "genai_smart_encode_abc123",
                "input_path": "/path/to/input.mp4",
                "output_path": "/path/to/output.mp4",
                "quality_preset": "high",
                "optimization_level": 2,
                "estimated_time": 180.5,
                "pipeline_steps": ["analyze_content", "optimize_parameters", "encode_video", "validate_quality"],
                "status": "queued"
            }
        }


class AdaptiveStreamingRequest(BaseModel):
    """Request model for adaptive streaming pipeline."""
    
    video_path: str = Field(..., description="Path to the input video file")
    streaming_profiles: List[Dict[str, Any]] = Field(..., description="List of streaming profiles")
    output_dir: Optional[str] = Field(None, description="Output directory (auto-generated if not provided)")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "streaming_profiles": [
                    {"resolution": "1920x1080", "bitrate": 5000, "profile": "high"},
                    {"resolution": "1280x720", "bitrate": 2500, "profile": "main"},
                    {"resolution": "854x480", "bitrate": 1000, "profile": "baseline"}
                ],
                "output_dir": "/path/to/output/segments"
            }
        }


class AdaptiveStreamingResponse(BaseModel):
    """Response model for adaptive streaming pipeline."""
    
    job_id: str = Field(..., description="Job ID for tracking progress")
    input_path: str = Field(..., description="Input video path")
    manifest_path: str = Field(..., description="HLS/DASH manifest path")
    segment_paths: List[str] = Field(..., description="List of segment file paths")
    streaming_profiles: List[Dict[str, Any]] = Field(..., description="Applied streaming profiles")
    estimated_time: float = Field(..., description="Estimated processing time in seconds")
    status: str = Field(default="queued", description="Job status")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "genai_adaptive_streaming_def456",
                "input_path": "/path/to/input.mp4",
                "manifest_path": "/path/to/output/playlist.m3u8",
                "segment_paths": ["/path/to/output/segments/"],
                "streaming_profiles": [],
                "estimated_time": 240.8,
                "status": "queued"
            }
        }


@router.post(
    "/smart-encode",
    response_model=SmartEncodeResponse,
    summary="AI-powered smart encoding pipeline",
    description="Complete AI-enhanced encoding pipeline with analysis, optimization, and validation",
)
async def smart_encode(
    request: SmartEncodeRequest,
    background_tasks: BackgroundTasks,
) -> SmartEncodeResponse:
    """
    Complete AI-powered smart encoding pipeline.
    
    This pipeline:
    1. Analyzes video content using AI models
    2. Optimizes FFmpeg parameters based on content
    3. Performs encoding with optimized settings
    4. Validates output quality using AI metrics
    5. Provides comprehensive quality report
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting smart encoding pipeline",
        video_path=request.video_path,
        quality_preset=request.quality_preset,
        optimization_level=request.optimization_level,
    )
    
    try:
        # Start smart encoding pipeline
        result = await pipeline_service.smart_encode(
            video_path=request.video_path,
            quality_preset=request.quality_preset,
            optimization_level=request.optimization_level,
            output_path=request.output_path,
        )
        
        logger.info(
            "Smart encoding pipeline job created",
            job_id=result.job_id,
            video_path=request.video_path,
            pipeline_steps=len(result.pipeline_steps),
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
            "Smart encoding pipeline failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Smart encoding pipeline failed: {str(e)}"
        )


@router.post(
    "/adaptive-streaming",
    response_model=AdaptiveStreamingResponse,
    summary="AI-optimized adaptive streaming pipeline",
    description="Generate AI-optimized adaptive streaming package with per-title optimization",
)
async def adaptive_streaming(
    request: AdaptiveStreamingRequest,
    background_tasks: BackgroundTasks,
) -> AdaptiveStreamingResponse:
    """
    Generate AI-optimized adaptive streaming package.
    
    This pipeline:
    1. Analyzes video content for complexity
    2. Optimizes bitrate ladder using AI
    3. Generates multiple quality variants
    4. Creates HLS/DASH manifests
    5. Optimizes segment boundaries using scene detection
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting adaptive streaming pipeline",
        video_path=request.video_path,
        profiles_count=len(request.streaming_profiles),
    )
    
    try:
        # Start adaptive streaming pipeline
        result = await pipeline_service.adaptive_streaming(
            video_path=request.video_path,
            streaming_profiles=request.streaming_profiles,
            output_dir=request.output_dir,
        )
        
        logger.info(
            "Adaptive streaming pipeline job created",
            job_id=result.job_id,
            video_path=request.video_path,
            profiles_count=len(result.streaming_profiles),
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
            "Adaptive streaming pipeline failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Adaptive streaming pipeline failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="GenAI Pipeline Health Check",
    description="Check the health status of GenAI pipeline services",
)
async def health_check():
    """Health check for GenAI pipeline services."""
    
    if not genai_settings.ENABLED:
        return JSONResponse(
            status_code=503,
            content={
                "status": "disabled",
                "message": "GenAI features are not enabled",
            }
        )
    
    try:
        # Check if all pipeline services are healthy
        health_status = {
            "status": "healthy",
            "services": {
                "pipeline_service": await pipeline_service.health_check(),
            },
            "gpu_available": genai_settings.gpu_available,
            "models_available": genai_settings.models_available,
            "available_pipelines": ["smart_encode", "adaptive_streaming"],
            "quality_presets": ["low", "medium", "high", "ultra"],
            "optimization_levels": [1, 2, 3],
        }
        
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error("GenAI pipeline health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            }
        )