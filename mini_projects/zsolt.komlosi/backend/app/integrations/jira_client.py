"""
Jira REST API client for SupportAI integration.
"""

import base64
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class JiraIssue:
    """Represents a Jira issue."""

    key: str
    summary: str
    description: Optional[str]
    status: str
    priority: Optional[str]
    issue_type: str
    project_key: str
    reporter: Optional[str]
    assignee: Optional[str]
    created: str
    updated: str
    labels: list[str]

    @classmethod
    def from_api_response(cls, data: dict) -> "JiraIssue":
        """Create JiraIssue from API response."""
        fields = data.get("fields", {})
        return cls(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            description=fields.get("description"),
            status=fields.get("status", {}).get("name", "Unknown"),
            priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
            issue_type=fields.get("issuetype", {}).get("name", "Unknown"),
            project_key=fields.get("project", {}).get("key", ""),
            reporter=fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
            assignee=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            created=fields.get("created", ""),
            updated=fields.get("updated", ""),
            labels=fields.get("labels", []),
        )


@dataclass
class JiraComment:
    """Represents a Jira comment."""

    id: str
    body: str
    author: str
    created: str

    @classmethod
    def from_api_response(cls, data: dict) -> "JiraComment":
        """Create JiraComment from API response."""
        return cls(
            id=data.get("id", ""),
            body=data.get("body", ""),
            author=data.get("author", {}).get("displayName", "Unknown"),
            created=data.get("created", ""),
        )


class JiraClient:
    """
    Jira REST API client.

    Provides methods for interacting with Jira Cloud/Server.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        user_email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        settings = get_settings()

        self.base_url = (base_url or settings.jira_url or "").rstrip("/")
        self.user_email = user_email or settings.jira_user_email
        self.api_token = api_token or settings.jira_api_token

        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if Jira is properly configured."""
        return all([self.base_url, self.user_email, self.api_token])

    def _get_auth_header(self) -> str:
        """Generate Basic Auth header."""
        credentials = f"{self.user_email}:{self.api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.base_url}/rest/api/3",
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_issue(self, issue_key: str) -> JiraIssue:
        """
        Get a Jira issue by key.

        Args:
            issue_key: Jira issue key (e.g., "PROJ-123")

        Returns:
            JiraIssue object
        """
        client = await self._get_client()
        response = await client.get(f"/issue/{issue_key}")
        response.raise_for_status()
        return JiraIssue.from_api_response(response.json())

    async def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        start_at: int = 0,
    ) -> list[JiraIssue]:
        """
        Search for issues using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results
            start_at: Starting index for pagination

        Returns:
            List of JiraIssue objects
        """
        client = await self._get_client()
        response = await client.get(
            "/search",
            params={
                "jql": jql,
                "maxResults": max_results,
                "startAt": start_at,
            },
        )
        response.raise_for_status()
        data = response.json()
        return [JiraIssue.from_api_response(issue) for issue in data.get("issues", [])]

    async def add_comment(self, issue_key: str, body: str, internal: bool = False) -> JiraComment:
        """
        Add a comment to an issue.

        Args:
            issue_key: Jira issue key
            body: Comment text
            internal: If True, adds as internal note (not visible to customer)

        Returns:
            Created JiraComment object
        """
        if internal:
            # Use Service Desk API for internal notes
            return await self._add_service_desk_comment(issue_key, body, public=False)
        else:
            # Use standard Jira API for public comments
            client = await self._get_client()

            # Use Atlassian Document Format for the comment body
            comment_body = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": body}],
                        }
                    ],
                }
            }

            response = await client.post(
                f"/issue/{issue_key}/comment",
                json=comment_body,
            )
            response.raise_for_status()
            return JiraComment.from_api_response(response.json())

    async def _add_service_desk_comment(
        self, issue_key: str, body: str, public: bool = True
    ) -> JiraComment:
        """
        Add a comment using Service Desk API (supports internal notes).

        Args:
            issue_key: Jira issue key
            body: Comment text
            public: If False, comment is internal (not visible to customer)

        Returns:
            Created JiraComment object
        """
        # Service Desk API uses a different base URL
        client = httpx.AsyncClient(
            base_url=f"{self.base_url}/rest/servicedeskapi",
            headers={
                "Authorization": self._get_auth_header(),
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-ExperimentalApi": "opt-in",  # Required for some JSM endpoints
            },
            timeout=30.0,
        )

        try:
            comment_body = {
                "body": body,
                "public": public,
            }

            response = await client.post(
                f"/request/{issue_key}/comment",
                json=comment_body,
            )
            response.raise_for_status()
            data = response.json()

            return JiraComment(
                id=str(data.get("id", "")),
                body=data.get("body", ""),
                author=data.get("author", {}).get("displayName", "Unknown"),
                created=data.get("created", {}).get("iso8601", ""),
            )
        finally:
            await client.aclose()

    async def get_comments(
        self,
        issue_key: str,
        max_results: int = 50,
    ) -> list[JiraComment]:
        """
        Get comments for an issue.

        Args:
            issue_key: Jira issue key
            max_results: Maximum number of comments

        Returns:
            List of JiraComment objects
        """
        client = await self._get_client()
        response = await client.get(
            f"/issue/{issue_key}/comment",
            params={"maxResults": max_results},
        )
        response.raise_for_status()
        data = response.json()
        return [JiraComment.from_api_response(c) for c in data.get("comments", [])]

    async def update_issue(
        self,
        issue_key: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[list[str]] = None,
        duedate: Optional[str] = None,
    ) -> None:
        """
        Update an issue's fields.

        Args:
            issue_key: Jira issue key
            summary: New summary (optional)
            description: New description (optional)
            priority: New priority name (optional)
            labels: New labels (optional)
            duedate: Due date in YYYY-MM-DD format (optional)
        """
        client = await self._get_client()

        fields = {}
        if summary is not None:
            fields["summary"] = summary
        if description is not None:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }
        if priority is not None:
            fields["priority"] = {"name": priority}
        if labels is not None:
            fields["labels"] = labels
        if duedate is not None:
            fields["duedate"] = duedate

        if fields:
            response = await client.put(
                f"/issue/{issue_key}",
                json={"fields": fields},
            )
            response.raise_for_status()

    async def transition_issue(
        self,
        issue_key: str,
        transition_name: str,
    ) -> None:
        """
        Transition an issue to a new status.

        Args:
            issue_key: Jira issue key
            transition_name: Name of the transition
        """
        client = await self._get_client()

        # First, get available transitions
        response = await client.get(f"/issue/{issue_key}/transitions")
        response.raise_for_status()
        transitions = response.json().get("transitions", [])

        # Find the transition by name
        transition_id = None
        for t in transitions:
            if t.get("name", "").lower() == transition_name.lower():
                transition_id = t.get("id")
                break

        if not transition_id:
            available = [t.get("name") for t in transitions]
            raise ValueError(
                f"Transition '{transition_name}' not found. "
                f"Available: {available}"
            )

        # Perform the transition
        response = await client.post(
            f"/issue/{issue_key}/transitions",
            json={"transition": {"id": transition_id}},
        )
        response.raise_for_status()

    async def get_projects(self) -> list[dict]:
        """
        Get all accessible projects.

        Returns:
            List of project dictionaries
        """
        client = await self._get_client()
        response = await client.get("/project")
        response.raise_for_status()
        return response.json()

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> JiraIssue:
        """
        Create a new issue.

        Args:
            project_key: Project key (e.g., "PROJ")
            summary: Issue summary
            description: Issue description
            issue_type: Issue type name (default: "Task")
            priority: Priority name (optional)
            labels: Issue labels (optional)

        Returns:
            Created JiraIssue object
        """
        client = await self._get_client()

        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
            "issuetype": {"name": issue_type},
        }

        if priority:
            fields["priority"] = {"name": priority}
        if labels:
            fields["labels"] = labels

        response = await client.post("/issue", json={"fields": fields})
        response.raise_for_status()

        # Get the created issue details
        created_key = response.json().get("key")
        return await self.get_issue(created_key)
