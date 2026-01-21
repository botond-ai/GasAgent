"""
E2E Test: Admin Extended Endpoints
Knowledge Router PROD

Tests:
- GET /api/admin/dev-mode (development mode check)

Priority: LOW (simple flag check)
"""

import pytest
from fastapi.testclient import TestClient


def test_dev_mode_endpoint(client: TestClient):
    """
    Test development mode flag endpoint.
    
    Expected: 200 OK with dev mode status
    """
    response = client.get("/api/admin/config/dev-mode")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "dev_mode" in data
    assert isinstance(data["dev_mode"], bool)
    
    # Optional fields
    if "openai_api_key_present" in data:
        assert isinstance(data["openai_api_key_present"], bool)
    
    if "debug_endpoints_enabled" in data:
        assert isinstance(data["debug_endpoints_enabled"], bool)
