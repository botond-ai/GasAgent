"""
User Management Endpoints

Handles user CRUD operations and user sub-resources (debug, conversations, memories).
Follows RESTful hierarchy: /users/{id}/<sub-resource>
"""

import logging
from fastapi import APIRouter, HTTPException, Query, status, Depends
from api.dependencies import get_cache_service
from api.schemas import UserUpdateRequest
from api.helpers import (
    handle_api_error,
    NotFoundError,
    cached_query,
    invalidate_cache_keys,
    validate_resource_exists
)
from database.pg_init import (
    get_all_users_pg,
    get_users_by_tenant,
    get_user_by_id_pg,
    update_user,
    delete_user_conversation_history_pg,
    get_long_term_memories_for_user
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
@handle_api_error("list users")
async def list_users(
    tenant_id: int | None = Query(None, description="Filter users by tenant"),
    cache = Depends(get_cache_service)
):
    """
    Get all users, optionally filtered by tenant.
    
    Args:
        tenant_id: Filter users by tenant (optional)
    
    Returns:
        List of user objects
    
    Cache: 5 minutes TTL
    """
    cache_key = f"users:tenant={tenant_id}"
    
    return cached_query(
        cache=cache,
        cache_key=cache_key,
        query_func=lambda: get_users_by_tenant(tenant_id) if tenant_id else get_all_users_pg(),
        ttl_seconds=300
    )


@router.get("/{user_id}")
@handle_api_error("fetch user")
async def get_user(user_id: int):
    """
    Get user details by ID.
    
    Args:
        user_id: User identifier
    
    Returns:
        User object with full details
    
    Raises:
        404: User not found
    """
    # Get user endpoint uses hardcoded tenant_id=1 for development
    user = get_user_by_id_pg(user_id, tenant_id=1)
    return validate_resource_exists(user, "User", user_id)


@router.patch("/{user_id}")
@handle_api_error("update user")
async def update_user_endpoint(
    user_id: int,
    update_data: UserUpdateRequest,
    cache = Depends(get_cache_service)
):
    """
    Update user details.
    
    Args:
        user_id: User identifier
        update_data: Fields to update (nickname, system_prompt, default_lang)
    
    Returns:
        Updated user object
    
    Side effects:
        - Invalidates user cache
    
    Raises:
        404: User not found
    """
    # Verify user exists
    user = get_user_by_id_pg(user_id, tenant_id=1)
    validate_resource_exists(user, "User", user_id)
    
    # Update user
    updated_user = update_user(
        user_id=user_id,
        nickname=update_data.nickname,
        system_prompt=update_data.system_prompt,
        default_lang=update_data.default_lang
    )
    
    # Invalidate cache
    tenant_id = user.get('tenant_id')
    invalidate_cache_keys(cache, [
        f"users:tenant={tenant_id}",
        "users:tenant=None"
    ])
    
    logger.info(f"✅ Updated user {user_id}")
    return updated_user


# ===== USER SUB-RESOURCES =====

@router.get("/{user_id}/debug")
@handle_api_error("fetch user debug info")
async def get_user_debug_info(user_id: int, tenant_id: int = Query(..., description="Tenant ID")):
    """
    Get debug information for a user.
    
    REST: Debug info is a sub-resource of user.
    
    Returns:
        {"user_data": {...}}
    
    Raises:
        404: User not found
    
    Use case: Frontend debug panel, admin diagnostics
    """
    logger.info(f"[GET /users/{user_id}/debug] Fetching user data for tenant {tenant_id}")
    
    user = get_user_by_id_pg(user_id, tenant_id)
    validate_resource_exists(user, "User", user_id)
    
    logger.info(f"[GET /users/{user_id}/debug] User found: {user.get('nickname', 'N/A')}")
    
    return {"user_data": user}


@router.delete("/{user_id}/conversations")
@handle_api_error("delete user conversations")
async def delete_user_conversations(user_id: int):
    """
    Delete all conversation history for a user.
    
    REST: Conversations are a sub-resource of user.
    
    Deletes:
        - All chat_sessions for the user
        - All chat_messages in those sessions (cascade)
    
    Returns:
        {"message": "...", "sessions_deleted": int, "messages_deleted": int}
    
    Raises:
        404: User not found
    
    Use case: Reset chat history (dev), GDPR compliance
    """
    logger.info(f"[DELETE /users/{user_id}/conversations] Starting deletion")
    
    user = get_user_by_id_pg(user_id, tenant_id=1)
    validate_resource_exists(user, "User", user_id)
    
    result = delete_user_conversation_history_pg(user_id)
    
    logger.info(
        f"[DELETE /users/{user_id}/conversations] Deleted {result['sessions_deleted']} sessions, "
        f"{result['messages_deleted']} messages"
    )
    
    return {
        "message": f"All conversation history deleted for user {user.get('nickname', 'N/A')}",
        "sessions_deleted": result['sessions_deleted'],
        "messages_deleted": result['messages_deleted']
    }


@router.get("/{user_id}/memories")
@handle_api_error("fetch user memories")
async def get_user_memories(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of memories to return")
):
    """
    Get all long-term memories for a user.
    
    REST: Memories are a sub-resource of user.
    
    Returns:
        {"memories": [...], "count": int}
    
    Raises:
        404: User not found
    
    Use case: View stored facts, LTM debugging, user profile page
    """
    logger.info(f"[GET /users/{user_id}/memories] Fetching memories (limit={limit})")
    
    user = get_user_by_id_pg(user_id, tenant_id=1)
    validate_resource_exists(user, "User", user_id)
    
    memories = get_long_term_memories_for_user(user_id, limit=limit)
    
    logger.info(f"[GET /users/{user_id}/memories] Found {len(memories)} memories")
    
    return {
        "memories": memories,
        "count": len(memories)
    }
