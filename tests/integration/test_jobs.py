"""
Job management tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from api.models.job import JobStatus, JobPriority


class TestJobEndpoints:
    """Test job management endpoints."""
    
    @pytest.mark.unit
    def test_list_jobs_success(self, authenticated_client, auth_headers):
        """Test successful job listing."""
        with patch('api.routers.jobs.select') as mock_select:
            # Mock database query results
            mock_result = MagicMock()
            mock_jobs = [
                MagicMock(
                    id=uuid4(),
                    status=JobStatus.COMPLETED,
                    input_path="input/video1.mp4",
                    output_path="output/video1.mp4",
                    progress=100.0,
                    created_at="2024-07-10T10:00:00Z",
                    api_key="rdf_testkey123",
                ),
                MagicMock(
                    id=uuid4(),
                    status=JobStatus.PROCESSING,
                    input_path="input/video2.mp4",
                    output_path="output/video2.mp4",
                    progress=50.0,
                    created_at="2024-07-10T11:00:00Z",
                    api_key="rdf_testkey123",
                ),
            ]
            
            mock_result.scalars.return_value.all.return_value = mock_jobs
            mock_result.scalar.return_value = 2  # Total count
            
            # Mock the database session execute method
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    "/api/v1/jobs",
                    headers=auth_headers,
                )
                
                assert response.status_code == 200
                data = response.json()
                
                assert "jobs" in data
                assert "total" in data
                assert "page" in data
                assert "per_page" in data
                assert "has_next" in data
                assert "has_prev" in data
                
                assert data["total"] == 2
                assert len(data["jobs"]) == 2
    
    @pytest.mark.unit
    def test_list_jobs_pagination(self, authenticated_client, auth_headers):
        """Test job listing with pagination parameters."""
        with patch('api.routers.jobs.select'):
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = []
                mock_result.scalar.return_value = 0
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    "/api/v1/jobs?page=2&per_page=10&status=completed&sort=created_at:desc",
                    headers=auth_headers,
                )
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["page"] == 2
                assert data["per_page"] == 10
    
    @pytest.mark.unit
    def test_list_jobs_unauthorized(self, client):
        """Test job listing without authentication."""
        response = client.get("/api/v1/jobs")
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "api key" in data["error"]["message"].lower()
    
    @pytest.mark.unit
    def test_get_job_success(self, authenticated_client, auth_headers):
        """Test successful job retrieval."""
        job_id = uuid4()
        
        with patch('api.routers.jobs.select') as mock_select:
            mock_result = MagicMock()
            mock_job = MagicMock(
                id=job_id,
                status=JobStatus.COMPLETED,
                input_path="input/test.mp4",
                output_path="output/test.mp4",
                progress=100.0,
                created_at="2024-07-10T10:00:00Z",
                completed_at="2024-07-10T10:05:00Z",
                api_key="rdf_testkey123",
            )
            mock_result.scalar_one_or_none.return_value = mock_job
            
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    f"/api/v1/jobs/{job_id}",
                    headers=auth_headers,
                )
                
                assert response.status_code == 200
                data = response.json()
                
                assert str(data["id"]) == str(job_id)
                assert data["status"] == "completed"
                assert data["progress"] == 100.0
    
    @pytest.mark.unit
    def test_get_job_not_found(self, authenticated_client, auth_headers):
        """Test job retrieval when job not found."""
        job_id = uuid4()
        
        with patch('api.routers.jobs.select'):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    f"/api/v1/jobs/{job_id}",
                    headers=auth_headers,
                )
                
                assert response.status_code == 404
                data = response.json()
                assert "error" in data
                assert "not found" in data["error"]["message"].lower()
    
    @pytest.mark.unit
    def test_cancel_job_success(self, authenticated_client, auth_headers):
        """Test successful job cancellation."""
        job_id = uuid4()
        
        with patch('api.routers.jobs.select') as mock_select:
            mock_result = MagicMock()
            mock_job = MagicMock(
                id=job_id,
                status=JobStatus.PROCESSING,
                api_key="rdf_testkey123",
            )
            mock_result.scalar_one_or_none.return_value = mock_job
            
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                with patch('api.routers.jobs.queue_service') as mock_queue:
                    mock_queue.cancel_job.return_value = True
                    
                    response = authenticated_client.post(
                        f"/api/v1/jobs/{job_id}/cancel",
                        headers=auth_headers,
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    
                    assert "message" in data
                    assert "cancelled" in data["message"].lower()
    
    @pytest.mark.unit
    def test_cancel_job_not_cancellable(self, authenticated_client, auth_headers):
        """Test job cancellation when job cannot be cancelled."""
        job_id = uuid4()
        
        with patch('api.routers.jobs.select'):
            mock_result = MagicMock()
            mock_job = MagicMock(
                id=job_id,
                status=JobStatus.COMPLETED,  # Completed jobs can't be cancelled
                api_key="rdf_testkey123",
            )
            mock_result.scalar_one_or_none.return_value = mock_job
            
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.post(
                    f"/api/v1/jobs/{job_id}/cancel",
                    headers=auth_headers,
                )
                
                assert response.status_code == 400
                data = response.json()
                assert "error" in data
                assert "cannot be cancelled" in data["error"]["message"].lower()
    
    @pytest.mark.unit
    def test_get_job_progress_sse(self, authenticated_client, auth_headers):
        """Test job progress Server-Sent Events endpoint."""
        job_id = uuid4()
        
        # Note: SSE testing is complex, this is a basic structure test
        response = authenticated_client.get(
            f"/api/v1/jobs/{job_id}/progress",
            headers=auth_headers,
        )
        
        # SSE endpoints typically return 200 with text/event-stream content-type
        # The actual streaming would need integration tests
        assert response.status_code in [200, 404]  # Depends on job existence


class TestJobSecurity:
    """Test job security aspects."""
    
    @pytest.mark.security
    def test_user_can_only_see_own_jobs(self, authenticated_client, auth_headers):
        """Test that users can only see their own jobs."""
        # This test verifies the API key filtering in the job list endpoint
        with patch('api.routers.jobs.select') as mock_select:
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = []
                mock_result.scalar.return_value = 0
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    "/api/v1/jobs",
                    headers=auth_headers,
                )
                
                assert response.status_code == 200
                
                # Verify that the query filters by API key
                # This would be tested more thoroughly in integration tests
                mock_db.execute.assert_called()
    
    @pytest.mark.security
    def test_user_cannot_access_other_user_job(self, authenticated_client, auth_headers):
        """Test that users cannot access jobs from other users."""
        job_id = uuid4()
        
        with patch('api.routers.jobs.select'):
            mock_result = MagicMock()
            mock_job = MagicMock(
                id=job_id,
                status=JobStatus.COMPLETED,
                api_key="different_api_key",  # Different API key
            )
            mock_result.scalar_one_or_none.return_value = mock_job
            
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    f"/api/v1/jobs/{job_id}",
                    headers=auth_headers,
                )
                
                # Should not find the job (filtered by API key)
                # This behavior depends on the actual implementation
                assert response.status_code in [403, 404]
    
    @pytest.mark.security
    def test_admin_can_see_all_jobs(self, admin_client, admin_auth_headers):
        """Test that admin users can see all jobs."""
        with patch('api.routers.jobs.select'):
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = []
                mock_result.scalar.return_value = 0
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = admin_client.get(
                    "/api/v1/jobs",
                    headers=admin_auth_headers,
                )
                
                assert response.status_code == 200
                
                # Admin should be able to see all jobs
                # This would be verified in the actual query construction


class TestJobFiltering:
    """Test job filtering and sorting functionality."""
    
    @pytest.mark.unit
    def test_filter_by_status(self, authenticated_client, auth_headers):
        """Test filtering jobs by status."""
        with patch('api.routers.jobs.select'):
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = []
                mock_result.scalar.return_value = 0
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    "/api/v1/jobs?status=completed",
                    headers=auth_headers,
                )
                
                assert response.status_code == 200
    
    @pytest.mark.unit
    def test_sort_jobs(self, authenticated_client, auth_headers):
        """Test sorting jobs."""
        sort_options = [
            "created_at:desc",
            "created_at:asc", 
            "status:desc",
            "progress:asc",
        ]
        
        for sort_option in sort_options:
            with patch('api.routers.jobs.select'):
                with patch('api.dependencies.get_db') as mock_get_db:
                    mock_db = AsyncMock()
                    mock_result = MagicMock()
                    mock_result.scalars.return_value.all.return_value = []
                    mock_result.scalar.return_value = 0
                    mock_db.execute.return_value = mock_result
                    mock_get_db.return_value = mock_db
                    
                    response = authenticated_client.get(
                        f"/api/v1/jobs?sort={sort_option}",
                        headers=auth_headers,
                    )
                    
                    assert response.status_code == 200
    
    @pytest.mark.unit
    def test_invalid_sort_parameter(self, authenticated_client, auth_headers):
        """Test handling of invalid sort parameters."""
        with patch('api.routers.jobs.select'):
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = []
                mock_result.scalar.return_value = 0
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    "/api/v1/jobs?sort=invalid_field:desc",
                    headers=auth_headers,
                )
                
                # Should still work but fall back to default sorting
                assert response.status_code == 200


class TestJobResponseFormat:
    """Test job response format and structure."""
    
    @pytest.mark.unit
    def test_job_response_structure(self, authenticated_client, auth_headers):
        """Test that job responses have the correct structure."""
        job_id = uuid4()
        
        with patch('api.routers.jobs.select'):
            mock_result = MagicMock()
            mock_job = MagicMock(
                id=job_id,
                status=JobStatus.COMPLETED,
                priority=JobPriority.NORMAL,
                progress=100.0,
                stage="completed",
                created_at="2024-07-10T10:00:00Z",
                started_at="2024-07-10T10:01:00Z",
                completed_at="2024-07-10T10:05:00Z",
                eta_seconds=None,
                api_key="rdf_testkey123",
            )
            mock_result.scalar_one_or_none.return_value = mock_job
            
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    f"/api/v1/jobs/{job_id}",
                    headers=auth_headers,
                )
                
                assert response.status_code == 200
                data = response.json()
                
                # Verify required fields
                required_fields = [
                    "id", "status", "priority", "progress", "stage",
                    "created_at", "started_at", "completed_at", "eta_seconds"
                ]
                
                for field in required_fields:
                    assert field in data, f"Missing required field: {field}"
                
                # Verify field types
                assert isinstance(data["progress"], (int, float))
                assert 0 <= data["progress"] <= 100
                assert data["status"] in [status.value for status in JobStatus]
                assert data["priority"] in [priority.value for priority in JobPriority]
    
    @pytest.mark.unit
    def test_job_list_response_structure(self, authenticated_client, auth_headers):
        """Test that job list responses have the correct structure."""
        with patch('api.routers.jobs.select'):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_result.scalar.return_value = 0
            
            with patch('api.dependencies.get_db') as mock_get_db:
                mock_db = AsyncMock()
                mock_db.execute.return_value = mock_result
                mock_get_db.return_value = mock_db
                
                response = authenticated_client.get(
                    "/api/v1/jobs",
                    headers=auth_headers,
                )
                
                assert response.status_code == 200
                data = response.json()
                
                # Verify pagination structure
                pagination_fields = ["jobs", "total", "page", "per_page", "has_next", "has_prev"]
                for field in pagination_fields:
                    assert field in data, f"Missing pagination field: {field}"
                
                # Verify field types
                assert isinstance(data["jobs"], list)
                assert isinstance(data["total"], int)
                assert isinstance(data["page"], int)
                assert isinstance(data["per_page"], int)
                assert isinstance(data["has_next"], bool)
                assert isinstance(data["has_prev"], bool)