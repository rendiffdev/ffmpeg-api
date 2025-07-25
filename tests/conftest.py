"""
Test configuration and fixtures
"""
import pytest
import asyncio
from typing import Generator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from api.models.database import Base
from api.models.api_key import APIKey
from api.models.job import Job, JobStatus, JobType


# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    """Create async database engine for testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    """Create async database session for testing."""
    async_session_maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_api_key():
    """Create a mock API key for testing."""
    return APIKey(
        id=uuid4(),
        name="Test API Key",
        key_hash="hashed_test_key",
        key_prefix="sk-test",
        is_active=True,
        rate_limit=1000,
        usage_count=0
    )


@pytest.fixture
def mock_job():
    """Create a mock job for testing."""
    return Job(
        id=uuid4(),
        type=JobType.CONVERT,
        status=JobStatus.PENDING,
        priority=1,
        input_file="test_input.mp4",
        output_file="test_output.mp4",
        parameters={"codec": "h264", "bitrate": "1000k"},
        progress=0.0,
        api_key_id=uuid4()
    )


@pytest.fixture
def auth_headers():
    """Create authentication headers for testing."""
    return {"X-API-Key": "sk-test_valid_key_for_testing"}


@pytest.fixture
def mock_async_session():
    """Create a mock async session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = False
    return mock_redis


@pytest.fixture
def mock_celery_app():
    """Create a mock Celery app."""
    mock_celery = MagicMock()
    mock_celery.send_task.return_value = MagicMock(id="test-task-id")
    return mock_celery


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "type": "convert",
        "input_file": "input.mp4",
        "output_file": "output.mp4",
        "parameters": {
            "codec": "h264",
            "bitrate": "1000k",
            "resolution": "1920x1080"
        },
        "priority": 1
    }


@pytest.fixture
def sample_api_key_data():
    """Sample API key data for testing."""
    return {
        "name": "Test API Key",
        "rate_limit": 1000,
        "description": "API key for testing"
    }


@pytest.fixture
def mock_file_upload():
    """Create a mock file upload."""
    mock_file = MagicMock()
    mock_file.filename = "test.mp4"
    mock_file.content_type = "video/mp4"
    mock_file.size = 1024 * 1024  # 1MB
    mock_file.read.return_value = b"fake video content"
    return mock_file


@pytest.fixture
def mock_storage():
    """Create a mock storage client."""
    mock_storage = MagicMock()
    mock_storage.upload_file.return_value = "https://storage.example.com/file.mp4"
    mock_storage.download_file.return_value = b"fake video content"
    mock_storage.delete_file.return_value = True
    mock_storage.file_exists.return_value = True
    return mock_storage


@pytest.fixture
def mock_ffmpeg():
    """Create a mock FFmpeg wrapper."""
    mock_ffmpeg = MagicMock()
    mock_ffmpeg.probe.return_value = {
        "format": {
            "duration": "60.0",
            "size": "1048576"
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080
            }
        ]
    }
    mock_ffmpeg.run.return_value = (None, None)
    return mock_ffmpeg


@pytest.fixture
def mock_webhook():
    """Create a mock webhook client."""
    mock_webhook = MagicMock()
    mock_webhook.send_notification.return_value = True
    return mock_webhook


@pytest.fixture
def mock_metrics():
    """Create a mock metrics client."""
    mock_metrics = MagicMock()
    mock_metrics.increment.return_value = None
    mock_metrics.gauge.return_value = None
    mock_metrics.histogram.return_value = None
    return mock_metrics


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    mock_logger = MagicMock()
    mock_logger.info.return_value = None
    mock_logger.warning.return_value = None
    mock_logger.error.return_value = None
    mock_logger.debug.return_value = None
    return mock_logger


# Database fixtures for integration tests
@pytest.fixture
async def test_api_key(async_session):
    """Create a test API key in the database."""
    api_key = APIKey(
        name="Test API Key",
        key_hash="hashed_test_key",
        key_prefix="sk-test",
        is_active=True,
        rate_limit=1000
    )
    
    async_session.add(api_key)
    await async_session.commit()
    await async_session.refresh(api_key)
    
    return api_key


@pytest.fixture
async def test_job(async_session, test_api_key):
    """Create a test job in the database."""
    job = Job(
        type=JobType.CONVERT,
        status=JobStatus.PENDING,
        priority=1,
        input_file="test_input.mp4",
        output_file="test_output.mp4",
        parameters={"codec": "h264"},
        api_key_id=test_api_key.id
    )
    
    async_session.add(job)
    await async_session.commit()
    await async_session.refresh(job)
    
    return job


# Test utilities
class TestUtils:
    """Utility functions for testing."""
    
    @staticmethod
    def create_mock_job(job_type: JobType = JobType.CONVERT, 
                       status: JobStatus = JobStatus.PENDING) -> Job:
        """Create a mock job with specified parameters."""
        return Job(
            id=uuid4(),
            type=job_type,
            status=status,
            priority=1,
            input_file="test.mp4",
            output_file="output.mp4",
            parameters={"codec": "h264"},
            api_key_id=uuid4()
        )
    
    @staticmethod
    def create_mock_api_key(name: str = "Test Key", 
                           is_active: bool = True) -> APIKey:
        """Create a mock API key with specified parameters."""
        return APIKey(
            id=uuid4(),
            name=name,
            key_hash="hashed_value",
            key_prefix="sk-test",
            is_active=is_active,
            rate_limit=1000,
            usage_count=0
        )


@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtils