"""
Mock FFmpeg wrapper for testing
"""
import asyncio
from typing import Dict, Any, Optional, Callable
from unittest.mock import AsyncMock


class MockFFmpegWrapper:
    """Mock FFmpeg wrapper for testing purposes."""
    
    def __init__(self):
        self.initialized = False
        self.command_history = []
    
    async def initialize(self):
        """Mock initialization."""
        self.initialized = True
    
    async def probe_file(self, file_path: str) -> Dict[str, Any]:
        """Mock file probing."""
        return {
            "format": {
                "filename": file_path,
                "duration": "10.0",
                "size": "1000000",
                "format_name": "mp4"
            },
            "streams": [
                {
                    "index": 0,
                    "codec_name": "h264",
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "duration": "10.0",
                    "bit_rate": "5000000"
                },
                {
                    "index": 1,
                    "codec_name": "aac",
                    "codec_type": "audio",
                    "sample_rate": "48000",
                    "channels": 2,
                    "duration": "10.0",
                    "bit_rate": "128000"
                }
            ]
        }
    
    async def get_file_duration(self, file_path: str) -> float:
        """Mock duration retrieval."""
        return 10.0
    
    def validate_operations(self, operations: list) -> bool:
        """Mock operation validation."""
        return True
    
    async def execute_command(
        self,
        input_path: str,
        output_path: str,
        options: Dict[str, Any],
        operations: list,
        progress_callback: Optional[Callable] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock command execution."""
        # Record the command for testing
        command_info = {
            "input_path": input_path,
            "output_path": output_path,
            "options": options,
            "operations": operations,
            "timeout": timeout
        }
        self.command_history.append(command_info)
        
        # Simulate progress updates
        if progress_callback:
            progress_steps = [0, 25, 50, 75, 100]
            for progress in progress_steps:
                await progress_callback({
                    "percentage": progress,
                    "frame": progress * 10,
                    "fps": 30.0,
                    "speed": 1.0,
                    "bitrate": 5000.0,
                    "time": f"00:00:{progress//10:02d}"
                })
                # Small delay to simulate processing
                await asyncio.sleep(0.01)
        
        # Return mock results
        return {
            "success": True,
            "command": f"ffmpeg -i {input_path} {output_path}",
            "processing_stats": {
                "frames_processed": 300,
                "total_time": 2.5,
                "average_fps": 120.0
            },
            "metrics": {
                "vmaf": 95.5,
                "psnr": 40.2,
                "ssim": 0.98
            }
        }
    
    def get_last_command(self) -> Optional[Dict[str, Any]]:
        """Get the last executed command for testing."""
        return self.command_history[-1] if self.command_history else None
    
    def clear_history(self):
        """Clear command history."""
        self.command_history.clear()


class MockFFmpegError(Exception):
    """Mock FFmpeg error for testing."""
    pass