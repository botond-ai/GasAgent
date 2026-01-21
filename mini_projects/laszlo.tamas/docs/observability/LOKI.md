# Loki Logging - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A Loki structured logging rendszer gyűjti és indexeli az összes alkalmazás logot. Centralizált log aggregation, keresés és real-time log streaming biztosítása Grafana integrációval.

## Használat

### Log queries Grafana-ban
```
# Chat workflow logs
{job="knowledge-router"} |= "chat_workflow" | json

# Error logs only
{job="knowledge-router"} |~ "ERROR|CRITICAL"

# Specific tenant logs
{job="knowledge-router"} | json | tenant_id="1"

# Database query logs
{job="knowledge-router"} |= "database" | json | duration > 1s
```

### Log level filtering
```
# Production error tracking
{job="knowledge-router", level="ERROR"} 

# Development debugging
{job="knowledge-router", level=~"DEBUG|INFO"}

# Performance monitoring
{job="knowledge-router"} | json | duration > 2000
```

### Live log tailing
```bash
# Docker logs with labels
docker logs -f knowledge-router-backend | grep -E "(ERROR|WARNING)"

# Via Loki API
curl "http://localhost:3100/loki/api/v1/tail?query={job=\"knowledge-router\"}"
```

## Technikai implementáció

### Python Logging Configuration
```python
import logging
import json
import time
from pythonjsonlogger import jsonlogger
from typing import Any, Dict

class KnowledgeRouterFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = time.strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ', 
            time.gmtime(record.created)
        )
        
        # Add severity level
        log_record['severity'] = record.levelname
        
        # Add service info
        log_record['service'] = 'knowledge-router'
        log_record['version'] = '1.0.0'
        
        # Add trace context if available
        if hasattr(record, 'tenant_id'):
            log_record['tenant_id'] = record.tenant_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'session_id'):
            log_record['session_id'] = record.session_id

# Configure structured logging
def setup_logging():
    """Setup structured logging with Loki integration."""
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # JSON formatter for structured logs
    formatter = KnowledgeRouterFormatter(
        '%(timestamp)s %(severity)s %(service)s %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler for local development
    file_handler = logging.FileHandler('/app/logs/application.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# Usage in application code
logger = setup_logging()
```

### Contextual Logging
```python
import logging
import contextvars
from typing import Optional

# Context variables for request tracing
tenant_id_var = contextvars.ContextVar('tenant_id')
user_id_var = contextvars.ContextVar('user_id') 
session_id_var = contextvars.ContextVar('session_id')

class ContextualLogger:
    """Logger that automatically includes context variables."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def _get_context(self) -> Dict[str, Any]:
        """Extract current context for logging."""
        context = {}
        
        try:
            context['tenant_id'] = tenant_id_var.get()
        except LookupError:
            pass
            
        try:
            context['user_id'] = user_id_var.get()
        except LookupError:
            pass
            
        try:
            context['session_id'] = session_id_var.get()
        except LookupError:
            pass
            
        return context
        
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        extra = {**self._get_context(), **kwargs}
        self.logger.info(message, extra=extra)
        
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        extra = {**self._get_context(), **kwargs}
        self.logger.error(message, extra=extra)
        
    def debug(self, message: str, **kwargs):
        """Log debug message with context.""" 
        extra = {**self._get_context(), **kwargs}
        self.logger.debug(message, extra=extra)

# Usage in services
logger = ContextualLogger(__name__)

async def process_chat_query(query: str, tenant_id: int, user_id: int):
    """Example service with contextual logging."""
    
    # Set context
    tenant_id_var.set(tenant_id)
    user_id_var.set(user_id)
    
    logger.info("Starting chat query processing", 
                query_length=len(query))
    
    try:
        result = await workflow.process(query)
        logger.info("Chat query completed successfully",
                   response_length=len(result.final_answer),
                   execution_time_ms=result.execution_time_ms)
        return result
        
    except Exception as e:
        logger.error("Chat query processing failed",
                    error=str(e),
                    error_type=type(e).__name__)
        raise
```

### Workflow Logging Integration
```python
class LoggedWorkflowNode:
    """Base class for workflow nodes with integrated logging."""
    
    def __init__(self, node_name: str):
        self.node_name = node_name
        self.logger = ContextualLogger(f"workflow.{node_name}")
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute node with comprehensive logging."""
        
        start_time = time.time()
        
        self.logger.info(f"Starting {self.node_name} execution",
                        input_state_keys=list(state.keys()))
        
        try:
            result_state = await self._node_logic(state)
            
            execution_time = (time.time() - start_time) * 1000
            
            self.logger.info(f"Completed {self.node_name} execution",
                           execution_time_ms=execution_time,
                           output_state_keys=list(result_state.keys()),
                           state_size_bytes=len(json.dumps(result_state)))
            
            return result_state
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            self.logger.error(f"Failed {self.node_name} execution",
                            execution_time_ms=execution_time,
                            error=str(e),
                            error_type=type(e).__name__,
                            traceback=traceback.format_exc())
            raise
            
    async def _node_logic(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Override this method with actual node logic."""
        raise NotImplementedError

class ReasoningNode(LoggedWorkflowNode):
    def __init__(self):
        super().__init__("reasoning")
        
    async def _node_logic(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.debug("Analyzing user query",
                         query=state.get('query'),
                         previous_context=bool(state.get('chat_history')))
        
        # Reasoning logic here
        reasoning_result = await self.llm.analyze_query(state['query'])
        
        self.logger.debug("Query analysis completed",
                         intent=reasoning_result.intent,
                         confidence=reasoning_result.confidence)
        
        return {**state, "reasoning": reasoning_result}
```

## Docker & Loki Configuration

### Loki Docker Setup
```yaml
# docker-compose.yml - Loki service
version: '3.8'

services:
  loki:
    image: grafana/loki:latest
    container_name: knowledge-router-loki
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - ./monitoring/loki/loki-config.yaml:/etc/loki/local-config.yaml
      - loki-storage:/loki
    networks:
      - monitoring

  promtail:
    image: grafana/promtail:latest
    container_name: knowledge-router-promtail
    volumes:
      - ./monitoring/promtail/promtail-config.yaml:/etc/promtail/config.yml
      - /var/log:/var/log:ro
      - ./logs:/app/logs:ro
    command: -config.file=/etc/promtail/config.yml
    networks:
      - monitoring
    depends_on:
      - loki

volumes:
  loki-storage:

networks:
  monitoring:
    driver: bridge
```

### Loki Configuration
```yaml
# monitoring/loki/loki-config.yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb:
    directory: /loki/index
  filesystem:
    directory: /loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: false
  retention_period: 0s
```

### Promtail Configuration
```yaml
# monitoring/promtail/promtail-config.yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: knowledge-router
    static_configs:
      - targets:
          - localhost
        labels:
          job: knowledge-router
          service: backend
          __path__: /app/logs/*.log
    pipeline_stages:
      - json:
          expressions:
            timestamp: timestamp
            severity: severity
            tenant_id: tenant_id
            user_id: user_id
            session_id: session_id
      - timestamp:
          source: timestamp
          format: "2006-01-02T15:04:05.000000Z"
      - labels:
          severity:
          tenant_id:
          service:
```

## Funkció-specifikus konfiguráció

```ini
# Logging settings
LOG_LEVEL=INFO
STRUCTURED_LOGGING=true
LOG_FILE_PATH=/app/logs/application.log

# Loki integration
LOKI_ENABLED=true
LOKI_URL=http://loki:3100
LOKI_PUSH_TIMEOUT_SECONDS=10

# Log retention
LOG_RETENTION_DAYS=30
MAX_LOG_FILE_SIZE_MB=100
```

### Health Check for Logging
```python
@app.get("/health/logging")
async def logging_health():
    """Health check for logging system."""
    
    try:
        # Test log write
        logger.info("Health check log test")
        
        # Test Loki connectivity
        loki_healthy = await check_loki_health()
        
        return {
            "status": "healthy" if loki_healthy else "degraded",
            "loki_url": "http://loki:3100",
            "log_level": logging.getLogger().level,
            "structured_logging": True
        }
        
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e)
        }
```