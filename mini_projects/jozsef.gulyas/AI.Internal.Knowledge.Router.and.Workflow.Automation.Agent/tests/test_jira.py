import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import base64

from src.infrastructure.tools.jira import JiraTools, JiraTicketResult


@pytest.fixture
def tool():
    return JiraTools(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token"
    )


@pytest.fixture
def unconfigured_tool():
    return JiraTools(base_url="", email="", api_token="")


class TestJiraToolsDefinition:
    def test_tool_definition_has_correct_name(self, tool):
        assert tool.TOOL_DEFINITION["function"]["name"] == "create_jira_ticket"

    def test_tool_definition_has_required_parameters(self, tool):
        params = tool.TOOL_DEFINITION["function"]["parameters"]
        assert "project_key" in params["properties"]
        assert "summary" in params["properties"]
        assert "issue_type" in params["properties"]
        assert "description" in params["properties"]
        assert "priority" in params["properties"]
        assert set(params["required"]) == {"project_key", "summary", "issue_type"}

    def test_tool_definition_has_issue_type_enum(self, tool):
        params = tool.TOOL_DEFINITION["function"]["parameters"]
        assert params["properties"]["issue_type"]["enum"] == ["Task", "Bug", "Story", "Epic"]

    def test_tool_definition_has_priority_enum(self, tool):
        params = tool.TOOL_DEFINITION["function"]["parameters"]
        assert params["properties"]["priority"]["enum"] == ["Highest", "High", "Medium", "Low", "Lowest"]


class TestJiraToolsInit:
    def test_init_sets_base_url(self, tool):
        assert tool.base_url == "https://test.atlassian.net"

    def test_init_strips_trailing_slash(self):
        tool = JiraTools(base_url="https://test.atlassian.net/", email="", api_token="")
        assert tool.base_url == "https://test.atlassian.net"

    def test_init_sets_email(self, tool):
        assert tool.email == "test@example.com"

    def test_init_sets_api_token(self, tool):
        assert tool.api_token == "test-token"


class TestGetAuthHeader:
    def test_generates_basic_auth_header(self, tool):
        header = tool._get_auth_header()
        expected_credentials = base64.b64encode(b"test@example.com:test-token").decode()
        assert header == f"Basic {expected_credentials}"


class TestCreateJiraTicket:
    @pytest.mark.asyncio
    async def test_creates_ticket_successfully(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "12345",
            "key": "PROJ-123",
            "self": "https://test.atlassian.net/rest/api/3/issue/12345"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.create_jira_ticket(
                project_key="PROJ",
                summary="Test ticket",
                issue_type="Task"
            )

            assert isinstance(result, JiraTicketResult)
            assert result.key == "PROJ-123"
            assert result.id == "12345"
            assert result.url == "https://test.atlassian.net/browse/PROJ-123"
            assert result.summary == "Test ticket"

    @pytest.mark.asyncio
    async def test_calls_correct_api_endpoint(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "1", "key": "PROJ-1"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.create_jira_ticket("PROJ", "Summary", "Task")

            call_args = mock_client.post.call_args
            assert call_args.args[0] == "https://test.atlassian.net/rest/api/3/issue"

    @pytest.mark.asyncio
    async def test_includes_description_in_adf_format(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "1", "key": "PROJ-1"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.create_jira_ticket(
                project_key="PROJ",
                summary="Test",
                issue_type="Bug",
                description="This is a bug"
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs["json"]
            desc = payload["fields"]["description"]
            assert desc["type"] == "doc"
            assert desc["version"] == 1
            assert desc["content"][0]["content"][0]["text"] == "This is a bug"

    @pytest.mark.asyncio
    async def test_includes_priority_when_provided(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "1", "key": "PROJ-1"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.create_jira_ticket(
                project_key="PROJ",
                summary="Test",
                issue_type="Task",
                priority="High"
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["fields"]["priority"] == {"name": "High"}

    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self, unconfigured_tool):
        with pytest.raises(ValueError, match="Jira configuration missing"):
            await unconfigured_tool.create_jira_ticket("PROJ", "Test", "Task")

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, tool):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await tool.create_jira_ticket("PROJ", "Test", "Task")


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_create_jira_ticket(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "1", "key": "PROJ-1"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(
                "create_jira_ticket",
                {
                    "project_key": "PROJ",
                    "summary": "Test ticket",
                    "issue_type": "Task"
                }
            )

            assert "PROJ-1" in result
            assert "Test ticket" in result
            assert "URL" in result

    @pytest.mark.asyncio
    async def test_execute_returns_config_error(self, unconfigured_tool):
        result = await unconfigured_tool.execute(
            "create_jira_ticket",
            {"project_key": "PROJ", "summary": "Test", "issue_type": "Task"}
        )
        assert "Configuration error" in result

    @pytest.mark.asyncio
    async def test_execute_raises_on_unknown_function(self, tool):
        with pytest.raises(ValueError, match="Unknown function"):
            await tool.execute("unknown_function", {})
