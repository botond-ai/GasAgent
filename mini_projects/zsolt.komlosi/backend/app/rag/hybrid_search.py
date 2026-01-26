"""
Hybrid search combining vector search and BM25 with Reciprocal Rank Fusion.
"""

from typing import List, Dict, Optional
from collections import defaultdict

from app.config import get_settings
from app.models import SearchResult
from .vectorstore import get_vectorstore
from .bm25 import get_bm25_index


class HybridSearch:
    """
    Hybrid search combining vector (semantic) and BM25 (lexical) search.
    Uses Reciprocal Rank Fusion (RRF) to combine results.
    """

    def __init__(
        self,
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None,
        rrf_k: int = 60,
    ):
        settings = get_settings()
        self.vector_weight = vector_weight or settings.rag_vector_weight
        self.bm25_weight = bm25_weight or settings.rag_bm25_weight
        self.rrf_k = rrf_k  # RRF constant (typically 60)

        self.vectorstore = get_vectorstore()
        self.bm25_index = get_bm25_index()

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_dict: Optional[Dict] = None,
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining vector and BM25 results.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_dict: Optional filter conditions (for vector search)

        Returns:
            List of SearchResult objects with combined scores
        """
        # Get more results from each source for better fusion
        fetch_k = top_k * 2

        # Vector search
        vector_results = self.vectorstore.search(
            query=query,
            top_k=fetch_k,
            filter_dict=filter_dict,
        )

        # BM25 search
        bm25_results = self.bm25_index.search(
            query=query,
            top_k=fetch_k,
        )

        # Combine using RRF
        combined = self._reciprocal_rank_fusion(
            vector_results=vector_results,
            bm25_results=bm25_results,
        )

        # Return top_k
        return combined[:top_k]

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[SearchResult],
        bm25_results: List[SearchResult],
    ) -> List[SearchResult]:
        """
        Combine results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) for each result in both lists
        where k is a constant (default 60).

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search

        Returns:
            Combined and reranked results
        """
        rrf_scores: Dict[str, float] = defaultdict(float)
        result_map: Dict[str, SearchResult] = {}

        # Process vector results
        for rank, result in enumerate(vector_results, start=1):
            chunk_id = result.chunk_id
            rrf_scores[chunk_id] += self.vector_weight * (1.0 / (self.rrf_k + rank))
            result_map[chunk_id] = result

        # Process BM25 results
        for rank, result in enumerate(bm25_results, start=1):
            chunk_id = result.chunk_id
            rrf_scores[chunk_id] += self.bm25_weight * (1.0 / (self.rrf_k + rank))
            if chunk_id not in result_map:
                result_map[chunk_id] = result

        # Sort by RRF score
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda x: rrf_scores[x],
            reverse=True,
        )

        # Build final results
        combined_results = []
        for chunk_id in sorted_ids:
            result = result_map[chunk_id]
            # Create new result with combined score
            combined_results.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    doc_id=result.doc_id,
                    content_hu=result.content_hu,
                    content_en=result.content_en,
                    title=result.title,
                    doc_type=result.doc_type,
                    score=rrf_scores[chunk_id],  # RRF score
                    url=result.url,
                    search_type="hybrid",
                )
            )

        return combined_results

    def vector_only_search(
        self,
        query: str,
        top_k: int = 10,
        filter_dict: Optional[Dict] = None,
    ) -> List[SearchResult]:
        """Perform vector-only search."""
        return self.vectorstore.search(
            query=query,
            top_k=top_k,
            filter_dict=filter_dict,
        )

    def bm25_only_search(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[SearchResult]:
        """Perform BM25-only search."""
        return self.bm25_index.search(
            query=query,
            top_k=top_k,
        )


# Singleton instance
_hybrid_search: Optional[HybridSearch] = None


def get_hybrid_search() -> HybridSearch:
    """Get or create the hybrid search singleton."""
    global _hybrid_search
    if _hybrid_search is None:
        _hybrid_search = HybridSearch()
    return _hybrid_search
