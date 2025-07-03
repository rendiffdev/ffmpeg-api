"""
Pydantic models for GenAI prediction endpoints.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class QualityPredictionRequest(BaseModel):
    """Request model for quality prediction."""
    
    video_path: str = Field(..., description="Path to the input video file")
    reference_path: Optional[str] = Field(None, description="Path to reference video (for full-reference metrics)")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/encoded.mp4",
                "reference_path": "/path/to/original.mp4"
            }
        }


class QualityMetrics(BaseModel):
    """Quality metrics container."""
    
    vmaf_score: float = Field(..., ge=0.0, le=100.0, description="VMAF score")
    psnr: Optional[float] = Field(None, description="PSNR value")
    ssim: Optional[float] = Field(None, description="SSIM value")
    dover_score: float = Field(..., ge=0.0, le=100.0, description="DOVER perceptual score")
    
    class Config:
        schema_extra = {
            "example": {
                "vmaf_score": 92.5,
                "psnr": 45.2,
                "ssim": 0.98,
                "dover_score": 89.3
            }
        }


class QualityPredictionResponse(BaseModel):
    """Response model for quality prediction."""
    
    video_path: str = Field(..., description="Input video path")
    quality_metrics: QualityMetrics = Field(..., description="Quality metrics")
    perceptual_quality: str = Field(..., description="Perceptual quality rating: excellent, good, fair, poor")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/encoded.mp4",
                "quality_metrics": {},
                "perceptual_quality": "excellent",
                "processing_time": 8.5
            }
        }


class EncodingQualityRequest(BaseModel):
    """Request model for encoding quality prediction."""
    
    video_path: str = Field(..., description="Path to the input video file")
    encoding_parameters: Dict[str, Any] = Field(..., description="Proposed encoding parameters")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "encoding_parameters": {
                    "crf": 23,
                    "preset": "medium",
                    "bitrate": 5000
                }
            }
        }


class EncodingQualityResponse(BaseModel):
    """Response model for encoding quality prediction."""
    
    video_path: str = Field(..., description="Input video path")
    predicted_vmaf: float = Field(..., ge=0.0, le=100.0, description="Predicted VMAF score")
    predicted_psnr: float = Field(..., description="Predicted PSNR value")
    predicted_dover: float = Field(..., ge=0.0, le=100.0, description="Predicted DOVER score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "predicted_vmaf": 93.2,
                "predicted_psnr": 44.8,
                "predicted_dover": 87.6,
                "confidence": 0.89,
                "processing_time": 2.3
            }
        }


class BandwidthLevel(BaseModel):
    """Bandwidth level with quality prediction."""
    
    bandwidth_kbps: int = Field(..., description="Bandwidth in kbps")
    predicted_quality: float = Field(..., description="Predicted quality score")
    recommended_resolution: str = Field(..., description="Recommended resolution for this bandwidth")
    
    class Config:
        schema_extra = {
            "example": {
                "bandwidth_kbps": 5000,
                "predicted_quality": 91.5,
                "recommended_resolution": "1920x1080"
            }
        }


class BandwidthQualityRequest(BaseModel):
    """Request model for bandwidth-quality prediction."""
    
    video_path: str = Field(..., description="Path to the input video file")
    bandwidth_levels: List[int] = Field(..., description="Bandwidth levels to test in kbps")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "bandwidth_levels": [1000, 2500, 5000, 7500, 10000]
            }
        }


class BandwidthQualityResponse(BaseModel):
    """Response model for bandwidth-quality prediction."""
    
    video_path: str = Field(..., description="Input video path")
    quality_curve: List[BandwidthLevel] = Field(..., description="Quality curve across bandwidth levels")
    optimal_bandwidth: int = Field(..., description="Optimal bandwidth in kbps")
    processing_time: float = Field(..., description="Analysis processing time in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "video_path": "/path/to/input.mp4",
                "quality_curve": [],
                "optimal_bandwidth": 5000,
                "processing_time": 5.7
            }
        }