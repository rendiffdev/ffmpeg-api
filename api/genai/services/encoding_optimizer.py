"""
Encoding Optimizer Service

Optimizes FFmpeg encoding parameters using AI analysis.
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import structlog
import cv2
import numpy as np

from ..models.optimization import (
    ParameterOptimizationResponse,
    BitrateladderResponse,
    CompressionResponse,
    FFmpegParameters,
    BitrateStep,
)
from ..config import genai_settings
from .model_manager import model_manager

logger = structlog.get_logger()


class EncodingOptimizerService:
    """
    Service for optimizing FFmpeg encoding parameters using AI analysis.
    
    Features:
    - AI-powered parameter selection
    - Per-title bitrate ladder generation
    - Compression optimization
    - Quality vs. size balance
    """
    
    def __init__(self):
        self.complexity_cache = {}
    
    async def optimize_parameters(
        self,
        video_path: str,
        target_quality: float = 95.0,
        target_bitrate: Optional[int] = None,
        scene_data: Optional[Dict[str, Any]] = None,
        optimization_mode: str = "quality",
    ) -> ParameterOptimizationResponse:
        """
        Optimize FFmpeg parameters using AI analysis.
        
        Args:
            video_path: Path to input video
            target_quality: Target quality score (0-100)
            target_bitrate: Target bitrate in kbps (optional)
            scene_data: Pre-analyzed scene data (optional)
            optimization_mode: Optimization mode (quality, size, speed)
        
        Returns:
            Parameter optimization response
        """
        start_time = time.time()
        
        try:
            # Validate input file
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Analyze video if scene data not provided
            if not scene_data:
                scene_data = await self._analyze_video_for_optimization(video_path)
            
            # Generate optimal parameters
            optimal_params = await self._generate_optimal_parameters(
                video_path, scene_data, target_quality, target_bitrate, optimization_mode
            )
            
            # Predict quality and file size
            predictions = await self._predict_encoding_results(
                video_path, optimal_params, scene_data
            )
            
            processing_time = time.time() - start_time
            
            return ParameterOptimizationResponse(
                video_path=video_path,
                optimal_parameters=optimal_params,
                predicted_quality=predictions["quality"],
                predicted_file_size=predictions["file_size"],
                confidence_score=predictions["confidence"],
                processing_time=processing_time,
            )
            
        except Exception as e:
            logger.error(
                "Parameter optimization failed",
                video_path=video_path,
                error=str(e),
            )
            raise
    
    async def generate_bitrate_ladder(
        self,
        video_path: str,
        min_bitrate: int = 500,
        max_bitrate: int = 10000,
        steps: int = 5,
        resolutions: Optional[List[str]] = None,
    ) -> BitrateladderResponse:
        """
        Generate AI-optimized bitrate ladder for adaptive streaming.
        
        Args:
            video_path: Path to input video
            min_bitrate: Minimum bitrate in kbps
            max_bitrate: Maximum bitrate in kbps
            steps: Number of bitrate steps
            resolutions: Target resolutions
        
        Returns:
            Bitrate ladder response
        """
        start_time = time.time()
        
        try:
            # Validate input file
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Analyze video complexity
            complexity_data = await self._analyze_video_for_optimization(video_path)
            
            # Generate bitrate steps
            bitrate_steps = await self._generate_bitrate_steps(
                video_path, complexity_data, min_bitrate, max_bitrate, steps, resolutions
            )
            
            # Find optimal step
            optimal_step = await self._find_optimal_bitrate_step(bitrate_steps)
            
            processing_time = time.time() - start_time
            
            return BitrateladderResponse(
                video_path=video_path,
                bitrate_ladder=bitrate_steps,
                optimal_step=optimal_step,
                processing_time=processing_time,
            )
            
        except Exception as e:
            logger.error(
                "Bitrate ladder generation failed",
                video_path=video_path,
                error=str(e),
            )
            raise
    
    async def optimize_compression(
        self,
        video_path: str,
        quality_target: float = 90.0,
        size_constraint: Optional[int] = None,
    ) -> CompressionResponse:
        """
        Optimize compression settings for quality/size balance.
        
        Args:
            video_path: Path to input video
            quality_target: Target quality score
            size_constraint: Maximum file size in bytes
        
        Returns:
            Compression optimization response
        """
        start_time = time.time()
        
        try:
            # Validate input file
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Analyze video
            analysis_data = await self._analyze_video_for_optimization(video_path)
            
            # Optimize compression settings
            compression_settings = await self._optimize_compression_settings(
                video_path, analysis_data, quality_target, size_constraint
            )
            
            # Predict results
            predictions = await self._predict_compression_results(
                video_path, compression_settings, analysis_data
            )
            
            processing_time = time.time() - start_time
            
            return CompressionResponse(
                video_path=video_path,
                compression_settings=compression_settings,
                predicted_file_size=predictions["file_size"],
                predicted_quality=predictions["quality"],
                compression_ratio=predictions["compression_ratio"],
                processing_time=processing_time,
            )
            
        except Exception as e:
            logger.error(
                "Compression optimization failed",
                video_path=video_path,
                error=str(e),
            )
            raise
    
    async def _analyze_video_for_optimization(self, video_path: str) -> Dict[str, Any]:
        """Analyze video for encoding optimization."""
        try:
            # Check cache first
            cache_key = f"{video_path}_{Path(video_path).stat().st_mtime}"
            if cache_key in self.complexity_cache:
                return self.complexity_cache[cache_key]
            
            # Open video and get properties
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps
            
            # Sample frames for analysis
            complexity_scores = []
            motion_scores = []
            texture_scores = []
            
            sample_count = min(50, frame_count // 30)  # Sample every 30 frames, max 50
            frame_step = max(1, frame_count // sample_count)
            
            prev_frame = None
            
            for i in range(0, frame_count, frame_step):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if not ret:
                    continue
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Calculate texture complexity
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                texture_score = laplacian.var()
                texture_scores.append(texture_score)
                
                # Calculate motion if previous frame exists
                if prev_frame is not None:
                    diff = cv2.absdiff(prev_frame, gray)
                    motion_score = diff.mean()
                    motion_scores.append(motion_score)
                
                prev_frame = gray.copy()
                
                if len(texture_scores) >= sample_count:
                    break
            
            cap.release()
            
            # Calculate overall metrics
            avg_texture = np.mean(texture_scores) if texture_scores else 0
            avg_motion = np.mean(motion_scores) if motion_scores else 0
            
            # Normalize scores
            complexity_score = min(100.0, (avg_texture / 2000.0 + avg_motion / 50.0) * 50)
            
            analysis_data = {
                "complexity_score": complexity_score,
                "motion_level": "high" if avg_motion > 30 else "medium" if avg_motion > 15 else "low",
                "texture_complexity": avg_texture,
                "video_properties": {
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "duration": duration,
                    "frame_count": frame_count,
                },
                "motion_metrics": {
                    "average": avg_motion,
                    "max": max(motion_scores) if motion_scores else 0,
                    "variance": np.var(motion_scores) if motion_scores else 0,
                },
            }
            
            # Cache the result
            self.complexity_cache[cache_key] = analysis_data
            
            return analysis_data
            
        except Exception as e:
            logger.error("Video analysis failed", error=str(e))
            # Return default analysis
            return {
                "complexity_score": 50.0,
                "motion_level": "medium",
                "texture_complexity": 1000.0,
                "video_properties": {
                    "width": 1920,
                    "height": 1080,
                    "fps": 30.0,
                    "duration": 60.0,
                    "frame_count": 1800,
                },
            }
    
    async def _generate_optimal_parameters(
        self,
        video_path: str,
        analysis_data: Dict[str, Any],
        target_quality: float,
        target_bitrate: Optional[int],
        optimization_mode: str,
    ) -> FFmpegParameters:
        """Generate optimal FFmpeg parameters based on analysis."""
        complexity = analysis_data["complexity_score"]
        motion_level = analysis_data["motion_level"]
        video_props = analysis_data["video_properties"]
        
        # Base parameters based on complexity
        if complexity < 30:
            # Low complexity
            base_crf = 28
            base_preset = "fast"
            base_bitrate = 1500
        elif complexity < 60:
            # Medium complexity
            base_crf = 23
            base_preset = "medium"
            base_bitrate = 3000
        else:
            # High complexity
            base_crf = 20
            base_preset = "slow"
            base_bitrate = 6000
        
        # Adjust based on optimization mode
        if optimization_mode == "size":
            base_crf += 3
            base_preset = "fast"
            base_bitrate = int(base_bitrate * 0.7)
        elif optimization_mode == "speed":
            base_crf += 1
            base_preset = "ultrafast"
            base_bitrate = int(base_bitrate * 1.2)
        elif optimization_mode == "quality":
            base_crf -= 2
            base_preset = "slow"
            base_bitrate = int(base_bitrate * 1.3)
        
        # Adjust for target quality
        quality_adjustment = (target_quality - 90) / 10.0
        base_crf = max(0, min(51, int(base_crf - quality_adjustment * 3)))
        
        # Use target bitrate if provided
        if target_bitrate:
            base_bitrate = target_bitrate
        
        # Calculate other parameters
        maxrate = int(base_bitrate * 1.5)
        bufsize = maxrate * 2
        
        # Adjust for resolution
        resolution = video_props["width"] * video_props["height"]
        if resolution > 3840 * 2160:  # 4K+
            keyint = 120
            bframes = 4
            refs = 6
        elif resolution > 1920 * 1080:  # > 1080p
            keyint = 90
            bframes = 3
            refs = 5
        else:  # <= 1080p
            keyint = 60
            bframes = 3
            refs = 4
        
        # Adjust for motion
        if motion_level == "high":
            bframes = max(1, bframes - 1)
            keyint = int(keyint * 0.8)
        
        return FFmpegParameters(
            crf=base_crf,
            preset=base_preset,
            bitrate=base_bitrate,
            maxrate=maxrate,
            bufsize=bufsize,
            profile="high",
            level="4.1",
            keyint=keyint,
            bframes=bframes,
            refs=refs,
        )
    
    async def _predict_encoding_results(
        self,
        video_path: str,
        parameters: FFmpegParameters,
        analysis_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Predict encoding quality and file size."""
        try:
            # Get video properties
            video_props = analysis_data["video_properties"]
            complexity = analysis_data["complexity_score"]
            
            # Predict quality based on CRF and complexity
            base_quality = 100 - (parameters.crf * 1.8)
            complexity_penalty = (complexity - 50) * 0.2
            predicted_quality = max(0, min(100, base_quality - complexity_penalty))
            
            # Predict file size
            duration = video_props["duration"]
            bitrate_kbps = parameters.bitrate or 3000
            predicted_size = int((bitrate_kbps * 1000 * duration) / 8)  # bytes
            
            # Confidence based on analysis completeness
            confidence = 0.85 if complexity > 0 else 0.6
            
            return {
                "quality": predicted_quality,
                "file_size": predicted_size,
                "confidence": confidence,
            }
            
        except Exception as e:
            logger.error("Prediction failed", error=str(e))
            return {
                "quality": 85.0,
                "file_size": 50 * 1024 * 1024,  # 50MB default
                "confidence": 0.5,
            }
    
    async def _generate_bitrate_steps(
        self,
        video_path: str,
        analysis_data: Dict[str, Any],
        min_bitrate: int,
        max_bitrate: int,
        steps: int,
        resolutions: Optional[List[str]],
    ) -> List[BitrateStep]:
        """Generate bitrate ladder steps."""
        if not resolutions:
            # Default resolutions based on input
            video_props = analysis_data["video_properties"]
            input_width = video_props["width"]
            input_height = video_props["height"]
            
            if input_width >= 3840:
                resolutions = ["3840x2160", "1920x1080", "1280x720", "854x480"]
            elif input_width >= 1920:
                resolutions = ["1920x1080", "1280x720", "854x480", "640x360"]
            else:
                resolutions = ["1280x720", "854x480", "640x360", "426x240"]
        
        # Generate bitrate steps
        bitrate_range = max_bitrate - min_bitrate
        step_size = bitrate_range / (steps - 1)
        
        ladder_steps = []
        for i in range(steps):
            bitrate = int(min_bitrate + (i * step_size))
            resolution = resolutions[min(i, len(resolutions) - 1)]
            
            # Predict quality for this step
            predicted_quality = await self._predict_quality_for_bitrate(
                analysis_data, bitrate, resolution
            )
            
            # Estimate file size
            duration = analysis_data["video_properties"]["duration"]
            estimated_size = int((bitrate * 1000 * duration) / 8)
            
            ladder_steps.append(BitrateStep(
                resolution=resolution,
                bitrate=bitrate,
                predicted_quality=predicted_quality,
                estimated_file_size=estimated_size,
            ))
        
        return ladder_steps
    
    async def _predict_quality_for_bitrate(
        self,
        analysis_data: Dict[str, Any],
        bitrate: int,
        resolution: str,
    ) -> float:
        """Predict quality for a given bitrate and resolution."""
        complexity = analysis_data["complexity_score"]
        
        # Parse resolution
        width, height = map(int, resolution.split('x'))
        pixel_count = width * height
        
        # Quality prediction based on bits per pixel
        bits_per_pixel = (bitrate * 1000) / (pixel_count * 30)  # Assuming 30 FPS
        
        # Base quality from bits per pixel
        if bits_per_pixel > 0.3:
            base_quality = 95
        elif bits_per_pixel > 0.2:
            base_quality = 90
        elif bits_per_pixel > 0.1:
            base_quality = 80
        elif bits_per_pixel > 0.05:
            base_quality = 70
        else:
            base_quality = 60
        
        # Adjust for complexity
        complexity_penalty = (complexity - 50) * 0.3
        predicted_quality = max(0, min(100, base_quality - complexity_penalty))
        
        return predicted_quality
    
    async def _find_optimal_bitrate_step(self, bitrate_steps: List[BitrateStep]) -> int:
        """Find the optimal bitrate step based on quality/efficiency."""
        best_efficiency = 0
        optimal_index = 0
        
        for i, step in enumerate(bitrate_steps):
            # Calculate efficiency as quality per bitrate
            efficiency = step.predicted_quality / step.bitrate
            
            if efficiency > best_efficiency:
                best_efficiency = efficiency
                optimal_index = i
        
        return optimal_index
    
    async def _optimize_compression_settings(
        self,
        video_path: str,
        analysis_data: Dict[str, Any],
        quality_target: float,
        size_constraint: Optional[int],
    ) -> FFmpegParameters:
        """Optimize compression settings for quality/size balance."""
        # Start with quality-optimized parameters
        base_params = await self._generate_optimal_parameters(
            video_path, analysis_data, quality_target, None, "quality"
        )
        
        if size_constraint:
            # Adjust parameters to meet size constraint
            duration = analysis_data["video_properties"]["duration"]
            target_bitrate = int((size_constraint * 8) / (duration * 1000))
            
            # Use the target bitrate
            base_params.bitrate = target_bitrate
            base_params.maxrate = int(target_bitrate * 1.3)
            base_params.bufsize = base_params.maxrate * 2
            
            # Adjust CRF if bitrate is very low
            if target_bitrate < 1000:
                base_params.crf = min(51, base_params.crf + 5)
            elif target_bitrate < 2000:
                base_params.crf = min(51, base_params.crf + 2)
        
        return base_params
    
    async def _predict_compression_results(
        self,
        video_path: str,
        settings: FFmpegParameters,
        analysis_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Predict compression results."""
        # Get original file size
        original_size = Path(video_path).stat().st_size
        
        # Predict new file size
        duration = analysis_data["video_properties"]["duration"]
        predicted_size = int((settings.bitrate * 1000 * duration) / 8)
        
        # Calculate compression ratio
        compression_ratio = predicted_size / original_size
        
        # Predict quality
        predictions = await self._predict_encoding_results(
            video_path, settings, analysis_data
        )
        
        return {
            "file_size": predicted_size,
            "quality": predictions["quality"],
            "compression_ratio": compression_ratio,
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the encoding optimizer service."""
        return {
            "service": "encoding_optimizer",
            "status": "healthy",
            "optimization_modes": ["quality", "size", "speed"],
            "supported_codecs": ["h264", "h265"],
            "cache_size": len(self.complexity_cache),
            "dependencies": {
                "opencv": self._check_opencv(),
                "numpy": self._check_numpy(),
            },
        }
    
    def _check_opencv(self) -> bool:
        """Check if OpenCV is available."""
        try:
            import cv2
            return True
        except ImportError:
            return False
    
    def _check_numpy(self) -> bool:
        """Check if NumPy is available."""
        try:
            import numpy
            return True
        except ImportError:
            return False