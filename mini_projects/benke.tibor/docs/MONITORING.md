# Prometheus & Grafana Monitoring

## Overview

A KnowledgeRouter teljes Prometheus + Grafana monitoring rendszert használ a teljesítmény és működési metrikák nyomon követésére.

## 🎯 Metrikák

### Request Metrics

**knowledgerouter_requests_total** (Counter)
- Total requests processed
- Labels: `domain`, `status`, `pipeline_mode`
- Example: `knowledgerouter_requests_total{domain="it",status="success",pipeline_mode="complex"}`

**knowledgerouter_latency_seconds** (Histogram)
- Request processing latency
- Labels: `domain`, `pipeline_mode`
- Buckets: 0.1s - 120s
- Percentiles: p50, p95, p99

**knowledgerouter_active_requests** (Gauge)
- Currently active requests
- Real-time concurrency monitoring

### LLM Metrics

**knowledgerouter_llm_calls_total** (Counter)
- Total LLM API calls
- Labels: `model`, `status`, `purpose`
- Purpose: intent, plan, observation, generation, memory

**knowledgerouter_llm_latency_seconds** (Histogram)
- LLM API call latency
- Labels: `model`, `purpose`
- Buckets: 0.1s - 30s

**knowledgerouter_llm_tokens_total** (Counter)
- Total LLM tokens consumed
- Labels: `model`, `token_type`, `purpose`
- Token types: input, output

**knowledgerouter_llm_cost_total** (Counter)
- Total LLM API cost in USD
- Labels: `model`, `purpose`
- Tracks cumulative cost based on token usage

**Cost Calculation:**
- GPT-4o: $2.50/M input, $10.00/M output
- GPT-4o-mini: $0.15/M input, $0.60/M output
- Claude 3.5 Sonnet: $3.00/M input, $15.00/M output
- o1-preview: $15.00/M input, $60.00/M output
- o1-mini: $3.00/M input, $12.00/M output

**Average Cost per Request:**
```promql
sum(knowledgerouter_llm_cost_total) / sum(knowledgerouter_requests_total)
```

### Cache Metrics

**knowledgerouter_cache_hits_total** (Counter)
- Total cache hits
- Labels: `cache_type` (embedding, query_result, request_idempotency)

**knowledgerouter_cache_misses_total** (Counter)
- Total cache misses
- Labels: `cache_type`

**Cache Hit Rate Calculation:**
```promql
100 * rate(knowledgerouter_cache_hits_total[5m]) / 
(rate(knowledgerouter_cache_hits_total[5m]) + rate(knowledgerouter_cache_misses_total[5m]))
```

### Error Metrics

**knowledgerouter_errors_total** (Counter)
- Total errors by type
- Labels: `error_type`, `component`
- Error types: llm_error, rag_error, tool_error, validation_error

### Tool & RAG Metrics

**knowledgerouter_tool_executions_total** (Counter)
- Tool execution count
- Labels: `tool_name`, `status`

**knowledgerouter_rag_latency_seconds** (Histogram)
- RAG retrieval latency
- Labels: `domain`
- Buckets: 0.05s - 5s

**knowledgerouter_replan_loops_total** (Counter)
- Replan loop iterations
- Labels: `reason`, `domain`

## 🚀 Quick Start

### 1. Start Services

```bash
docker-compose up -d backend prometheus grafana
```

**Ports:**
- Backend: http://localhost:8001
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

### 2. Verify Metrics Endpoint

```bash
curl http://localhost:8001/api/metrics/
```

**Expected Output:**
```
# HELP knowledgerouter_requests_total Total number of requests processed
# TYPE knowledgerouter_requests_total counter
knowledgerouter_requests_total{domain="it",status="success",pipeline_mode="complex"} 42.0
...
```

### 3. Access Grafana Dashboard

1. Open http://localhost:3001
2. Login: `admin` / `admin`
3. Go to **Dashboards** → **KnowledgeRouter Monitoring**

## 📊 Dashboard Panels

### Request Metrics
- **Request Rate (req/s)**: Requests per second by domain and status
- **Request Latency (p50, p95, p99)**: Latency percentiles
- **Active Requests**: Real-time concurrent requests

### LLM Metrics
- **LLM Call Rate**: LLM API calls per second by model
- **LLM Latency (p95)**: 95th percentile LLM call latency
- **Total LLM Cost (USD)**: Cumulative API cost across all models
- **Cost per Request (USD)**: Average cost per request
- **LLM Cost Over Time**: Cost rate by model and purpose

### Cache Performance
- **Cache Hit Rate (%)**: Cache efficiency by type
  - Embedding cache
  - Query result cache
  - Request idempotency cache

### Error & Reliability
- **Error Rate**: Errors per second by type
- **Tool Execution Rate**: Tool usage frequency

### Advanced Metrics
- **RAG Retrieval Latency (p95)**: Vector search performance
- **Replan Loop Frequency**: Workflow replanning iterations

## 📈 Key Queries

### Latency Monitoring

**p95 latency by domain:**
```promql
histogram_quantile(0.95, 
  rate(knowledgerouter_latency_seconds_bucket{domain="it"}[5m]))
```

**Average latency by pipeline mode:**
```promql
rate(knowledgerouter_latency_seconds_sum[5m]) / 
rate(knowledgerouter_latency_seconds_count[5m])
```

### Performance Analysis

**LLM calls per request:**
```promql
rate(knowledgerouter_llm_calls_total[5m]) / 
rate(knowledgerouter_requests_total[5m])
```

**Cache hit rate:**
```promql
100 * (
  rate(knowledgerouter_cache_hits_total[5m]) / 
  (rate(knowledgerouter_cache_hits_total[5m]) + 
   rate(knowledgerouter_cache_misses_total[5m]))
)
```

### Error Rate

**Error percentage:**
```promql
100 * (
  rate(knowledgerouter_requests_total{status="error"}[5m]) /
  rate(knowledgerouter_requests_total[5m])
)
```

## 🔧 Configuration

### Prometheus (prometheus.yml)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'knowledgerouter'
    scrape_interval: 15s
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/api/metrics/'
```

### Grafana Datasource (grafana/provisioning/datasources/prometheus.yml)

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

### Dashboard Provisioning (grafana/provisioning/dashboards/dashboard.yml)

```yaml
apiVersion: 1

providers:
  - name: 'KnowledgeRouter'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

## 🧪 Testing Metrics

### Generate Load

```bash
# Simple pipeline (15-20 sec)
for i in {1..10}; do
  curl -X POST http://localhost:8001/api/query/ \
    -H "Content-Type: application/json" \
    -d '{"user_id":"test","session_id":"load_test","query":"Mi a VPN beállítás?"}' &
done

# Complex pipeline (30-50 sec)
export USE_SIMPLE_PIPELINE=False
docker-compose restart backend

for i in {1..5}; do
  curl -X POST http://localhost:8001/api/query/ \
    -H "Content-Type: application/json" \
    -d '{"user_id":"test","session_id":"complex_test","query":"Hogyan készítsek Jira ticketet?"}' &
done
```

### Verify Metrics

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Query specific metric
curl 'http://localhost:9090/api/v1/query?query=knowledgerouter_requests_total'

# Grafana API
curl -u admin:admin http://localhost:3001/api/dashboards/home
```

## 📌 Production Recommendations

### Retention

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

storage:
  tsdb:
    retention.time: 30d  # Keep 30 days of metrics
    retention.size: 10GB  # Max 10GB storage
```

### Alerting

Create `prometheus-alerts.yml`:

```yaml
groups:
  - name: knowledgerouter_alerts
    rules:
      - alert: HighErrorRate
        expr: |
          100 * (
            rate(knowledgerouter_requests_total{status="error"}[5m]) /
            rate(knowledgerouter_requests_total[5m])
          ) > 5
        for: 5m
        annotations:
          summary: "High error rate (>5%) detected"
          
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95, 
            rate(knowledgerouter_latency_seconds_bucket[5m])) > 60
        for: 10m
        annotations:
          summary: "p95 latency > 60s for 10 minutes"
          
      - alert: LowCacheHitRate
        expr: |
          100 * (
            rate(knowledgerouter_cache_hits_total[5m]) /
            (rate(knowledgerouter_cache_hits_total[5m]) + 
             rate(knowledgerouter_cache_misses_total[5m]))
          ) < 40
        for: 15m
        annotations:
          summary: "Cache hit rate < 40% for 15 minutes"
```

### Security

```yaml
# grafana environment in docker-compose.yml
environment:
  - GF_SECURITY_ADMIN_USER=${GRAFANA_ADMIN_USER:-admin}
  - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-changeme}
  - GF_AUTH_ANONYMOUS_ENABLED=false
  - GF_AUTH_DISABLE_LOGIN_FORM=false
```

## 🔍 Troubleshooting

### Metrics Not Showing

1. **Check backend health:**
   ```bash
   docker logs knowledgerouter_backend | grep metrics
   ```

2. **Verify Prometheus scraping:**
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

3. **Test metrics endpoint:**
   ```bash
   curl http://localhost:8001/api/metrics/ | head -20
   ```

### Grafana Dashboard Empty

1. **Check Prometheus datasource:**
   - Grafana UI → Configuration → Data Sources → Prometheus
   - Test connection

2. **Verify dashboard queries:**
   - Edit panel → Query inspector
   - Check for PromQL syntax errors

3. **Generate test metrics:**
   ```bash
   curl -X POST http://localhost:8001/api/query/ \
     -H "Content-Type: application/json" \
     -d '{"user_id":"test","session_id":"test","query":"test"}'
   ```

### High Cardinality Warning

If you see "too many time series" warnings:

1. **Reduce label cardinality:**
   - Avoid high-cardinality labels (user_id, session_id in metric labels)
   - Use aggregations in queries

2. **Increase Prometheus memory:**
   ```yaml
   # docker-compose.yml
   prometheus:
     deploy:
       resources:
         limits:
           memory: 2G
   ```

## 📚 Resources

- **Prometheus Documentation**: https://prometheus.io/docs/
- **Grafana Documentation**: https://grafana.com/docs/
- **PromQL Guide**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Grafana Dashboards**: https://grafana.com/grafana/dashboards/

---

**Version:** 2.10.0  
**Last Updated:** 2026-01-21  
**Related:** [FEATURES.md](FEATURES.md), [PIPELINE_MODES.md](PIPELINE_MODES.md)
