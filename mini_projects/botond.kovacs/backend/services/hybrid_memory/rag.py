"""
RAG retrieval logic for hybrid memory. Only triggers if recall intent is detected in user message.
"""
from typing import List, Dict, Any, Optional
import re

RECALL_TRIGGERS = [
    r"\bremember\b",
    r"\brecall\b",
    r"\bearlier\b",
    r"\bbefore\b",
    r"you said",
]

RECALL_PATTERN = re.compile("|".join(RECALL_TRIGGERS), re.IGNORECASE)


def should_trigger_rag(message: str) -> bool:
    return bool(RECALL_PATTERN.search(message))


def rag_retrieve(query: str, vector_store, threshold: float = 0.7) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve relevant context from vector store if semantic similarity exceeds threshold.
    vector_store: must have a .similarity_search(query, threshold) method.
    """
    results = vector_store.similarity_search(query, threshold=threshold)
    if not results or all(r.get('score', 0) < threshold for r in results):
        return None
    return [r for r in results if r.get('score', 0) >= threshold]
