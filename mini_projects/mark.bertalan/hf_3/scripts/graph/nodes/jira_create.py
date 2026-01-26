"""
Jira Task Creation Node.

Creates a Jira task via REST API.
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
    Create a Jira task using the Jira REST API.

    Uses the extracted task details to create a task in the appropriate Jira project.

    Args:
        state: Current RAG state

    Returns:
        Updated state with jira_task_key and jira_task_url
    """
    logger.info("Create Jira Task node executing")
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

    try:
        # Prepare Jira API request
        auth_string = f"{_jira_config.jira_email}:{_jira_config.jira_api_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
        }

        # Map priority to Jira priority ID (customize based on your Jira instance)
        priority_map = {
            "High": "High",
            "Medium": "Medium",
            "Low": "Low"
        }

        # Create issue payload
        payload = {
            "fields": {
                "project": {
                    "key": project_key
                },
                "summary": summary,
                "description": description,
                "issuetype": {
                    "name": "Task"
                },
                "priority": {
                    "name": priority_map.get(priority, "Medium")
                }
            }
        }

        # Call Jira API
        url = f"{_jira_config.jira_base_url}/rest/api/3/issue"
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10
        )

        response.raise_for_status()

        # Parse response
        result = response.json()
        task_key = result.get("key")
        task_url = f"{_jira_config.jira_base_url}/browse/{task_key}"

        # Store results
        state["jira_task_key"] = task_key
        state["jira_task_url"] = task_url

        # Update generated answer
        state["generated_answer"] = (
            f"✓ Jira task created successfully!\n\n"
            f"Task Key: {task_key}\n"
            f"Department: {department.upper()}\n"
            f"Priority: {priority}\n"
            f"Summary: {summary}\n\n"
            f"View task: {task_url}"
        )

        # Track timing
        latency = (time.time() - start_time) * 1000
        state["step_timings"]["jira_creation_ms"] = latency

        logger.info(f"Jira task created: {task_key} in {latency:.2f}ms")

    except requests.exceptions.HTTPError as e:
        error_msg = f"Jira API error: {e}"
        if e.response is not None:
            error_msg += f" - {e.response.text}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["generated_answer"] = f"Failed to create Jira task: {error_msg}"

    except Exception as e:
        logger.error(f"Jira creation error: {e}")
        state["errors"].append(f"Jira creation failed: {e}")
        state["generated_answer"] = f"Failed to create Jira task: {e}"

    return state
