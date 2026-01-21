"""
Cache Warmup Endpoint

Pre-loads caches when user is selected (BEFORE first message sent).
Eliminates cold start latency:
- Tenant cache (5 min TTL)
- User cache (5 min TTL)  
- System prompt cache (3-tier: memory → DB → LLM)

Usage: Frontend calls this on user dropdown change.
"""

import logging
import time
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from database.pg_init import get_tenant_by_id, get_user_by_id_pg
from services.cache_service import get_context_cache

logger = logging.getLogger(__name__)

router = APIRouter()


class WarmupRequest(BaseModel):
    """Request to warm up caches for a user."""
    tenant_id: int
    user_id: int


class WarmupResponse(BaseModel):
    """Cache warmup results."""
    success: bool
    tenant_cached: bool
    user_cached: bool
    system_prompt_cached: bool
    cache_source: str  # "memory" | "database" | "llm_generated"
    total_time_ms: float


@router.post("/warmup", response_model=WarmupResponse)
async def warmup_caches(request: WarmupRequest):
    """
    Warm up all caches for a user (tenant, user, system prompt).
    
    Called by frontend when user is selected from dropdown.
    Pre-loads caches to eliminate cold start on first message.
    
    Performance impact:
    - Cold cache: ~800-1200ms (includes LLM system prompt generation)
    - Warm cache: ~2-5ms (all memory hits)
    
    Args:
        request: Tenant ID and User ID to warm up
    
    Returns:
        WarmupResponse with cache hit/miss details and timing
    """
    start_time = time.time()
    
    try:
        cache = get_context_cache()
        
        # === STEP 1: Warm tenant cache ===
        tenant_cache_key = f"tenant:{request.tenant_id}"
        tenant = cache.get(tenant_cache_key)
        tenant_cached = tenant is not None
        
        if tenant is None:
            logger.info(f"🔥 WARMUP: Tenant cache MISS - loading {request.tenant_id}")
            tenant = get_tenant_by_id(request.tenant_id)
            if tenant:
                cache.set(tenant_cache_key, tenant, ttl_seconds=300)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tenant {request.tenant_id} not found"
                )
        else:
            logger.info(f"🔥 WARMUP: Tenant cache HIT - {request.tenant_id}")
        
        # === STEP 2: Warm user cache ===
        user_cache_key = f"user:{request.user_id}"
        user = cache.get(user_cache_key)
        user_cached = user is not None
        
        if user is None:
            logger.info(f"🔥 WARMUP: User cache MISS - loading {request.user_id}")
            user = get_user_by_id_pg(request.user_id, request.tenant_id)
            if user:
                cache.set(user_cache_key, user, ttl_seconds=300)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {request.user_id} not found"
                )
        else:
            logger.info(f"🔥 WARMUP: User cache HIT - {request.user_id}")
        
        # === STEP 3: Warm system prompt cache (3-tier) ===
        from services.unified_chat_workflow import UnifiedChatWorkflow
        from api.dependencies import get_chat_workflow
        
        workflow = get_chat_workflow()
        if workflow:
            tenant_prompt = tenant.get("system_prompt") if tenant else None
            user_prompt = user.get("system_prompt") if user else None
            
            # This will check: memory → DB → LLM (and cache result)
            system_prompt, cached, source = workflow._get_or_build_system_prompt(
                user_id=request.user_id,
                user=user,
                tenant_prompt=tenant_prompt,
                user_prompt=user_prompt
            )
            
            system_prompt_cached = cached
            cache_source = source
            
            logger.info(f"🔥 WARMUP: System prompt {cache_source} - {'HIT' if cached else 'GENERATED'}")
        else:
            # Workflow not initialized (OPENAI_API_KEY missing)
            system_prompt_cached = False
            cache_source = "workflow_unavailable"
            logger.warning("🔥 WARMUP: Workflow not available - skipping system prompt")
        
        total_time = (time.time() - start_time) * 1000  # Convert to ms
        
        logger.info(
            f"✅ WARMUP COMPLETE: tenant_id={request.tenant_id}, user_id={request.user_id}, "
            f"time={total_time:.1f}ms, cache_source={cache_source}"
        )
        
        return WarmupResponse(
            success=True,
            tenant_cached=tenant_cached,
            user_cached=user_cached,
            system_prompt_cached=system_prompt_cached,
            cache_source=cache_source,
            total_time_ms=round(total_time, 1)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ WARMUP FAILED: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache warmup failed: {str(e)}"
        )
