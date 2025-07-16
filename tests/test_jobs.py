"""
Test job management endpoints and functionality
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from api.main import app
from api.models.job import Job, JobStatus, JobType
from api.services.job import JobService


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_job():
    """Mock job for testing."""
    return Job(
        id=uuid4(),
        type=JobType.CONVERT,
        status=JobStatus.PENDING,
        priority=1,
        input_file="test.mp4",
        output_file="output.mp4",
        parameters={"codec": "h264"},
        progress=0.0,
        api_key_id=uuid4()
    )


@pytest.fixture
def auth_headers():
    """Authentication headers for testing."""
    return {"X-API-Key": "sk-test_valid_key"}


class TestJobEndpoints:
    """Test job-related endpoints."""

    @patch('api.dependencies.get_current_api_key')
    @patch('api.services.job.JobService.get_jobs')
    def test_get_jobs(self, mock_get_jobs, mock_auth, client, mock_job, auth_headers):
        """Test getting jobs list."""
        mock_auth.return_value = MagicMock()
        mock_get_jobs.return_value = [mock_job]
        
        response = client.get("/api/v1/jobs", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "convert"
        assert data[0]["status"] == "pending"

    @patch('api.dependencies.get_current_api_key')
    @patch('api.services.job.JobService.get_job')
    def test_get_job_by_id(self, mock_get_job, mock_auth, client, mock_job, auth_headers):
        """Test getting specific job by ID."""
        mock_auth.return_value = MagicMock()
        mock_get_job.return_value = mock_job
        
        job_id = str(mock_job.id)
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["type"] == "convert"

    @patch('api.dependencies.get_current_api_key')
    @patch('api.services.job.JobService.get_job')
    def test_get_job_not_found(self, mock_get_job, mock_auth, client, auth_headers):
        """Test getting non-existent job."""
        mock_auth.return_value = MagicMock()
        mock_get_job.return_value = None
        
        response = client.get("/api/v1/jobs/nonexistent", headers=auth_headers)
        
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    @patch('api.dependencies.get_current_api_key')
    @patch('api.services.job.JobService.create_job')
    def test_create_job(self, mock_create_job, mock_auth, client, mock_job, auth_headers):
        """Test creating a new job."""
        mock_auth.return_value = MagicMock()
        mock_create_job.return_value = mock_job
        
        job_data = {
            "type": "convert",
            "input_file": "test.mp4",
            "output_file": "output.mp4",
            "parameters": {"codec": "h264"},
            "priority": 1
        }
        
        response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "convert"
        assert data["status"] == "pending"

    @patch('api.dependencies.get_current_api_key')
    @patch('api.services.job.JobService.cancel_job')
    def test_cancel_job(self, mock_cancel_job, mock_auth, client, mock_job, auth_headers):
        """Test canceling a job."""
        mock_auth.return_value = MagicMock()
        mock_cancel_job.return_value = True
        
        job_id = str(mock_job.id)
        response = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Job cancelled successfully"

    @patch('api.dependencies.get_current_api_key')
    @patch('api.services.job.JobService.cancel_job')
    def test_cancel_job_not_found(self, mock_cancel_job, mock_auth, client, auth_headers):
        """Test canceling non-existent job."""
        mock_auth.return_value = MagicMock()
        mock_cancel_job.return_value = False
        
        response = client.post("/api/v1/jobs/nonexistent/cancel", headers=auth_headers)
        
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    @patch('api.dependencies.get_current_api_key')
    @patch('api.services.job.JobService.get_job_logs')
    def test_get_job_logs(self, mock_get_logs, mock_auth, client, auth_headers):
        """Test getting job logs."""
        mock_auth.return_value = MagicMock()
        mock_logs = [
            {"timestamp": "2025-01-01T00:00:00Z", "level": "INFO", "message": "Job started"},
            {"timestamp": "2025-01-01T00:01:00Z", "level": "INFO", "message": "Processing..."}
        ]
        mock_get_logs.return_value = mock_logs
        
        response = client.get("/api/v1/jobs/test-id/logs", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["message"] == "Job started"


class TestJobService:
    """Test job service functionality."""

    @pytest.mark.asyncio
    async def test_create_job(self, mock_job):
        """Test job creation in service."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('api.services.job.Job') as mock_job_class:
            mock_job_class.return_value = mock_job
            
            result = await JobService.create_job(
                mock_session,
                job_type=JobType.CONVERT,
                input_file="test.mp4",
                output_file="output.mp4",
                parameters={"codec": "h264"},
                api_key_id=uuid4()
            )
            
            assert result == mock_job
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_jobs(self, mock_job):
        """Test getting jobs from service."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [mock_job]
        mock_session.execute.return_value = mock_result
        
        result = await JobService.get_jobs(mock_session, api_key_id=uuid4())
        
        assert len(result) == 1
        assert result[0] == mock_job

    @pytest.mark.asyncio
    async def test_update_job_status(self, mock_job):
        """Test updating job status."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('api.services.job.JobService.get_job') as mock_get:
            mock_get.return_value = mock_job
            
            result = await JobService.update_job_status(
                mock_session,
                job_id=mock_job.id,
                status=JobStatus.PROCESSING,
                progress=50.0
            )
            
            assert result.status == JobStatus.PROCESSING
            assert result.progress == 50.0
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_job(self, mock_job):
        """Test canceling a job."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('api.services.job.JobService.get_job') as mock_get:
            mock_get.return_value = mock_job
            
            result = await JobService.cancel_job(mock_session, job_id=mock_job.id)
            
            assert result is True
            assert mock_job.status == JobStatus.CANCELLED
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self):
        """Test canceling non-existent job."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('api.services.job.JobService.get_job') as mock_get:
            mock_get.return_value = None
            
            result = await JobService.cancel_job(mock_session, job_id=uuid4())
            
            assert result is False

    @pytest.mark.asyncio
    async def test_get_job_logs(self):
        """Test getting job logs."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_logs = [
            {"timestamp": "2025-01-01T00:00:00Z", "level": "INFO", "message": "Job started"}
        ]
        
        with patch('api.services.job.JobService._get_logs_from_storage') as mock_get_logs:
            mock_get_logs.return_value = mock_logs
            
            result = await JobService.get_job_logs(mock_session, job_id=uuid4())
            
            assert len(result) == 1
            assert result[0]["message"] == "Job started"


class TestJobValidation:
    """Test job input validation."""

    @patch('api.dependencies.get_current_api_key')
    def test_create_job_invalid_type(self, mock_auth, client, auth_headers):
        """Test creating job with invalid type."""
        mock_auth.return_value = MagicMock()
        
        job_data = {
            "type": "invalid_type",
            "input_file": "test.mp4",
            "output_file": "output.mp4"
        }
        
        response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 422
        assert "validation error" in response.json()["detail"][0]["msg"]

    @patch('api.dependencies.get_current_api_key')
    def test_create_job_missing_required_fields(self, mock_auth, client, auth_headers):
        """Test creating job with missing required fields."""
        mock_auth.return_value = MagicMock()
        
        job_data = {
            "type": "convert"
            # Missing input_file and output_file
        }
        
        response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("input_file" in error["loc"] for error in errors)
        assert any("output_file" in error["loc"] for error in errors)

    @patch('api.dependencies.get_current_api_key')
    def test_create_job_invalid_priority(self, mock_auth, client, auth_headers):
        """Test creating job with invalid priority."""
        mock_auth.return_value = MagicMock()
        
        job_data = {
            "type": "convert",
            "input_file": "test.mp4",
            "output_file": "output.mp4",
            "priority": -1  # Invalid priority
        }
        
        response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 422
        assert "priority" in str(response.json()["detail"])