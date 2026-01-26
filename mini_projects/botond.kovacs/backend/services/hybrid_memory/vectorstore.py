"""
DummyVectorStore for hybrid memory demo.
Replace with a real vector store (e.g., FAISS, Chroma) in production.
"""
from typing import List, Dict, Any

class DummyVectorStore:
    def similarity_search(self, query: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        # Always return empty for demo
        return []
