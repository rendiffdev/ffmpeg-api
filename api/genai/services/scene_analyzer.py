"""
Scene Analyzer Service

Analyzes video scenes using PySceneDetect + VideoMAE.
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any
import structlog
import cv2
import numpy as np

from ..models.analysis import Scene, SceneAnalysisResponse
from ..config import genai_settings
from .model_manager import model_manager

logger = structlog.get_logger()


class SceneAnalyzerService:
    """
    Service for analyzing video scenes using PySceneDetect and VideoMAE.
    
    Features:
    - Scene boundary detection with PySceneDetect
    - Content analysis with VideoMAE
    - Complexity scoring for encoding optimization
    - Motion level assessment
    """
    
    def __init__(self):
        self.scene_detector = None
        self.videomae_model = None
    
    async def analyze_scenes(
        self,
        video_path: str,
        sensitivity_threshold: float = 30.0,
        analysis_depth: str = "medium",
    ) -> SceneAnalysisResponse:
        """
        Analyze video scenes with PySceneDetect and VideoMAE.
        
        Args:
            video_path: Path to the video file
            sensitivity_threshold: Scene detection sensitivity (0-100)
            analysis_depth: Analysis depth (basic, medium, detailed)
        
        Returns:
            Scene analysis response with detected scenes
        """
        start_time = time.time()
        
        try:
            # Validate input file
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Detect scenes using PySceneDetect
            scenes_data = await self._detect_scenes(video_path, sensitivity_threshold)
            
            # Analyze each scene with VideoMAE (if detailed analysis requested)
            if analysis_depth in ["medium", "detailed"]:
                scenes_data = await self._analyze_scene_content(
                    video_path, scenes_data, analysis_depth
                )
            
            # Calculate overall statistics
            total_duration = sum(scene["duration"] for scene in scenes_data)
            average_complexity = sum(scene["complexity_score"] for scene in scenes_data) / len(scenes_data) if scenes_data else 0
            
            # Create scene objects
            scenes = [
                Scene(
                    id=scene["id"],
                    start_time=scene["start_time"],
                    end_time=scene["end_time"],
                    duration=scene["duration"],
                    complexity_score=scene["complexity_score"],
                    motion_level=scene["motion_level"],
                    content_type=scene["content_type"],
                    optimal_bitrate=scene.get("optimal_bitrate"),
                )
                for scene in scenes_data
            ]
            
            processing_time = time.time() - start_time
            
            return SceneAnalysisResponse(
                video_path=video_path,
                total_scenes=len(scenes),
                total_duration=total_duration,
                average_complexity=average_complexity,
                scenes=scenes,
                processing_time=processing_time,
            )
            
        except Exception as e:
            logger.error(
                "Scene analysis failed",
                video_path=video_path,
                error=str(e),
            )
            raise
    
    async def _detect_scenes(self, video_path: str, threshold: float) -> List[Dict[str, Any]]:
        """Detect scene boundaries using PySceneDetect."""
        try:
            from scenedetect import detect, ContentDetector
            
            # Detect scenes
            scene_list = detect(video_path, ContentDetector(threshold=threshold))
            
            # Convert to our format
            scenes_data = []
            for i, (start_time, end_time) in enumerate(scene_list):
                duration = (end_time - start_time).total_seconds()
                
                scenes_data.append({
                    "id": i + 1,
                    "start_time": start_time.total_seconds(),
                    "end_time": end_time.total_seconds(),
                    "duration": duration,
                    "complexity_score": 50.0,  # Default, will be updated by VideoMAE
                    "motion_level": "medium",  # Default, will be updated by analysis
                    "content_type": "unknown",  # Default, will be updated by VideoMAE
                })
            
            return scenes_data
            
        except ImportError:
            raise ImportError("PySceneDetect not installed. Install with: pip install scenedetect")
        except Exception as e:
            logger.error("Scene detection failed", error=str(e))
            raise
    
    async def _analyze_scene_content(
        self,
        video_path: str,
        scenes_data: List[Dict[str, Any]],
        analysis_depth: str,
    ) -> List[Dict[str, Any]]:
        """Analyze scene content using VideoMAE."""
        try:
            # Load VideoMAE model
            videomae = await model_manager.load_model(
                model_name=genai_settings.VIDEOMAE_MODEL,
                model_type="videomae",
            )
            
            # Analyze each scene
            for scene in scenes_data:
                # Extract frames from scene
                frames = await self._extract_scene_frames(
                    video_path, scene["start_time"], scene["end_time"]
                )
                
                if frames:
                    # Analyze with VideoMAE
                    analysis = await self._analyze_frames_with_videomae(
                        frames, videomae, analysis_depth
                    )
                    
                    # Update scene data
                    scene.update(analysis)
            
            return scenes_data
            
        except Exception as e:
            logger.error("Scene content analysis failed", error=str(e))
            # Return scenes with default values if analysis fails
            return scenes_data
    
    async def _extract_scene_frames(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
    ) -> List[Any]:
        """Extract frames from a scene for analysis."""
        try:
            import cv2
            import numpy as np
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate frame positions
            start_frame = int(start_time * fps)
            end_frame = int(end_time * fps)
            
            # Extract frames (sample every N frames to avoid too many)
            frames = []
            frame_step = max(1, (end_frame - start_frame) // 16)  # Max 16 frames per scene
            
            for frame_num in range(start_frame, end_frame, frame_step):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                if ret:
                    frames.append(frame)
            
            cap.release()
            return frames
            
        except Exception as e:
            logger.error("Frame extraction failed", error=str(e))
            return []
    
    async def _analyze_frames_with_videomae(
        self,
        frames: List[Any],
        videomae: Dict[str, Any],
        analysis_depth: str,
    ) -> Dict[str, Any]:
        """Analyze frames using VideoMAE model."""
        try:
            import torch
            import numpy as np
            from PIL import Image
            
            model = videomae["model"]
            processor = videomae["processor"]
            
            # Convert frames to PIL Images
            pil_frames = []
            for frame in frames:
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_frame = Image.fromarray(rgb_frame)
                pil_frames.append(pil_frame)
            
            # Process frames
            inputs = processor(pil_frames, return_tensors="pt")
            
            # Move to GPU if available
            if genai_settings.gpu_available:
                device = torch.device(genai_settings.GPU_DEVICE)
                inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # Get predictions
            with torch.no_grad():
                outputs = model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # Analyze predictions for content characteristics
            analysis = self._interpret_videomae_predictions(predictions, analysis_depth)
            
            return analysis
            
        except Exception as e:
            logger.error("VideoMAE analysis failed", error=str(e))
            return {
                "complexity_score": 50.0,
                "motion_level": "medium",
                "content_type": "unknown",
            }
    
    def _interpret_videomae_predictions(
        self,
        predictions: Any,
        analysis_depth: str,
    ) -> Dict[str, Any]:
        """Interpret VideoMAE predictions for encoding optimization."""
        try:
            import torch
            
            # Get prediction probabilities
            probs = predictions.cpu().numpy()[0]
            
            # Calculate complexity score based on prediction confidence
            max_prob = np.max(probs)
            entropy = -np.sum(probs * np.log(probs + 1e-8))
            
            # Higher entropy suggests more complex content
            complexity_score = min(100.0, (entropy / 5.0) * 100)
            
            # Determine motion level based on prediction patterns
            motion_level = "low"
            if complexity_score > 70:
                motion_level = "high"
            elif complexity_score > 40:
                motion_level = "medium"
            
            # Map predictions to content types (simplified)
            content_type = "general"
            if max_prob > 0.7:
                content_type = "action" if complexity_score > 60 else "dialogue"
            
            # Calculate optimal bitrate based on complexity
            base_bitrate = 2000  # kbps
            bitrate_multiplier = 1.0 + (complexity_score / 100.0)
            optimal_bitrate = int(base_bitrate * bitrate_multiplier)
            
            return {
                "complexity_score": complexity_score,
                "motion_level": motion_level,
                "content_type": content_type,
                "optimal_bitrate": optimal_bitrate,
            }
            
        except Exception as e:
            logger.error("VideoMAE interpretation failed", error=str(e))
            return {
                "complexity_score": 50.0,
                "motion_level": "medium",
                "content_type": "unknown",
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the scene analyzer service."""
        return {
            "service": "scene_analyzer",
            "status": "healthy",
            "videomae_model": genai_settings.VIDEOMAE_MODEL,
            "scene_threshold": genai_settings.SCENE_THRESHOLD,
            "dependencies": {
                "scenedetect": self._check_scenedetect(),
                "videomae": self._check_videomae(),
            },
        }
    
    def _check_scenedetect(self) -> bool:
        """Check if PySceneDetect is available."""
        try:
            import scenedetect
            return True
        except ImportError:
            return False
    
    def _check_videomae(self) -> bool:
        """Check if VideoMAE dependencies are available."""
        try:
            from transformers import VideoMAEImageProcessor
            return True
        except ImportError:
            return False