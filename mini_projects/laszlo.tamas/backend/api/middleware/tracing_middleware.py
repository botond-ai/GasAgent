"""
OpenTelemetry Tracing Middleware

Integrates distributed tracing with request context.

Responsibilities:
1. Extract trace context from incoming HTTP headers (W3C Trace Context)
2. Start a new span for each HTTP request
3. Store trace_id in ContextVar for correlation
4. Inject trace context into response headers for downstream services

Note: This middleware requires OpenTelemetry SDK to be initialized.
If OTEL is disabled, it gracefully degrades (no-op).
"""

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .request_context import trace_id_ctx_var

# Lazy import OTEL (only if enabled)
try:
    from opentelemetry import trace
    from opentelemetry.propagate import extract, inject
    from opentelemetry.trace import Status, StatusCode
    
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class TracingMiddleware(BaseHTTPMiddleware):
    """
    OpenTelemetry tracing middleware for FastAPI.
    
    Creates a root span for each HTTP request with:
    - http.method
    - http.route
    - http.status_code
    - http.request_id (correlation)
    
    Graceful degradation: If OTEL not initialized, this middleware is a no-op.
    """

    async def dispatch(self, request: Request, call_next):
        # ====================================================================
        # GRACEFUL DEGRADATION (OTEL disabled or not initialized)
        # ====================================================================
        if not OTEL_AVAILABLE:
            # OTEL not installed, skip tracing
            return await call_next(request)
        
        tracer = trace.get_tracer(__name__)
        
        # Check if tracer is initialized (not a no-op tracer)
        if not tracer or tracer.__class__.__name__ == "ProxyTracer":
            # OTEL SDK not initialized, skip tracing
            return await call_next(request)
        
        # ====================================================================
        # 1. EXTRACT TRACE CONTEXT from incoming headers (W3C Trace Context)
        # ====================================================================
        # Extract parent context from headers (traceparent, tracestate)
        parent_context = extract(request.headers)
        
        # ====================================================================
        # 2. START ROOT SPAN for this HTTP request
        # ====================================================================
        span_name = f"{request.method} {request.url.path}"
        
        with tracer.start_as_current_span(
            span_name,
            context=parent_context,
            kind=trace.SpanKind.SERVER,
        ) as span:
            # ================================================================
            # 3. STORE TRACE_ID in ContextVar
            # ================================================================
            span_context = span.get_span_context()
            if span_context.is_valid:
                trace_id_hex = format(span_context.trace_id, "032x")
                trace_id_ctx_var.set(trace_id_hex)
                request.state.trace_id = trace_id_hex
            
            # ================================================================
            # 4. ADD SPAN ATTRIBUTES (HTTP metadata)
            # ================================================================
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.route", request.url.path)
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("http.host", request.url.hostname or "unknown")
            
            # Add request_id from RequestContextMiddleware (if available)
            if hasattr(request.state, "request_id"):
                span.set_attribute("request_id", request.state.request_id)
            
            # ================================================================
            # 5. PROCESS REQUEST
            # ================================================================
            try:
                response: Response = await call_next(request)
                
                # Add response status code
                span.set_attribute("http.status_code", response.status_code)
                
                # Mark span status based on HTTP status code
                if response.status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR, "Server error"))
                elif response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, "Client error"))
                else:
                    span.set_status(Status(StatusCode.OK))
                
                # ============================================================
                # 6. INJECT TRACE CONTEXT into response headers
                # ============================================================
                # This allows downstream services to continue the trace
                inject(response.headers)
                
                return response
            
            except Exception as exc:
                # Record exception in span
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
