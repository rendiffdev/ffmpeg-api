"""
Test service layer functionality
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from api.services.job import JobService
from api.services.api_key import APIKeyService
from api.models.job import Job, JobStatus, JobType
from api.models.api_key import APIKey


class TestJobService:
    """Test job service functionality."""

    @pytest.mark.asyncio
    async def test_create_job_success(self):
        """Test successful job creation."""
        mock_session = AsyncMock()
        api_key_id = uuid4()
        
        job = await JobService.create_job(
            session=mock_session,
            job_type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            parameters={"codec": "h264"},
            api_key_id=api_key_id
        )
        
        assert job.type == JobType.CONVERT
        assert job.status == JobStatus.PENDING
        assert job.input_file == "test.mp4"
        assert job.output_file == "output.mp4"
        assert job.parameters == {"codec": "h264"}
        assert job.api_key_id == api_key_id
        
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_by_id(self):
        """Test getting job by ID."""
        mock_session = AsyncMock()
        job_id = uuid4()
        mock_job = Job(
            id=job_id,
            type=JobType.CONVERT,
            status=JobStatus.PENDING,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_session.execute.return_value = mock_result
        
        result = await JobService.get_job(mock_session, job_id)
        
        assert result == mock_job
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        """Test getting non-existent job."""
        mock_session = AsyncMock()
        job_id = uuid4()
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await JobService.get_job(mock_session, job_id)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_jobs_by_api_key(self):
        """Test getting jobs filtered by API key."""
        mock_session = AsyncMock()
        api_key_id = uuid4()
        mock_jobs = [
            Job(id=uuid4(), type=JobType.CONVERT, status=JobStatus.PENDING, 
                input_file="test1.mp4", output_file="output1.mp4", api_key_id=api_key_id),
            Job(id=uuid4(), type=JobType.COMPRESS, status=JobStatus.COMPLETED, 
                input_file="test2.mp4", output_file="output2.mp4", api_key_id=api_key_id)
        ]
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_jobs
        mock_session.execute.return_value = mock_result
        
        result = await JobService.get_jobs(mock_session, api_key_id=api_key_id)
        
        assert len(result) == 2
        assert all(job.api_key_id == api_key_id for job in result)

    @pytest.mark.asyncio
    async def test_update_job_status(self):
        """Test updating job status."""
        mock_session = AsyncMock()
        job_id = uuid4()
        mock_job = Job(
            id=job_id,
            type=JobType.CONVERT,
            status=JobStatus.PENDING,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        with patch.object(JobService, 'get_job', return_value=mock_job):
            result = await JobService.update_job_status(
                mock_session, job_id, JobStatus.PROCESSING, progress=25.0
            )
            
            assert result.status == JobStatus.PROCESSING
            assert result.progress == 25.0
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_job_success(self):
        """Test successful job cancellation."""
        mock_session = AsyncMock()
        job_id = uuid4()
        mock_job = Job(
            id=job_id,
            type=JobType.CONVERT,
            status=JobStatus.PENDING,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        with patch.object(JobService, 'get_job', return_value=mock_job):
            result = await JobService.cancel_job(mock_session, job_id)
            
            assert result is True
            assert mock_job.status == JobStatus.CANCELLED
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self):
        """Test cancelling non-existent job."""
        mock_session = AsyncMock()
        job_id = uuid4()
        
        with patch.object(JobService, 'get_job', return_value=None):
            result = await JobService.cancel_job(mock_session, job_id)
            
            assert result is False
            mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_job_logs(self):
        """Test getting job logs."""
        mock_session = AsyncMock()
        job_id = uuid4()
        mock_logs = [
            {"timestamp": "2025-01-01T00:00:00Z", "level": "INFO", "message": "Job started"},
            {"timestamp": "2025-01-01T00:01:00Z", "level": "INFO", "message": "Processing..."}
        ]
        
        with patch.object(JobService, '_get_logs_from_storage', return_value=mock_logs):
            result = await JobService.get_job_logs(mock_session, job_id)
            
            assert len(result) == 2
            assert result[0]["message"] == "Job started"
            assert result[1]["message"] == "Processing..."

    @pytest.mark.asyncio
    async def test_get_job_stats(self):
        """Test getting job statistics."""
        mock_session = AsyncMock()
        api_key_id = uuid4()
        
        # Mock the database query results
        mock_results = [
            ("pending", 5),
            ("processing", 2),
            ("completed", 10),
            ("failed", 1)
        ]
        
        mock_result = AsyncMock()
        mock_result.all.return_value = mock_results
        mock_session.execute.return_value = mock_result
        
        stats = await JobService.get_job_stats(mock_session, api_key_id)
        
        assert stats["pending"] == 5
        assert stats["processing"] == 2
        assert stats["completed"] == 10
        assert stats["failed"] == 1
        assert stats["total"] == 18


class TestAPIKeyService:
    """Test API key service functionality."""

    @pytest.mark.asyncio
    async def test_create_api_key(self):
        """Test creating a new API key."""
        mock_session = AsyncMock()
        
        result = await APIKeyService.create_api_key(
            session=mock_session,
            name="Test Key",
            rate_limit=500
        )
        
        assert result["name"] == "Test Key"
        assert result["key"].startswith("sk-")
        assert len(result["key"]) == 51
        assert result["rate_limit"] == 500
        
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self):
        """Test successful API key validation."""
        mock_session = AsyncMock()
        raw_key = "sk-test_1234567890abcdef"
        mock_api_key = APIKey(
            id=uuid4(),
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            is_active=True
        )
        
        with patch.object(APIKeyService, '_get_key_by_prefix', return_value=mock_api_key):
            with patch.object(APIKeyService, '_hash_key', return_value="hashed_value"):
                result = await APIKeyService.validate_api_key(mock_session, raw_key)
                
                assert result == mock_api_key
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_hash(self):
        """Test API key validation with invalid hash."""
        mock_session = AsyncMock()
        raw_key = "sk-test_1234567890abcdef"
        mock_api_key = APIKey(
            id=uuid4(),
            name="Test Key",
            key_hash="correct_hash",
            key_prefix="sk-test",
            is_active=True
        )
        
        with patch.object(APIKeyService, '_get_key_by_prefix', return_value=mock_api_key):
            with patch.object(APIKeyService, '_hash_key', return_value="wrong_hash"):
                result = await APIKeyService.validate_api_key(mock_session, raw_key)
                
                assert result is None

    @pytest.mark.asyncio
    async def test_validate_api_key_inactive(self):
        """Test API key validation with inactive key."""
        mock_session = AsyncMock()
        raw_key = "sk-test_1234567890abcdef"
        mock_api_key = APIKey(
            id=uuid4(),
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            is_active=False
        )
        
        with patch.object(APIKeyService, '_get_key_by_prefix', return_value=mock_api_key):
            with patch.object(APIKeyService, '_hash_key', return_value="hashed_value"):
                result = await APIKeyService.validate_api_key(mock_session, raw_key)
                
                assert result is None

    @pytest.mark.asyncio
    async def test_get_api_keys(self):
        """Test getting API keys."""
        mock_session = AsyncMock()
        mock_keys = [
            APIKey(id=uuid4(), name="Key 1", key_hash="hash1", key_prefix="sk-test"),
            APIKey(id=uuid4(), name="Key 2", key_hash="hash2", key_prefix="sk-prod")
        ]
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_keys
        mock_session.execute.return_value = mock_result
        
        result = await APIKeyService.get_api_keys(mock_session)
        
        assert len(result) == 2
        assert result[0].name == "Key 1"
        assert result[1].name == "Key 2"

    @pytest.mark.asyncio
    async def test_deactivate_api_key(self):
        """Test deactivating an API key."""
        mock_session = AsyncMock()
        key_id = uuid4()
        mock_api_key = APIKey(
            id=key_id,
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            is_active=True
        )
        
        with patch.object(APIKeyService, 'get_api_key', return_value=mock_api_key):
            result = await APIKeyService.deactivate_api_key(mock_session, key_id)
            
            assert result is True
            assert mock_api_key.is_active is False
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_api_key_not_found(self):
        """Test deactivating non-existent API key."""
        mock_session = AsyncMock()
        key_id = uuid4()
        
        with patch.object(APIKeyService, 'get_api_key', return_value=None):
            result = await APIKeyService.deactivate_api_key(mock_session, key_id)
            
            assert result is False
            mock_session.commit.assert_not_called()

    def test_generate_key_format(self):
        """Test generated key format."""
        key, hash_value = APIKeyService._generate_key()
        
        assert key.startswith("sk-")
        assert len(key) == 51
        assert len(hash_value) == 64
        assert key != hash_value

    def test_hash_key_consistency(self):
        """Test key hashing consistency."""
        key = "test_key_123"
        hash1 = APIKeyService._hash_key(key)
        hash2 = APIKeyService._hash_key(key)
        
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_extract_prefix(self):
        """Test key prefix extraction."""
        key = "sk-test_1234567890abcdef"
        prefix = APIKeyService._extract_prefix(key)
        
        assert prefix == "sk-test"
        
        # Test invalid format
        invalid_key = "invalid_key"
        prefix = APIKeyService._extract_prefix(invalid_key)
        assert prefix == ""

    def test_validate_key_format(self):
        """Test key format validation."""
        valid_key = "sk-test_1234567890abcdef1234567890abcdef12345678"
        invalid_key = "invalid_key"
        
        assert APIKeyService._validate_key_format(valid_key) is True
        assert APIKeyService._validate_key_format(invalid_key) is False


class TestServiceIntegration:
    """Test service integration scenarios."""

    @pytest.mark.asyncio
    async def test_job_creation_with_api_key_validation(self):
        """Test creating a job with API key validation."""
        mock_session = AsyncMock()
        api_key_id = uuid4()
        
        # Mock API key validation
        mock_api_key = APIKey(
            id=api_key_id,
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            is_active=True,
            rate_limit=1000,
            usage_count=0
        )
        
        with patch.object(APIKeyService, 'validate_api_key', return_value=mock_api_key):
            # Create job
            job = await JobService.create_job(
                session=mock_session,
                job_type=JobType.CONVERT,
                input_file="test.mp4",
                output_file="output.mp4",
                parameters={"codec": "h264"},
                api_key_id=api_key_id
            )
            
            assert job.api_key_id == api_key_id
            assert job.type == JobType.CONVERT

    @pytest.mark.asyncio
    async def test_rate_limiting_check(self):
        """Test rate limiting functionality."""
        mock_session = AsyncMock()
        api_key_id = uuid4()
        
        # Mock API key at rate limit
        mock_api_key = APIKey(
            id=api_key_id,
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            is_active=True,
            rate_limit=10,
            usage_count=10  # At limit
        )
        
        with patch.object(APIKeyService, 'get_api_key', return_value=mock_api_key):
            # Check if key is rate limited
            assert mock_api_key.is_rate_limited() is True
            
            # Usage count below limit
            mock_api_key.usage_count = 5
            assert mock_api_key.is_rate_limited() is False