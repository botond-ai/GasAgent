"""Response cache for LLM outputs.

Caches LLM-generated responses based on query and retrieved documents
to reduce redundant API calls and costs.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class ResponseCache:
    """Simple file-based cache for LLM responses."""

    def __init__(self, cache_dir: str = "./response_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _make_key(self, query: str, doc_texts: List[str]) -> str:
        """Generate cache key from query and document texts."""
        # Hash the concatenated query + sorted doc texts for deterministic key
        combined = query + "|" + "|".join(sorted(doc_texts))
        hash_digest = hashlib.sha256(combined.encode()).hexdigest()
        return hash_digest

    def get(self, query: str, doc_texts: List[str]) -> Optional[str]:
        """Retrieve cached response if available.

        Args:
            query: User query.
            doc_texts: List of retrieved document texts.

        Returns:
            Cached response or None if not found.
        """
        key = self._make_key(query, doc_texts)
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                return data.get("response")
        except Exception as exc:
            logger.warning("Failed to read cache: %s", exc)
            return None

    def set(self, query: str, doc_texts: List[str], response: str) -> None:
        """Cache a response.

        Args:
            query: User query.
            doc_texts: List of retrieved document texts.
            response: LLM-generated response to cache.
        """
        key = self._make_key(query, doc_texts)
        cache_file = self.cache_dir / f"{key}.json"

        try:
            data = {"query": query, "doc_count": len(doc_texts), "response": response}
            with open(cache_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception as exc:
            logger.warning("Failed to write cache: %s", exc)

    def clear(self) -> None:
        """Clear all cached responses."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cache cleared")
        except Exception as exc:
            logger.warning("Failed to clear cache: %s", exc)

    def stats(self) -> dict:
        """Return cache statistics."""
        try:
            files = list(self.cache_dir.glob("*.json"))
            return {"cache_entries": len(files), "cache_dir": str(self.cache_dir)}
        except Exception as exc:
            logger.warning("Failed to get cache stats: %s", exc)
            return {"error": str(exc)}
