"""
E2E Test: API Endpoints
Knowledge Router PROD

Tests all critical API endpoints:
- Sessions (create, get, list)
- Messages (send, get history)
- Documents (upload, list, get)
- Workflows (chat, process-document)

Priority: HIGH (API is external interface)
"""

import pytest
from fastapi.testclient import TestClient
import io


@pytest.mark.e2e
class TestAPIEndpoints:
    """Test FastAPI endpoints end-to-end."""
    
    # ========================================================================
    # HEALTH & VERSION
    # ========================================================================
    
    def test_health_endpoint(self, test_client):
        """Test /health endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_version_endpoint(self, test_client):
        """Test /api/version endpoint."""
        response = test_client.get("/api/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "name" in data
    
    # ========================================================================
    # SESSIONS
    # ========================================================================
    
    @pytest.mark.skip(reason="Knowledge Router doesn't have POST /sessions endpoint - sessions created via workflow")
    def test_create_session(self, test_client, test_tenant_user):
        """Test POST /api/sessions/ - create new session."""
        response = test_client.post(
            "/api/sessions/",
            params={
                "user_id": test_tenant_user["user_id"],
                "tenant_id": test_tenant_user["tenant_id"]
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "session_id" in data
        assert data["session_id"] is not None
    
    @pytest.mark.skip(reason="No GET /sessions/{id} endpoint - use GET /sessions/{id}/messages instead")
    def test_get_session(self, test_client, test_session):
        """Test GET /api/sessions/{session_id} - get session details."""
        response = test_client.get(
            f"/api/sessions/{test_session['session_id']}",
            params={
                "user_id": test_session["user_id"],
                "tenant_id": test_session["tenant_id"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_session["session_id"]
    
    def test_list_sessions(self, test_client, test_tenant_user):
        """Test GET /api/sessions/ - list user sessions."""
        response = test_client.get(
            "/api/sessions/",
            params={
                "user_id": test_tenant_user["user_id"],
                "tenant_id": test_tenant_user["tenant_id"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)
    
    # ========================================================================
    # MESSAGES
    # ========================================================================
    
    @pytest.mark.skip(reason="No GET /api/messages endpoint - use GET /sessions/{id}/messages")
    def test_get_message_history(self, test_client, test_session):
        """Test GET /api/messages/ - get message history."""
        response = test_client.get(
            "/api/messages/",
            params={
                "session_id": test_session["session_id"],
                "user_id": test_session["user_id"],
                "tenant_id": test_session["tenant_id"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)
    
    @pytest.mark.openai
    @pytest.mark.slow
    def test_send_message(self, test_client, test_session):
        """
        Test POST /api/sessions/{session_id}/messages - add message to session.
        
        Real OpenAI call - costs ~$0.001
        """
        session_id = test_session["session_id"]
        response = test_client.post(
            f"/api/sessions/{session_id}/messages",
            json={
                "tenant_id": 1,
                "user_id": 1,
                "role": "user",
                "content": "szia"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        # Response: {"status": "message_added", "session_id": ...}
        assert data["status"] == "message_added"
        assert "session_id" in data
    
    # ========================================================================
    # DOCUMENTS
    # ========================================================================
    
    def test_list_documents(self, test_client, test_tenant_user):
        """Test GET /api/documents/ - list user documents."""
        response = test_client.get(
            "/api/documents/",
            params={
                "user_id": test_tenant_user["user_id"],
                "tenant_id": test_tenant_user["tenant_id"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert isinstance(data["documents"], list)
    
    def test_get_document(self, test_client, test_document):
        """Test GET /api/documents/{document_id} - get document details."""
        response = test_client.get(
            f"/api/documents/{test_document['document_id']}",
            params={
                "user_id": test_document["user_id"],
                "tenant_id": test_document["tenant_id"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_document["document_id"]
    
    @pytest.mark.openai
    @pytest.mark.slow
    def test_upload_document(self, test_client, test_tenant_user):
        """
        Test POST /api/workflows/process-document - upload & process document.
        
        Real OpenAI call for embedding - costs ~$0.001
        """
        # Create test file content
        import uuid
        unique_id = str(uuid.uuid4())
        file_content = f"Unique test document content for pytest {unique_id}. This is a completely unique text file that should not match any existing documents in the database. Random UUID: {unique_id}".encode()
        file = io.BytesIO(file_content)
        
        response = test_client.post(
            "/api/workflows/process-document",
            data={
                "tenant_id": str(test_tenant_user["tenant_id"]),
                "user_id": str(test_tenant_user["user_id"]),
                "visibility": "private",
                "enable_streaming": "false"
            },
            files={
                "file": ("test_upload.txt", file, "text/plain")
            }
        )
        
        # 202 Accepted for async processing, or 200/201 for synchronous
        assert response.status_code in [200, 201, 202]
        data = response.json()
        
        # Debug: print response structure
        print(f"\nDEBUG upload response: {data}")
        
        assert "document_id" in data
        assert data["document_id"] is not None
    
    # ========================================================================
    # WORKFLOWS
    # ========================================================================
    
    @pytest.mark.openai
    @pytest.mark.slow
    def test_unified_chat_endpoint(self, test_client, test_session):
        """
        Test POST /api/workflows/chat - unified chat workflow.
        
        Real OpenAI call - costs ~$0.001-0.005 depending on query
        """
        response = test_client.post(
            "/api/chat",
            json={
                "user_context": {
                    "tenant_id": test_session["tenant_id"],
                    "user_id": test_session["user_id"]
                },
                "session_id": test_session["session_id"],
                "query": "hello, how are you?",
                "enable_streaming": False
            }
        )
        
        if response.status_code != 200:
            print(f"\n=== DEBUG: Response status: {response.status_code} ===")
            print(f"Response body: {response.text}")
        
        assert response.status_code == 200
        data = response.json()
        # Unified chat response: {"answer": ..., "role": ..., "session_id": ..., ...}
        assert "answer" in data
        assert data["answer"] is not None
    
    # ========================================================================
    # ERROR HANDLING
    # ========================================================================
    
    @pytest.mark.skip(reason="No GET /sessions/{id} endpoint exists")
    def test_invalid_session_id(self, test_client, test_tenant_user):
        """Test error handling for invalid session_id."""
        response = test_client.get(
            "/api/sessions/99999",
            params={
                "user_id": test_tenant_user["user_id"],
                "tenant_id": test_tenant_user["tenant_id"]
            }
        )
        assert response.status_code in [404, 400]
    
    def test_invalid_document_id(self, test_client, test_tenant_user):
        """Test error handling for invalid document_id."""
        response = test_client.get(
            "/api/documents/99999",
            params={
                "user_id": test_tenant_user["user_id"],
                "tenant_id": test_tenant_user["tenant_id"]
            }
        )
        assert response.status_code in [404, 400]
    
    # ========================================================================
    # ADDITIONAL HEALTH ENDPOINTS
    # ========================================================================
    
    def test_db_check_endpoint(self, test_client):
        """Test GET /api/db-check - database connection check."""
        response = test_client.get("/api/db-check")
        assert response.status_code == 200
        
        data = response.json()
        # Response is [status: bool, message: str]
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0] is True  # status
        assert "sikeres" in data[1].lower() or "success" in data[1].lower()  # message
    
    # ========================================================================
    # DOCUMENT DELETE
    # ========================================================================
    
    def test_delete_document(self, test_client, test_document):
        """Test DELETE /api/documents/{document_id} - delete document."""
        doc_id = test_document["document_id"]
        tenant_id = test_document["tenant_id"]
        user_id = test_document["user_id"]
        
        response = test_client.delete(
            f"/api/documents/{doc_id}",
            params={
                "tenant_id": tenant_id,
                "user_id": user_id
            }
        )
        assert response.status_code == 204  # DELETE returns 204 No Content
        
        # 204 No Content has no response body
        # data = response.json()
        # assert data["status"] == "success"
        # assert data["document_id"] == doc_id
    
    # ========================================================================
    # WORKFLOW STATUS
    # ========================================================================
    
    def test_workflow_status(self, test_client):
        """Test GET /api/workflows/status - workflow system status."""
        response = test_client.get("/api/workflows/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "system" in data
        assert "workflows" in data
        assert "langgraph" in data["system"]
        assert "qdrant" in data["system"]
    
    @pytest.mark.skip(reason="POST /sessions/ doesn't exist - sessions created via workflow")
    def test_missing_required_params(self, test_client):
        """Test error handling for missing required parameters."""
        response = test_client.post("/api/sessions/")
        assert response.status_code == 422  # FastAPI validation error
