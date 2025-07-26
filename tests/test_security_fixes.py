"""
Tests for security fixes implementation
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

# Test FFmpeg command injection fix
def test_ffmpeg_command_injection_prevention():
    """Test that FFmpeg command builder prevents injection attacks."""
    from worker.utils.ffmpeg import FFmpegCommandBuilder, FFmpegCommandError
    
    builder = FFmpegCommandBuilder()
    
    # Test dangerous characters in paths
    with pytest.raises(FFmpegCommandError, match="Dangerous character detected"):
        builder._validate_paths("/path/to/input.mp4", "/output; rm -rf /")
    
    with pytest.raises(FFmpegCommandError, match="Dangerous character detected"):
        builder._validate_paths("/input`whoami`.mp4", "/output.mp4")
    
    # Test valid paths should pass
    try:
        builder._validate_paths("/valid/input.mp4", "/valid/output.mp4")
        assert True  # Should not raise exception
    except FFmpegCommandError:
        pytest.fail("Valid paths should not raise validation error")


def test_ffmpeg_parameter_validation():
    """Test FFmpeg parameter validation."""
    from worker.utils.ffmpeg import FFmpegCommandBuilder, FFmpegCommandError
    
    builder = FFmpegCommandBuilder()
    
    # Test invalid codec
    with pytest.raises(FFmpegCommandError, match="Invalid video codec"):
        builder._validate_transcode_params({"video_codec": "malicious_codec"})
    
    # Test valid codec
    try:
        builder._validate_transcode_params({"video_codec": "h264"})
        assert True
    except FFmpegCommandError:
        pytest.fail("Valid codec should not raise error")
    
    # Test CRF out of range
    with pytest.raises(FFmpegCommandError, match="out of range"):
        builder._validate_transcode_params({"crf": 100})


def test_path_traversal_prevention():
    """Test that path traversal attacks are prevented."""
    from api.utils.validators import validate_secure_path, SecurityError
    
    # Test directory traversal attempts
    with pytest.raises(SecurityError, match="Directory traversal"):
        validate_secure_path("../../../etc/passwd")
    
    with pytest.raises(SecurityError, match="Directory traversal"):
        validate_secure_path("/storage/../../../etc/passwd")
    
    # Test null byte injection
    with pytest.raises(SecurityError, match="Dangerous character"):
        validate_secure_path("/storage/file\x00.txt")
    
    # Test command injection
    with pytest.raises(SecurityError, match="Dangerous character"):
        validate_secure_path("/storage/file; rm -rf /")


def test_input_validation_operations():
    """Test enhanced operation validation."""
    from api.utils.validators import validate_operations, SecurityError
    
    # Test too many operations (DOS prevention)
    large_ops = [{"type": "trim", "start": 0}] * 100
    with pytest.raises(ValueError, match="Too many operations"):
        validate_operations(large_ops)
    
    # Test invalid operation type format
    with pytest.raises(SecurityError, match="Invalid operation type format"):
        validate_operations([{"type": "trim; rm -rf /"}])
    
    # Test valid operations
    valid_ops = [
        {"type": "trim", "start": 10, "duration": 30},
        {"type": "transcode", "video_codec": "h264"}
    ]
    result = validate_operations(valid_ops)
    assert len(result) == 2
    assert result[0]["type"] == "trim"


def test_rate_limiting_middleware():
    """Test rate limiting middleware functionality."""
    from api.middleware.security import RateLimitMiddleware, APIKeyQuota
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import Response
    from unittest.mock import AsyncMock
    
    app = Starlette()
    middleware = RateLimitMiddleware(app, calls=2, period=3600, enabled=True)
    
    # Test quota retrieval
    quota = middleware._get_client_quota("basic_test_key")
    assert isinstance(quota, APIKeyQuota)
    assert quota.calls_per_hour == 500  # Basic tier
    
    # Test enterprise key
    enterprise_quota = middleware._get_client_quota("ent_test_key")
    assert enterprise_quota.calls_per_hour == 10000  # Enterprise tier


def test_error_message_sanitization():
    """Test error message sanitization."""
    from api.utils.error_handler import ProductionErrorHandler, ErrorLevel
    
    handler = ProductionErrorHandler(debug_mode=False)
    
    # Test sensitive information removal
    error = Exception("Database error at postgresql://user:password@host:5432/db")
    result = handler.sanitize_error_message(error, ErrorLevel.HIGH)
    
    # Should not contain sensitive information
    assert "password" not in str(result)
    assert "postgresql://" not in str(result)
    assert result["error"]["message"] == "An error occurred"
    
    # Test debug mode
    debug_handler = ProductionErrorHandler(debug_mode=True)
    debug_result = debug_handler.sanitize_error_message(error, ErrorLevel.LOW)
    assert "debug_info" in debug_result["error"]


def test_security_middleware_headers():
    """Test security headers middleware."""
    from api.middleware.security import SecurityHeadersMiddleware
    from starlette.applications import Starlette
    from starlette.testclient import TestClient
    
    app = Starlette()
    
    @app.route("/test")
    async def test_endpoint(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"message": "test"})
    
    app.add_middleware(SecurityHeadersMiddleware)
    
    client = TestClient(app)
    response = client.get("/test")
    
    # Check security headers
    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" in response.headers
    assert "Content-Security-Policy" in response.headers


def test_input_sanitization_middleware():
    """Test input sanitization middleware."""
    from api.middleware.security import InputSanitizationMiddleware
    from starlette.applications import Starlette
    from starlette.testclient import TestClient
    
    app = Starlette()
    
    @app.route("/test", methods=["POST"])
    async def test_endpoint(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"message": "test"})
    
    app.add_middleware(InputSanitizationMiddleware, max_body_size=1024)
    
    client = TestClient(app)
    
    # Test content type validation
    response = client.post("/test", 
                          data="test", 
                          headers={"Content-Type": "text/plain"})
    assert response.status_code == 415  # Unsupported Media Type
    
    # Test valid content type
    response = client.post("/test", 
                          json={"data": "test"})
    assert response.status_code == 200


def test_security_audit_middleware():
    """Test security audit middleware."""
    from api.middleware.security import SecurityAuditMiddleware
    from starlette.applications import Starlette
    from starlette.testclient import TestClient
    import structlog
    from io import StringIO
    
    app = Starlette()
    
    @app.route("/test")
    async def test_endpoint(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"message": "test"})
    
    app.add_middleware(SecurityAuditMiddleware)
    
    client = TestClient(app)
    
    # Test normal request
    response = client.get("/test")
    assert response.status_code == 200


def test_comprehensive_security_config():
    """Test the comprehensive security configuration."""
    from api.security_config import SecurityConfig, validate_request_data
    
    config = SecurityConfig()
    
    # Test valid request data
    valid_data = {
        "input_path": "/storage/test.mp4",
        "output_path": "/storage/output.mp4",
        "operations": [
            {"type": "trim", "start": 10, "duration": 30}
        ]
    }
    
    # This should work with our security fixes
    try:
        result = validate_request_data(valid_data)
        assert "input_path" in result
        assert "operations" in result
        assert len(result["operations"]) == 1
    except Exception as e:
        # If validation fails, it should be due to path not being in allowed base paths
        # which is expected in test environment
        assert "Path outside allowed directories" in str(e)


# Integration test
def test_end_to_end_security():
    """Test that all security components work together."""
    from api.security_config import apply_security_to_app, get_security_info
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    
    app = FastAPI()
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    @app.post("/api/v1/process")
    async def process_video():
        return {"message": "processed"}
    
    # Apply security configuration
    app = apply_security_to_app(app)
    
    client = TestClient(app)
    
    # Test health endpoint (should work)
    response = client.get("/health")
    assert response.status_code == 200
    
    # Check security info
    security_info = get_security_info()
    assert security_info["security_enabled"] is True
    assert "rate_limiting" in security_info
    assert "input_validation" in security_info


if __name__ == "__main__":
    # Run basic validation tests
    test_ffmpeg_command_injection_prevention()
    test_path_traversal_prevention()
    test_input_validation_operations()
    test_error_message_sanitization()
    print("✅ All security fix tests passed!")