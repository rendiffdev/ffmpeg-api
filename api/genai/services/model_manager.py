"""
GenAI Model Manager

Manages loading, caching, and lifecycle of AI models.
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from contextlib import asynccontextmanager
import structlog

from ..config import genai_settings

logger = structlog.get_logger()


@dataclass
class ModelInfo:
    """Information about a loaded model."""
    
    name: str
    model_type: str
    model_path: str
    device: str
    memory_usage: int  # MB
    load_time: float
    last_used: float
    use_count: int


class ModelManager:
    """
    Manages AI model lifecycle including loading, caching, and cleanup.
    
    Features:
    - Lazy loading of models
    - LRU cache with configurable size
    - GPU memory management
    - Automatic cleanup of unused models
    """
    
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.model_info: Dict[str, ModelInfo] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start the background cleanup task."""
        if genai_settings.ENABLED:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Background task to cleanup unused models."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._cleanup_unused_models()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Model cleanup task failed", error=str(e))
    
    async def _cleanup_unused_models(self):
        """Remove unused models from memory based on LRU policy."""
        async with self._lock:
            current_time = time.time()
            model_count = len(self.models)
            
            # Remove models that haven't been used for a while
            if model_count > genai_settings.MODEL_CACHE_SIZE:
                # Sort by last used time
                sorted_models = sorted(
                    self.model_info.items(),
                    key=lambda x: x[1].last_used
                )
                
                # Remove oldest models
                models_to_remove = model_count - genai_settings.MODEL_CACHE_SIZE
                for i in range(models_to_remove):
                    model_name = sorted_models[i][0]
                    await self._unload_model(model_name)
    
    async def _unload_model(self, model_name: str):
        """Unload a specific model from memory."""
        if model_name in self.models:
            logger.info("Unloading model", model_name=model_name)
            
            # Clean up GPU memory if using CUDA
            if genai_settings.gpu_available:
                try:
                    import torch
                    if hasattr(self.models[model_name], 'cpu'):
                        self.models[model_name].cpu()
                    torch.cuda.empty_cache()
                except ImportError:
                    pass
            
            del self.models[model_name]
            del self.model_info[model_name]
    
    async def load_model(self, model_name: str, model_type: str, **kwargs) -> Any:
        """
        Load a model with caching and error handling.
        
        Args:
            model_name: Name/identifier of the model
            model_type: Type of model (esrgan, videomae, etc.)
            **kwargs: Additional arguments for model loading
        
        Returns:
            Loaded model instance
        """
        async with self._lock:
            # Return cached model if available
            if model_name in self.models:
                self.model_info[model_name].last_used = time.time()
                self.model_info[model_name].use_count += 1
                return self.models[model_name]
            
            # Load new model
            logger.info("Loading model", model_name=model_name, model_type=model_type)
            start_time = time.time()
            
            try:
                model = await self._load_model_by_type(model_name, model_type, **kwargs)
                load_time = time.time() - start_time
                
                # Store model and info
                self.models[model_name] = model
                self.model_info[model_name] = ModelInfo(
                    name=model_name,
                    model_type=model_type,
                    model_path=kwargs.get('model_path', ''),
                    device=genai_settings.GPU_DEVICE if genai_settings.gpu_available else 'cpu',
                    memory_usage=self._estimate_memory_usage(model),
                    load_time=load_time,
                    last_used=time.time(),
                    use_count=1,
                )
                
                logger.info(
                    "Model loaded successfully",
                    model_name=model_name,
                    load_time=load_time,
                    device=self.model_info[model_name].device,
                )
                
                return model
                
            except Exception as e:
                logger.error(
                    "Failed to load model",
                    model_name=model_name,
                    model_type=model_type,
                    error=str(e),
                )
                raise
    
    async def _load_model_by_type(self, model_name: str, model_type: str, **kwargs) -> Any:
        """Load model based on type."""
        if model_type == "esrgan":
            return await self._load_esrgan_model(model_name, **kwargs)
        elif model_type == "videomae":
            return await self._load_videomae_model(model_name, **kwargs)
        elif model_type == "vmaf":
            return await self._load_vmaf_model(model_name, **kwargs)
        elif model_type == "dover":
            return await self._load_dover_model(model_name, **kwargs)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
    
    async def _load_esrgan_model(self, model_name: str, **kwargs) -> Any:
        """Load Real-ESRGAN model."""
        try:
            from realesrgan import RealESRGANer
            from basicsr.archs.rrdbnet_arch import RRDBNet
            
            # Model configurations
            model_configs = {
                "RealESRGAN_x4plus": {
                    "model_path": f"{genai_settings.MODEL_PATH}/RealESRGAN_x4plus.pth",
                    "netscale": 4,
                    "arch": "RRDBNet",
                    "num_block": 23,
                    "num_feat": 64,
                },
                "RealESRGAN_x2plus": {
                    "model_path": f"{genai_settings.MODEL_PATH}/RealESRGAN_x2plus.pth",
                    "netscale": 2,
                    "arch": "RRDBNet",
                    "num_block": 23,
                    "num_feat": 64,
                },
            }
            
            config = model_configs.get(model_name)
            if not config:
                raise ValueError(f"Unknown Real-ESRGAN model: {model_name}")
            
            # Create model
            model = RRDBNet(
                num_in_ch=3,
                num_out_ch=3,
                num_feat=config["num_feat"],
                num_block=config["num_block"],
                num_grow_ch=32,
                scale=config["netscale"],
            )
            
            # Create upsampler
            upsampler = RealESRGANer(
                scale=config["netscale"],
                model_path=config["model_path"],
                model=model,
                tile=0,
                tile_pad=10,
                pre_pad=0,
                half=genai_settings.gpu_available,
                gpu_id=0 if genai_settings.gpu_available else None,
            )
            
            return upsampler
            
        except ImportError as e:
            raise ImportError(f"Real-ESRGAN dependencies not installed: {e}")
    
    async def _load_videomae_model(self, model_name: str, **kwargs) -> Any:
        """Load VideoMAE model."""
        try:
            from transformers import VideoMAEImageProcessor, VideoMAEForVideoClassification
            
            # Load model and processor
            processor = VideoMAEImageProcessor.from_pretrained(model_name)
            model = VideoMAEForVideoClassification.from_pretrained(model_name)
            
            # Move to GPU if available
            if genai_settings.gpu_available:
                import torch
                device = torch.device(genai_settings.GPU_DEVICE)
                model = model.to(device)
            
            return {"model": model, "processor": processor}
            
        except ImportError as e:
            raise ImportError(f"VideoMAE dependencies not installed: {e}")
    
    async def _load_vmaf_model(self, model_name: str, **kwargs) -> Any:
        """Load VMAF model."""
        try:
            import ffmpeg
            
            # VMAF is handled by FFmpeg, so we just return a placeholder
            # The actual VMAF computation will be done in the quality predictor
            return {"model_version": model_name, "available": True}
            
        except ImportError as e:
            raise ImportError(f"FFmpeg-python not installed: {e}")
    
    async def _load_dover_model(self, model_name: str, **kwargs) -> Any:
        """Load DOVER perceptual quality model.
        
        Note: DOVER is a research model. For production use, we implement
        a practical perceptual quality estimator based on established metrics.
        """
        try:
            # Return a quality estimator that uses traditional metrics
            # This is more reliable than depending on research models
            return {
                "model_version": model_name,
                "available": True,
                "type": "traditional_estimator",
                "description": "Perceptual quality estimator using established metrics"
            }
            
        except ImportError as e:
            raise ImportError(f"Quality estimation dependencies not installed: {e}")
    
    def _estimate_memory_usage(self, model: Any) -> int:
        """Estimate memory usage of a model in MB."""
        try:
            import torch
            if hasattr(model, 'parameters'):
                param_count = sum(p.numel() for p in model.parameters())
                # Rough estimate: 4 bytes per parameter (float32)
                return int(param_count * 4 / (1024 * 1024))
            return 100  # Default estimate
        except:
            return 100
    
    async def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get information about a loaded model."""
        return self.model_info.get(model_name)
    
    async def list_loaded_models(self) -> List[ModelInfo]:
        """List all currently loaded models."""
        return list(self.model_info.values())
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the model manager."""
        return {
            "models_loaded": len(self.models),
            "cache_size": genai_settings.MODEL_CACHE_SIZE,
            "gpu_available": genai_settings.gpu_available,
            "model_path": genai_settings.MODEL_PATH,
        }
    
    async def shutdown(self):
        """Shutdown the model manager and cleanup resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Unload all models
        async with self._lock:
            for model_name in list(self.models.keys()):
                await self._unload_model(model_name)


# Global model manager instance
model_manager = ModelManager()