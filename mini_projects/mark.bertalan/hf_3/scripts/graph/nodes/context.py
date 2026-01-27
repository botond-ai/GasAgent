"""
Context Building Node.

Extracts and formats retrieved chunks for LLM consumption.
"""

import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)


def build_context_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build context from retrieved chunks for LLM.

    Extracts text content from cosine search results and formats
    as a list of strings.

    Args:
        state: Current RAG state

    Returns:
        Updated state with retrieved_context
    """
    logger.info("Build Context node executing")
    start_time = time.time()

    cosine_results = state.get("cosine_results", [])

    try:
        # Extract text from cosine search results
        # Results format: (id, distance, similarity, text, metadata)
        retrieved_chunks = [result[3] for result in cosine_results]

        # Store in state
        state["retrieved_context"] = retrieved_chunks

        # Track timing
        latency = (time.time() - start_time) * 1000
        state["step_timings"]["context_building_ms"] = latency

        logger.info(f"Built context with {len(retrieved_chunks)} chunks in {latency:.2f}ms")

    except Exception as e:
        logger.error(f"Context building error: {e}")
        state["errors"].append(f"Context building failed: {e}")
        state["retrieved_context"] = []

    return state
