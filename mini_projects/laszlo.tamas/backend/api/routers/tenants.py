"""
Tenant Management Endpoints

Handles tenant CRUD operations and tenant-user relationships.
All endpoints support caching with 5-minute TTL.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query

from api.dependencies import get_cache_service
from api.schemas import TenantUpdateRequest
from api.helpers import (
    handle_api_error,
    NotFoundError,
    cached_query,
    invalidate_cache_keys,
    validate_resource_exists
)
from database.pg_init import (
    get_active_tenants,
    get_all_tenants,
    get_tenant_by_id,
    get_users_by_tenant,
    update_tenant
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
@handle_api_error("list tenants")
async def list_tenants(
    active_only: bool = Query(True, description="Filter by active status"),
    cache = Depends(get_cache_service)
):
    """
    Get all tenants or only active ones.
    
    Args:
        active_only: Filter to only active tenants (default: True)
    
    Returns:
        List of tenant objects with id, name, is_active fields
    
    Cache: 5 minutes TTL
    """
    cache_key = f"tenants:active={active_only}"
    
    return cached_query(
        cache=cache,
        cache_key=cache_key,
        query_func=lambda: get_active_tenants() if active_only else get_all_tenants(),
        ttl_seconds=300
    )


@router.get("/{tenant_id}")
@handle_api_error("fetch tenant")
async def get_tenant(tenant_id: int):
    """
    Get tenant details by ID.
    
    Args:
        tenant_id: Tenant identifier
    
    Returns:
        Tenant object with full details
    
    Raises:
        404: Tenant not found
    """
    tenant = get_tenant_by_id(tenant_id)
    return validate_resource_exists(tenant, "Tenant", tenant_id)


@router.patch("/{tenant_id}")
@handle_api_error("update tenant")
async def update_tenant_endpoint(
    tenant_id: int,
    update_data: TenantUpdateRequest,
    cache = Depends(get_cache_service)
):
    """
    Update tenant details.
    
    Args:
        tenant_id: Tenant identifier
        update_data: Fields to update (name, is_active)
    
    Returns:
        Updated tenant object
    
    Side effects:
        - Invalidates tenant cache
    
    Raises:
        404: Tenant not found
    """
    # Verify tenant exists
    tenant = get_tenant_by_id(tenant_id)
    validate_resource_exists(tenant, "Tenant", tenant_id)
    
    # Update tenant
    updated_tenant = update_tenant(
        tenant_id=tenant_id,
        name=update_data.name,
        is_active=update_data.is_active
    )
    
    # Invalidate cache
    invalidate_cache_keys(cache, [
        "tenants:active=True",
        "tenants:active=False"
    ])
    
    logger.info(f"✅ Updated tenant {tenant_id}")
    return updated_tenant


@router.get("/{tenant_id}/users")
@handle_api_error("fetch tenant users")
async def get_tenant_users(
    tenant_id: int,
    cache = Depends(get_cache_service)
):
    """
    Get all users for a specific tenant (RESTful hierarchy).
    
    Args:
        tenant_id: Tenant identifier
    
    Returns:
        List of user objects belonging to tenant
    
    Cache: 5 minutes TTL
    
    Raises:
        404: Tenant not found
    """
    # Verify tenant exists
    tenant = get_tenant_by_id(tenant_id)
    validate_resource_exists(tenant, "Tenant", tenant_id)
    
    # Fetch users with cache
    return cached_query(
        cache=cache,
        cache_key=f"tenant:{tenant_id}:users",
        query_func=lambda: get_users_by_tenant(tenant_id),
        ttl_seconds=300
    )
