"""
Test configuration and fixtures for Rendiff FFmpeg API
"""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Import our application components
from api.main import app
from api.config import settings
from api.models.database import Base, get_session, init_db
from api.models.api_key import ApiKey, ApiKeyCreate
from api.models.job import Job
from api.services.api_key import ApiKeyService
from api.dependencies import get_current_user, get_db


# ==================== Test Database Setup ====================

@pytest_asyncio.fixture(scope="session")
async def test_db_engine():
    """Create test database engine."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,  # Set to True for SQL debugging
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_db_engine):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def override_db_dependency(test_db_session):
    """Override the database dependency for testing."""
    async def _get_test_db():
        yield test_db_session
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


# ==================== Authentication Fixtures ====================

@pytest_asyncio.fixture
async def test_api_key(test_db_session):
    """Create a test API key."""
    service = ApiKeyService(test_db_session)
    
    request = ApiKeyCreate(
        name="Test API Key",
        owner_name="Test User",
        role="user",
        max_concurrent_jobs=5,
        monthly_quota_minutes=1000,
    )
    
    api_key_obj, full_key = await service.create_api_key(
        request=request,
        created_by="test_fixture",
    )
    
    return {
        "api_key_obj": api_key_obj,
        "full_key": full_key,
        "prefix": api_key_obj.prefix,
        "id": api_key_obj.id,
    }


@pytest_asyncio.fixture
async def test_admin_api_key(test_db_session):
    """Create a test admin API key."""
    service = ApiKeyService(test_db_session)
    
    request = ApiKeyCreate(
        name="Test Admin Key",
        owner_name="Test Admin",
        role="admin",
        max_concurrent_jobs=50,
        monthly_quota_minutes=10000,
    )
    
    api_key_obj, full_key = await service.create_api_key(
        request=request,
        created_by="test_fixture",
    )
    
    return {
        "api_key_obj": api_key_obj,
        "full_key": full_key,
        "prefix": api_key_obj.prefix,
        "id": api_key_obj.id,
    }


@pytest.fixture
def mock_user_dependency():
    """Mock the get_current_user dependency for testing."""
    from api.models.api_key import ApiKeyUser
    
    def _create_mock_user(is_admin=False, api_key="test-key"):
        mock_user = ApiKeyUser(
            id="test-user-123",
            api_key_id=None,
            api_key_prefix="test",
            role="admin" if is_admin else "user",
            max_concurrent_jobs=5,
            monthly_quota_minutes=1000,
            is_admin=is_admin,
            total_jobs_created=0,
            total_minutes_processed=0,
            last_used_at=None,
        )
        return mock_user, api_key
    
    return _create_mock_user


@pytest.fixture
def auth_headers(test_api_key):
    """Create authentication headers for API requests."""
    if isinstance(test_api_key, dict):
        api_key = test_api_key["full_key"]
    else:
        api_key = "test-api-key"
    
    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }


@pytest.fixture
def admin_auth_headers(test_admin_api_key):
    """Create admin authentication headers for API requests."""
    if isinstance(test_admin_api_key, dict):
        api_key = test_admin_api_key["full_key"]
    else:
        api_key = "test-admin-key"
    
    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }


# ==================== Test Client Setup ====================

@pytest.fixture
def client(override_db_dependency):
    """Create test client with database override."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client, test_api_key, mock_user_dependency):
    """Create authenticated test client."""
    # Mock the authentication for testing
    mock_user = mock_user_dependency(is_admin=False, api_key=test_api_key["full_key"])
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    yield client
    
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def admin_client(client, test_admin_api_key, mock_user_dependency):
    """Create admin authenticated test client."""
    # Mock the authentication for testing
    mock_user = mock_user_dependency(is_admin=True, api_key=test_admin_api_key["full_key"])
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    yield client
    
    app.dependency_overrides.pop(get_current_user, None)


# ==================== Storage and File Fixtures ====================

@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_video_file(temp_storage_dir):
    """Create a sample video file for testing."""
    video_file = temp_storage_dir / "sample.mp4"
    
    # Create a minimal video file (just headers for testing)
    video_file.write_bytes(b'\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41isom')
    
    return video_file


@pytest.fixture
def sample_audio_file(temp_storage_dir):
    """Create a sample audio file for testing."""
    audio_file = temp_storage_dir / "sample.mp3"
    
    # Create a minimal MP3 file (just headers for testing)
    audio_file.write_bytes(b'\xFF\xFB\x90\x00' + b'\x00' * 100)
    
    return audio_file


# ==================== Mock Service Fixtures ====================

@pytest.fixture
def mock_queue_service():
    """Mock queue service for testing."""
    from tests.mocks.queue import MockQueueService
    return MockQueueService()


@pytest.fixture
def mock_storage_service():
    """Mock storage service for testing."""
    from tests.mocks.storage import MockStorageBackend
    config = {"type": "local", "base_path": "/tmp/test"}
    return MockStorageBackend(config)


@pytest.fixture
def mock_ffmpeg():
    """Mock FFmpeg for testing."""
    from tests.mocks.ffmpeg import MockFFmpegWrapper
    return MockFFmpegWrapper()


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    from tests.mocks.queue import MockRedis
    return MockRedis()


@pytest.fixture
def mock_celery_app():
    """Mock Celery application for testing."""
    from tests.mocks.queue import MockCeleryApp
    return MockCeleryApp()


# ==================== Test Data Fixtures ====================

@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "input": "test-input.mp4",
        "output": "test-output.mp4",
        "operations": [
            {
                "type": "convert",
                "format": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac"
            }
        ],
        "options": {
            "quality": "high",
            "optimize_for_streaming": True
        },
        "priority": "normal"
    }


@pytest.fixture
def sample_convert_request():
    """Sample convert request for testing."""
    return {
        "input": {
            "path": "input/video.mp4",
            "storage": "local"
        },
        "output": {
            "path": "output/converted.mp4",
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
            "quality": "medium"
        }
    }


# ==================== Database Test Data ====================

@pytest_asyncio.fixture
async def sample_jobs(test_db_session, test_api_key):
    """Create sample jobs in the test database."""
    jobs = []
    
    for i in range(3):
        job = Job(
            status=["queued", "processing", "completed"][i],
            input_path=f"input/video{i+1}.mp4",
            output_path=f"output/video{i+1}.mp4",
            api_key=test_api_key["full_key"],
            progress=float(i * 33.33),
            stage=["queued", "processing", "completed"][i],
        )
        test_db_session.add(job)
    
    await test_db_session.commit()
    
    # Refresh to get IDs
    for job in jobs:
        await test_db_session.refresh(job)
    
    return jobs


# ==================== Configuration Fixtures ====================

@pytest.fixture(scope="session")
def test_settings():
    """Test-specific settings."""
    original_env = {}
    
    # Store original environment variables
    test_env_vars = [
        "DATABASE_URL",
        "REDIS_URL",
        "ENABLE_API_KEYS",
        "ENABLE_IP_WHITELIST",
        "DEBUG",
        "TESTING",
    ]
    
    for var in test_env_vars:
        original_env[var] = os.environ.get(var)
    
    # Set test environment variables
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Use different DB for tests
    os.environ["ENABLE_API_KEYS"] = "true"
    os.environ["ENABLE_IP_WHITELIST"] = "false"
    os.environ["DEBUG"] = "true"
    os.environ["TESTING"] = "true"
    
    yield
    
    # Restore original environment variables
    for var, value in original_env.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value


# ==================== Async Fixtures Support ====================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== Helper Functions ====================

def assert_job_response(response_data, expected_status=None):
    """Helper function to assert job response structure."""
    assert "id" in response_data
    assert "status" in response_data
    assert "created_at" in response_data
    assert "progress" in response_data
    
    if expected_status:
        assert response_data["status"] == expected_status


def assert_error_response(response_data, expected_code=None):
    """Helper function to assert error response structure."""
    assert "error" in response_data
    error = response_data["error"]
    assert "code" in error
    assert "message" in error
    
    if expected_code:
        assert error["code"] == expected_code


# ==================== Test Markers Setup ====================

# Custom pytest markers for categorizing tests
pytest_plugins = ["pytest_asyncio"]

# Configure test timeout
pytest.mark.timeout = pytest.mark.timeout(300)  # 5 minutes default timeout