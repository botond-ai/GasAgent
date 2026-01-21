"""
Admin Endpoints

Cache management, configuration queries, and system control.
"""

import logging
from fastapi import APIRouter, HTTPException

from api.helpers import handle_api_error
from api.schemas import (
    CacheStatsResponse, CacheInvalidateResponse, CacheClearResponse, DevModeResponse
)
from services.cache_control import get_cache_control

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/cache/stats", response_model=CacheStatsResponse)
@handle_api_error("get cache stats")
async def get_cache_stats():
    """
    Get comprehensive cache statistics for all layers.
    
    Returns statistics for:
    - Memory cache (Tier 1)
    - PostgreSQL cache (Tier 2)
    - Current configuration flags
    
    **Frontend**: Auto-refreshes every 5 seconds
    
    Use case: Admin dashboard monitoring
    """
    cache_control = get_cache_control()
    stats = cache_control.get_stats()
    
    logger.info(f"📊 Cache stats requested: memory_size={stats['memory_cache']['size']}, db_users={stats['db_cache']['cached_users']}")
    
    return stats


@router.post("/cache/clear", response_model=CacheClearResponse)
@handle_api_error("clear all caches")
async def clear_all_caches():
    """
    Clear ALL cache layers (memory + DB).
    
    ⚠️ WARNING: This is a destructive operation!
    - Memory cache: All entries cleared
    - DB cache: All user_prompt_cache entries deleted
    
    **Use case**: Development/debugging when cache becomes stale
    """
    cache_control = get_cache_control()
    result = cache_control.clear_all()
    
    logger.warning(f"🗑️ ALL CACHES CLEARED! memory={result['memory_cleared']}, db={result['db_cleared']}")
    
    return result


@router.delete("/cache/user/{user_id}", response_model=CacheInvalidateResponse)
@handle_api_error("invalidate user cache")
async def invalidate_user_cache(user_id: int):
    """
    Invalidate all caches for a specific user.
    
    Clears:
    - Memory cache: system_prompt:{user_id}, user:{user_id}
    - DB cache: All user_prompt_cache entries for user
    
    **Use case**: User updates their system_prompt or preferences
    """
    cache_control = get_cache_control()
    result = cache_control.invalidate_user(user_id)
    
    logger.info(f"🗑️ User cache invalidated: user_id={user_id}, memory={result['memory_cleared']}, db={result['db_cleared']}")
    
    return result


@router.delete("/cache/tenant/{tenant_id}", response_model=CacheInvalidateResponse)
@handle_api_error("invalidate tenant cache")
async def invalidate_tenant_cache(tenant_id: int):
    """
    Invalidate all caches for a tenant and its users.
    
    Clears:
    - Memory cache: All tenant and user entries
    - DB cache: All user_prompt_cache entries for tenant's users
    
    **Use case**: Tenant updates company-wide system_prompt
    """
    cache_control = get_cache_control()
    result = cache_control.invalidate_tenant(tenant_id)
    
    logger.info(f"🗑️ Tenant cache invalidated: tenant_id={tenant_id}, users={result['users_affected']}, memory={result['memory_cleared']}, db={result['db_cleared']}")
    
    return result


@router.post("/cache/enable")
@handle_api_error("enable cache")
async def enable_cache():
    """
    Enable caching at runtime (without restart).
    
    ⚠️ Note: This only affects the in-memory cache flag.
    DEV_MODE in system.ini takes precedence.
    
    **Use case**: Re-enable cache after debugging
    """
    # Check if DEV_MODE is active
    from services.config_service import get_config_service
    config = get_config_service()
    
    if config.is_dev_mode():
        return {
            "success": False,
            "message": "Cannot enable cache: DEV_MODE=true in system.ini (restart required to change)"
        }
    
    # Enable cache (would need cache_control to support this)
    # For now, just return status
    return {
        "success": True,
        "message": "Cache is already enabled (DEV_MODE=false)"
    }


@router.post("/cache/disable")
@handle_api_error("disable cache")
async def disable_cache():
    """
    Disable caching at runtime (without restart).
    
    ⚠️ WARNING: This will impact performance!
    All requests will hit the database directly.
    
    **Use case**: Debugging cache-related issues
    """
    # Note: True runtime disable would require cache_control refactoring
    # For now, document that DEV_MODE in system.ini is the proper way
    return {
        "success": False,
        "message": "Runtime cache disable not implemented. Use DEV_MODE=true in system.ini and restart."
    }


@router.get("/config/dev-mode", response_model=DevModeResponse)
@handle_api_error("get dev mode")
async def get_dev_mode():
    """
    Get development mode status from system.ini.
    
    Used by frontend to determine runtime cache behavior.
    Returns the current DEV_MODE setting which controls all cache layers.
    
    **Frontend**: Fetches once on app startup and caches the result.
    
    Use case: Frontend cache behavior detection
    """
    from services.config_service import get_config_service
    
    config = get_config_service()
    dev_mode = config.is_dev_mode()
    
    logger.info(f"🔧 DEV_MODE status requested: {dev_mode}")
    
    return {"dev_mode": dev_mode}


@router.get("/config/idle-timeout")
@handle_api_error("get idle timeout")
async def get_idle_timeout():
    """
    Get idle timeout for auto-consolidation from system.ini.
    
    Returns the configured timeout in seconds.
    Frontend uses this to determine when to trigger session consolidation.
    
    **Frontend**: Fetches once on app startup.
    """
    from services.config_service import get_config_service
    
    config = get_config_service()
    idle_timeout = config.get_idle_timeout_seconds()
    
    logger.info(f"⏰ IDLE_TIMEOUT requested: {idle_timeout}s")
    
    return {"idle_timeout_seconds": idle_timeout}
