"""
Pydantic models for GenAI enhancement endpoints.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class UpscaleRequest(BaseModel):
    """Request model for video upscaling."""
    
    video_path: str = Field(..., description="Path to the input video file")
    scale_factor: int = Field(default=4, ge=2, le=8, description="Upscaling factor (2x, 4x, 8x)")
    model_variant: str = Field(default="RealESRGAN_x4plus", description="Model variant to use")
    output_path: Optional[str] = Field(None, description="Output path (auto-generated if not provided)")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "scale_factor": 4,
                "model_variant": "RealESRGAN_x4plus",
                "output_path": "/path/to/output_4x.mp4"
            }
        }


class UpscaleResponse(BaseModel):
    """Response model for video upscaling."""
    
    job_id: str = Field(..., description="Job ID for tracking progress")
    input_path: str = Field(..., description="Input video path")
    output_path: str = Field(..., description="Output video path")
    scale_factor: int = Field(..., description="Applied upscaling factor")
    model_used: str = Field(..., description="Model variant used")
    estimated_time: float = Field(..., description="Estimated processing time in seconds")
    status: str = Field(default="queued", description="Job status")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "genai_upscale_abc123",
                "input_path": "/path/to/input.mp4",
                "output_path": "/path/to/output_4x.mp4",
                "scale_factor": 4,
                "model_used": "RealESRGAN_x4plus",
                "estimated_time": 120.5,
                "status": "queued"
            }
        }


class DenoiseRequest(BaseModel):
    """Request model for video denoising."""
    
    video_path: str = Field(..., description="Path to the input video file")
    noise_level: str = Field(default="medium", description="Noise level: low, medium, high")
    model_variant: str = Field(default="RealESRGAN_x2plus", description="Model variant for denoising")
    output_path: Optional[str] = Field(None, description="Output path (auto-generated if not provided)")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/noisy_input.mp4",
                "noise_level": "medium",
                "model_variant": "RealESRGAN_x2plus",
                "output_path": "/path/to/denoised_output.mp4"
            }
        }


class DenoiseResponse(BaseModel):
    """Response model for video denoising."""
    
    job_id: str = Field(..., description="Job ID for tracking progress")
    input_path: str = Field(..., description="Input video path")
    output_path: str = Field(..., description="Output video path")
    noise_level: str = Field(..., description="Applied noise level setting")
    model_used: str = Field(..., description="Model variant used")
    estimated_time: float = Field(..., description="Estimated processing time in seconds")
    status: str = Field(default="queued", description="Job status")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "genai_denoise_def456",
                "input_path": "/path/to/noisy_input.mp4",
                "output_path": "/path/to/denoised_output.mp4",
                "noise_level": "medium",
                "model_used": "RealESRGAN_x2plus",
                "estimated_time": 95.2,
                "status": "queued"
            }
        }


class RestoreRequest(BaseModel):
    """Request model for video restoration."""
    
    video_path: str = Field(..., description="Path to the input video file")
    restoration_strength: float = Field(default=0.7, ge=0.0, le=1.0, description="Restoration strength (0.0-1.0)")
    model_variant: str = Field(default="RealESRGAN_x4plus", description="Model variant for restoration")
    output_path: Optional[str] = Field(None, description="Output path (auto-generated if not provided)")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/damaged_input.mp4",
                "restoration_strength": 0.7,
                "model_variant": "RealESRGAN_x4plus",
                "output_path": "/path/to/restored_output.mp4"
            }
        }


class RestoreResponse(BaseModel):
    """Response model for video restoration."""
    
    job_id: str = Field(..., description="Job ID for tracking progress")
    input_path: str = Field(..., description="Input video path")
    output_path: str = Field(..., description="Output video path")
    restoration_strength: float = Field(..., description="Applied restoration strength")
    model_used: str = Field(..., description="Model variant used")
    estimated_time: float = Field(..., description="Estimated processing time in seconds")
    status: str = Field(default="queued", description="Job status")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "genai_restore_ghi789",
                "input_path": "/path/to/damaged_input.mp4",
                "output_path": "/path/to/restored_output.mp4",
                "restoration_strength": 0.7,
                "model_used": "RealESRGAN_x4plus",
                "estimated_time": 150.8,
                "status": "queued"
            }
        }