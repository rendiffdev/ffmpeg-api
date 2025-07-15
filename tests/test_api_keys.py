"""
Test API key authentication and management
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from api.main import app
from api.models.api_key import APIKey
from api.services.api_key import APIKeyService


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_api_key():
    """Mock API key for testing."""
    return APIKey(
        id="test-key-id",
        name="Test Key",
        key_hash="hashed_key_value",
        key_prefix="sk-test",
        is_active=True,
        usage_count=5,
        rate_limit=1000
    )


class TestAPIKeyAuthentication:
    """Test API key authentication."""

    @patch('api.services.api_key.APIKeyService.validate_api_key')
    def test_valid_api_key(self, mock_validate, client, mock_api_key):
        """Test valid API key authentication."""
        mock_validate.return_value = mock_api_key
        
        response = client.get(
            "/api/v1/jobs",
            headers={"X-API-Key": "sk-test_valid_key"}
        )
        
        assert response.status_code == 200
        mock_validate.assert_called_once()

    @patch('api.services.api_key.APIKeyService.validate_api_key')
    def test_invalid_api_key(self, mock_validate, client):
        """Test invalid API key rejection."""
        mock_validate.return_value = None
        
        response = client.get(
            "/api/v1/jobs",
            headers={"X-API-Key": "sk-invalid_key"}
        )
        
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_missing_api_key(self, client):
        """Test missing API key rejection."""
        response = client.get("/api/v1/jobs")
        
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    @patch('api.services.api_key.APIKeyService.validate_api_key')
    def test_inactive_api_key(self, mock_validate, client):
        """Test inactive API key rejection."""
        inactive_key = APIKey(
            id="inactive-key",
            name="Inactive Key",
            key_hash="hash",
            key_prefix="sk-test",
            is_active=False
        )
        mock_validate.return_value = inactive_key
        
        response = client.get(
            "/api/v1/jobs",
            headers={"X-API-Key": "sk-test_inactive"}
        )
        
        # Should be rejected during validation
        assert response.status_code == 401


class TestAPIKeyService:
    """Test API key service functionality."""

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, mock_api_key):
        """Test successful API key validation."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('api.services.api_key.APIKeyService._get_key_by_prefix') as mock_get:
            mock_get.return_value = mock_api_key
            
            result = await APIKeyService.validate_api_key(
                mock_session, "sk-test_valid_key"
            )
            
            assert result == mock_api_key
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_api_key_not_found(self):
        """Test API key validation with non-existent key."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('api.services.api_key.APIKeyService._get_key_by_prefix') as mock_get:
            mock_get.return_value = None
            
            result = await APIKeyService.validate_api_key(
                mock_session, "sk-nonexistent"
            )
            
            assert result is None

    @pytest.mark.asyncio
    async def test_create_api_key(self):
        """Test API key creation."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        with patch('api.services.api_key.APIKeyService._generate_key') as mock_gen:
            mock_gen.return_value = ("sk-test_new_key", "hashed_value")
            
            result = await APIKeyService.create_api_key(
                mock_session, "Test Key", rate_limit=500
            )
            
            assert result["key"].startswith("sk-test_")
            assert result["name"] == "Test Key"
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

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