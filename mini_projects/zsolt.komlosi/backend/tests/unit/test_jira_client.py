"""
Unit tests for Jira client.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.jira_client import JiraClient, JiraIssue, JiraComment


class TestJiraIssue:
    """Tests for JiraIssue dataclass."""

    def test_from_api_response_full(self):
        """Test creating JiraIssue from complete API response."""
        data = {
            "key": "PROJ-123",
            "fields": {
                "summary": "Test issue",
                "description": "Test description",
                "status": {"name": "Open"},
                "priority": {"name": "High"},
                "issuetype": {"name": "Bug"},
                "project": {"key": "PROJ"},
                "reporter": {"displayName": "John Doe"},
                "assignee": {"displayName": "Jane Smith"},
                "created": "2024-01-15T10:00:00.000+0000",
                "updated": "2024-01-15T12:00:00.000+0000",
                "labels": ["urgent", "customer"],
            }
        }

        issue = JiraIssue.from_api_response(data)

        assert issue.key == "PROJ-123"
        assert issue.summary == "Test issue"
        assert issue.description == "Test description"
        assert issue.status == "Open"
        assert issue.priority == "High"
        assert issue.issue_type == "Bug"
        assert issue.project_key == "PROJ"
        assert issue.reporter == "John Doe"
        assert issue.assignee == "Jane Smith"
        assert issue.labels == ["urgent", "customer"]

    def test_from_api_response_minimal(self):
        """Test creating JiraIssue from minimal API response."""
        data = {
            "key": "PROJ-456",
            "fields": {
                "summary": "Minimal issue",
            }
        }

        issue = JiraIssue.from_api_response(data)

        assert issue.key == "PROJ-456"
        assert issue.summary == "Minimal issue"
        assert issue.description is None
        assert issue.status == "Unknown"
        assert issue.priority is None
        assert issue.assignee is None


class TestJiraComment:
    """Tests for JiraComment dataclass."""

    def test_from_api_response(self):
        """Test creating JiraComment from API response."""
        data = {
            "id": "12345",
            "body": "This is a comment",
            "author": {"displayName": "John Doe"},
            "created": "2024-01-15T10:00:00.000+0000",
        }

        comment = JiraComment.from_api_response(data)

        assert comment.id == "12345"
        assert comment.body == "This is a comment"
        assert comment.author == "John Doe"
        assert comment.created == "2024-01-15T10:00:00.000+0000"


class TestJiraClient:
    """Tests for JiraClient class."""

    def test_is_configured_false(self):
        """Test is_configured returns False when not configured."""
        with patch("app.integrations.jira_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                jira_url=None,
                jira_user_email=None,
                jira_api_token=None,
            )

            client = JiraClient()
            assert client.is_configured is False

    def test_is_configured_true(self):
        """Test is_configured returns True when configured."""
        with patch("app.integrations.jira_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                jira_url="https://test.atlassian.net",
                jira_user_email="test@example.com",
                jira_api_token="test-token",
            )

            client = JiraClient(
                base_url="https://test.atlassian.net",
                user_email="test@example.com",
                api_token="test-token",
            )
            assert client.is_configured is True

    def test_get_auth_header(self):
        """Test Basic Auth header generation."""
        with patch("app.integrations.jira_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                jira_url="https://test.atlassian.net",
                jira_user_email="test@example.com",
                jira_api_token="test-token",
            )

            client = JiraClient(
                base_url="https://test.atlassian.net",
                user_email="test@example.com",
                api_token="test-token",
            )

            auth_header = client._get_auth_header()
            assert auth_header.startswith("Basic ")
            # Base64 of "test@example.com:test-token"
            assert "dGVzdEBleGFtcGxlLmNvbTp0ZXN0LXRva2Vu" in auth_header

    @pytest.mark.asyncio
    async def test_get_issue(self):
        """Test getting a Jira issue."""
        with patch("app.integrations.jira_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                jira_url="https://test.atlassian.net",
                jira_user_email="test@example.com",
                jira_api_token="test-token",
            )

            client = JiraClient(
                base_url="https://test.atlassian.net",
                user_email="test@example.com",
                api_token="test-token",
            )

            # Mock the HTTP client
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "key": "PROJ-123",
                "fields": {
                    "summary": "Test issue",
                    "status": {"name": "Open"},
                }
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.is_closed = False

            client._client = mock_client

            issue = await client.get_issue("PROJ-123")

            assert issue.key == "PROJ-123"
            assert issue.summary == "Test issue"
            mock_client.get.assert_called_once_with("/issue/PROJ-123")

    @pytest.mark.asyncio
    async def test_add_comment(self):
        """Test adding a comment to an issue."""
        with patch("app.integrations.jira_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                jira_url="https://test.atlassian.net",
                jira_user_email="test@example.com",
                jira_api_token="test-token",
            )

            client = JiraClient(
                base_url="https://test.atlassian.net",
                user_email="test@example.com",
                api_token="test-token",
            )

            # Mock the HTTP client
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "12345",
                "body": "Test comment",
                "author": {"displayName": "Test User"},
                "created": "2024-01-15T10:00:00.000+0000",
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False

            client._client = mock_client

            comment = await client.add_comment("PROJ-123", "Test comment")

            assert comment.id == "12345"
            mock_client.post.assert_called_once()


class TestJiraTools:
    """Tests for Jira LangChain tools."""

    def test_jira_not_configured(self):
        """Test tools return error when Jira is not configured."""
        with patch("app.tools.jira_tools.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                jira_configured=False,
            )

            from app.tools.jira_tools import jira_get_issue

            result = jira_get_issue.invoke({"issue_key": "PROJ-123"})
            assert "error" in result
            assert "not configured" in result["error"]
