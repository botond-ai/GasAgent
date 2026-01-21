# Grafana Dashboard - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A Grafana dashboard-ok vizualizálják a Prometheus metrikákat. Real-time monitoring, alerting és teljesítmény trend analysis a Knowledge Router rendszerhez.

## Használat

### Dashboard elérése
```
URL: http://localhost:3000
User: admin
Password: admin

Main Dashboard: "Knowledge Router - System Overview"
Tenant Dashboard: "Knowledge Router - Tenant Analysis"
```

### Key dashboard panels
- **Chat Response Times**: P50, P95, P99 latency
- **Workflow Execution**: Success rate, error trends
- **Database Health**: Connection pool, query performance  
- **Vector Search**: Qdrant response times, accuracy metrics
- **Multi-tenant Overview**: Per-tenant resource usage

### Alerting setup
```yaml
# Alert: High chat response time
- alert: ChatResponseTimeSlow
  expr: histogram_quantile(0.95, chat_response_duration_seconds) > 5.0
  for: 2m
  annotations:
    summary: "Chat responses are slow (>5s P95)"
```

## Technikai implementáció

### Dashboard Provisioning
```json
{
  "dashboard": {
    "id": null,
    "title": "Knowledge Router - System Overview",
    "tags": ["knowledge-router"],
    "timezone": "UTC",
    "panels": [
      {
        "id": 1,
        "title": "Chat Request Rate",
        "type": "graph", 
        "targets": [
          {
            "expr": "rate(chat_requests_total[5m])",
            "legendFormat": "Requests/sec"
          }
        ],
        "yAxes": [
          {
            "label": "Requests/sec",
            "min": 0
          }
        ]
      },
      {
        "id": 2,
        "title": "Workflow Success Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(workflow_executions_total{status=\"success\"}[5m]) / rate(workflow_executions_total[5m]) * 100",
            "legendFormat": "Success Rate %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "steps": [
                {"color": "red", "value": 0},
                {"color": "yellow", "value": 95},  
                {"color": "green", "value": 99}
              ]
            }
          }
        }
      }
    ]
  }
}
```

### Multi-Tenant Monitoring
```json
{
  "id": 10,
  "title": "Per-Tenant Performance",
  "type": "table",
  "targets": [
    {
      "expr": "sum(rate(chat_requests_total[5m])) by (tenant_id)",
      "format": "table",
      "legendFormat": "{{tenant_id}}"
    },
    {
      "expr": "histogram_quantile(0.95, sum(rate(chat_response_duration_seconds_bucket[5m])) by (tenant_id, le))",
      "format": "table"
    }
  ],
  "transformations": [
    {
      "id": "merge",
      "options": {}
    },
    {
      "id": "organize",
      "options": {
        "excludeByName": {},
        "indexByName": {},
        "renameByName": {
          "tenant_id": "Tenant ID",
          "Value #A": "Requests/sec", 
          "Value #B": "P95 Response Time (s)"
        }
      }
    }
  ]
}
```

### Database Performance Panel
```json
{
  "id": 20,
  "title": "Database Performance",
  "type": "row",
  "collapsed": false,
  "panels": [
    {
      "id": 21,
      "title": "Active Connections",
      "type": "graph",
      "targets": [
        {
          "expr": "database_connections_active",
          "legendFormat": "Active Connections"
        },
        {
          "expr": "database_connections_pool_size", 
          "legendFormat": "Pool Size"
        }
      ],
      "alert": {
        "conditions": [
          {
            "evaluator": {
              "params": [80],
              "type": "gt"
            },
            "operator": {
              "type": "and"
            },
            "query": {
              "params": ["A", "5m", "now"]
            },
            "reducer": {
              "params": [],
              "type": "last"
            },
            "type": "query"
          }
        ],
        "executionErrorState": "alerting",
        "for": "5m",
        "frequency": "10s",
        "handler": 1,
        "name": "High Database Connections",
        "noDataState": "no_data",
        "notifications": []
      }
    }
  ]
}
```

### Workflow Execution Analysis
```json
{
  "id": 30,
  "title": "Workflow Node Performance",
  "type": "heatmap",
  "targets": [
    {
      "expr": "sum(rate(workflow_duration_seconds_bucket[5m])) by (node_name, le)",
      "format": "heatmap",
      "legendFormat": "{{node_name}}"
    }
  ],
  "heatmap": {
    "xAxis": {
      "show": true
    },
    "yAxis": {
      "show": true,
      "min": "auto",
      "max": "auto"
    }
  },
  "tooltip": {
    "show": true,
    "showHistogram": true
  }
}
```

### Vector Store Monitoring
```json
{
  "id": 40,
  "title": "Qdrant Search Performance",
  "type": "graph",
  "targets": [
    {
      "expr": "histogram_quantile(0.50, rate(qdrant_search_duration_seconds_bucket[5m]))",
      "legendFormat": "P50 Search Time"
    },
    {
      "expr": "histogram_quantile(0.95, rate(qdrant_search_duration_seconds_bucket[5m]))",
      "legendFormat": "P95 Search Time"
    },
    {
      "expr": "rate(qdrant_searches_total{status=\"error\"}[5m])",
      "legendFormat": "Error Rate"
    }
  ],
  "yAxes": [
    {
      "label": "Search Time (seconds)",
      "logBase": 1,
      "min": 0
    },
    {
      "label": "Errors/sec", 
      "logBase": 1,
      "min": 0
    }
  ]
}
```

## Docker Compose Integration
```yaml
# docker-compose.yml - Grafana service
version: '3.8'

services:
  grafana:
    image: grafana/grafana:latest
    container_name: knowledge-router-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
    depends_on:
      - prometheus
    networks:
      - monitoring

volumes:
  grafana-storage:

networks:
  monitoring:
    driver: bridge
```

### Dashboard Provisioning Configuration
```yaml
# monitoring/grafana/provisioning/dashboards/dashboard.yaml
apiVersion: 1

providers:
  - name: 'knowledge-router'
    orgId: 1
    folder: ''
    folderUid: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

### Data Source Configuration
```yaml
# monitoring/grafana/provisioning/datasources/prometheus.yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      timeInterval: "5s"
```

## Funkció-specifikus konfiguráció

```ini
# Grafana settings
GRAFANA_ENABLED=true
GRAFANA_PORT=3000
GRAFANA_ADMIN_PASSWORD=your_secure_password

# Dashboard provisioning
AUTO_PROVISION_DASHBOARDS=true
DASHBOARD_UPDATE_INTERVAL=10s

# Alerting
ENABLE_GRAFANA_ALERTING=true
ALERT_NOTIFICATION_CHANNELS=slack,email
```

### Alert Rules Configuration
```yaml
# monitoring/grafana/provisioning/alerting/rules.yaml
groups:
  - name: knowledge-router
    interval: 30s
    rules:
      - alert: ChatResponseTimeSlow
        expr: histogram_quantile(0.95, rate(chat_response_duration_seconds_bucket[5m])) > 5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Chat response time is too slow"
          description: "95th percentile response time is {{ $value }}s"
          
      - alert: WorkflowFailureRateHigh
        expr: rate(workflow_executions_total{status="error"}[5m]) / rate(workflow_executions_total[5m]) > 0.1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "High workflow failure rate"
          description: "{{ $value }}% of workflows are failing"
```