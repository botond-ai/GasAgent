# AI Metrics Monitoring Module

## Overview

The AI Metrics Monitoring module provides comprehensive tracking and reporting of AI API usage metrics across the Homework.04 application. It follows SOLID principles to ensure maintainability, extensibility, and clean architecture.

**Key Metrics Tracked:**
- **Inference Count**: Total number of API calls made
- **Tokens In**: Total input tokens consumed
- **Tokens Out**: Total output tokens generated
- **Cost in USD**: Total cost of API calls based on current OpenAI pricing
- **Latency p95**: 95th percentile of request latency
- **Latency p50/p99**: Median and mean latencies

## Architecture

### SOLID Principles

The metrics module strictly adheres to SOLID design principles:

**S - Single Responsibility**
- `APICallMetric`: Only holds metric data
- `OpenAIPricingCalculator`: Only calculates costs
- `InMemoryMetricsCollector`: Only manages in-memory metric storage
- `MetricsMiddleware`: Only records calls to collectors

**O - Open/Closed**
- Easy to add new metric types without modifying existing code
- New collector implementations can be added without changing the interface

**L - Liskov Substitution**
- All collectors implement `MetricCollector` interface
- Can be swapped without breaking application logic

**I - Interface Segregation**
- Focused interfaces with minimal methods
- `MetricCollector` has only essential methods

**D - Dependency Inversion**
- Services depend on `MetricCollector` abstraction, not concrete implementations
- `MetricsMiddleware` depends on abstraction

### Core Components

#### 1. `APICallMetric` (Dataclass)
Represents a single API call metric.

```python
@dataclass
class APICallMetric:
    timestamp: datetime
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    operation_type: str  # "embedding" or "llm_completion"
    success: bool = True
    error_message: Optional[str] = None
```

#### 2. `MetricCollector` (Abstract Base Class)
Interface for all metric collection strategies.

```python
class MetricCollector(ABC):
    @abstractmethod
    def record_call(self, metric: APICallMetric) -> None:
        """Record a single API call metric."""
    
    @abstractmethod
    def get_summary(self) -> MetricsSummary:
        """Return aggregated metrics summary."""
    
    @abstractmethod
    def reset(self) -> None:
        """Clear all collected metrics."""
    
    @abstractmethod
    def export(self, filepath: str) -> None:
        """Export metrics to a file."""
    
    @abstractmethod
    def load(self, filepath: str) -> None:
        """Load metrics from a file."""
```

#### 3. `InMemoryMetricsCollector` (Implementation)
Concrete implementation using in-memory storage.

**Features:**
- Stores all metrics in memory for fast access
- Calculates aggregations on-demand
- Supports percentile calculations (p95, p50, mean)
- Aggregates by operation type and model
- Export/import via JSON

**Aggregation Methods:**
- `get_summary()`: Total and per-model/operation statistics
- `_aggregate_by_field()`: Group metrics by any field
- `_calculate_percentile()`: Compute percentiles efficiently

#### 4. `OpenAIPricingCalculator` (Static Methods)
Calculates costs based on current OpenAI pricing.

**Supported Models:**

*Embedding Models:*
- `text-embedding-3-small`: $0.02 per 1M tokens
- `text-embedding-3-large`: $0.13 per 1M tokens

*LLM Models:*
- `gpt-4o-mini`: $0.15 in / $0.60 out per 1M tokens
- `gpt-4o`: $2.5 in / $10.0 out per 1M tokens
- `gpt-4-turbo`: $10.0 in / $30.0 out per 1M tokens
- `gpt-3.5-turbo`: $0.50 in / $1.50 out per 1M tokens

**Pricing Update:**
To update for new models or pricing changes:

```python
# Update in OpenAIPricingCalculator class
LLM_PRICES = {
    "new-model": {"input": X.XX, "output": Y.YY},
    ...
}
```

#### 5. `MetricsMiddleware` (Wrapper)
Convenience class for recording metrics with automatic cost calculation.

```python
class MetricsMiddleware:
    def record_embedding_call(self, model, tokens_in, latency_ms, ...):
        # Automatically calculates cost and records

    def record_llm_call(self, model, tokens_in, tokens_out, latency_ms, ...):
        # Automatically calculates cost and records
```

#### 6. `MetricsSummary` (Dataclass)
Aggregated metrics data.

```python
@dataclass
class MetricsSummary:
    total_inferences: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    latency_p95_ms: float
    latency_p50_ms: float
    latency_mean_ms: float
    by_operation: Dict[str, Dict]  # Breakdown by operation
    by_model: Dict[str, Dict]      # Breakdown by model
```

## Usage

### 1. Integration in Main Application

In `app/main.py`:

```python
from .metrics import create_metrics_collector

# Initialize metrics collector
metrics_collector = create_metrics_collector()

# Pass to services
emb_service = OpenAIEmbeddingService(
    api_key=cfg.openai_api_key,
    model=cfg.embedding_model,
    metrics_collector=metrics_collector,
)

rag_agent = RAGAgent(
    api_key=cfg.openai_api_key,
    llm_model=cfg.llm_model,
    metrics_collector=metrics_collector,
)

# Pass to CLI
cli = CLI(
    emb_service=emb_service,
    vector_store=vector_store,
    rag_agent=rag_agent,
    metrics_collector=metrics_collector,
)
```

### 2. Integration in Services

In `app/embeddings.py`:

```python
class OpenAIEmbeddingService(EmbeddingService):
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        metrics_collector: Optional[MetricCollector] = None,
    ) -> None:
        self.metrics_middleware = (
            MetricsMiddleware(metrics_collector) if metrics_collector else None
        )

    def get_embedding(self, text: str) -> List[float]:
        start_time = time.time()
        try:
            tokens_in = len(text) // 4  # Estimate
            resp = openai.Embedding.create(model=self.model, input=text)
            embedding = resp["data"][0]["embedding"]
            
            # Record metrics
            if self.metrics_middleware:
                latency_ms = (time.time() - start_time) * 1000
                self.metrics_middleware.record_embedding_call(
                    model=self.model,
                    tokens_in=tokens_in,
                    latency_ms=latency_ms,
                    success=True,
                )
            
            return embedding
        except Exception as exc:
            # Record failed call
            if self.metrics_middleware:
                latency_ms = (time.time() - start_time) * 1000
                self.metrics_middleware.record_embedding_call(
                    model=self.model,
                    tokens_in=tokens_in,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(exc),
                )
            return []
```

### 3. Interactive CLI Commands

In interactive mode, use these commands:

```bash
# View current metrics summary
/metrics

# Export metrics to JSON file
/metrics export

# Produces metrics_export.json with:
{
  "timestamp": "2026-01-25T...",
  "total_calls": 42,
  "calls": [
    {
      "timestamp": "...",
      "model": "text-embedding-3-small",
      "tokens_in": 250,
      "tokens_out": 0,
      "latency_ms": 45.3,
      "cost_usd": 0.0000063,
      "operation_type": "embedding",
      "success": true
    },
    ...
  ],
  "summary": {
    "total_inferences": 42,
    "total_tokens_in": 15234,
    "total_tokens_out": 8567,
    "total_cost_usd": 0.0247,
    "latency_p95_ms": 125.3,
    "latency_p50_ms": 68.5,
    "latency_mean_ms": 72.1,
    "by_operation": {
      "embedding": {...},
      "llm_completion": {...}
    },
    "by_model": {
      "text-embedding-3-small": {...},
      "gpt-4o-mini": {...}
    }
  }
}
```

## Metrics Display

The CLI displays formatted metrics using `_print_metrics_summary()`:

```
--- AI Metrics Summary ---
Total Inferences: 42
Total Tokens In: 15,234
Total Tokens Out: 8,567
Total Cost: $0.024700

Latency Statistics (milliseconds):
  p95: 125.30ms
  p50 (median): 68.50ms
  Mean: 72.10ms

Breakdown by Operation:
  embedding:
    Calls: 32
    Tokens In: 12,500
    Tokens Out: 0
    Cost: $0.000250
    Latency p95: 52.10ms
  
  llm_completion:
    Calls: 10
    Tokens In: 2,734
    Tokens Out: 8,567
    Cost: $0.024450
    Latency p95: 98.50ms

Breakdown by Model:
  text-embedding-3-small:
    Calls: 32
    Cost: $0.000250
    Latency p95: 52.10ms
  
  gpt-4o-mini:
    Calls: 10
    Cost: $0.024450
    Latency p95: 98.50ms
```

## Token Estimation

Current implementation uses rough token estimation:
- **For text**: `tokens ≈ len(text) // 4`

For more accurate token counting, you can integrate OpenAI's `tiktoken`:

```python
import tiktoken

def count_tokens_accurate(text: str, model: str) -> int:
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))
```

Then update services to use accurate counting.

## Cost Calculation Examples

### Embedding Call
```python
# 500 tokens for text-embedding-3-small ($0.02 per 1M)
cost = OpenAIPricingCalculator.calculate_cost(
    tokens_in=500,
    tokens_out=0,
    model="text-embedding-3-small",
    operation_type="embedding",
)
# cost = (500 / 1_000_000) * 0.02 = $0.00001
```

### LLM Call
```python
# 1000 input, 500 output tokens for gpt-4o-mini
cost = OpenAIPricingCalculator.calculate_cost(
    tokens_in=1000,
    tokens_out=500,
    model="gpt-4o-mini",
    operation_type="llm_completion",
)
# cost = (1000/1M * 0.15) + (500/1M * 0.60) = 0.00015 + 0.0003 = $0.00045
```

## Testing

Comprehensive test suite in `tests/test_metrics.py`:

```bash
# Run all metrics tests
pytest tests/test_metrics.py -v

# Run specific test class
pytest tests/test_metrics.py::TestOpenAIPricingCalculator -v

# Run with coverage
pytest tests/test_metrics.py --cov=app.metrics
```

Test coverage includes:
- Metric creation and validation
- Cost calculations for all models
- In-memory collection and aggregation
- Percentile calculations
- JSON export/import
- Middleware recording

## Future Enhancements

### 1. Persistent Storage
```python
class PersistentMetricsCollector(MetricCollector):
    """PostgreSQL/MongoDB backed metrics storage."""
    pass
```

### 2. Real-time Streaming
```python
class StreamingMetricsCollector(MetricCollector):
    """Stream metrics to external monitoring system."""
    pass
```

### 3. Advanced Analytics
- Trend analysis (cost/throughput over time)
- Anomaly detection in latency
- Model comparison dashboards
- Budget forecasting

### 4. Alerts
- Cost threshold alerts
- Latency SLA violations
- Error rate tracking
- API quota monitoring

### 5. Integration
- Datadog/New Relic export
- CloudWatch metrics
- Prometheus scraping endpoint

## Configuration

Currently all metrics tracking is automatic once enabled. Future configuration options:

```python
# .env
METRICS_ENABLED=true
METRICS_EXPORT_PATH=./metrics
METRICS_SAMPLE_RATE=1.0  # Sample 100% of requests
METRICS_BUFFER_SIZE=10000  # In-memory buffer before flush
```

## Troubleshooting

### Metrics Not Showing
1. Verify `metrics_collector` is passed to services
2. Check `OpenAIEmbeddingService` and `RAGAgent` are recording calls
3. Ensure `/metrics` command is used in interactive mode

### Incorrect Costs
1. Verify model names match `OpenAIPricingCalculator` supported models
2. Check pricing is up-to-date with OpenAI's current rates
3. Token estimation may be rough; use `tiktoken` for accuracy

### Performance Issues
1. Percentile calculation uses `statistics.quantiles` - efficient for typical datasets
2. For very large datasets (100K+ metrics), consider persistent storage
3. Use `export` to clear in-memory metrics periodically

## Dependencies

No additional dependencies required beyond existing project requirements. Uses Python standard library:
- `abc` - Abstract base classes
- `dataclasses` - Data structures
- `datetime` - Timestamps
- `json` - Export/import
- `logging` - Debug logging
- `statistics` - Percentile calculations
- `time` - Latency measurement

## License

Part of ai-agents-hu project.
