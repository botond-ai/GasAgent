"""
OpenTelemetry Tracing Initialization

Sets up the OTEL SDK with OTLP exporter to Tempo.

Usage:
    from observability.tracing import init_tracing, get_tracer
    
    # In main.py (startup)
    init_tracing()
    
    # In any module
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation"):
        # ... do work ...

Environment Variables:
    - ENABLE_TRACES: Enable/disable tracing (default: true)
    - OTEL_SERVICE_NAME: Service name for traces (default: knowledge-router-backend)
    - OTEL_EXPORTER_OTLP_ENDPOINT: Tempo endpoint (default: http://tempo:4317)
    - OTEL_TRACE_SAMPLING_RATIO: Sampling ratio (default: 1.0 for dev, 0.1 for prod)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Global flag to track initialization
_tracing_initialized = False

# Lazy import OTEL (only if enabled)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    
    OTEL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OpenTelemetry packages not installed: {e}. Tracing disabled.")
    OTEL_AVAILABLE = False


def init_tracing():
    """
    Initialize OpenTelemetry tracing with OTLP exporter to Tempo.
    
    Should be called once during application startup (in main.py lifespan).
    
    Graceful degradation: If OTEL not available or disabled, this is a no-op.
    """
    global _tracing_initialized
    
    if _tracing_initialized:
        logger.warning("Tracing already initialized, skipping...")
        return
    
    # Check if tracing enabled
    enable_traces = os.getenv("ENABLE_TRACES", "true").lower() == "true"
    if not enable_traces:
        logger.info("📊 Tracing disabled (ENABLE_TRACES=false)")
        return
    
    if not OTEL_AVAILABLE:
        logger.warning("📊 Tracing disabled (OpenTelemetry packages not installed)")
        return
    
    # ========================================================================
    # 1. CONFIGURE RESOURCE (Service metadata)
    # ========================================================================
    service_name = os.getenv("OTEL_SERVICE_NAME", "knowledge-router-backend")
    service_version = os.getenv("APP_VERSION", "0.0.0")
    
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        "deployment.environment": os.getenv("ENVIRONMENT", "local"),
    })
    
    # ========================================================================
    # 2. CONFIGURE OTLP EXPORTER (Tempo)
    # ========================================================================
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")
    insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
    
    try:
        span_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=insecure,
        )
    except Exception as e:
        logger.error(f"Failed to initialize OTLP exporter: {e}. Tracing disabled.")
        return
    
    # ========================================================================
    # 3. CONFIGURE TRACER PROVIDER
    # ========================================================================
    tracer_provider = TracerProvider(resource=resource)
    
    # Add batch span processor (async export for performance)
    span_processor = BatchSpanProcessor(span_exporter)
    tracer_provider.add_span_processor(span_processor)
    
    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)
    
    # ========================================================================
    # 4. AUTO-INSTRUMENTATION (FastAPI, SQLAlchemy, HTTP clients)
    # ========================================================================
    try:
        # FastAPI auto-instrumentation will be applied to app instance in main.py
        # SQLAlchemy instrumentation (PostgreSQL queries)
        SQLAlchemyInstrumentor().instrument()
        
        # HTTP client instrumentation (httpx for OpenAI, requests for Qdrant)
        HTTPXClientInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        
        logger.info("✅ Auto-instrumentation enabled (SQLAlchemy, HTTPX, Requests)")
    except Exception as e:
        logger.warning(f"Auto-instrumentation failed (non-critical): {e}")
    
    _tracing_initialized = True
    logger.info(f"✅ OpenTelemetry tracing initialized (exporting to {otlp_endpoint})")


def get_tracer(name: str):
    """
    Get a tracer for the given module/component.
    
    Args:
        name: Tracer name (usually __name__ of the calling module)
    
    Returns:
        Tracer instance (no-op if tracing not initialized)
    
    Usage:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("my_operation"):
            # ... do work ...
    """
    if not OTEL_AVAILABLE or not _tracing_initialized:
        # Return no-op tracer (safe to call .start_as_current_span())
        from opentelemetry.trace import NoOpTracerProvider
        return NoOpTracerProvider().get_tracer(name)
    
    return trace.get_tracer(name)


def instrument_fastapi_app(app):
    """
    Apply FastAPI auto-instrumentation to the app instance.
    
    Should be called in main.py after app creation.
    
    Args:
        app: FastAPI application instance
    """
    if not OTEL_AVAILABLE or not _tracing_initialized:
        logger.debug("FastAPI auto-instrumentation skipped (tracing not initialized)")
        return
    
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("✅ FastAPI auto-instrumentation enabled")
    except Exception as e:
        logger.warning(f"FastAPI auto-instrumentation failed (non-critical): {e}")
