"""
Jira MCP Tools - Wraps AtlassianClient for MCP protocol.

Tools:
- create_ticket: Create a new Jira ticket
- search_issues: Search existing issues
"""

import logging
from typing import Dict, Any

try:
    from mcp.types import Tool, TextContent
except ImportError:
    Tool = None
    TextContent = None

logger = logging.getLogger(__name__)


def create_ticket_tool() -> Tool:
    """
    Create a Jira ticket.
    
    MCP Tool definition for creating Jira tickets.
    """
    return Tool(
        name="jira_create_ticket",
        description="Create a new Jira ticket in the SCRUM project",
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Ticket summary (title)"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed ticket description"
                },
                "issue_type": {
                    "type": "string",
                    "enum": ["Task", "Bug", "Story", "Epic"],
                    "description": "Issue type (default: Task)"
                },
                "priority": {
                    "type": "string",
                    "enum": ["Lowest", "Low", "Medium", "High", "Highest"],
                    "description": "Priority level"
                }
            },
            "required": ["summary", "description"]
        }
    )


async def create_ticket(
    summary: str,
    description: str,
    issue_type: str = "Task",
    priority: str = "Medium"
) -> Dict[str, Any]:
    """
    Create a Jira ticket via AtlassianClient.
    
    Args:
        summary: Ticket title
        description: Ticket body
        issue_type: Type of issue
        priority: Priority level
    
    Returns:
        Ticket creation result {success, ticket_key, ticket_url, error}
    """
    try:
        from infrastructure.atlassian_client import atlassian_client
        
        logger.info(f"🎫 Creating Jira ticket: {summary}")
        
        result = await atlassian_client.create_jira_ticket(
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=priority
        )
        
        logger.info(f"✅ Ticket created: {result.get('ticket_key')}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Jira ticket creation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def search_issues_tool() -> Tool:
    """
    Search Jira issues.
    
    MCP Tool definition for searching issues.
    """
    return Tool(
        name="jira_search_issues",
        description="Search for Jira issues by JQL (Jira Query Language)",
        inputSchema={
            "type": "object",
            "properties": {
                "jql": {
                    "type": "string",
                    "description": "JQL query string (e.g., 'project = SCRUM AND status = Open')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default: 10)"
                }
            },
            "required": ["jql"]
        }
    )


async def search_issues(
    jql: str,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Search Jira issues via AtlassianClient.
    
    Args:
        jql: Jira Query Language string
        limit: Maximum number of results
    
    Returns:
        Search results {issues: [...], total, error}
    """
    try:
        from infrastructure.atlassian_client import atlassian_client
        
        logger.info(f"🔍 Searching Jira: {jql}")
        
        result = await atlassian_client.search_issues(
            jql=jql,
            limit=limit
        )
        
        logger.info(f"✅ Found {len(result.get('issues', []))} issues")
        return result
        
    except Exception as e:
        logger.error(f"❌ Jira search failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
