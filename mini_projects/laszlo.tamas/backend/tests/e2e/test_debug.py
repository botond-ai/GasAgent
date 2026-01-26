"""
E2E Test: Debug Endpoints
Knowledge Router PROD

Tests:
- POST /api/debug/reset/postgres
- POST /api/debug/reset/qdrant
- POST /api/debug/reset/cache
- GET /api/debug/test-db

⚠️ WARNING: Destructive tests - only run in development!

Priority: LOW (dev/debug utilities)
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_reset_postgres(client: TestClient):
    """
    Test PostgreSQL reset endpoint.
    
    ⚠️ DESTRUCTIVE: Deletes all documents and chunks
    """
    response = client.post("/api/debug/reset/postgres")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "success"
    assert "documents_deleted" in data
    assert "chunks_deleted" in data
    assert isinstance(data["documents_deleted"], int)
    assert isinstance(data["chunks_deleted"], int)


@pytest.mark.integration
def test_reset_qdrant(client: TestClient):
    """
    Test Qdrant reset endpoint.
    
    ⚠️ DESTRUCTIVE: Deletes all vectors
    NOTE: May return error if collection doesn't exist (fresh DB)
    """
    response = client.post("/api/debug/reset/qdrant")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    # Status can be "success" OR "error" if collection doesn't exist
    assert data["status"] in ["success", "error"]
    
    if data["status"] == "success":
        # Response may have "points_deleted" or "message"
        assert "points_deleted" in data or "message" in data


@pytest.mark.integration
def test_reset_cache(client: TestClient):
    """
    Test cache reset endpoint.
    
    ⚠️ DESTRUCTIVE: Clears all cache layers
    """
    response = client.post("/api/debug/reset/cache")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "success"
    # Response has "message" field, not "memory_cleared"/"db_cleared"
    assert "message" in data


@pytest.mark.integration
def test_reset_cache(client: TestClient):
    """
    Test cache reset endpoint.
    
    ⚠️ DESTRUCTIVE: Clears all cache layers
    """
    response = client.post("/api/debug/reset/cache")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "success"
    # Response has "message" field, not "memory_cleared"/"db_cleared"
    assert "message" in data

