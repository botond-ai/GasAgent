"""
Jira Task Creation Node.

Creates a Jira task via MCP (preferred) or REST API (fallback).
"""

import logging
import time
from typing import Dict, Any
import requests
import base64

logger = logging.getLogger(__name__)

# Global configuration (set by graph during initialization)
_jira_config = None


def set_jira_config(config):
    """Set the Jira configuration for this node."""
    global _jira_config
    _jira_config = config


def create_jira_task_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a Jira task using MCP (preferred) or REST API (fallback).

    Uses the extracted task details to create a task in the appropriate Jira project.
    Checks for duplicate issues before creating.

    Args:
        state: Current RAG state

    Returns:
        Updated state with jira_task_key, jira_task_url, and duplicate warnings
    """
    logger.info("===== Create Jira Task node executing =====")
    start_time = time.time()

    # Check if Jira is enabled
    if not _jira_config or not _jira_config.jira_enabled:
        logger.warning("Jira integration not enabled (missing configuration)")
        state["errors"].append("Jira integration not configured")
        state["generated_answer"] = "Jira integration is not configured. Please set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN in your .env file."
        return state

    # Get task details
    department = state.get("jira_department", "support")
    summary = state.get("jira_summary", "Task from RAG system")
    description = state.get("jira_description", "No description provided")
    priority = state.get("jira_priority", "Medium")

    # Map department to Jira project
    project_key = _jira_config.jira_department_mapping.get(department)
    if not project_key:
        logger.warning(f"No Jira project mapping for department: {department}")
        state["errors"].append(f"No Jira project for department: {department}")
        state["generated_answer"] = f"Could not create Jira task: No project mapping for department '{department}'. Please check JIRA_DEPARTMENT_MAPPING in .env file."
        return state

    # Try MCP first if enabled
    if getattr(_jira_config, 'use_jira_mcp', True):
        try:
            result = _create_with_mcp(project_key, summary, description, priority, department)
            if result["success"]:
                _update_state_with_result(state, result, department, summary, priority, start_time)
                return state
            else:
                logger.warning(f"MCP creation failed: {result.get('error')}, falling back to REST API")
        except Exception as e:
            logger.warning(f"MCP not available: {e}, falling back to REST API")

    # Fallback to REST API
    try:
        result = _create_with_rest_api(
            _jira_config,
            project_key,
            summary,
            description,
            priority
        )
        _update_state_with_result(state, result, department, summary, priority, start_time)

    except Exception as e:
        logger.error(f"Jira creation error: {e}", exc_info=True)
        state["errors"].append(f"Jira creation failed: {e}")
        state["generated_answer"] = f"Failed to create Jira task: {e}"

    return state


def _create_with_mcp(
    project_key: str,
    summary: str,
    description: str,
    priority: str,
    department: str
) -> Dict[str, Any]:
    """
    Create Jira issue using MCP with duplicate checking.

    Args:
        project_key: Jira project key
        summary: Issue summary
        description: Issue description
        priority: Issue priority
        department: Department name

    Returns:
        Result dict with success, key, url, duplicates
    """
    from scripts.mcp_client import JiraMCPClient, run_async_in_thread

    logger.info("Creating Jira issue via MCP")

    async def create_issue_async():
        async with JiraMCPClient(
            _jira_config.jira_base_url,
            _jira_config.jira_email,
            _jira_config.jira_api_token
        ) as jira_client:
            return await jira_client.create_issue(
                project_key=project_key,
                summary=summary,
                description=description,
                issue_type="Task",
                priority=priority,
                check_duplicates=True  # Enable duplicate checking
            )

    result = run_async_in_thread(create_issue_async())

    logger.info(f"MCP result: success={result['success']}, duplicates={result.get('duplicate_warning', False)}")

    return result


def _create_with_rest_api(
    config,
    project_key: str,
    summary: str,
    description: str,
    priority: str
) -> Dict[str, Any]:
    """
    Create Jira issue using REST API (fallback).

    Args:
        config: Jira configuration
        project_key: Jira project key
        summary: Issue summary
        description: Issue description
        priority: Issue priority

    Returns:
        Result dict with success, key, url
    """
    logger.info("Creating Jira issue via REST API")

    # Prepare authentication
    auth_string = f"{config.jira_email}:{config.jira_api_token}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json",
    }

    # Map priority
    priority_map = {
        "High": "High",
        "Medium": "Medium",
        "Low": "Low"
    }

    # Create issue payload
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Task"},
            "priority": {"name": priority_map.get(priority, "Medium")}
        }
    }

    # Call Jira API
    url = f"{config.jira_base_url}/rest/api/3/issue"
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=10
    )

    response.raise_for_status()

    # Parse response
    data = response.json()
    task_key = data.get("key")
    task_url = f"{config.jira_base_url}/browse/{task_key}"

    logger.info(f"✓ Created via REST API: {task_key}")

    return {
        "success": True,
        "key": task_key,
        "url": task_url,
        "duplicate_warning": False,
        "similar_issues": []
    }


def _update_state_with_result(
    state: Dict[str, Any],
    result: Dict[str, Any],
    department: str,
    summary: str,
    priority: str,
    start_time: float
):
    """
    Update state with Jira creation result.

    Args:
        state: Current RAG state
        result: Jira creation result
        department: Department name
        summary: Issue summary
        priority: Issue priority
        start_time: Operation start time
    """
    if not result["success"]:
        error_msg = result.get("error", "Unknown error")
        logger.error(f"Jira creation failed: {error_msg}")
        state["errors"].append(f"Jira creation failed: {error_msg}")
        state["generated_answer"] = f"Failed to create Jira task: {error_msg}"
        return

    # Store results
    state["jira_task_key"] = result["key"]
    state["jira_task_url"] = result["url"]

    # Build response message
    response_parts = [
        "✓ Jira task created successfully!\n",
        f"Task Key: {result['key']}",
        f"Department: {department.upper()}",
        f"Priority: {priority}",
        f"Summary: {summary}\n",
        f"View task: {result['url']}"
    ]

    # Add duplicate warning if found
    if result.get("duplicate_warning"):
        similar = result.get("similar_issues", [])
        response_parts.append("\n⚠️  Warning: Found similar existing tickets:")
        for issue in similar[:3]:  # Show top 3
            response_parts.append(f"  • {issue['key']}: {issue['summary']} ({issue['status']})")

        state["jira_duplicate_warning"] = True
        state["jira_similar_issues"] = similar

        logger.warning(f"Created ticket despite {len(similar)} similar issues found")

    state["generated_answer"] = "\n".join(response_parts)

    # Track timing
    latency = (time.time() - start_time) * 1000
    state["step_timings"]["jira_creation_ms"] = latency

    logger.info(f"===== Jira task created: {result['key']} in {latency:.2f}ms =====")
