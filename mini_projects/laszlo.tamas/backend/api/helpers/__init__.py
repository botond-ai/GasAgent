"""
API Helper Utilities

Common patterns and utilities for API routers.
Reduces boilerplate and ensures consistency.
"""

from .error_handlers import handle_api_error, NotFoundError, ForbiddenError
from .cache_helpers import cached_query, invalidate_cache_keys
from .validators import validate_resource_exists, validate_ownership, validate_tenant_isolation

__all__ = [
    # Error handling
    "handle_api_error",
    "NotFoundError",
    "ForbiddenError",
    
    # Cache
    "cached_query",
    "invalidate_cache_keys",
    
    # Validators
    "validate_resource_exists",
    "validate_ownership",
    "validate_tenant_isolation",
]
