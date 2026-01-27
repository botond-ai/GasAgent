"""
Custom exceptions for Fleet API client.
Following best practices for exception handling and error reporting.
"""

from typing import Optional, Dict, Any


class FleetAPIException(Exception):
    """Base exception for all Fleet API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(FleetAPIException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class AuthorizationError(FleetAPIException):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(message, status_code=403, **kwargs)


class ResourceNotFoundError(FleetAPIException):
    """Raised when requested resource is not found."""
    
    def __init__(self, resource: str, resource_id: Any = None, **kwargs):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with ID {resource_id} not found"
        super().__init__(message, status_code=404, **kwargs)


class ValidationError(FleetAPIException):
    """Raised when request validation fails."""
    
    def __init__(self, message: str = "Validation failed", **kwargs):
        super().__init__(message, status_code=422, **kwargs)


class RateLimitError(FleetAPIException):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        retry_after: Optional[int] = None,
        message: str = "Rate limit exceeded",
        **kwargs
    ):
        self.retry_after = retry_after
        super().__init__(message, status_code=429, **kwargs)


class ServerError(FleetAPIException):
    """Raised when server encounters an error."""
    
    def __init__(self, message: str = "Internal server error", **kwargs):
        super().__init__(message, status_code=500, **kwargs)


class ConfigurationError(FleetAPIException):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: str = "Invalid configuration", **kwargs):
        super().__init__(message, status_code=500, **kwargs)


class NetworkError(FleetAPIException):
    """Raised when network communication fails."""
    
    def __init__(self, message: str = "Network error occurred", **kwargs):
        super().__init__(message, **kwargs)
