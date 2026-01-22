import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.infrastructure.tools.tool_executor import ToolExecutor


@pytest.fixture
def executor():
    return ToolExecutor()


class TestToolExecutorInit:
    def test_creates_exchange_tool(self, executor):
        assert executor.exchange_tool is not None

    def test_creates_holiday_tools(self, executor):
        assert executor.holiday_tools is not None

    def test_creates_jira_tools(self, executor):
        assert executor.jira_tools is not None

    def test_creates_slack_tools(self, executor):
        assert executor.slack_tools is not None

    def test_tool_map_has_all_functions(self, executor):
        assert "convert_currency" in executor._tool_map
        assert "is_us_holiday" in executor._tool_map
        assert "list_us_holidays" in executor._tool_map
        assert "create_jira_ticket" in executor._tool_map
        assert "send_slack_message" in executor._tool_map


class TestGetToolDefinitions:
    def test_returns_list_of_definitions(self, executor):
        definitions = executor.get_tool_definitions()
        assert isinstance(definitions, list)
        assert len(definitions) == 5  # 1 exchange + 2 holiday + 1 jira + 1 slack

    def test_contains_convert_currency(self, executor):
        definitions = executor.get_tool_definitions()
        names = [d["function"]["name"] for d in definitions]
        assert "convert_currency" in names

    def test_contains_is_us_holiday(self, executor):
        definitions = executor.get_tool_definitions()
        names = [d["function"]["name"] for d in definitions]
        assert "is_us_holiday" in names

    def test_contains_list_us_holidays(self, executor):
        definitions = executor.get_tool_definitions()
        names = [d["function"]["name"] for d in definitions]
        assert "list_us_holidays" in names

    def test_contains_create_jira_ticket(self, executor):
        definitions = executor.get_tool_definitions()
        names = [d["function"]["name"] for d in definitions]
        assert "create_jira_ticket" in names

    def test_contains_send_slack_message(self, executor):
        definitions = executor.get_tool_definitions()
        names = [d["function"]["name"] for d in definitions]
        assert "send_slack_message" in names

    def test_all_definitions_have_function_type(self, executor):
        definitions = executor.get_tool_definitions()
        assert all(d["type"] == "function" for d in definitions)


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_convert_currency(self, executor):
        mock_response = MagicMock()
        mock_response.json.return_value = {"rates": {"EUR": 92.5}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await executor.execute(
                "convert_currency",
                {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}
            )

            assert "USD" in result
            assert "EUR" in result

    @pytest.mark.asyncio
    async def test_execute_is_us_holiday(self, executor):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"date": "2024-12-25", "name": "Christmas Day", "localName": "Christmas Day"}
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await executor.execute(
                "is_us_holiday",
                {"date": "2024-12-25"}
            )

            assert "Christmas" in result

    @pytest.mark.asyncio
    async def test_execute_list_us_holidays(self, executor):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"date": "2024-01-01", "name": "New Year's Day", "localName": "New Year's Day"}
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await executor.execute(
                "list_us_holidays",
                {"year": 2024}
            )

            assert "2024" in result
            assert "New Year" in result

    @pytest.mark.asyncio
    async def test_execute_create_jira_ticket(self, executor):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "123", "key": "PROJ-1"}
        mock_response.raise_for_status = MagicMock()

        # Configure Jira tool
        executor.jira_tools.base_url = "https://test.atlassian.net"
        executor.jira_tools.email = "test@example.com"
        executor.jira_tools.api_token = "test-token"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await executor.execute(
                "create_jira_ticket",
                {"project_key": "PROJ", "summary": "Test", "issue_type": "Task"}
            )

            assert "PROJ-1" in result

    @pytest.mark.asyncio
    async def test_execute_send_slack_message(self, executor):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "channel": "C123", "ts": "123.456"}
        mock_response.raise_for_status = MagicMock()

        # Configure Slack tool
        executor.slack_tools.bot_token = "xoxb-test-token"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await executor.execute(
                "send_slack_message",
                {"channel": "#general", "message": "Hello!"}
            )

            assert "Message sent" in result

    @pytest.mark.asyncio
    async def test_execute_unknown_function_returns_error(self, executor):
        result = await executor.execute("unknown_function", {})

        assert "Error" in result
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_execute_handles_tool_exception(self, executor):
        with patch.object(
            executor.exchange_tool,
            "execute",
            side_effect=Exception("API error")
        ):
            result = await executor.execute(
                "convert_currency",
                {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}
            )

            assert "Error" in result
            assert "API error" in result


class TestToolMapping:
    def test_convert_currency_maps_to_exchange_tool(self, executor):
        assert executor._tool_map["convert_currency"] is executor.exchange_tool

    def test_is_us_holiday_maps_to_holiday_tools(self, executor):
        assert executor._tool_map["is_us_holiday"] is executor.holiday_tools

    def test_list_us_holidays_maps_to_holiday_tools(self, executor):
        assert executor._tool_map["list_us_holidays"] is executor.holiday_tools

    def test_create_jira_ticket_maps_to_jira_tools(self, executor):
        assert executor._tool_map["create_jira_ticket"] is executor.jira_tools

    def test_send_slack_message_maps_to_slack_tools(self, executor):
        assert executor._tool_map["send_slack_message"] is executor.slack_tools
