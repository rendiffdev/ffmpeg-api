"""
API Key management endpoint tests
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from api.models.api_key import ApiKeyStatus


class TestApiKeyEndpoints:
    """Test API key management endpoints."""
    
    @pytest.mark.unit
    def test_create_api_key_success(self, admin_client, admin_auth_headers):
        """Test successful API key creation."""
        request_data = {
            "name": "Test API Key",
            "owner_name": "Test User",
            "role": "user",
            "max_concurrent_jobs": 10,
            "monthly_quota_minutes": 5000,
        }
        
        # Mock the service response
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            mock_api_key = MagicMock()
            mock_api_key.id = uuid4()
            mock_api_key.name = "Test API Key"
            mock_api_key.prefix = "rdf_test"
            mock_api_key.status = ApiKeyStatus.ACTIVE
            mock_api_key.role = "user"
            mock_api_key.max_concurrent_jobs = 10
            mock_api_key.monthly_quota_minutes = 5000
            mock_api_key.total_jobs_created = 0
            mock_api_key.total_minutes_processed = 0
            mock_api_key.last_used_at = None
            mock_api_key.created_at = "2024-07-10T10:00:00Z"
            mock_api_key.expires_at = None
            mock_api_key.owner_name = "Test User"
            
            mock_service.create_api_key.return_value = (mock_api_key, "rdf_testkey123456789")
            mock_service_class.return_value = mock_service
            
            response = admin_client.post(
                "/api/v1/admin/api-keys/",
                json=request_data,
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "api_key" in data
            assert "key" in data
            assert "warning" in data
            
            api_key_data = data["api_key"]
            assert api_key_data["name"] == "Test API Key"
            assert api_key_data["role"] == "user"
            assert api_key_data["status"] == "active"
            
            # Full key should be returned only once
            assert data["key"] == "rdf_testkey123456789"
            assert "Store this key securely" in data["warning"]
    
    @pytest.mark.unit
    def test_create_api_key_unauthorized(self, client, auth_headers):
        """Test API key creation without admin privileges."""
        request_data = {
            "name": "Test API Key",
            "role": "user",
        }
        
        response = client.post(
            "/api/v1/admin/api-keys/",
            json=request_data,
            headers=auth_headers,
        )
        
        # Should be forbidden for non-admin users
        assert response.status_code == 403
        
        data = response.json()
        assert "error" in data
        assert "Admin access required" in data["error"]["message"]
    
    @pytest.mark.unit
    def test_create_api_key_validation_error(self, admin_client, admin_auth_headers):
        """Test API key creation with validation errors."""
        request_data = {
            "name": "",  # Empty name should fail validation
            "role": "invalid_role",  # Invalid role
            "max_concurrent_jobs": -1,  # Negative value
        }
        
        response = admin_client.post(
            "/api/v1/admin/api-keys/",
            json=request_data,
            headers=admin_auth_headers,
        )
        
        assert response.status_code == 422  # Validation error
        
        data = response.json()
        assert "detail" in data  # FastAPI validation error format
    
    @pytest.mark.unit
    def test_list_api_keys_success(self, admin_client, admin_auth_headers):
        """Test successful API key listing."""
        # Mock the service response
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            
            # Create mock API keys
            mock_keys = []
            for i in range(3):
                mock_key = MagicMock()
                mock_key.id = uuid4()
                mock_key.name = f"Test Key {i+1}"
                mock_key.prefix = f"rdf_test{i+1}"
                mock_key.status = ApiKeyStatus.ACTIVE
                mock_key.role = "user"
                mock_key.max_concurrent_jobs = 5
                mock_key.monthly_quota_minutes = 1000
                mock_key.total_jobs_created = i
                mock_key.total_minutes_processed = i * 10
                mock_key.last_used_at = None
                mock_key.created_at = "2024-07-10T10:00:00Z"
                mock_key.expires_at = None
                mock_key.owner_name = f"User {i+1}"
                mock_keys.append(mock_key)
            
            mock_service.list_api_keys.return_value = (mock_keys, 3)
            mock_service_class.return_value = mock_service
            
            response = admin_client.get(
                "/api/v1/admin/api-keys/",
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "api_keys" in data
            assert "total" in data
            assert "page" in data
            assert "per_page" in data
            assert "has_next" in data
            assert "has_prev" in data
            
            assert data["total"] == 3
            assert len(data["api_keys"]) == 3
            
            # Check first API key
            first_key = data["api_keys"][0]
            assert first_key["name"] == "Test Key 1"
            assert first_key["prefix"] == "rdf_test1"
            assert first_key["status"] == "active"
    
    @pytest.mark.unit
    def test_list_api_keys_pagination(self, admin_client, admin_auth_headers):
        """Test API key listing with pagination."""
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.list_api_keys.return_value = ([], 0)  # Empty list
            mock_service_class.return_value = mock_service
            
            response = admin_client.get(
                "/api/v1/admin/api-keys/?page=2&per_page=10&status=active",
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            
            # Verify service was called with correct parameters
            mock_service.list_api_keys.assert_called_once_with(
                page=2,
                per_page=10,
                status=ApiKeyStatus.ACTIVE,
                owner_id=None,
            )
    
    @pytest.mark.unit
    def test_get_api_key_success(self, admin_client, admin_auth_headers):
        """Test successful API key retrieval."""
        key_id = uuid4()
        
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            
            mock_key = MagicMock()
            mock_key.id = key_id
            mock_key.name = "Test Key"
            mock_key.prefix = "rdf_test"
            mock_key.status = ApiKeyStatus.ACTIVE
            mock_key.role = "user"
            mock_key.max_concurrent_jobs = 5
            mock_key.monthly_quota_minutes = 1000
            mock_key.total_jobs_created = 0
            mock_key.total_minutes_processed = 0
            mock_key.last_used_at = None
            mock_key.created_at = "2024-07-10T10:00:00Z"
            mock_key.expires_at = None
            mock_key.owner_name = "Test User"
            
            mock_service.get_api_key_by_id.return_value = mock_key
            mock_service_class.return_value = mock_service
            
            response = admin_client.get(
                f"/api/v1/admin/api-keys/{key_id}",
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["name"] == "Test Key"
            assert data["prefix"] == "rdf_test"
            assert data["status"] == "active"
    
    @pytest.mark.unit
    def test_get_api_key_not_found(self, admin_client, admin_auth_headers):
        """Test API key retrieval when key not found."""
        key_id = uuid4()
        
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_api_key_by_id.return_value = None
            mock_service_class.return_value = mock_service
            
            response = admin_client.get(
                f"/api/v1/admin/api-keys/{key_id}",
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 404
            
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()
    
    @pytest.mark.unit
    def test_update_api_key_success(self, admin_client, admin_auth_headers):
        """Test successful API key update."""
        key_id = uuid4()
        
        update_data = {
            "name": "Updated Key Name",
            "status": "inactive",
            "max_concurrent_jobs": 15,
        }
        
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            
            mock_updated_key = MagicMock()
            mock_updated_key.id = key_id
            mock_updated_key.name = "Updated Key Name"
            mock_updated_key.prefix = "rdf_test"
            mock_updated_key.status = ApiKeyStatus.INACTIVE
            mock_updated_key.role = "user"
            mock_updated_key.max_concurrent_jobs = 15
            mock_updated_key.monthly_quota_minutes = 1000
            mock_updated_key.total_jobs_created = 0
            mock_updated_key.total_minutes_processed = 0
            mock_updated_key.last_used_at = None
            mock_updated_key.created_at = "2024-07-10T10:00:00Z"
            mock_updated_key.expires_at = None
            mock_updated_key.owner_name = "Test User"
            
            mock_service.update_api_key.return_value = mock_updated_key
            mock_service_class.return_value = mock_service
            
            response = admin_client.put(
                f"/api/v1/admin/api-keys/{key_id}",
                json=update_data,
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["name"] == "Updated Key Name"
            assert data["status"] == "inactive"
            assert data["max_concurrent_jobs"] == 15
    
    @pytest.mark.unit
    def test_revoke_api_key_success(self, admin_client, admin_auth_headers):
        """Test successful API key revocation."""
        key_id = uuid4()
        
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            
            mock_revoked_key = MagicMock()
            mock_revoked_key.id = key_id
            mock_revoked_key.name = "Test Key"
            mock_revoked_key.prefix = "rdf_test"
            mock_revoked_key.status = ApiKeyStatus.REVOKED
            mock_revoked_key.role = "user"
            mock_revoked_key.max_concurrent_jobs = 5
            mock_revoked_key.monthly_quota_minutes = 1000
            mock_revoked_key.total_jobs_created = 0
            mock_revoked_key.total_minutes_processed = 0
            mock_revoked_key.last_used_at = None
            mock_revoked_key.created_at = "2024-07-10T10:00:00Z"
            mock_revoked_key.expires_at = None
            mock_revoked_key.owner_name = "Test User"
            
            mock_service.revoke_api_key.return_value = mock_revoked_key
            mock_service_class.return_value = mock_service
            
            response = admin_client.post(
                f"/api/v1/admin/api-keys/{key_id}/revoke",
                params={"reason": "Test revocation"},
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "revoked"
            
            # Verify service was called with correct parameters
            mock_service.revoke_api_key.assert_called_once_with(
                key_id=key_id,
                reason="Test revocation",
                revoked_by=mock_service.return_value,  # This would be the admin user in reality
            )
    
    @pytest.mark.unit
    def test_delete_api_key_success(self, admin_client, admin_auth_headers):
        """Test successful API key deletion."""
        key_id = uuid4()
        
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.delete_api_key.return_value = None
            mock_service_class.return_value = mock_service
            
            response = admin_client.delete(
                f"/api/v1/admin/api-keys/{key_id}",
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 204  # No content
            
            # Verify service was called
            mock_service.delete_api_key.assert_called_once_with(key_id)
    
    @pytest.mark.unit
    def test_cleanup_expired_keys(self, admin_client, admin_auth_headers):
        """Test cleanup of expired API keys."""
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.cleanup_expired_keys.return_value = 5  # 5 keys cleaned up
            mock_service_class.return_value = mock_service
            
            response = admin_client.post(
                "/api/v1/admin/api-keys/cleanup-expired",
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "message" in data
            assert "5" in data["message"]
            assert "cleaned up" in data["message"].lower()


class TestApiKeyEndpointSecurity:
    """Test security aspects of API key endpoints."""
    
    @pytest.mark.security
    def test_non_admin_cannot_access_endpoints(self, client, auth_headers):
        """Test that non-admin users cannot access API key management."""
        endpoints = [
            ("POST", "/api/v1/admin/api-keys/", {"name": "test"}),
            ("GET", "/api/v1/admin/api-keys/", None),
            ("GET", f"/api/v1/admin/api-keys/{uuid4()}", None),
            ("PUT", f"/api/v1/admin/api-keys/{uuid4()}", {"name": "updated"}),
            ("POST", f"/api/v1/admin/api-keys/{uuid4()}/revoke", None),
            ("DELETE", f"/api/v1/admin/api-keys/{uuid4()}", None),
            ("POST", "/api/v1/admin/api-keys/cleanup-expired", None),
        ]
        
        for method, endpoint, data in endpoints:
            if method == "POST":
                response = client.post(endpoint, json=data, headers=auth_headers)
            elif method == "GET":
                response = client.get(endpoint, headers=auth_headers)
            elif method == "PUT":
                response = client.put(endpoint, json=data, headers=auth_headers)
            elif method == "DELETE":
                response = client.delete(endpoint, headers=auth_headers)
            
            assert response.status_code == 403
            
            data = response.json()
            assert "error" in data
            assert "admin" in data["error"]["message"].lower()
    
    @pytest.mark.security
    def test_unauthenticated_cannot_access_endpoints(self, client):
        """Test that unauthenticated users cannot access API key management."""
        endpoints = [
            ("POST", "/api/v1/admin/api-keys/", {"name": "test"}),
            ("GET", "/api/v1/admin/api-keys/", None),
            ("GET", f"/api/v1/admin/api-keys/{uuid4()}", None),
        ]
        
        for method, endpoint, data in endpoints:
            if method == "POST":
                response = client.post(endpoint, json=data)
            elif method == "GET":
                response = client.get(endpoint)
            
            assert response.status_code == 401
            
            response_data = response.json()
            assert "error" in response_data
            assert "api key" in response_data["error"]["message"].lower()
    
    @pytest.mark.security
    def test_api_key_not_exposed_in_responses(self, admin_client, admin_auth_headers):
        """Test that full API keys are never exposed in list/get responses."""
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            
            mock_key = MagicMock()
            mock_key.id = uuid4()
            mock_key.name = "Test Key"
            mock_key.prefix = "rdf_test"  # Only prefix should be shown
            mock_key.status = ApiKeyStatus.ACTIVE
            mock_key.role = "user"
            mock_key.max_concurrent_jobs = 5
            mock_key.monthly_quota_minutes = 1000
            mock_key.total_jobs_created = 0
            mock_key.total_minutes_processed = 0
            mock_key.last_used_at = None
            mock_key.created_at = "2024-07-10T10:00:00Z"
            mock_key.expires_at = None
            mock_key.owner_name = "Test User"
            
            # Test list endpoint
            mock_service.list_api_keys.return_value = ([mock_key], 1)
            mock_service_class.return_value = mock_service
            
            response = admin_client.get(
                "/api/v1/admin/api-keys/",
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            
            api_key_data = data["api_keys"][0]
            assert "prefix" in api_key_data
            assert "key" not in api_key_data  # Full key should not be present
            assert "key_hash" not in api_key_data  # Hash should not be present
            assert api_key_data["prefix"] == "rdf_test"
    
    @pytest.mark.security
    def test_sensitive_fields_not_exposed(self, admin_client, admin_auth_headers):
        """Test that sensitive fields are not exposed in API responses."""
        key_id = uuid4()
        
        with patch('api.routers.api_keys.ApiKeyService') as mock_service_class:
            mock_service = AsyncMock()
            
            mock_key = MagicMock()
            mock_key.id = key_id
            mock_key.name = "Test Key"
            mock_key.prefix = "rdf_test"
            mock_key.status = ApiKeyStatus.ACTIVE
            mock_key.role = "user"
            mock_key.max_concurrent_jobs = 5
            mock_key.monthly_quota_minutes = 1000
            mock_key.total_jobs_created = 0
            mock_key.total_minutes_processed = 0
            mock_key.last_used_at = None
            mock_key.created_at = "2024-07-10T10:00:00Z"
            mock_key.expires_at = None
            mock_key.owner_name = "Test User"
            # Sensitive fields that should NOT be exposed
            mock_key.key_hash = "secret_hash"
            mock_key.owner_email = "test@example.com"
            mock_key.created_by = "admin_user"
            
            mock_service.get_api_key_by_id.return_value = mock_key
            mock_service_class.return_value = mock_service
            
            response = admin_client.get(
                f"/api/v1/admin/api-keys/{key_id}",
                headers=admin_auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # These fields should NOT be present in the response
            sensitive_fields = ["key_hash", "owner_email", "created_by"]
            for field in sensitive_fields:
                assert field not in data