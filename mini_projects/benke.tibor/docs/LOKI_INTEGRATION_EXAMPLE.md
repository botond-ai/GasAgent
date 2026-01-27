# Backend Integration Example - Loki Structured Logging

## BEFORE vs AFTER - Agent.py Changes

### File: `backend/services/agent.py`

**BEFORE (current logging):**
```python
# Line ~316
def _intent_detection_node(self, state: AgentState) -> AgentState:
    logger.info("Intent detection node executing")
    # ... domain detection logic ...
    logger.info(f"Detected domain: {domain} (confidence: {confidence:.3f})")
    return {**state, "domain": domain, "confidence": confidence}
```

**AFTER (structured logging):**
```python
# Add import at top of file
from infrastructure.structured_logging import log_node_execution
import time

# Line ~316
def _intent_detection_node(self, state: AgentState) -> AgentState:
    start_time = time.time()
    
    # ... domain detection logic ...
    
    latency_ms = (time.time() - start_time) * 1000
    
    log_node_execution(
        logger,
        node="intent_detection",
        message="Intent detection completed",
        level="INFO",
        domain=domain,
        confidence=confidence,
        user_id=state.get("user_id", "unknown"),
        session_id=state.get("session_id", "unknown"),
        latency_ms=latency_ms
    )
    
    return {**state, "domain": domain, "confidence": confidence}
```

---

### Generation Node Example

**BEFORE:**
```python
# Line ~959
def _generation_node(self, state: AgentState) -> AgentState:
    logger.info("Generation node executing")
    # ... LLM call ...
    logger.info(f"🤖 LLM generation latency: {latency}ms (domain={domain})")
    return {**state, "llm_response": answer}
```

**AFTER:**
```python
def _generation_node(self, state: AgentState) -> AgentState:
    start_time = time.time()
    domain = state.get("domain", "general")
    user_id = state.get("user_id", "unknown")
    session_id = state.get("session_id", "unknown")
    
    # ... LLM call ...
    # response = await llm.ainvoke(...)
    
    latency_ms = (time.time() - start_time) * 1000
    
    # Extract token usage if available
    tokens = getattr(response, 'usage', {}).get('total_tokens', 0)
    cost = tokens * 0.00001  # Approximate cost calculation
    
    log_node_execution(
        logger,
        node="generation",
        message="LLM response generated",
        level="INFO",
        domain=domain,
        user_id=user_id,
        session_id=session_id,
        latency_ms=latency_ms,
        tokens=tokens,
        cost=cost
    )
    
    return {**state, "llm_response": answer, "tokens": tokens}
```

---

### Error Logging Example

**BEFORE:**
```python
try:
    # ... some operation ...
except Exception as e:
    logger.error(f"Tool execution failed: {e}")
```

**AFTER:**
```python
try:
    # ... some operation ...
except Exception as e:
    log_node_execution(
        logger,
        node="tool_executor",
        message=f"Tool execution failed: {str(e)}",
        level="ERROR",
        domain=state.get("domain"),
        user_id=state.get("user_id"),
        session_id=state.get("session_id"),
        error_type=type(e).__name__
    )
    # Or use logger.error with extra
    logger.error(
        "Tool execution failed",
        extra={
            "node": "tool_executor",
            "domain": state.get("domain"),
            "user_id": state.get("user_id"),
            "error_type": type(e).__name__,
            "error_message": str(e)
        },
        exc_info=True  # Includes stack trace
    )
```

---

## Full Integration Steps

### 1. Import at top of agent.py

```python
# backend/services/agent.py - Line ~1-30

import logging
import time  # ADD THIS
from infrastructure.structured_logging import log_node_execution  # ADD THIS

logger = logging.getLogger(__name__)
```

### 2. Update ALL node methods (11 nodes total)

**Nodes to update:**
1. `_intent_detection_node` (Line ~316)
2. `_plan_node` (Line ~402)
3. `_tool_selection_node` (Line ~495)
4. `_retrieval_node` (Line ~600-650)
5. `_tool_executor_node` (Line ~700-800)
6. `_observation_check_node` (Line ~900)
7. `_generation_node` (Line ~959)
8. `_guardrail_node` (Line ~1050)
9. `_feedback_metrics_node` (Line ~1100)
10. `_workflow_node` (Line ~507)
11. `_memory_update_node` (Line ~214)

**Pattern for each node:**
```python
async def _<node_name>_node(self, state: AgentState) -> AgentState:
    start_time = time.time()
    
    # Get context
    domain = state.get("domain", "general")
    user_id = state.get("user_id", "unknown")
    session_id = state.get("session_id", "unknown")
    
    # ... node logic ...
    
    # Log at the end
    latency_ms = (time.time() - start_time) * 1000
    log_node_execution(
        logger,
        node="<node_name>",
        message="<Node description> completed",
        level="INFO",
        domain=domain,
        user_id=user_id,
        session_id=session_id,
        latency_ms=latency_ms
        # Add node-specific fields (e.g., tokens, citations, etc.)
    )
    
    return {**state, ...}
```

### 3. Settings.py initialization

```python
# backend/core/settings.py - AT THE VERY END

# ============================================================================
# STRUCTURED LOGGING SETUP
# ============================================================================
import os
from infrastructure.structured_logging import setup_structured_logging

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
JSON_LOGGING = os.getenv("JSON_LOGGING", "true").lower() == "true"

setup_structured_logging(
    log_level=LOG_LEVEL,
    log_file=None,  # stdout only for Docker
    json_format=JSON_LOGGING
)

logger = logging.getLogger(__name__)
logger.info(
    "Django application started",
    extra={
        "log_level": LOG_LEVEL,
        "json_logging": JSON_LOGGING,
        "debug": DEBUG
    }
)
```

### 4. Environment variables

```bash
# .env
LOG_LEVEL=INFO
JSON_LOGGING=true
```

### 5. Restart & Verify

```bash
docker-compose restart backend
docker-compose logs backend --tail 20

# Should see JSON output like:
# {"timestamp":"2026-01-23T10:30:45Z","level":"INFO","name":"core.settings",
#  "message":"Django application started","log_level":"INFO","json_logging":true}
```

---

## Minimal Quick Win (Just to See Logs in Grafana)

**If you just want to see SOMETHING in Grafana quickly:**

### core/settings.py (add at the end):

```python
# MINIMAL LOKI INTEGRATION (END OF FILE)
from infrastructure.structured_logging import setup_structured_logging
setup_structured_logging(log_level="INFO", json_format=True)
```

**That's it!** Django's existing logging will now output JSON.

Restart backend:
```bash
docker-compose restart backend
```

Go to Grafana → Explore → Loki → Query: `{job="backend"}`

You'll see Django startup logs, request logs, etc. in JSON format! ✅

---

## Expected JSON Output Examples

### Intent Detection Log:
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
  "confidence": 0.95,
  "latency_ms": 234.56
}
```

### Generation Log:
```json
{
  "timestamp": "2026-01-23T10:30:58.789012Z",
  "level": "INFO",
  "name": "services.agent",
  "message": "LLM response generated",
  "module": "agent",
  "function": "_generation_node",
  "line": 1020,
  "node": "generation",
  "domain": "it",
  "user_id": "user123",
  "session_id": "session456",
  "latency_ms": 12345.67,
  "tokens": 1234,
  "cost": 0.01234
}
```

### Error Log:
```json
{
  "timestamp": "2026-01-23T10:31:02.345678Z",
  "level": "ERROR",
  "name": "services.agent",
  "message": "Tool execution failed",
  "module": "agent",
  "function": "_tool_executor_node",
  "line": 750,
  "node": "tool_executor",
  "domain": "it",
  "user_id": "user123",
  "session_id": "session456",
  "error_type": "TimeoutError",
  "error_message": "Jira API timeout after 10 seconds",
  "exc_info": "Traceback (most recent call last):\n  File ..."
}
```

---

## Next: Grafana Dashboards & Alerts

Once you have logs flowing, create dashboards:

1. **Node Performance Dashboard**
   - Panel: Latency by node (time series)
   - Query: `avg_over_time({job="backend"} | json | latency_ms [5m]) by (node)`

2. **Error Monitoring Dashboard**
   - Panel: Error rate (graph)
   - Query: `sum(rate({job="backend"} | json | level="ERROR" [1m]))`

3. **User Activity Dashboard**
   - Panel: Active users (stat)
   - Query: `count(count_over_time({job="backend"} | json [1h]) by (user_id))`

See full dashboard configs in `docs/LOKI_LOGGING.md`

---

**Questions? Issues? Let me know!**
