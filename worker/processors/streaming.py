"""
Streaming format generation for HLS and DASH.
"""
import asyncio
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import structlog

from worker.utils.ffmpeg import FFmpegWrapper, FFmpegError
from worker.utils.progress import ProgressTracker

logger = structlog.get_logger()


class StreamingError(Exception):
    """Base exception for streaming operations."""
    pass


class StreamingProcessor:
    """Handles creation of streaming formats (HLS/DASH)."""
    
    def __init__(self):
        self.ffmpeg = FFmpegWrapper()
        self.initialized = False
        
        # Default streaming configurations
        self.hls_presets = {
            'adaptive': [
                {'resolution': '1920x1080', 'bitrate': '5000k', 'name': '1080p'},
                {'resolution': '1280x720', 'bitrate': '3000k', 'name': '720p'},
                {'resolution': '854x480', 'bitrate': '1500k', 'name': '480p'},
                {'resolution': '640x360', 'bitrate': '800k', 'name': '360p'}
            ],
            'single': [
                {'resolution': '1280x720', 'bitrate': '3000k', 'name': '720p'}
            ]
        }
    
    async def initialize(self):
        """Initialize the streaming processor."""
        if not self.initialized:
            await self.ffmpeg.initialize()
            self.initialized = True
            logger.info("StreamingProcessor initialized")
    
    async def create_hls_stream(self, input_path: str, output_dir: str,
                               options: Dict[str, Any], 
                               progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Create HLS (HTTP Live Streaming) format.
        
        Args:
            input_path: Input video file path
            output_dir: Output directory for HLS files
            options: HLS generation options
            progress_callback: Progress callback function
            
        Returns:
            Dict containing HLS generation results
        """
        await self.initialize()
        
        try:
            logger.info("Starting HLS stream creation", input_path=input_path, output_dir=output_dir)
            
            # Parse HLS options
            hls_options = self._parse_hls_options(options)
            
            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Generate HLS variants
            if hls_options['adaptive']:
                return await self._create_adaptive_hls(input_path, output_dir, hls_options, progress_callback)
            else:
                return await self._create_single_hls(input_path, output_dir, hls_options, progress_callback)
                
        except Exception as e:
            logger.error("HLS creation failed", error=str(e))
            raise StreamingError(f"HLS creation failed: {e}")
    
    async def create_dash_stream(self, input_path: str, output_dir: str,
                                options: Dict[str, Any],
                                progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Create DASH (Dynamic Adaptive Streaming over HTTP) format.
        
        Args:
            input_path: Input video file path
            output_dir: Output directory for DASH files
            options: DASH generation options
            progress_callback: Progress callback function
            
        Returns:
            Dict containing DASH generation results
        """
        await self.initialize()
        
        try:
            logger.info("Starting DASH stream creation", input_path=input_path, output_dir=output_dir)
            
            # Parse DASH options
            dash_options = self._parse_dash_options(options)
            
            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Generate DASH manifest
            return await self._create_dash_manifest(input_path, output_dir, dash_options, progress_callback)
                
        except Exception as e:
            logger.error("DASH creation failed", error=str(e))
            raise StreamingError(f"DASH creation failed: {e}")
    
    def _parse_hls_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Parse HLS-specific options."""
        return {
            'adaptive': options.get('adaptive', True),
            'segment_duration': options.get('segment_duration', 6),
            'playlist_type': options.get('playlist_type', 'vod'),
            'variants': options.get('variants', self.hls_presets['adaptive' if options.get('adaptive', True) else 'single']),
            'encryption': options.get('encryption', False),
            'start_number': options.get('start_number', 0)
        }
    
    def _parse_dash_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Parse DASH-specific options."""
        return {
            'segment_duration': options.get('segment_duration', 4),
            'adaptation_sets': options.get('adaptation_sets', ['video', 'audio']),
            'variants': options.get('variants', self.hls_presets['adaptive']),
            'single_file': options.get('single_file', False),
            'init_segment': options.get('init_segment', True)
        }
    
    async def _create_adaptive_hls(self, input_path: str, output_dir: str,
                                  options: Dict[str, Any], 
                                  progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Create adaptive bitrate HLS stream with multiple variants."""
        variants = options['variants']
        segment_duration = options['segment_duration']
        
        # Create variant directories
        variant_info = []
        for i, variant in enumerate(variants):
            variant_dir = Path(output_dir) / variant['name']
            variant_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate variant playlist
            playlist_path = variant_dir / "playlist.m3u8"
            segments_pattern = variant_dir / "segment_%03d.ts"
            
            # Build FFmpeg command for this variant
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-b:v', variant['bitrate'],
                '-s', variant['resolution'],
                '-preset', 'medium',
                '-g', str(int(30 * segment_duration)),  # Keyframe interval
                '-sc_threshold', '0',  # Disable scene change detection
                '-f', 'hls',
                '-hls_time', str(segment_duration),
                '-hls_playlist_type', options['playlist_type'],
                '-hls_segment_filename', str(segments_pattern),
                str(playlist_path)
            ]
            
            logger.info(f"Creating HLS variant: {variant['name']}", command=' '.join(cmd))
            
            # Execute FFmpeg command
            result = await self._execute_ffmpeg_command(cmd, progress_callback, len(variants), i)
            
            variant_info.append({
                'name': variant['name'],
                'resolution': variant['resolution'],
                'bitrate': variant['bitrate'],
                'playlist_path': str(playlist_path),
                'bandwidth': self._calculate_bandwidth(variant['bitrate'])
            })
        
        # Create master playlist
        master_playlist_path = Path(output_dir) / "master.m3u8"
        await self._create_master_playlist(master_playlist_path, variant_info)
        
        return {
            'type': 'hls_adaptive',
            'master_playlist': str(master_playlist_path),
            'variants': variant_info,
            'segment_duration': segment_duration,
            'total_variants': len(variants)
        }
    
    async def _create_single_hls(self, input_path: str, output_dir: str,
                               options: Dict[str, Any],
                               progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Create single bitrate HLS stream."""
        variant = options['variants'][0]
        segment_duration = options['segment_duration']
        
        # Output files
        playlist_path = Path(output_dir) / "playlist.m3u8"
        segments_pattern = Path(output_dir) / "segment_%03d.ts"
        
        # Build FFmpeg command
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:v', variant['bitrate'],
            '-s', variant['resolution'],
            '-preset', 'medium',
            '-f', 'hls',
            '-hls_time', str(segment_duration),
            '-hls_playlist_type', options['playlist_type'],
            '-hls_segment_filename', str(segments_pattern),
            str(playlist_path)
        ]
        
        logger.info("Creating single HLS stream", command=' '.join(cmd))
        
        # Execute FFmpeg command
        await self._execute_ffmpeg_command(cmd, progress_callback, 1, 0)
        
        return {
            'type': 'hls_single',
            'playlist': str(playlist_path),
            'variant': variant,
            'segment_duration': segment_duration
        }
    
    async def _create_dash_manifest(self, input_path: str, output_dir: str,
                                   options: Dict[str, Any],
                                   progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Create DASH manifest and segments."""
        variants = options['variants']
        segment_duration = options['segment_duration']
        
        # Create adaptation sets for video and audio
        video_adaptations = []
        for i, variant in enumerate(variants):
            representation_id = f"video_{variant['name']}"
            
            # Create representation directory
            repr_dir = Path(output_dir) / representation_id
            repr_dir.mkdir(parents=True, exist_ok=True)
            
            # Build FFmpeg command for DASH
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-b:v', variant['bitrate'],
                '-s', variant['resolution'],
                '-preset', 'medium',
                '-f', 'dash',
                '-seg_duration', str(segment_duration),
                '-adaptation_sets', 'id=0,streams=v id=1,streams=a',
                '-use_template', '1',
                '-use_timeline', '1',
                str(Path(output_dir) / 'manifest.mpd')
            ]
            
            logger.info(f"Creating DASH representation: {representation_id}", command=' '.join(cmd))
            
            # Execute FFmpeg command
            await self._execute_ffmpeg_command(cmd, progress_callback, len(variants), i)
            
            video_adaptations.append({
                'id': representation_id,
                'resolution': variant['resolution'],
                'bitrate': variant['bitrate'],
                'bandwidth': self._calculate_bandwidth(variant['bitrate'])
            })
        
        manifest_path = Path(output_dir) / 'manifest.mpd'
        
        return {
            'type': 'dash',
            'manifest': str(manifest_path),
            'video_adaptations': video_adaptations,
            'segment_duration': segment_duration
        }
    
    async def _execute_ffmpeg_command(self, cmd: List[str], progress_callback: Optional[callable],
                                    total_variants: int, current_variant: int):
        """Execute FFmpeg command with progress tracking."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor progress if callback provided
            if progress_callback:
                async def monitor_progress():
                    if process.stderr:
                        async for line in process.stderr:
                            line_str = line.decode('utf-8', errors='ignore').strip()
                            # Parse FFmpeg progress and adjust for multiple variants
                            # This is a simplified progress calculation
                            base_progress = (current_variant / total_variants) * 100
                            variant_progress = 100 / total_variants
                            await progress_callback({
                                'percentage': base_progress + (variant_progress * 0.5)  # Estimated
                            })
                
                # Start progress monitoring
                progress_task = asyncio.create_task(monitor_progress())
            
            # Wait for process completion
            stdout, stderr = await process.communicate()
            
            if progress_callback:
                await progress_task
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                raise StreamingError(f"FFmpeg command failed: {error_msg}")
                
        except Exception as e:
            raise StreamingError(f"FFmpeg execution failed: {e}")
    
    async def _create_master_playlist(self, playlist_path: Path, variant_info: List[Dict[str, Any]]):
        """Create HLS master playlist file."""
        playlist_content = ["#EXTM3U", "#EXT-X-VERSION:6"]
        
        for variant in variant_info:
            # Add stream info
            resolution = variant['resolution']
            bandwidth = variant['bandwidth']
            name = variant['name']
            
            playlist_content.append(
                f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={resolution},NAME=\"{name}\""
            )
            playlist_content.append(f"{name}/playlist.m3u8")
        
        # Write master playlist
        with open(playlist_path, 'w') as f:
            f.write('\n'.join(playlist_content))
        
        logger.info("Master playlist created", path=str(playlist_path))
    
    def _calculate_bandwidth(self, bitrate_str: str) -> int:
        """Calculate bandwidth from bitrate string (e.g., '3000k' -> 3000000)."""
        try:
            if bitrate_str.endswith('k'):
                return int(bitrate_str[:-1]) * 1000
            elif bitrate_str.endswith('M'):
                return int(bitrate_str[:-1]) * 1000000
            else:
                return int(bitrate_str)
        except ValueError:
            return 3000000  # Default bandwidth
    
    async def create_streaming_package(self, input_path: str, output_dir: str,
                                     format_type: str, options: Dict[str, Any],
                                     progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Create complete streaming package (HLS or DASH).
        
        Args:
            input_path: Input video file
            output_dir: Output directory
            format_type: 'hls' or 'dash'
            options: Streaming options
            progress_callback: Progress callback
            
        Returns:
            Dict containing streaming package information
        """
        await self.initialize()
        
        try:
            if format_type.lower() == 'hls':
                return await self.create_hls_stream(input_path, output_dir, options, progress_callback)
            elif format_type.lower() == 'dash':
                return await self.create_dash_stream(input_path, output_dir, options, progress_callback)
            else:
                raise StreamingError(f"Unsupported streaming format: {format_type}")
                
        except Exception as e:
            logger.error("Streaming package creation failed", error=str(e))
            raise StreamingError(f"Streaming package creation failed: {e}")
    
    async def validate_streaming_output(self, output_dir: str, format_type: str) -> Dict[str, Any]:
        """Validate generated streaming files."""
        try:
            validation_results = {
                'valid': False,
                'files_found': [],
                'missing_files': [],
                'errors': []
            }
            
            output_path = Path(output_dir)
            
            if format_type.lower() == 'hls':
                # Check for master playlist or single playlist
                master_playlist = output_path / "master.m3u8"
                single_playlist = output_path / "playlist.m3u8"
                
                if master_playlist.exists():
                    validation_results['files_found'].append(str(master_playlist))
                    # Check variant playlists
                    with open(master_playlist, 'r') as f:
                        content = f.read()
                        for line in content.split('\n'):
                            if line.endswith('.m3u8') and not line.startswith('#'):
                                variant_playlist = output_path / line
                                if variant_playlist.exists():
                                    validation_results['files_found'].append(str(variant_playlist))
                                else:
                                    validation_results['missing_files'].append(str(variant_playlist))
                                    
                elif single_playlist.exists():
                    validation_results['files_found'].append(str(single_playlist))
                else:
                    validation_results['errors'].append("No HLS playlist found")
                
                # Check for segment files
                segment_files = list(output_path.rglob("*.ts"))
                validation_results['files_found'].extend([str(f) for f in segment_files])
                
            elif format_type.lower() == 'dash':
                # Check for DASH manifest
                manifest = output_path / "manifest.mpd"
                if manifest.exists():
                    validation_results['files_found'].append(str(manifest))
                else:
                    validation_results['errors'].append("DASH manifest not found")
                
                # Check for segment files
                segment_files = list(output_path.rglob("*.m4s"))
                validation_results['files_found'].extend([str(f) for f in segment_files])
            
            validation_results['valid'] = len(validation_results['errors']) == 0
            
            return validation_results
            
        except Exception as e:
            return {
                'valid': False,
                'files_found': [],
                'missing_files': [],
                'errors': [f"Validation failed: {e}"]
            }