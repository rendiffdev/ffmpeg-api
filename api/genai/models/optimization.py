"""
Pydantic models for GenAI optimization endpoints.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ParameterOptimizationRequest(BaseModel):
    """Request model for FFmpeg parameter optimization."""
    
    video_path: str = Field(..., description="Path to the input video file")
    target_quality: float = Field(default=95.0, ge=0.0, le=100.0, description="Target quality score (0-100)")
    target_bitrate: Optional[int] = Field(None, description="Target bitrate in kbps (optional)")
    scene_data: Optional[Dict[str, Any]] = Field(None, description="Pre-analyzed scene data")
    optimization_mode: str = Field(default="quality", description="Optimization mode: quality, size, speed")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "target_quality": 95.0,
                "target_bitrate": 5000,
                "scene_data": None,
                "optimization_mode": "quality"
            }
        }


class FFmpegParameters(BaseModel):
    """Optimized FFmpeg parameters."""
    
    crf: int = Field(..., ge=0, le=51, description="Constant Rate Factor")
    preset: str = Field(..., description="Encoding preset")
    bitrate: Optional[int] = Field(None, description="Target bitrate in kbps")
    maxrate: Optional[int] = Field(None, description="Maximum bitrate in kbps")
    bufsize: Optional[int] = Field(None, description="Buffer size")
    profile: str = Field(..., description="H.264/H.265 profile")
    level: Optional[str] = Field(None, description="H.264/H.265 level")
    keyint: Optional[int] = Field(None, description="Keyframe interval")
    bframes: Optional[int] = Field(None, description="Number of B-frames")
    refs: Optional[int] = Field(None, description="Reference frames")
    
    class Config:
        schema_extra = {
            "example": {
                "crf": 22,
                "preset": "medium",
                "bitrate": 5000,
                "maxrate": 7500,
                "bufsize": 10000,
                "profile": "high",
                "level": "4.1",
                "keyint": 120,
                "bframes": 3,
                "refs": 4
            }
        }


class ParameterOptimizationResponse(BaseModel):
    """Response model for FFmpeg parameter optimization."""
    
    video_path: str = Field(..., description="Input video path")
    optimal_parameters: FFmpegParameters = Field(..., description="Optimized FFmpeg parameters")
    predicted_quality: float = Field(..., description="Predicted quality score")
    predicted_file_size: int = Field(..., description="Predicted file size in bytes")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Optimization confidence")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "optimal_parameters": {},
                "predicted_quality": 94.8,
                "predicted_file_size": 104857600,
                "confidence_score": 0.92,
                "processing_time": 4.5
            }
        }


class BitrateladderRequest(BaseModel):
    """Request model for generating bitrate ladder."""
    
    video_path: str = Field(..., description="Path to the input video file")
    min_bitrate: int = Field(default=500, ge=100, description="Minimum bitrate in kbps")
    max_bitrate: int = Field(default=10000, ge=1000, description="Maximum bitrate in kbps")
    steps: int = Field(default=5, ge=3, le=10, description="Number of bitrate steps")
    resolutions: Optional[List[str]] = Field(None, description="Target resolutions (e.g., ['1920x1080', '1280x720'])")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "min_bitrate": 500,
                "max_bitrate": 8000,
                "steps": 5,
                "resolutions": ["1920x1080", "1280x720", "854x480"]
            }
        }


class BitrateStep(BaseModel):
    """Individual bitrate ladder step."""
    
    resolution: str = Field(..., description="Video resolution")
    bitrate: int = Field(..., description="Bitrate in kbps")
    predicted_quality: float = Field(..., description="Predicted quality score")
    estimated_file_size: int = Field(..., description="Estimated file size in bytes")
    
    class Config:
        schema_extra = {
            "example": {
                "resolution": "1920x1080",
                "bitrate": 5000,
                "predicted_quality": 92.5,
                "estimated_file_size": 62914560
            }
        }


class BitrateladderResponse(BaseModel):
    """Response model for bitrate ladder generation."""
    
    video_path: str = Field(..., description="Input video path")
    bitrate_ladder: List[BitrateStep] = Field(..., description="Generated bitrate ladder")
    optimal_step: int = Field(..., description="Index of recommended optimal step")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "bitrate_ladder": [],
                "optimal_step": 2,
                "processing_time": 6.2
            }
        }


class CompressionRequest(BaseModel):
    """Request model for compression optimization."""
    
    video_path: str = Field(..., description="Path to the input video file")
    quality_target: float = Field(default=90.0, ge=0.0, le=100.0, description="Target quality score")
    size_constraint: Optional[int] = Field(None, description="Maximum file size in bytes")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "quality_target": 90.0,
                "size_constraint": 104857600
            }
        }


class CompressionResponse(BaseModel):
    """Response model for compression optimization."""
    
    video_path: str = Field(..., description="Input video path")
    compression_settings: FFmpegParameters = Field(..., description="Optimal compression settings")
    predicted_file_size: int = Field(..., description="Predicted file size in bytes")
    predicted_quality: float = Field(..., description="Predicted quality score")
    compression_ratio: float = Field(..., description="Predicted compression ratio")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "compression_settings": {},
                "predicted_file_size": 83886080,
                "predicted_quality": 89.7,
                "compression_ratio": 0.25,
                "processing_time": 3.8
            }
        }