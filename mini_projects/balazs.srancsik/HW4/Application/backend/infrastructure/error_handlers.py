"""
Global error handling utilities for the SupportAI application.
Provides centralized exception handling, retry logic, and graceful degradation.
"""
import logging
import traceback
import asyncio
from functools import wraps
from typing import Callable, Any, Optional, Type, Tuple
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import httpx

logger = logging.getLogger(__name__)


# Custom Exception Classes
class SupportAIException(Exception):
    """Base exception for SupportAI application."""
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ToolExecutionError(SupportAIException):
    """Exception raised when a tool fails to execute."""
    def __init__(self, tool_name: str, message: str, details: dict = None):
        super().__init__(
            message=f"Tool '{tool_name}' failed: {message}",
            error_code="TOOL_EXECUTION_ERROR",
            details={"tool_name": tool_name, **(details or {})}
        )
        self.tool_name = tool_name


class ExternalAPIError(SupportAIException):
    """Exception raised when an external API call fails."""
    def __init__(self, api_name: str, message: str, status_code: int = None, details: dict = None):
        super().__init__(
            message=f"External API '{api_name}' error: {message}",
            error_code="EXTERNAL_API_ERROR",
            details={"api_name": api_name, "status_code": status_code, **(details or {})}
        )
        self.api_name = api_name
        self.status_code = status_code


class DatabaseError(SupportAIException):
    """Exception raised for database operations."""
    def __init__(self, operation: str, message: str, details: dict = None):
        super().__init__(
            message=f"Database error during '{operation}': {message}",
            error_code="DATABASE_ERROR",
            details={"operation": operation, **(details or {})}
        )
        self.operation = operation


class ValidationException(SupportAIException):
    """Exception raised for input validation failures."""
    def __init__(self, field: str, message: str, details: dict = None):
        super().__init__(
            message=f"Validation error for '{field}': {message}",
            error_code="VALIDATION_ERROR",
            details={"field": field, **(details or {})}
        )
        self.field = field


class RateLimitError(SupportAIException):
    """Exception raised when rate limit is exceeded."""
    def __init__(self, service: str, retry_after: int = None, details: dict = None):
        super().__init__(
            message=f"Rate limit exceeded for '{service}'",
            error_code="RATE_LIMIT_ERROR",
            details={"service": service, "retry_after": retry_after, **(details or {})}
        )
        self.service = service
        self.retry_after = retry_after


class TimeoutError(SupportAIException):
    """Exception raised when an operation times out."""
    def __init__(self, operation: str, timeout_seconds: float, details: dict = None):
        super().__init__(
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            error_code="TIMEOUT_ERROR",
            details={"operation": operation, "timeout_seconds": timeout_seconds, **(details or {})}
        )
        self.operation = operation
        self.timeout_seconds = timeout_seconds


# Global Exception Handler for FastAPI
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for FastAPI application.
    Catches all unhandled exceptions and returns appropriate JSON responses.
    """
    # Log the full traceback for debugging
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Handle our custom exceptions
    if isinstance(exc, SupportAIException):
        return JSONResponse(
            status_code=500,
            content={
                "error": exc.message,
                "error_code": exc.error_code,
                "details": exc.details
            }
        )
    
    # Handle Pydantic validation errors
    if isinstance(exc, ValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "error_code": "VALIDATION_ERROR",
                "details": exc.errors()
            }
        )
    
    # Handle HTTP exceptions
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_code": "HTTP_ERROR"
            }
        )
    
    # Handle httpx errors (external API calls)
    if isinstance(exc, httpx.HTTPStatusError):
        return JSONResponse(
            status_code=502,
            content={
                "error": f"External service error: {exc.response.status_code}",
                "error_code": "EXTERNAL_SERVICE_ERROR"
            }
        )
    
    if isinstance(exc, httpx.TimeoutException):
        return JSONResponse(
            status_code=504,
            content={
                "error": "External service timeout",
                "error_code": "EXTERNAL_SERVICE_TIMEOUT"
            }
        )
    
    if isinstance(exc, httpx.ConnectError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "Unable to connect to external service",
                "error_code": "EXTERNAL_SERVICE_UNAVAILABLE"
            }
        )
    
    # Generic error response for unknown exceptions
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred",
            "error_code": "INTERNAL_SERVER_ERROR",
            "details": {"type": type(exc).__name__}
        }
    )


# Retry Decorator with Exponential Backoff
def retry_async(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.HTTPStatusError,
        ConnectionError,
        asyncio.TimeoutError
    ),
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)
):
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exception types that should trigger a retry
        retryable_status_codes: HTTP status codes that should trigger a retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Check if it's an HTTP error with a retryable status code
                    if isinstance(e, httpx.HTTPStatusError):
                        if e.response.status_code not in retryable_status_codes:
                            raise
                        
                        # Check for Retry-After header
                        retry_after = e.response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = min(float(retry_after), max_delay)
                            except ValueError:
                                pass
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {delay:.1f}s due to: {type(e).__name__}: {str(e)[:100]}"
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        logger.error(
                            f"All {max_retries} retries exhausted for {func.__name__}: "
                            f"{type(e).__name__}: {str(e)[:200]}"
                        )
                        raise
                except Exception as e:
                    # Non-retryable exception, raise immediately
                    logger.error(f"Non-retryable error in {func.__name__}: {type(e).__name__}: {str(e)[:200]}")
                    raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


# Timeout Decorator
def timeout_async(seconds: float, operation_name: str = None):
    """
    Decorator to add timeout to async functions.
    
    Args:
        seconds: Timeout in seconds
        operation_name: Name of the operation for error messages
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            op_name = operation_name or func.__name__
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(f"Timeout after {seconds}s for operation: {op_name}")
                raise TimeoutError(operation=op_name, timeout_seconds=seconds)
        
        return wrapper
    return decorator


# Safe execution wrapper for tools
async def safe_tool_execute(
    tool_name: str,
    execute_func: Callable,
    *args,
    default_error_message: str = "Tool execution failed",
    **kwargs
) -> dict:
    """
    Safely execute a tool function with comprehensive error handling.
    
    Args:
        tool_name: Name of the tool being executed
        execute_func: The async function to execute
        default_error_message: Default message if error doesn't provide one
        *args, **kwargs: Arguments to pass to the function
    
    Returns:
        Dict with success status and either data or error information
    """
    try:
        result = await execute_func(*args, **kwargs)
        return result
    except httpx.TimeoutException as e:
        logger.error(f"Tool {tool_name} timeout: {e}")
        return {
            "success": False,
            "error": f"Request timed out",
            "error_code": "TIMEOUT",
            "system_message": f"{tool_name} timed out - external service may be slow"
        }
    except httpx.ConnectError as e:
        logger.error(f"Tool {tool_name} connection error: {e}")
        return {
            "success": False,
            "error": "Unable to connect to service",
            "error_code": "CONNECTION_ERROR",
            "system_message": f"{tool_name} failed - service unavailable"
        }
    except httpx.HTTPStatusError as e:
        logger.error(f"Tool {tool_name} HTTP error: {e.response.status_code}")
        return {
            "success": False,
            "error": f"Service returned error: {e.response.status_code}",
            "error_code": "HTTP_ERROR",
            "system_message": f"{tool_name} failed with HTTP {e.response.status_code}"
        }
    except ValidationError as e:
        logger.error(f"Tool {tool_name} validation error: {e}")
        return {
            "success": False,
            "error": "Invalid input parameters",
            "error_code": "VALIDATION_ERROR",
            "system_message": f"{tool_name} received invalid parameters"
        }
    except SupportAIException as e:
        logger.error(f"Tool {tool_name} SupportAI error: {e.message}")
        return {
            "success": False,
            "error": e.message,
            "error_code": e.error_code,
            "system_message": f"{tool_name} failed: {e.message}"
        }
    except Exception as e:
        logger.error(f"Tool {tool_name} unexpected error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e) or default_error_message,
            "error_code": "UNKNOWN_ERROR",
            "system_message": f"{tool_name} failed unexpectedly: {str(e)[:100]}"
        }


# Input validation helpers
def validate_not_empty(value: Any, field_name: str) -> None:
    """Validate that a value is not None or empty."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationException(field_name, "Value cannot be empty")


def validate_string_length(value: str, field_name: str, min_length: int = 0, max_length: int = None) -> None:
    """Validate string length constraints."""
    if not isinstance(value, str):
        raise ValidationException(field_name, "Value must be a string")
    
    if len(value) < min_length:
        raise ValidationException(field_name, f"Value must be at least {min_length} characters")
    
    if max_length and len(value) > max_length:
        raise ValidationException(field_name, f"Value must not exceed {max_length} characters")


def validate_in_list(value: Any, field_name: str, allowed_values: list) -> None:
    """Validate that a value is in a list of allowed values."""
    if value not in allowed_values:
        raise ValidationException(
            field_name, 
            f"Value must be one of: {', '.join(str(v) for v in allowed_values)}"
        )


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and invalid characters."""
    import re
    # Remove path separators and null bytes
    filename = filename.replace('/', '').replace('\\', '').replace('\x00', '')
    # Remove other potentially dangerous characters
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:255 - len(ext) - 1] + '.' + ext if ext else name[:255]
    return filename or 'unnamed'


def sanitize_user_input(text: str, max_length: int = 10000) -> str:
    """Sanitize user input text."""
    if not isinstance(text, str):
        return ""
    # Remove null bytes
    text = text.replace('\x00', '')
    # Limit length
    if len(text) > max_length:
        text = text[:max_length]
    return text.strip()
