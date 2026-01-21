"""
Error Handling Helpers

Standardized error handling patterns for API routers.
Uses ServiceError hierarchy for consistent error handling.
Production-ready implementation with context preservation.
"""

import logging
from typing import Any, Callable, TypeVar
from functools import wraps
from services.exceptions import (
    ServiceError,
    ValidationError,
    AuthorizationError,
    DatabaseError,
    DocumentServiceError,
    WorkflowError
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class NotFoundError(ServiceError):
    """Raise when resource not found - maps to 404 Not Found."""
    def __init__(self, resource: str, resource_id: Any):
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(
            f"{resource} {resource_id} not found",
            context={
                "resource": resource,
                "resource_id": resource_id,
                "operation": "resource_lookup"
            }
        )


class ForbiddenError(AuthorizationError):
    """Raise when access is forbidden - maps to AuthorizationError (403)."""
    def __init__(self, message: str = "Access denied", context: dict = None):
        super().__init__(
            message,
            context=context or {"operation": "access_check"}
        )


def handle_api_error(
    operation: str,
    resource: str = None,
    context: dict = None
):
    """
    Decorator to handle common API errors using ServiceError hierarchy.
    
    Automatically maps exceptions to appropriate ServiceError types:
    - NotFoundError -> ValidationError (400) 
    - ForbiddenError -> AuthorizationError (403)
    - Database exceptions -> DatabaseError (503)
    - Other exceptions -> WorkflowError (500)
    
    Usage:
        @handle_api_error("fetch user", "user", {"tenant_id": 1})
        async def get_user(user_id: int):
            # raises NotFoundError if not found -> ValidationError
            # raises ForbiddenError if access denied -> AuthorizationError
            # other exceptions -> WorkflowError
    
    Args:
        operation: Description of operation (e.g., "fetch user")
        resource: Resource name (e.g., "user", "tenant") 
        context: Additional context for error logging
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            
            except (NotFoundError, ForbiddenError):
                # Already ServiceError types, re-raise as-is
                raise
                
            except ServiceError:
                # Already a ServiceError, re-raise as-is
                raise
            
            except Exception as e:
                # Map generic exceptions to ServiceError types
                error_context = {
                    "operation": operation,
                    "resource": resource,
                    "error_type": type(e).__name__,
                    **(context or {})
                }
                
                # Check if it's a database-related error
                if "database" in str(e).lower() or "connection" in str(e).lower():
                    logger.error(f"Database error during {operation}: {e}", exc_info=True)
                    raise DatabaseError(
                        f"Database error during {operation}",
                        context=error_context
                    )
                
                # Check if it's a document-related error
                if resource and "document" in resource.lower():
                    logger.error(f"Document service error during {operation}: {e}", exc_info=True)
                    raise DocumentServiceError(
                        f"Document processing error during {operation}",
                        context=error_context
                    )
                
                # Default to WorkflowError for other exceptions
                logger.error(f"Workflow error during {operation}: {e}", exc_info=True)
                raise WorkflowError(
                    f"Error during {operation}",
                    context=error_context
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            
            except (NotFoundError, ForbiddenError):
                # Already ServiceError types, re-raise as-is
                raise
                
            except ServiceError:
                # Already a ServiceError, re-raise as-is
                raise
            
            except Exception as e:
                # Map generic exceptions to ServiceError types
                error_context = {
                    "operation": operation,
                    "resource": resource,
                    "error_type": type(e).__name__,
                    **(context or {})
                }
                
                # Check if it's a database-related error
                if "database" in str(e).lower() or "connection" in str(e).lower():
                    logger.error(f"Database error during {operation}: {e}", exc_info=True)
                    raise DatabaseError(
                        f"Database error during {operation}",
                        context=error_context
                    )
                
                # Check if it's a document-related error
                if resource and "document" in resource.lower():
                    logger.error(f"Document service error during {operation}: {e}", exc_info=True)
                    raise DocumentServiceError(
                        f"Document processing error during {operation}",
                        context=error_context
                    )
                
                # Default to WorkflowError for other exceptions
                logger.error(f"Workflow error during {operation}: {e}", exc_info=True)
                raise WorkflowError(
                    f"Error during {operation}",
                    context=error_context
                )
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
