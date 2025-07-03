"""
Pipeline Service

Combines multiple GenAI services into comprehensive video processing pipelines.
"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
import structlog

from ..models.pipeline import SmartEncodeResponse, AdaptiveStreamingResponse
from ..config import genai_settings
from .scene_analyzer import SceneAnalyzerService
from .complexity_analyzer import ComplexityAnalyzerService
from .content_classifier import ContentClassifierService
from .encoding_optimizer import EncodingOptimizerService
from .quality_predictor import QualityPredictorService

logger = structlog.get_logger()


class PipelineService:
    """
    Service for combining multiple GenAI services into complete pipelines.
    
    Features:
    - Smart encoding with AI analysis and optimization
    - Adaptive streaming package generation
    - End-to-end quality assurance
    - Progress tracking and monitoring
    """
    
    def __init__(self):
        # Initialize component services
        self.scene_analyzer = SceneAnalyzerService()
        self.complexity_analyzer = ComplexityAnalyzerService()
        self.content_classifier = ContentClassifierService()
        self.encoding_optimizer = EncodingOptimizerService()
        self.quality_predictor = QualityPredictorService()
        
        # Active jobs tracking
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
    
    async def smart_encode(
        self,
        video_path: str,
        quality_preset: str = "high",
        optimization_level: int = 2,
        output_path: Optional[str] = None,
    ) -> SmartEncodeResponse:
        """
        Complete AI-powered smart encoding pipeline.
        
        Args:
            video_path: Path to input video
            quality_preset: Quality preset (low, medium, high, ultra)
            optimization_level: Optimization level (1-3)
            output_path: Output path (auto-generated if not provided)
        
        Returns:
            Smart encode job response
        """
        # Validate input file
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Generate job ID and output path
        job_id = f"genai_smart_encode_{uuid.uuid4().hex[:8]}"
        if not output_path:
            input_path = Path(video_path)
            output_path = str(input_path.parent / f"{input_path.stem}_smart_encoded{input_path.suffix}")
        
        # Define pipeline steps based on optimization level
        pipeline_steps = self._define_smart_encode_steps(optimization_level)
        
        # Estimate processing time
        estimated_time = await self._estimate_smart_encode_time(
            video_path, optimization_level
        )
        
        # Create job record
        job_data = {
            "job_id": job_id,
            "input_path": video_path,
            "output_path": output_path,
            "quality_preset": quality_preset,
            "optimization_level": optimization_level,
            "pipeline_steps": pipeline_steps,
            "status": "queued",
            "progress": 0.0,
            "current_step": 0,
            "created_at": time.time(),
            "estimated_time": estimated_time,
        }
        
        self.active_jobs[job_id] = job_data
        
        # Start processing (async)
        asyncio.create_task(self._process_smart_encode_job(job_data))
        
        return SmartEncodeResponse(
            job_id=job_id,
            input_path=video_path,
            output_path=output_path,
            quality_preset=quality_preset,
            optimization_level=optimization_level,
            estimated_time=estimated_time,
            pipeline_steps=pipeline_steps,
            status="queued",
        )
    
    async def adaptive_streaming(
        self,
        video_path: str,
        streaming_profiles: List[Dict[str, Any]],
        output_dir: Optional[str] = None,
    ) -> AdaptiveStreamingResponse:
        """
        Generate AI-optimized adaptive streaming package.
        
        Args:
            video_path: Path to input video
            streaming_profiles: List of streaming profile configurations
            output_dir: Output directory (auto-generated if not provided)
        
        Returns:
            Adaptive streaming job response
        """
        # Validate input file
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Generate job ID and output directory
        job_id = f"genai_adaptive_streaming_{uuid.uuid4().hex[:8]}"
        if not output_dir:
            input_path = Path(video_path)
            output_dir = str(input_path.parent / f"{input_path.stem}_adaptive")
        
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate manifest and segment paths
        manifest_path = str(Path(output_dir) / "playlist.m3u8")
        segment_paths = [str(Path(output_dir) / "segments")]
        
        # Estimate processing time
        estimated_time = await self._estimate_adaptive_streaming_time(
            video_path, len(streaming_profiles)
        )
        
        # Create job record
        job_data = {
            "job_id": job_id,
            "input_path": video_path,
            "output_dir": output_dir,
            "manifest_path": manifest_path,
            "segment_paths": segment_paths,
            "streaming_profiles": streaming_profiles,
            "status": "queued",
            "progress": 0.0,
            "created_at": time.time(),
            "estimated_time": estimated_time,
        }
        
        self.active_jobs[job_id] = job_data
        
        # Start processing (async)
        asyncio.create_task(self._process_adaptive_streaming_job(job_data))
        
        return AdaptiveStreamingResponse(
            job_id=job_id,
            input_path=video_path,
            manifest_path=manifest_path,
            segment_paths=segment_paths,
            streaming_profiles=streaming_profiles,
            estimated_time=estimated_time,
            status="queued",
        )
    
    def _define_smart_encode_steps(self, optimization_level: int) -> List[str]:
        """Define pipeline steps based on optimization level."""
        base_steps = [
            "analyze_content",
            "optimize_parameters",
            "encode_video",
            "validate_quality"
        ]
        
        if optimization_level >= 2:
            # Add scene analysis and complexity analysis
            base_steps.insert(0, "detect_scenes")
            base_steps.insert(1, "analyze_complexity")
        
        if optimization_level >= 3:
            # Add content classification and quality prediction
            base_steps.insert(2, "classify_content")
            base_steps.insert(-1, "predict_quality")
        
        return base_steps
    
    async def _process_smart_encode_job(self, job_data: Dict[str, Any]):
        """Process smart encoding job through the pipeline."""
        try:
            job_data["status"] = "processing"
            
            video_path = job_data["input_path"]
            quality_preset = job_data["quality_preset"]
            optimization_level = job_data["optimization_level"]
            pipeline_steps = job_data["pipeline_steps"]
            
            # Pipeline state
            analysis_data = {}
            scene_data = None
            complexity_data = None
            content_data = None
            
            total_steps = len(pipeline_steps)
            
            for i, step in enumerate(pipeline_steps):
                job_data["current_step"] = i
                
                logger.info(
                    "Executing pipeline step",
                    job_id=job_data["job_id"],
                    step=step,
                    progress=f"{i+1}/{total_steps}"
                )
                
                if step == "detect_scenes":
                    scene_data = await self.scene_analyzer.analyze_scenes(
                        video_path=video_path,
                        sensitivity_threshold=30.0,
                        analysis_depth="medium"
                    )
                    analysis_data["scenes"] = scene_data
                
                elif step == "analyze_complexity":
                    complexity_data = await self.complexity_analyzer.analyze_complexity(
                        video_path=video_path,
                        sampling_rate=2
                    )
                    analysis_data["complexity"] = complexity_data
                
                elif step == "classify_content":
                    content_data = await self.content_classifier.classify_content(
                        video_path=video_path
                    )
                    analysis_data["content"] = content_data
                
                elif step == "analyze_content":
                    # Comprehensive content analysis
                    if not complexity_data:
                        complexity_data = await self.complexity_analyzer.analyze_complexity(
                            video_path=video_path,
                            sampling_rate=1
                        )
                    analysis_data["complexity"] = complexity_data
                
                elif step == "optimize_parameters":
                    # Generate optimal encoding parameters
                    target_quality = self._get_target_quality_for_preset(quality_preset)
                    
                    optimization_response = await self.encoding_optimizer.optimize_parameters(
                        video_path=video_path,
                        target_quality=target_quality,
                        scene_data=scene_data.dict() if scene_data else None,
                        optimization_mode="quality" if quality_preset in ["high", "ultra"] else "balanced"
                    )
                    
                    analysis_data["optimal_parameters"] = optimization_response.optimal_parameters
                    analysis_data["predicted_quality"] = optimization_response.predicted_quality
                
                elif step == "predict_quality":
                    # Predict encoding quality before actual encoding
                    if "optimal_parameters" in analysis_data:
                        quality_prediction = await self.quality_predictor.predict_encoding_quality(
                            video_path=video_path,
                            encoding_parameters=analysis_data["optimal_parameters"].dict()
                        )
                        analysis_data["quality_prediction"] = quality_prediction
                
                elif step == "encode_video":
                    # Perform actual encoding with optimized parameters
                    await self._execute_optimized_encoding(
                        job_data, analysis_data
                    )
                
                elif step == "validate_quality":
                    # Validate output quality
                    if Path(job_data["output_path"]).exists():
                        quality_validation = await self.quality_predictor.predict_quality(
                            video_path=job_data["output_path"]
                        )
                        analysis_data["output_quality"] = quality_validation
                
                # Update progress
                progress = ((i + 1) / total_steps) * 100
                job_data["progress"] = progress
            
            # Job completed successfully
            job_data["status"] = "completed"
            job_data["progress"] = 100.0
            job_data["analysis_data"] = analysis_data
            
            logger.info(
                "Smart encoding pipeline completed",
                job_id=job_data["job_id"],
                input_path=video_path,
                output_path=job_data["output_path"],
            )
            
        except Exception as e:
            job_data["status"] = "failed"
            job_data["error"] = str(e)
            
            logger.error(
                "Smart encoding pipeline failed",
                job_id=job_data["job_id"],
                error=str(e),
            )
    
    async def _process_adaptive_streaming_job(self, job_data: Dict[str, Any]):
        """Process adaptive streaming job."""
        try:
            job_data["status"] = "processing"
            
            video_path = job_data["input_path"]
            streaming_profiles = job_data["streaming_profiles"]
            output_dir = job_data["output_dir"]
            
            # Step 1: Analyze content for optimal segmentation
            job_data["progress"] = 10.0
            scene_data = await self.scene_analyzer.analyze_scenes(
                video_path=video_path,
                sensitivity_threshold=25.0,  # More sensitive for streaming
                analysis_depth="basic"
            )
            
            # Step 2: Optimize bitrate ladder
            job_data["progress"] = 25.0
            bitrates = [profile.get("bitrate", 3000) for profile in streaming_profiles]
            min_bitrate = min(bitrates)
            max_bitrate = max(bitrates)
            
            bitrate_ladder = await self.encoding_optimizer.generate_bitrate_ladder(
                video_path=video_path,
                min_bitrate=min_bitrate,
                max_bitrate=max_bitrate,
                steps=len(streaming_profiles)
            )
            
            # Step 3: Generate optimized streaming profiles
            job_data["progress"] = 40.0
            optimized_profiles = self._optimize_streaming_profiles(
                streaming_profiles, bitrate_ladder, scene_data
            )
            
            # Step 4: Encode all variants
            job_data["progress"] = 50.0
            encoded_variants = []
            
            for i, profile in enumerate(optimized_profiles):
                variant_progress = 50.0 + (40.0 * (i + 1) / len(optimized_profiles))
                job_data["progress"] = variant_progress
                
                # Encode variant (simulated)
                variant_path = await self._encode_streaming_variant(
                    video_path, profile, output_dir, i
                )
                encoded_variants.append(variant_path)
            
            # Step 5: Generate manifest files
            job_data["progress"] = 90.0
            await self._generate_streaming_manifest(
                encoded_variants, optimized_profiles, job_data["manifest_path"]
            )
            
            # Job completed
            job_data["status"] = "completed"
            job_data["progress"] = 100.0
            job_data["encoded_variants"] = encoded_variants
            job_data["optimized_profiles"] = optimized_profiles
            
            logger.info(
                "Adaptive streaming pipeline completed",
                job_id=job_data["job_id"],
                variants_count=len(encoded_variants),
            )
            
        except Exception as e:
            job_data["status"] = "failed"
            job_data["error"] = str(e)
            
            logger.error(
                "Adaptive streaming pipeline failed",
                job_id=job_data["job_id"],
                error=str(e),
            )
    
    def _get_target_quality_for_preset(self, quality_preset: str) -> float:
        """Get target quality for preset."""
        quality_map = {
            "low": 70.0,
            "medium": 85.0,
            "high": 95.0,
            "ultra": 98.0,
        }
        return quality_map.get(quality_preset, 85.0)
    
    async def _execute_optimized_encoding(
        self,
        job_data: Dict[str, Any],
        analysis_data: Dict[str, Any],
    ):
        """Execute encoding with optimized parameters."""
        try:
            # This would integrate with the existing FFmpeg processing pipeline
            # For now, simulate the encoding process
            
            input_path = job_data["input_path"]
            output_path = job_data["output_path"]
            
            # Get optimal parameters
            if "optimal_parameters" in analysis_data:
                params = analysis_data["optimal_parameters"]
                
                # Build FFmpeg command with optimal parameters
                ffmpeg_cmd = self._build_ffmpeg_command(
                    input_path, output_path, params
                )
                
                # Execute encoding (simulated)
                logger.info(
                    "Executing optimized encoding",
                    job_id=job_data["job_id"],
                    command=ffmpeg_cmd[:100] + "..." if len(ffmpeg_cmd) > 100 else ffmpeg_cmd
                )
                
                # Simulate encoding time
                await asyncio.sleep(2.0)
                
                # Create dummy output file for testing
                Path(output_path).touch()
                
            else:
                raise ValueError("No optimal parameters found for encoding")
                
        except Exception as e:
            logger.error("Optimized encoding failed", error=str(e))
            raise
    
    def _build_ffmpeg_command(
        self,
        input_path: str,
        output_path: str,
        params: Any,
    ) -> str:
        """Build FFmpeg command with optimal parameters."""
        # Convert parameters to FFmpeg command
        cmd_parts = [
            "ffmpeg",
            "-i", input_path,
            "-c:v", "libx264",
            "-crf", str(params.crf),
            "-preset", params.preset,
        ]
        
        if params.bitrate:
            cmd_parts.extend(["-b:v", f"{params.bitrate}k"])
        
        if params.maxrate:
            cmd_parts.extend(["-maxrate", f"{params.maxrate}k"])
        
        if params.bufsize:
            cmd_parts.extend(["-bufsize", f"{params.bufsize}k"])
        
        cmd_parts.extend([
            "-profile:v", params.profile,
            "-level", params.level,
            "-g", str(params.keyint),
            "-bf", str(params.bframes),
            "-refs", str(params.refs),
            "-y",  # Overwrite output
            output_path
        ])
        
        return " ".join(cmd_parts)
    
    def _optimize_streaming_profiles(
        self,
        original_profiles: List[Dict[str, Any]],
        bitrate_ladder: Any,
        scene_data: Any,
    ) -> List[Dict[str, Any]]:
        """Optimize streaming profiles based on AI analysis."""
        optimized_profiles = []
        
        for i, profile in enumerate(original_profiles):
            # Get corresponding bitrate step
            if i < len(bitrate_ladder.bitrate_ladder):
                ladder_step = bitrate_ladder.bitrate_ladder[i]
                
                # Optimize profile
                optimized_profile = profile.copy()
                optimized_profile["bitrate"] = ladder_step.bitrate
                optimized_profile["resolution"] = ladder_step.resolution
                optimized_profile["predicted_quality"] = ladder_step.predicted_quality
                
                # Add scene-aware settings
                if scene_data and scene_data.average_complexity > 70:
                    # High complexity content
                    optimized_profile["keyint_max"] = 60
                    optimized_profile["bframes"] = 2
                else:
                    # Normal content
                    optimized_profile["keyint_max"] = 120
                    optimized_profile["bframes"] = 3
                
                optimized_profiles.append(optimized_profile)
            else:
                optimized_profiles.append(profile)
        
        return optimized_profiles
    
    async def _encode_streaming_variant(
        self,
        input_path: str,
        profile: Dict[str, Any],
        output_dir: str,
        variant_index: int,
    ) -> str:
        """Encode a single streaming variant."""
        # Generate output path for variant
        variant_name = f"variant_{variant_index}_{profile['bitrate']}k.m3u8"
        variant_path = str(Path(output_dir) / variant_name)
        
        # Simulate encoding process
        logger.info(
            "Encoding streaming variant",
            variant_index=variant_index,
            bitrate=profile.get("bitrate"),
            resolution=profile.get("resolution"),
        )
        
        # In a real implementation, this would execute FFmpeg
        await asyncio.sleep(1.0)  # Simulate encoding time
        
        # Create dummy variant file
        Path(variant_path).touch()
        
        return variant_path
    
    async def _generate_streaming_manifest(
        self,
        variant_paths: List[str],
        profiles: List[Dict[str, Any]],
        manifest_path: str,
    ):
        """Generate HLS master manifest."""
        try:
            manifest_content = "#EXTM3U\n#EXT-X-VERSION:3\n\n"
            
            for i, (variant_path, profile) in enumerate(zip(variant_paths, profiles)):
                bitrate = profile.get("bitrate", 3000)
                resolution = profile.get("resolution", "1920x1080")
                
                manifest_content += f"#EXT-X-STREAM-INF:BANDWIDTH={bitrate * 1000},RESOLUTION={resolution}\n"
                manifest_content += f"{Path(variant_path).name}\n\n"
            
            # Write manifest file
            with open(manifest_path, "w") as f:
                f.write(manifest_content)
                
            logger.info("Streaming manifest generated", manifest_path=manifest_path)
            
        except Exception as e:
            logger.error("Manifest generation failed", error=str(e))
            raise
    
    async def _estimate_smart_encode_time(
        self,
        video_path: str,
        optimization_level: int,
    ) -> float:
        """Estimate processing time for smart encoding."""
        try:
            import cv2
            
            # Get video duration
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps
            cap.release()
            
            # Base encoding time (roughly real-time with GPU)
            base_time = duration * 0.5 if genai_settings.gpu_available else duration * 2.0
            
            # Add analysis overhead
            analysis_overhead = {
                1: 10,   # Basic optimization
                2: 30,   # Scene + complexity analysis
                3: 60,   # Full AI pipeline
            }.get(optimization_level, 30)
            
            return base_time + analysis_overhead
            
        except Exception:
            # Default estimate
            return 120.0
    
    async def _estimate_adaptive_streaming_time(
        self,
        video_path: str,
        profile_count: int,
    ) -> float:
        """Estimate processing time for adaptive streaming."""
        try:
            import cv2
            
            # Get video duration
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps
            cap.release()
            
            # Encoding time per variant
            time_per_variant = duration * 0.3 if genai_settings.gpu_available else duration * 1.0
            
            # Total time including analysis
            total_time = (time_per_variant * profile_count) + 60  # 60s analysis overhead
            
            return total_time
            
        except Exception:
            # Default estimate
            return profile_count * 60.0 + 120.0
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a pipeline job."""
        return self.active_jobs.get(job_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the pipeline service."""
        # Check all component services
        component_health = {}
        
        try:
            component_health["scene_analyzer"] = await self.scene_analyzer.health_check()
        except:
            component_health["scene_analyzer"] = {"status": "unhealthy"}
        
        try:
            component_health["complexity_analyzer"] = await self.complexity_analyzer.health_check()
        except:
            component_health["complexity_analyzer"] = {"status": "unhealthy"}
        
        try:
            component_health["content_classifier"] = await self.content_classifier.health_check()
        except:
            component_health["content_classifier"] = {"status": "unhealthy"}
        
        try:
            component_health["encoding_optimizer"] = await self.encoding_optimizer.health_check()
        except:
            component_health["encoding_optimizer"] = {"status": "unhealthy"}
        
        try:
            component_health["quality_predictor"] = await self.quality_predictor.health_check()
        except:
            component_health["quality_predictor"] = {"status": "unhealthy"}
        
        # Overall health
        healthy_components = sum(
            1 for health in component_health.values() 
            if health.get("status") == "healthy"
        )
        total_components = len(component_health)
        
        overall_status = "healthy" if healthy_components == total_components else "degraded"
        
        return {
            "service": "pipeline_service",
            "status": overall_status,
            "active_jobs": len(self.active_jobs),
            "components": component_health,
            "component_health": f"{healthy_components}/{total_components}",
            "available_pipelines": ["smart_encode", "adaptive_streaming"],
        }