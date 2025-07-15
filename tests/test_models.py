"""
Test database models and relationships
"""
import pytest
from datetime import datetime
from uuid import uuid4

from api.models.api_key import APIKey
from api.models.job import Job, JobStatus, JobType
from api.models.database import Base
from api.services.api_key import APIKeyService


class TestAPIKeyModel:
    """Test APIKey model functionality."""

    def test_api_key_creation(self):
        """Test creating an API key model."""
        key_id = uuid4()
        api_key = APIKey(
            id=key_id,
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            is_active=True,
            rate_limit=1000,
            usage_count=0
        )
        
        assert api_key.id == key_id
        assert api_key.name == "Test Key"
        assert api_key.key_hash == "hashed_value"
        assert api_key.key_prefix == "sk-test"
        assert api_key.is_active is True
        assert api_key.rate_limit == 1000
        assert api_key.usage_count == 0

    def test_api_key_defaults(self):
        """Test API key model defaults."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test"
        )
        
        assert api_key.is_active is True
        assert api_key.rate_limit == 1000
        assert api_key.usage_count == 0
        assert api_key.last_used is None

    def test_api_key_string_representation(self):
        """Test API key string representation."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test"
        )
        
        str_repr = str(api_key)
        assert "Test Key" in str_repr
        assert "sk-test" in str_repr

    def test_api_key_increment_usage(self):
        """Test incrementing API key usage."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            usage_count=5
        )
        
        api_key.increment_usage()
        assert api_key.usage_count == 6
        assert api_key.last_used is not None

    def test_api_key_deactivate(self):
        """Test deactivating API key."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            is_active=True
        )
        
        api_key.deactivate()
        assert api_key.is_active is False

    def test_api_key_is_rate_limited(self):
        """Test rate limiting check."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test",
            rate_limit=10,
            usage_count=5
        )
        
        assert not api_key.is_rate_limited()
        
        api_key.usage_count = 10
        assert api_key.is_rate_limited()


class TestJobModel:
    """Test Job model functionality."""

    def test_job_creation(self):
        """Test creating a job model."""
        job_id = uuid4()
        api_key_id = uuid4()
        
        job = Job(
            id=job_id,
            type=JobType.CONVERT,
            status=JobStatus.PENDING,
            priority=1,
            input_file="test.mp4",
            output_file="output.mp4",
            parameters={"codec": "h264"},
            api_key_id=api_key_id
        )
        
        assert job.id == job_id
        assert job.type == JobType.CONVERT
        assert job.status == JobStatus.PENDING
        assert job.priority == 1
        assert job.input_file == "test.mp4"
        assert job.output_file == "output.mp4"
        assert job.parameters == {"codec": "h264"}
        assert job.api_key_id == api_key_id

    def test_job_defaults(self):
        """Test job model defaults."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        assert job.status == JobStatus.PENDING
        assert job.priority == 1
        assert job.progress == 0.0
        assert job.parameters == {}
        assert job.error_message is None
        assert job.started_at is None
        assert job.completed_at is None

    def test_job_string_representation(self):
        """Test job string representation."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        str_repr = str(job)
        assert "convert" in str_repr
        assert "test.mp4" in str_repr

    def test_job_start(self):
        """Test starting a job."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        job.start()
        assert job.status == JobStatus.PROCESSING
        assert job.started_at is not None

    def test_job_complete(self):
        """Test completing a job."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        job.complete()
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100.0
        assert job.completed_at is not None

    def test_job_fail(self):
        """Test failing a job."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        error_msg = "Processing failed"
        job.fail(error_msg)
        assert job.status == JobStatus.FAILED
        assert job.error_message == error_msg
        assert job.completed_at is not None

    def test_job_cancel(self):
        """Test canceling a job."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        job.cancel()
        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None

    def test_job_update_progress(self):
        """Test updating job progress."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        job.update_progress(50.0)
        assert job.progress == 50.0

    def test_job_duration(self):
        """Test job duration calculation."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        # Job not started yet
        assert job.duration is None
        
        # Start job
        job.start()
        assert job.duration is not None
        
        # Complete job
        job.complete()
        duration = job.duration
        assert duration is not None
        assert duration > 0

    def test_job_is_terminal(self):
        """Test checking if job is in terminal state."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        # Pending job is not terminal
        assert not job.is_terminal()
        
        # Processing job is not terminal
        job.status = JobStatus.PROCESSING
        assert not job.is_terminal()
        
        # Completed job is terminal
        job.status = JobStatus.COMPLETED
        assert job.is_terminal()
        
        # Failed job is terminal
        job.status = JobStatus.FAILED
        assert job.is_terminal()
        
        # Cancelled job is terminal
        job.status = JobStatus.CANCELLED
        assert job.is_terminal()

    def test_job_can_be_cancelled(self):
        """Test checking if job can be cancelled."""
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=uuid4()
        )
        
        # Pending job can be cancelled
        assert job.can_be_cancelled()
        
        # Processing job can be cancelled
        job.status = JobStatus.PROCESSING
        assert job.can_be_cancelled()
        
        # Completed job cannot be cancelled
        job.status = JobStatus.COMPLETED
        assert not job.can_be_cancelled()
        
        # Failed job cannot be cancelled
        job.status = JobStatus.FAILED
        assert not job.can_be_cancelled()
        
        # Already cancelled job cannot be cancelled
        job.status = JobStatus.CANCELLED
        assert not job.can_be_cancelled()


class TestJobTypes:
    """Test job type enumeration."""

    def test_job_type_values(self):
        """Test job type enum values."""
        assert JobType.CONVERT == "convert"
        assert JobType.COMPRESS == "compress"
        assert JobType.EXTRACT_AUDIO == "extract_audio"
        assert JobType.THUMBNAIL == "thumbnail"
        assert JobType.ANALYZE == "analyze"
        assert JobType.BATCH == "batch"

    def test_job_type_iteration(self):
        """Test iterating over job types."""
        job_types = list(JobType)
        assert len(job_types) == 6
        assert JobType.CONVERT in job_types
        assert JobType.BATCH in job_types


class TestJobStatuses:
    """Test job status enumeration."""

    def test_job_status_values(self):
        """Test job status enum values."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.PROCESSING == "processing"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"

    def test_job_status_iteration(self):
        """Test iterating over job statuses."""
        job_statuses = list(JobStatus)
        assert len(job_statuses) == 5
        assert JobStatus.PENDING in job_statuses
        assert JobStatus.CANCELLED in job_statuses


class TestModelRelationships:
    """Test model relationships."""

    def test_api_key_job_relationship(self):
        """Test relationship between API key and jobs."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hashed_value",
            key_prefix="sk-test"
        )
        
        job = Job(
            type=JobType.CONVERT,
            input_file="test.mp4",
            output_file="output.mp4",
            api_key_id=api_key.id
        )
        
        # In a real database, this would be a foreign key relationship
        assert job.api_key_id == api_key.id


class TestAPIKeyService:
    """Test API key service model interactions."""

    def test_generate_key_format(self):
        """Test generated key format."""
        key, hash_value = APIKeyService._generate_key()
        
        assert key.startswith("sk-")
        assert len(key) == 51  # sk- + 48 chars
        assert len(hash_value) == 64  # SHA256 hex
        assert key != hash_value

    def test_hash_key_consistency(self):
        """Test key hashing consistency."""
        key = "test_key_123"
        hash1 = APIKeyService._hash_key(key)
        hash2 = APIKeyService._hash_key(key)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

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