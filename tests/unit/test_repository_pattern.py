"""
Tests for repository pattern implementation
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from api.repositories.job_repository import JobRepository
from api.repositories.api_key_repository import APIKeyRepository
from api.services.job_service import JobService
from api.models.job import Job, JobStatus
from api.models.api_key import APIKey


class TestJobRepository:
    """Test job repository implementation."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        session = Mock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session
    
    @pytest.fixture
    def job_repository(self):
        """Job repository instance."""
        return JobRepository()
    
    def test_repository_initialization(self, job_repository):
        """Test repository initializes correctly."""
        assert job_repository.model == Job
    
    @pytest.mark.asyncio
    async def test_get_by_status(self, job_repository, mock_session):
        """Test getting jobs by status."""
        # Mock the database response
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Call the method
        jobs = await job_repository.get_by_status(mock_session, JobStatus.PENDING)
        
        # Verify the call was made
        assert mock_session.execute.called
        assert isinstance(jobs, list)
    
    @pytest.mark.asyncio
    async def test_get_pending_jobs(self, job_repository, mock_session):
        """Test getting pending jobs."""
        # Mock the database response
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Call the method
        jobs = await job_repository.get_pending_jobs(mock_session)
        
        # Verify the call was made
        assert mock_session.execute.called
        assert isinstance(jobs, list)


class TestAPIKeyRepository:
    """Test API key repository implementation."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        session = Mock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session
    
    @pytest.fixture
    def api_key_repository(self):
        """API key repository instance."""
        return APIKeyRepository()
    
    def test_repository_initialization(self, api_key_repository):
        """Test repository initializes correctly."""
        assert api_key_repository.model == APIKey
    
    @pytest.mark.asyncio
    async def test_get_by_key(self, api_key_repository, mock_session):
        """Test getting API key by key value."""
        # Mock the database response
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Call the method
        api_key = await api_key_repository.get_by_key(mock_session, "test_key")
        
        # Verify the call was made
        assert mock_session.execute.called
        assert api_key is None


class TestJobService:
    """Test job service implementation."""
    
    @pytest.fixture
    def mock_repository(self):
        """Mock job repository."""
        repo = Mock()
        repo.create = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.get_by_user_id = AsyncMock()
        repo.get_by_status = AsyncMock()
        repo.update_status = AsyncMock()
        return repo
    
    @pytest.fixture
    def job_service(self, mock_repository):
        """Job service instance with mocked repository."""
        return JobService(mock_repository)
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return Mock()
    
    @pytest.mark.asyncio
    async def test_create_job_success(self, job_service, mock_repository, mock_session):
        """Test successful job creation."""
        # Setup mock
        mock_job = Mock()
        mock_job.id = "test_job_id"
        mock_job.user_id = "test_user"
        mock_job.filename = "test.mp4"
        mock_job.conversion_type = "mp4_to_webm"
        mock_repository.create.return_value = mock_job
        
        # Test data
        job_data = {
            'filename': 'test.mp4',
            'user_id': 'test_user',
            'conversion_type': 'mp4_to_webm'
        }
        
        # Call the service
        result = await job_service.create_job(mock_session, **job_data)
        
        # Verify
        assert result == mock_job
        mock_repository.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_job_missing_field(self, job_service, mock_session):
        """Test job creation with missing required field."""
        # Test data missing required field
        job_data = {
            'filename': 'test.mp4',
            'user_id': 'test_user'
            # Missing 'conversion_type'
        }
        
        # Call the service and expect validation error
        with pytest.raises(Exception):  # ValidationError in actual implementation
            await job_service.create_job(mock_session, **job_data)
    
    @pytest.mark.asyncio
    async def test_get_job_not_found(self, job_service, mock_repository, mock_session):
        """Test getting non-existent job."""
        # Setup mock to return None
        mock_repository.get_by_id.return_value = None
        
        # Call the service and expect NotFoundError
        with pytest.raises(Exception):  # NotFoundError in actual implementation
            await job_service.get_job(mock_session, "non_existent_id")
    
    @pytest.mark.asyncio
    async def test_get_jobs_by_user(self, job_service, mock_repository, mock_session):
        """Test getting jobs by user."""
        # Setup mock
        mock_jobs = [Mock(), Mock()]
        mock_repository.get_by_user_id.return_value = mock_jobs
        
        # Call the service
        result = await job_service.get_jobs_by_user(mock_session, "test_user")
        
        # Verify
        assert result == mock_jobs
        mock_repository.get_by_user_id.assert_called_once_with(mock_session, "test_user", 100)


class TestRepositoryIntegration:
    """Integration tests for repository pattern."""
    
    def test_service_uses_repository_interface(self):
        """Test that service accepts repository interface."""
        from api.interfaces.job_repository import JobRepositoryInterface
        
        # Create a mock that implements the interface
        mock_repo = Mock(spec=JobRepositoryInterface)
        
        # Should be able to create service with interface
        service = JobService(mock_repo)
        assert service.job_repository == mock_repo
    
    def test_repository_implements_interface(self):
        """Test that repository implements the interface."""
        from api.interfaces.job_repository import JobRepositoryInterface
        
        repo = JobRepository()
        
        # Check that repository has all required methods
        assert hasattr(repo, 'create')
        assert hasattr(repo, 'get_by_id')
        assert hasattr(repo, 'get_by_status')
        assert hasattr(repo, 'update_status')
        
        # Verify it's considered an instance of the interface
        assert isinstance(repo, JobRepositoryInterface)


if __name__ == "__main__":
    pytest.main([__file__])