"""
Prompt templates for LLM-based workflow nodes.
Centralized, versioned prompt management.
"""
from .templates import (
    INTENT_DETECTION_PROMPT,
    TRIAGE_CLASSIFICATION_PROMPT,
    DRAFT_ANSWER_PROMPT,
    FALLBACK_ANSWER_PROMPT,
    POLICY_CHECK_PROMPT,
    PROMPT_VERSION,
)

__all__ = [
    "INTENT_DETECTION_PROMPT",
    "TRIAGE_CLASSIFICATION_PROMPT",
    "DRAFT_ANSWER_PROMPT",
    "FALLBACK_ANSWER_PROMPT",
    "POLICY_CHECK_PROMPT",
    "PROMPT_VERSION",
]
