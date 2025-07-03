"""
GenAI Prediction Router

Endpoints for AI-powered video quality prediction.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog

from ..models.prediction import (
    QualityPredictionRequest,
    QualityPredictionResponse,
    EncodingQualityRequest,
    EncodingQualityResponse,
    BandwidthQualityRequest,
    BandwidthQualityResponse,
)
from ..services.quality_predictor import QualityPredictorService
from ..config import genai_settings

logger = structlog.get_logger()

router = APIRouter()

# Initialize services
quality_predictor = QualityPredictorService()


@router.post(
    "/quality",
    response_model=QualityPredictionResponse,
    summary="Predict video quality using VMAF + DOVER",
    description="AI-powered video quality assessment using VMAF and DOVER metrics",
)
async def predict_quality(
    request: QualityPredictionRequest,
    background_tasks: BackgroundTasks,
) -> QualityPredictionResponse:
    """
    Predict video quality using VMAF and DOVER metrics.
    
    This endpoint:
    1. Computes VMAF scores (with reference if provided)
    2. Calculates DOVER perceptual quality scores
    3. Provides comprehensive quality assessment
    4. Returns perceptual quality rating
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting quality prediction",
        video_path=request.video_path,
        has_reference=request.reference_path is not None,
    )
    
    try:
        # Perform quality prediction
        result = await quality_predictor.predict_quality(
            video_path=request.video_path,
            reference_path=request.reference_path,
        )
        
        logger.info(
            "Quality prediction completed",
            video_path=request.video_path,
            vmaf_score=result.quality_metrics.vmaf_score,
            dover_score=result.quality_metrics.dover_score,
            perceptual_quality=result.perceptual_quality,
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
            "Quality prediction failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Quality prediction failed: {str(e)}"
        )


@router.post(
    "/encoding-quality",
    response_model=EncodingQualityResponse,
    summary="Predict encoding quality before processing",
    description="Predict video quality before encoding using AI models",
)
async def predict_encoding_quality(
    request: EncodingQualityRequest,
    background_tasks: BackgroundTasks,
) -> EncodingQualityResponse:
    """
    Predict video quality before encoding using AI models.
    
    This endpoint:
    1. Analyzes input video and proposed encoding parameters
    2. Uses ML models to predict quality metrics
    3. Provides confidence scores for predictions
    4. Helps optimize encoding settings before processing
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting encoding quality prediction",
        video_path=request.video_path,
        encoding_parameters=request.encoding_parameters,
    )
    
    try:
        # Perform encoding quality prediction
        result = await quality_predictor.predict_encoding_quality(
            video_path=request.video_path,
            encoding_parameters=request.encoding_parameters,
        )
        
        logger.info(
            "Encoding quality prediction completed",
            video_path=request.video_path,
            predicted_vmaf=result.predicted_vmaf,
            confidence=result.confidence,
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
            "Encoding quality prediction failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Encoding quality prediction failed: {str(e)}"
        )


@router.post(
    "/bandwidth-quality",
    response_model=BandwidthQualityResponse,
    summary="Predict quality at different bandwidths",
    description="Generate quality curve across different bandwidth levels",
)
async def predict_bandwidth_quality(
    request: BandwidthQualityRequest,
    background_tasks: BackgroundTasks,
) -> BandwidthQualityResponse:
    """
    Predict quality at different bandwidth levels.
    
    This endpoint:
    1. Analyzes video content complexity
    2. Predicts quality at various bandwidth levels
    3. Generates quality curve for adaptive streaming
    4. Identifies optimal bandwidth for target quality
    """
    
    if not genai_settings.ENABLED:
        raise HTTPException(
            status_code=503,
            detail="GenAI features are not enabled. Set GENAI_ENABLED=true to use this endpoint."
        )
    
    logger.info(
        "Starting bandwidth-quality prediction",
        video_path=request.video_path,
        bandwidth_levels=request.bandwidth_levels,
    )
    
    try:
        # Perform bandwidth-quality prediction
        result = await quality_predictor.predict_bandwidth_quality(
            video_path=request.video_path,
            bandwidth_levels=request.bandwidth_levels,
        )
        
        logger.info(
            "Bandwidth-quality prediction completed",
            video_path=request.video_path,
            quality_curve_points=len(result.quality_curve),
            optimal_bandwidth=result.optimal_bandwidth,
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
            "Bandwidth-quality prediction failed",
            video_path=request.video_path,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Bandwidth-quality prediction failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="GenAI Prediction Health Check",
    description="Check the health status of GenAI prediction services",
)
async def health_check():
    """Health check for GenAI prediction services."""
    
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
                "quality_predictor": await quality_predictor.health_check(),
            },
            "gpu_available": genai_settings.gpu_available,
            "models_available": genai_settings.models_available,
            "supported_metrics": ["vmaf", "psnr", "ssim", "dover"],
            "vmaf_model": genai_settings.VMAF_MODEL,
            "dover_model": genai_settings.DOVER_MODEL,
        }
        
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error("GenAI prediction health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            }
        )