"""
Slack integration tool for LLM function calling.

Uses Slack Web API.
Requires SLACK_BOT_TOKEN environment variable.
"""
import os
import httpx
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SlackMessageResult:
    """Result of sending a Slack message."""
    channel: str
    timestamp: str
    message: str


class SlackTools:
    """
    LLM tool for sending Slack messages.

    Requires environment variables:
    - SLACK_BOT_TOKEN: Bot User OAuth Token (starts with xoxb-)
      Get it from https://api.slack.com/apps -> OAuth & Permissions

    The bot needs these scopes:
    - chat:write (to send messages)
    - chat:write.public (to send to channels without joining)
    """

    TOOL_DEFINITION = {
        "type": "function",
        "function": {
            "name": "send_slack_message",
            "description": "Send a message to a Slack channel or user",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "The channel name (e.g., '#general'), channel ID, or user ID to send the message to"
                    },
                    "message": {
                        "type": "string",
                        "description": "The message text to send. Supports Slack markdown formatting."
                    },
                    "thread_ts": {
                        "type": "string",
                        "description": "Optional: timestamp of parent message to reply in a thread"
                    }
                },
                "required": ["channel", "message"]
            }
        }
    }

    BASE_URL = "https://slack.com/api"

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN", "")

    def _get_headers(self) -> dict:
        """Generate request headers with auth."""
        return {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }

    async def send_slack_message(
        self,
        channel: str,
        message: str,
        thread_ts: Optional[str] = None
    ) -> SlackMessageResult:
        """
        Send a message to a Slack channel.

        Args:
            channel: Channel name (#channel), channel ID (C1234567890), or user ID (U1234567890)
            message: The message text (supports Slack mrkdwn)
            thread_ts: Optional parent message timestamp for threading

        Returns:
            SlackMessageResult with message details
        """
        if not self.bot_token:
            raise ValueError(
                "Slack configuration missing. Set SLACK_BOT_TOKEN environment variable."
            )

        payload = {
            "channel": channel,
            "text": message,
        }

        if thread_ts:
            payload["thread_ts"] = thread_ts

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers=self._get_headers(),
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        if not data.get("ok"):
            error = data.get("error", "Unknown error")
            raise SlackApiError(f"Slack API error: {error}")

        return SlackMessageResult(
            channel=data.get("channel", channel),
            timestamp=data.get("ts", ""),
            message=message
        )

    async def execute(self, function_name: str, arguments: dict[str, Any]) -> str:
        """Execute the tool based on function name and arguments."""
        if function_name == "send_slack_message":
            try:
                result = await self.send_slack_message(
                    channel=arguments["channel"],
                    message=arguments["message"],
                    thread_ts=arguments.get("thread_ts")
                )
                return (
                    f"Message sent to {result.channel}\n"
                    f"Timestamp: {result.timestamp}"
                )
            except ValueError as e:
                return f"Configuration error: {str(e)}"
            except SlackApiError as e:
                return str(e)
            except httpx.HTTPStatusError as e:
                return f"HTTP error: {e.response.status_code}"

        raise ValueError(f"Unknown function: {function_name}")


class SlackApiError(Exception):
    """Custom exception for Slack API errors."""
    pass
