# Tempo Tracing - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A Tempo distributed tracing rendszer nyomon követi a kérések útját a teljes mikroszolgáltatás architektúrán keresztül. End-to-end request tracking, performance bottleneck identification és service dependency mapping.

## Használat

### Trace keresés Grafana-ban
```
# Trace ID alapú keresés
TraceID: abc123def456

# Service alapú keresés  
service.name = "knowledge-router" AND status = "error"

# Duration alapú keresés
duration > 2s AND service.name = "knowledge-router"

# Multi-tenant trace filtering
tenant.id = "1" AND operation = "chat_workflow"
```

### Trace analysis patterns
- **Chat request flow**: API → Workflow → LLM → Database → Response
- **Document processing**: Upload → Parsing → Chunking → Embedding → Storage
- **Memory operations**: Search → Retrieval → Context building → Storage

### Performance debugging
```
# Slow traces analysis
duration > 5s | group by service.name | avg(duration)

# Error rate by service
status = "error" | group by service.name | rate()
```

## Technikai implementáció

### OpenTelemetry Setup
```python
from opentelemetry import trace, baggage
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

def setup_tracing():
    """Configure OpenTelemetry tracing for Knowledge Router."""
    
    # Resource information
    resource = Resource.create({
        "service.name": "knowledge-router",
        "service.version": "1.0.0",
        "deployment.environment": "development"
    })
    
    # Trace provider
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer = trace.get_tracer(__name__)
    
    # OTLP exporter to Tempo
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://tempo:4317",
        insecure=True
    )
    
    # Batch span processor
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
    # Auto-instrumentation
    FastAPIInstrumentor.instrument()
    SQLAlchemyInstrumentor.instrument()
    RequestsInstrumentor.instrument()
    
    return tracer

tracer = setup_tracing()
```

### Workflow Tracing Integration
```python
from opentelemetry import trace
from typing import Dict, Any

class TracedWorkflowNode:
    """Workflow node with distributed tracing."""
    
    def __init__(self, node_name: str):
        self.node_name = node_name
        self.tracer = trace.get_tracer(__name__)
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute node with tracing."""
        
        with self.tracer.start_as_current_span(f"workflow.{self.node_name}") as span:
            # Add span attributes
            span.set_attribute("workflow.node.name", self.node_name)
            span.set_attribute("workflow.tenant.id", str(state.get('tenant_id')))
            span.set_attribute("workflow.user.id", str(state.get('user_id', '')))
            span.set_attribute("workflow.session.id", state.get('session_id', ''))
            
            # Add baggage for downstream services
            baggage.set_baggage("tenant.id", str(state.get('tenant_id')))
            baggage.set_baggage("user.id", str(state.get('user_id', '')))
            
            try:
                result_state = await self._execute_node_logic(state)
                
                # Record success metrics
                span.set_attribute("workflow.status", "success")
                span.set_attribute("workflow.output.size", len(str(result_state)))
                span.set_status(trace.Status(trace.StatusCode.OK))
                
                return result_state
                
            except Exception as e:
                # Record error information
                span.set_attribute("workflow.status", "error")
                span.set_attribute("workflow.error.type", type(e).__name__)
                span.set_attribute("workflow.error.message", str(e))
                span.set_status(
                    trace.Status(trace.StatusCode.ERROR, str(e))
                )
                
                # Re-raise to maintain error handling
                raise

class TracedReasoningNode(TracedWorkflowNode):
    def __init__(self):
        super().__init__("reasoning")
        
    async def _execute_node_logic(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Reasoning with detailed tracing."""
        
        with self.tracer.start_as_current_span("reasoning.query_analysis") as span:
            span.set_attribute("reasoning.query.length", len(state['query']))
            span.set_attribute("reasoning.has_context", bool(state.get('chat_history')))
            
            # LLM call tracing
            with self.tracer.start_as_current_span("reasoning.llm_call") as llm_span:
                llm_span.set_attribute("llm.provider", "openai")
                llm_span.set_attribute("llm.model", "gpt-4")
                
                reasoning_result = await self.llm.analyze_query(state['query'])
                
                llm_span.set_attribute("llm.response.intent", reasoning_result.intent)
                llm_span.set_attribute("llm.response.confidence", reasoning_result.confidence)
                llm_span.set_attribute("llm.tokens.input", reasoning_result.tokens_used.input)
                llm_span.set_attribute("llm.tokens.output", reasoning_result.tokens_used.output)
        
        return {**state, "reasoning": reasoning_result}
```

### Database Tracing
```python
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy import create_engine, event
from opentelemetry import trace

class TracedDatabaseService:
    """Database service with query tracing."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.tracer = trace.get_tracer(__name__)
        
        # Auto-instrument SQLAlchemy
        SQLAlchemyInstrumentor().instrument(engine=self.engine)
        
        # Custom query event listeners
        event.listen(self.engine, "before_cursor_execute", self._before_execute)
        event.listen(self.engine, "after_cursor_execute", self._after_execute)
        
    def _before_execute(self, conn, cursor, statement, parameters, context, executemany):
        """Add custom attributes before query execution."""
        span = trace.get_current_span()
        if span:
            span.set_attribute("db.operation.type", statement.split()[0].upper())
            span.set_attribute("db.statement.length", len(statement))
            if parameters:
                span.set_attribute("db.parameters.count", len(parameters))
                
    def _after_execute(self, conn, cursor, statement, parameters, context, executemany):
        """Add custom attributes after query execution.""" 
        span = trace.get_current_span()
        if span and hasattr(cursor, 'rowcount'):
            span.set_attribute("db.rows.affected", cursor.rowcount)

    async def get_long_term_memories(
        self, 
        tenant_id: int, 
        user_id: int,
        limit: int = 10
    ):
        """Get memories with tracing."""
        
        with self.tracer.start_as_current_span("database.get_memories") as span:
            span.set_attribute("db.operation", "select")
            span.set_attribute("db.table", "long_term_memories") 
            span.set_attribute("db.tenant_id", str(tenant_id))
            span.set_attribute("db.user_id", str(user_id))
            span.set_attribute("db.limit", limit)
            
            # Execute query - SQLAlchemy instrumentation handles the rest
            query = """
                SELECT * FROM long_term_memories 
                WHERE tenant_id = %s AND user_id = %s
                ORDER BY created_at DESC LIMIT %s
            """
            
            result = await self.execute_query(query, (tenant_id, user_id, limit))
            
            span.set_attribute("db.results.count", len(result))
            return result
```

### Vector Store Tracing
```python
from qdrant_client import QdrantClient
from opentelemetry import trace

class TracedQdrantService:
    """Qdrant service with distributed tracing."""
    
    def __init__(self, qdrant_url: str):
        self.client = QdrantClient(url=qdrant_url)
        self.tracer = trace.get_tracer(__name__)
        
    async def search_documents(
        self,
        query_vector: List[float],
        tenant_id: int,
        collection_name: str,
        limit: int = 5
    ):
        """Search with detailed tracing."""
        
        with self.tracer.start_as_current_span("vector_store.search") as span:
            span.set_attribute("vector_store.provider", "qdrant")
            span.set_attribute("vector_store.collection", collection_name)
            span.set_attribute("vector_store.tenant_id", str(tenant_id))
            span.set_attribute("vector_store.query.dimensions", len(query_vector))
            span.set_attribute("vector_store.search.limit", limit)
            
            try:
                search_result = await self.client.search(
                    collection_name=f"{collection_name}_tenant_{tenant_id}",
                    query_vector=query_vector,
                    limit=limit,
                    with_payload=True
                )
                
                span.set_attribute("vector_store.results.count", len(search_result))
                if search_result:
                    span.set_attribute("vector_store.results.top_score", search_result[0].score)
                    span.set_attribute("vector_store.results.min_score", search_result[-1].score)
                
                return search_result
                
            except Exception as e:
                span.set_attribute("vector_store.error", str(e))
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
```

## Docker Compose Configuration

### Tempo Service Setup
```yaml
# docker-compose.yml - Tempo service
version: '3.8'

services:
  tempo:
    image: grafana/tempo:latest
    container_name: knowledge-router-tempo
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./monitoring/tempo/tempo.yaml:/etc/tempo.yaml
      - tempo-storage:/tmp/tempo
    ports:
      - "3200:3200"   # HTTP
      - "4317:4317"   # OTLP gRPC receiver
      - "4318:4318"   # OTLP HTTP receiver
    networks:
      - monitoring

  # OTEL Collector for trace processing
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    container_name: knowledge-router-otel-collector
    command: ["--config=/etc/otelcol-contrib/otel-collector.yml"]
    volumes:
      - ./monitoring/otel/otel-collector.yml:/etc/otelcol-contrib/otel-collector.yml
    ports:
      - "4317:4317"   # OTLP gRPC receiver
      - "4318:4318"   # OTLP HTTP receiver
      - "8889:8889"   # Prometheus metrics
    depends_on:
      - tempo
    networks:
      - monitoring

volumes:
  tempo-storage:

networks:
  monitoring:
    driver: bridge
```

### Tempo Configuration
```yaml
# monitoring/tempo/tempo.yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

ingester:
  trace_idle_period: 10s
  max_block_bytes: 1_000_000
  max_block_duration: 5m

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/traces
    wal:
      path: /tmp/tempo/wal
    pool:
      max_workers: 100
      queue_depth: 10000

querier:
  frontend_worker:
    frontend_address: tempo:9095

query_frontend:
  search:
    duration_slo: 5s
    throughput_bytes_slo: 1.073741824e+09
  trace_by_id:
    duration_slo: 5s
```

## Funkció-specifikus konfiguráció

```ini
# Tracing settings
TRACING_ENABLED=true
TEMPO_ENDPOINT=http://tempo:4317
TRACE_SAMPLE_RATE=1.0

# OpenTelemetry settings
OTEL_SERVICE_NAME=knowledge-router
OTEL_SERVICE_VERSION=1.0.0
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=development

# Trace export
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

### Health Check for Tracing
```python
@app.get("/health/tracing")
async def tracing_health():
    """Health check for distributed tracing."""
    
    with tracer.start_as_current_span("health_check.tracing") as span:
        span.set_attribute("health_check.component", "tracing")
        
        try:
            # Test trace export
            span.add_event("health_check_executed")
            
            return {
                "status": "healthy",
                "tempo_endpoint": "http://tempo:4317",
                "tracing_enabled": True,
                "sample_rate": 1.0
            }
            
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            return {
                "status": "unhealthy",
                "error": str(e)
            }
```