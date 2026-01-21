"""Resilience utilities - retry logic with exponential backoff."""

import time
import logging
from functools import wraps
from typing import Callable, TypeVar, Any

from services.exceptions import (
    EmbeddingServiceError,
    QdrantServiceError,
    DatabaseError,
    ServiceError
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_on_transient_error(
    max_retries: int = 3,
    initial_backoff: float = 1.0,
    backoff_multiplier: float = 2.0,
    retryable_exceptions: tuple = (
        EmbeddingServiceError,
        QdrantServiceError,
        DatabaseError
    )
) -> Callable:
    """
    Decorator for retrying functions on transient errors with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_backoff: Initial backoff delay in seconds (default: 1.0)
        backoff_multiplier: Multiplier for exponential backoff (default: 2.0)
        retryable_exceptions: Tuple of exception types to retry on
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_on_transient_error(max_retries=3, initial_backoff=1.0)
        def risky_operation():
            # This will be retried up to 3 times on transient errors
            return api_call()
    
    Behavior:
        - Retry 1: wait 1s
        - Retry 2: wait 2s
        - Retry 3: wait 4s
        - After 3 failures: raise last exception
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            backoff = initial_backoff
            
            for attempt in range(max_retries + 1):  # +1 because first attempt is not a retry
                try:
                    result = func(*args, **kwargs)
                    
                    # Log successful retry (if this was a retry)
                    if attempt > 0:
                        logger.info(
                            f"✅ {func.__name__} succeeded on attempt {attempt + 1}/{max_retries + 1}"
                        )
                    
                    return result
                
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Check if this was the last attempt
                    if attempt == max_retries:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_retries + 1} attempts",
                            extra={
                                "function": func.__name__,
                                "attempts": max_retries + 1,
                                "error_type": type(e).__name__,
                                "error_context": getattr(e, 'context', {}),
                            },
                            exc_info=True
                        )
                        raise  # Re-raise the original exception
                    
                    # Log retry attempt
                    logger.warning(
                        f"⚠️ {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {backoff}s...",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_attempts": max_retries + 1,
                            "backoff_seconds": backoff,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "error_context": getattr(e, 'context', {}),
                        }
                    )
                    
                    # Sleep before retry
                    time.sleep(backoff)
                    
                    # Exponential backoff
                    backoff *= backoff_multiplier
                
                except Exception as e:
                    # Non-retryable exception - fail immediately
                    logger.error(
                        f"❌ {func.__name__} failed with non-retryable error: {type(e).__name__}",
                        extra={
                            "function": func.__name__,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                        exc_info=True
                    )
                    raise
            
            # This should never be reached, but for type safety
            if last_exception:
                raise last_exception
            
            raise RuntimeError(f"{func.__name__} failed with unknown error")
        
        return wrapper
    
    return decorator


def retry_with_config(config_service) -> Callable:
    """
    Create retry decorator with parameters from ConfigService.
    
    Args:
        config_service: ConfigService instance
    
    Returns:
        Configured retry decorator
    
    Example:
        from services.config_service import get_config_service
        config = get_config_service()
        
        @retry_with_config(config)
        def my_function():
            # Retry logic configured from system.ini
            pass
    """
    return retry_on_transient_error(
        max_retries=config_service.get_max_retries(),
        initial_backoff=config_service.get_initial_backoff(),
        backoff_multiplier=config_service.get_backoff_multiplier()
    )
