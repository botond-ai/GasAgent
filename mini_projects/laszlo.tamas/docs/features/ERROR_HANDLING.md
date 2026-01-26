# Error Handling - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A comprehensive error handling rendszer graceful degradation-t biztosít minden system szinten. User-friendly hibaüzeneteket ad vissza, miközben részletes technical logokat készít debugging-hoz.

## Használat

### Error handling patterns
```python
from services.error_handler import ErrorHandler
from exceptions import WorkflowError, ValidationError

try:
    result = await chat_service.process_query(query, tenant_id, user_id)
except WorkflowError as e:
    # Workflow-specific errors with context
    error_response = ErrorHandler.handle_workflow_error(e, user_context)
    return error_response
except ValidationError as e:
    # Input validation errors
    return ErrorHandler.handle_validation_error(e)
```

## Technikai implementáció

### Error Classification
```python
# Custom exception hierarchy
class KnowledgeRouterError(Exception):
    """Base exception for all Knowledge Router errors."""
    def __init__(self, message: str, error_code: str = None, context: dict = None):
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.context = context or {}
        super().__init__(message)

class WorkflowError(KnowledgeRouterError):
    """Workflow execution errors."""
    pass

class ValidationError(KnowledgeRouterError):
    """Input validation errors."""
    pass

class LLMError(KnowledgeRouterError):
    """LLM API errors."""
    pass

class DatabaseError(KnowledgeRouterError):
    """Database operation errors."""
    pass

class VectorStoreError(KnowledgeRouterError):
    """Qdrant vector store errors."""
    pass

# Error Handler Service
class ErrorHandler:
    @staticmethod
    def handle_workflow_error(
        error: WorkflowError, 
        user_context: UserContext = None
    ) -> dict:
        """Handle workflow execution errors gracefully."""
        
        language = user_context.language if user_context else "en"
        
        user_messages = {
            "hu": "Sajnos hiba történt a kérés feldolgozása során. Kérjük próbálja újra.",
            "en": "An error occurred while processing your request. Please try again."
        }
        
        # Log detailed error for debugging
        log_error(
            "Workflow execution failed",
            error_code=error.error_code,
            message=error.message,
            context=error.context,
            user_id=user_context.user_id if user_context else None,
            tenant_id=user_context.tenant_id if user_context else None
        )
        
        return {
            "success": False,
            "error_code": error.error_code,
            "user_message": user_messages.get(language, user_messages["en"]),
            "retry_suggested": True
        }
    
    @staticmethod 
    def handle_validation_error(error: ValidationError) -> dict:
        """Handle input validation errors."""
        
        return {
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "user_message": f"Invalid input: {error.message}",
            "retry_suggested": False
        }

# Graceful degradation decorator
def graceful_degradation(fallback_response=None):
    """Decorator for graceful error handling with fallback."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_error(f"Function {func.__name__} failed", error=str(e))
                
                if fallback_response:
                    return fallback_response
                else:
                    # Return generic error response
                    return {
                        "success": False,
                        "error": "Service temporarily unavailable",
                        "retry_after": 60
                    }
        return wrapper
    return decorator
```

### Retry Mechanisms
```python
class RetryHandler:
    @staticmethod
    async def retry_with_backoff(
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        exceptions: tuple = (Exception,)
    ):
        """Retry function with exponential backoff."""
        
        for attempt in range(max_retries + 1):
            try:
                return await func()
            except exceptions as e:
                if attempt == max_retries:
                    raise e
                
                delay = initial_delay * (backoff_factor ** attempt)
                log_warning(f"Retry attempt {attempt + 1} after {delay}s delay")
                await asyncio.sleep(delay)

# Usage example
@graceful_degradation(fallback_response="Service temporarily unavailable")
async def generate_embedding(text: str):
    return await RetryHandler.retry_with_backoff(
        lambda: openai_client.embeddings.create(input=text),
        max_retries=3,
        exceptions=(openai.RateLimitError, openai.APIConnectionError)
    )
```

## Funkció-specifikus konfiguráció

```ini
# Error handling
ENABLE_GRACEFUL_DEGRADATION=true
MAX_RETRY_ATTEMPTS=3
RETRY_BACKOFF_FACTOR=2.0
LOG_ALL_ERRORS=true

# User experience
ENABLE_USER_FRIENDLY_ERRORS=true  
DEFAULT_ERROR_LANGUAGE=hu
SUGGEST_RETRY_ON_ERRORS=true
```