"""
Pydantic models for GenAI pipeline endpoints.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


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