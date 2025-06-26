"""
Health check endpoints
"""
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from api.config import settings
from api.dependencies import get_db
from api.services.queue import QueueService
from api.services.storage import StorageService

logger = structlog.get_logger()
router = APIRouter()

queue_service = QueueService()
storage_service = StorageService()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
    }


@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Detailed health check with component status.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "components": {},
    }
    
    # Check database
    try:
        result = await db.execute(text("SELECT 1"))
        health_status["components"]["database"] = {
            "status": "healthy",
            "type": "postgresql",
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
    
    # Check queue
    try:
        queue_health = await queue_service.health_check()
        health_status["components"]["queue"] = queue_health
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["queue"] = {
            "status": "unhealthy",
            "error": str(e),
        }
    
    # Check storage backends
    try:
        storage_health = await storage_service.health_check()
        health_status["components"]["storage"] = storage_health
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["storage"] = {
            "status": "unhealthy",
            "error": str(e),
        }
    
    # Check FFmpeg
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            health_status["components"]["ffmpeg"] = {
                "status": "healthy",
                "version": version_line,
            }
        else:
            raise Exception("FFmpeg not working")
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["ffmpeg"] = {
            "status": "unhealthy",
            "error": str(e),
        }
    
    return health_status


@router.get("/capabilities")
async def get_capabilities() -> Dict[str, Any]:
    """
    Get system capabilities and supported formats.
    """
    return {
        "version": settings.VERSION,
        "features": {
            "api_version": "v1",
            "max_file_size": settings.MAX_UPLOAD_SIZE,
            "max_job_duration": settings.MAX_JOB_DURATION,
            "concurrent_jobs": settings.MAX_CONCURRENT_JOBS_PER_KEY,
        },
        "formats": {
            "input": {
                "video": [
                    "mp4", "avi", "mov", "mkv", "webm", "flv", "wmv",
                    "mpeg", "mpg", "m4v", "3gp", "3g2", "mxf", "ts", "vob"
                ],
                "audio": [
                    "mp3", "wav", "flac", "aac", "ogg", "wma", "m4a",
                    "opus", "ape", "alac", "aiff", "dts", "ac3"
                ],
            },
            "output": {
                "containers": ["mp4", "webm", "mkv", "mov", "hls", "dash"],
                "video_codecs": ["h264", "h265", "vp9", "av1", "prores"],
                "audio_codecs": ["aac", "mp3", "opus", "vorbis", "flac"],
            },
        },
        "operations": [
            "convert", "transcode", "resize", "trim", "concat",
            "watermark", "filter", "analyze", "stream"
        ],
        "filters": [
            "denoise", "deinterlace", "stabilize", "sharpen", "blur",
            "brightness", "contrast", "saturation", "hue", "eq"
        ],
        "analysis": {
            "metrics": ["vmaf", "psnr", "ssim"],
            "probing": ["format", "streams", "metadata"],
        },
        "storage_backends": list(storage_service.backends.keys()),
        "hardware_acceleration": {
            "available": await check_hardware_acceleration(),
            "types": ["nvidia", "vaapi", "qsv", "videotoolbox"],
        },
    }


async def check_hardware_acceleration() -> list:
    """Check available hardware acceleration."""
    available = []
    
    # Check NVIDIA
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            available.append("nvidia")
    except:
        pass
    
    # Check VAAPI (Linux)
    import os
    if os.path.exists("/dev/dri/renderD128"):
        available.append("vaapi")
    
    return available