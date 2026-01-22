from dataclasses import dataclass
from typing import List

from infrastructure.vector_store import VectorStore, SearchResult, Domain


@dataclass
class RAGResult:
    """Result of a RAG retrieval operation."""
    context: str
    citations: List[dict]


class RAGEngine:
    """
    RAG retrieval engine - handles querying and context building.

    Single Responsibility: Retrieving relevant documents and formatting
    them for LLM consumption.
    """

    def __init__(self, vector_store: VectorStore, relevance_threshold: float = 0.7):
        self.vector_store = vector_store
        self.relevance_threshold = relevance_threshold

    async def retrieve_for_query(self, query: str, domain: Domain, top_k: int = 5) -> RAGResult:
        """
        Retrieve relevant documents for a query.

        Args:
            query: The search query
            domain: Domain to search within
            top_k: Maximum number of results to retrieve

        Returns:
            RAGResult with formatted context and citations
        """
        results = await self.vector_store.search(query, domain, top_k=top_k)

        relevant = [r for r in results if r.score >= self.relevance_threshold]

        context = self._build_context(relevant)
        citations = self._format_citations(relevant)

        return RAGResult(context=context, citations=citations)

    def _build_context(self, results: List[SearchResult]) -> str:
        """Format documents into LLM-friendly context."""
        return "\n\n".join([
            f"[{r.doc_id}] {r.title}:\n{r.text}"
            for r in results
        ])

    def _format_citations(self, results: List[SearchResult]) -> List[dict]:
        """Format citations for response."""
        return [
            {"doc_id": r.doc_id, "title": r.title, "score": r.score}
            for r in results
        ]
