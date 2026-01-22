import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.infrastructure.tools.slack import SlackTools, SlackMessageResult, SlackApiError


@pytest.fixture
def tool():
    return SlackTools(bot_token="xoxb-test-token")


@pytest.fixture
def unconfigured_tool():
    return SlackTools(bot_token="")


class TestSlackToolsDefinition:
    def test_tool_definition_has_correct_name(self, tool):
        assert tool.TOOL_DEFINITION["function"]["name"] == "send_slack_message"

    def test_tool_definition_has_required_parameters(self, tool):
        params = tool.TOOL_DEFINITION["function"]["parameters"]
        assert "channel" in params["properties"]
        assert "message" in params["properties"]
        assert "thread_ts" in params["properties"]
        assert set(params["required"]) == {"channel", "message"}

    def test_tool_definition_has_description(self, tool):
        assert "send" in tool.TOOL_DEFINITION["function"]["description"].lower()
        assert "slack" in tool.TOOL_DEFINITION["function"]["description"].lower()


class TestSlackToolsInit:
    def test_init_sets_bot_token(self, tool):
        assert tool.bot_token == "xoxb-test-token"

    def test_init_with_env_variable(self):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-env-token"}):
            tool = SlackTools()
            assert tool.bot_token == "xoxb-env-token"


class TestGetHeaders:
    def test_generates_bearer_auth_header(self, tool):
        headers = tool._get_headers()
        assert headers["Authorization"] == "Bearer xoxb-test-token"
        assert headers["Content-Type"] == "application/json"


class TestSendSlackMessage:
    @pytest.mark.asyncio
    async def test_sends_message_successfully(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channel": "C1234567890",
            "ts": "1234567890.123456",
            "message": {"text": "Hello"}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.send_slack_message(
                channel="#general",
                message="Hello, world!"
            )

            assert isinstance(result, SlackMessageResult)
            assert result.channel == "C1234567890"
            assert result.timestamp == "1234567890.123456"
            assert result.message == "Hello, world!"

    @pytest.mark.asyncio
    async def test_calls_correct_api_endpoint(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "channel": "C123", "ts": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.send_slack_message("#general", "Test")

            call_args = mock_client.post.call_args
            assert call_args.args[0] == "https://slack.com/api/chat.postMessage"

    @pytest.mark.asyncio
    async def test_includes_thread_ts_when_provided(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "channel": "C123", "ts": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.send_slack_message(
                channel="#general",
                message="Reply",
                thread_ts="1234567890.000000"
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["thread_ts"] == "1234567890.000000"

    @pytest.mark.asyncio
    async def test_does_not_include_thread_ts_when_not_provided(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "channel": "C123", "ts": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.send_slack_message("#general", "Test")

            call_args = mock_client.post.call_args
            payload = call_args.kwargs["json"]
            assert "thread_ts" not in payload

    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self, unconfigured_tool):
        with pytest.raises(ValueError, match="Slack configuration missing"):
            await unconfigured_tool.send_slack_message("#general", "Test")

    @pytest.mark.asyncio
    async def test_raises_on_slack_api_error(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "channel_not_found"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(SlackApiError, match="channel_not_found"):
                await tool.send_slack_message("#nonexistent", "Test")

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
                await tool.send_slack_message("#general", "Test")


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_send_slack_message(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channel": "C1234567890",
            "ts": "1234567890.123456"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(
                "send_slack_message",
                {"channel": "#general", "message": "Hello!"}
            )

            assert "Message sent" in result
            assert "C1234567890" in result
            assert "Timestamp" in result

    @pytest.mark.asyncio
    async def test_execute_returns_config_error(self, unconfigured_tool):
        result = await unconfigured_tool.execute(
            "send_slack_message",
            {"channel": "#general", "message": "Test"}
        )
        assert "Configuration error" in result

    @pytest.mark.asyncio
    async def test_execute_returns_slack_api_error(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(
                "send_slack_message",
                {"channel": "#general", "message": "Test"}
            )

            assert "Slack API error" in result
            assert "invalid_auth" in result

    @pytest.mark.asyncio
    async def test_execute_raises_on_unknown_function(self, tool):
        with pytest.raises(ValueError, match="Unknown function"):
            await tool.execute("unknown_function", {})
