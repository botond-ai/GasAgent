"""
Jira Evaluation Node.

Evaluates if creating a Jira ticket would be helpful based on the user's query and generated answer.
"""

import logging
import time
from typing import Dict, Any
import json

logger = logging.getLogger(__name__)

# Global service (set by graph during initialization)
_llm = None


def set_llm(llm):
    """Set the LLM service for this node."""
    global _llm
    _llm = llm


def evaluate_jira_need_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate if a Jira ticket should be offered to the user.

    Uses LLM to determine if the user's query represents:
    - A problem/bug that needs tracking
    - A feature request
    - An improvement suggestion
    - An issue requiring follow-up

    Args:
        state: Current RAG state

    Returns:
        Updated state with jira_suggested flag and suggested details
    """
    logger.info("===== Evaluate Jira Need node executing =====")
    start_time = time.time()

    query = state.get("query", "")
    generated_answer = state.get("generated_answer", "")

    logger.info(f"Query: {query[:100]}...")
    logger.info(f"Answer: {generated_answer[:100]}...")

    if not _llm:
        logger.error("LLM not configured for evaluation - cannot suggest Jira tickets")
        state["jira_suggested"] = False
        return state

    if not query or not generated_answer:
        logger.warning("Missing query or answer, skipping evaluation")
        state["jira_suggested"] = False
        return state

    try:
        # Build evaluation prompt
        evaluation_prompt = f"""You are helping determine if a Jira ticket should be created for a user's query.

User Query: "{query}"
Generated Answer: "{generated_answer}"

Analyze if this situation warrants creating a Jira ticket. A ticket should be suggested if:
- User reports a problem, bug, or issue
- User requests a new feature or enhancement
- User suggests an improvement
- User describes something that needs investigation or follow-up
- The answer indicates something should be fixed or implemented

A ticket should NOT be suggested for:
- Simple informational questions (e.g., "What is the vacation policy?")
- Questions with complete answers that require no action
- General knowledge queries

Respond in JSON format:
{{
  "suggest_ticket": true/false,
  "reason": "Brief explanation why ticket is/isn't suggested",
  "department": "hr|dev|support|management (if suggest_ticket is true)",
  "suggested_summary": "Suggested ticket title (if suggest_ticket is true)",
  "priority": "High|Medium|Low (if suggest_ticket is true)"
}}

If you don't suggest a ticket, only populate suggest_ticket and reason fields.
"""

        # Use LLM to evaluate
        response = _llm.generate(
            prompt=evaluation_prompt,
            context=[],
            max_tokens=300
        )

        # Parse JSON response
        response_clean = response.strip()
        if "```json" in response_clean:
            response_clean = response_clean.split("```json")[1].split("```")[0].strip()
        elif "```" in response_clean:
            response_clean = response_clean.split("```")[1].split("```")[0].strip()

        evaluation = json.loads(response_clean)

        # Store evaluation results
        suggest_ticket = evaluation.get("suggest_ticket", False)
        state["jira_suggested"] = suggest_ticket

        if suggest_ticket:
            state["jira_suggestion_reason"] = evaluation.get("reason", "Issue requires follow-up")
            state["jira_department"] = evaluation.get("department", "support").lower()
            state["jira_summary"] = evaluation.get("suggested_summary", query[:100])
            state["jira_priority"] = evaluation.get("priority", "Medium")
            state["jira_description"] = f"User Query: {query}\n\nContext: {generated_answer}"

            logger.info("="*60)
            logger.info("✅ JIRA TICKET SUGGESTED!")
            logger.info(f"Department: {state['jira_department']}")
            logger.info(f"Priority: {state['jira_priority']}")
            logger.info(f"Summary: {state['jira_summary'][:80]}")
            logger.info(f"Reason: {state['jira_suggestion_reason']}")
            logger.info("="*60)
        else:
            state["jira_suggestion_reason"] = evaluation.get("reason", "No action required")
            logger.info("="*60)
            logger.info("❌ NO JIRA TICKET SUGGESTED")
            logger.info(f"Reason: {state['jira_suggestion_reason']}")
            logger.info("="*60)

        # Track timing
        latency = (time.time() - start_time) * 1000
        state["step_timings"]["jira_evaluation_ms"] = latency

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM evaluation as JSON: {e}")
        logger.error(f"LLM response: {response}")
        state["jira_suggested"] = False
        state["errors"].append(f"Jira evaluation failed: {e}")

    except Exception as e:
        logger.error(f"Jira evaluation error: {e}")
        state["jira_suggested"] = False
        state["errors"].append(f"Jira evaluation failed: {e}")

    return state
