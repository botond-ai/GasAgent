"""
Retrieval Node.

Executes dual search (cosine similarity + KNN) against vector store.
"""

import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global service (set by graph during initialization)
_vector_store = None


def set_vector_store(vector_store):
    """Set the vector store service for this node."""
    global _vector_store
    _vector_store = vector_store


def retrieve_chunks_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve relevant document chunks using dual search.

    Executes both:
    - Cosine similarity search
    - KNN (Euclidean distance) search

    Args:
        state: Current RAG state

    Returns:
        Updated state with cosine_results and knn_results
    """
    logger.info("Retrieve Chunks node executing")
    start_time = time.time()

    query_embedding = state.get("query_embedding")
    k = state.get("k", 3)

    if query_embedding is None:
        state["errors"].append("No query embedding available for retrieval")
        return state

    try:
        # Execute dual search
        cosine_matches = _vector_store.similarity_search(query_embedding, k=k)
        knn_matches = _vector_store.knn_search(query_embedding, k=k)

        # Store results in state
        state["cosine_results"] = cosine_matches
        state["knn_results"] = knn_matches

        # Track timing
        latency = (time.time() - start_time) * 1000
        state["step_timings"]["retrieval_ms"] = latency

        logger.info(f"Retrieved {len(cosine_matches)} cosine results and {len(knn_matches)} KNN results in {latency:.2f}ms")

    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        state["errors"].append(f"Retrieval failed: {e}")

    return state
