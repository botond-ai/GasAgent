"""
Validation Helpers

Reusable validation patterns for API routers.
"""

from typing import Optional, Dict, Any
from .error_handlers import NotFoundError, ForbiddenError


def validate_resource_exists(
    resource: Optional[Dict[str, Any]],
    resource_name: str,
    resource_id: Any
) -> Dict[str, Any]:
    """
    Validate resource exists, raise NotFoundError if not.
    
    Usage:
        tenant = validate_resource_exists(
            get_tenant_by_id(tenant_id),
            "Tenant",
            tenant_id
        )
    
    Args:
        resource: Resource dict or None
        resource_name: Human-readable resource name
        resource_id: Resource identifier
    
    Returns:
        Resource dict
    
    Raises:
        NotFoundError: If resource is None
    """
    if not resource:
        raise NotFoundError(resource_name, resource_id)
    return resource


def validate_ownership(
    resource: Dict[str, Any],
    user_id: int,
    owner_field: str = "user_id",
    error_message: str = "Access denied: You don't own this resource"
) -> None:
    """
    Validate user owns the resource.
    
    Usage:
        validate_ownership(document, user_id)
    
    Args:
        resource: Resource dict
        user_id: Current user ID
        owner_field: Field name containing owner ID (default: "user_id")
        error_message: Custom error message
    
    Raises:
        ForbiddenError: If user doesn't own resource
    """
    if resource.get(owner_field) != user_id:
        raise ForbiddenError(error_message)


def validate_tenant_isolation(
    resource: Dict[str, Any],
    tenant_id: int,
    tenant_field: str = "tenant_id"
) -> None:
    """
    Validate resource belongs to user's tenant.
    
    Usage:
        validate_tenant_isolation(document, tenant_id)
    
    Args:
        resource: Resource dict
        tenant_id: Current tenant ID
        tenant_field: Field name containing tenant ID (default: "tenant_id")
    
    Raises:
        ForbiddenError: If resource belongs to different tenant
    """
    if resource.get(tenant_field) != tenant_id:
        raise ForbiddenError("Access denied: Resource belongs to different tenant")
