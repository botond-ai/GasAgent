"""
Cache Helper Utilities

Reusable cache patterns for API routers.
Reduces cache boilerplate code.
"""

import logging
from typing import Callable, TypeVar, Any, List

logger = logging.getLogger(__name__)

T = TypeVar('T')


def cached_query(
    cache: Any,
    cache_key: str,
    query_func: Callable[[], T],
    ttl_seconds: int = 300
) -> T:
    """
    Execute query with cache check.
    
    Pattern:
        1. Try cache
        2. On miss, execute query
        3. Store result in cache
        4. Return result
    
    Usage:
        tenants = cached_query(
            cache=cache,
            cache_key="tenants:active=True",
            query_func=lambda: get_active_tenants(),
            ttl_seconds=300
        )
    
    Args:
        cache: Cache service instance
        cache_key: Cache key string
        query_func: Function that returns data
        ttl_seconds: Time-to-live in seconds (default: 5 minutes)
    
    Returns:
        Query result (from cache or fresh)
    """
    # Try cache
    cached_result = cache.get(cache_key)
    
    if cached_result is not None:
        logger.info(f"🟢 Cache HIT: {cache_key}")
        return cached_result
    
    # Cache MISS - execute query
    logger.info(f"🔴 Cache MISS: {cache_key}")
    result = query_func()
    
    # Store in cache
    cache.set(cache_key, result, ttl_seconds=ttl_seconds)
    
    return result


def invalidate_cache_keys(cache: Any, keys: List[str]) -> None:
    """
    Invalidate multiple cache keys.
    
    Usage:
        invalidate_cache_keys(cache, [
            "tenants:active=True",
            "tenants:active=False",
            f"tenant:{tenant_id}"
        ])
    
    Args:
        cache: Cache service instance
        keys: List of cache keys to invalidate
    """
    for key in keys:
        cache.delete(key)
        logger.debug(f"🗑️ Cache invalidated: {key}")
