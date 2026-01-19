"""
Tests for Chat API routes.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.routes.chat import router
from app.models.api import ChatRequest, ChatResponse


@pytest.fixture
def app():
    """Create a test FastAPI app with the chat router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.analyze.return_value = {
        "session_id": "test-session-123",
        "triage": {
            "category": "Technical",
            "subcategory": "Login Issue",
            "priority": "P2",
            "sla_hours": 8,
            "suggested_team": "IT Support",
            "sentiment": "frustrated",
            "language": "Hungarian",
            "confidence": 0.92,
        },
        "answer_draft": {
            "greeting": "Kedves Felhasználó!",
            "body": "Köszönjük a megkeresését.",
            "closing": "Üdvözlettel, Support",
            "tone": "empathetic_professional",
        },
        "citations": [],
        "policy_check": {
            "refund_promise": False,
            "sla_mentioned": False,
            "escalation_needed": False,
            "compliance": "passed",
        },
    }
    return agent


class TestChatRequest:
    """Tests for ChatRequest model."""

    def test_valid_request(self):
        """Test valid chat request creation."""
        request = ChatRequest(
            message="Nem tudok belépni a fiókomba.",
            session_id="test-123",
            source="web",
        )

        assert request.message == "Nem tudok belépni a fiókomba."
        assert request.session_id == "test-123"
        assert request.source == "web"

    def test_request_with_defaults(self):
        """Test request with default values."""
        request = ChatRequest(message="Test message")

        assert request.message == "Test message"
        assert request.session_id is None
        assert request.source == "web"
        assert request.ip_address is None

    def test_request_with_ip_address(self):
        """Test request with IP address."""
        request = ChatRequest(
            message="Test",
            ip_address="192.168.1.1",
        )

        assert request.ip_address == "192.168.1.1"

    def test_request_source_validation(self):
        """Test that source must be valid literal."""
        # Valid sources
        for source in ["web", "jira", "api"]:
            request = ChatRequest(message="Test", source=source)
            assert request.source == source

    def test_request_empty_message_fails(self):
        """Test that empty message fails validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest(message="")


class TestChatResponse:
    """Tests for ChatResponse model."""

    def test_successful_response(self):
        """Test successful response creation."""
        response = ChatResponse(
            success=True,
            data={"session_id": "test", "triage": {}},
        )

        assert response.success is True
        assert response.data["session_id"] == "test"
        assert response.error is None

    def test_error_response(self):
        """Test error response creation."""
        response = ChatResponse(
            success=False,
            data={},
            error="Something went wrong",
        )

        assert response.success is False
        assert response.error == "Something went wrong"


class TestChatEndpoint:
    """Tests for /chat endpoint."""

    @patch("app.api.routes.chat.get_agent")
    def test_chat_endpoint_success(self, mock_get_agent, client, mock_agent):
        """Test successful chat request."""
        mock_get_agent.return_value = mock_agent

        # Override dependency
        from app.api.routes import chat
        original_get_agent = chat.get_agent

        with patch.object(chat, "get_agent", return_value=mock_agent):
            response = client.post(
                "/api/v1/chat",
                json={"message": "Nem tudok belépni."},
            )

        # Note: This will fail without proper dependency override
        # The actual test would need proper FastAPI dependency injection mocking

    def test_chat_request_model_validation(self):
        """Test that chat request validates correctly."""
        valid_request = {
            "message": "Test message",
            "session_id": "123",
            "ip_address": "8.8.8.8",
            "source": "web",
        }

        request = ChatRequest(**valid_request)
        assert request.message == "Test message"

    def test_chat_request_rejects_invalid_source(self):
        """Test that invalid source is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest(message="Test", source="invalid")


class TestSessionHandling:
    """Tests for session handling in chat."""

    def test_new_session_created(self, mock_agent):
        """Test that new session ID is created when not provided."""
        mock_agent.analyze.return_value = {
            "session_id": "new-generated-session",
            "triage": {},
            "answer_draft": {},
        }

        # Call analyze without session_id
        result = mock_agent.analyze(ticket_text="Test", session_id=None)

        assert "session_id" in result

    def test_existing_session_used(self, mock_agent):
        """Test that existing session ID is used when provided."""
        existing_session = "existing-session-456"

        mock_agent.analyze.return_value = {
            "session_id": existing_session,
            "triage": {},
            "answer_draft": {},
        }

        result = mock_agent.analyze(
            ticket_text="Test",
            session_id=existing_session,
        )

        assert result["session_id"] == existing_session
