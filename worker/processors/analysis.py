"""
Media analysis processor for quality metrics and video analysis.
"""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

from api.models.job import Job
from worker.utils.quality import QualityCalculator, QualityMetricsError
from worker.utils.ffmpeg import FFmpegWrapper, FFmpegError
from worker.utils.progress import ProgressTracker

logger = structlog.get_logger()


class AnalysisError(Exception):
    """Base exception for analysis operations."""
    pass


class AnalysisProcessor:
    """Handles media analysis operations including quality metrics."""
    
    def __init__(self):
        self.quality_calculator = QualityCalculator()
        self.ffmpeg = FFmpegWrapper()
        self.initialized = False
    
    async def initialize(self):
        """Initialize the analysis processor."""
        if not self.initialized:
            await self.quality_calculator.initialize()
            await self.ffmpeg.initialize()
            self.initialized = True
            logger.info("AnalysisProcessor initialized")
    
    async def analyze(self, job: Job) -> Dict[str, Any]:
        """
        Main analysis method for quality metrics calculation.
        
        Args:
            job: Job object containing analysis parameters
            
        Returns:
            Dict containing analysis results and quality metrics
        """
        try:
            await self.initialize()
            
            # Create progress tracker
            progress = ProgressTracker(str(job.id))
            
            await progress.set_stage("initializing", "Starting quality analysis", 0)
            
            # Parse job parameters
            analysis_params = self._parse_analysis_params(job)
            
            logger.info(
                "Starting video quality analysis",
                job_id=str(job.id),
                reference_path=analysis_params['reference_path'],
                test_path=analysis_params['test_path'],
                analysis_type=analysis_params['analysis_type']
            )
            
            # Download files if needed (for remote storage)
            await progress.set_stage("downloading", "Downloading source files", 10)
            local_paths = await self._prepare_analysis_files(analysis_params, progress)
            
            # Perform analysis based on type
            await progress.set_stage("analyzing", "Calculating quality metrics", 30)
            
            if analysis_params['analysis_type'] == 'quality_comparison':
                results = await self._analyze_quality_comparison(local_paths, progress)
            elif analysis_params['analysis_type'] == 'content_analysis':
                results = await self._analyze_content(local_paths, progress)
            elif analysis_params['analysis_type'] == 'encoding_analysis':
                results = await self._analyze_encoding(local_paths, progress)
            else:
                # Default to comprehensive analysis
                results = await self._analyze_comprehensive(local_paths, progress)
            
            # Generate quality report
            await progress.set_stage("reporting", "Generating analysis report", 90)
            report = await self.quality_calculator.generate_quality_report(results)
            results['quality_report'] = report
            
            await progress.complete("Analysis completed successfully")
            
            logger.info(
                "Video quality analysis completed",
                job_id=str(job.id),
                results_summary=self._create_results_summary(results)
            )
            
            return results
            
        except Exception as e:
            logger.error("Analysis failed", job_id=str(job.id), error=str(e))
            await progress.error(f"Analysis failed: {e}")
            raise AnalysisError(f"Analysis failed: {e}")
    
    def _parse_analysis_params(self, job: Job) -> Dict[str, Any]:
        """Parse analysis parameters from job object."""
        # For analysis jobs, input_path might contain reference video
        # and options might contain test video path and analysis type
        
        options = job.options or {}
        
        # Default analysis parameters
        params = {
            'reference_path': job.input_path,
            'test_path': options.get('test_path', job.output_path),
            'analysis_type': options.get('analysis_type', 'comprehensive'),
            'vmaf_model': options.get('vmaf_model', 'hd'),
            'include_frame_data': options.get('include_frame_data', False),
            'generate_thumbnails': options.get('generate_thumbnails', False)
        }
        
        return params
    
    async def _prepare_analysis_files(self, params: Dict[str, Any], 
                                    progress: ProgressTracker) -> Dict[str, str]:
        """Prepare local copies of files for analysis."""
        # For now, assume files are already local
        # In production, this would handle downloading from storage backends
        
        reference_path = params['reference_path']
        test_path = params['test_path']
        
        # Validate files exist and are accessible
        if not os.path.exists(reference_path):
            raise AnalysisError(f"Reference file not found: {reference_path}")
        if not os.path.exists(test_path):
            raise AnalysisError(f"Test file not found: {test_path}")
        
        return {
            'reference_path': reference_path,
            'test_path': test_path
        }
    
    async def _analyze_quality_comparison(self, paths: Dict[str, str], 
                                        progress: ProgressTracker) -> Dict[str, Any]:
        """Perform quality comparison analysis (VMAF, PSNR, SSIM)."""
        reference_path = paths['reference_path']
        test_path = paths['test_path']
        
        try:
            # Calculate all quality metrics
            await progress.set_stage("analyzing", "Calculating VMAF, PSNR, SSIM", 40)
            
            metrics = await self.quality_calculator.calculate_all_metrics(
                reference_path, test_path
            )
            
            # Calculate bitrate comparison
            await progress.set_stage("analyzing", "Analyzing bitrate efficiency", 70)
            
            bitrate_metrics = await self.quality_calculator.calculate_bitrate_comparison(
                reference_path, test_path
            )
            
            # Combine results
            results = {
                'analysis_type': 'quality_comparison',
                'quality_metrics': metrics,
                'bitrate_analysis': bitrate_metrics,
                'file_comparison': await self._compare_file_properties(reference_path, test_path)
            }
            
            return results
            
        except QualityMetricsError as e:
            raise AnalysisError(f"Quality comparison failed: {e}")
    
    async def _analyze_content(self, paths: Dict[str, str], 
                             progress: ProgressTracker) -> Dict[str, Any]:
        """Perform content analysis (scene detection, motion analysis)."""
        test_path = paths['test_path']
        
        try:
            await progress.set_stage("analyzing", "Analyzing video content", 50)
            
            # Get detailed video information
            video_info = await self._get_detailed_video_info(test_path)
            
            # Analyze video complexity (motion, scene changes)
            complexity_analysis = await self._analyze_video_complexity(test_path)
            
            results = {
                'analysis_type': 'content_analysis',
                'video_info': video_info,
                'complexity_analysis': complexity_analysis
            }
            
            return results
            
        except Exception as e:
            raise AnalysisError(f"Content analysis failed: {e}")
    
    async def _analyze_encoding(self, paths: Dict[str, str], 
                              progress: ProgressTracker) -> Dict[str, Any]:
        """Perform encoding efficiency analysis."""
        reference_path = paths['reference_path']
        test_path = paths['test_path']
        
        try:
            await progress.set_stage("analyzing", "Analyzing encoding efficiency", 50)
            
            # Get encoding parameters comparison
            encoding_comparison = await self._compare_encoding_parameters(
                reference_path, test_path
            )
            
            # Calculate compression efficiency
            compression_analysis = await self._analyze_compression_efficiency(
                reference_path, test_path
            )
            
            results = {
                'analysis_type': 'encoding_analysis',
                'encoding_comparison': encoding_comparison,
                'compression_analysis': compression_analysis
            }
            
            return results
            
        except Exception as e:
            raise AnalysisError(f"Encoding analysis failed: {e}")
    
    async def _analyze_comprehensive(self, paths: Dict[str, str], 
                                   progress: ProgressTracker) -> Dict[str, Any]:
        """Perform comprehensive analysis including all metrics."""
        try:
            # Perform all analysis types
            await progress.set_stage("analyzing", "Quality comparison analysis", 35)
            quality_results = await self._analyze_quality_comparison(paths, progress)
            
            await progress.set_stage("analyzing", "Content analysis", 60)
            content_results = await self._analyze_content(paths, progress)
            
            await progress.set_stage("analyzing", "Encoding analysis", 80)
            encoding_results = await self._analyze_encoding(paths, progress)
            
            # Combine all results
            results = {
                'analysis_type': 'comprehensive',
                'quality_metrics': quality_results.get('quality_metrics'),
                'bitrate_analysis': quality_results.get('bitrate_analysis'),
                'file_comparison': quality_results.get('file_comparison'),
                'video_info': content_results.get('video_info'),
                'complexity_analysis': content_results.get('complexity_analysis'),
                'encoding_comparison': encoding_results.get('encoding_comparison'),
                'compression_analysis': encoding_results.get('compression_analysis')
            }
            
            return results
            
        except Exception as e:
            raise AnalysisError(f"Comprehensive analysis failed: {e}")
    
    async def _compare_file_properties(self, reference_path: str, test_path: str) -> Dict[str, Any]:
        """Compare basic file properties between reference and test files."""
        try:
            ref_info = await self.ffmpeg.probe_file(reference_path)
            test_info = await self.ffmpeg.probe_file(test_path)
            
            ref_format = ref_info.get('format', {})
            test_format = test_info.get('format', {})
            
            ref_video = next((s for s in ref_info.get('streams', []) 
                             if s.get('codec_type') == 'video'), {})
            test_video = next((s for s in test_info.get('streams', []) 
                              if s.get('codec_type') == 'video'), {})
            
            return {
                'file_sizes': {
                    'reference': int(ref_format.get('size', 0)),
                    'test': int(test_format.get('size', 0)),
                    'size_difference_bytes': int(ref_format.get('size', 0)) - int(test_format.get('size', 0)),
                    'size_reduction_percent': ((int(ref_format.get('size', 0)) - int(test_format.get('size', 0))) / int(ref_format.get('size', 1))) * 100 if int(ref_format.get('size', 0)) > 0 else 0
                },
                'durations': {
                    'reference': float(ref_format.get('duration', 0)),
                    'test': float(test_format.get('duration', 0)),
                    'duration_difference': float(ref_format.get('duration', 0)) - float(test_format.get('duration', 0))
                },
                'resolutions': {
                    'reference': f"{ref_video.get('width', 0)}x{ref_video.get('height', 0)}",
                    'test': f"{test_video.get('width', 0)}x{test_video.get('height', 0)}",
                    'resolution_changed': (ref_video.get('width'), ref_video.get('height')) != (test_video.get('width'), test_video.get('height'))
                },
                'codecs': {
                    'reference': ref_video.get('codec_name', 'unknown'),
                    'test': test_video.get('codec_name', 'unknown'),
                    'codec_changed': ref_video.get('codec_name') != test_video.get('codec_name')
                }
            }
            
        except Exception as e:
            logger.error("File comparison failed", error=str(e))
            return {'error': f"File comparison failed: {e}"}
    
    async def _get_detailed_video_info(self, file_path: str) -> Dict[str, Any]:
        """Get detailed video information including streams and metadata."""
        try:
            probe_info = await self.ffmpeg.probe_file(file_path)
            
            format_info = probe_info.get('format', {})
            streams = probe_info.get('streams', [])
            
            video_streams = [s for s in streams if s.get('codec_type') == 'video']
            audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
            
            return {
                'container': format_info.get('format_name', 'unknown'),
                'duration': float(format_info.get('duration', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'size': int(format_info.get('size', 0)),
                'video_streams': len(video_streams),
                'audio_streams': len(audio_streams),
                'primary_video': video_streams[0] if video_streams else {},
                'primary_audio': audio_streams[0] if audio_streams else {},
                'metadata': format_info.get('tags', {})
            }
            
        except Exception as e:
            logger.error("Video info extraction failed", error=str(e))
            return {'error': f"Video info extraction failed: {e}"}
    
    async def _analyze_video_complexity(self, file_path: str) -> Dict[str, Any]:
        """Analyze video complexity (motion, scene changes, etc.)."""
        try:
            # This is a simplified complexity analysis
            # In production, you might use more sophisticated metrics
            
            probe_info = await self.ffmpeg.probe_file(file_path)
            video_stream = next((s for s in probe_info.get('streams', []) 
                               if s.get('codec_type') == 'video'), {})
            
            # Basic complexity indicators
            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)
            fps = self._parse_fps(video_stream.get('r_frame_rate', '0/1'))
            
            # Estimate complexity based on resolution and frame rate
            pixel_count = width * height
            complexity_score = (pixel_count * fps) / 1000000  # Normalized score
            
            if complexity_score > 100:
                complexity_level = 'very_high'
            elif complexity_score > 50:
                complexity_level = 'high'
            elif complexity_score > 20:
                complexity_level = 'medium'
            else:
                complexity_level = 'low'
            
            return {
                'resolution': f"{width}x{height}",
                'frame_rate': fps,
                'pixel_count': pixel_count,
                'complexity_score': complexity_score,
                'complexity_level': complexity_level,
                'estimated_encoding_difficulty': complexity_level
            }
            
        except Exception as e:
            logger.error("Video complexity analysis failed", error=str(e))
            return {'error': f"Video complexity analysis failed: {e}"}
    
    async def _compare_encoding_parameters(self, reference_path: str, test_path: str) -> Dict[str, Any]:
        """Compare encoding parameters between reference and test files."""
        try:
            ref_info = await self.ffmpeg.probe_file(reference_path)
            test_info = await self.ffmpeg.probe_file(test_path)
            
            ref_video = next((s for s in ref_info.get('streams', []) 
                             if s.get('codec_type') == 'video'), {})
            test_video = next((s for s in test_info.get('streams', []) 
                              if s.get('codec_type') == 'video'), {})
            
            return {
                'codec_comparison': {
                    'reference': ref_video.get('codec_name', 'unknown'),
                    'test': test_video.get('codec_name', 'unknown'),
                    'codec_family_changed': ref_video.get('codec_name', '').split('_')[0] != test_video.get('codec_name', '').split('_')[0]
                },
                'profile_comparison': {
                    'reference': ref_video.get('profile', 'unknown'),
                    'test': test_video.get('profile', 'unknown'),
                    'profile_changed': ref_video.get('profile') != test_video.get('profile')
                },
                'pixel_format_comparison': {
                    'reference': ref_video.get('pix_fmt', 'unknown'),
                    'test': test_video.get('pix_fmt', 'unknown'),
                    'pixel_format_changed': ref_video.get('pix_fmt') != test_video.get('pix_fmt')
                }
            }
            
        except Exception as e:
            logger.error("Encoding parameter comparison failed", error=str(e))
            return {'error': f"Encoding parameter comparison failed: {e}"}
    
    async def _analyze_compression_efficiency(self, reference_path: str, test_path: str) -> Dict[str, Any]:
        """Analyze compression efficiency between reference and test files."""
        try:
            bitrate_metrics = await self.quality_calculator.calculate_bitrate_comparison(
                reference_path, test_path
            )
            
            # Calculate efficiency metrics
            compression_ratio = bitrate_metrics.get('compression_ratio', 0)
            size_reduction = bitrate_metrics.get('size_reduction_percent', 0)
            bitrate_reduction = bitrate_metrics.get('bitrate_reduction_percent', 0)
            
            # Determine efficiency rating
            if size_reduction > 50 and compression_ratio > 5:
                efficiency_rating = 'excellent'
            elif size_reduction > 30 and compression_ratio > 3:
                efficiency_rating = 'very_good'
            elif size_reduction > 15 and compression_ratio > 2:
                efficiency_rating = 'good'
            elif size_reduction > 0:
                efficiency_rating = 'fair'
            else:
                efficiency_rating = 'poor'
            
            return {
                'compression_ratio': compression_ratio,
                'size_reduction_percent': size_reduction,
                'bitrate_reduction_percent': bitrate_reduction,
                'efficiency_rating': efficiency_rating,
                'space_saved_bytes': bitrate_metrics.get('reference_size', 0) - bitrate_metrics.get('test_size', 0)
            }
            
        except Exception as e:
            logger.error("Compression efficiency analysis failed", error=str(e))
            return {'error': f"Compression efficiency analysis failed: {e}"}
    
    def _parse_fps(self, fps_string: str) -> float:
        """Parse frame rate from FFmpeg format."""
        try:
            if '/' in fps_string:
                numerator, denominator = fps_string.split('/')
                return float(numerator) / float(denominator)
            return float(fps_string)
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    def _create_results_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of analysis results for logging."""
        summary = {
            'analysis_type': results.get('analysis_type', 'unknown')
        }
        
        # Add quality metrics summary
        quality_metrics = results.get('quality_metrics')
        if quality_metrics:
            vmaf_data = quality_metrics.get('vmaf', {})
            if isinstance(vmaf_data, dict) and 'mean' in vmaf_data:
                summary['vmaf_score'] = vmaf_data['mean']
        
        # Add compression summary
        bitrate_analysis = results.get('bitrate_analysis')
        if bitrate_analysis:
            summary['compression_ratio'] = bitrate_analysis.get('compression_ratio')
            summary['size_reduction_percent'] = bitrate_analysis.get('size_reduction_percent')
        
        return summary