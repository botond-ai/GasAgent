"""
Request Context Management

Provides ContextVar-based correlation ID propagation across async boundaries.

Usage:
    from api.middleware.request_context import get_request_id, get_trace_id
    
    # Anywhere in the application (even in nested async functions)
    request_id = get_request_id()  # Returns current request's ID
    trace_id = get_trace_id()      # Returns current trace ID from OTEL

Context Variables:
    - request_id: Unique per HTTP request (transient)
    - session_id: Persistent across conversation (from request body)
    - tenant_id: Current tenant ID (from request body)
    - user_id: Current user ID (from request body)
    - trace_id: OpenTelemetry trace ID (hex format)
"""

import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ============================================================================
# CONTEXT VARIABLES (Thread-safe, async-safe)
# ============================================================================

request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
session_id_ctx_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
tenant_id_ctx_var: ContextVar[Optional[int]] = ContextVar("tenant_id", default=None)
user_id_ctx_var: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
trace_id_ctx_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


# ============================================================================
# GETTER FUNCTIONS (Public API)
# ============================================================================

def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_id_ctx_var.get()


def get_session_id() -> Optional[str]:
    """Get current session ID from context."""
    return session_id_ctx_var.get()


def get_tenant_id() -> Optional[int]:
    """Get current tenant ID from context."""
    return tenant_id_ctx_var.get()


def get_user_id() -> Optional[int]:
    """Get current user ID from context."""
    return user_id_ctx_var.get()


def get_trace_id() -> Optional[str]:
    """Get current OpenTelemetry trace ID from context."""
    return trace_id_ctx_var.get()


def set_request_context(
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
    trace_id: Optional[str] = None,
):
    """
    Manually set request context (useful for background tasks, tests).
    
    Args:
        request_id: Unique request identifier
        session_id: Conversation session ID
        tenant_id: Tenant ID
        user_id: User ID
        trace_id: OpenTelemetry trace ID
    """
    if request_id:
        request_id_ctx_var.set(request_id)
    if session_id:
        session_id_ctx_var.set(session_id)
    if tenant_id is not None:
        tenant_id_ctx_var.set(tenant_id)
    if user_id is not None:
        user_id_ctx_var.set(user_id)
    if trace_id:
        trace_id_ctx_var.set(trace_id)


# ============================================================================
# MIDDLEWARE
# ============================================================================

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for request context propagation.
    
    Responsibilities:
    1. Generate or extract request_id from headers (X-Request-ID)
    2. Extract session_id, tenant_id, user_id from request body (if available)
    3. Store correlation IDs in ContextVars
    4. Inject request_id and trace_id into response headers
    
    Note: trace_id is handled by TracingMiddleware (OTEL integration)
    """

    async def dispatch(self, request: Request, call_next):
        # ====================================================================
        # 1. REQUEST ID (Generate or extract from header)
        # ====================================================================
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = f"req-{uuid.uuid4().hex[:12]}"
        
        request_id_ctx_var.set(request_id)
        
        # Store in request state for easy access
        request.state.request_id = request_id
        
        # ====================================================================
        # 2. SESSION/TENANT/USER IDs (from body - extracted later in routes)
        # ====================================================================
        # Note: We cannot parse body here (would consume the stream).
        # These will be set by ChatRequest validation in unified_chat_endpoint.
        # We just ensure the ContextVars exist.
        
        # ====================================================================
        # 3. PROCESS REQUEST
        # ====================================================================
        response: Response = await call_next(request)
        
        # ====================================================================
        # 4. INJECT CORRELATION IDs INTO RESPONSE HEADERS
        # ====================================================================
        response.headers["X-Request-ID"] = request_id
        
        # Add trace_id if available (set by TracingMiddleware)
        trace_id = get_trace_id()
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        
        return response
