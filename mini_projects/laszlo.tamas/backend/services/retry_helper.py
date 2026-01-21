"""
Retry Helper - Exponential backoff decorator for transient failures.

Production-ready retry logic for external service calls (Qdrant, OpenAI, PostgreSQL).
Prevents instant failures on temporary network issues, rate limits, or service hiccups.
Based on KA Chat implementation with Knowledge Router customizations.

CONFIGURATION:
All retry parameters are configurable via system.ini [resilience] section:
- MAX_RETRIES: Maximum retry attempts (default: 3)
- INITIAL_BACKOFF_SECONDS: Initial delay (default: 1)
- BACKOFF_MULTIPLIER: Exponential multiplier (default: 2.0)
- RATE_LIMIT_MAX_ATTEMPTS: Rate limit retry attempts (default: 5)
- RATE_LIMIT_INITIAL_DELAY: Rate limit initial delay (default: 2)
"""

import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Tuple, Type
from services.exceptions import (
    QdrantServiceError,
    EmbeddingServiceError,
    DatabaseError,
    WorkflowError
)
from services.config_service import get_config_service

logger = logging.getLogger(__name__)

# Type variable for generic function return type
T = TypeVar('T')


def retry_with_backoff(
    max_attempts: int = None,
    base_delay: float = None,
    max_delay: float = None,
    exponential_base: float = None,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        QdrantServiceError,
        EmbeddingServiceError,
        DatabaseError,
        ConnectionError,
        TimeoutError
    )
):
    """
    Decorator that retries a function with exponential backoff on transient failures.
    
    Args:
        max_attempts: Maximum number of attempts (default: from config MAX_RETRIES)
        base_delay: Initial delay in seconds (default: from config INITIAL_BACKOFF_SECONDS)
        max_delay: Maximum delay cap in seconds (default: from config MAX_DELAY_SECONDS)
        exponential_base: Exponential multiplier (default: from config BACKOFF_MULTIPLIER)
        retryable_exceptions: Tuple of exception types to retry on
    
    Configuration:
        Uses system.ini [resilience] section for defaults:
        - MAX_RETRIES=3
        - INITIAL_BACKOFF_SECONDS=1
        - BACKOFF_MULTIPLIER=2.0
        - MAX_DELAY_SECONDS=10
    
    Delay formula: min(base_delay * (exponential_base ** attempt), max_delay)
    Example delays: 1s, 2s, 4s (with config defaults)
    
    Usage:
        @retry_with_backoff()  # Uses config defaults
        def search_qdrant(vector, tenant_id):
            return qdrant_service.search_document_chunks(vector, tenant_id)
    
        @retry_with_backoff(max_attempts=5, base_delay=2.0)  # Override config
        def call_critical_api(data):
            return api.call(data)
    """
    # Load defaults from config if not specified
    config = get_config_service()
    
    if max_attempts is None:
        max_attempts = config.get_max_retries()
    if base_delay is None:
        base_delay = config.get_initial_backoff()
    if max_delay is None:
        max_delay = config.get_max_delay()
    if exponential_base is None:
        exponential_base = config.get_backoff_multiplier()
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # Attempt execution
                    result = func(*args, **kwargs)
                    
                    # Log success after retry
                    if attempt > 1:
                        logger.info(
                            f"✅ Retry successful on attempt {attempt} (config-driven)",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "config_source": "system.ini",
                                "base_delay": base_delay,
                                "multiplier": exponential_base
                            }
                        )
                    
                    return result
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Last attempt - don't retry
                    if attempt == max_attempts:
                        logger.error(
                            f"❌ All {max_attempts} retry attempts failed",
                            extra={
                                "function": func.__name__,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "attempts": max_attempts
                            },
                            exc_info=True
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay
                    )
                    
                    logger.warning(
                        f"⚠️ Retry attempt {attempt}/{max_attempts} failed, waiting {delay:.1f}s",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "delay_seconds": delay,
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                    
                    # Wait before retry
                    time.sleep(delay)
                
                except Exception as e:
                    # Non-retryable exception - fail immediately
                    logger.error(
                        f"❌ Non-retryable exception in {func.__name__}",
                        extra={
                            "function": func.__name__,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "retryable": False
                        },
                        exc_info=True
                    )
                    raise
            
            # Should never reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            
            raise RuntimeError(f"Unexpected retry loop exit in {func.__name__}")
        
        return wrapper
    return decorator


def retry_on_rate_limit(
    max_attempts: int = None,
    base_delay: float = None,
    max_delay: float = None
):
    """
    Specialized retry decorator for API rate limits (e.g., OpenAI).
    
    Uses config-driven longer delays to respect rate limit cooldowns.
    
    Args:
        max_attempts: Maximum number of attempts (default: from config RATE_LIMIT_MAX_ATTEMPTS)
        base_delay: Initial delay in seconds (default: from config RATE_LIMIT_INITIAL_DELAY)
        max_delay: Maximum delay cap in seconds (default: from config RATE_LIMIT_MAX_DELAY)
    
    Configuration:
        Uses system.ini [resilience] section for defaults:
        - RATE_LIMIT_MAX_ATTEMPTS=5
        - RATE_LIMIT_INITIAL_DELAY=2
        - RATE_LIMIT_MAX_DELAY=60
        - RATE_LIMIT_MULTIPLIER=2
    
    Delay sequence: 2s, 4s, 8s, 16s, 32s (with config defaults, capped at 60s)
    
    Usage:
        @retry_on_rate_limit()  # Uses config defaults
        def call_openai_api(messages):
            return llm.invoke(messages)
    """
    # Load defaults from config if not specified
    config = get_config_service()
    
    if max_attempts is None:
        max_attempts = config.get_rate_limit_max_attempts()
    if base_delay is None:
        base_delay = config.get_rate_limit_initial_delay()
    if max_delay is None:
        max_delay = config.get_rate_limit_max_delay()
    
    return retry_with_backoff(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=config.get_rate_limit_multiplier(),
        retryable_exceptions=(
            # OpenAI-specific exceptions
            # Note: These are library-agnostic since OpenAI client versions vary
            Exception,  # Catch all for rate limit errors (library-specific)
        )
    )


def retry_quick(max_attempts: int = None, base_delay: float = None):
    """
    Quick retry for fast-fail operations (e.g., cache lookups).
    
    Args:
        max_attempts: Maximum number of attempts (default: from config QUICK_RETRY_MAX_ATTEMPTS)
        base_delay: Initial delay in seconds (default: from config QUICK_RETRY_INITIAL_DELAY)
    
    Configuration:
        Uses system.ini [resilience] section for defaults:
        - QUICK_RETRY_MAX_ATTEMPTS=2
        - QUICK_RETRY_INITIAL_DELAY=0.5
    
    Delay sequence: 0.5s, 1s (with config defaults)
    
    Usage:
        @retry_quick()  # Uses config defaults
        def get_from_cache(key):
            return cache.get(key)
    """
    # Load defaults from config if not specified
    config = get_config_service()
    
    if max_attempts is None:
        max_attempts = config.get_quick_retry_max_attempts()
    if base_delay is None:
        base_delay = config.get_quick_retry_initial_delay()
    
    return retry_with_backoff(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=2.0,
        exponential_base=2.0
    )