"""
Monitoring API Endpoints

Exposes Prometheus metrics endpoint for scraping.

Endpoints:
- GET /metrics - Prometheus metrics in exposition format
"""

import logging
from fastapi import APIRouter, Response

from observability.ai_metrics import get_metrics_text, get_metrics_content_type, METRICS_ENABLED

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])


@router.get("/metrics", include_in_schema=True)
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus exposition format for scraping.
    
    Metrics include:
    - LLM requests, tokens, cost, latency
    - Agent errors, node duration, iterations
    - RAG search duration, relevance scores, cache hits
    - Infrastructure errors, timeouts, retries
    
    Scraped by Prometheus every 15s (configured in monitoring/prometheus/prometheus.yml).
    
    Returns:
        Response with text/plain Prometheus metrics
    """
    if not METRICS_ENABLED:
        return Response(
            content="# Metrics disabled (ENABLE_METRICS=false)\n",
            media_type="text/plain"
        )
    
    try:
        metrics_text = get_metrics_text()
        return Response(
            content=metrics_text,
            media_type=get_metrics_content_type()
        )
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return Response(
            content=f"# Error generating metrics: {e}\n",
            media_type="text/plain",
            status_code=500
        )
