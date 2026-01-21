# Prometheus Metrics - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A Prometheus integration gyűjti és exportálja a rendszer összes teljesítmény metrikáját. Real-time monitoring és alerting dashboard-okhoz szükséges adatok biztosítása.

## Használat

### Prometheus scraping beállítás
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'knowledge-router'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 10s
    metrics_path: '/metrics'
```

### Metrikák elérése
```bash
# Raw metrics endpoint
curl http://localhost:8000/metrics

# Key metrics preview
curl http://localhost:8000/metrics | grep -E "(workflow_|chat_|database_)"
```

### Grafana dashboard import
```
Knowledge Router - Main Dashboard
ID: custom-kr-dashboard-001
Metrics: workflow performance, database health, API response times
```

## Technikai implementáció

### Prometheus Metrics Setup
```python
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client.asgi import make_asgi_app
from fastapi import FastAPI

# Initialize metrics
workflow_executions_total = Counter(
    'workflow_executions_total',
    'Total workflow executions',
    ['tenant_id', 'node_name', 'status']
)

workflow_duration_seconds = Histogram(
    'workflow_duration_seconds', 
    'Workflow execution duration',
    ['tenant_id', 'node_name'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')]
)

chat_requests_total = Counter(
    'chat_requests_total',
    'Total chat requests',
    ['tenant_id', 'status']
)

database_connections_active = Gauge(
    'database_connections_active',
    'Active database connections'
)

qdrant_search_duration = Histogram(
    'qdrant_search_duration_seconds',
    'Qdrant search duration',
    ['tenant_id', 'collection'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, float('inf')]
)

system_info = Info(
    'knowledge_router_system',
    'System information'
)

# Set system info
system_info.info({
    'version': '1.0.0',
    'python_version': '3.11',
    'environment': 'development'
})
```

### FastAPI Integration
```python
from fastapi import FastAPI
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.asgi import make_asgi_app

app = FastAPI()

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Middleware for automatic metrics collection
@app.middleware("http")
async def prometheus_middleware(request, call_next):
    """Collect HTTP metrics automatically."""
    
    start_time = time.time()
    
    response = await call_next(request)
    
    # Record HTTP metrics
    http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code
    ).inc()
    
    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(time.time() - start_time)
    
    return response

# Custom metrics in business logic
async def track_workflow_execution(
    tenant_id: int,
    node_name: str,
    duration_seconds: float,
    status: str
):
    """Track workflow execution metrics."""
    
    workflow_executions_total.labels(
        tenant_id=str(tenant_id),
        node_name=node_name,
        status=status
    ).inc()
    
    if status == "success":
        workflow_duration_seconds.labels(
            tenant_id=str(tenant_id),
            node_name=node_name
        ).observe(duration_seconds)
```

### Workflow Metrics Collection
```python
class PrometheusWorkflowTracker:
    """Prometheus-integrated workflow tracker."""
    
    def __init__(self):
        self.metrics = {
            'executions': workflow_executions_total,
            'duration': workflow_duration_seconds,
            'errors': workflow_errors_total,
            'state_size': workflow_state_size_bytes
        }
        
    async def track_node_execution(
        self,
        node_name: str,
        tenant_id: int,
        execution_func,
        state: Dict[str, Any]
    ):
        """Track node execution with Prometheus metrics."""
        
        start_time = time.time()
        status = "success"
        
        try:
            # Execute node
            result = await execution_func(state)
            
            # Track state size
            state_size = len(json.dumps(result).encode('utf-8'))
            self.metrics['state_size'].labels(
                tenant_id=str(tenant_id),
                node_name=node_name
            ).set(state_size)
            
            return result
            
        except Exception as e:
            status = "error"
            raise
            
        finally:
            # Record execution metrics
            duration = time.time() - start_time
            
            self.metrics['executions'].labels(
                tenant_id=str(tenant_id),
                node_name=node_name,
                status=status
            ).inc()
            
            if status == "success":
                self.metrics['duration'].labels(
                    tenant_id=str(tenant_id),
                    node_name=node_name
                ).observe(duration)
```

### Database Metrics
```python
from sqlalchemy.pool import Pool
from sqlalchemy import event

class DatabaseMetricsCollector:
    """PostgreSQL metrics for Prometheus."""
    
    def __init__(self, engine):
        self.engine = engine
        self.setup_connection_metrics()
        
    def setup_connection_metrics(self):
        """Setup database connection metrics."""
        
        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            database_connections_total.labels(
                database="postgresql",
                action="connect"
            ).inc()
            
        @event.listens_for(self.engine, "close") 
        def receive_close(dbapi_connection, connection_record):
            database_connections_total.labels(
                database="postgresql", 
                action="close"
            ).inc()
            
    def collect_pool_metrics(self):
        """Collect connection pool metrics."""
        
        pool = self.engine.pool
        
        database_connections_active.set(pool.checkedout())
        database_connections_pool_size.set(pool.size())
        database_connections_overflow.set(pool.overflow())
```

### Vector Store Metrics
```python
class QdrantMetricsCollector:
    """Qdrant vector store metrics."""
    
    def __init__(self, qdrant_client):
        self.client = qdrant_client
        
    async def track_search(
        self, 
        collection: str,
        tenant_id: int,
        search_func
    ):
        """Track Qdrant search with metrics."""
        
        start_time = time.time()
        
        try:
            result = await search_func()
            
            # Record successful search
            qdrant_searches_total.labels(
                tenant_id=str(tenant_id),
                collection=collection,
                status="success"
            ).inc()
            
            return result
            
        except Exception as e:
            qdrant_searches_total.labels(
                tenant_id=str(tenant_id), 
                collection=collection,
                status="error"
            ).inc()
            raise
            
        finally:
            duration = time.time() - start_time
            qdrant_search_duration.labels(
                tenant_id=str(tenant_id),
                collection=collection
            ).observe(duration)
```

## Funkció-specifikus konfiguráció

```ini
# Prometheus settings
PROMETHEUS_ENABLED=true
PROMETHEUS_ENDPOINT=/metrics
PROMETHEUS_INCLUDE_REQUEST_METRICS=true

# Metrics collection
COLLECT_WORKFLOW_METRICS=true
COLLECT_DATABASE_METRICS=true
COLLECT_VECTOR_STORE_METRICS=true

# Performance
METRICS_COLLECTION_INTERVAL_SECONDS=10
METRICS_RETENTION_SECONDS=3600

# Custom labels
PROMETHEUS_ENVIRONMENT_LABEL=development
PROMETHEUS_INSTANCE_LABEL=knowledge-router-1
```

### Health Check Integration
```python
@app.get("/health/prometheus")
async def prometheus_health():
    """Health check for Prometheus monitoring."""
    
    return {
        "status": "healthy",
        "metrics_endpoint": "/metrics",
        "collectors": [
            "workflow_metrics",
            "database_metrics", 
            "vector_store_metrics",
            "http_metrics"
        ],
        "last_scrape": datetime.utcnow().isoformat()
    }
```