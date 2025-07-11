"""
Video processing module with production-grade FFmpeg integration.
"""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import structlog

from worker.base import BaseProcessor, ProcessingError
from worker.utils.ffmpeg import FFmpegWrapper, FFmpegError
from worker.utils.progress import ProgressTracker

logger = structlog.get_logger()


class VideoProcessingError(ProcessingError):
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


class VideoProcessor(BaseProcessor):
    """Handles video processing operations with FFmpeg."""
    
    def __init__(self):
        super().__init__()
        self.ffmpeg = FFmpegWrapper()
        self.supported_input_formats = {
            'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm', 'm4v', 
            '3gp', 'ts', 'mts', 'm2ts', 'vob', 'mpg', 'mpeg', 'ogv'
        }
        self.supported_output_formats = {
            'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'm4v', 'ts', 'mpg'
        }
    
    def get_supported_formats(self) -> Dict[str, list]:
        """Get supported input and output formats."""
        return {
            "input": list(self.supported_input_formats),
            "output": list(self.supported_output_formats)
        }
        
    async def initialize(self):
        """Initialize the video processor."""
        if not self.initialized:
            await self.ffmpeg.initialize()
            self.initialized = True
            self.logger.info("VideoProcessor initialized")
    
    async def get_video_info(self, input_path: str) -> Dict[str, Any]:
        """Get video file information."""
        try:
            return await self.ffmpeg.probe_file(input_path)
        except FFmpegError as e:
            raise VideoProcessingError(f"Failed to get video info: {e}")
    
    async def validate_input(self, input_path: str) -> bool:
        """Validate input file - override base method."""
        await super().validate_input(input_path)  # Basic validation
        
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
        
        return True
    
    async def validate_output(self, output_path: str) -> bool:
        """Validate output path - override base method."""
        await super().validate_output(output_path)  # Basic validation
        
        file_ext = Path(output_path).suffix.lower().lstrip('.')
        if file_ext not in self.supported_output_formats:
            raise UnsupportedFormatError(f"Unsupported output format: {file_ext}")
        
        return True
    
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
            await self.validate_input(input_path)
            
            # Validate operations
            if not self.ffmpeg.validate_operations(operations):
                raise VideoProcessingError("Invalid operations provided")
            
            # Validate output format
            await self.validate_output(output_path)
            
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
                             timestamp: float = 10.0, width: int = 320, height: int = 240) -> Dict[str, Any]:
        """Create a thumbnail image from video at specified timestamp."""
        await self.initialize()
        
        try:
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
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
                        'video_codec': 'mjpeg'
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
                'dimensions': f"{width}x{height}"
            }
            
        except Exception as e:
            logger.error("Thumbnail creation failed", error=str(e))
            raise VideoProcessingError(f"Thumbnail creation failed: {e}")