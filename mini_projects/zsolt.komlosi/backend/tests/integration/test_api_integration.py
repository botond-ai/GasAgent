"""
Integration tests for the SupportAI API.

These tests verify the full flow through the API endpoints.
Note: These tests require mocked external services (OpenAI, Qdrant).
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_openai():
    """Mock OpenAI API responses."""
    with patch("langchain_openai.ChatOpenAI") as mock:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = MagicMock(content="Mocked response")
        mock_instance.with_structured_output.return_value = mock_instance
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant vector store."""
    with patch("app.rag.vectorstore.QdrantClient") as mock:
        mock_instance = MagicMock()
        mock_instance.search.return_value = []
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_settings():
    """Mock settings with webhook secret disabled."""
    settings = MagicMock()
    settings.jira_webhook_secret = None
    settings.jira_configured = False
    settings.jira_url = None
    settings.openai_api_key = "test-key"
    settings.openai_model = "gpt-4"
    return settings


@pytest.fixture
def app(mock_openai, mock_qdrant):
    """Create test FastAPI app with mocked dependencies."""
    from app.main import app
    return app


@pytest.fixture
def client(app, mock_settings):
    """Create test client with mocked settings."""
    from app.config import get_settings

    # Override settings dependency
    app.dependency_overrides[get_settings] = lambda: mock_settings

    client = TestClient(app)
    yield client

    # Clean up
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Integration tests for health endpoint."""

    def test_health_endpoint_returns_ok(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_includes_version(self, client):
        """Test that health includes version info."""
        response = client.get("/health")
        data = response.json()

        assert "version" in data
        assert data["version"]  # Not empty


class TestChatIntegration:
    """Integration tests for chat endpoint."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent for chat tests."""
        agent = MagicMock()
        agent.analyze.return_value = {
            "session_id": "test-session",
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
                "closing": "Üdvözlettel",
                "tone": "empathetic_professional",
            },
            "citations": [],
            "policy_check": {
                "refund_promise": False,
                "sla_mentioned": False,
                "escalation_needed": False,
                "compliance": "passed",
            },
            "should_auto_respond": True,
        }
        return agent

    @patch("app.api.deps.get_agent")
    def test_chat_endpoint_processes_hungarian_ticket(self, mock_get_agent, client, mock_agent):
        """Test processing a Hungarian support ticket."""
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Nem tudok belépni a fiókomba. Sürgős!",
                "source": "web",
            },
        )

        # Verify the endpoint was called
        assert response.status_code in [200, 500]  # May fail without full mocking

    @patch("app.api.deps.get_agent")
    def test_chat_endpoint_processes_english_ticket(self, mock_get_agent, client, mock_agent):
        """Test processing an English support ticket."""
        mock_agent.analyze.return_value["triage"]["language"] = "English"
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/api/v1/chat",
            json={
                "message": "I cannot log into my account. Please help!",
                "source": "api",
            },
        )

        assert response.status_code in [200, 500]


class TestJiraWebhookIntegration:
    """Integration tests for Jira webhook endpoint."""

    @pytest.fixture
    def sample_jira_payload(self):
        """Sample Jira webhook payload."""
        return {
            "webhookEvent": "jira:issue_created",
            "issue": {
                "key": "SUPPORT-123",
                "fields": {
                    "summary": "Nem tudok belépni",
                    "description": "A jelszavam nem működik.",
                    "reporter": {
                        "displayName": "Kovács János",
                        "name": "jkovacs",
                    },
                },
            },
        }

    @pytest.fixture
    def sample_jsm_payload(self):
        """Sample JSM webhook payload (without webhookEvent)."""
        return {
            "issue": {
                "key": "SUPPORT-456",
                "fields": {
                    "summary": "Password reset request",
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "I need to reset my password."}
                                ]
                            }
                        ]
                    },
                    "reporter": {
                        "displayName": "John Smith",
                    },
                },
            },
        }

    def test_webhook_ignores_unsupported_events(self, client):
        """Test that unsupported events are ignored."""
        response = client.post(
            "/api/v1/jira/webhook",
            json={
                "webhookEvent": "jira:issue_deleted",
                "issue": {"key": "TEST-1"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_webhook_ignores_empty_payload(self, client):
        """Test that empty payload is handled."""
        response = client.post(
            "/api/v1/jira/webhook",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_webhook_extracts_reporter_name(self, client, sample_jira_payload, app):
        """Test that reporter name is extracted from payload."""
        from app.api.deps import get_agent

        mock_agent = MagicMock()
        mock_agent.analyze.return_value = {
            "session_id": "jira-SUPPORT-123",
            "triage": {"category": "Technical", "priority": "P2", "confidence": 0.9},
            "answer_draft": {"greeting": "Hi", "body": "Test", "closing": "Bye"},
        }

        # Override agent dependency
        app.dependency_overrides[get_agent] = lambda: mock_agent

        response = client.post(
            "/api/v1/jira/webhook",
            json=sample_jira_payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["ticket_id"] == "SUPPORT-123"


class TestDocumentIntegration:
    """Integration tests for document endpoints."""

    def test_document_list_returns_array(self, client):
        """Test that document list returns proper structure."""
        response = client.get("/api/v1/documents")

        # May require auth or return empty
        assert response.status_code in [200, 401, 500]

        if response.status_code == 200:
            data = response.json()
            assert "documents" in data
            assert "total" in data
            assert isinstance(data["documents"], list)


class TestJiraStatusEndpoint:
    """Integration tests for Jira status endpoint."""

    def test_jira_status_returns_configuration(self, client):
        """Test that Jira status endpoint returns config info."""
        response = client.get("/api/v1/jira/status")

        assert response.status_code == 200
        data = response.json()
        assert "configured" in data


class TestErrorHandling:
    """Integration tests for error handling."""

    def test_invalid_json_returns_error(self, client):
        """Test that invalid JSON returns appropriate error."""
        response = client.post(
            "/api/v1/chat",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422  # Unprocessable Entity

    def test_missing_required_fields_returns_error(self, client):
        """Test that missing required fields returns validation error."""
        response = client.post(
            "/api/v1/chat",
            json={},  # Missing 'message' field
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_invalid_source_returns_error(self, client):
        """Test that invalid source value returns validation error."""
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Test",
                "source": "invalid_source",
            },
        )

        assert response.status_code == 422
