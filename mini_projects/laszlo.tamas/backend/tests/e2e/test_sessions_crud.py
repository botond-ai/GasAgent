"""
E2E Test: Session CRUD Operations
Knowledge Router PROD

Tests session management endpoints beyond listing:
- GET /api/sessions/{session_id}/messages (get messages)
- POST /api/sessions/{session_id}/messages (add message)
- PATCH /api/sessions/{session_id}/title (update title)
- DELETE /api/sessions/{session_id} (soft delete)
- POST /api/sessions/{session_id}/consolidate (LTM extraction)

Note: Session listing already tested in test_api_endpoints.py
Priority: HIGH (session management critical for chat)
"""

import pytest


@pytest.mark.e2e
class TestSessionCRUD:
    """Test session CRUD operations."""
    
    def test_get_session_messages(self, test_client, test_session):
        """Test GET /api/sessions/{session_id}/messages - get chat history."""
        session_id = test_session["session_id"]
        user_id = test_session["user_id"]
        
        response = test_client.get(
            f"/api/sessions/{session_id}/messages",
            params={"user_id": user_id}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "messages" in data
        assert "count" in data
        assert isinstance(data["messages"], list)
        assert data["count"] == len(data["messages"])
        
        # If messages exist, verify structure
        if len(data["messages"]) > 0:
            message = data["messages"][0]
            assert "role" in message
            assert "content" in message
            assert "created_at" in message
    
    def test_add_system_message(self, test_client, test_session):
        """Test POST /api/sessions/{session_id}/messages - add system message."""
        session_id = test_session["session_id"]
        tenant_id = test_session["tenant_id"]
        user_id = test_session["user_id"]
        
        response = test_client.post(
            f"/api/sessions/{session_id}/messages",
            json={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "role": "system",
                "content": "Test system message from pytest",
                "metadata": {"source": "pytest"}
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "message_added"
        assert data["session_id"] == session_id
        
        # Verify message was added
        messages_response = test_client.get(
            f"/api/sessions/{session_id}/messages",
            params={"user_id": user_id}
        )
        messages = messages_response.json()["messages"]
        
        # Find our test message
        test_message = next(
            (m for m in messages if m["content"] == "Test system message from pytest"),
            None
        )
        assert test_message is not None
        assert test_message["role"] == "system"
    
    def test_update_session_title(self, test_client, test_session):
        """Test PATCH /api/sessions/{session_id}/title - update session title."""
        session_id = test_session["session_id"]
        
        new_title = "Updated Test Session Title"
        response = test_client.patch(
            f"/api/sessions/{session_id}/title",
            json={"title": new_title}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "title_updated"
        assert data["session_id"] == session_id
        assert data["new_title"] == new_title
    
    def test_delete_session(self, test_client, test_tenant_user):
        """Test DELETE /api/sessions/{session_id} - soft delete session."""
        from database.pg_init import create_session_pg
        
        # Create a test session to delete
        import uuid
        test_session_id = str(uuid.uuid4())
        create_session_pg(
            test_session_id,
            test_tenant_user["tenant_id"],
            test_tenant_user["user_id"]
        )
        
        # Delete the session
        response = test_client.delete(f"/api/sessions/{test_session_id}")
        assert response.status_code == 204  # DELETE returns 204 No Content
        
        # 204 No Content has no response body
        # assert data["status"] == "session_deleted"
        # assert data["session_id"] == test_session_id
    
    @pytest.mark.skip(reason="LTM consolidation requires OpenAI API - expensive test")
    def test_consolidate_session_memory(self, test_client, test_session):
        """Test POST /api/sessions/{session_id}/consolidate - extract LTM."""
        session_id = test_session["session_id"]
        
        response = test_client.post(f"/api/sessions/{session_id}/consolidate")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "memories_created" in data
        assert data["session_id"] == session_id
