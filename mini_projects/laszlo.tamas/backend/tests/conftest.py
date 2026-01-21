"""
Global Pytest Configuration & Shared Fixtures
Knowledge Router PROD

Fixtures:
- test_client: FastAPI TestClient instance
- test_session: Test session for workflows
- test_document: Test document with chunks
- mock_openai_client: Mocked OpenAI client (SDK v1.0+)
"""

import pytest
import os
import uuid
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from fastapi.testclient import TestClient


# ===== FASTAPI CLIENT FIXTURE =====

@pytest.fixture(scope="session")
def test_client():
    """
    FastAPI TestClient for API endpoint testing.
    Session-scoped for performance (reuse across tests).
    
    CRITICAL FIX: TestClient doesn't trigger @app.on_event("startup") in pytest.
    Must manually call init_workflows() before creating client, otherwise
    workflow-dependent tests fail with 503.
    """
    from main import app
    from api.dependencies import init_workflows
    import sys
    
    # MANUALLY trigger startup (TestClient in pytest doesn't do it automatically)
    sys.stderr.write("🔧 [tests/conftest] Initializing workflows for test session\n")
    sys.stderr.flush()
    init_workflows()
    sys.stderr.write("   [tests/conftest] init_workflows() called\n")
    sys.stderr.flush()
    
    return TestClient(app)


@pytest.fixture
def client(test_client):
    """Alias for test_client (backward compatibility)."""
    return test_client


# ===== DATABASE FIXTURES =====

# REMOVED: Conflicted with backend/conftest.py test_session fixture
# Session creation now handled by backend/conftest.py with database integration

# REMOVED: test_document fixture
# The fixture in backend/conftest.py provides real DB integration with Qdrant indexing
# for @pytest.mark.openai tests. Mock fixtures are not needed for e2e workflow tests.


# ===== OPENAI MOCKING (SDK v1.0+) =====

@pytest.fixture
def mock_openai_client():
    """
    Mock OpenAI client compatible with SDK v1.0+.
    
    Usage:
        def test_example(mock_openai_client):
            with mock_openai_client:
                # OpenAI calls will be mocked
                result = workflow.execute(...)
    """
    mock_completion_response = MagicMock()
    mock_completion_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"action": "CHAT", "reasoning": "Test reasoning"}',
                role="assistant"
            )
        )
    ]
    mock_completion_response.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15
    )
    
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion_response
    
    # Patch get_openai_client function
    patch_target = "services.unified_chat_workflow.get_openai_client"
    patcher = patch(patch_target, return_value=mock_client)
    
    return patcher


@pytest.fixture
def mock_openai_chat_completion(mock_openai_client):
    """
    Alias for mock_openai_client for backward compatibility.
    
    Usage in tests: mock_openai_chat_completion.start() / .stop()
    """
    return mock_openai_client


# ===== HELPER FUNCTIONS =====

# Note: pytest_configure, pytest_collection_modifyitems, and pytest_addoption
# are already defined in backend/conftest.py (root level)
# No need to redefine here to avoid conflicts

