"""
Prometheus metrics for KnowledgeRouter monitoring.

Metrics:
- knowledgerouter_requests_total: Counter for total requests by domain and status
- knowledgerouter_latency_seconds: Histogram for request latency
- knowledgerouter_llm_calls_total: Counter for LLM API calls
- knowledgerouter_llm_latency_seconds: Histogram for LLM call latency
- knowledgerouter_llm_tokens_total: Counter for LLM tokens consumed
- knowledgerouter_llm_cost_total: Counter for LLM API cost in USD
- knowledgerouter_cache_hits_total: Counter for cache hits
- knowledgerouter_cache_misses_total: Counter for cache misses
- knowledgerouter_errors_total: Counter for errors by type
- knowledgerouter_tool_executions_total: Counter for tool executions
- knowledgerouter_rag_latency_seconds: Histogram for RAG retrieval latency
- knowledgerouter_active_requests: Gauge for currently active requests
- knowledgerouter_replan_loops_total: Counter for replan loop iterations
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from prometheus_client.core import CollectorRegistry
import logging

logger = logging.getLogger(__name__)

# Create custom registry
metrics_registry = CollectorRegistry()

# Request metrics
requests_total = Counter(
    'knowledgerouter_requests_total',
    'Total number of requests processed',
    ['domain', 'status', 'pipeline_mode'],
    registry=metrics_registry
)

request_latency = Histogram(
    'knowledgerouter_latency_seconds',
    'Request processing latency in seconds',
    ['domain', 'pipeline_mode'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0),
    registry=metrics_registry
)

# LLM metrics
llm_calls_total = Counter(
    'knowledgerouter_llm_calls_total',
    'Total number of LLM API calls',
    ['model', 'status', 'purpose'],
    registry=metrics_registry
)

llm_latency = Histogram(
    'knowledgerouter_llm_latency_seconds',
    'LLM API call latency in seconds',
    ['model', 'purpose'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0),
    registry=metrics_registry
)

llm_tokens_total = Counter(
    'knowledgerouter_llm_tokens_total',
    'Total number of LLM tokens consumed',
    ['model', 'token_type', 'purpose'],
    registry=metrics_registry
)

llm_cost_total = Counter(
    'knowledgerouter_llm_cost_total',
    'Total LLM API cost in USD',
    ['model', 'purpose'],
    registry=metrics_registry
)

# Cache metrics
cache_hits_total = Counter(
    'knowledgerouter_cache_hits_total',
    'Total number of cache hits',
    ['cache_type'],
    registry=metrics_registry
)

cache_misses_total = Counter(
    'knowledgerouter_cache_misses_total',
    'Total number of cache misses',
    ['cache_type'],
    registry=metrics_registry
)

# Error metrics
errors_total = Counter(
    'knowledgerouter_errors_total',
    'Total number of errors',
    ['error_type', 'component'],
    registry=metrics_registry
)

# Tool execution metrics
tool_executions_total = Counter(
    'knowledgerouter_tool_executions_total',
    'Total number of tool executions',
    ['tool_name', 'status'],
    registry=metrics_registry
)

# RAG metrics
rag_latency = Histogram(
    'knowledgerouter_rag_latency_seconds',
    'RAG retrieval latency in seconds',
    ['domain'],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
    registry=metrics_registry
)

# Active requests gauge
active_requests = Gauge(
    'knowledgerouter_active_requests',
    'Number of currently active requests',
    registry=metrics_registry
)

# Replan loop metrics
replan_loops_total = Counter(
    'knowledgerouter_replan_loops_total',
    'Total number of replan loop iterations',
    ['reason', 'domain'],
    registry=metrics_registry
)


# LLM cost configuration (USD per million tokens)
LLM_COST_CONFIG = {
    'gpt-4o': {'input': 2.50, 'output': 10.00},
    'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
    'claude-3-5-sonnet-20241022': {'input': 3.00, 'output': 15.00},
    'claude-3-5-sonnet': {'input': 3.00, 'output': 15.00},
    'o1-preview': {'input': 15.00, 'output': 60.00},
    'o1-mini': {'input': 3.00, 'output': 12.00},
}


class MetricsCollector:
    """Helper class for collecting and recording metrics."""
    
    @staticmethod
    def record_request(domain: str, status: str, pipeline_mode: str, latency_seconds: float):
        """Record a completed request with latency."""
        requests_total.labels(domain=domain, status=status, pipeline_mode=pipeline_mode).inc()
        request_latency.labels(domain=domain, pipeline_mode=pipeline_mode).observe(latency_seconds)
    
    @staticmethod
    def record_llm_call(
        model: str, 
        status: str, 
        purpose: str, 
        latency_seconds: float = None,
        input_tokens: int = 0,
        output_tokens: int = 0
    ):
        """Record an LLM API call with tokens and cost."""
        llm_calls_total.labels(model=model, status=status, purpose=purpose).inc()
        if latency_seconds is not None:
            llm_latency.labels(model=model, purpose=purpose).observe(latency_seconds)
        
        # Record token usage
        if input_tokens > 0:
            llm_tokens_total.labels(model=model, token_type='input', purpose=purpose).inc(input_tokens)
        if output_tokens > 0:
            llm_tokens_total.labels(model=model, token_type='output', purpose=purpose).inc(output_tokens)
        
        # Calculate and record cost
        if status == 'success' and (input_tokens > 0 or output_tokens > 0):
            cost_config = LLM_COST_CONFIG.get(model, {'input': 0.0, 'output': 0.0})
            input_cost = (input_tokens / 1_000_000) * cost_config['input']
            output_cost = (output_tokens / 1_000_000) * cost_config['output']
            total_cost = input_cost + output_cost
            
            if total_cost > 0:
                llm_cost_total.labels(model=model, purpose=purpose).inc(total_cost)
    
    @staticmethod
    def record_cache_hit(cache_type: str):
        """Record a cache hit."""
        cache_hits_total.labels(cache_type=cache_type).inc()
    
    @staticmethod
    def record_cache_miss(cache_type: str):
        """Record a cache miss."""
        cache_misses_total.labels(cache_type=cache_type).inc()
    
    @staticmethod
    def record_error(error_type: str, component: str):
        """Record an error."""
        errors_total.labels(error_type=error_type, component=component).inc()
    
    @staticmethod
    def record_tool_execution(tool_name: str, status: str):
        """Record a tool execution."""
        tool_executions_total.labels(tool_name=tool_name, status=status).inc()
    
    @staticmethod
    def record_rag_latency(domain: str, latency_seconds: float):
        """Record RAG retrieval latency."""
        rag_latency.labels(domain=domain).observe(latency_seconds)
    
    @staticmethod
    def record_replan_loop(reason: str, domain: str):
        """Record a replan loop iteration."""
        replan_loops_total.labels(reason=reason, domain=domain).inc()
    
    @staticmethod
    def increment_active_requests():
        """Increment active requests gauge."""
        active_requests.inc()
    
    @staticmethod
    def decrement_active_requests():
        """Decrement active requests gauge."""
        active_requests.dec()


def get_metrics_output() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest(metrics_registry)
