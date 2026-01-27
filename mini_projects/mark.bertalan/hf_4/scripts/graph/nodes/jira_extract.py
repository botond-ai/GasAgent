"""
Jira Task Details Extraction Node.

Uses LLM to extract task details from user query.
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


def extract_jira_details_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract Jira task details from user query using LLM.

    Extracts:
    - Department (hr, dev, support, management)
    - Task summary (title)
    - Task description
    - Priority (High, Medium, Low)

    Args:
        state: Current RAG state

    Returns:
        Updated state with jira_department, jira_summary, jira_description, jira_priority
    """
    logger.info("Extract Jira Details node executing")
    start_time = time.time()

    query = state.get("query", "")

    if not query:
        state["errors"].append("No query provided for Jira extraction")
        return state

    try:
        # Build prompt for extraction
        extraction_prompt = f"""Extract the following details from the user's request to create a Jira task:

User Request: "{query}"

Extract:
1. Department: Which department is this for? (hr, dev, support, or management)
2. Summary: A brief title for the task (max 100 characters)
3. Description: A detailed description of what needs to be done
4. Priority: Task priority (High, Medium, or Low)

Respond in JSON format:
{{
  "department": "hr|dev|support|management",
  "summary": "Task title",
  "description": "Detailed description",
  "priority": "High|Medium|Low"
}}

If you cannot determine a field, use these defaults:
- Department: "support"
- Priority: "Medium"
"""

        # Use LLM to extract details
        response = _llm.generate(
            prompt=extraction_prompt,
            context=[],  # No context needed for extraction
            max_tokens=300
        )

        # Parse JSON response
        # Try to find JSON in the response
        response_clean = response.strip()
        if "```json" in response_clean:
            response_clean = response_clean.split("```json")[1].split("```")[0].strip()
        elif "```" in response_clean:
            response_clean = response_clean.split("```")[1].split("```")[0].strip()

        details = json.loads(response_clean)

        # Store extracted details in state
        state["jira_department"] = details.get("department", "support").lower()
        state["jira_summary"] = details.get("summary", "Task from RAG system")
        state["jira_description"] = details.get("description", query)
        state["jira_priority"] = details.get("priority", "Medium")

        # Track timing
        latency = (time.time() - start_time) * 1000
        state["step_timings"]["jira_extraction_ms"] = latency

        logger.info(f"Extracted Jira details in {latency:.2f}ms: dept={state['jira_department']}, priority={state['jira_priority']}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"LLM response: {response}")
        # Fallback: use query as description
        state["jira_department"] = "support"
        state["jira_summary"] = query[:100] if len(query) > 100 else query
        state["jira_description"] = query
        state["jira_priority"] = "Medium"
        state["errors"].append(f"Jira extraction failed, using defaults: {e}")

    except Exception as e:
        logger.error(f"Jira extraction error: {e}")
        state["errors"].append(f"Jira extraction failed: {e}")
        # Set defaults
        state["jira_department"] = "support"
        state["jira_summary"] = query[:100] if len(query) > 100 else query
        state["jira_description"] = query
        state["jira_priority"] = "Medium"

    return state
