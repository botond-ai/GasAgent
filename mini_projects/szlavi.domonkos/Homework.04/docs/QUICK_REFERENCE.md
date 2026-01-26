# Quick Reference: Error Rate & Agent Latency Metrics

## Quick Start

### Recording Errors
```python
from app.metrics import MetricsMiddleware

# When operation succeeds
middleware.record_embedding_call(
    model="text-embedding-3-small",
    tokens_in=100,
    latency_ms=50.0,
    success=True  # Success
)

# When operation fails
middleware.record_embedding_call(
    model="text-embedding-3-small",
    tokens_in=100,
    latency_ms=50.0,
    success=False,  # Failure
    error_message="API rate limit exceeded"
)
```

### Recording Agent Execution
```python
import time

# Measure agent execution time
start_time = time.time()
result = agent.execute(request)
latency_ms = (time.time() - start_time) * 1000

# Record the execution
middleware.record_agent_execution(
    latency_ms=latency_ms,
    success=True,  # or False
    error_message=None  # if failed
)
```

### Viewing Metrics
```python
summary = collector.get_summary()

# Error rate
print(f"Error Rate: {summary.error_rate:.2f}%")
print(f"Total Errors: {summary.total_errors}")

# Agent latency
print(f"Agent p95: {summary.agent_execution_latency_p95_ms:.0f}ms")
print(f"Agent Mean: {summary.agent_execution_latency_mean_ms:.0f}ms")
```

## Key Formulas

### Error Rate
```
Error Rate (%) = (failed_calls / total_calls) × 100
```

Examples:
- 1 failure out of 10 calls = 10%
- 5 failures out of 100 calls = 5%
- 50 failures out of 50 calls = 100%

### Agent Latency Percentiles
```
p95: 95th percentile (95% of calls are faster than this)
p50: 50th percentile / median (middle value)
Mean: Average of all values
```

## MetricsSummary Fields

| Field | Type | Description |
|-------|------|-------------|
| `error_rate` | float | Percentage of failed operations (0-100) |
| `total_errors` | int | Count of failed operations |
| `agent_execution_latency_p95_ms` | float | 95th percentile agent latency |
| `agent_execution_latency_mean_ms` | float | Average agent latency |

## Common Patterns

### Check for Service Degradation
```python
summary = collector.get_summary()

if summary.error_rate > 5.0:
    print("⚠️  Error rate elevated!")
    print(f"  {summary.total_errors} failures out of {summary.total_inferences} calls")
```

### Monitor Agent Performance
```python
summary = collector.get_summary()

if summary.agent_execution_latency_p95_ms > 2000:
    print("⚠️  Agent execution is slow!")
    print(f"  p95 latency: {summary.agent_execution_latency_p95_ms:.0f}ms")
```

### Track by Operation Type
```python
summary = collector.get_summary()

for op_type, stats in summary.by_operation.items():
    print(f"{op_type}: {stats['count']} calls")
    if op_type == "agent_execution":
        print(f"  Mean latency: {stats['latency_mean_ms']:.0f}ms")
```

## Alert Thresholds

**Recommended Alert Thresholds:**

| Metric | Warning | Critical |
|--------|---------|----------|
| Error Rate | > 5% | > 10% |
| Agent p95 Latency | > 2000ms | > 3000ms |
| Embedding Success | < 95% | < 90% |
| LLM Success | < 95% | < 90% |

## CLI Output
```bash
/metrics
```

Shows:
- Error rate and error count
- Agent execution latency p95 and mean
- Breakdown by operation type
- Breakdown by model

## Testing

### Run Tests
```bash
# All tests
pytest tests/test_metrics.py -v

# Only error rate tests
pytest tests/test_metrics.py::TestErrorRateMetrics -v

# Only agent latency tests
pytest tests/test_metrics.py::TestMetricsMiddleware::test_record_agent_execution -v
```

### Test Cases Included
- Error rate: 0%, 100%, mixed scenarios
- Agent latency: single, multiple, failures
- Cross-operation error tracking
- Edge cases and validation

## Backward Compatibility

✅ Existing code continues to work
✅ New fields are optional (but recommended)
✅ Default values: error_rate=0.0, agent_latency=0.0
✅ All original metrics still tracked

## File Locations

| Resource | Path |
|----------|------|
| Implementation | `app/metrics.py` |
| Tests | `tests/test_metrics.py` (29 tests) |
| CLI | `app/cli.py` |
| Documentation | `ERROR_RATE_AND_AGENT_LATENCY_METRICS.md` |
| Guide | `ENHANCEMENT_SUMMARY.md` |

## Support

**For detailed information, see:**
- `ERROR_RATE_AND_AGENT_LATENCY_METRICS.md` - Complete guide
- `ENHANCEMENT_SUMMARY.md` - Implementation summary
- `docs/METRICS.md` - Original metrics documentation

**Questions?**
- Check the troubleshooting section in ERROR_RATE_AND_AGENT_LATENCY_METRICS.md
- Review test cases for usage examples
- Check CLI output with `/metrics` command

---

**Last Updated:** January 25, 2026
**Status:** Production Ready ✅
**Tests:** 29/29 PASSING ✅
