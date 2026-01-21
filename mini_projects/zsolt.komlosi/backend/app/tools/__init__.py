"""
Tools package - exports all LangChain tools.
"""

from .location import get_location_info
from .holidays import get_holidays
from .sla import calculate_sla_deadline
from .jira_tools import (
    jira_get_issue,
    jira_search_issues,
    jira_add_comment,
    jira_update_priority,
    jira_add_labels,
    jira_transition_issue,
    JIRA_TOOLS,
)

# Tool list for the agent (core tools)
TOOLS = [get_location_info, get_holidays, calculate_sla_deadline]

# All tools including Jira
ALL_TOOLS = TOOLS + JIRA_TOOLS

__all__ = [
    "get_location_info",
    "get_holidays",
    "calculate_sla_deadline",
    "jira_get_issue",
    "jira_search_issues",
    "jira_add_comment",
    "jira_update_priority",
    "jira_add_labels",
    "jira_transition_issue",
    "TOOLS",
    "JIRA_TOOLS",
    "ALL_TOOLS",
]
