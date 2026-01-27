"""
Generation Node.

Generates answer using LLM with retrieved context and conversation history.
"""

import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global service (set by graph during initialization)
_llm = None


def set_llm(llm):
    """Set the LLM service for this node."""
    global _llm
    _llm = llm


def generate_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate answer using LLM with retrieved context and conversation history.

    Args:
        state: Current RAG state

    Returns:
        Updated state with generated_answer and updated conversation_history
    """
    logger.info("===== Generate Answer node executing =====")
    start_time = time.time()

    query = state.get("query", "")
    retrieved_context = state.get("retrieved_context", [])
    max_tokens = state.get("max_tokens", 500)
    conversation_history = state.get("conversation_history", [])

    logger.info(f"Query: {query[:100]}...")
    logger.info(f"Conversation history length: {len(conversation_history)}")

    if not query:
        state["errors"].append("No query provided for generation")
        return state

    try:
        # Generate answer using LLM with conversation history
        generated_answer = _llm.generate(
            prompt=query,
            context=retrieved_context,
            max_tokens=max_tokens,
            conversation_history=conversation_history
        )

        # Store generated answer
        state["generated_answer"] = generated_answer

        # Update conversation history
        # Add current query and assistant response
        updated_history = conversation_history.copy()
        updated_history.append({"role": "user", "content": query})
        updated_history.append({"role": "assistant", "content": generated_answer})
        state["conversation_history"] = updated_history

        # Track timing
        latency = (time.time() - start_time) * 1000
        state["step_timings"]["generation_ms"] = latency

        logger.info(f"Answer generated in {latency:.2f}ms")
        logger.info(f"Updated conversation history: {len(updated_history)} messages")

    except Exception as e:
        logger.error(f"Generation error: {e}")
        state["errors"].append(f"Generation failed: {e}")
        state["generated_answer"] = "Error: Could not generate answer"

    return state
