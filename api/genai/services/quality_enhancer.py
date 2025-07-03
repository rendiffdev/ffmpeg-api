"""
Quality Enhancer Service

Enhances video quality using Real-ESRGAN and other AI models.
"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

from ..models.enhancement import UpscaleResponse, DenoiseResponse, RestoreResponse
from ..config import genai_settings
from .model_manager import model_manager

logger = structlog.get_logger()


class QualityEnhancerService:
    """
    Service for AI-powered video quality enhancement.
    
    Features:
    - Video upscaling using Real-ESRGAN
    - Noise reduction and restoration
    - Frame-by-frame processing with FFmpeg reassembly
    - Progress tracking and job management
    """
    
    def __init__(self):
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
    
    async def upscale_video(
        self,
        video_path: str,
        scale_factor: int = 4,
        model_variant: str = "RealESRGAN_x4plus",
        output_path: Optional[str] = None,
    ) -> UpscaleResponse:
        """
        Upscale video using Real-ESRGAN.
        
        Args:
            video_path: Path to input video
            scale_factor: Upscaling factor (2, 4, 8)
            model_variant: Real-ESRGAN model variant
            output_path: Output path (auto-generated if not provided)
        
        Returns:
            Upscale job response
        """
        # Validate input
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Generate job ID and output path
        job_id = f"genai_upscale_{uuid.uuid4().hex[:8]}"
        if not output_path:
            input_path = Path(video_path)
            output_path = str(input_path.parent / f"{input_path.stem}_upscaled_{scale_factor}x{input_path.suffix}")
        
        # Estimate processing time
        estimated_time = await self._estimate_processing_time(video_path, "upscale", scale_factor)
        
        # Create job record
        job_data = {
            "job_id": job_id,
            "input_path": video_path,
            "output_path": output_path,
            "operation": "upscale",
            "scale_factor": scale_factor,
            "model_variant": model_variant,
            "status": "queued",
            "progress": 0.0,
            "created_at": time.time(),
            "estimated_time": estimated_time,
        }
        
        self.active_jobs[job_id] = job_data
        
        # Start processing (async)
        asyncio.create_task(self._process_upscale_job(job_data))
        
        return UpscaleResponse(
            job_id=job_id,
            input_path=video_path,
            output_path=output_path,
            scale_factor=scale_factor,
            model_used=model_variant,
            estimated_time=estimated_time,
            status="queued",
        )
    
    async def denoise_video(
        self,
        video_path: str,
        noise_level: str = "medium",
        model_variant: str = "RealESRGAN_x2plus",
        output_path: Optional[str] = None,
    ) -> DenoiseResponse:
        """
        Denoise video using Real-ESRGAN.
        
        Args:
            video_path: Path to input video
            noise_level: Noise level (low, medium, high)
            model_variant: Real-ESRGAN model variant
            output_path: Output path (auto-generated if not provided)
        
        Returns:
            Denoise job response
        """
        # Validate input
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Generate job ID and output path
        job_id = f"genai_denoise_{uuid.uuid4().hex[:8]}"
        if not output_path:
            input_path = Path(video_path)
            output_path = str(input_path.parent / f"{input_path.stem}_denoised{input_path.suffix}")
        
        # Estimate processing time
        estimated_time = await self._estimate_processing_time(video_path, "denoise")
        
        # Create job record
        job_data = {
            "job_id": job_id,
            "input_path": video_path,
            "output_path": output_path,
            "operation": "denoise",
            "noise_level": noise_level,
            "model_variant": model_variant,
            "status": "queued",
            "progress": 0.0,
            "created_at": time.time(),
            "estimated_time": estimated_time,
        }
        
        self.active_jobs[job_id] = job_data
        
        # Start processing (async)
        asyncio.create_task(self._process_denoise_job(job_data))
        
        return DenoiseResponse(
            job_id=job_id,
            input_path=video_path,
            output_path=output_path,
            noise_level=noise_level,
            model_used=model_variant,
            estimated_time=estimated_time,
            status="queued",
        )
    
    async def restore_video(
        self,
        video_path: str,
        restoration_strength: float = 0.7,
        model_variant: str = "RealESRGAN_x4plus",
        output_path: Optional[str] = None,
    ) -> RestoreResponse:
        """
        Restore damaged video using Real-ESRGAN.
        
        Args:
            video_path: Path to input video
            restoration_strength: Restoration strength (0.0-1.0)
            model_variant: Real-ESRGAN model variant
            output_path: Output path (auto-generated if not provided)
        
        Returns:
            Restore job response
        """
        # Validate input
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Generate job ID and output path
        job_id = f"genai_restore_{uuid.uuid4().hex[:8]}"
        if not output_path:
            input_path = Path(video_path)
            output_path = str(input_path.parent / f"{input_path.stem}_restored{input_path.suffix}")
        
        # Estimate processing time
        estimated_time = await self._estimate_processing_time(video_path, "restore")
        
        # Create job record
        job_data = {
            "job_id": job_id,
            "input_path": video_path,
            "output_path": output_path,
            "operation": "restore",
            "restoration_strength": restoration_strength,
            "model_variant": model_variant,
            "status": "queued",
            "progress": 0.0,
            "created_at": time.time(),
            "estimated_time": estimated_time,
        }
        
        self.active_jobs[job_id] = job_data
        
        # Start processing (async)
        asyncio.create_task(self._process_restore_job(job_data))
        
        return RestoreResponse(
            job_id=job_id,
            input_path=video_path,
            output_path=output_path,
            restoration_strength=restoration_strength,
            model_used=model_variant,
            estimated_time=estimated_time,
            status="queued",
        )
    
    async def _process_upscale_job(self, job_data: Dict[str, Any]):
        """Process video upscaling job."""
        try:
            job_data["status"] = "processing"
            
            # Load Real-ESRGAN model
            esrgan_model = await model_manager.load_model(
                model_name=job_data["model_variant"],
                model_type="esrgan",
            )
            
            # Process video
            await self._process_video_with_esrgan(
                job_data,
                esrgan_model,
                operation="upscale",
            )
            
            job_data["status"] = "completed"
            job_data["progress"] = 100.0
            
            logger.info(
                "Video upscaling completed",
                job_id=job_data["job_id"],
                input_path=job_data["input_path"],
                output_path=job_data["output_path"],
            )
            
        except Exception as e:
            job_data["status"] = "failed"
            job_data["error"] = str(e)
            
            logger.error(
                "Video upscaling failed",
                job_id=job_data["job_id"],
                error=str(e),
            )
    
    async def _process_denoise_job(self, job_data: Dict[str, Any]):
        """Process video denoising job."""
        try:
            job_data["status"] = "processing"
            
            # Load Real-ESRGAN model
            esrgan_model = await model_manager.load_model(
                model_name=job_data["model_variant"],
                model_type="esrgan",
            )
            
            # Process video
            await self._process_video_with_esrgan(
                job_data,
                esrgan_model,
                operation="denoise",
            )
            
            job_data["status"] = "completed"
            job_data["progress"] = 100.0
            
            logger.info(
                "Video denoising completed",
                job_id=job_data["job_id"],
                input_path=job_data["input_path"],
                output_path=job_data["output_path"],
            )
            
        except Exception as e:
            job_data["status"] = "failed"
            job_data["error"] = str(e)
            
            logger.error(
                "Video denoising failed",
                job_id=job_data["job_id"],
                error=str(e),
            )
    
    async def _process_restore_job(self, job_data: Dict[str, Any]):
        """Process video restoration job."""
        try:
            job_data["status"] = "processing"
            
            # Load Real-ESRGAN model
            esrgan_model = await model_manager.load_model(
                model_name=job_data["model_variant"],
                model_type="esrgan",
            )
            
            # Process video
            await self._process_video_with_esrgan(
                job_data,
                esrgan_model,
                operation="restore",
            )
            
            job_data["status"] = "completed"
            job_data["progress"] = 100.0
            
            logger.info(
                "Video restoration completed",
                job_id=job_data["job_id"],
                input_path=job_data["input_path"],
                output_path=job_data["output_path"],
            )
            
        except Exception as e:
            job_data["status"] = "failed"
            job_data["error"] = str(e)
            
            logger.error(
                "Video restoration failed",
                job_id=job_data["job_id"],
                error=str(e),
            )
    
    async def _process_video_with_esrgan(
        self,
        job_data: Dict[str, Any],
        esrgan_model: Any,
        operation: str,
    ):
        """Process video frames with Real-ESRGAN."""
        try:
            import cv2
            import numpy as np
            import tempfile
            import os
            
            # Create temporary directory for frames
            with tempfile.TemporaryDirectory() as temp_dir:
                frames_dir = Path(temp_dir) / "frames"
                enhanced_dir = Path(temp_dir) / "enhanced"
                frames_dir.mkdir()
                enhanced_dir.mkdir()
                
                # Extract frames using FFmpeg
                await self._extract_frames_ffmpeg(
                    job_data["input_path"],
                    str(frames_dir),
                )
                
                # Get list of frame files
                frame_files = sorted(frames_dir.glob("frame_*.png"))
                total_frames = len(frame_files)
                
                if total_frames == 0:
                    raise ValueError("No frames extracted from video")
                
                # Process each frame with Real-ESRGAN
                for i, frame_file in enumerate(frame_files):
                    # Load frame
                    frame = cv2.imread(str(frame_file))
                    
                    # Enhance frame
                    enhanced_frame, _ = esrgan_model.enhance(frame)
                    
                    # Save enhanced frame
                    output_frame_path = enhanced_dir / frame_file.name
                    cv2.imwrite(str(output_frame_path), enhanced_frame)
                    
                    # Update progress
                    progress = (i + 1) / total_frames * 80  # Reserve 20% for reassembly
                    job_data["progress"] = progress
                
                # Reassemble video using FFmpeg
                await self._reassemble_video_ffmpeg(
                    str(enhanced_dir),
                    job_data["input_path"],
                    job_data["output_path"],
                )
                
                job_data["progress"] = 100.0
                
        except Exception as e:
            logger.error(
                "Frame processing failed",
                job_id=job_data["job_id"],
                operation=operation,
                error=str(e),
            )
            raise
    
    async def _extract_frames_ffmpeg(self, video_path: str, frames_dir: str):
        """Extract frames from video using FFmpeg."""
        import subprocess
        
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", "fps=fps=30",  # Extract at 30 FPS
            f"{frames_dir}/frame_%06d.png",
            "-y",  # Overwrite output files
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg frame extraction failed: {stderr.decode()}")
    
    async def _reassemble_video_ffmpeg(
        self,
        frames_dir: str,
        original_video_path: str,
        output_path: str,
    ):
        """Reassemble video from enhanced frames using FFmpeg."""
        import subprocess
        
        cmd = [
            "ffmpeg",
            "-framerate", "30",
            "-i", f"{frames_dir}/frame_%06d.png",
            "-i", original_video_path,  # For audio track
            "-c:v", "libx264",
            "-c:a", "copy",  # Copy audio without re-encoding
            "-pix_fmt", "yuv420p",
            "-shortest",  # Match shortest stream duration
            output_path,
            "-y",  # Overwrite output file
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg video reassembly failed: {stderr.decode()}")
    
    async def _estimate_processing_time(
        self,
        video_path: str,
        operation: str,
        scale_factor: int = 1,
    ) -> float:
        """Estimate processing time for video enhancement."""
        try:
            import cv2
            
            # Get video properties
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps
            cap.release()
            
            # Base processing time per second of video
            base_time_per_second = {
                "upscale": 2.0 * scale_factor,  # Scaling factor affects processing time
                "denoise": 1.5,
                "restore": 2.5,
            }.get(operation, 2.0)
            
            # Adjust for GPU availability
            if genai_settings.gpu_available:
                base_time_per_second *= 0.3  # GPU is much faster
            
            estimated_time = duration * base_time_per_second
            
            return max(estimated_time, 10.0)  # Minimum 10 seconds
            
        except Exception:
            # Return default estimate if we can't analyze the video
            return 120.0
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of an enhancement job."""
        return self.active_jobs.get(job_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the quality enhancer service."""
        return {
            "service": "quality_enhancer",
            "status": "healthy",
            "active_jobs": len(self.active_jobs),
            "supported_operations": ["upscale", "denoise", "restore"],
            "esrgan_models": ["RealESRGAN_x4plus", "RealESRGAN_x2plus", "RealESRGAN_x8plus"],
            "dependencies": {
                "opencv": self._check_opencv(),
                "esrgan": self._check_esrgan(),
                "ffmpeg": self._check_ffmpeg(),
            },
        }
    
    def _check_opencv(self) -> bool:
        """Check if OpenCV is available."""
        try:
            import cv2
            return True
        except ImportError:
            return False
    
    def _check_esrgan(self) -> bool:
        """Check if Real-ESRGAN is available."""
        try:
            from realesrgan import RealESRGANer
            return True
        except ImportError:
            return False
    
    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        try:
            import subprocess
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
            return result.returncode == 0
        except:
            return False