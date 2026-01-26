"""
FastAPI Exception Middleware - Centralized exception handling for Knowledge Router PROD.

Maps ServiceError hierarchy to consistent HTTP responses.
Production-ready error handling with logging and context preservation.
Based on KA Chat enterprise-grade exception handling architecture.
"""

import logging
from typing import Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from services.exceptions import (
    ServiceError,
    ValidationError,
    AuthorizationError,
    ConfigurationError,
    DatabaseError,
    QdrantServiceError,
    EmbeddingServiceError,
    WorkflowError,
    DocumentServiceError,
    CacheServiceError
)
from api.helpers.error_handlers import NotFoundError

logger = logging.getLogger(__name__)


def register_exception_handlers(app):
    """
    Register all exception handlers with FastAPI app.
    
    Usage in main.py:
        from api.exception_middleware import register_exception_handlers
        register_exception_handlers(app)
    """
    
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """Handle validation errors (400 Bad Request)."""
        logger.warning(
            "Validation error",
            extra={
                "error_type": "ValidationError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "ValidationError",
                "message": str(exc),
                "context": exc.context,
                "detail": "A kérés validációja sikertelen" if "hu" in request.headers.get("accept-language", "").lower() else "Request validation failed"
            }
        )
    
    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(request: Request, exc: NotFoundError):
        """Handle resource not found errors (404 Not Found)."""
        logger.info(
            "Resource not found",
            extra={
                "error_type": "NotFoundError",
                "resource": exc.resource,
                "resource_id": exc.resource_id,
                "path": request.url.path,
                "method": request.method
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "NotFoundError",
                "message": str(exc),
                "detail": f"{exc.resource} nem található" if "hu" in request.headers.get("accept-language", "").lower() else f"{exc.resource} not found"
            }
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(request: Request, exc: AuthorizationError):
        """Handle authorization errors (403 Forbidden)."""
        logger.warning(
            "Authorization error",
            extra={
                "error_type": "AuthorizationError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "AuthorizationError",
                "message": str(exc),
                "context": exc.context,
                "detail": "Nincs hozzáférési jogosultság" if "hu" in request.headers.get("accept-language", "").lower() else "Access denied"
            }
        )

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(request: Request, exc: ConfigurationError):
        """Handle configuration errors (500 Internal Server Error)."""
        logger.error(
            "Configuration error",
            extra={
                "error_type": "ConfigurationError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "ConfigurationError",
                "message": "Configuration error occurred",  # Don't expose internal details
                "detail": "Konfigurációs hiba" if "hu" in request.headers.get("accept-language", "").lower() else "System configuration error"
            }
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        """Handle database errors (503 Service Unavailable)."""
        logger.error(
            "Database error",
            extra={
                "error_type": "DatabaseError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "DatabaseError",
                "message": "Database connection error",  # Don't expose internal details
                "detail": "Adatbázis hiba, próbáld újra később" if "hu" in request.headers.get("accept-language", "").lower() else "Database error, please try again later"
            }
        )

    @app.exception_handler(QdrantServiceError)
    async def qdrant_error_handler(request: Request, exc: QdrantServiceError):
        """Handle Qdrant service errors (503 Service Unavailable)."""
        logger.error(
            "Qdrant service error",
            extra={
                "error_type": "QdrantServiceError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "QdrantServiceError",
                "message": "Vector database error",  # Don't expose internal details
                "detail": "Keresési szolgáltatás hiba, próbáld újra" if "hu" in request.headers.get("accept-language", "").lower() else "Search service error, please try again"
            }
        )

    @app.exception_handler(EmbeddingServiceError)
    async def embedding_error_handler(request: Request, exc: EmbeddingServiceError):
        """Handle embedding service errors (503 Service Unavailable)."""
        logger.error(
            "Embedding service error",
            extra={
                "error_type": "EmbeddingServiceError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "EmbeddingServiceError",
                "message": "AI embedding service error",  # Don't expose internal details
                "detail": "AI szolgáltatás hiba, próbáld újra" if "hu" in request.headers.get("accept-language", "").lower() else "AI service error, please try again"
            }
        )

    @app.exception_handler(WorkflowError)
    async def workflow_error_handler(request: Request, exc: WorkflowError):
        """Handle workflow errors (500 Internal Server Error)."""
        logger.error(
            "Workflow error",
            extra={
                "error_type": "WorkflowError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "WorkflowError",
                "message": "Workflow execution error",  # Don't expose internal details
                "detail": "Workflow végrehajtási hiba" if "hu" in request.headers.get("accept-language", "").lower() else "Workflow execution error"
            }
        )

    @app.exception_handler(DocumentServiceError)
    async def document_error_handler(request: Request, exc: DocumentServiceError):
        """Handle document service errors (500 Internal Server Error)."""
        logger.error(
            "Document service error",
            extra={
                "error_type": "DocumentServiceError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "DocumentServiceError",
                "message": "Document processing error",  # Don't expose internal details
                "detail": "Dokumentum feldolgozási hiba" if "hu" in request.headers.get("accept-language", "").lower() else "Document processing error"
            }
        )

    @app.exception_handler(CacheServiceError)
    async def cache_error_handler(request: Request, exc: CacheServiceError):
        """Handle cache service errors (500 Internal Server Error)."""
        logger.error(
            "Cache service error",
            extra={
                "error_type": "CacheServiceError",
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "CacheServiceError",
                "message": "Cache operation error",  # Don't expose internal details
                "detail": "Cache művelet hiba" if "hu" in request.headers.get("accept-language", "").lower() else "Cache operation error"
            }
        )

    @app.exception_handler(ServiceError)
    async def generic_service_error_handler(request: Request, exc: ServiceError):
        """
        Generic handler for all ServiceError subclasses not caught above.
        This is a catch-all for any new ServiceError types.
        """
        logger.error(
            "Service error",
            extra={
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                "context": exc.context,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": exc.__class__.__name__,
                "message": "Service error occurred",  # Don't expose internal details
                "detail": "Szolgáltatás hiba" if "hu" in request.headers.get("accept-language", "").lower() else "Service error"
            }
        )

    logger.info("✅ Exception handlers registered successfully")