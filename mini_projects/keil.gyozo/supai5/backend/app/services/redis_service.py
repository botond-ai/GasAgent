"""
Redis caching service for embeddings and results.
"""
import json
import hashlib
from typing import Optional, Any
from redis import Redis
from datetime import timedelta

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisService:
    """Service for managing Redis cache operations."""

    def __init__(self):
        """Initialize Redis client."""
        self.client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True
        )
        self.ttl = timedelta(hours=settings.cache_ttl_hours)
        logger.info("Initialized RedisService")

    def _generate_key(self, prefix: str, data: str) -> str:
        """
        Generate cache key with hash.

        Args:
            prefix: Key prefix (e.g., 'embedding', 'rag', 'triage')
            data: Data to hash

        Returns:
            Cache key string
        """
        hash_value = hashlib.sha256(data.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_value}"

    def get_embedding(self, text: str) -> Optional[list[float]]:
        """
        Retrieve cached embedding.

        Args:
            text: Text to look up

        Returns:
            Embedding vector or None
        """
        key = self._generate_key("embedding", text)
        cached = self.client.get(key)

        if cached:
            logger.debug(f"Cache hit for embedding: {key}")
            return json.loads(cached)

        logger.debug(f"Cache miss for embedding: {key}")
        return None

    def set_embedding(self, text: str, embedding: list[float]) -> None:
        """
        Cache embedding vector.

        Args:
            text: Text key
            embedding: Embedding vector
        """
        key = self._generate_key("embedding", text)
        self.client.setex(
            key,
            self.ttl,
            json.dumps(embedding)
        )
        logger.debug(f"Cached embedding: {key}")

    def get_rag_result(self, ticket_id: str) -> Optional[dict]:
        """
        Retrieve cached RAG result.

        Args:
            ticket_id: Ticket identifier

        Returns:
            RAG result or None
        """
        key = f"rag:{ticket_id}"
        cached = self.client.get(key)

        if cached:
            logger.debug(f"Cache hit for RAG result: {key}")
            return json.loads(cached)

        return None

    def set_rag_result(self, ticket_id: str, result: dict) -> None:
        """
        Cache RAG result.

        Args:
            ticket_id: Ticket identifier
            result: RAG result dict
        """
        key = f"rag:{ticket_id}"
        self.client.setex(
            key,
            timedelta(hours=1),  # Shorter TTL for results
            json.dumps(result)
        )
        logger.debug(f"Cached RAG result: {key}")

    def get_triage_result(self, ticket_id: str) -> Optional[dict]:
        """
        Retrieve cached triage result.

        Args:
            ticket_id: Ticket identifier

        Returns:
            Triage result or None
        """
        key = f"triage:{ticket_id}"
        cached = self.client.get(key)

        if cached:
            logger.debug(f"Cache hit for triage: {key}")
            return json.loads(cached)

        return None

    def set_triage_result(self, ticket_id: str, result: dict) -> None:
        """
        Cache triage result.

        Args:
            ticket_id: Ticket identifier
            result: Triage result dict
        """
        key = f"triage:{ticket_id}"
        self.client.setex(
            key,
            timedelta(hours=1),
            json.dumps(result)
        )
        logger.debug(f"Cached triage result: {key}")

    def clear_pattern(self, pattern: str) -> int:
        """
        Delete keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., 'embedding:*')

        Returns:
            Number of keys deleted
        """
        keys = list(self.client.scan_iter(match=pattern))
        if keys:
            count = self.client.delete(*keys)
            logger.info(f"Deleted {count} keys matching pattern: {pattern}")
            return count
        return 0

    def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
