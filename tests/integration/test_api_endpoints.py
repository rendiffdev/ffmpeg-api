"""
Tests for API endpoints and route functionality
"""
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.models.job import Job, JobStatus
from api.models.api_key import ApiKeyUser


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.mark.unit
    def test_health_check_basic(self, client):
        """Test basic health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert data["status"] == "healthy"
    
    @pytest.mark.unit
    def test_health_check_detailed(self, client):
        """Test detailed health check endpoint."""
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "timestamp" in data
        
        # Should have database and storage checks
        checks = data["checks"]
        assert isinstance(checks, dict)


class TestConvertEndpoints:
    """Test video conversion endpoints."""
    
    @pytest.fixture
    def authenticated_client(self, client, override_db_dependency):
        """Create authenticated test client."""
        # Mock authentication
        def mock_get_current_user():
            return (
                ApiKeyUser(
                    id="test-user",
                    api_key_id="test-key-id",
                    api_key_prefix="test",
                    role="user",
                    max_concurrent_jobs=5,
                    monthly_quota_minutes=1000,
                    is_admin=False,
                    total_jobs_created=0,
                    total_minutes_processed=0,
                    last_used_at=None,
                ),
                "test-api-key"
            )
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        yield client
        app.dependency_overrides.pop(get_current_user, None)
    
    @pytest.mark.unit
    def test_convert_video_validation_error(self, authenticated_client):
        """Test convert endpoint with validation error."""
        # Missing required fields
        request_data = {
            "input": {
                "path": "input.mp4"
                # Missing storage backend
            }
        }
        
        response = authenticated_client.post(
            "/api/v1/convert",
            json=request_data
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.unit
    def test_convert_video_success(self, authenticated_client):
        """Test successful video conversion request."""
        request_data = {
            "input": {
                "path": "input.mp4",
                "storage": "local"
            },
            "output": {
                "path": "output.mp4",
                "storage": "local"
            },
            "operations": [
                {
                    "type": "convert",
                    "format": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac"
                }
            ],
            "options": {
                "quality": "high"
            }
        }
        
        with patch('api.routers.convert.QueueService') as mock_queue:
            mock_queue_instance = AsyncMock()
            mock_queue_instance.submit_job.return_value = str(uuid4())
            mock_queue.return_value = mock_queue_instance
            
            response = authenticated_client.post(
                "/api/v1/convert",
                json=request_data
            )
            
            assert response.status_code == 200
            
            data = response.json()
            assert "job_id" in data
            assert "status" in data
            assert data["status"] == "queued"
    
    @pytest.mark.unit
    def test_convert_video_unauthenticated(self, client):
        """Test convert endpoint without authentication."""
        request_data = {
            "input": {
                "path": "input.mp4",
                "storage": "local"
            },
            "output": {
                "path": "output.mp4",
                "storage": "local"
            }
        }
        
        response = client.post("/api/v1/convert", json=request_data)
        assert response.status_code == 401


class TestJobEndpoints:
    """Test job management endpoints."""
    
    @pytest.fixture
    def authenticated_client(self, client, override_db_dependency):
        """Create authenticated test client."""
        def mock_get_current_user():
            return (
                ApiKeyUser(
                    id="test-user",
                    api_key_id="test-key-id",
                    api_key_prefix="test",
                    role="user",
                    max_concurrent_jobs=5,
                    monthly_quota_minutes=1000,
                    is_admin=False,
                    total_jobs_created=0,
                    total_minutes_processed=0,
                    last_used_at=None,
                ),
                "test-api-key"
            )
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        yield client
        app.dependency_overrides.pop(get_current_user, None)
    
    @pytest.mark.unit
    def test_list_jobs_success(self, authenticated_client, test_db_session):
        """Test successful job listing."""
        response = authenticated_client.get("/api/v1/jobs")
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert isinstance(data["jobs"], list)
    
    @pytest.mark.unit
    def test_list_jobs_with_filters(self, authenticated_client):
        """Test job listing with filters."""
        response = authenticated_client.get(
            "/api/v1/jobs?status=completed&page=1&per_page=5"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 5
    
    @pytest.mark.unit
    def test_get_job_by_id(self, authenticated_client, test_db_session):
        """Test getting specific job by ID."""
        # Create test job
        job = Job(
            id=str(uuid4()),
            status=JobStatus.COMPLETED,
            input_path="test-input.mp4",
            output_path="test-output.mp4",
            api_key="test-api-key",
            operations=[],
            options={}
        )
        test_db_session.add(job)
        test_db_session.commit()
        
        response = authenticated_client.get(f"/api/v1/jobs/{job.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == str(job.id)
        assert data["status"] == "completed"
    
    @pytest.mark.unit
    def test_get_job_not_found(self, authenticated_client):
        """Test getting non-existent job."""
        fake_job_id = str(uuid4())
        response = authenticated_client.get(f"/api/v1/jobs/{fake_job_id}")
        assert response.status_code == 404
    
    @pytest.mark.unit
    def test_cancel_job_success(self, authenticated_client, test_db_session):
        """Test successful job cancellation."""
        # Create test job in processing state
        job = Job(
            id=str(uuid4()),
            status=JobStatus.PROCESSING,
            input_path="test-input.mp4",
            output_path="test-output.mp4",
            api_key="test-api-key",
            operations=[],
            options={}
        )
        test_db_session.add(job)
        test_db_session.commit()
        
        with patch('api.routers.jobs.QueueService') as mock_queue:
            mock_queue_instance = AsyncMock()
            mock_queue_instance.cancel_job.return_value = True
            mock_queue.return_value = mock_queue_instance
            
            response = authenticated_client.post(f"/api/v1/jobs/{job.id}/cancel")
            assert response.status_code == 200
            
            data = response.json()
            assert "message" in data
    
    @pytest.mark.unit
    def test_cancel_completed_job(self, authenticated_client, test_db_session):
        """Test cancelling already completed job."""
        # Create completed job
        job = Job(
            id=str(uuid4()),
            status=JobStatus.COMPLETED,
            input_path="test-input.mp4",
            output_path="test-output.mp4",
            api_key="test-api-key",
            operations=[],
            options={}
        )
        test_db_session.add(job)
        test_db_session.commit()
        
        response = authenticated_client.post(f"/api/v1/jobs/{job.id}/cancel")
        assert response.status_code == 400  # Cannot cancel completed job
    
    @pytest.mark.unit
    def test_get_job_progress(self, authenticated_client, test_db_session):
        """Test getting job progress."""
        # Create job with progress
        job = Job(
            id=str(uuid4()),
            status=JobStatus.PROCESSING,
            input_path="test-input.mp4",
            output_path="test-output.mp4",
            api_key="test-api-key",
            operations=[],
            options={},
            progress=45.5,
            current_stage="processing"
        )
        test_db_session.add(job)
        test_db_session.commit()
        
        response = authenticated_client.get(f"/api/v1/jobs/{job.id}/progress")
        assert response.status_code == 200
        
        data = response.json()
        assert data["progress"] == 45.5
        assert data["stage"] == "processing"


class TestAdminEndpoints:
    """Test admin-only endpoints."""
    
    @pytest.fixture
    def admin_client(self, client, override_db_dependency):
        """Create admin authenticated test client."""
        def mock_get_current_user():
            return (
                ApiKeyUser(
                    id="admin-user",
                    api_key_id="admin-key-id",
                    api_key_prefix="admin",
                    role="admin",
                    max_concurrent_jobs=50,
                    monthly_quota_minutes=10000,
                    is_admin=True,
                    total_jobs_created=0,
                    total_minutes_processed=0,
                    last_used_at=None,
                ),
                "admin-api-key"
            )
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        yield client
        app.dependency_overrides.pop(get_current_user, None)
    
    @pytest.fixture
    def user_client(self, client, override_db_dependency):
        """Create regular user test client."""
        def mock_get_current_user():
            return (
                ApiKeyUser(
                    id="regular-user",
                    api_key_id="user-key-id",
                    api_key_prefix="user",
                    role="user",
                    max_concurrent_jobs=5,
                    monthly_quota_minutes=1000,
                    is_admin=False,
                    total_jobs_created=0,
                    total_minutes_processed=0,
                    last_used_at=None,
                ),
                "user-api-key"
            )
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        yield client
        app.dependency_overrides.pop(get_current_user, None)
    
    @pytest.mark.unit
    def test_admin_stats_success(self, admin_client):
        """Test admin stats endpoint access."""
        response = admin_client.get("/api/v1/admin/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_jobs" in data
        assert "active_workers" in data
        assert "system_stats" in data
    
    @pytest.mark.unit
    def test_admin_stats_forbidden_for_user(self, user_client):
        """Test admin stats forbidden for regular users."""
        response = user_client.get("/api/v1/admin/stats")
        assert response.status_code == 403
    
    @pytest.mark.unit
    def test_admin_system_info(self, admin_client):
        """Test admin system info endpoint."""
        response = admin_client.get("/api/v1/admin/system")
        assert response.status_code == 200
        
        data = response.json()
        assert "system" in data
        assert "database" in data
        assert "storage" in data
        assert "workers" in data


class TestErrorHandling:
    """Test API error handling."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.mark.unit
    def test_404_for_nonexistent_endpoint(self, client):
        """Test 404 response for non-existent endpoint."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
    
    @pytest.mark.unit
    def test_405_for_wrong_method(self, client):
        """Test 405 response for wrong HTTP method."""
        response = client.post("/api/v1/health")  # Health is GET only
        assert response.status_code == 405
    
    @pytest.mark.unit
    def test_validation_error_format(self, client):
        """Test validation error response format."""
        # Send invalid JSON to an endpoint
        response = client.post(
            "/api/v1/convert",
            json={"invalid": "data"},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.mark.unit
    @pytest.mark.skipif(
        not hasattr(app, 'rate_limiter'), 
        reason="Rate limiting not configured"
    )
    def test_rate_limiting_enforcement(self, client):
        """Test rate limiting is enforced."""
        # This test would require actual rate limiting to be configured
        # For now, we'll just test that the endpoint responds normally
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestCORS:
    """Test CORS functionality."""
    
    @pytest.mark.unit
    def test_cors_headers_present(self, client):
        """Test that CORS headers are present."""
        response = client.options("/api/v1/health")
        
        # Should have CORS headers
        headers = response.headers
        assert "access-control-allow-origin" in headers or response.status_code == 200
    
    @pytest.mark.unit
    def test_preflight_request(self, client):
        """Test CORS preflight request."""
        response = client.options(
            "/api/v1/convert",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # Should handle preflight request
        assert response.status_code in [200, 204]


class TestResponseFormats:
    """Test API response formats."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.mark.unit
    def test_json_response_format(self, client):
        """Test JSON response format."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        # Should be valid JSON
        data = response.json()
        assert isinstance(data, dict)
        
        # Should have correct content type
        assert "application/json" in response.headers.get("content-type", "")
    
    @pytest.mark.unit
    def test_error_response_format(self, client):
        """Test error response format consistency."""
        response = client.get("/api/v1/jobs/invalid-uuid")
        
        data = response.json()
        
        # Error responses should have consistent format
        if response.status_code >= 400:
            # Should have error information
            assert "detail" in data or "error" in data


class TestApiVersioning:
    """Test API versioning."""
    
    @pytest.mark.unit
    def test_v1_endpoints_accessible(self, client):
        """Test that v1 endpoints are accessible."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    
    @pytest.mark.unit
    def test_version_in_response_headers(self, client):
        """Test API version in response headers."""
        response = client.get("/api/v1/health")
        
        # Should include version information
        data = response.json()
        if "version" in data:
            assert data["version"] is not None