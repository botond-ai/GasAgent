"""
Preprocess Query Node.

Initializes state and validates query input.
"""

import logging
import uuid
from typing import Dict, Any

logger = logging.getLogger(__name__)


def preprocess_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Preprocess and validate the incoming query.

    - Generate unique query ID
    - Initialize state fields (step_timings, errors)
    - Validate query text
    - Set defaults for k and max_tokens

    Args:
        state: Current RAG state

    Returns:
        Updated state with initialized fields
    """
    logger.info("Preprocess Query node executing")

    # Generate unique ID for this query
    if "query_id" not in state:
        state["query_id"] = str(uuid.uuid4())

    # Initialize tracking fields
    if "step_timings" not in state:
        state["step_timings"] = {}

    if "errors" not in state:
        state["errors"] = []

    # Initialize conversation history if not present
    if "conversation_history" not in state:
        state["conversation_history"] = []

    # Validate query
    query = state.get("query", "")
    if not query or not query.strip():
        state["errors"].append("Empty query provided")
        logger.warning("Empty query provided")

    # Set defaults
    if "k" not in state:
        state["k"] = 3

    if "max_tokens" not in state:
        state["max_tokens"] = 500

    if "skip_llm" not in state:
        state["skip_llm"] = False

    logger.info(f"Query preprocessed: ID={state['query_id']}, k={state['k']}")

    return state
