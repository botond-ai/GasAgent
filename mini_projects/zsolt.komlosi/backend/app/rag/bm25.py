"""
BM25 sparse retrieval for hybrid search.
"""

from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
import re

from app.models import SearchResult


class BM25Index:
    """
    BM25 index for sparse keyword-based retrieval.
    Used in combination with vector search for hybrid retrieval.
    """

    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.tokenized_docs: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25.
        Simple word tokenization with lowercasing.
        """
        # Remove punctuation and split on whitespace
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = text.split()
        # Remove very short tokens
        tokens = [t for t in tokens if len(t) > 2]
        return tokens

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Add documents to the BM25 index.

        Args:
            documents: List of document dicts with at least 'content_en' field
        """
        self.documents.extend(documents)

        # Tokenize all documents
        for doc in documents:
            content = doc.get("content_en", "") + " " + doc.get("content_hu", "")
            tokens = self._tokenize(content)
            # Add keywords if available
            keywords = doc.get("keywords", [])
            tokens.extend([k.lower() for k in keywords])
            self.tokenized_docs.append(tokens)

        # Rebuild BM25 index
        if self.tokenized_docs:
            self.bm25 = BM25Okapi(self.tokenized_docs)

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[SearchResult]:
        """
        Search the BM25 index.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of SearchResult objects with BM25 scores
        """
        if not self.bm25 or not self.documents:
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        # Get BM25 scores
        scores = self.bm25.get_scores(query_tokens)

        # Get top-k indices
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]

        # Build results
        results = []
        max_score = max(scores) if scores.any() else 1.0

        for idx in top_indices:
            if scores[idx] > 0:
                doc = self.documents[idx]
                # Normalize score to 0-1 range
                normalized_score = scores[idx] / max_score if max_score > 0 else 0

                results.append(
                    SearchResult(
                        chunk_id=doc.get("chunk_id", ""),
                        doc_id=doc.get("doc_id", ""),
                        content_hu=doc.get("content_hu", ""),
                        content_en=doc.get("content_en", ""),
                        title=doc.get("title", ""),
                        doc_type=doc.get("doc_type", ""),
                        score=normalized_score,
                        url=doc.get("url"),
                        search_type="bm25",
                    )
                )

        return results

    def clear(self) -> None:
        """Clear the index."""
        self.documents = []
        self.tokenized_docs = []
        self.bm25 = None


# Singleton instance
_bm25_index: Optional[BM25Index] = None


def get_bm25_index() -> BM25Index:
    """Get or create the BM25 index singleton."""
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = BM25Index()
    return _bm25_index
