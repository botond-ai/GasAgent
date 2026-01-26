"""Embedding service abstraction and OpenAI implementation.

Follows a small EmbeddingService interface (ABC) so implementations
can be swapped without changing application logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
import logging
import time

import openai

from .metrics import MetricsMiddleware, MetricCollector

logger = logging.getLogger(__name__)


class EmbeddingService(ABC):
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Return embedding vector for given text."""


class OpenAIEmbeddingService(EmbeddingService):
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        metrics_collector: Optional[MetricCollector] = None,
    ) -> None:
        openai.api_key = api_key
        self.model = model
        self.metrics_middleware = (
            MetricsMiddleware(metrics_collector) if metrics_collector else None
        )

    def get_embedding(self, text: str) -> List[float]:
        start_time = time.time()
        try:
            # Count tokens (rough estimate: 1 token ≈ 4 characters)
            tokens_in = len(text) // 4
            
            resp = openai.Embedding.create(model=self.model, input=text)
            embedding = resp["data"][0]["embedding"]
            
            # Record metrics if collector is available
            if self.metrics_middleware:
                latency_ms = (time.time() - start_time) * 1000
                self.metrics_middleware.record_embedding_call(
                    model=self.model,
                    tokens_in=tokens_in,
                    latency_ms=latency_ms,
                    success=True,
                )
            
            return embedding
        except Exception as exc:  # keep broad to avoid breaking the CLI
            logger.error("Embedding generation failed: %s", exc)
            
            # Record failed metric if collector is available
            if self.metrics_middleware:
                latency_ms = (time.time() - start_time) * 1000
                tokens_in = len(text) // 4
                self.metrics_middleware.record_embedding_call(
                    model=self.model,
                    tokens_in=tokens_in,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(exc),
                )
            
            return []
