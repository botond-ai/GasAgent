"""
MCP Client for Jira Integration.

Provides structured access to Jira via Model Context Protocol.
"""

import logging
from typing import Dict, Any, List, Optional
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class JiraMCPClient:
    """
    MCP client for Jira operations.

    Provides high-level methods for:
    - Creating issues
    - Searching for duplicates
    - Updating issues
    - Adding comments
    """

    def __init__(self, jira_base_url: str, jira_email: str, jira_api_token: str):
        """
        Initialize Jira MCP client.

        Args:
            jira_base_url: Jira instance URL
            jira_email: Jira account email
            jira_api_token: Jira API token
        """
        self.jira_base_url = jira_base_url
        self.jira_email = jira_email
        self.jira_api_token = jira_api_token
        self._session: Optional[ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Establish MCP connection to Jira server."""
        try:
            # Configure MCP server parameters
            server_params = StdioServerParameters(
                command="npx",
                args=[
                    "-y",
                    "@modelcontextprotocol/server-atlassian",
                    self.jira_base_url,
                    self.jira_email,
                    self.jira_api_token
                ],
                env=None
            )

            # Create stdio client
            self._stdio_context = stdio_client(server_params)
            self._stdio, self._write = await self._stdio_context.__aenter__()

            # Create session
            self._session = ClientSession(self._stdio, self._write)
            await self._session.__aenter__()

            # Initialize session
            await self._session.initialize()

            logger.info("✓ Connected to Jira MCP server")

        except Exception as e:
            logger.error(f"Failed to connect to Jira MCP server: {e}")
            raise

    async def disconnect(self):
        """Close MCP connection."""
        try:
            if self._session:
                await self._session.__aexit__(None, None, None)
            if hasattr(self, '_stdio_context'):
                await self._stdio_context.__aexit__(None, None, None)
            logger.info("✓ Disconnected from Jira MCP server")
        except Exception as e:
            logger.error(f"Error disconnecting from Jira MCP: {e}")

    async def search_similar_issues(
        self,
        project_key: str,
        summary: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar issues to avoid duplicates.

        Args:
            project_key: Jira project key (e.g., "DEV")
            summary: Issue summary to search for
            max_results: Maximum number of results

        Returns:
            List of similar issues with key, summary, status
        """
        try:
            # Create JQL query to find similar issues
            # Search for issues with similar summary text that are not resolved
            search_terms = ' '.join(summary.split()[:5])  # Use first 5 words
            jql = f'project = {project_key} AND summary ~ "{search_terms}" AND status != Done AND status != Closed'

            logger.info(f"Searching for similar issues: {jql}")

            # Call MCP search tool
            result = await self._session.call_tool(
                "jira_search_issues",
                arguments={
                    "jql": jql,
                    "max_results": max_results,
                    "fields": ["summary", "status", "priority", "assignee"]
                }
            )

            # Parse results
            issues = []
            if result and result.content:
                # MCP returns content as list of text/image content blocks
                for content_block in result.content:
                    if content_block.type == "text":
                        import json
                        data = json.loads(content_block.text)
                        issues = data.get("issues", [])
                        break

            logger.info(f"Found {len(issues)} similar issues")
            return issues

        except Exception as e:
            logger.error(f"Error searching for similar issues: {e}")
            return []

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: str = "Medium",
        check_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Create a Jira issue with duplicate checking.

        Args:
            project_key: Jira project key
            summary: Issue summary/title
            description: Issue description
            issue_type: Type of issue (Task, Bug, Story, etc.)
            priority: Priority (High, Medium, Low)
            check_duplicates: Whether to check for duplicates first

        Returns:
            Dict with issue details (key, url, warnings)
        """
        result = {
            "success": False,
            "key": None,
            "url": None,
            "duplicate_warning": False,
            "similar_issues": []
        }

        try:
            # Check for duplicates first
            if check_duplicates:
                similar = await self.search_similar_issues(project_key, summary)
                if similar:
                    result["duplicate_warning"] = True
                    result["similar_issues"] = [
                        {
                            "key": issue.get("key"),
                            "summary": issue.get("fields", {}).get("summary"),
                            "status": issue.get("fields", {}).get("status", {}).get("name")
                        }
                        for issue in similar
                    ]
                    logger.warning(f"Found {len(similar)} similar issues")

            # Create the issue
            logger.info(f"Creating Jira issue in project {project_key}")

            mcp_result = await self._session.call_tool(
                "jira_create_issue",
                arguments={
                    "project_key": project_key,
                    "summary": summary,
                    "description": description,
                    "issue_type": issue_type,
                    "priority": priority
                }
            )

            # Parse result
            if mcp_result and mcp_result.content:
                for content_block in mcp_result.content:
                    if content_block.type == "text":
                        import json
                        data = json.loads(content_block.text)

                        result["success"] = True
                        result["key"] = data.get("key")
                        result["url"] = f"{self.jira_base_url}/browse/{result['key']}"

                        logger.info(f"✓ Created Jira issue: {result['key']}")
                        break

            return result

        except Exception as e:
            logger.error(f"Error creating Jira issue: {e}", exc_info=True)
            result["error"] = str(e)
            return result

    async def add_comment(self, issue_key: str, comment: str) -> bool:
        """
        Add a comment to an existing issue.

        Args:
            issue_key: Jira issue key (e.g., "DEV-123")
            comment: Comment text

        Returns:
            True if successful
        """
        try:
            logger.info(f"Adding comment to {issue_key}")

            await self._session.call_tool(
                "jira_add_comment",
                arguments={
                    "issue_key": issue_key,
                    "comment": comment
                }
            )

            logger.info(f"✓ Comment added to {issue_key}")
            return True

        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            return False

    async def update_issue(
        self,
        issue_key: str,
        fields: Dict[str, Any]
    ) -> bool:
        """
        Update an existing issue.

        Args:
            issue_key: Jira issue key
            fields: Fields to update (e.g., {"priority": "High"})

        Returns:
            True if successful
        """
        try:
            logger.info(f"Updating {issue_key}")

            await self._session.call_tool(
                "jira_update_issue",
                arguments={
                    "issue_key": issue_key,
                    "fields": fields
                }
            )

            logger.info(f"✓ Updated {issue_key}")
            return True

        except Exception as e:
            logger.error(f"Error updating issue: {e}")
            return False

    async def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Get issue details.

        Args:
            issue_key: Jira issue key

        Returns:
            Issue details or None
        """
        try:
            result = await self._session.call_tool(
                "jira_get_issue",
                arguments={
                    "issue_key": issue_key
                }
            )

            if result and result.content:
                for content_block in result.content:
                    if content_block.type == "text":
                        import json
                        return json.loads(content_block.text)

            return None

        except Exception as e:
            logger.error(f"Error getting issue: {e}")
            return None


def run_async_in_thread(coro):
    """
    Helper to run async code in sync context.

    Creates a new event loop in the current thread if needed.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
