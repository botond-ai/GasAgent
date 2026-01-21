"""
Query expansion using LLM to generate multiple search queries.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.models import ExpandedQuery
from app.core.prompts import QUERY_EXPANSION_PROMPT


class ExpandedQueries(BaseModel):
    """Structured output for query expansion."""

    queries: List[str] = Field(
        description="List of 3 expanded search queries in English"
    )


class QueryExpander:
    """
    Query expansion using LLM to generate diverse search queries.
    Helps improve retrieval by covering different aspects of the question.
    """

    def __init__(self):
        settings = get_settings()
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,  # Higher temperature for diversity
        )
        self.structured_llm = self.llm.with_structured_output(ExpandedQueries)

    def expand(
        self,
        query: str,
        context: Optional[str] = None,
        num_queries: int = 3,
    ) -> ExpandedQuery:
        """
        Expand a query into multiple diverse search queries.

        Args:
            query: Original query (may be in Hungarian)
            context: Optional context from conversation
            num_queries: Number of queries to generate

        Returns:
            ExpandedQuery with original and expanded queries
        """
        prompt = QUERY_EXPANSION_PROMPT.format(
            query=query,
            context=context or "No additional context",
        )

        try:
            result: ExpandedQueries = self.structured_llm.invoke(prompt)
            expanded = result.queries[:num_queries]
        except Exception as e:
            # Fallback: just use the original query
            print(f"Query expansion failed: {e}")
            expanded = [query]

        # Also translate the original query to English
        translated = self._translate_to_english(query)

        return ExpandedQuery(
            original=query,
            expanded=expanded,
            language=self._detect_language(query),
            translated=translated,
        )

    def _translate_to_english(self, text: str) -> str:
        """
        Translate text to English if not already in English.
        Uses LLM for translation.
        """
        # Simple heuristic: if mostly ASCII, probably English
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text) if text else 1
        if ascii_ratio > 0.95:
            return text

        try:
            response = self.llm.invoke(
                f"Translate the following text to English. Only output the translation, nothing else.\n\n{text}"
            )
            return response.content.strip()
        except Exception:
            return text

    def _detect_language(self, text: str) -> str:
        """Simple language detection based on characters."""
        # Hungarian-specific characters
        hungarian_chars = "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"
        hungarian_count = sum(1 for c in text if c in hungarian_chars)

        if hungarian_count > 0:
            return "hu"
        return "en"


# Singleton instance
_query_expander: Optional[QueryExpander] = None


def get_query_expander() -> QueryExpander:
    """Get or create the query expander singleton."""
    global _query_expander
    if _query_expander is None:
        _query_expander = QueryExpander()
    return _query_expander
