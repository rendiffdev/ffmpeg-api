"""
GenAI Configuration Settings

Separate configuration for GenAI features that can be enabled/disabled
independently from the main API.
"""

from functools import lru_cache
from typing import List, Optional
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class GenAISettings(BaseSettings):
    """GenAI-specific settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="GENAI_",
    )
    
    # GenAI Module Control
    ENABLED: bool = Field(default=False, description="Enable GenAI features")
    
    # Model Storage
    MODEL_PATH: str = Field(default="./models/genai", description="Path to store AI models")
    MODEL_CACHE_SIZE: int = Field(default=3, description="Number of models to keep in memory")
    
    # GPU Configuration
    GPU_ENABLED: bool = Field(default=True, description="Use GPU for inference")
    GPU_DEVICE: str = Field(default="cuda:0", description="GPU device to use")
    GPU_MEMORY_LIMIT: Optional[int] = Field(default=None, description="GPU memory limit in MB")
    
    # Model-specific Settings
    # Real-ESRGAN for quality enhancement
    ESRGAN_MODEL: str = Field(default="RealESRGAN_x4plus", description="Real-ESRGAN model variant")
    ESRGAN_SCALE: int = Field(default=4, description="Default upscaling factor")
    
    # VideoMAE for content analysis
    VIDEOMAE_MODEL: str = Field(default="MCG-NJU/videomae-base", description="VideoMAE model")
    VIDEOMAE_BATCH_SIZE: int = Field(default=8, description="Batch size for video analysis")
    
    # Scene Detection
    SCENE_THRESHOLD: float = Field(default=30.0, description="Scene detection threshold")
    SCENE_MIN_LENGTH: float = Field(default=1.0, description="Minimum scene length in seconds")
    
    # Quality Prediction
    VMAF_MODEL: str = Field(default="vmaf_v0.6.1", description="VMAF model version")
    DOVER_MODEL: str = Field(default="dover_mobile", description="DOVER model variant")
    
    # Performance Settings
    INFERENCE_TIMEOUT: int = Field(default=300, description="Inference timeout in seconds")
    BATCH_PROCESSING: bool = Field(default=True, description="Enable batch processing")
    PARALLEL_WORKERS: int = Field(default=2, description="Number of parallel AI workers")
    
    # Caching
    ENABLE_CACHE: bool = Field(default=True, description="Enable result caching")
    CACHE_TTL: int = Field(default=86400, description="Cache TTL in seconds")
    CACHE_SIZE: int = Field(default=1000, description="Maximum cache entries")
    
    # Monitoring
    ENABLE_METRICS: bool = Field(default=True, description="Enable GenAI metrics")
    LOG_INFERENCE_TIME: bool = Field(default=True, description="Log inference times")
    
    @validator("MODEL_PATH")
    def ensure_model_path_exists(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    
    @validator("GPU_DEVICE")
    def validate_gpu_device(cls, v):
        if v and not v.startswith(("cuda:", "cpu", "mps:")):
            raise ValueError("GPU device must start with 'cuda:', 'cpu', or 'mps:'")
        return v
    
    @property
    def models_available(self) -> bool:
        """Check if GenAI models are available."""
        model_path = Path(self.MODEL_PATH)
        return model_path.exists() and any(model_path.iterdir())
    
    @property
    def gpu_available(self) -> bool:
        """Check if GPU is available for inference."""
        if not self.GPU_ENABLED:
            return False
        
        try:
            import torch
            return torch.cuda.is_available() and self.GPU_DEVICE.startswith("cuda:")
        except ImportError:
            return False


@lru_cache()
def get_genai_settings() -> GenAISettings:
    """Get cached GenAI settings instance."""
    return GenAISettings()


# Global GenAI settings instance
genai_settings = get_genai_settings()