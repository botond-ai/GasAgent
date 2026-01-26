"""Jira Cloud API client service.

Provides async methods to fetch tickets from Jira Cloud using the REST API.
"""

import base64
from datetime import datetime
from typing import Optional

import httpx

from app.core.config import Settings
from app.models.schemas import JiraTicket


class JiraService:
    """Async Jira Cloud API client."""

    def __init__(self, settings: Settings):
        """Initialize Jira service with settings.

        Args:
            settings: Application settings containing Jira configuration
        """
        self.settings = settings
        self.base_url = settings.jira_url.rstrip("/")
        self._auth_header = self._build_auth_header()

    def _build_auth_header(self) -> str:
        """Build Basic auth header from email and API token.

        Returns:
            Base64-encoded authorization header value
        """
        credentials = f"{self.settings.jira_email}:{self.settings.jira_api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _build_jql_query(
        self, since: datetime, project_key: Optional[str] = None
    ) -> str:
        """Build JQL query to fetch tickets created since a given time.

        Args:
            since: Fetch tickets created after this timestamp
            project_key: Optional project key to filter by

        Returns:
            JQL query string
        """
        # Format datetime for JQL (Jira uses yyyy-MM-dd HH:mm format)
        since_str = since.strftime("%Y-%m-%d %H:%M")

        jql_parts = [f'created >= "{since_str}"']

        if project_key:
            jql_parts.append(f'project = "{project_key}"')

        jql = " AND ".join(jql_parts) + " ORDER BY created ASC"
        return jql

    def _parse_ticket(self, raw: dict) -> JiraTicket:
        """Parse raw Jira API response into JiraTicket model.

        Args:
            raw: Raw ticket data from Jira API

        Returns:
            Parsed JiraTicket instance
        """
        fields = raw.get("fields", {})
        reporter = fields.get("reporter") or {}
        priority = fields.get("priority") or {}
        status = fields.get("status") or {}

        # Parse created timestamp (ISO 8601 format)
        created_str = fields.get("created", "")
        created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))

        return JiraTicket(
            key=raw.get("key", ""),
            summary=fields.get("summary", ""),
            description=fields.get("description"),
            created=created,
            reporter_email=reporter.get("emailAddress"),
            reporter_name=reporter.get("displayName"),
            priority=priority.get("name"),
            status=status.get("name", "Unknown"),
        )

    async def fetch_new_tickets(
        self, since: datetime, max_results: int = 50
    ) -> list[JiraTicket]:
        """Fetch tickets created since the given timestamp.

        Args:
            since: Fetch tickets created after this timestamp
            max_results: Maximum number of tickets to return

        Returns:
            List of JiraTicket objects

        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        jql = self._build_jql_query(since, self.settings.jira_project_key or None)

        url = f"{self.base_url}/rest/api/3/search"
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": "key,summary,description,created,reporter,priority,status",
        }
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            issues = data.get("issues", [])

            return [self._parse_ticket(issue) for issue in issues]

    async def test_connection(self) -> bool:
        """Test the Jira connection with current credentials.

        Returns:
            True if connection is successful, False otherwise
        """
        url = f"{self.base_url}/rest/api/3/myself"
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10)
                return response.status_code == 200
        except Exception:
            return False
