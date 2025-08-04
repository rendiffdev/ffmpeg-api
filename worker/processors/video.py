"""
Video processing module with production-grade FFmpeg integration.
"""
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import structlog

from worker.utils.ffmpeg import FFmpegWrapper, FFmpegError
from worker.utils.progress import ProgressTracker

logger = structlog.get_logger()


class VideoProcessingError(Exception):
    """Base exception for video processing errors."""
    pass


class InvalidInputError(VideoProcessingError):
    """Exception for invalid input files."""
    pass


class UnsupportedFormatError(VideoProcessingError):
    """Exception for unsupported formats."""
    pass


class ProcessingTimeoutError(VideoProcessingError):
    """Exception for processing timeouts."""
    pass


class VideoProcessor:
    """Handles video processing operations with FFmpeg."""
    
    def __init__(self):
        self.ffmpeg = FFmpegWrapper()
        self.initialized = False
        self.supported_input_formats = {
            'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm', 'm4v', 
            '3gp', 'ts', 'mts', 'm2ts', 'vob', 'mpg', 'mpeg', 'ogv'
        }
        self.supported_output_formats = {
            'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'm4v', 'ts', 'mpg'
        }
        
    async def initialize(self):
        """Initialize the video processor."""
        if not self.initialized:
            await self.ffmpeg.initialize()
            self.initialized = True
            logger.info("VideoProcessor initialized")
    
    async def process(self, input_path: str, output_path: str, 
                     options: Dict[str, Any], operations: List[Dict[str, Any]],
                     progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Main video processing method.
        
        Args:
            input_path: Path to input video file
            output_path: Path for output video file
            options: Global processing options
            operations: List of operations to perform
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing processing results and metrics
        """
        try:
            await self.initialize()
            
            # Validate input file
            await self._validate_input(input_path)
            
            # Validate operations
            if not self.ffmpeg.validate_operations(operations):
                raise VideoProcessingError("Invalid operations provided")
            
            # Validate output format
            await self._validate_output_format(output_path, options)
            
            # Create output directory if needed
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Set processing timeout based on input duration
            duration = await self.ffmpeg.get_file_duration(input_path)
            timeout = self._calculate_timeout(duration, operations)
            
            logger.info(
                "Starting video processing",
                input_path=input_path,
                output_path=output_path,
                operations=operations,
                options=options,
                estimated_timeout=timeout
            )
            
            # Execute FFmpeg processing
            result = await self.ffmpeg.execute_command(
                input_path=input_path,
                output_path=output_path,
                options=options,
                operations=operations,
                progress_callback=progress_callback,
                timeout=timeout
            )
            
            # Validate output file
            await self._validate_output(output_path)
            
            # Extract processing metrics
            metrics = await self._extract_metrics(input_path, output_path, result)
            
            logger.info(
                "Video processing completed successfully",
                input_path=input_path,
                output_path=output_path,
                metrics=metrics
            )
            
            return {
                'success': True,
                'input_path': input_path,
                'output_path': output_path,
                'metrics': metrics,
                'processing_stats': result.get('processing_stats', {}),
                'command': result.get('command', '')
            }
            
        except FFmpegError as e:
            logger.error("FFmpeg processing failed", error=str(e))
            raise VideoProcessingError(f"FFmpeg processing failed: {e}")
        except Exception as e:
            logger.error("Video processing failed", error=str(e))
            raise VideoProcessingError(f"Video processing failed: {e}")
    
    async def _validate_input(self, input_path: str):
        """Validate input video file."""
        if not os.path.exists(input_path):
            raise InvalidInputError(f"Input file not found: {input_path}")
        
        if os.path.getsize(input_path) == 0:
            raise InvalidInputError(f"Input file is empty: {input_path}")
        
        # Check file extension
        file_ext = Path(input_path).suffix.lower().lstrip('.')
        if file_ext not in self.supported_input_formats:
            raise UnsupportedFormatError(f"Unsupported input format: {file_ext}")
        
        # Probe file to ensure it's valid
        try:
            probe_info = await self.ffmpeg.probe_file(input_path)
            
            # Check if file has video stream
            video_streams = [s for s in probe_info.get('streams', []) 
                           if s.get('codec_type') == 'video']
            if not video_streams:
                raise InvalidInputError(f"No video stream found in: {input_path}")
            
            # Check if video stream is readable
            video_stream = video_streams[0]
            if video_stream.get('disposition', {}).get('attached_pic'):
                raise InvalidInputError(f"File contains only cover art: {input_path}")
                
        except FFmpegError as e:
            raise InvalidInputError(f"Invalid or corrupted video file: {e}")
    
    async def _validate_output_format(self, output_path: str, options: Dict[str, Any]):
        """Validate output format and options."""
        file_ext = Path(output_path).suffix.lower().lstrip('.')
        
        # Check if format is specified in options
        format_name = options.get('format', file_ext)
        
        if format_name not in self.supported_output_formats:
            raise UnsupportedFormatError(f"Unsupported output format: {format_name}")
        
        # Validate codec compatibility with container
        self._validate_codec_container_compatibility(options, format_name)
    
    def _validate_codec_container_compatibility(self, options: Dict[str, Any], container: str):
        """Validate codec-container compatibility."""
        video_codec = options.get('video_codec')
        audio_codec = options.get('audio_codec')
        
        # Container-specific codec restrictions
        codec_restrictions = {
            'mp4': {
                'video': ['h264', 'h265', 'hevc', 'av1'],
                'audio': ['aac', 'mp3', 'ac3']
            },
            'webm': {
                'video': ['vp8', 'vp9', 'av1'],
                'audio': ['vorbis', 'opus']
            },
            'avi': {
                'video': ['h264', 'xvid', 'divx'],
                'audio': ['mp3', 'ac3', 'pcm']
            }
        }
        
        if container in codec_restrictions:
            restrictions = codec_restrictions[container]
            
            if video_codec and video_codec not in restrictions.get('video', []):
                logger.warning(
                    f"Video codec {video_codec} may not be compatible with {container} container"
                )
            
            if audio_codec and audio_codec not in restrictions.get('audio', []):
                logger.warning(
                    f"Audio codec {audio_codec} may not be compatible with {container} container"
                )
    
    def _calculate_timeout(self, duration: float, operations: List[Dict[str, Any]]) -> int:
        """Calculate processing timeout based on input duration and operations."""
        if duration <= 0:
            return 3600  # 1 hour default for unknown duration
        
        # Base timeout: 10x realtime for complex operations
        base_multiplier = 10
        
        # Adjust based on operations
        for operation in operations:
            op_type = operation.get('type')
            if op_type == 'transcode':
                # Transcoding is CPU intensive
                base_multiplier += 5
            elif op_type == 'watermark':
                # Watermarking adds processing time
                base_multiplier += 2
            elif op_type == 'filter':
                # Filters can be expensive
                base_multiplier += 3
        
        timeout = int(duration * base_multiplier)
        
        # Set reasonable bounds
        timeout = max(300, min(timeout, 14400))  # 5 minutes to 4 hours
        
        return timeout
    
    async def _validate_output(self, output_path: str):
        """Validate that output file was created successfully."""
        if not os.path.exists(output_path):
            raise VideoProcessingError(f"Output file was not created: {output_path}")
        
        if os.path.getsize(output_path) == 0:
            raise VideoProcessingError(f"Output file is empty: {output_path}")
        
        # Quick probe to ensure output is valid
        try:
            probe_info = await self.ffmpeg.probe_file(output_path)
            
            # Ensure output has video stream
            video_streams = [s for s in probe_info.get('streams', []) 
                           if s.get('codec_type') == 'video']
            if not video_streams:
                raise VideoProcessingError(f"Output file has no video stream: {output_path}")
                
        except FFmpegError as e:
            raise VideoProcessingError(f"Invalid output file created: {e}")
    
    async def _extract_metrics(self, input_path: str, output_path: str, 
                              result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract processing metrics and file information."""
        try:
            # Get input and output file info
            input_info = await self.ffmpeg.probe_file(input_path)
            output_info = await self.ffmpeg.probe_file(output_path)
            
            # Extract basic metrics
            input_format = input_info.get('format', {})
            output_format = output_info.get('format', {})
            
            input_size = int(input_format.get('size', 0))
            output_size = int(output_format.get('size', 0))
            
            # Calculate compression ratio
            compression_ratio = input_size / output_size if output_size > 0 else 0
            
            # Extract video stream info
            input_video = next((s for s in input_info.get('streams', []) 
                               if s.get('codec_type') == 'video'), {})
            output_video = next((s for s in output_info.get('streams', []) 
                                if s.get('codec_type') == 'video'), {})
            
            metrics = {
                'input_size_bytes': input_size,
                'output_size_bytes': output_size,
                'compression_ratio': compression_ratio,
                'size_reduction_percent': ((input_size - output_size) / input_size * 100) if input_size > 0 else 0,
                'input_duration': float(input_format.get('duration', 0)),
                'output_duration': float(output_format.get('duration', 0)),
                'input_bitrate': int(input_format.get('bit_rate', 0)),
                'output_bitrate': int(output_format.get('bit_rate', 0)),
                'input_codec': input_video.get('codec_name', 'unknown'),
                'output_codec': output_video.get('codec_name', 'unknown'),
                'input_resolution': f"{input_video.get('width', 0)}x{input_video.get('height', 0)}",
                'output_resolution': f"{output_video.get('width', 0)}x{output_video.get('height', 0)}",
                'input_fps': self._parse_fps(input_video.get('r_frame_rate', '0/1')),
                'output_fps': self._parse_fps(output_video.get('r_frame_rate', '0/1')),
                'processing_stats': result.get('processing_stats', {})
            }
            
            return metrics
            
        except Exception as e:
            logger.error("Failed to extract metrics", error=str(e))
            return {
                'error': f"Failed to extract metrics: {e}",
                'processing_stats': result.get('processing_stats', {})
            }
    
    def _parse_fps(self, fps_string: str) -> float:
        """Parse frame rate from FFmpeg format (e.g., '25/1')."""
        try:
            if '/' in fps_string:
                numerator, denominator = fps_string.split('/')
                return float(numerator) / float(denominator)
            return float(fps_string)
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    async def get_video_info(self, file_path: str) -> Dict[str, Any]:
        """Get detailed video file information."""
        await self.initialize()
        
        try:
            probe_info = await self.ffmpeg.probe_file(file_path)
            
            # Extract relevant information
            format_info = probe_info.get('format', {})
            video_stream = next((s for s in probe_info.get('streams', []) 
                               if s.get('codec_type') == 'video'), {})
            audio_streams = [s for s in probe_info.get('streams', []) 
                           if s.get('codec_type') == 'audio']
            
            return {
                'filename': format_info.get('filename', ''),
                'format_name': format_info.get('format_name', ''),
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'bit_rate': int(format_info.get('bit_rate', 0)),
                'video': {
                    'codec': video_stream.get('codec_name', ''),
                    'width': video_stream.get('width', 0),
                    'height': video_stream.get('height', 0),
                    'fps': self._parse_fps(video_stream.get('r_frame_rate', '0/1')),
                    'bit_rate': int(video_stream.get('bit_rate', 0)),
                    'pixel_format': video_stream.get('pix_fmt', ''),
                    'profile': video_stream.get('profile', '')
                },
                'audio': [
                    {
                        'codec': stream.get('codec_name', ''),
                        'channels': stream.get('channels', 0),
                        'sample_rate': stream.get('sample_rate', 0),
                        'bit_rate': int(stream.get('bit_rate', 0)),
                        'language': stream.get('tags', {}).get('language', '')
                    }
                    for stream in audio_streams
                ],
                'metadata': format_info.get('tags', {})
            }
            
        except FFmpegError as e:
            raise VideoProcessingError(f"Failed to get video info: {e}")
    
    async def create_thumbnail(self, input_path: str, output_path: str, 
                             timestamp: float = 10.0, width: int = 320, height: int = 240,
                             quality: str = "high") -> Dict[str, Any]:
        """Create a high-quality thumbnail image from video at specified timestamp."""
        await self.initialize()
        
        try:
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Quality settings
            quality_settings = {
                'low': {'qscale': 10, 'format': 'mjpeg'},
                'medium': {'qscale': 5, 'format': 'mjpeg'},
                'high': {'qscale': 2, 'format': 'mjpeg'},
                'png': {'format': 'png'}
            }
            
            quality_config = quality_settings.get(quality, quality_settings['high'])
            
            # Create thumbnail using FFmpeg
            options = {
                'format': 'image2',
                'vframes': 1  # Extract single frame
            }
            
            operations = [
                {
                    'type': 'trim',
                    'params': {'start_time': timestamp}
                },
                {
                    'type': 'transcode',
                    'params': {
                        'width': width,
                        'height': height,
                        'video_codec': quality_config['format'],
                        **({} if 'qscale' not in quality_config else {'qscale': quality_config['qscale']})
                    }
                }
            ]
            
            result = await self.ffmpeg.execute_command(
                input_path=input_path,
                output_path=output_path,
                options=options,
                operations=operations,
                timeout=60  # 1 minute timeout for thumbnail
            )
            
            return {
                'success': True,
                'thumbnail_path': output_path,
                'timestamp': timestamp,
                'dimensions': f"{width}x{height}",
                'quality': quality
            }
            
        except Exception as e:
            logger.error("Thumbnail creation failed", error=str(e))
            raise VideoProcessingError(f"Thumbnail creation failed: {e}")
    
    async def create_thumbnail_grid(self, input_path: str, output_path: str,
                                  rows: int = 3, cols: int = 4, width: int = 1280, height: int = 720) -> Dict[str, Any]:
        """Create a thumbnail grid showing multiple frames from the video."""
        await self.initialize()
        
        try:
            # Get video duration to calculate timestamps
            duration = await self.ffmpeg.get_file_duration(input_path)
            if duration <= 0:
                raise VideoProcessingError("Could not determine video duration")
            
            # Calculate grid dimensions
            tile_width = width // cols
            tile_height = height // rows
            total_tiles = rows * cols
            
            # Skip first and last 10% of video for better thumbnails
            start_time = duration * 0.1
            end_time = duration * 0.9
            interval = (end_time - start_time) / (total_tiles - 1)
            
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Create grid using FFmpeg tile filter
            options = {
                'format': 'image2',
                'vframes': 1
            }
            
            operations = [
                {
                    'type': 'filter',
                    'params': {
                        'select': f'not(mod(n\\,{int(duration * 25 / total_tiles)}))',  # Assuming 25fps
                        'tile': f'{cols}x{rows}',
                        'scale': f'{tile_width}:{tile_height}'
                    }
                }
            ]
            
            result = await self.ffmpeg.execute_command(
                input_path=input_path,
                output_path=output_path,
                options=options,
                operations=operations,
                timeout=120  # 2 minute timeout for grid
            )
            
            return {
                'success': True,
                'thumbnail_grid_path': output_path,
                'dimensions': f"{width}x{height}",
                'grid_size': f"{cols}x{rows}",
                'total_frames': total_tiles
            }
            
        except Exception as e:
            logger.error("Thumbnail grid creation failed", error=str(e))
            raise VideoProcessingError(f"Thumbnail grid creation failed: {e}")
    
    async def create_multiple_thumbnails(self, input_path: str, output_dir: str,
                                       count: int = 5, width: int = 320, height: int = 240,
                                       quality: str = "high") -> Dict[str, Any]:
        """Create multiple thumbnails at evenly spaced intervals."""
        await self.initialize()
        
        try:
            # Get video duration
            duration = await self.ffmpeg.get_file_duration(input_path)
            if duration <= 0:
                raise VideoProcessingError("Could not determine video duration")
            
            # Calculate timestamps (skip first and last 10%)
            start_time = duration * 0.1
            end_time = duration * 0.9
            interval = (end_time - start_time) / (count - 1) if count > 1 else 0
            
            # Ensure output directory exists
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            thumbnails = []
            for i in range(count):
                timestamp = start_time + (i * interval)
                output_path = f"{output_dir}/thumb_{i+1:03d}_{int(timestamp)}s.jpg"
                
                result = await self.create_thumbnail(
                    input_path=input_path,
                    output_path=output_path,
                    timestamp=timestamp,
                    width=width,
                    height=height,
                    quality=quality
                )
                
                thumbnails.append({
                    'path': output_path,
                    'timestamp': timestamp,
                    'index': i + 1
                })
            
            return {
                'success': True,
                'thumbnails': thumbnails,
                'count': count,
                'total_duration': duration
            }
            
        except Exception as e:
            logger.error("Multiple thumbnails creation failed", error=str(e))
            raise VideoProcessingError(f"Multiple thumbnails creation failed: {e}")
    
    async def create_adaptive_stream(self, input_path: str, output_path: str,
                                   format_type: str = "hls", variants: List[Dict] = None,
                                   segment_duration: int = 6) -> Dict[str, Any]:
        """Create adaptive streaming formats (HLS/DASH) with multiple quality variants."""
        await self.initialize()
        
        try:
            # Default variants if none provided
            if variants is None:
                variants = [
                    {"resolution": "1920x1080", "bitrate": "5000k", "name": "1080p"},
                    {"resolution": "1280x720", "bitrate": "2500k", "name": "720p"},
                    {"resolution": "854x480", "bitrate": "1000k", "name": "480p"},
                    {"resolution": "640x360", "bitrate": "500k", "name": "360p"}
                ]
            
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Set output path based on format
            if format_type == "hls":
                output_file = f"{output_path}/playlist.m3u8"
            else:  # dash
                output_file = f"{output_path}/manifest.mpd"
            
            # Configure streaming options
            options = {
                'format': format_type
            }
            
            operations = [
                {
                    'type': 'streaming',
                    'params': {
                        'format': format_type,
                        'segment_time': segment_duration,
                        'variants': variants
                    }
                }
            ]
            
            # Add multi-variant encoding for adaptive streaming
            for i, variant in enumerate(variants):
                operations.append({
                    'type': 'transcode',
                    'params': {
                        'video_codec': 'h264',
                        'audio_codec': 'aac',
                        'video_bitrate': variant['bitrate'],
                        'width': int(variant['resolution'].split('x')[0]),
                        'height': int(variant['resolution'].split('x')[1]),
                        'preset': 'medium'
                    }
                })
            
            # Calculate timeout based on video duration and number of variants
            duration = await self.ffmpeg.get_file_duration(input_path)
            timeout = max(600, int(duration * len(variants) * 2))  # 2x realtime per variant
            
            logger.info(
                "Starting adaptive streaming creation",
                format=format_type,
                variants=len(variants),
                duration=duration,
                timeout=timeout
            )
            
            result = await self.ffmpeg.execute_command(
                input_path=input_path,
                output_path=output_file,
                options=options,
                operations=operations,
                timeout=timeout
            )
            
            return {
                'success': True,
                'output_path': output_path,
                'manifest_file': output_file,
                'format': format_type,
                'variants': variants,
                'segment_duration': segment_duration,
                'total_duration': duration
            }
            
        except Exception as e:
            logger.error("Adaptive streaming creation failed", error=str(e))
            raise VideoProcessingError(f"Adaptive streaming creation failed: {e}")
    
    async def analyze_quality(self, input_path: str, reference_path: str = None,
                            metrics: List[str] = None) -> Dict[str, Any]:
        """Analyze video quality using VMAF, PSNR, and SSIM metrics."""
        await self.initialize()
        
        try:
            if metrics is None:
                metrics = ['vmaf', 'psnr', 'ssim']
            
            analysis_results = {}
            
            # Create temporary files for analysis
            with tempfile.TemporaryDirectory() as temp_dir:
                for metric in metrics:
                    if metric.lower() == 'vmaf' and reference_path:
                        # VMAF requires a reference video
                        result = await self._analyze_vmaf(input_path, reference_path, temp_dir)
                        analysis_results['vmaf'] = result
                    elif metric.lower() == 'psnr' and reference_path:
                        # PSNR comparison with reference
                        result = await self._analyze_psnr(input_path, reference_path, temp_dir)
                        analysis_results['psnr'] = result
                    elif metric.lower() == 'ssim' and reference_path:
                        # SSIM comparison with reference
                        result = await self._analyze_ssim(input_path, reference_path, temp_dir)
                        analysis_results['ssim'] = result
                    else:
                        # Basic video quality metrics without reference
                        result = await self._analyze_basic_quality(input_path, temp_dir)
                        analysis_results['basic'] = result
            
            return {
                'success': True,
                'input_path': input_path,
                'reference_path': reference_path,
                'metrics': analysis_results,
                'analyzed_metrics': metrics
            }
            
        except Exception as e:
            logger.error("Quality analysis failed", error=str(e))
            raise VideoProcessingError(f"Quality analysis failed: {e}")
    
    async def _analyze_vmaf(self, input_path: str, reference_path: str, temp_dir: str) -> Dict[str, Any]:
        """Analyze VMAF score between input and reference video."""
        vmaf_log = f"{temp_dir}/vmaf.json"
        
        operations = [
            {
                'type': 'filter',
                'params': {
                    'vmaf': f'model_path=/usr/share/vmaf/vmaf_v0.6.1.pkl:log_path={vmaf_log}:log_fmt=json'
                }
            }
        ]
        
        # Use reference as second input
        cmd = ['ffmpeg', '-y', '-i', input_path, '-i', reference_path]
        cmd.extend(['-lavfi', f'[0:v][1:v]libvmaf=model_path=/usr/share/vmaf/vmaf_v0.6.1.pkl:log_path={vmaf_log}:log_fmt=json'])
        cmd.extend(['-f', 'null', '-'])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            
            # Read VMAF results
            if os.path.exists(vmaf_log):
                with open(vmaf_log, 'r') as f:
                    vmaf_data = json.load(f)
                
                return {
                    'mean_score': vmaf_data.get('pooled_metrics', {}).get('vmaf', {}).get('mean', 0),
                    'min_score': vmaf_data.get('pooled_metrics', {}).get('vmaf', {}).get('min', 0),
                    'max_score': vmaf_data.get('pooled_metrics', {}).get('vmaf', {}).get('max', 0),
                    'harmonic_mean': vmaf_data.get('pooled_metrics', {}).get('vmaf', {}).get('harmonic_mean', 0)
                }
            else:
                return {'error': 'VMAF analysis failed - no output generated'}
                
        except Exception as e:
            return {'error': f'VMAF analysis failed: {str(e)}'}
    
    async def _analyze_psnr(self, input_path: str, reference_path: str, temp_dir: str) -> Dict[str, Any]:
        """Analyze PSNR between input and reference video."""
        psnr_log = f"{temp_dir}/psnr.log"
        
        cmd = ['ffmpeg', '-y', '-i', input_path, '-i', reference_path]
        cmd.extend(['-lavfi', f'[0:v][1:v]psnr=stats_file={psnr_log}'])
        cmd.extend(['-f', 'null', '-'])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            
            # Parse PSNR results from stderr
            if os.path.exists(psnr_log):
                with open(psnr_log, 'r') as f:
                    psnr_lines = f.readlines()
                
                # Extract average PSNR values
                if psnr_lines:
                    last_line = psnr_lines[-1]
                    # Parse PSNR values from the summary line
                    psnr_values = {}
                    if 'average:' in last_line:
                        parts = last_line.split('average:')[1].split()
                        for part in parts:
                            if ':' in part and 'inf' not in part:
                                key, value = part.split(':')
                                try:
                                    psnr_values[key] = float(value)
                                except ValueError:
                                    continue
                    
                    return psnr_values
            
            return {'error': 'PSNR analysis failed - no output generated'}
            
        except Exception as e:
            return {'error': f'PSNR analysis failed: {str(e)}'}
    
    async def _analyze_ssim(self, input_path: str, reference_path: str, temp_dir: str) -> Dict[str, Any]:
        """Analyze SSIM between input and reference video."""
        cmd = ['ffmpeg', '-y', '-i', input_path, '-i', reference_path]
        cmd.extend(['-lavfi', '[0:v][1:v]ssim'])
        cmd.extend(['-f', 'null', '-'])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            # Parse SSIM from stderr
            stderr_text = stderr.decode('utf-8')
            ssim_values = {}
            
            for line in stderr_text.split('\n'):
                if 'SSIM' in line and 'All:' in line:
                    # Extract SSIM values
                    parts = line.split()
                    for part in parts:
                        if part.startswith('All:') or part.startswith('Y:') or part.startswith('U:') or part.startswith('V:'):
                            key, value = part.split(':')
                            try:
                                ssim_values[key.lower()] = float(value.split('(')[0])
                            except (ValueError, IndexError):
                                continue
            
            return ssim_values if ssim_values else {'error': 'SSIM analysis failed'}
            
        except Exception as e:
            return {'error': f'SSIM analysis failed: {str(e)}'}
    
    async def _analyze_basic_quality(self, input_path: str, temp_dir: str) -> Dict[str, Any]:
        """Analyze basic video quality metrics without reference."""
        try:
            # Get basic video information
            probe_info = await self.ffmpeg.probe_file(input_path)
            video_stream = next((s for s in probe_info.get('streams', []) 
                               if s.get('codec_type') == 'video'), {})
            
            # Calculate basic quality indicators
            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)
            bitrate = int(video_stream.get('bit_rate', 0))
            fps = self._parse_fps(video_stream.get('r_frame_rate', '0/1'))
            
            # Quality score based on resolution and bitrate
            pixel_count = width * height
            if pixel_count > 0:
                bits_per_pixel = bitrate / (pixel_count * fps) if fps > 0 else 0
            else:
                bits_per_pixel = 0
            
            return {
                'resolution': f"{width}x{height}",
                'bitrate': bitrate,
                'fps': fps,
                'bits_per_pixel': bits_per_pixel,
                'quality_score': min(100, max(0, bits_per_pixel * 50))  # Normalized quality score
            }
            
        except Exception as e:
            return {'error': f'Basic quality analysis failed: {str(e)}'}
    
    async def create_watermarked_video(self, input_path: str, output_path: str,
                                     watermark_path: str, position: str = "top-right",
                                     opacity: float = 0.7, scale: float = 0.1) -> Dict[str, Any]:
        """Create a watermarked video with enhanced positioning and scaling options."""
        await self.initialize()
        
        try:
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Position mappings
            position_map = {
                'top-left': '10:10',
                'top-right': 'W-w-10:10',
                'bottom-left': '10:H-h-10',
                'bottom-right': 'W-w-10:H-h-10',
                'center': '(W-w)/2:(H-h)/2'
            }
            
            overlay_position = position_map.get(position, 'W-w-10:10')
            
            # Create watermark overlay filter
            watermark_filter = f"movie={watermark_path}:loop=1,setpts=N/(FRAME_RATE*TB),scale=iw*{scale}:ih*{scale},format=rgba,colorchannelmixer=aa={opacity}[watermark];[in][watermark]overlay={overlay_position}[out]"
            
            operations = [
                {
                    'type': 'filter',  
                    'params': {
                        'complex_filter': watermark_filter
                    }  
                },
                {
                    'type': 'transcode',
                    'params': {
                        'video_codec': 'h264',
                        'audio_codec': 'copy',  # Copy audio without re-encoding
                        'preset': 'medium'
                    }
                }
            ]
            
            result = await self.ffmpeg.execute_command(
                input_path=input_path,
                output_path=output_path,
                options={},
                operations=operations,
                timeout=self._calculate_timeout(await self.ffmpeg.get_file_duration(input_path), operations)
            )
            
            return {
                'success': True,
                'output_path': output_path,
                'watermark_position': position,
                'watermark_opacity': opacity,
                'watermark_scale': scale
            }
            
        except Exception as e:
            logger.error("Watermark creation failed", error=str(e))
            raise VideoProcessingError(f"Watermark creation failed: {e}")