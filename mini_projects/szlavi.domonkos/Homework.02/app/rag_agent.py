"""RAG (Retrieval-Augmented Generation) agent.

Combines retrieved documents with an LLM to generate context-aware responses.
Supports optional response caching to reduce API costs.
"""
from __future__ import annotations

from typing import List, Tuple, Optional
import logging

import openai

from .response_cache import ResponseCache

logger = logging.getLogger(__name__)


class RAGAgent:
    """RAG agent that retrieves documents and generates LLM responses."""

    def __init__(
        self,
        api_key: str,
        llm_model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        use_cache: bool = True,
        cache_dir: str = "./response_cache",
    ) -> None:
        openai.api_key = api_key
        self.llm_model = llm_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cache = ResponseCache(cache_dir) if use_cache else None

    def _build_context(self, retrieved_docs: List[Tuple[str, float, str]]) -> str:
        """Build a context string from retrieved documents."""
        if not retrieved_docs:
            return "(No relevant documents found.)"

        context_parts = []
        for i, (doc_id, score, text) in enumerate(retrieved_docs, start=1):
            context_parts.append(f"[Document {i} (relevance: {score:.4f})]\n{text}")

        return "\n\n".join(context_parts)

    def generate_response(
        self, query: str, retrieved_docs: List[Tuple[str, float, str]]
    ) -> str:
        """Generate an LLM response based on query and retrieved documents.

        Args:
            query: User query/prompt.
            retrieved_docs: List of (id, score, text) tuples from retrieval.

        Returns:
            Generated response text.
        """
        # Extract doc texts for cache key
        doc_texts = [text for _, _, text in retrieved_docs]

        # Check cache first
        if self.cache:
            cached = self.cache.get(query, doc_texts)
            if cached:
                logger.info("Using cached response for query")
                return f"(cached) {cached}"

        context = self._build_context(retrieved_docs)

        system_prompt = (
            "You are a helpful assistant that answers questions based on provided context. "
            "Be concise and accurate. If the context doesn't contain relevant information, say so."
        )

        user_prompt = f"""Context from company documents:

{context}

User question: {query}

Please answer the question based on the context provided above."""

        try:
            response = openai.ChatCompletion.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            answer = response["choices"][0]["message"]["content"].strip()
            # Cache the response
            if self.cache:
                self.cache.set(query, doc_texts, answer)
            return answer
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            return f"(Error generating response: {exc})"
