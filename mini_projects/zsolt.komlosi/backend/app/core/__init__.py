"""
Core package - agent and workflow definitions.
"""

from .agent import SupportAIAgent
from .state import AgentState
from .prompts import (
    ANALYSIS_PROMPT,
    QUERY_EXPANSION_PROMPT,
    ANSWER_GENERATION_PROMPT,
    POLICY_CHECK_PROMPT,
    CUSTOMER_RESPONSE_PROMPT,
    ROLLING_SUMMARY_PROMPT,
    RERANKING_PROMPT,
)

__all__ = [
    "SupportAIAgent",
    "AgentState",
    "ANALYSIS_PROMPT",
    "QUERY_EXPANSION_PROMPT",
    "ANSWER_GENERATION_PROMPT",
    "POLICY_CHECK_PROMPT",
    "CUSTOMER_RESPONSE_PROMPT",
    "ROLLING_SUMMARY_PROMPT",
    "RERANKING_PROMPT",
]
