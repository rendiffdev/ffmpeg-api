"""
GenAI Routers Package

FastAPI routers for GenAI endpoints.
"""

from .analyze import router as analyze_router
from .enhance import router as enhance_router
from .optimize import router as optimize_router
from .predict import router as predict_router
from .pipeline import router as pipeline_router

__all__ = [
    "analyze_router",
    "enhance_router", 
    "optimize_router",
    "predict_router",
    "pipeline_router",
]