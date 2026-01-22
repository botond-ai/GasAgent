"""
Tool executor for running LLM tools.
"""
from typing import Any

from .exchange_rates import ExchangeRateTool
from .holidays import HolidayTools
from .jira import JiraTools
from .slack import SlackTools


class ToolExecutor:
    """
    Executes LLM tools and returns results.

    Manages tool registration and execution dispatch.
    """

    def __init__(self):
        self.exchange_tool = ExchangeRateTool()
        self.holiday_tools = HolidayTools()
        self.jira_tools = JiraTools()
        self.slack_tools = SlackTools()

        # Map function names to their tool instances
        self._tool_map = {
            "convert_currency": self.exchange_tool,
            "is_us_holiday": self.holiday_tools,
            "list_us_holidays": self.holiday_tools,
            "create_jira_ticket": self.jira_tools,
            "send_slack_message": self.slack_tools,
        }

    def get_tool_definitions(self) -> list[dict]:
        """Get all tool definitions for OpenAI function calling."""
        return [
            self.exchange_tool.TOOL_DEFINITION,
            *self.holiday_tools.TOOL_DEFINITIONS,
            self.jira_tools.TOOL_DEFINITION,
            self.slack_tools.TOOL_DEFINITION,
        ]

    async def execute(self, function_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute a tool by function name.

        Args:
            function_name: The name of the function to execute
            arguments: The arguments to pass to the function

        Returns:
            String result from the tool
        """
        tool = self._tool_map.get(function_name)
        if tool is None:
            return f"Error: Unknown tool '{function_name}'"

        try:
            return await tool.execute(function_name, arguments)
        except Exception as e:
            return f"Error executing {function_name}: {str(e)}"
