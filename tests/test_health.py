"""
Test health endpoints
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_check(client):
    """Test basic health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_detailed_health_check(client):
    """Test detailed health check endpoint."""
    response = client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "components" in data
    assert "timestamp" in data
    
    # Check component health
    components = data["components"]
    assert "database" in components
    assert "queue" in components
    assert "storage" in components
    assert "ffmpeg" in components


def test_capabilities(client):
    """Test capabilities endpoint."""
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    
    data = response.json()
    assert "version" in data
    assert "features" in data
    assert "formats" in data
    assert "operations" in data
    
    # Check formats
    formats = data["formats"]
    assert "input" in formats
    assert "output" in formats
    assert "mp4" in formats["input"]["video"]
    assert "h264" in formats["output"]["video_codecs"]