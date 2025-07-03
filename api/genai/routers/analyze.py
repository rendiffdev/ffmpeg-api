"""
GenAI Analysis Router

Endpoints for video content analysis using AI models.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog

from ..models.analysis import (
    SceneAnalysisRequest,
    SceneAnalysisResponse,
    ComplexityAnalysisRequest,
    ComplexityAnalysisResponse,
    ContentTypeRequest,
    ContentTypeResponse,
)
from ..services.scene_analyzer import SceneAnalyzerService
from ..services.complexity_analyzer import ComplexityAnalyzerService
from ..services.content_classifier import ContentClassifierService
from ..config import genai_settings

logger = structlog.get_logger()

router = APIRouter()

# Initialize services
scene_analyzer = SceneAnalyzerService()
complexity_analyzer = ComplexityAnalyzerService()
content_classifier = ContentClassifierService()


@router.post(
    "/scenes",
    response_model=SceneAnalysisResponse,
    summary="Analyze video scenes using PySceneDetect + VideoMAE",
    description="Detect and analyze video scenes with AI-powered content classification",
)
async def analyze_scenes(
    request: SceneAnalysisRequest,
    background_tasks: BackgroundTasks,
) -> SceneAnalysisResponse:
    """
    Analyze video scenes using PySceneDetect for detection and VideoMAE for content analysis.
    
    This endpoint:
    1. Detects scene boundaries using PySceneDetect
    2. Analyzes each scene with VideoMAE for content classification
    3. Provides complexity scores and optimal encoding suggestions
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting scene analysis",
        video_path=request.video_path,
        threshold=request.sensitivity_threshold,
        depth=request.analysis_depth,
    )
    
    try:
        # Perform scene analysis
        result = await scene_analyzer.analyze_scenes(
            video_path=request.video_path,
            sensitivity_threshold=request.sensitivity_threshold,
            analysis_depth=request.analysis_depth,
        )
        
        logger.info(
            "Scene analysis completed",
            video_path=request.video_path,
            scenes_detected=result.total_scenes,
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
            "Scene analysis failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Scene analysis failed: {str(e)}"
        )


@router.post(
    "/complexity",
    response_model=ComplexityAnalysisResponse,
    summary="Analyze video complexity using VideoMAE",
    description="Analyze video complexity for optimal encoding parameter selection",
)
async def analyze_complexity(
    request: ComplexityAnalysisRequest,
    background_tasks: BackgroundTasks,
) -> ComplexityAnalysisResponse:
    """
    Analyze video complexity using VideoMAE to determine optimal encoding parameters.
    
    This endpoint:
    1. Samples frames from the video
    2. Analyzes motion vectors and texture complexity
    3. Provides recommendations for FFmpeg parameters
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting complexity analysis",
        video_path=request.video_path,
        sampling_rate=request.sampling_rate,
    )
    
    try:
        # Perform complexity analysis
        result = await complexity_analyzer.analyze_complexity(
            video_path=request.video_path,
            sampling_rate=request.sampling_rate,
        )
        
        logger.info(
            "Complexity analysis completed",
            video_path=request.video_path,
            complexity_score=result.overall_complexity,
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
            "Complexity analysis failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Complexity analysis failed: {str(e)}"
        )


@router.post(
    "/content-type",
    response_model=ContentTypeResponse,
    summary="Classify video content type using VideoMAE",
    description="Classify video content (action, dialogue, landscape, etc.) for content-aware encoding",
)
async def classify_content_type(
    request: ContentTypeRequest,
    background_tasks: BackgroundTasks,
) -> ContentTypeResponse:
    """
    Classify video content type using VideoMAE for content-aware encoding.
    
    This endpoint:
    1. Analyzes video frames with VideoMAE
    2. Classifies content into categories (action, dialogue, landscape, etc.)
    3. Provides confidence scores for each category
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting content type classification",
        video_path=request.video_path,
    )
    
    try:
        # Perform content classification
        result = await content_classifier.classify_content(
            video_path=request.video_path,
        )
        
        logger.info(
            "Content classification completed",
            video_path=request.video_path,
            primary_category=result.primary_category,
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
            "Content classification failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Content classification failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="GenAI Analysis Health Check",
    description="Check the health status of GenAI analysis services",
)
async def health_check():
    """Health check for GenAI analysis services."""
    
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
                "scene_analyzer": await scene_analyzer.health_check(),
                "complexity_analyzer": await complexity_analyzer.health_check(),
                "content_classifier": await content_classifier.health_check(),
            },
            "gpu_available": genai_settings.gpu_available,
            "models_available": genai_settings.models_available,
        }
        
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error("GenAI analysis health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            }
        )