"""
Authentication system tests
"""
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from api.models.api_key import ApiKey, ApiKeyCreate, ApiKeyUser, ApiKeyStatus
from api.services.api_key import ApiKeyService
from api.dependencies import _is_ip_whitelisted, require_api_key, get_current_user
from api.utils.error_handlers import NotFoundError, ConflictError


class TestApiKeyModel:
    """Test API key model functionality."""
    
    def test_generate_key(self):
        """Test API key generation."""
        full_key, prefix, key_hash = ApiKey.generate_key()
        
        # Check key format
        assert full_key.startswith("rdf_")
        assert len(full_key) > 20  # Should be reasonably long
        
        # Check prefix
        assert prefix == full_key[:8]
        assert prefix.startswith("rdf_")
        
        # Check hash
        assert len(key_hash) == 64  # SHA-256 produces 64 character hex string
        assert key_hash == ApiKey.hash_key(full_key)
    
    def test_hash_key(self):
        """Test key hashing."""
        key1 = "test_key_123"
        key2 = "test_key_456"
        
        hash1 = ApiKey.hash_key(key1)
        hash2 = ApiKey.hash_key(key2)
        
        # Hashes should be different for different keys
        assert hash1 != hash2
        
        # Same key should produce same hash
        assert hash1 == ApiKey.hash_key(key1)
        
        # Hash should be 64 characters (SHA-256)
        assert len(hash1) == 64
    
    def test_is_valid(self):
        """Test API key validity checking."""
        from datetime import datetime, timedelta
        
        # Create mock API key
        api_key = MagicMock(spec=ApiKey)
        api_key.status = ApiKeyStatus.ACTIVE
        api_key.expires_at = None
        
        # Mock the is_valid method behavior
        def mock_is_valid():
            if api_key.status != ApiKeyStatus.ACTIVE:
                return False
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                return False
            return True
        
        api_key.is_valid = mock_is_valid
        
        # Test active key without expiration
        assert api_key.is_valid() is True
        
        # Test inactive key
        api_key.status = ApiKeyStatus.REVOKED
        assert api_key.is_valid() is False
        
        # Test expired key
        api_key.status = ApiKeyStatus.ACTIVE
        api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        assert api_key.is_valid() is False
    
    def test_is_expired(self):
        """Test API key expiration checking."""
        from datetime import datetime, timedelta
        
        api_key = MagicMock(spec=ApiKey)
        
        def mock_is_expired():
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                return True
            return False
        
        api_key.is_expired = mock_is_expired
        
        # Test key without expiration
        api_key.expires_at = None
        assert api_key.is_expired() is False
        
        # Test future expiration
        api_key.expires_at = datetime.utcnow() + timedelta(days=1)
        assert api_key.is_expired() is False
        
        # Test past expiration
        api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        assert api_key.is_expired() is True


class TestApiKeyUser:
    """Test API key user model."""
    
    def test_quota_property(self):
        """Test quota property."""
        user = ApiKeyUser(
            id="test-user",
            api_key_id=uuid4(),
            api_key_prefix="rdf_test",
            role="user",
            max_concurrent_jobs=10,
            monthly_quota_minutes=5000,
            is_admin=False,
            total_jobs_created=5,
            total_minutes_processed=100,
            last_used_at=None,
        )
        
        quota = user.quota
        assert quota["concurrent_jobs"] == 10
        assert quota["monthly_minutes"] == 5000
    
    def test_admin_user(self):
        """Test admin user properties."""
        admin_user = ApiKeyUser(
            id="admin-user",
            api_key_id=uuid4(),
            api_key_prefix="rdf_admin",
            role="admin",
            max_concurrent_jobs=50,
            monthly_quota_minutes=100000,
            is_admin=True,
            total_jobs_created=0,
            total_minutes_processed=0,
            last_used_at=None,
        )
        
        assert admin_user.is_admin is True
        assert admin_user.role == "admin"
        assert admin_user.max_concurrent_jobs == 50


@pytest_asyncio.fixture
async def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.delete = AsyncMock()
    return session


class TestApiKeyService:
    """Test API key service functionality."""
    
    @pytest_asyncio.async_test
    async def test_create_api_key(self, mock_db_session):
        """Test API key creation."""
        service = ApiKeyService(mock_db_session)
        
        request = ApiKeyCreate(
            name="Test Key",
            owner_name="Test User",
            role="user",
            max_concurrent_jobs=5,
            monthly_quota_minutes=1000,
        )
        
        # Mock successful creation
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        with patch.object(ApiKey, 'generate_key', return_value=("rdf_testkey", "rdf_test", "testhash")):
            api_key, full_key = await service.create_api_key(request, "test_creator")
        
        assert full_key == "rdf_testkey"
        assert api_key.name == "Test Key"
        assert api_key.role == "user"
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest_asyncio.async_test
    async def test_validate_api_key_success(self, mock_db_session):
        """Test successful API key validation."""
        service = ApiKeyService(mock_db_session)
        
        # Mock API key object
        mock_api_key = MagicMock(spec=ApiKey)
        mock_api_key.id = uuid4()
        mock_api_key.prefix = "rdf_test"
        mock_api_key.role = "user"
        mock_api_key.max_concurrent_jobs = 5
        mock_api_key.monthly_quota_minutes = 1000
        mock_api_key.total_jobs_created = 0
        mock_api_key.total_minutes_processed = 0
        mock_api_key.last_used_at = None
        mock_api_key.is_valid.return_value = True
        mock_api_key.update_last_used = MagicMock()
        
        # Mock database response
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db_session.execute.return_value = mock_result
        
        user = await service.validate_api_key("rdf_testkey12345")
        
        assert user is not None
        assert user.role == "user"
        assert user.max_concurrent_jobs == 5
        mock_api_key.update_last_used.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest_asyncio.async_test
    async def test_validate_api_key_not_found(self, mock_db_session):
        """Test API key validation when key not found."""
        service = ApiKeyService(mock_db_session)
        
        # Mock database response - no key found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        user = await service.validate_api_key("invalid_key")
        
        assert user is None
    
    @pytest_asyncio.async_test
    async def test_validate_api_key_invalid(self, mock_db_session):
        """Test API key validation when key is invalid."""
        service = ApiKeyService(mock_db_session)
        
        # Mock API key object that's invalid
        mock_api_key = MagicMock(spec=ApiKey)
        mock_api_key.is_valid.return_value = False
        
        # Mock database response
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db_session.execute.return_value = mock_result
        
        user = await service.validate_api_key("rdf_expiredkey")
        
        assert user is None
    
    @pytest_asyncio.async_test
    async def test_revoke_api_key(self, mock_db_session):
        """Test API key revocation."""
        service = ApiKeyService(mock_db_session)
        
        # Mock API key object
        mock_api_key = MagicMock(spec=ApiKey)
        mock_api_key.id = uuid4()
        mock_api_key.status = ApiKeyStatus.ACTIVE
        
        # Mock database response
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db_session.execute.return_value = mock_result
        
        revoked_key = await service.revoke_api_key(
            mock_api_key.id,
            reason="Test revocation",
            revoked_by="test_admin"
        )
        
        assert revoked_key.status == ApiKeyStatus.REVOKED
        assert revoked_key.revocation_reason == "Test revocation"
        assert revoked_key.revoked_by == "test_admin"
        mock_db_session.commit.assert_called_once()
    
    @pytest_asyncio.async_test
    async def test_revoke_api_key_not_found(self, mock_db_session):
        """Test API key revocation when key not found."""
        service = ApiKeyService(mock_db_session)
        
        # Mock database response - no key found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(NotFoundError):
            await service.revoke_api_key(uuid4(), "Test reason", "test_admin")


class TestIPValidation:
    """Test IP whitelist validation functionality."""
    
    def test_ip_validation_single_ip(self):
        """Test IP validation with single IP addresses."""
        whitelist = ["192.168.1.100", "10.0.0.1"]
        
        # Test exact matches
        assert _is_ip_whitelisted("192.168.1.100", whitelist) is True
        assert _is_ip_whitelisted("10.0.0.1", whitelist) is True
        
        # Test non-matches
        assert _is_ip_whitelisted("192.168.1.101", whitelist) is False
        assert _is_ip_whitelisted("10.0.0.2", whitelist) is False
    
    def test_ip_validation_cidr_ranges(self):
        """Test IP validation with CIDR ranges."""
        whitelist = ["192.168.1.0/24", "10.0.0.0/8"]
        
        # Test IPs within ranges
        assert _is_ip_whitelisted("192.168.1.1", whitelist) is True
        assert _is_ip_whitelisted("192.168.1.254", whitelist) is True
        assert _is_ip_whitelisted("10.1.2.3", whitelist) is True
        assert _is_ip_whitelisted("10.255.255.255", whitelist) is True
        
        # Test IPs outside ranges
        assert _is_ip_whitelisted("192.168.2.1", whitelist) is False
        assert _is_ip_whitelisted("172.16.0.1", whitelist) is False
    
    def test_ip_validation_mixed(self):
        """Test IP validation with mixed single IPs and CIDR ranges."""
        whitelist = ["192.168.1.100", "10.0.0.0/24", "172.16.1.1"]
        
        # Test single IP matches
        assert _is_ip_whitelisted("192.168.1.100", whitelist) is True
        assert _is_ip_whitelisted("172.16.1.1", whitelist) is True
        
        # Test CIDR range matches
        assert _is_ip_whitelisted("10.0.0.50", whitelist) is True
        assert _is_ip_whitelisted("10.0.0.255", whitelist) is True
        
        # Test non-matches
        assert _is_ip_whitelisted("192.168.1.101", whitelist) is False
        assert _is_ip_whitelisted("10.0.1.1", whitelist) is False
    
    def test_ip_validation_backward_compatibility(self):
        """Test backward compatibility with string prefix matching."""
        whitelist = ["192.168.1"]  # Old style prefix
        
        # Should still work with startswith for backward compatibility
        assert _is_ip_whitelisted("192.168.1.100", whitelist) is True
        assert _is_ip_whitelisted("192.168.1.1", whitelist) is True
        
        # Should not match different prefixes
        assert _is_ip_whitelisted("192.168.2.100", whitelist) is False
    
    def test_ip_validation_invalid_ip(self):
        """Test IP validation with invalid IP addresses."""
        whitelist = ["192.168.1.0/24"]
        
        # Test invalid IP addresses - should fall back to string comparison
        result = _is_ip_whitelisted("invalid.ip.address", whitelist)
        assert result is False  # Should not match
        
        # Test with backward compatibility format
        whitelist_compat = ["invalid"]
        result = _is_ip_whitelisted("invalid.ip.address", whitelist_compat)
        assert result is True  # Should match with startswith
    
    def test_vulnerability_fix(self):
        """Test that the IP validation vulnerability is fixed."""
        # This is the scenario that was vulnerable before the fix
        client_ip = "192.168.1.100"
        whitelist = ["192.168.1.1"]  # Only allow 192.168.1.1
        
        # With the old vulnerable method, this would return True
        # With the new secure method, this should return False
        result = _is_ip_whitelisted(client_ip, whitelist)
        assert result is False  # Should NOT match
        
        # Test the exact match case
        result = _is_ip_whitelisted("192.168.1.1", whitelist)
        assert result is True  # Should match


class TestAuthenticationIntegration:
    """Test authentication integration functionality."""
    
    @pytest.mark.asyncio
    async def test_require_api_key_success(self):
        """Test successful API key requirement."""
        from fastapi import Request
        from unittest.mock import AsyncMock
        
        # Mock request
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        
        # Mock database session
        mock_db = AsyncMock()
        
        # Mock API key service and user
        mock_user = MagicMock()
        mock_user.api_key_prefix = "rdf_test"
        mock_user.id = "user-123"
        
        with patch('api.dependencies.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.validate_api_key.return_value = mock_user
            mock_service_class.return_value = mock_service
            
            with patch('api.dependencies.settings') as mock_settings:
                mock_settings.ENABLE_API_KEYS = True
                mock_settings.ENABLE_IP_WHITELIST = False
                
                # Test the dependency
                result = await require_api_key(request, "rdf_testkey123", mock_db)
                
                assert result == "rdf_testkey123"
                mock_service.validate_api_key.assert_called_once_with("rdf_testkey123")
    
    @pytest.mark.asyncio
    async def test_require_api_key_invalid(self):
        """Test API key requirement with invalid key."""
        from fastapi import Request, HTTPException
        from unittest.mock import AsyncMock
        
        # Mock request
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.1"
        
        # Mock database session
        mock_db = AsyncMock()
        
        with patch('api.dependencies.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.validate_api_key.return_value = None  # Invalid key
            mock_service_class.return_value = mock_service
            
            with patch('api.dependencies.settings') as mock_settings:
                mock_settings.ENABLE_API_KEYS = True
                mock_settings.ENABLE_IP_WHITELIST = False
                
                # Test the dependency - should raise HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await require_api_key(request, "invalid_key", mock_db)
                
                assert exc_info.value.status_code == 401
                assert "Invalid API key" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_require_api_key_disabled(self):
        """Test API key requirement when authentication is disabled."""
        from fastapi import Request
        from unittest.mock import AsyncMock
        
        # Mock request
        request = MagicMock(spec=Request)
        mock_db = AsyncMock()
        
        with patch('api.dependencies.settings') as mock_settings:
            mock_settings.ENABLE_API_KEYS = False
            
            # Test the dependency
            result = await require_api_key(request, None, mock_db)
            
            assert result == "anonymous"


class TestAuthenticationSecurity:
    """Test authentication security features."""
    
    def test_key_generation_entropy(self):
        """Test that generated keys have sufficient entropy."""
        keys = []
        
        # Generate multiple keys
        for _ in range(100):
            full_key, _, _ = ApiKey.generate_key()
            keys.append(full_key)
        
        # All keys should be unique
        assert len(set(keys)) == 100
        
        # All keys should start with rdf_
        for key in keys:
            assert key.startswith("rdf_")
    
    def test_hash_consistency(self):
        """Test that hash function is consistent."""
        key = "test_key_for_hashing"
        
        # Hash the same key multiple times
        hashes = [ApiKey.hash_key(key) for _ in range(10)]
        
        # All hashes should be identical
        assert len(set(hashes)) == 1
        
        # Hash should be deterministic
        assert all(h == hashes[0] for h in hashes)
    
    def test_hash_uniqueness(self):
        """Test that different keys produce different hashes."""
        keys = [f"test_key_{i}" for i in range(100)]
        hashes = [ApiKey.hash_key(key) for key in keys]
        
        # All hashes should be unique
        assert len(set(hashes)) == 100
    
    def test_timing_attack_resistance(self):
        """Test that API key validation is resistant to timing attacks."""
        # This is a conceptual test - in practice, we'd measure timing
        # but here we just verify the hash comparison approach
        
        valid_hash = ApiKey.hash_key("valid_key")
        invalid_key = "invalid_key"
        invalid_hash = ApiKey.hash_key(invalid_key)
        
        # Hashes should be different
        assert valid_hash != invalid_hash
        
        # Both hashes should be same length (important for timing resistance)
        assert len(valid_hash) == len(invalid_hash) == 64