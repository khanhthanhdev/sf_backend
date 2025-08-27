"""
Test main application functionality.
"""

import pytest
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "docs_url" in data
    assert "health_url" in data


def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "version" in data
    assert "environment" in data


def test_cors_headers(client: TestClient):
    """Test CORS headers are present."""
    response = client.options("/")
    assert response.status_code == 200
    
    # Check CORS headers
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers


def test_process_time_header(client: TestClient):
    """Test that process time header is added."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "x-process-time" in response.headers
    
    # Verify it's a valid float
    process_time = float(response.headers["x-process-time"])
    assert process_time >= 0