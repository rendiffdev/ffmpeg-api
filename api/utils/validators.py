"""
Input validation utilities
"""
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse

from api.services.storage import StorageService


# Allowed file extensions
ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", 
    ".mpeg", ".mpg", ".m4v", ".3gp", ".3g2", ".mxf", ".ts", ".vob"
}

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", 
    ".opus", ".ape", ".alac", ".aiff", ".dts", ".ac3"
}

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg"
}

# Regex patterns
PATH_REGEX = re.compile(r'^[a-zA-Z0-9\-_./]+$')
CODEC_REGEX = re.compile(r'^[a-zA-Z0-9\-_]+$')


async def validate_input_path(
    path: str, 
    storage_service: StorageService
) -> Tuple[str, str]:
    """
    Validate input file path.
    Returns: (backend_name, validated_path)
    """
    if not path:
        raise ValueError("Input path cannot be empty")
    
    # Parse storage URI
    backend_name, file_path = storage_service.parse_uri(path)
    
    # Check if backend exists
    if backend_name not in storage_service.backends:
        raise ValueError(f"Unknown storage backend: {backend_name}")
    
    # Validate file extension
    file_ext = Path(file_path).suffix.lower()
    if file_ext not in (ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS):
        raise ValueError(f"Unsupported input file type: {file_ext}")
    
    # Check if file exists
    backend = storage_service.backends[backend_name]
    if not await backend.exists(file_path):
        raise ValueError(f"Input file not found: {path}")
    
    return backend_name, file_path


async def validate_output_path(
    path: str,
    storage_service: StorageService
) -> Tuple[str, str]:
    """
    Validate output file path.
    Returns: (backend_name, validated_path)
    """
    if not path:
        raise ValueError("Output path cannot be empty")
    
    # Parse storage URI
    backend_name, file_path = storage_service.parse_uri(path)
    
    # Check if backend exists
    if backend_name not in storage_service.backends:
        raise ValueError(f"Unknown storage backend: {backend_name}")
    
    # Check if backend allows output
    storage_config = storage_service.config
    output_backends = storage_config.get("policies", {}).get("output_backends", [])
    if output_backends and backend_name not in output_backends:
        raise ValueError(f"Backend '{backend_name}' not allowed for output")
    
    # Validate path format
    if not PATH_REGEX.match(file_path):
        raise ValueError(f"Invalid output path format: {file_path}")
    
    # Ensure directory exists
    backend = storage_service.backends[backend_name]
    output_dir = str(Path(file_path).parent)
    await backend.ensure_dir(output_dir)
    
    return backend_name, file_path


def validate_operations(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and normalize operations list."""
    validated = []
    
    for op in operations:
        if "type" not in op:
            raise ValueError("Operation missing 'type' field")
        
        op_type = op["type"]
        
        if op_type == "trim":
            validated_op = validate_trim_operation(op)
        elif op_type == "watermark":
            validated_op = validate_watermark_operation(op)
        elif op_type == "filter":
            validated_op = validate_filter_operation(op)
        elif op_type == "stream":
            validated_op = validate_stream_operation(op)
        else:
            raise ValueError(f"Unknown operation type: {op_type}")
        
        validated.append(validated_op)
    
    return validated


def validate_trim_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate trim operation."""
    validated = {"type": "trim"}
    
    # Validate start time
    if "start" in op:
        start = op["start"]
        if isinstance(start, (int, float)):
            validated["start"] = float(start)
        elif isinstance(start, str):
            validated["start"] = parse_time_string(start)
        else:
            raise ValueError("Invalid start time format")
    
    # Validate duration or end time
    if "duration" in op:
        duration = op["duration"]
        if isinstance(duration, (int, float)):
            validated["duration"] = float(duration)
        else:
            raise ValueError("Invalid duration format")
    elif "end" in op:
        end = op["end"]
        if isinstance(end, (int, float)):
            validated["end"] = float(end)
        elif isinstance(end, str):
            validated["end"] = parse_time_string(end)
        else:
            raise ValueError("Invalid end time format")
    
    return validated


def validate_watermark_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate watermark operation."""
    if "image" not in op:
        raise ValueError("Watermark operation requires 'image' field")
    
    return {
        "type": "watermark",
        "image": op["image"],
        "position": op.get("position", "bottom-right"),
        "opacity": float(op.get("opacity", 0.8)),
        "scale": float(op.get("scale", 0.1)),
    }


def validate_filter_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate filter operation."""
    if "name" not in op:
        raise ValueError("Filter operation requires 'name' field")
    
    allowed_filters = {
        "denoise", "deinterlace", "stabilize", "sharpen", "blur",
        "brightness", "contrast", "saturation", "hue", "eq"
    }
    
    filter_name = op["name"]
    if filter_name not in allowed_filters:
        raise ValueError(f"Unknown filter: {filter_name}")
    
    return {
        "type": "filter",
        "name": filter_name,
        "params": op.get("params", {}),
    }


def validate_stream_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate streaming operation."""
    stream_format = op.get("format", "hls").lower()
    if stream_format not in ["hls", "dash"]:
        raise ValueError(f"Unknown streaming format: {stream_format}")
    
    return {
        "type": "stream",
        "format": stream_format,
        "variants": op.get("variants", []),
        "segment_duration": int(op.get("segment_duration", 6)),
    }


def parse_time_string(time_str: str) -> float:
    """Parse time string in format HH:MM:SS.ms to seconds."""
    parts = time_str.split(":")
    if len(parts) == 1:
        return float(parts[0])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    else:
        raise ValueError(f"Invalid time format: {time_str}")