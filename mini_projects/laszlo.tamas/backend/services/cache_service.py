"""
Simple in-memory cache for tenant and user data.
Reduces PostgreSQL query overhead for frequently accessed data.
P0.17: Now respects ENABLE_MEMORY_CACHE from system.ini
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SimpleCache:
    """Thread-safe in-memory cache with TTL support."""
    
    def __init__(self, default_ttl_seconds: int = 300, dev_mode: bool = False):
        """
        Initialize cache.
        
        Args:
            default_ttl_seconds: Default time-to-live in seconds (default: 5 minutes)
            dev_mode: If True, cache is disabled (always returns None)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = timedelta(seconds=default_ttl_seconds)
        self.dev_mode = dev_mode
        
        if dev_mode:
            logger.warning("⚠️ DEV_MODE=true - Cache DISABLED")
        else:
            logger.info(f"Cache initialized with TTL: {default_ttl_seconds}s")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found or expired
        """
        # DEV_MODE: Always return None (cache disabled)
        if self.dev_mode:
            return None
        
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check if expired
        if datetime.now() > entry["expires_at"]:
            logger.info(f"⏰ Cache expired: {key}")
            del self._cache[key]
            return None
        
        logger.info(f"✅ Cache hit: {key}")
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (uses default if None)
        """
        # DEV_MODE: Skip caching
        if self.dev_mode:
            return
        
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self.default_ttl
        expires_at = datetime.now() + ttl
        
        self._cache[key] = {
            "value": value,
            "expires_at": expires_at
        }
        
        logger.info(f"💾 Cache set: {key} (expires: {expires_at.strftime('%H:%M:%S')})")
    
    def invalidate(self, key: str):
        """
        Remove key from cache.
        
        Args:
            key: Cache key to remove
        """
        if key in self._cache:
            del self._cache[key]
            logger.info(f"🗑️ Cache invalidated: {key}")
    
    def delete(self, key: str):
        """
        Alias for invalidate() - removes key from cache.
        
        Args:
            key: Cache key to remove
        """
        self.invalidate(key)
    
    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()
        logger.info("Cache cleared")
    
    def clear_pattern(self, pattern: str):
        """
        Clear all cache keys matching a pattern (prefix match).
        
        Args:
            pattern: Key prefix to match (e.g., "users:tenant=" clears "users:tenant=1", "users:tenant=2", etc.)
        """
        if self.dev_mode:
            return
        
        keys_to_delete = [key for key in self._cache.keys() if key.startswith(pattern)]
        
        for key in keys_to_delete:
            del self._cache[key]
        
        if keys_to_delete:
            logger.info(f"🗑️ Cache pattern cleared: {pattern} ({len(keys_to_delete)} keys)")
    
    def cleanup_expired(self):
        """Remove all expired entries from cache."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def append_to_list(self, key: str, item: Any, max_size: int, ttl_seconds: Optional[int] = None):
        """
        Append item to a cached list with sliding window (FIFO).
        If list exceeds max_size, oldest item is removed.
        
        Args:
            key: Cache key
            item: Item to append
            max_size: Maximum list size (sliding window)
            ttl_seconds: Time-to-live in seconds (uses default if None)
        """
        if self.dev_mode:
            return
        
        # Get existing list or create new
        current_list = self.get(key)
        if current_list is None:
            current_list = []
        
        # Append new item
        current_list.append(item)
        
        # Sliding window: remove oldest if exceeds max_size
        if len(current_list) > max_size:
            current_list.pop(0)
            logger.debug(f"📦 Chat history sliding window: removed oldest message (key={key})")
        
        # Save back to cache
        self.set(key, current_list, ttl_seconds)


class DummyCache:
    """
    No-op cache for debugging purposes.
    Used when ENABLE_MEMORY_CACHE=false in system.ini.
    """
    
    def get(self, key: str) -> Optional[Any]:
        """Always return None (cache disabled)."""
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Do nothing (cache disabled)."""
        pass
    
    def append_to_list(self, key: str, item: Any, max_size: int, ttl_seconds: Optional[int] = None):
        """Do nothing (cache disabled)."""
        pass
    
    def invalidate(self, key: str):
        """Do nothing (cache disabled)."""
        pass
    
    def delete(self, key: str):
        """Do nothing (cache disabled)."""
        pass
    
    def clear(self):
        """Do nothing (cache disabled)."""
        pass
    
    def clear_pattern(self, pattern: str):
        """Do nothing (cache disabled)."""
        pass
    
    def cleanup_expired(self):
        """Do nothing (cache disabled)."""
        pass


# Global cache instance
_context_cache = None  # Will be initialized on first access


def get_context_cache() -> SimpleCache:
    """
    Get the global context cache instance.
    Respects ENABLE_MEMORY_CACHE from system.ini (P0.17).
    """
    global _context_cache
    
    if _context_cache is None:
        # Import here to avoid circular dependency
        from services.config_service import get_config_service
        
        config = get_config_service()
        
        # Check if DEV_MODE is enabled (highest priority - disables all caches)
        if config.is_dev_mode():
            logger.warning("⚠️ DEV_MODE=true - ALL CACHES DISABLED")
            _context_cache = DummyCache()
        # Check if memory cache is explicitly disabled
        elif not config.get_bool('cache', 'ENABLE_MEMORY_CACHE', default=True):
            logger.warning("⚠️ Memory cache DISABLED (system.ini: ENABLE_MEMORY_CACHE=false)")
            _context_cache = DummyCache()
        else:
            # Get TTL from config
            ttl = config.get_int('cache', 'MEMORY_CACHE_TTL_SECONDS', default=3600)
            _context_cache = SimpleCache(default_ttl_seconds=ttl, dev_mode=False)
            logger.info(f"✅ Memory cache ENABLED (TTL: {ttl}s)")
    
    return _context_cache


# === Chat History Cache Helpers ===

def get_chat_history_cache_key(session_id: str) -> str:
    """
    Generate cache key for session-level chat history.
    
    Args:
        session_id: Current session ID
    
    Returns:
        Cache key string
    """
    return f"chat_history:session:{session_id}"


def get_chat_history_from_cache(session_id: str) -> Optional[list]:
    """
    Get chat history from cache (session-level only).
    
    Args:
        session_id: Current session ID
    
    Returns:
        List of messages or None if not cached
    """
    cache = get_context_cache()
    key = get_chat_history_cache_key(session_id)
    return cache.get(key)


def set_chat_history_to_cache(session_id: str, messages: list, ttl_seconds: int = 3600):
    """
    Initialize chat history cache with messages from DB (session-level only).
    
    Args:
        session_id: Current session ID
        messages: List of message dicts
        ttl_seconds: Cache TTL (default: 1 hour)
    """
    cache = get_context_cache()
    key = get_chat_history_cache_key(session_id)
    cache.set(key, messages, ttl_seconds)
    logger.info(f"💬 Chat history cached: {key} ({len(messages)} messages)")


def append_message_to_cache(session_id: str, message: dict, max_size: int = 30):
    """
    Append new message to chat history cache (sliding window, session-level only).
    
    Args:
        session_id: Current session ID
        message: Message dict with 'role' and 'content'
        max_size: Maximum messages to keep (default: 30)
    """
    cache = get_context_cache()
    key = get_chat_history_cache_key(session_id)
    cache.append_to_list(key, message, max_size, ttl_seconds=3600)
    logger.debug(f"💬 Message appended to cache: {key} (role={message.get('role')})")


def clear_chat_history_cache(session_id: str):
    """
    Clear chat history cache for specific session.
    
    Args:
        session_id: Session ID to clear
    """
    cache = get_context_cache()
    key = get_chat_history_cache_key(session_id)
    cache.invalidate(key)
    logger.info(f"🗑️ Chat history cache cleared: {key}")


# Alias for backward compatibility - call the function to get the cache instance
simple_cache = get_context_cache()
