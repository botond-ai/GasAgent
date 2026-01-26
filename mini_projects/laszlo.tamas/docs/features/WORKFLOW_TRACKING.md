# Workflow Tracking - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A workflow tracking system nyomon követi az összes LangGraph workflow végrehajtást, node-ok közötti átmeneteket, végrehajtási időket és hibákat. Teljes observability biztosítása érdekében.

## Használat

### Workflow execution tracking
```python
# Workflow indítása tracking-gel
from services.unified_chat_workflow import UnifiedChatWorkflow

workflow = UnifiedChatWorkflow()
result = await workflow.arun({
    "query": "Mi a szabadság szabályzat?",
    "tenant_id": 1,
    "user_id": 1
})

# Automatikus tracking minden node végrehajtásnál
```

### Tracking adatok lekérése
```python
# Workflow execution history
executions = await workflow_tracker.get_executions_by_session(
    session_id="uuid",
    tenant_id=1
)

# Node performance metrics
node_stats = await workflow_tracker.get_node_performance(
    node_name="reasoning_node",
    time_range="24h"
)
```

### UI-ban történő monitoring
```
http://localhost:8000/monitoring/workflows
- Workflow execution history
- Node performance metrics  
- Error rate by node
- Execution time trends
```

## Technikai implementáció

### Database Schema (workflow_executions)
```sql
CREATE TABLE workflow_executions (
    id BIGSERIAL PRIMARY KEY,
    workflow_id UUID NOT NULL,
    parent_workflow_id UUID REFERENCES workflow_executions(workflow_id),
    session_id UUID,
    
    -- Multi-tenant isolation
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    user_id INTEGER REFERENCES users(id),
    
    -- Node tracking
    node_name VARCHAR(100) NOT NULL,
    node_index INTEGER NOT NULL DEFAULT 0,
    
    -- State tracking
    state_before JSONB,
    state_after JSONB,
    
    -- Performance metrics
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms FLOAT,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'running',
    error_message TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Indexes
    INDEX idx_workflow_executions_session (session_id, tenant_id),
    INDEX idx_workflow_executions_node (node_name, tenant_id),
    INDEX idx_workflow_executions_tenant (tenant_id, started_at DESC)
);
```

### Tracking Service Implementation
```python
import asyncio
import copy
from datetime import datetime
from typing import Dict, Any, Optional
from database.repositories.workflow_repository import WorkflowRepository

class WorkflowTracker:
    def __init__(self):
        self.workflow_repo = WorkflowRepository()
        
    async def start_node_execution(
        self, 
        node_name: str, 
        node_index: int,
        state: Dict[str, Any],
        session_id: str,
        tenant_id: int,
        user_id: Optional[int] = None,
        parent_workflow_id: Optional[str] = None
    ) -> str:
        """Start tracking node execution."""
        
        workflow_id = str(uuid.uuid4())
        
        execution_record = {
            'workflow_id': workflow_id,
            'parent_workflow_id': parent_workflow_id,
            'session_id': session_id,
            'tenant_id': tenant_id,
            'user_id': user_id,
            'node_name': node_name,
            'node_index': node_index,
            'state_before': copy.deepcopy(state),
            'started_at': datetime.utcnow(),
            'status': 'running'
        }
        
        await self.workflow_repo.create_execution(execution_record)
        return workflow_id
        
    async def complete_node_execution(
        self,
        workflow_id: str,
        final_state: Dict[str, Any], 
        duration_ms: float,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Complete node execution tracking."""
        
        status = "error" if error_message else "completed"
        
        await self.workflow_repo.update_execution(
            workflow_id=workflow_id,
            updates={
                'state_after': copy.deepcopy(final_state),
                'completed_at': datetime.utcnow(),
                'duration_ms': duration_ms,
                'status': status,
                'error_message': error_message,
                'metadata': metadata or {}
            }
        )
```

### LangGraph Integration
```python
class TrackedWorkflowGraph:
    """LangGraph with integrated workflow tracking."""
    
    def __init__(self):
        self.tracker = WorkflowTracker()
        self.graph = self._build_graph()
        
    def _build_graph(self):
        """Build LangGraph with tracking decorators."""
        
        from langgraph.graph import Graph
        
        graph = Graph()
        
        # Add tracked nodes
        graph.add_node("reasoning", self._tracked_reasoning_node)
        graph.add_node("tool_execution", self._tracked_tool_execution_node) 
        graph.add_node("operational", self._tracked_operational_node)
        graph.add_node("memory_read", self._tracked_memory_read_node)
        graph.add_node("memory_write", self._tracked_memory_write_node)
        
        # Add edges with routing tracking
        graph.add_edge("reasoning", "tool_execution")
        graph.add_conditional_edges(
            "tool_execution", 
            self._tracked_routing_decision,
            {
                "operational": "operational",
                "memory_read": "memory_read", 
                "end": END
            }
        )
        
        return graph
        
    def _tracked_reasoning_node(self, state):
        """Reasoning node with tracking wrapper."""
        return self._track_node_execution(
            "reasoning_node", 
            self._reasoning_node_logic,
            state
        )
        
    async def _track_node_execution(
        self, 
        node_name: str, 
        node_function,
        state: Dict[str, Any]
    ):
        """Generic node execution tracking."""
        
        # Start tracking
        workflow_id = await self.tracker.start_node_execution(
            node_name=node_name,
            node_index=state.get('node_sequence', 0),
            state=state,
            session_id=state['session_id'],
            tenant_id=state['tenant_id'],
            user_id=state.get('user_id')
        )
        
        start_time = time.time()
        error_message = None
        
        try:
            # Execute actual node logic
            result_state = await node_function(state)
            
        except Exception as e:
            error_message = str(e)
            result_state = state  # Return original state on error
            
        finally:
            # Complete tracking
            duration_ms = (time.time() - start_time) * 1000
            
            await self.tracker.complete_node_execution(
                workflow_id=workflow_id,
                final_state=result_state,
                duration_ms=duration_ms,
                error_message=error_message,
                metadata=self._extract_execution_metadata(result_state)
            )
            
        return result_state
```

## Funkció-specifikus konfiguráció

```ini
# Workflow tracking
ENABLE_WORKFLOW_TRACKING=true
TRACK_STATE_SNAPSHOTS=true
TRACK_EXECUTION_METRICS=true

# Performance settings
MAX_TRACKED_EXECUTIONS_PER_SESSION=1000
EXECUTION_HISTORY_RETENTION_DAYS=30

# Monitoring
ENABLE_WORKFLOW_MONITORING_UI=true
MONITORING_UPDATE_INTERVAL_SECONDS=5
```

### Performance Monitoring
```python
async def get_workflow_performance_metrics(
    tenant_id: int,
    time_range: str = "24h"
) -> Dict[str, Any]:
    """Get workflow performance metrics."""
    
    metrics = await workflow_repo.get_performance_metrics(
        tenant_id=tenant_id,
        time_range=time_range
    )
    
    return {
        "total_executions": metrics["total_count"],
        "avg_duration_ms": metrics["avg_duration"],
        "error_rate": metrics["error_rate"],
        "nodes_by_performance": metrics["node_stats"],
        "execution_trends": metrics["time_series"]
    }
```