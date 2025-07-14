"""
Test helper functions
"""
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import MagicMock
from uuid import uuid4

from api.models.job import Job, JobStatus
from api.models.api_key import ApiKey, ApiKeyStatus


def assert_job_response(response_data: Dict[str, Any], expected_status: Optional[str] = None) -> None:
    """Assert that a response contains valid job data structure.
    
    Args:
        response_data: Response data to validate
        expected_status: Expected job status (optional)
    """
    required_fields = ["id", "status", "progress", "created_at", "stage"]
    
    for field in required_fields:
        assert field in response_data, f"Missing required field: {field}"
    
    # Validate field types
    assert isinstance(response_data["progress"], (int, float))
    assert 0 <= response_data["progress"] <= 100
    
    if expected_status:
        assert response_data["status"] == expected_status


def assert_error_response(response_data: Dict[str, Any], expected_code: Optional[str] = None) -> None:
    """Assert that a response contains valid error structure.
    
    Args:
        response_data: Response data to validate
        expected_code: Expected error code (optional)
    """
    assert "error" in response_data, "Response should contain error field"
    
    error = response_data["error"]
    required_fields = ["code", "message", "type"]
    
    for field in required_fields:
        assert field in error, f"Missing required error field: {field}"
    
    if expected_code:
        assert error["code"] == expected_code


def create_mock_job(**kwargs) -> MagicMock:
    """Create a mock job object for testing.
    
    Args:
        **kwargs: Job field overrides
        
    Returns:
        Mock job object
    """
    defaults = {
        "id": uuid4(),
        "status": JobStatus.QUEUED,
        "input_path": "input/test.mp4",
        "output_path": "output/test.mp4",
        "progress": 0.0,
        "stage": "queued",
        "api_key": "rdf_testkey123",
        "created_at": "2024-07-10T10:00:00Z",
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "worker_id": None,
        "processing_time": None,
    }
    
    # Update defaults with provided kwargs
    defaults.update(kwargs)
    
    mock_job = MagicMock(spec=Job)
    for key, value in defaults.items():
        setattr(mock_job, key, value)
    
    return mock_job


def create_mock_api_key(**kwargs) -> MagicMock:
    """Create a mock API key object for testing.
    
    Args:
        **kwargs: API key field overrides
        
    Returns:
        Mock API key object
    """
    defaults = {
        "id": uuid4(),
        "name": "Test API Key",
        "key_hash": "test_hash_12345",
        "prefix": "rdf_test",
        "status": ApiKeyStatus.ACTIVE,
        "role": "user",
        "max_concurrent_jobs": 5,
        "monthly_quota_minutes": 1000,
        "total_jobs_created": 0,
        "total_minutes_processed": 0,
        "last_used_at": None,
        "created_at": "2024-07-10T10:00:00Z",
        "expires_at": None,
        "owner_name": "Test User",
    }
    
    # Update defaults with provided kwargs
    defaults.update(kwargs)
    
    mock_api_key = MagicMock(spec=ApiKey)
    for key, value in defaults.items():
        setattr(mock_api_key, key, value)
    
    # Add method mocks
    mock_api_key.is_valid.return_value = defaults["status"] == ApiKeyStatus.ACTIVE
    mock_api_key.is_expired.return_value = False
    mock_api_key.update_last_used = MagicMock()
    
    return mock_api_key


def create_test_video_file(directory: Optional[Path] = None) -> Path:
    """Create a test video file for testing.
    
    Args:
        directory: Directory to create file in (uses temp dir if None)
        
    Returns:
        Path to created test file
    """
    if directory is None:
        directory = Path(tempfile.gettempdir())
    
    video_file = directory / "test_video.mp4"
    
    # Create a minimal MP4 file with basic headers
    # This is just enough to be recognized as an MP4 file by basic checks
    mp4_header = (
        b'\x00\x00\x00\x20'  # Box size (32 bytes)
        b'ftyp'              # Box type (file type)
        b'mp41'              # Major brand
        b'\x00\x00\x00\x00'  # Minor version
        b'mp41'              # Compatible brand 1
        b'isom'              # Compatible brand 2
        b'\x00\x00\x00\x08'  # Another box size
        b'free'              # Free space box
    )
    
    video_file.write_bytes(mp4_header + b'\x00' * 1000)  # Add some padding
    
    return video_file


def create_test_audio_file(directory: Optional[Path] = None) -> Path:
    """Create a test audio file for testing.
    
    Args:
        directory: Directory to create file in (uses temp dir if None)
        
    Returns:
        Path to created test file
    """
    if directory is None:
        directory = Path(tempfile.gettempdir())
    
    audio_file = directory / "test_audio.mp3"
    
    # Create a minimal MP3 file with basic headers
    mp3_header = (
        b'\xFF\xFB'          # MP3 sync word and header
        b'\x90\x00'          # Header continuation
        b'\x00' * 32         # Empty frame data
    )
    
    audio_file.write_bytes(mp3_header + b'\x00' * 1000)  # Add some padding
    
    return audio_file


def create_test_image_file(directory: Optional[Path] = None) -> Path:
    """Create a test image file for testing.
    
    Args:
        directory: Directory to create file in (uses temp dir if None)
        
    Returns:
        Path to created test file
    """
    if directory is None:
        directory = Path(tempfile.gettempdir())
    
    image_file = directory / "test_image.jpg"
    
    # Create a minimal JPEG file with basic headers
    jpeg_header = (
        b'\xFF\xD8'          # JPEG SOI (Start of Image)
        b'\xFF\xE0'          # JFIF APP0 marker
        b'\x00\x10'          # Length
        b'JFIF\x00'          # JFIF identifier
        b'\x01\x01'          # Version
        b'\x00'              # Units
        b'\x00\x01'          # X density
        b'\x00\x01'          # Y density
        b'\x00\x00'          # Thumbnail size
        b'\xFF\xD9'          # JPEG EOI (End of Image)
    )
    
    image_file.write_bytes(jpeg_header)
    
    return image_file


def validate_api_response_structure(response_data: Dict[str, Any], schema: Dict[str, type]) -> None:
    """Validate that an API response matches the expected schema.
    
    Args:
        response_data: Response data to validate
        schema: Expected schema as field_name -> expected_type mapping
    """
    for field_name, expected_type in schema.items():
        assert field_name in response_data, f"Missing required field: {field_name}"
        
        field_value = response_data[field_name]
        if field_value is not None:  # Allow None values
            assert isinstance(field_value, expected_type), \
                f"Field {field_name} should be {expected_type}, got {type(field_value)}"


def create_test_conversion_request(
    input_format: str = "mp4",
    output_format: str = "mp4",
    **kwargs
) -> Dict[str, Any]:
    """Create a test conversion request.
    
    Args:
        input_format: Input file format
        output_format: Output file format
        **kwargs: Additional request parameters
        
    Returns:
        Conversion request dictionary
    """
    defaults = {
        "input": {
            "path": f"input/test.{input_format}",
            "storage": "local"
        },
        "output": {
            "path": f"output/converted.{output_format}",
            "storage": "local"
        },
        "operations": [
            {
                "type": "convert",
                "format": output_format,
            }
        ],
        "options": {
            "quality": "medium"
        },
        "priority": "normal"
    }
    
    # Update defaults with provided kwargs
    defaults.update(kwargs)
    
    return defaults


def assert_pagination_response(response_data: Dict[str, Any]) -> None:
    """Assert that a response contains valid pagination structure.
    
    Args:
        response_data: Response data to validate
    """
    pagination_fields = ["page", "per_page", "total", "has_next", "has_prev"]
    
    for field in pagination_fields:
        assert field in response_data, f"Missing pagination field: {field}"
    
    # Validate field types
    assert isinstance(response_data["page"], int)
    assert isinstance(response_data["per_page"], int)
    assert isinstance(response_data["total"], int)
    assert isinstance(response_data["has_next"], bool)
    assert isinstance(response_data["has_prev"], bool)
    
    # Validate logical constraints
    assert response_data["page"] >= 1
    assert response_data["per_page"] >= 1
    assert response_data["total"] >= 0


def create_mock_file_upload(filename: str, content: bytes = b"test content") -> Dict[str, Any]:
    """Create a mock file upload for testing.
    
    Args:
        filename: Name of the uploaded file
        content: File content bytes
        
    Returns:
        Mock file upload data
    """
    return {
        "filename": filename,
        "content": content,
        "content_type": "application/octet-stream",
        "size": len(content),
    }


def assert_http_error(response_data: Dict[str, Any], expected_status: int) -> None:
    """Assert that a response contains the expected HTTP error.
    
    Args:
        response_data: Response data to validate
        expected_status: Expected HTTP status code
    """
    assert "error" in response_data
    error = response_data["error"]
    
    assert "message" in error
    assert "code" in error
    
    # For HTTP errors, the code might be the status code
    if "status_code" in error:
        assert error["status_code"] == expected_status


def generate_test_jwt_token(payload: Dict[str, Any]) -> str:
    """Generate a test JWT token for testing.
    
    Args:
        payload: JWT payload
        
    Returns:
        Test JWT token string
    """
    # This is a mock implementation for testing
    # In real implementation, you'd use a proper JWT library
    import base64
    import json
    
    header = {"alg": "HS256", "typ": "JWT"}
    
    header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = "test_signature"
    
    return f"{header_encoded}.{payload_encoded}.{signature}"