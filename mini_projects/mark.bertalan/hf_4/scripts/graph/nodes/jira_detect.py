"""
Jira Intent Detection Node.

Detects if the user wants to create a Jira task.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def detect_jira_intent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect if user wants to create a Jira task.

    Uses keyword-based detection to identify task creation intents.

    Args:
        state: Current RAG state

    Returns:
        Updated state with create_jira_task flag
    """
    logger.info("Detect Jira Intent node executing")

    query = state.get("query", "").lower()

    # Keywords that indicate task creation intent
    task_creation_keywords = [
        "create a task",
        "create a ticket",
        "create an issue",
        "open a task",
        "open a ticket",
        "file a task",
        "file a ticket",
        "make a task",
        "make a ticket",
        "log a task",
        "log a ticket",
        "submit a task",
        "submit a ticket",
        "create jira",
        "open jira",
    ]

    # Check if query contains task creation keywords
    create_task = any(keyword in query for keyword in task_creation_keywords)

    state["create_jira_task"] = create_task

    if create_task:
        logger.info("Jira task creation intent detected")
    else:
        logger.info("No Jira task creation intent detected")

    return state
