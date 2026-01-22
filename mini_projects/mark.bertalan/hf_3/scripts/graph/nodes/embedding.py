"""
Embedding Node.

Generates embeddings for the query text.
"""

import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global service (set by graph during initialization)
_embedder = None


def set_embedder(embedder):
    """Set the embedder service for this node."""
    global _embedder
    _embedder = embedder


def embed_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate embedding for the query text.

    Args:
        state: Current RAG state

    Returns:
        Updated state with query_embedding and query_chunks
    """
    logger.info("Embed Query node executing")
    start_time = time.time()

    query = state.get("query", "")
    if not query:
        state["errors"].append("No query provided for embedding")
        return state

    try:
        # Generate embeddings using the embedder service
        # Returns list of (chunk_text, embedding_vector) tuples
        chunk_embeddings = _embedder.get_embedding(query)

        # Store results in state
        state["query_chunks"] = chunk_embeddings
        state["query_embedding"] = chunk_embeddings[0][1]  # First chunk's embedding vector

        # Track timing
        latency = (time.time() - start_time) * 1000
        state["step_timings"]["embedding_ms"] = latency

        logger.info(f"Query embedded in {latency:.2f}ms")

    except Exception as e:
        logger.error(f"Embedding error: {e}")
        state["errors"].append(f"Embedding failed: {e}")

    return state
