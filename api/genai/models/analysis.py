"""
Pydantic models for GenAI analysis endpoints.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SceneAnalysisRequest(BaseModel):
    """Request model for scene analysis."""
    
    video_path: str = Field(..., description="Path to the video file")
    sensitivity_threshold: float = Field(default=30.0, ge=0.0, le=100.0, description="Scene detection sensitivity")
    analysis_depth: str = Field(default="medium", description="Analysis depth: basic, medium, detailed")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/video.mp4",
                "sensitivity_threshold": 30.0,
                "analysis_depth": "medium"
            }
        }


class Scene(BaseModel):
    """Individual scene information."""
    
    id: int = Field(..., description="Scene ID")
    start_time: float = Field(..., description="Scene start time in seconds")
    end_time: float = Field(..., description="Scene end time in seconds")
    duration: float = Field(..., description="Scene duration in seconds")
    complexity_score: float = Field(..., ge=0.0, le=100.0, description="Scene complexity (0-100)")
    motion_level: str = Field(..., description="Motion level: low, medium, high")
    content_type: str = Field(..., description="Content type: action, dialogue, landscape, etc.")
    optimal_bitrate: Optional[int] = Field(None, description="Suggested bitrate for this scene")
    
    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "start_time": 0.0,
                "end_time": 15.5,
                "duration": 15.5,
                "complexity_score": 75.2,
                "motion_level": "high",
                "content_type": "action",
                "optimal_bitrate": 8000
            }
        }


class SceneAnalysisResponse(BaseModel):
    """Response model for scene analysis."""
    
    video_path: str = Field(..., description="Analyzed video path")
    total_scenes: int = Field(..., description="Total number of scenes detected")
    total_duration: float = Field(..., description="Total video duration in seconds")
    average_complexity: float = Field(..., ge=0.0, le=100.0, description="Average complexity score")
    scenes: List[Scene] = Field(..., description="List of detected scenes")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/video.mp4",
                "total_scenes": 5,
                "total_duration": 120.0,
                "average_complexity": 68.4,
                "scenes": [],
                "processing_time": 2.5
            }
        }


class ComplexityAnalysisRequest(BaseModel):
    """Request model for complexity analysis."""
    
    video_path: str = Field(..., description="Path to the video file")
    sampling_rate: int = Field(default=1, ge=1, le=10, description="Frame sampling rate (every N frames)")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/video.mp4",
                "sampling_rate": 2
            }
        }


class ComplexityAnalysisResponse(BaseModel):
    """Response model for complexity analysis."""
    
    video_path: str = Field(..., description="Analyzed video path")
    overall_complexity: float = Field(..., ge=0.0, le=100.0, description="Overall complexity score")
    motion_metrics: Dict[str, float] = Field(..., description="Motion analysis metrics")
    texture_analysis: Dict[str, float] = Field(..., description="Texture complexity metrics")
    recommended_encoding: Dict[str, Any] = Field(..., description="Recommended encoding settings")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/video.mp4",
                "overall_complexity": 72.5,
                "motion_metrics": {
                    "average_motion": 25.3,
                    "max_motion": 89.1,
                    "motion_variance": 15.7
                },
                "texture_analysis": {
                    "texture_complexity": 45.2,
                    "edge_density": 30.8,
                    "gradient_magnitude": 22.1
                },
                "recommended_encoding": {
                    "crf": 22,
                    "preset": "medium",
                    "bitrate": 6000
                },
                "processing_time": 3.2
            }
        }


class ContentTypeRequest(BaseModel):
    """Request model for content type classification."""
    
    video_path: str = Field(..., description="Path to the video file")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/video.mp4"
            }
        }


class ContentCategory(BaseModel):
    """Content category with confidence."""
    
    category: str = Field(..., description="Content category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    
    class Config:
        schema_extra = {
            "example": {
                "category": "action",
                "confidence": 0.87
            }
        }


class ContentTypeResponse(BaseModel):
    """Response model for content type classification."""
    
    video_path: str = Field(..., description="Analyzed video path")
    primary_category: str = Field(..., description="Primary content category")
    categories: List[ContentCategory] = Field(..., description="All detected categories with confidence")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/video.mp4",
                "primary_category": "action",
                "categories": [
                    {"category": "action", "confidence": 0.87},
                    {"category": "adventure", "confidence": 0.65},
                    {"category": "drama", "confidence": 0.23}
                ],
                "processing_time": 1.8
            }
        }