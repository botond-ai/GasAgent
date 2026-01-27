"""
Cache service abstractions following SOLID principles.

Provides interface-based caching that can be implemented with
different backends (Redis, in-memory, Memcached, etc.) without
affecting business logic.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import timedelta

from app.core.logging import get_logger

logger = get_logger(__name__)


class ICacheService(ABC):
    """Interface for caching (Dependency Inversion Principle).
    
    Clients depend on this abstraction, enabling flexible
    cache implementation switching.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if found, None otherwise
        """
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> None:
        """Store a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live, if supported
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a cache entry.
        
        Args:
            key: Cache key
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        pass


class InMemoryCacheService(ICacheService):
    """Simple in-memory cache implementation.
    
    Suitable for development and testing.
    Not suitable for production distributed systems.
    """

    def __init__(self):
        """Initialize in-memory cache storage."""
        self._cache: dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache."""
        value = self._cache.get(key)
        if value is not None:
            logger.debug(f"Cache hit: {key}")
        else:
            logger.debug(f"Cache miss: {key}")
        return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> None:
        """Store a value in cache."""
        self._cache[key] = value
        logger.debug(f"Cached: {key}")
        if ttl:
            logger.debug(f"TTL: {ttl} (not enforced in in-memory cache)")

    async def delete(self, key: str) -> None:
        """Delete a cache entry."""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Deleted from cache: {key}")

    async def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.debug("Cache cleared")

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._cache


class NoOpCacheService(ICacheService):
    """No-operation cache service for testing/development.
    
    All operations are no-ops. Useful when caching should be disabled.
    """

    async def get(self, key: str) -> Optional[Any]:
        """Always return None."""
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> None:
        """Do nothing."""
        pass

    async def delete(self, key: str) -> None:
        """Do nothing."""
        pass

    async def clear(self) -> None:
        """Do nothing."""
        pass

    async def exists(self, key: str) -> bool:
        """Always return False."""
        return False
