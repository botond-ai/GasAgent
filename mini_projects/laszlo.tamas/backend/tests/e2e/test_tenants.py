"""
E2E Test: Tenant Endpoints
Knowledge Router PROD

Tests all tenant management endpoints:
- GET /api/tenants (list)
- GET /api/tenants/{tenant_id} (get)
- PATCH /api/tenants/{tenant_id} (update)
- GET /api/tenants/{tenant_id}/users (list tenant users)

Priority: HIGH (tenant isolation critical)
"""

import pytest


@pytest.mark.e2e
class TestTenantEndpoints:
    """Test tenant CRUD operations."""
    
    def test_list_tenants_all(self, test_client):
        """Test GET /api/tenants - list all tenants."""
        response = test_client.get(
            "/api/tenants",
            params={"active_only": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify tenant structure
        tenant = data[0]
        assert "tenant_id" in tenant
        assert "name" in tenant
        assert "is_active" in tenant
    
    def test_list_tenants_active_only(self, test_client):
        """Test GET /api/tenants?active_only=true - list only active tenants."""
        response = test_client.get(
            "/api/tenants",
            params={"active_only": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # All tenants should be active
        for tenant in data:
            assert tenant["is_active"] is True
    
    def test_get_tenant(self, test_client, test_tenant_user):
        """Test GET /api/tenants/{tenant_id} - get specific tenant."""
        tenant_id = test_tenant_user["tenant_id"]
        
        response = test_client.get(f"/api/tenants/{tenant_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["tenant_id"] == tenant_id
        assert "name" in data
        assert "is_active" in data
        assert "created_at" in data
    
    def test_get_tenant_invalid_id(self, test_client):
        """Test GET /api/tenants/{tenant_id} - invalid tenant ID."""
        response = test_client.get("/api/tenants/99999")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "Tenant" in data["detail"]
    
    def test_update_tenant(self, test_client, test_tenant_user):
        """Test PATCH /api/tenants/{tenant_id} - update tenant."""
        tenant_id = test_tenant_user["tenant_id"]
        
        # Get original tenant
        original = test_client.get(f"/api/tenants/{tenant_id}").json()
        
        # Update tenant name
        new_name = f"Updated Test Tenant {tenant_id}"
        response = test_client.patch(
            f"/api/tenants/{tenant_id}",
            json={
                "name": new_name,
                "is_active": True
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["tenant_id"] == tenant_id
        assert data["name"] == new_name
        
        # Restore original name (cleanup)
        test_client.patch(
            f"/api/tenants/{tenant_id}",
            json={"name": original["name"]}
        )
    
    def test_get_tenant_users(self, test_client, test_tenant_user):
        """Test GET /api/tenants/{tenant_id}/users - list users in tenant."""
        tenant_id = test_tenant_user["tenant_id"]
        
        response = test_client.get(f"/api/tenants/{tenant_id}/users")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify user structure
        user = data[0]
        assert "user_id" in user  # Response uses 'user_id', not 'id'
        assert "tenant_id" in user
        assert user["tenant_id"] == tenant_id
        assert "firstname" in user or "lastname" in user or "nickname" in user
    
    def test_get_tenant_users_invalid_tenant(self, test_client):
        """Test GET /api/tenants/{tenant_id}/users - invalid tenant."""
        response = test_client.get("/api/tenants/99999/users")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
