"""
Response Formatting Node.

Final validation and metrics logging.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def format_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Finalize response and log metrics.

    Performs final validation, appends Jira suggestion to answer if applicable,
    and logs completion metrics.

    Args:
        state: Current RAG state

    Returns:
        Final state with all fields populated
    """
    logger.info("Format Response node executing")

    # Check if this is a Jira confirmation path or planner skipped RAG
    is_jira_confirmation_path = state.get("jira_confirmation_detected", False)
    skip_retrieval = state.get("skip_retrieval", False)
    plan_needs_rag = state.get("plan_needs_rag", True)

    # Validate required fields only for full RAG path
    if not is_jira_confirmation_path and plan_needs_rag and not skip_retrieval:
        required_fields = ["query_id", "query", "cosine_results", "knn_results"]
        missing_fields = [field for field in required_fields if field not in state]

        if missing_fields:
            error_msg = f"Missing required fields: {missing_fields}"
            logger.error(error_msg)
            state["errors"].append(error_msg)
    else:
        if is_jira_confirmation_path:
            logger.info("Jira confirmation path - skipping RAG field validation")
        elif not plan_needs_rag:
            logger.info("Planner skipped RAG - no retrieval validation needed")
        elif skip_retrieval:
            logger.info("Planner skipped retrieval - partial RAG validation")

    # If planner skipped RAG entirely and no answer generated, create a simple response
    if not plan_needs_rag and "generated_answer" not in state:
        query = state.get("query", "")
        logger.info("Planner skipped RAG - generating simple response")
        state["generated_answer"] = (
            f"I understand you're asking: '{query}'\n\n"
            f"Based on the query analysis, this appears to be a simple query that doesn't require "
            f"document retrieval. However, I don't have enough context to provide a detailed answer "
            f"without accessing the knowledge base.\n\n"
            f"Could you rephrase your question or provide more details?"
        )

    # Append Jira suggestion to generated answer if suggested
    jira_suggested = state.get("jira_suggested", False)
    logger.info(f"===== Format Response: jira_suggested={jira_suggested} =====")

    if jira_suggested:
        generated_answer = state.get("generated_answer", "")
        department = state.get("jira_department", "support").upper()
        priority = state.get("jira_priority", "Medium")
        summary = state.get("jira_summary", "")

        logger.info(f"Appending Jira offer: dept={department}, priority={priority}")

        jira_offer = f"\n\n---\n\n📋 **Jira Ticket Suggestion**\n\n"
        jira_offer += f"I can create a Jira ticket for this issue:\n"
        jira_offer += f"- Department: {department}\n"
        jira_offer += f"- Priority: {priority}\n"
        jira_offer += f"- Summary: {summary[:80]}...\n\n"
        jira_offer += f"Would you like me to create this ticket? (Reply 'yes' or 'no')"

        state["generated_answer"] = generated_answer + jira_offer
        logger.info("Successfully appended Jira suggestion to answer")

    # Log timing metrics
    step_timings = state.get("step_timings", {})
    if step_timings:
        total_time = sum(step_timings.values())
        logger.info(f"Query processing complete. Total time: {total_time:.2f}ms")
        for step, duration in step_timings.items():
            logger.info(f"  {step}: {duration:.2f}ms")

    # Log any errors
    errors = state.get("errors", [])
    if errors:
        logger.warning(f"Completed with {len(errors)} error(s): {errors}")
    else:
        logger.info("Query processing completed successfully")

    return state
