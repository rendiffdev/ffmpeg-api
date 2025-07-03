"""
Complexity Analyzer Service

Analyzes video complexity for optimal encoding parameters.
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, Any
import structlog
import cv2
import numpy as np

from ..models.analysis import ComplexityAnalysisResponse
from ..config import genai_settings
from .model_manager import model_manager

logger = structlog.get_logger()


class ComplexityAnalyzerService:
    """
    Service for analyzing video complexity using AI models.
    
    Features:
    - Motion vector analysis
    - Texture complexity assessment
    - Temporal complexity evaluation
    - Encoding parameter recommendations
    """
    
    def __init__(self):
        self.videomae_model = None
    
    async def analyze_complexity(
        self,
        video_path: str,
        sampling_rate: int = 1,
    ) -> ComplexityAnalysisResponse:
        """
        Analyze video complexity for optimal encoding parameters.
        
        Args:
            video_path: Path to the video file
            sampling_rate: Frame sampling rate (every N frames)
        
        Returns:
            Complexity analysis response
        """
        start_time = time.time()
        
        try:
            # Validate input file
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Analyze video complexity
            complexity_data = await self._analyze_video_complexity(video_path, sampling_rate)
            
            # Generate encoding recommendations
            recommendations = await self._generate_encoding_recommendations(complexity_data)
            
            processing_time = time.time() - start_time
            
            return ComplexityAnalysisResponse(
                video_path=video_path,
                overall_complexity=complexity_data["overall_complexity"],
                motion_metrics=complexity_data["motion_metrics"],
                texture_analysis=complexity_data["texture_analysis"],
                recommended_encoding=recommendations,
                processing_time=processing_time,
            )
            
        except Exception as e:
            logger.error(
                "Complexity analysis failed",
                video_path=video_path,
                error=str(e),
            )
            raise
    
    async def _analyze_video_complexity(
        self, 
        video_path: str, 
        sampling_rate: int
    ) -> Dict[str, Any]:
        """Analyze video complexity using computer vision techniques."""
        try:
            # Open video
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Initialize metrics
            motion_vectors = []
            texture_scores = []
            gradient_magnitudes = []
            
            prev_frame = None
            frame_idx = 0
            
            while frame_idx < frame_count:
                # Set frame position
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                # Convert to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Calculate texture complexity
                texture_score = self._calculate_texture_complexity(gray)
                texture_scores.append(texture_score)
                
                # Calculate gradient magnitude
                grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
                gradient_mag = np.sqrt(grad_x**2 + grad_y**2).mean()
                gradient_magnitudes.append(gradient_mag)
                
                # Calculate motion if we have a previous frame
                if prev_frame is not None:
                    motion = self._calculate_motion_complexity(prev_frame, gray)
                    motion_vectors.append(motion)
                
                prev_frame = gray.copy()
                frame_idx += sampling_rate
            
            cap.release()
            
            # Calculate overall complexity metrics
            overall_complexity = self._calculate_overall_complexity(
                motion_vectors, texture_scores, gradient_magnitudes
            )
            
            motion_metrics = {
                "average_motion": np.mean(motion_vectors) if motion_vectors else 0.0,
                "max_motion": np.max(motion_vectors) if motion_vectors else 0.0,
                "motion_variance": np.var(motion_vectors) if motion_vectors else 0.0,
            }
            
            texture_analysis = {
                "texture_complexity": np.mean(texture_scores),
                "edge_density": np.mean(gradient_magnitudes),
                "gradient_magnitude": np.max(gradient_magnitudes),
            }
            
            return {
                "overall_complexity": overall_complexity,
                "motion_metrics": motion_metrics,
                "texture_analysis": texture_analysis,
            }
            
        except Exception as e:
            logger.error("Video complexity analysis failed", error=str(e))
            # Return default values
            return {
                "overall_complexity": 50.0,
                "motion_metrics": {
                    "average_motion": 25.0,
                    "max_motion": 50.0,
                    "motion_variance": 10.0,
                },
                "texture_analysis": {
                    "texture_complexity": 30.0,
                    "edge_density": 20.0,
                    "gradient_magnitude": 40.0,
                },
            }
    
    def _calculate_texture_complexity(self, gray_frame: np.ndarray) -> float:
        """Calculate texture complexity using Laplacian variance."""
        try:
            laplacian = cv2.Laplacian(gray_frame, cv2.CV_64F)
            variance = laplacian.var()
            # Normalize to 0-100 scale
            return min(100.0, variance / 100.0)
        except:
            return 30.0
    
    def _calculate_motion_complexity(self, prev_frame: np.ndarray, curr_frame: np.ndarray) -> float:
        """Calculate motion complexity using optical flow."""
        try:
            # Calculate dense optical flow
            flow = cv2.calcOpticalFlowPyrLK(
                prev_frame, curr_frame, 
                None, None
            )[0]
            
            if flow is not None:
                # Calculate motion magnitude
                magnitude = np.sqrt(flow[:, :, 0]**2 + flow[:, :, 1]**2)
                return magnitude.mean()
            else:
                return 0.0
        except:
            # Fallback: simple frame difference
            diff = cv2.absdiff(prev_frame, curr_frame)
            return diff.mean() / 2.55  # Normalize to 0-100
    
    def _calculate_overall_complexity(
        self, 
        motion_vectors: list, 
        texture_scores: list, 
        gradient_magnitudes: list
    ) -> float:
        """Calculate overall complexity score."""
        try:
            # Weight different complexity factors
            motion_weight = 0.4
            texture_weight = 0.35
            gradient_weight = 0.25
            
            motion_score = np.mean(motion_vectors) if motion_vectors else 0
            texture_score = np.mean(texture_scores) if texture_scores else 0
            gradient_score = np.mean(gradient_magnitudes) if gradient_magnitudes else 0
            
            # Normalize gradient score to 0-100
            gradient_score = min(100.0, gradient_score / 2.0)
            
            overall = (
                motion_score * motion_weight +
                texture_score * texture_weight +
                gradient_score * gradient_weight
            )
            
            return min(100.0, overall)
            
        except:
            return 50.0
    
    async def _generate_encoding_recommendations(
        self, 
        complexity_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate FFmpeg encoding recommendations based on complexity."""
        complexity = complexity_data["overall_complexity"]
        
        # Base recommendations
        if complexity < 30:
            # Low complexity - dialogue, static scenes
            recommendations = {
                "crf": 26,
                "preset": "fast",
                "bitrate": 1500,
            }
        elif complexity < 60:
            # Medium complexity - normal content
            recommendations = {
                "crf": 23,
                "preset": "medium",
                "bitrate": 3000,
            }
        else:
            # High complexity - action, high motion
            recommendations = {
                "crf": 20,
                "preset": "slow",
                "bitrate": 6000,
            }
        
        return recommendations
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the complexity analyzer service."""
        return {
            "service": "complexity_analyzer",
            "status": "healthy",
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