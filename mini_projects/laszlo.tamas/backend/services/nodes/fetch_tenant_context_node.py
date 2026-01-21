"""
Fetch Tenant Context Node - Retrieves tenant data with caching.
"""
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.workflow_schemas import ChatState, ContextData

logger = logging.getLogger(__name__)


def fetch_tenant_context_node(state: "ChatState", cache, get_tenant_fn) -> "ChatState":
    """
    Node 2a: Fetch tenant data (cached 5 min).
    
    Args:
        state: Current workflow state
        cache: Cache service instance
        get_tenant_fn: Function to fetch tenant from database with retry
    
    Returns:
        Updated state with tenant_data
    """
    start_time = time.time()
    logger.info("[NODE 2a: fetch_tenant_data] Fetching tenant data")
    
    try:
        user_ctx = state["user_context"]
        
        tenant_cache_key = f"tenant:{user_ctx['tenant_id']}"
        tenant_start = time.time()
        tenant = cache.get(tenant_cache_key)
        
        if tenant is None:
            tenant = get_tenant_fn(user_ctx["tenant_id"])
            if tenant:
                cache.set(tenant_cache_key, tenant, ttl_seconds=300)  # 5 min
                logger.info(f"🟡 TENANT DB: {tenant_cache_key} in {time.time() - tenant_start:.2f}s")
            else:
                logger.warning(f"🔴 TENANT NOT FOUND: {user_ctx['tenant_id']}")
        else:
            logger.info(f"🟢 TENANT CACHE HIT: {tenant_cache_key} in {time.time() - tenant_start:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"✅ [NODE 2a: fetch_tenant_data] Completed in {total_time:.2f}s")
        
        # Update nested ContextData structure
        existing_context = state.get("context", {})
        if existing_context is None:
            existing_context = {}
        
        updated_context: "ContextData" = {
            **existing_context,
            "tenant_data": tenant
        }
        
        return {
            **state,
            "context": updated_context
        }
    
    except Exception as e:
        logger.error(f"[NODE 2a] Tenant fetch failed: {e}", exc_info=True)
        
        # Update nested ContextData structure (error case)
        existing_context = state.get("context", {})
        if existing_context is None:
            existing_context = {}
        
        updated_context: "ContextData" = {
            **existing_context,
            "tenant_data": None
        }
        
        return {
            **state,
            "context": updated_context,
            "error": f"Tenant fetch error: {str(e)}"
        }
