"""
E2E Test: User Endpoints
Knowledge Router PROD

Tests all user management endpoints:
- GET /api/users (list)
- GET /api/users/{user_id} (get)
- PATCH /api/users/{user_id} (update)
- GET /api/users/{user_id}/debug (debug info)
- DELETE /api/users/{user_id}/conversations (clear history)
- GET /api/users/{user_id}/memories (long-term memories)

Priority: HIGH (user data operations)
"""

import pytest


@pytest.mark.e2e
class TestUserEndpoints:
    """Test user CRUD operations."""
    
    def test_list_users_all(self, test_client):
        """Test GET /api/users - list all users."""
        response = test_client.get("/api/users")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify user structure
        user = data[0]
        assert "user_id" in user  # Response uses 'user_id', not 'id'
        assert "tenant_id" in user
    
    def test_list_users_by_tenant(self, test_client, test_tenant_user):
        """Test GET /api/users?tenant_id=X - filter by tenant."""
        tenant_id = test_tenant_user["tenant_id"]
        
        response = test_client.get(
            "/api/users",
            params={"tenant_id": tenant_id}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # All users should belong to the tenant
        for user in data:
            assert user["tenant_id"] == tenant_id
    
    def test_get_user(self, test_client, test_tenant_user):
        """Test GET /api/users/{user_id} - get specific user."""
        user_id = test_tenant_user["user_id"]
        
        response = test_client.get(f"/api/users/{user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == user_id  # Response uses 'user_id', not 'id'
        assert "tenant_id" in data
        assert "nickname" in data or "firstname" in data
        assert "created_at" in data
    
    def test_get_user_invalid_id(self, test_client):
        """Test GET /api/users/{user_id} - invalid user ID."""
        response = test_client.get("/api/users/99999")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "User" in data["detail"]
    
    def test_update_user(self, test_client, test_tenant_user):
        """Test PATCH /api/users/{user_id} - update user."""
        user_id = test_tenant_user["user_id"]
        
        # Get original user
        original = test_client.get(f"/api/users/{user_id}").json()
        
        # Update user nickname
        new_nickname = f"TestUser_{user_id}_Updated"
        response = test_client.patch(
            f"/api/users/{user_id}",
            json={
                "nickname": new_nickname,
                "system_prompt": "You are a helpful assistant.",
                "default_lang": "en"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == user_id  # Response uses 'user_id', not 'id'
        assert data["nickname"] == new_nickname
        
        # Restore original (cleanup)
        if original.get("nickname"):
            test_client.patch(
                f"/api/users/{user_id}",
                json={"nickname": original["nickname"]}
            )
    
    def test_get_user_debug_info(self, test_client, test_tenant_user):
        """Test GET /api/users/{user_id}/debug - get debug info."""
        user_id = test_tenant_user["user_id"]
        tenant_id = test_tenant_user["tenant_id"]
        
        response = test_client.get(f"/api/users/{user_id}/debug?tenant_id={tenant_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "user_data" in data
        assert data["user_data"]["user_id"] == user_id  # Response uses 'user_id', not 'id'
    
    def test_delete_user_conversations(self, test_client, test_tenant_user, test_session):
        """Test DELETE /api/users/{user_id}/conversations - clear chat history."""
        user_id = test_tenant_user["user_id"]
        
        response = test_client.delete(f"/api/users/{user_id}/conversations")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "sessions_deleted" in data
        assert "messages_deleted" in data
        assert isinstance(data["sessions_deleted"], int)
        assert isinstance(data["messages_deleted"], int)
    
    def test_get_user_memories(self, test_client, test_tenant_user):
        """Test GET /api/users/{user_id}/memories - get long-term memories."""
        user_id = test_tenant_user["user_id"]
        
        response = test_client.get(
            f"/api/users/{user_id}/memories",
            params={"limit": 10}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "memories" in data
        assert "count" in data
        assert isinstance(data["memories"], list)
        assert data["count"] == len(data["memories"])
    
    def test_get_user_memories_invalid_user(self, test_client):
        """Test GET /api/users/{user_id}/memories - invalid user."""
        response = test_client.get("/api/users/99999/memories")
        assert response.status_code == 404
