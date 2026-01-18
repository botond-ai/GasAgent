"""
Jira LangChain tools for the SupportAI agent.

These tools allow the agent to interact with Jira within the LangGraph workflow.
"""

import asyncio
from typing import Optional

from langchain_core.tools import tool

from app.config import get_settings
from app.integrations.jira_client import JiraClient


def _get_client() -> JiraClient:
    """Get Jira client instance."""
    return JiraClient()


def _run_async(coro):
    """Run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@tool
def jira_get_issue(issue_key: str) -> dict:
    """
    Get details of a Jira issue by its key.

    Args:
        issue_key: The Jira issue key (e.g., "PROJ-123")

    Returns:
        Dictionary with issue details including summary, description, status, etc.
    """
    settings = get_settings()
    if not settings.jira_configured:
        return {"error": "Jira is not configured"}

    client = _get_client()

    async def _get():
        issue = await client.get_issue(issue_key)
        await client.close()
        return {
            "key": issue.key,
            "summary": issue.summary,
            "description": issue.description,
            "status": issue.status,
            "priority": issue.priority,
            "issue_type": issue.issue_type,
            "reporter": issue.reporter,
            "assignee": issue.assignee,
            "labels": issue.labels,
        }

    try:
        return _run_async(_get())
    except Exception as e:
        return {"error": str(e)}


@tool
def jira_search_issues(jql: str, max_results: int = 10) -> dict:
    """
    Search for Jira issues using JQL (Jira Query Language).

    Args:
        jql: JQL query string (e.g., "project = PROJ AND status = Open")
        max_results: Maximum number of results to return (default: 10)

    Returns:
        Dictionary with list of matching issues
    """
    settings = get_settings()
    if not settings.jira_configured:
        return {"error": "Jira is not configured"}

    client = _get_client()

    async def _search():
        issues = await client.search_issues(jql, max_results)
        await client.close()
        return {
            "count": len(issues),
            "issues": [
                {
                    "key": i.key,
                    "summary": i.summary,
                    "status": i.status,
                    "priority": i.priority,
                }
                for i in issues
            ],
        }

    try:
        return _run_async(_search())
    except Exception as e:
        return {"error": str(e)}


@tool
def jira_add_comment(issue_key: str, comment: str) -> dict:
    """
    Add a comment to a Jira issue.

    Args:
        issue_key: The Jira issue key (e.g., "PROJ-123")
        comment: The comment text to add

    Returns:
        Dictionary with result status
    """
    settings = get_settings()
    if not settings.jira_configured:
        return {"error": "Jira is not configured"}

    client = _get_client()

    async def _comment():
        result = await client.add_comment(issue_key, comment)
        await client.close()
        return {
            "success": True,
            "comment_id": result.id,
            "issue_key": issue_key,
        }

    try:
        return _run_async(_comment())
    except Exception as e:
        return {"error": str(e)}


@tool
def jira_update_priority(issue_key: str, priority: str) -> dict:
    """
    Update the priority of a Jira issue.

    Args:
        issue_key: The Jira issue key (e.g., "PROJ-123")
        priority: The new priority name (e.g., "High", "Medium", "Low")

    Returns:
        Dictionary with result status
    """
    settings = get_settings()
    if not settings.jira_configured:
        return {"error": "Jira is not configured"}

    client = _get_client()

    async def _update():
        await client.update_issue(issue_key, priority=priority)
        await client.close()
        return {
            "success": True,
            "issue_key": issue_key,
            "new_priority": priority,
        }

    try:
        return _run_async(_update())
    except Exception as e:
        return {"error": str(e)}


@tool
def jira_add_labels(issue_key: str, labels: list[str]) -> dict:
    """
    Add labels to a Jira issue (for categorization).

    Args:
        issue_key: The Jira issue key (e.g., "PROJ-123")
        labels: List of labels to add

    Returns:
        Dictionary with result status
    """
    settings = get_settings()
    if not settings.jira_configured:
        return {"error": "Jira is not configured"}

    client = _get_client()

    async def _add_labels():
        # First get existing labels
        issue = await client.get_issue(issue_key)
        existing = issue.labels or []
        new_labels = list(set(existing + labels))

        await client.update_issue(issue_key, labels=new_labels)
        await client.close()
        return {
            "success": True,
            "issue_key": issue_key,
            "labels": new_labels,
        }

    try:
        return _run_async(_add_labels())
    except Exception as e:
        return {"error": str(e)}


@tool
def jira_transition_issue(issue_key: str, transition: str) -> dict:
    """
    Transition a Jira issue to a new status.

    Args:
        issue_key: The Jira issue key (e.g., "PROJ-123")
        transition: The transition name (e.g., "In Progress", "Done")

    Returns:
        Dictionary with result status
    """
    settings = get_settings()
    if not settings.jira_configured:
        return {"error": "Jira is not configured"}

    client = _get_client()

    async def _transition():
        await client.transition_issue(issue_key, transition)
        await client.close()
        return {
            "success": True,
            "issue_key": issue_key,
            "transition": transition,
        }

    try:
        return _run_async(_transition())
    except Exception as e:
        return {"error": str(e)}


# List of Jira tools for the agent
JIRA_TOOLS = [
    jira_get_issue,
    jira_search_issues,
    jira_add_comment,
    jira_update_priority,
    jira_add_labels,
    jira_transition_issue,
]
