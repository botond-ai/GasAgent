"""
Custom exception classes for Knowledge Router PROD.

Provides typed exceptions with context for better error handling and debugging.
Based on KA Chat exception architecture for enterprise-grade error management.
"""


class ServiceError(Exception):
    """Base exception for all service-layer errors."""
    
    def __init__(self, message: str, context: dict = None):
        """
        Initialize service error with message and optional context.
        
        Args:
            message: Human-readable error description
            context: Additional context (user_id, tenant_id, operation, etc.)
        """
        super().__init__(message)
        self.context = context or {}
    
    def __str__(self):
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{super().__str__()} [Context: {ctx_str}]"
        return super().__str__()


class ValidationError(ServiceError):
    """Raised when request validation fails (400 Bad Request)."""
    pass


class AuthorizationError(ServiceError):
    """Raised when authorization/permissions fail (403 Forbidden)."""
    pass


class ConfigurationError(ServiceError):
    """Raised when system configuration is invalid (500 Internal Server Error)."""
    pass


class DatabaseError(ServiceError):
    """Raised when database operations fail (503 Service Unavailable)."""
    pass


class QdrantServiceError(ServiceError):
    """Raised when Qdrant vector database operations fail (503 Service Unavailable)."""
    pass


# Legacy alias for backward compatibility
QdrantError = QdrantServiceError


class EmbeddingServiceError(ServiceError):
    """Raised when embedding generation fails (503 Service Unavailable)."""
    pass


class WorkflowError(ServiceError):
    """Raised when LangGraph workflow execution fails (500 Internal Server Error)."""
    pass


class DocumentServiceError(ServiceError):
    """Raised when document operations fail (500 Internal Server Error)."""
    pass


class CacheServiceError(ServiceError):
    """Raised when cache operations fail (500 Internal Server Error)."""
    pass