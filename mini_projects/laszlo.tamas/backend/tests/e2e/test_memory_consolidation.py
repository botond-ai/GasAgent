"""
E2E Test: Session Memory Consolidation
Knowledge Router PROD

Tests:
- POST /api/sessions/{session_id}/consolidate (memory extraction from session)

Prerequisites:
- Session with messages (created by test fixtures)
- OpenAI API key (for LLM fact extraction)

Priority: MEDIUM (core memory feature)
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.openai
def test_consolidate_session_memory(client: TestClient, test_session):
    """
    Test session memory consolidation workflow.
    
    Real OpenAI call - costs ~$0.002-0.005
    
    Prerequisites:
    - Session must have messages (created in setup)
    """
    import uuid
    
    # Use a fresh UUID for this test (not test_session, which might be reused)
    session_id = str(uuid.uuid4())
    user_id = test_session["user_id"]
    
    # First, create a session with messages via chat endpoint
    chat_response = client.post(
        "/api/chat",
        json={
            "user_context": {
                "tenant_id": test_session["tenant_id"],
                "user_id": user_id
            },
            "session_id": session_id,
            "query": "My favorite color is blue and I work at Company XYZ"
        }
    )
    assert chat_response.status_code == 200, "Chat should create session with message"
    
    # Now consolidate memories
    response = client.post(
        f"/api/sessions/{session_id}/consolidate",
        json={
            "user_context": {
                "tenant_id": test_session["tenant_id"],
                "user_id": user_id
            }
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    # Status can be 'success' (memories extracted) or 'skipped' (not enough messages/already processed)
    assert data["status"] in ["success", "skipped"]
    
    # Check memory extraction results
    if "memories_extracted" in data:
        assert isinstance(data["memories_extracted"], int)
        assert data["memories_extracted"] >= 0
    
    if "qdrant_vectors_created" in data:
        assert isinstance(data["qdrant_vectors_created"], int)
    
    if "summary" in data:
        assert isinstance(data["summary"], str)


@pytest.mark.integration
def test_consolidate_empty_session(client: TestClient, test_session):
    """
    Test memory consolidation on empty session.
    
    Expected: Should handle gracefully (no memories extracted)
    """
    import uuid
    session_id = str(uuid.uuid4())  # Valid UUID format required
    user_id = test_session["user_id"]
    
    # Create empty session (no messages)
    client.post(
        "/api/chat/rag",
        json={
            "tenant_id": test_session["tenant_id"],
            "user_id": user_id,
            "session_id": session_id,
            "query": "quick test"
        }
    )
    
    # Consolidate (should succeed but extract 0 memories)
    response = client.post(
        f"/api/sessions/{session_id}/consolidate",
        json={
            "user_context": {
                "tenant_id": test_session["tenant_id"],
                "user_id": user_id
            }
        }
    )
    
    # Should not error, but may return 0 memories
    assert response.status_code in [200, 404, 400]
