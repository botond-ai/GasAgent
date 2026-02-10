"""RAG (Retrieval-Augmented Generation) agent.

Combines retrieved documents with an LLM to generate context-aware responses.
Supports optional response caching to reduce API costs.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

import openai

from .metrics import MetricCollector, MetricsMiddleware
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
        metrics_collector: Optional[MetricCollector] = None,
    ) -> None:
        openai.api_key = api_key
        self.llm_model = llm_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cache = ResponseCache(cache_dir) if use_cache else None
        self.metrics_middleware = (
            MetricsMiddleware(metrics_collector) if metrics_collector else None
        )

    def _build_context(self, retrieved_docs: List[Tuple[str, float, str]]) -> str:
        """Build a context string from retrieved documents."""
        if not retrieved_docs:
            return "(No relevant documents found.)"

        context_parts = []
        for i, (doc_id, score, text) in enumerate(retrieved_docs, start=1):
            context_parts.append(f"[Document {i} (relevance: {score:.4f})]\n{text}")

        return "\n\n".join(context_parts)

    def _count_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: 1 token ≈ 4 characters).

        Args:
            text: Text to count tokens for.

        Returns:
            Estimated token count.
        """
        return len(text) // 4

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
        start_time = time.time()

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

            # Record metrics if collector is available
            if self.metrics_middleware:
                latency_ms = (time.time() - start_time) * 1000
                tokens_in = self._count_tokens(system_prompt + user_prompt)
                tokens_out = self._count_tokens(answer)
                self.metrics_middleware.record_llm_call(
                    model=self.llm_model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    success=True,
                )

            # Cache the response
            if self.cache:
                self.cache.set(query, doc_texts, answer)
            return answer
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)

            # Record failed metric if collector is available
            if self.metrics_middleware:
                latency_ms = (time.time() - start_time) * 1000
                tokens_in = self._count_tokens(system_prompt + user_prompt)
                self.metrics_middleware.record_llm_call(
                    model=self.llm_model,
                    tokens_in=tokens_in,
                    tokens_out=0,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(exc),
                )

            return f"Error generating response: {exc}"
