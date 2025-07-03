"""
GenAI Router Integration

Conditional integration of GenAI routers into the main FastAPI application.
This module provides a function to conditionally mount GenAI routers based on
configuration settings.
"""

from fastapi import FastAPI
import structlog

from .config import genai_settings
from .routers import (
    analyze_router,
    enhance_router,
    optimize_router,
    predict_router,
    pipeline_router,
)

logger = structlog.get_logger()


def mount_genai_routers(app: FastAPI) -> None:
    """
    Conditionally mount GenAI routers to the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    if not genai_settings.ENABLED:
        logger.info("GenAI features disabled, skipping router mounting")
        return
    
    try:
        # Check GPU availability if required
        if genai_settings.GPU_ENABLED and not genai_settings.gpu_available:
            logger.warning(
                "GPU requested but not available, GenAI features may run slowly on CPU"
            )
        
        # Mount GenAI routers under /api/genai/v1
        app.include_router(
            analyze_router,
            prefix="/api/genai/v1/analyze",
            tags=["genai-analysis"],
        )
        
        app.include_router(
            enhance_router,
            prefix="/api/genai/v1/enhance",
            tags=["genai-enhancement"],
        )
        
        app.include_router(
            optimize_router,
            prefix="/api/genai/v1/optimize",
            tags=["genai-optimization"],
        )
        
        app.include_router(
            predict_router,
            prefix="/api/genai/v1/predict",
            tags=["genai-prediction"],
        )
        
        app.include_router(
            pipeline_router,
            prefix="/api/genai/v1/pipeline",
            tags=["genai-pipeline"],
        )
        
        logger.info(
            "GenAI routers mounted successfully",
            gpu_enabled=genai_settings.GPU_ENABLED,
            gpu_available=genai_settings.gpu_available,
            model_path=genai_settings.MODEL_PATH,
        )
        
    except Exception as e:
        logger.error(
            "Failed to mount GenAI routers",
            error=str(e),
        )
        raise


def get_genai_info() -> dict:
    """
    Get information about GenAI configuration and availability.
    
    Returns:
        Dictionary with GenAI status information
    """
    if not genai_settings.ENABLED:
        return {
            "enabled": False,
            "message": "GenAI features are disabled. Set GENAI_ENABLED=true to enable.",
        }
    
    return {
        "enabled": True,
        "gpu_enabled": genai_settings.GPU_ENABLED,
        "gpu_available": genai_settings.gpu_available,
        "gpu_device": genai_settings.GPU_DEVICE,
        "model_path": genai_settings.MODEL_PATH,
        "models_available": genai_settings.models_available,
        "endpoints": {
            "analysis": "/api/genai/v1/analyze/",
            "enhancement": "/api/genai/v1/enhance/",
            "optimization": "/api/genai/v1/optimize/",
            "prediction": "/api/genai/v1/predict/",
            "pipeline": "/api/genai/v1/pipeline/",
        },
        "supported_models": {
            "real_esrgan": ["RealESRGAN_x4plus", "RealESRGAN_x2plus", "RealESRGAN_x8plus"],
            "videomae": genai_settings.VIDEOMAE_MODEL,
            "vmaf": genai_settings.VMAF_MODEL,
            "dover": genai_settings.DOVER_MODEL,
        },
    }