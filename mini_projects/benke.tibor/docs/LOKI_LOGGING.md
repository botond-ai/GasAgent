# Loki Logging Stack

**Version:** v2.12.0  
**Last Updated:** 2026-01-23  
**Stack:** Loki + Promtail + Grafana

---

## 🎯 Overview

A KnowledgeRouter **structured logging** megoldást használ **Grafana Loki**-val:
- **Loki**: Log aggregation (Prometheus for logs)
- **Promtail**: Log shipper (scrapes logs, pushes to Loki)
- **Grafana**: Visualization + LogQL queries
- **Structured JSON**: Context-rich logging (user_id, session_id, node, domain, latency)curl http://localhost:3100/ready
# → "ready" (egyszerű szöveg, ha fut)

curl http://localhost:3100/metrics
# → Prometheus metrikák (nem ember-olvasható)

---

## 🚀 Quick Start

### 1. Start Loki Stack

```bash
# Start all services (including Loki + Promtail)
docker-compose up -d

# Verify Loki is running
curl http://localhost:3100/ready

# Verify Promtail is scraping
curl http://localhost:9080/metrics | grep promtail_targets_active_total
```

### 2. Access Grafana

```
URL: http://localhost:3001
Username: admin
Password: admin
```

**Navigate to:** Explore → Select "Loki" datasource

### 3. Query Logs

```logql
# All backend logs (FONTOS: container label, nem job!)
{container="knowledgerouter_backend"}

# IT domain logs only
{container="knowledgerouter_backend"} | json | domain="it"

# Generation node logs
{container="knowledgerouter_backend"} | json | node="generation"

# Errors in last 1 hour
{container="knowledgerouter_backend"} | json | level="ERROR"

# User-specific logs
{container="knowledgerouter_backend"} | json | user_id="user123"

# High latency queries (>5 seconds)
{container="knowledgerouter_backend"} | json | latency_ms > 5000
```

**⚠️ FONTOS:** Promtail Docker scraping esetén a label **`container`**, NEM `job`!
- ✅ Helyes: `{container="knowledgerouter_backend"}`
- ❌ Helytelen: `{job="backend"}`

---

## 📊 Log Structure

### Structured JSON Format

```json
{
  "timestamp": "2026-01-23T10:30:45.123456Z",
  "level": "INFO",
  "name": "services.agent",
  "message": "Intent detection completed",
  "module": "agent",
  "function": "_intent_detection_node",
  "line": 318,
  "node": "intent_detection",
  "domain": "it",
  "user_id": "user123",
  "session_id": "session456",
  "latency_ms": 1234.56,
  "tokens": 512,
  "cost": 0.0012
}
```

### Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `timestamp` | ISO8601 | UTC timestamp | `2026-01-23T10:30:45.123456Z` |
| `level` | string | Log level | `INFO`, `WARNING`, `ERROR` |
| `name` | string | Logger name | `services.agent` |
| `message` | string | Log message | `Intent detection completed` |
| `node` | string | LangGraph node | `intent_detection`, `generation` |
| `domain` | string | Detected domain | `it`, `hr`, `finance` |
| `user_id` | string | User identifier | `user123` |
| `session_id` | string | Session identifier | `session456` |
| `latency_ms` | float | Operation latency | `1234.56` |
| `tokens` | int | LLM tokens used | `512` |
| `cost` | float | LLM cost ($) | `0.0012` |

---

## 🔍 LogQL Queries

### Basic Queries

```logql
# All logs from backend service
{container="knowledgerouter_backend"}

# Logs from last 5 minutes
{container="knowledgerouter_backend"} [5m]

# Filter by log level
{container="knowledgerouter_backend"} | json | level="ERROR"

# Filter by domain
{container="knowledgerouter_backend"} | json | domain="it"

# Filter by node
{container="knowledgerouter_backend"} | json | node="generation"
```

### Advanced Queries

```logql
# Count errors per minute
sum(count_over_time({container="knowledgerouter_backend"} | json | level="ERROR" [1m]))

# Average latency per node
avg_over_time({container="knowledgerouter_backend"} | json | latency_ms [5m]) by (node)

# Top users by query count
topk(10, sum(count_over_time({container="knowledgerouter_backend"} | json [1h])) by (user_id))

# Errors with full context
{container="knowledgerouter_backend"} | json | level="ERROR" | line_format "{{.timestamp}} [{{.node}}] {{.message}} (user={{.user_id}})"

# High latency queries (>10 seconds)
{container="knowledgerouter_backend"} | json | latency_ms > 10000

# Specific user's entire session
{container="knowledgerouter_backend"} | json | session_id="session456"
```

### Filtering & Aggregation

```logql
# Filter by regex
{container="knowledgerouter_backend"} |~ "VPN|network"

# Exclude debug logs
{container="knowledgerouter_backend"} | json | level!="DEBUG"

# Multi-condition filter
{container="knowledgerouter_backend"} | json | domain="it" | level="ERROR" | latency_ms > 5000

# Rate of errors per second
rate({container="knowledgerouter_backend"} | json | level="ERROR" [1m])

# Percentile latency (p95)
quantile_over_time(0.95, {container="knowledgerouter_backend"} | json | latency_ms [5m])
```

---

## 🛠️ Usage in Code

### Setup Structured Logging

```python
# backend/core/settings.py or __init__.py
from infrastructure.structured_logging import setup_structured_logging

# Initialize at app startup
setup_structured_logging(
    log_level="INFO",              # DEBUG, INFO, WARNING, ERROR
    log_file="/var/log/backend/app.log",  # Optional file output
    json_format=True               # JSON for Loki (True in production)
)
```

### Log with Context

```python
import logging
from infrastructure.structured_logging import log_node_execution

logger = logging.getLogger(__name__)

# Method 1: Using extra parameter
logger.info(
    "Query processing completed",
    extra={
        "node": "generation",
        "domain": "it",
        "user_id": "user123",
        "session_id": "session456",
        "latency_ms": 12345.67,
        "tokens": 1234,
        "cost": 0.0123
    }
)

# Method 2: Using convenience function
log_node_execution(
    logger,
    node="generation",
    message="LLM response generated",
    level="INFO",
    domain="it",
    user_id="user123",
    latency_ms=12345.67,
    tokens=1234
)
```

### Context Manager (Auto-enrich)

```python
from infrastructure.structured_logging import LogContext

# All logs within context will include user_id and session_id
with LogContext(user_id="user123", session_id="session456"):
    logger.info("Processing started", extra={"node": "intent_detection"})
    # ... process query ...
    logger.info("Processing completed", extra={"node": "generation"})

# Output:
# {"timestamp": "...", "message": "Processing started", "node": "intent_detection", 
#  "user_id": "user123", "session_id": "session456"}
```

---

## 📈 Grafana Dashboards

### Create Dashboard

1. **Navigate:** Grafana → Dashboards → New Dashboard
2. **Add Panel:** Add visualization
3. **Data Source:** Select "Loki"
4. **Query:** Enter LogQL query

### Example Panels

**Panel 1: Error Rate**
```logql
sum(rate({job="backend"} | json | level="ERROR" [1m]))
```

**Panel 2: Latency by Node**
```logql
avg_over_time({job="backend"} | json | latency_ms [5m]) by (node)
```

**Panel 3: Top Users**
```logql
topk(10, sum(count_over_time({job="backend"} | json [1h])) by (user_id))
```

**Panel 4: Log Volume**
```logql
sum(count_over_time({job="backend"} [5m]))
```

### Pre-configured Dashboards

```bash
# Import dashboard JSON
grafana/provisioning/dashboards/backend-logs.json
```

---

## 🔧 Configuration Files

### loki-config.yml

```yaml
# Storage: Local filesystem (production: use S3, GCS, etc.)
storage:
  filesystem:
    chunks_directory: /loki/chunks
    rules_directory: /loki/rules

# Retention: 30 days (adjust as needed)
limits_config:
  retention_period: 720h  # 30 days
```

### promtail-config.yml

```yaml
# Scrape backend logs
scrape_configs:
  - job_name: backend
    static_configs:
      - targets:
          - localhost
        labels:
          job: backend
          service: knowledgerouter
          __path__: /var/log/backend/*.log
    pipeline_stages:
      - json:
          expressions:
            timestamp: timestamp
            level: level
            node: node
            domain: domain
      - timestamp:
          source: timestamp
          format: RFC3339Nano
      - labels:
          level:
          node:
          domain:
```

---

## 🚨 Alerting

### Prometheus AlertManager Integration

```yaml
# loki-config.yml
ruler:
  alertmanager_url: http://alertmanager:9093

# Alert rules
groups:
  - name: backend_alerts
    interval: 1m
    rules:
      - alert: HighErrorRate
        expr: |
          rate({container="knowledgerouter_backend"} | json | level="ERROR" [1m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"
      
      - alert: HighLatency
        expr: |
          avg_over_time({container="knowledgerouter_backend"} | json | latency_ms [5m]) > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "Average latency is {{ $value }}ms"
```

---

## 🎯 Best Practices

### 1. Use Structured Logging

✅ **Good:**
```python
logger.info("Query processed", extra={"latency_ms": 1234, "user_id": "user123"})
```

❌ **Bad:**
```python
logger.info(f"Query processed in 1234ms for user user123")
```

### 2. Add Context to All Logs

```python
# Always include: node, domain, user_id, session_id
log_node_execution(
    logger,
    node="generation",
    message="Processing completed",
    domain="it",
    user_id=user_id,
    session_id=session_id,
    latency_ms=latency
)
```

### 3. Log Levels

- **DEBUG**: Detailed diagnostic info (disable in production)
- **INFO**: Normal operations (query processing, node execution)
- **WARNING**: Unexpected but recoverable (replan triggered, cache miss)
- **ERROR**: Errors that need attention (LLM failure, timeout)
- **CRITICAL**: System failures (DB connection lost, Qdrant unavailable)

### 4. Avoid Logging Sensitive Data

```python
# ❌ Bad: Logs PII
logger.info(f"User email: {email}")

# ✅ Good: Logs user_id only
logger.info("User authenticated", extra={"user_id": user_id})
```

### 5. Use Labels Wisely

**Good labels** (low cardinality):
- `level` (5 values: DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `node` (~10 values: intent_detection, retrieval, generation)
- `domain` (6 values: it, hr, finance, marketing, legal, general)

**Bad labels** (high cardinality):
- `user_id` (thousands of unique values) → Use as JSON field, not label
- `session_id` (infinite unique values) → Use as JSON field, not label

---

## 📊 Performance & Costs

### Storage Estimates

| Log Volume | Retention | Storage (compressed) |
|------------|-----------|----------------------|
| 1 GB/day | 7 days | ~5 GB |
| 1 GB/day | 30 days | ~20 GB |
| 5 GB/day | 30 days | ~100 GB |

### Query Performance

- **Fast queries** (< 1s): Label filters `{container="knowledgerouter_backend"} | json | level="ERROR"`
- **Slow queries** (> 5s): Full-text search `{container="knowledgerouter_backend"} |~ "search term"`
- **Optimization**: Use labels for filtering, JSON fields for context

---

## 🐛 Troubleshooting

### Loki Not Receiving Logs

```bash
# Check Promtail is running
docker logs knowledgerouter_promtail

# Check Promtail targets
curl http://localhost:9080/metrics | grep promtail_targets_active_total

# Verify Loki is accessible
curl http://localhost:3100/ready
```

### Logs Not Appearing in Grafana

1. **Check datasource:** Grafana → Configuration → Data Sources → Loki
2. **Test connection:** Click "Save & Test"
3. **Verify query:** Explore → Loki → `{container="knowledgerouter_backend"}`
4. **Check time range:** Set to "Last 15 minutes"
5. **Check label:** Loki API: `curl http://localhost:3100/loki/api/v1/label/container/values`

### Grafana Datasource Issues

**Problem:** "Only one datasource per organization can be marked as default" error

**Cause:** Duplicate datasource configs in `grafana/provisioning/datasources/`

**Solution:**
```bash
# Check for duplicate configs
ls grafana/provisioning/datasources/*.yml

# Keep only datasources.yml (remove prometheus.yml if exists)
rm grafana/provisioning/datasources/prometheus.yml

# Restart Grafana
docker-compose restart grafana
```

**Best Practice:** Use single `datasources.yml` file for all datasources:
```yaml
datasources:
  - name: Prometheus
    isDefault: true    # For monitoring dashboards
  - name: Loki
    isDefault: false   # For log queries
```

### High Memory Usage

```yaml
# loki-config.yml - Limit cache size
query_range:
  results_cache:
    cache:
      embedded_cache:
        max_size_mb: 100  # Reduce if memory constrained
```

---

## 📚 Resources

- **Loki Documentation**: https://grafana.com/docs/loki/latest/
- **LogQL Syntax**: https://grafana.com/docs/loki/latest/logql/
- **Promtail**: https://grafana.com/docs/loki/latest/clients/promtail/
- **Grafana Explore**: https://grafana.com/docs/grafana/latest/explore/

---

**Next Steps:**
1. ✅ Start Loki stack: `docker-compose up -d`
2. ✅ Access Grafana: http://localhost:3001
3. ✅ Explore logs: Loki datasource → `{container="knowledgerouter_backend"}`
4. 📊 Create dashboards for monitoring
5. 🚨 Setup alerts for errors & high latency

---

## 🔧 Verified Configuration (2026-01-26)

### ✅ Working Setup

**Loki Query (Grafana Explore):**
```logql
{container="knowledgerouter_backend"}
```

**Datasource Config (`grafana/provisioning/datasources/datasources.yml`):**
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true        # For monitoring dashboards
  
  - name: Loki
    type: loki
    url: http://loki:3100
    isDefault: false       # Use via Explore or manual selection
```

**Promtail Label:** Docker scraping creates `container` label automatically (not `job`).

**Verification:**
```bash
# Check available labels
curl http://localhost:3100/loki/api/v1/label/container/values
# → {"status":"success","data":["knowledgerouter_backend","knowledgerouter_frontend"]}

# Check logs exist
curl -G http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={container="knowledgerouter_backend"}' \
  --data-urlencode 'limit=10'
```
