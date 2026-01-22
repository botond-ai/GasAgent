"""
Jira integration tool for LLM function calling.

Uses Jira REST API v3 (Atlassian Cloud).
Requires JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN environment variables.
"""
import os
import base64
import httpx
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class JiraTicketResult:
    """Result of creating a Jira ticket."""
    key: str
    id: str
    url: str
    summary: str


class JiraTools:
    """
    LLM tool for Jira ticket creation.

    Requires environment variables:
    - JIRA_BASE_URL: Your Jira instance URL (e.g., https://yourcompany.atlassian.net)
    - JIRA_EMAIL: Email address for authentication
    - JIRA_API_TOKEN: API token from https://id.atlassian.com/manage-profile/security/api-tokens
    """

    TOOL_DEFINITION = {
        "type": "function",
        "function": {
            "name": "create_jira_ticket",
            "description": "Create a new Jira ticket/issue in a specified project",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_key": {
                        "type": "string",
                        "description": "The Jira project key (e.g., 'PROJ', 'DEV', 'SUPPORT')"
                    },
                    "summary": {
                        "type": "string",
                        "description": "The ticket title/summary"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the issue"
                    },
                    "issue_type": {
                        "type": "string",
                        "description": "Type of issue: Task, Bug, Story, Epic",
                        "enum": ["Task", "Bug", "Story", "Epic"]
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority level: Highest, High, Medium, Low, Lowest",
                        "enum": ["Highest", "High", "Medium", "Low", "Lowest"]
                    }
                },
                "required": ["project_key", "summary", "issue_type"]
            }
        }
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        self.base_url = (base_url or os.getenv("JIRA_BASE_URL", "")).rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL", "")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN", "")

    def _get_auth_header(self) -> str:
        """Generate Basic Auth header."""
        credentials = f"{self.email}:{self.api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def create_jira_ticket(
        self,
        project_key: str,
        summary: str,
        issue_type: str,
        description: Optional[str] = None,
        priority: Optional[str] = None
    ) -> JiraTicketResult:
        """
        Create a new Jira ticket.

        Args:
            project_key: The project key (e.g., "PROJ")
            summary: Ticket title
            issue_type: Type of issue (Task, Bug, Story, Epic)
            description: Optional detailed description
            priority: Optional priority level

        Returns:
            JiraTicketResult with ticket details
        """
        if not self.base_url or not self.email or not self.api_token:
            raise ValueError(
                "Jira configuration missing. Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN."
            )

        # Build the issue payload
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        if description:
            # Jira Cloud uses Atlassian Document Format (ADF) for description
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }
                ]
            }

        if priority:
            fields["priority"] = {"name": priority}

        payload = {"fields": fields}

        headers = {
            "Authorization": self._get_auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/rest/api/3/issue",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        return JiraTicketResult(
            key=data["key"],
            id=data["id"],
            url=f"{self.base_url}/browse/{data['key']}",
            summary=summary
        )

    async def execute(self, function_name: str, arguments: dict[str, Any]) -> str:
        """Execute the tool based on function name and arguments."""
        if function_name == "create_jira_ticket":
            try:
                result = await self.create_jira_ticket(
                    project_key=arguments["project_key"],
                    summary=arguments["summary"],
                    issue_type=arguments["issue_type"],
                    description=arguments.get("description"),
                    priority=arguments.get("priority")
                )
                return (
                    f"Created Jira ticket {result.key}: '{result.summary}'\n"
                    f"URL: {result.url}"
                )
            except ValueError as e:
                return f"Configuration error: {str(e)}"
            except httpx.HTTPStatusError as e:
                return f"Jira API error: {e.response.status_code} - {e.response.text}"

        raise ValueError(f"Unknown function: {function_name}")
