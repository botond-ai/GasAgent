"""
Jira Confirmation Detection Node.

Detects if the user is confirming or rejecting a pending Jira ticket suggestion.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def detect_jira_confirmation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect if user is responding yes/no to a pending Jira suggestion.

    Args:
        state: Current RAG state

    Returns:
        Updated state with jira_confirmation_detected and create_jira_task flags
    """
    logger.info("Detect Jira Confirmation node executing")

    query = state.get("query", "").lower().strip()
    pending_suggestion = state.get("pending_jira_suggestion")

    # Default: no confirmation detected
    state["jira_confirmation_detected"] = False
    state["create_jira_task"] = False

    # Check if there's a pending suggestion
    if not pending_suggestion:
        logger.info("No pending Jira suggestion")
        return state

    # Check if query is a yes/no response
    affirmative_responses = ["yes", "y", "yeah", "yep", "sure", "ok", "okay", "create it", "do it", "please"]
    negative_responses = ["no", "n", "nope", "nah", "don't", "skip", "cancel"]

    if query in affirmative_responses or any(word in query for word in ["yes", "create it", "do it"]):
        # User confirmed - create ticket
        logger.info("User confirmed Jira ticket creation")
        state["jira_confirmation_detected"] = True
        state["create_jira_task"] = True

        # Copy pending suggestion details to state for creation
        state["jira_department"] = pending_suggestion.get("department", "support")
        state["jira_summary"] = pending_suggestion.get("summary", "")
        state["jira_description"] = pending_suggestion.get("description", "")
        state["jira_priority"] = pending_suggestion.get("priority", "Medium")

    elif query in negative_responses or any(word in query for word in ["no", "don't", "skip"]):
        # User declined
        logger.info("User declined Jira ticket creation")
        state["jira_confirmation_detected"] = True
        state["create_jira_task"] = False
        state["generated_answer"] = "Okay, I won't create a Jira ticket. How else can I help you?"

    else:
        # Not a yes/no response - treat as new query
        logger.info("Query is not a yes/no response, treating as new query")
        state["jira_confirmation_detected"] = False

    return state
