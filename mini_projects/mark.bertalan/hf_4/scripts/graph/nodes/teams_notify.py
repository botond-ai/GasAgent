"""
Teams Notification Node.

Sends notifications to Microsoft Teams when Jira tickets are created.
Uses JSON for structured communication.
"""

import logging
import time
import json
from typing import Dict, Any
import requests

logger = logging.getLogger(__name__)

# Global configuration (set by graph during initialization)
_teams_config = None


def set_teams_config(config):
    """Set the Teams configuration for this node."""
    global _teams_config
    _teams_config = config


def send_teams_notification_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a Teams notification about the created Jira ticket.

    This node sends an adaptive card to the appropriate Teams channel
    based on the department of the Jira ticket.

    Args:
        state: Current RAG state with jira_task_key and jira_task_url

    Returns:
        Updated state with teams notification status in JSON format
    """
    logger.info("===== Teams Notification node executing =====")
    start_time = time.time()

    # Initialize notification result
    notification_result = {
        "sent": False,
        "channel": None,
        "error": None,
        "webhook_url_preview": None,
        "response_status": None
    }

    try:
        # Check if Teams is enabled
        if not _teams_config or not _teams_config.teams_enabled:
            logger.info("Teams integration not enabled (missing configuration)")
            notification_result["error"] = "Teams integration not configured"
            state["teams_notification"] = notification_result
            return state

        # Get Jira ticket details
        jira_task_key = state.get("jira_task_key")
        jira_task_url = state.get("jira_task_url")
        jira_department = state.get("jira_department", "support")
        jira_summary = state.get("jira_summary", "Task from RAG system")
        jira_priority = state.get("jira_priority", "Medium")
        jira_description = state.get("jira_description", "")
        query = state.get("query", "")

        if not jira_task_key or not jira_task_url:
            logger.warning("No Jira ticket to notify about")
            notification_result["error"] = "No Jira ticket found in state"
            state["teams_notification"] = notification_result
            return state

        # Get webhook URL for department
        webhook_url = _teams_config.teams_webhooks.get(jira_department.lower())

        if not webhook_url:
            logger.warning(f"No Teams webhook configured for department: {jira_department}")
            notification_result["error"] = f"No webhook for department {jira_department}"
            notification_result["channel"] = jira_department
            state["teams_notification"] = notification_result
            return state

        notification_result["webhook_url_preview"] = webhook_url[:50] + "..."
        notification_result["channel"] = jira_department

        # Determine theme color based on priority
        priority_colors = {
            "High": "FF0000",      # Red
            "Medium": "FFA500",    # Orange
            "Low": "00FF00"        # Green
        }
        theme_color = priority_colors.get(jira_priority, "0076D7")

        # Create adaptive card for Teams (MessageCard format - more widely supported)
        adaptive_card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": theme_color,
            "summary": f"New Jira Ticket: {jira_task_key}",
            "sections": [
                {
                    "activityTitle": f"🎫 New Jira Ticket Created",
                    "activitySubtitle": f"{jira_task_key} | {jira_department.upper()} | {jira_priority} Priority",
                    "activityImage": "https://cdn-icons-png.flaticon.com/512/5968/5968875.png",
                    "facts": [
                        {
                            "name": "Ticket:",
                            "value": jira_task_key
                        },
                        {
                            "name": "Summary:",
                            "value": jira_summary
                        },
                        {
                            "name": "Priority:",
                            "value": jira_priority
                        },
                        {
                            "name": "Department:",
                            "value": jira_department.upper()
                        },
                        {
                            "name": "Original Query:",
                            "value": query[:200] + ("..." if len(query) > 200 else "")
                        }
                    ],
                    "markdown": True
                }
            ],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View in Jira",
                    "targets": [
                        {
                            "os": "default",
                            "uri": jira_task_url
                        }
                    ]
                }
            ]
        }

        # Log the payload
        logger.info(f"Sending Teams notification to {jira_department} channel")
        logger.debug(f"Webhook URL: {notification_result['webhook_url_preview']}")
        logger.debug(f"Adaptive card payload: {json.dumps(adaptive_card, indent=2)}")

        # Send to Teams
        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            json=adaptive_card,
            timeout=10
        )

        notification_result["response_status"] = response.status_code

        # Check response
        response.raise_for_status()

        # Success
        notification_result["sent"] = True
        notification_result["error"] = None

        logger.info(f"✓ Teams notification sent successfully")
        logger.info(f"  Channel: {jira_department}")
        logger.info(f"  Status: {response.status_code}")
        logger.info(f"  Ticket: {jira_task_key}")

    except requests.exceptions.Timeout as e:
        error_msg = f"Teams API timeout: {e}"
        logger.error(error_msg)
        notification_result["error"] = error_msg
        state["errors"].append(error_msg)

    except requests.exceptions.HTTPError as e:
        error_msg = f"Teams API HTTP error: {e.response.status_code}"
        if e.response is not None:
            try:
                error_details = e.response.json()
                error_msg += f" - {json.dumps(error_details)}"
            except:
                error_msg += f" - {e.response.text[:200]}"
        logger.error(error_msg)
        notification_result["error"] = error_msg
        notification_result["response_status"] = e.response.status_code if e.response else None
        state["errors"].append(error_msg)

    except requests.exceptions.RequestException as e:
        error_msg = f"Teams API request error: {e}"
        logger.error(error_msg, exc_info=True)
        notification_result["error"] = error_msg
        state["errors"].append(error_msg)

    except Exception as e:
        error_msg = f"Teams notification error: {e}"
        logger.error(error_msg, exc_info=True)
        notification_result["error"] = error_msg
        state["errors"].append(error_msg)

    # Store notification result in state
    state["teams_notification"] = notification_result

    # Track timing
    latency = (time.time() - start_time) * 1000
    state["step_timings"]["teams_notification_ms"] = latency

    logger.info(f"===== Teams notification completed in {latency:.2f}ms =====")
    logger.info(f"Result: {json.dumps(notification_result, indent=2)}")

    return state
