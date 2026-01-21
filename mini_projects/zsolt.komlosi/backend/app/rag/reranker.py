"""
LLM-based reranker for improving retrieval quality.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.models import SearchResult, RerankedResult


class DocumentScore(BaseModel):
    """Score for a single document."""

    chunk_id: str = Field(description="The chunk ID")
    score: float = Field(ge=0.0, le=1.0, description="Relevance score 0-1")
    reasoning: str = Field(description="Brief explanation of the score")


class RerankingResult(BaseModel):
    """Structured output for reranking."""

    scores: List[DocumentScore] = Field(description="Scores for each document")


class LLMReranker:
    """
    LLM-based reranker for two-stage retrieval.
    Takes top-N results from retriever and reranks to top-K.
    """

    def __init__(self):
        settings = get_settings()
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.0,  # Deterministic for consistent ranking
        )
        self.top_k = settings.rag_rerank_top_k
        self.structured_llm = self.llm.with_structured_output(RerankingResult)

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: Optional[int] = None,
    ) -> List[RerankedResult]:
        """
        Rerank search results using LLM.

        Args:
            query: Original search query
            results: List of SearchResult to rerank
            top_k: Number of results to return (default from config)

        Returns:
            List of RerankedResult with new scores
        """
        if not results:
            return []

        top_k = top_k or self.top_k

        # Prepare documents for LLM
        docs_text = self._format_documents(results)

        prompt = f"""You are a relevance judge for customer support queries.

Customer's question:
{query}

Rate how relevant each document is to answering this question.
Score from 0.0 (not relevant) to 1.0 (highly relevant).
Consider:
- Direct relevance to the question
- Usefulness for answering
- Specificity of information

Documents to evaluate:
{docs_text}

Return scores for each document with brief reasoning."""

        try:
            result: RerankingResult = self.structured_llm.invoke(prompt)

            # Map scores back to results
            score_map = {s.chunk_id: s for s in result.scores}

            reranked = []
            for search_result in results:
                doc_score = score_map.get(search_result.chunk_id)
                if doc_score:
                    reranked.append(
                        RerankedResult(
                            chunk_id=search_result.chunk_id,
                            doc_id=search_result.doc_id,
                            content_hu=search_result.content_hu,
                            title=search_result.title,
                            original_score=search_result.score,
                            reranked_score=doc_score.score,
                            reasoning=doc_score.reasoning,
                        )
                    )
                else:
                    # If not scored, use original score
                    reranked.append(
                        RerankedResult(
                            chunk_id=search_result.chunk_id,
                            doc_id=search_result.doc_id,
                            content_hu=search_result.content_hu,
                            title=search_result.title,
                            original_score=search_result.score,
                            reranked_score=search_result.score,
                            reasoning="Not evaluated by reranker",
                        )
                    )

            # Sort by reranked score
            reranked.sort(key=lambda x: x.reranked_score, reverse=True)

            return reranked[:top_k]

        except Exception as e:
            print(f"Reranking failed: {e}")
            # Fallback: return original order
            return [
                RerankedResult(
                    chunk_id=r.chunk_id,
                    doc_id=r.doc_id,
                    content_hu=r.content_hu,
                    title=r.title,
                    original_score=r.score,
                    reranked_score=r.score,
                    reasoning="Reranking failed, using original score",
                )
                for r in results[:top_k]
            ]

    def _format_documents(self, results: List[SearchResult]) -> str:
        """Format documents for LLM prompt."""
        parts = []
        for i, result in enumerate(results, 1):
            # Truncate content for prompt
            content = result.content_hu[:500] + "..." if len(result.content_hu) > 500 else result.content_hu
            parts.append(
                f"[{result.chunk_id}] {result.title}\n{content}\n"
            )
        return "\n---\n".join(parts)


# Singleton instance
_reranker: Optional[LLMReranker] = None


def get_reranker() -> LLMReranker:
    """Get or create the reranker singleton."""
    global _reranker
    if _reranker is None:
        _reranker = LLMReranker()
    return _reranker
