"""
Unit Test: Cache Service
Knowledge Router PROD

Tests SimpleCache functionality:
- get/set operations
- TTL expiry
- DEV_MODE bypass
- Pattern-based clearing
- Append to list with sliding window

Priority: HIGH (cache is critical infrastructure)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from services.cache_service import SimpleCache


@pytest.mark.unit
class TestSimpleCache:
    """Test SimpleCache functionality."""
    
    # ========================================================================
    # BASIC GET/SET
    # ========================================================================
    
    def test_set_and_get_basic(self):
        """Test basic set and get operations."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.set("test_key", "test_value")
        result = cache.get("test_key")
        
        assert result == "test_value"
    
    def test_get_nonexistent_key_returns_none(self):
        """Test getting a key that doesn't exist returns None."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        result = cache.get("nonexistent_key")
        
        assert result is None
    
    def test_set_overwrites_existing(self):
        """Test that setting a key overwrites existing value."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.set("key", "value1")
        cache.set("key", "value2")
        result = cache.get("key")
        
        assert result == "value2"
    
    def test_set_complex_types(self):
        """Test caching complex types (dict, list)."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        # Dict
        cache.set("dict_key", {"name": "test", "value": 42})
        dict_result = cache.get("dict_key")
        assert dict_result == {"name": "test", "value": 42}
        
        # List
        cache.set("list_key", [1, 2, 3, "four"])
        list_result = cache.get("list_key")
        assert list_result == [1, 2, 3, "four"]
    
    # ========================================================================
    # TTL EXPIRY
    # ========================================================================
    
    def test_ttl_expiry(self):
        """Test that cached values expire after TTL."""
        cache = SimpleCache(default_ttl_seconds=1, dev_mode=False)
        
        cache.set("expiring_key", "value")
        
        # Should exist immediately
        assert cache.get("expiring_key") == "value"
        
        # Simulate time passing by manipulating expires_at
        cache._cache["expiring_key"]["expires_at"] = datetime.now() - timedelta(seconds=1)
        
        # Should now return None (expired)
        assert cache.get("expiring_key") is None
    
    def test_custom_ttl_per_key(self):
        """Test setting custom TTL for individual keys."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.set("short_ttl", "value", ttl_seconds=1)
        cache.set("long_ttl", "value", ttl_seconds=3600)
        
        # Simulate short TTL expiry
        cache._cache["short_ttl"]["expires_at"] = datetime.now() - timedelta(seconds=1)
        
        # Short TTL should be expired
        assert cache.get("short_ttl") is None
        # Long TTL should still exist
        assert cache.get("long_ttl") == "value"
    
    def test_cleanup_expired(self):
        """Test cleanup_expired removes expired entries."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # Expire key1 and key2
        cache._cache["key1"]["expires_at"] = datetime.now() - timedelta(seconds=1)
        cache._cache["key2"]["expires_at"] = datetime.now() - timedelta(seconds=1)
        
        cache.cleanup_expired()
        
        # key1 and key2 should be gone
        assert "key1" not in cache._cache
        assert "key2" not in cache._cache
        # key3 should remain
        assert cache.get("key3") == "value3"
    
    # ========================================================================
    # DEV_MODE BYPASS
    # ========================================================================
    
    def test_dev_mode_get_always_returns_none(self):
        """Test that DEV_MODE=True disables cache reads."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=True)
        
        # Manually insert into cache (bypassing set)
        cache._cache["test_key"] = {
            "value": "test_value",
            "expires_at": datetime.now() + timedelta(hours=1)
        }
        
        # Get should still return None in dev_mode
        assert cache.get("test_key") is None
    
    def test_dev_mode_set_does_not_store(self):
        """Test that DEV_MODE=True disables cache writes."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=True)
        
        cache.set("key", "value")
        
        # Cache should be empty
        assert len(cache._cache) == 0
    
    # ========================================================================
    # INVALIDATE / DELETE
    # ========================================================================
    
    def test_invalidate_removes_key(self):
        """Test invalidate removes specific key."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.invalidate("key1")
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
    
    def test_delete_alias_for_invalidate(self):
        """Test delete() is an alias for invalidate()."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.set("key", "value")
        cache.delete("key")
        
        assert cache.get("key") is None
    
    def test_invalidate_nonexistent_key_no_error(self):
        """Test invalidating non-existent key doesn't raise error."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        # Should not raise
        cache.invalidate("nonexistent")
    
    # ========================================================================
    # CLEAR / CLEAR_PATTERN
    # ========================================================================
    
    def test_clear_removes_all_entries(self):
        """Test clear removes all cached entries."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        cache.clear()
        
        assert len(cache._cache) == 0
    
    def test_clear_pattern_prefix_match(self):
        """Test clear_pattern removes keys with matching prefix."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.set("users:tenant=1:user=1", "data1")
        cache.set("users:tenant=1:user=2", "data2")
        cache.set("users:tenant=2:user=1", "data3")
        cache.set("sessions:session=abc", "data4")
        
        cache.clear_pattern("users:tenant=1")
        
        # Keys matching pattern should be gone
        assert cache.get("users:tenant=1:user=1") is None
        assert cache.get("users:tenant=1:user=2") is None
        # Other keys should remain
        assert cache.get("users:tenant=2:user=1") == "data3"
        assert cache.get("sessions:session=abc") == "data4"
    
    def test_clear_pattern_in_dev_mode_no_error(self):
        """Test clear_pattern in DEV_MODE doesn't raise error."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=True)
        
        # Should not raise
        cache.clear_pattern("any:pattern")
    
    # ========================================================================
    # APPEND TO LIST
    # ========================================================================
    
    def test_append_to_list_creates_new_list(self):
        """Test append_to_list creates new list if key doesn't exist."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.append_to_list("messages", "msg1", max_size=10)
        
        result = cache.get("messages")
        assert result == ["msg1"]
    
    def test_append_to_list_appends_to_existing(self):
        """Test append_to_list appends to existing list."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        cache.append_to_list("messages", "msg1", max_size=10)
        cache.append_to_list("messages", "msg2", max_size=10)
        cache.append_to_list("messages", "msg3", max_size=10)
        
        result = cache.get("messages")
        assert result == ["msg1", "msg2", "msg3"]
    
    def test_append_to_list_sliding_window(self):
        """Test append_to_list removes oldest when max_size exceeded."""
        cache = SimpleCache(default_ttl_seconds=300, dev_mode=False)
        
        for i in range(5):
            cache.append_to_list("messages", f"msg{i}", max_size=3)
        
        result = cache.get("messages")
        
        # Should only have last 3 messages
        assert len(result) == 3
        assert result == ["msg2", "msg3", "msg4"]
