"""
Fetch User Context Node - Retrieves user data with caching.
"""
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.workflow_schemas import ChatState, ContextData

logger = logging.getLogger(__name__)


def fetch_user_context_node(state: "ChatState", cache, get_user_fn) -> "ChatState":
    """
    Node 2b: Fetch user data (cached 5 min).
    
    Args:
        state: Current workflow state
        cache: Cache service instance
        get_user_fn: Function to fetch user from database with retry
    
    Returns:
        Updated state with user_data
    """
    start_time = time.time()
    logger.info("[NODE 2b: fetch_user_data] Fetching user data")
    
    try:
        user_ctx = state["user_context"]
        
        user_cache_key = f"user:{user_ctx['user_id']}"
        user_start = time.time()
        user = cache.get(user_cache_key)
        
        if user is None:
            user = get_user_fn(user_ctx["user_id"], user_ctx["tenant_id"])
            if user:
                cache.set(user_cache_key, user, ttl_seconds=300)  # 5 min
                logger.info(f"🟡 USER DB: {user_cache_key} in {time.time() - user_start:.2f}s")
            else:
                logger.warning(f"🔴 USER NOT FOUND: {user_ctx['user_id']}")
        else:
            logger.info(f"🟢 USER CACHE HIT: {user_cache_key} in {time.time() - user_start:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"✅ [NODE 2b: fetch_user_data] Completed in {total_time:.2f}s")
        
        # Update nested ContextData structure
        existing_context = state.get("context", {})
        if existing_context is None:
            existing_context = {}
        
        updated_context: "ContextData" = {
            **existing_context,
            "user_data": user
        }

        # Extract user language for query_rewrite_node
        user_language = user.get("default_lang", "en") if user else "en"
        updated_user_context = {
            **state.get("user_context", {}),
            "user_language": user_language
        }
        
        return {
            **state,
            "context": updated_context,
            "user_context": updated_user_context
        }
    
    except Exception as e:
        logger.error(f"[NODE 2b] User fetch failed: {e}", exc_info=True)
        
        # Update nested ContextData structure (error case)
        existing_context = state.get("context", {})
        if existing_context is None:
            existing_context = {}
        
        updated_context: "ContextData" = {
            **existing_context,
            "user_data": None
        }

        # Default user language for error case
        updated_user_context = {
            **state.get("user_context", {}),
            "user_language": "en"  # Default fallback
        }
        
        return {
            **state,
            "context": updated_context,
            "user_context": updated_user_context,
            "error": f"User fetch error: {str(e)}"
        }
