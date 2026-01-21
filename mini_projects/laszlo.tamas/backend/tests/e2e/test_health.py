"""
E2E Test: Health & System Endpoints
Knowledge Router PROD

Tests:
- GET / (root endpoint)
- GET /health (health check)

Priority: LOW (simple endpoints, no business logic)
"""

import pytest
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """
    Test root endpoint - basic health check.
    
    Expected: 200 OK with version info
    """
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "ok"
    assert "message" in data
    assert "version" in data
    assert "Knowledge Router" in data["message"]


def test_health_endpoint(client: TestClient):
    """
    Test health check endpoint for load balancers.
    
    Expected: 200 OK with health status
    """
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] in ["healthy", "ok"]
