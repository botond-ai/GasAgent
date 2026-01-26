"""
AI-Enhanced Prometheus Metrics

Provides metrics for LLM, RAG, Agent workflows, and infrastructure.

CRITICAL: NO HIGH-CARDINALITY LABELS
- ❌ FORBIDDEN: tenant_id, user_id, request_id, session_id as labels
- ✅ ALLOWED: model, operation, status, error_type, node_name, tool_name

High-cardinality data goes to:
- Structured logs (Loki) - for tenant-level cost tracking
- PostgreSQL workflow_executions - for per-request audit

Metric Categories:
1. LLM Metrics (requests, tokens, cost, latency, fallback)
2. Agent Metrics (errors, node duration, iterations, tools)
3. RAG Metrics (search duration, results, relevance, cache)
4. Infrastructure Metrics (errors, timeouts, retries, SLA)

Usage:
    from observability.ai_metrics import (
        llm_requests_total,
        llm_latency_seconds,
        record_llm_call,
    )
    
    # Record LLM call
    with record_llm_call(model="gpt-4o", operation="chat.completion"):
        response = openai_client.chat.completions.create(...)
    
    # Manual metric update
    llm_requests_total.labels(model="gpt-4o", operation="chat", status="success").inc()
"""

import os
import time
import logging
from contextlib import contextmanager
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from .cost_tracker import calculate_cost

logger = logging.getLogger(__name__)

# Check if metrics enabled
METRICS_ENABLED = os.getenv("ENABLE_METRICS", "true").lower() == "true"

# ============================================================================
# 1. LLM METRICS
# ============================================================================

# Request counter (with status tracking)
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['model', 'operation', 'status']  # operation: chat|embedding|completion, status: success|error|timeout
)

# Token usage counter
llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens consumed',
    ['model', 'direction']  # direction: prompt|completion
)

# Cost tracking (USD)
llm_cost_usd_total = Counter(
    'llm_cost_usd_total',
    'Total LLM cost in USD',
    ['model']
)

# Latency histogram (buckets optimized for LLM calls: 0.5s - 30s)
llm_latency_seconds = Histogram(
    'llm_latency_seconds',
    'LLM API call latency in seconds',
    ['model', 'operation'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
)

# Model fallback tracking
model_fallback_count = Counter(
    'model_fallback_count',
    'Number of model fallbacks triggered',
    ['from_model', 'to_model', 'reason']  # reason: rate_limit|error|timeout
)

# Token usage per request (for loop guard alerts)
token_usage_per_request = Histogram(
    'token_usage_per_request',
    'Token usage per request',
    ['model'],
    buckets=[100, 500, 1000, 2000, 5000, 8000, 10000, 15000, 20000]
)

# Cost per request (endpoint-level aggregation)
cost_per_request_usd = Gauge(
    'cost_per_request_usd',
    'Average cost per request in USD',
    ['endpoint']  # endpoint: /api/chat
)


# ============================================================================
# 2. AGENT METRICS
# ============================================================================

# Error counter (categorized by type and node)
agent_error_count = Counter(
    'agent_error_count',
    'Agent errors by type and node',
    ['error_type', 'node_name', 'severity']  # severity: warning|error|critical
)

# Node execution duration
workflow_node_duration_seconds = Histogram(
    'workflow_node_duration_seconds',
    'LangGraph node execution duration',
    ['node_name'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Iteration tracking (loop detection)
workflow_iterations_total = Counter(
    'workflow_iterations_total',
    'Total agent workflow iterations'
)

# Reflection tracking
workflow_reflections_total = Counter(
    'workflow_reflections_total',
    'Total agent reflections triggered'
)

# Tool invocations
tool_invocations_total = Counter(
    'tool_invocations_total',
    'Tool invocation count',
    ['tool_name', 'status']  # status: success|error
)


# ============================================================================
# 3. RAG PIPELINE METRICS
# ============================================================================

# Qdrant search duration
qdrant_search_duration_seconds = Histogram(
    'qdrant_search_duration_seconds',
    'Qdrant vector search duration',
    ['collection'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
)

# Qdrant search result count
qdrant_search_results_count = Histogram(
    'qdrant_search_results_count',
    'Number of results returned by Qdrant',
    ['collection'],
    buckets=[0, 1, 5, 10, 20, 50, 100]
)

# Embedding generation duration
embedding_generation_duration_seconds = Histogram(
    'embedding_generation_duration_seconds',
    'Embedding generation latency',
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
)

# RAG relevance score (average per search)
rag_retrieved_chunk_relevance_score_avg = Gauge(
    'rag_retrieved_chunk_relevance_score_avg',
    'Average relevance score of retrieved chunks',
    ['collection']
)

# RAG relevance score distribution
rag_retrieved_chunk_relevance_score = Histogram(
    'rag_retrieved_chunk_relevance_score',
    'Relevance score distribution',
    ['collection'],
    buckets=[0.0, 0.3, 0.5, 0.7, 0.85, 0.95, 1.0]
)

# Cache hit/miss tracking
cache_hit_total = Counter(
    'cache_hit_total',
    'Cache hits',
    ['tier', 'resource_type']  # tier: memory|database|qdrant|built, resource_type: prompt|chunks|embeddings
)

cache_miss_total = Counter(
    'cache_miss_total',
    'Cache misses',
    ['tier', 'resource_type']
)


# ============================================================================
# 4. INFRASTRUCTURE METRICS
# ============================================================================

# Generic error counter
errors_total = Counter(
    'errors_total',
    'Total errors by type',
    ['error_type', 'node_name']
)

# Timeout tracking
timeout_total = Counter(
    'timeout_total',
    'Timeouts by service',
    ['service']  # service: openai|qdrant|postgres
)

# Retry tracking
retry_attempts_total = Counter(
    'retry_attempts_total',
    'Retry attempts',
    ['service', 'operation']
)

# SLA violation tracking
sla_violation_total = Counter(
    'sla_violation_total',
    'SLA violations',
    ['metric_type', 'threshold']  # metric_type: latency|error_rate|cost
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

@contextmanager
def record_llm_call(
    model: str,
    operation: str = "chat",
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
):
    """
    Context manager for recording LLM call metrics.
    
    Args:
        model: Model name (e.g., "gpt-4o")
        operation: Operation type ("chat", "embedding", "completion")
        prompt_tokens: Input tokens (optional, can be set after)
        completion_tokens: Output tokens (optional, can be set after)
    
    Usage:
        with record_llm_call(model="gpt-4o", operation="chat") as metrics:
            response = openai_client.chat.completions.create(...)
            metrics.set_tokens(response.usage.prompt_tokens, response.usage.completion_tokens)
    
    Yields:
        Metrics recorder object with .set_tokens() method
    """
    if not METRICS_ENABLED:
        yield None
        return
    
    start_time = time.time()
    status = "success"
    
    class MetricsRecorder:
        def __init__(self):
            self.prompt_tokens = prompt_tokens
            self.completion_tokens = completion_tokens
            self.cached_tokens = 0  # Cache tracking
        
        def set_tokens(self, prompt: int, completion: int = 0, cached: int = 0):
            """Set token counts including cached tokens."""
            self.prompt_tokens = prompt
            self.completion_tokens = completion
            self.cached_tokens = cached
    
    recorder = MetricsRecorder()
    
    try:
        yield recorder
    except Exception as e:
        status = "error"
        logger.error(f"LLM call failed: {e}")
        raise
    finally:
        duration = time.time() - start_time
        
        # Record metrics
        llm_requests_total.labels(model=model, operation=operation, status=status).inc()
        llm_latency_seconds.labels(model=model, operation=operation).observe(duration)
        
        if recorder.prompt_tokens is not None:
            llm_tokens_total.labels(model=model, direction="prompt").inc(recorder.prompt_tokens)
            
            # Record cached tokens separately
            if recorder.cached_tokens > 0:
                llm_tokens_total.labels(model=model, direction="cached").inc(recorder.cached_tokens)
            
            if recorder.completion_tokens is not None:
                llm_tokens_total.labels(model=model, direction="completion").inc(recorder.completion_tokens)
                
                # Calculate and record cost (cache-aware)
                cost = calculate_cost(
                    model, 
                    recorder.prompt_tokens, 
                    recorder.completion_tokens,
                    recorder.cached_tokens
                )
                llm_cost_usd_total.labels(model=model).inc(cost)
                
                # Record token usage per request (for loop guard)
                total_tokens = recorder.prompt_tokens + recorder.completion_tokens
                token_usage_per_request.labels(model=model).observe(total_tokens)


def record_rag_search(
    collection: str,
    duration_seconds: float,
    result_count: int,
    relevance_scores: list[float],
):
    """
    Record RAG search metrics.
    
    Args:
        collection: Qdrant collection name
        duration_seconds: Search duration
        result_count: Number of results
        relevance_scores: List of relevance scores (0.0-1.0)
    """
    if not METRICS_ENABLED:
        return
    
    qdrant_search_duration_seconds.labels(collection=collection).observe(duration_seconds)
    qdrant_search_results_count.labels(collection=collection).observe(result_count)
    
    if relevance_scores:
        avg_score = sum(relevance_scores) / len(relevance_scores)
        rag_retrieved_chunk_relevance_score_avg.labels(collection=collection).set(avg_score)
        
        for score in relevance_scores:
            rag_retrieved_chunk_relevance_score.labels(collection=collection).observe(score)


def get_metrics_text() -> str:
    """
    Generate Prometheus metrics in text format.
    
    Returns:
        Metrics in Prometheus exposition format
    """
    return generate_latest().decode('utf-8')


def get_metrics_content_type() -> str:
    """
    Get Prometheus metrics content type.
    
    Returns:
        Content-Type header value
    """
    return CONTENT_TYPE_LATEST
