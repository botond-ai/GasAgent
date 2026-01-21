"""
E2E Test: Admin Endpoints
Knowledge Router PROD

Tests admin/system management endpoints:
- GET /api/admin/cache/stats (cache statistics)
- POST /api/admin/cache/clear (clear all caches)
- DELETE /api/admin/cache/user/{user_id} (invalidate user cache)
- DELETE /api/admin/cache/tenant/{tenant_id} (invalidate tenant cache)
- GET /api/admin/config/dev-mode (dev mode status)

Priority: MEDIUM (admin tools, not critical for core functionality)
"""

import pytest


@pytest.mark.e2e
class TestAdminEndpoints:
    """Test admin and system management endpoints."""
    
    def test_get_cache_stats(self, test_client):
        """Test GET /api/admin/cache/stats - get cache statistics."""
        response = test_client.get("/api/admin/cache/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "memory_cache" in data
        assert "db_cache" in data
        
        # Verify memory cache structure
        assert "size" in data["memory_cache"]
        assert "keys" in data["memory_cache"]
        
        # Verify DB cache structure
        assert "cached_users" in data["db_cache"]
    
    def test_get_dev_mode_status(self, test_client):
        """Test GET /api/admin/config/dev-mode - get development mode status."""
        response = test_client.get("/api/admin/config/dev-mode")
        assert response.status_code == 200
        
        data = response.json()
        assert "dev_mode" in data
        assert isinstance(data["dev_mode"], bool)
    
    def test_invalidate_user_cache(self, test_client, test_tenant_user):
        """Test DELETE /api/admin/cache/user/{user_id} - clear user cache."""
        user_id = test_tenant_user["user_id"]
        
        response = test_client.delete(f"/api/admin/cache/user/{user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "memory_cleared" in data
        assert "db_cleared" in data
        assert isinstance(data["memory_cleared"], int)
        assert isinstance(data["db_cleared"], int)
    
    def test_invalidate_tenant_cache(self, test_client, test_tenant_user):
        """Test DELETE /api/admin/cache/tenant/{tenant_id} - clear tenant cache."""
        tenant_id = test_tenant_user["tenant_id"]
        
        response = test_client.delete(f"/api/admin/cache/tenant/{tenant_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "memory_cleared" in data
        assert "db_cleared" in data
        assert "users_affected" in data
        assert isinstance(data["users_affected"], int)
    
    def test_clear_all_caches(self, test_client):
        """Test POST /api/admin/cache/clear - clear all cache layers."""
        response = test_client.post("/api/admin/cache/clear")
        assert response.status_code == 200
        
        data = response.json()
        assert "memory_cleared" in data
        assert "db_cleared" in data
        assert isinstance(data["memory_cleared"], int)
        assert isinstance(data["db_cleared"], int)
