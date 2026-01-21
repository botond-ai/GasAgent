"""
Observability Module

Provides instrumentation for metrics, logging, and distributed tracing.

Components:
- tracing.py: OpenTelemetry SDK initialization
- instrumented_llm.py: LLM call span instrumentation
- structured_logger.py: JSON logging with correlation IDs
- loki_handler.py: Loki log shipper
- ai_metrics.py: Prometheus metrics for AI workloads
- cost_tracker.py: LLM cost calculation
"""

# Tracing imports (lazy-loaded, safe if OTEL not installed)
try:
    from .tracing import init_tracing, get_tracer, instrument_fastapi_app
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    def init_tracing(): pass
    def get_tracer(name): 
        from opentelemetry.trace import NoOpTracerProvider
        return NoOpTracerProvider().get_tracer(name)
    def instrument_fastapi_app(app): pass

__all__ = [
    "init_tracing",
    "get_tracer",
    "instrument_fastapi_app",
    "TRACING_AVAILABLE",
]
