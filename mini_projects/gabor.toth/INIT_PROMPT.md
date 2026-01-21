# Advanced RAG Workflow with Hybrid LangGraph Architecture

You are GitHub Copilot working on an AI agent system. Your task is to build a complete, production-ready RAG (Retrieval-Augmented Generation) workflow with comprehensive error handling, logging, and observability.

## Project Goal

Implement an **Advanced RAG Agent** that:
1. Routes user questions to appropriate knowledge categories
2. Searches vector embeddings for relevant context
3. Handles errors gracefully with exponential backoff retries
4. Logs every operation for debugging and analytics
5. Provides real-time user feedback via activity callbacks
6. Persists complete workflow logs for offline analysis

## Architecture Overview

### Workflow Pattern: Hybrid LangGraph

The workflow combines:
- **4 Explicit Orchestration Nodes** - Decision making, error handling, quality evaluation
- **1 Tool Node** - Wraps LangChain @tool decorated functions for parallel execution
- **2 Utility Nodes** - Deduplication, response formatting with log aggregation

**Node Sequence:**
```
validate_input → tools (ToolNode) → process_tool_results → handle_errors → 
evaluate_search_quality → route_to_fallback → deduplicate_chunks → tools (again if fallback) → 
format_response (END)
```

### Key Components

#### 1. Tool Registry (4 Tools)
Each tool MUST:
- Be decorated with `@tool` from LangChain
- Return JSON with timing metadata (`_time_ms` field)
- Include error signals (`_error`, `_error_type` fields)
- Support retry logic via `retry_with_backoff()` helper

Tools:
- `category_router_tool()` - Route question to categories using LLM
- `embed_question_tool()` - Convert question to embeddings
- `search_vectors_tool()` - Search vector DB for relevant chunks
- `generate_answer_tool()` - Generate answer from chunks using LLM

#### 2. Error Handling & Recovery

**Retry Strategy:**
- Exponential backoff: 1st retry after 0.5s delay, 2nd after 1s delay
- Max 2 retries per tool call
- Error signals in tool output: `_error: true`, `_error_type: "api_error" | "timeout" | ...`

**Error Decision Node (`handle_errors_node`):**
- If error_count == 0: continue to quality evaluation
- If recoverable error AND retry_count < 2: retry the tools
- If retry_count >= 2: trigger fallback search
- If non-recoverable: skip to response formatting

**Fallback Search:**
- Triggered when: retries exhausted OR quality metrics insufficient
- Behavior: Search ALL categories instead of routed category
- Logged as recovery action

#### 3. Hybrid Logging System

**Three Parallel Channels:**

**Channel 1: Real-Time Activity Callback (UI)**
- Sends user-friendly messages to frontend
- Used for: Success notifications, error warnings, retry indicators, progress updates
- Examples:
  - "✅ Kategória router: Technology (95%) - 234ms"
  - "🔄 Újrapróbálás 1/2..."
  - "📊 Keresési minőség alacsony: 2 chunk, avg_similarity=0.32"
  - "✅ Feldolgozás befejezve (2456ms, 0 hiba)"

**Channel 2: Structured State Logging (`workflow_logs[]`)**
- Synchronous: Appended to state during node execution
- Format: JSON events with timestamp + metadata
- Every event includes: event type, timestamp, relevant metrics
- Examples:
  ```json
  {
    "event": "tool_success",
    "tool_name": "category_router_tool",
    "time_ms": 234.5,
    "timestamp": "2024-01-15T10:30:45.123456"
  }
  ```

**Channel 3: Async File Persistence**
- Non-blocking: `write_workflow_log_async()` saves after workflow completes
- Location: `data/logs/{user_id}/{timestamp}_{session_id}.json`
- Content: Aggregated WorkflowLog + debug_metadata
- For: Offline analytics, audit trail, performance analysis

#### 4. WorkflowState Extension (Error & Logging Fields)

All nodes have access to these state fields for tracking:

```python
TypedDict WorkflowState:
    # Logging infrastructure
    workflow_logs: List[Dict]              # All structured events
    workflow_start_time: float             # Workflow start timestamp
    
    # Error tracking
    errors: List[str]                      # Error messages
    error_count: int                       # Total error count
    retry_count: int                       # Retry attempts
    tool_failures: Dict[str, Optional[str]]  # Per-tool failures
    recovery_actions: List[str]            # Recovery audit trail
    last_error_type: Optional[str]         # Most recent error type
    
    # Core RAG fields
    question: str
    routed_category: Optional[str]
    context_chunks: List[Chunk]
    final_answer: str
    fallback_triggered: bool
    activity_callback: Optional[ActivityCallback]
```

#### 5. WorkflowOutput Enhancement

The final output includes logging data:

```python
@dataclass
class WorkflowOutput:
    final_answer: str
    answer_with_citations: str
    citation_sources: List[CitationSource]
    workflow_steps: List[str]
    error_messages: List[str]
    routed_category: Optional[str]
    search_strategy: str
    fallback_triggered: bool
    
    # NEW: Logging fields
    workflow_log: Optional[Dict]    # Aggregated workflow metrics
    debug_metadata: Optional[Dict]  # Debug info (tool failures, errors, etc.)
```

## Implementation Requirements

### 1. Retry with Backoff (Helper Function)

```python
async def retry_with_backoff(func, max_retries=2):
    """
    Retry async function with exponential backoff.
    
    Returns: (success_result, error) tuple
    """
    # Implementation: Try up to max_retries times
    # Backoff: 0.5s, then 1.0s
    # Return result/error for tool to process
```

### 2. Tool Registry with LangChain Integration

Each tool MUST:
- Import `@tool` from `langchain_core.tools`
- Return a dict with: `success: bool`, `data: Any`, `system_message: str`, `_time_ms: float`
- Include error handling: catch exceptions, set `_error: true`, `_error_type: str`
- Include timing: `start_time = time.time()`, calculate `elapsed_ms`

All 4 tools wrapped in `ToolRegistry` class for management.

### 3. Explicit Node: `validate_input_node`

Initialize logging infrastructure:
- Set `workflow_start_time = time.time()`
- Initialize `workflow_logs = []`
- Initialize all error fields: `error_count = 0`, `retry_count = 0`, `errors = []`, etc.
- Log validation success event
- Return state

### 4. Explicit Node: `process_tool_results_node`

Process ToolNode outputs:
- Extract `tool_result` from state
- If JSON string: parse it (catch `JSONDecodeError`)
- Detect errors: check for `_error` field
- If error: log error event + activity callback warning
- If success: extract `_time_ms`, log success event
- Merge non-internal fields into state
- Return state

### 5. Explicit Node: `handle_errors_node`

Error recovery decision:
- If `error_count == 0`: log and continue to quality evaluation
- If recoverable error AND `retry_count < 2`:
  - Increment `retry_count`
  - Log retry decision event
  - Send activity callback: "🔄 Újrapróbálás N/2..."
  - Return to "tools" node
- If retries exhausted:
  - Set `fallback_triggered = True`
  - Log fallback decision
  - Send activity callback: "🔄 Retries kimerültek..."
  - Return to "tools" for fallback
- If non-recoverable:
  - Log skip decision
  - Send activity callback warning
  - Skip to "format_response"

### 6. Utility Nodes: Quality & Fallback Evaluation

**`evaluate_search_quality_node`:**
- Calculate chunk_count, avg_similarity from context_chunks
- Decide: `fallback_needed = chunk_count < 3 OR avg_similarity < 0.3`
- Log quality_evaluation event with metrics
- Send activity callback if fallback needed
- Return state (routing decision handled separately)

**`route_to_fallback_decision_node`:**
- If fallback_triggered: set search_strategy to FALLBACK, log routing, return to "tools"
- Else: proceed to deduplicate_chunks

### 7. Utility Node: `deduplicate_chunks_node`

Deduplicate by content hash:
- Track original_count before dedup
- Create unique_chunks list (hash-based dedup)
- Log deduplication event with original/final/removed counts
- Send activity callback with dedup results
- Return state

### 8. Explicit Node: `format_response_node` (Critical)

**Aggregation & Log Assembly:**
- Calculate `total_time_ms = (now - workflow_start_time) * 1000`
- Aggregate metrics from state:
  - error_count, retry_count, recovery_actions
  - fallback_triggered, chunk_count
- Build final `workflow_log` dict:
  ```python
  {
    "session_id": state.session_id,
    "user_id": state.user_id,
    "question": state.question,
    "total_time_ms": total_ms,
    "status": "success" | "completed_with_errors",
    "error_count": count,
    "retry_count": count,
    "fallback_triggered": bool,
    "answer_generated": bool,
    "chunk_count": count,
    "citation_count": count,
    "logs": state.workflow_logs,  # All event logs
    "recovery_actions": state.recovery_actions,
  }
  ```
- Build `debug_metadata` dict:
  ```python
  {
    "tool_failures": state.tool_failures,
    "error_messages": state.error_messages,
    "last_error_type": state.last_error_type,
    "search_strategy": state.search_strategy.value,
    "fallback_metrics": {...},
  }
  ```
- Log workflow_complete event
- Send final activity callback: "✅ Feldolgozás befejezve (XXXms, N hiba)"
- Assign logs to state for return in WorkflowOutput
- Return state

### 9. Helper Function: `log_and_notify()`

Utility for simultaneous UI + state logging:

```python
async def log_and_notify(state, message, activity_type="info"):
    """
    Send activity callback (UI) + append to workflow_logs simultaneously.
    
    Args:
        state: WorkflowState
        message: User-facing message
        activity_type: "info", "success", "warning", "error"
    """
    # Append to state["workflow_logs"] with timestamp
    # Call state["activity_callback"].log_activity() if exists
```

### 10. Async File Writing: `write_workflow_log_async()`

Non-blocking JSON persistence:

```python
async def write_workflow_log_async(user_id: str, session_id: str, workflow_log: Dict):
    """
    Write workflow log to disk asynchronously.
    
    Creates: data/logs/{user_id}/{timestamp}_{session_id}.json
    
    - Create directory if needed (os.makedirs)
    - Use timestamp for filename ordering
    - Write JSON with indentation
    - Catch & log file I/O errors without crashing workflow
    """
```

### 11. Tool Implementations Details

All 4 tools MUST include:

```python
@tool
async def tool_name(...) -> Dict:
    start_time = time.time()
    try:
        # Tool logic here
        result = {...}
        elapsed_ms = (time.time() - start_time) * 1000
        result["_time_ms"] = elapsed_ms
        return result
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "_error": True,
            "_error_type": "error_category",
            "_time_ms": elapsed_ms,
            "error_message": str(e)
        }
```

## Logging Tiers (7 Levels)

Implementation must support all 7 tiers:

1. **TIER 1: Mandatory** - Every tool call records: endpoint, status_code (success/error), response_time_ms
2. **TIER 2: Tool Calls** - Each tool logged with name, arguments, result, timing, error details
3. **TIER 3: Error Recovery** - Retry decisions, fallback triggers, recovery actions
4. **TIER 4: State Snapshots** - Periodic state field snapshots at critical nodes
5. **TIER 5: User-Facing Activity** - Activity callback messages (progress, errors, success)
6. **TIER 6: Offline Analysis** - Persisted JSON logs for analytics and audit trail
7. **TIER 7: Performance Metrics** - Per-operation timing, quality scores, resource usage

## Integration Points

### With AdvancedRAGAgent

```python
class AdvancedRAGAgent:
    async def answer_question(self, user_id, question, available_categories, 
                             activity_callback=None) -> WorkflowOutput:
        # Initialize state with all logging fields
        initial_state = {..., 
            "workflow_logs": [],
            "workflow_start_time": time.time(),
            "error_count": 0,
            "retry_count": 0,
            ...
        }
        
        # Run workflow
        result = self.graph.invoke(initial_state)
        
        # Async write logs (non-blocking)
        asyncio.create_task(
            write_workflow_log_async(user_id, session_id, result["workflow_log"])
        )
        
        # Return output with logs
        return WorkflowOutput(..., 
            workflow_log=result["workflow_log"],
            debug_metadata=result["debug_metadata"]
        )
```

### With FastAPI Endpoint & ChatService

The `ChatService` orchestrates the workflow and returns response with:

```python
@app.post("/api/chat")
async def chat(request: ChatRequest):
    response = await chat_service.process_message(
        user_id=request.user_id,
        session_id=request.session_id,
        user_message=request.message
    )
    
    return response  # Dict with structure below
```

**Response Structure:**
```python
{
    "final_answer": str,              # Generated answer with citations
    "tools_used": List[str],          # Tools called in workflow
    "fallback_search": bool,          # Whether fallback was triggered
    "memory_snapshot": {
        "routed_category": str,       # Category message was routed to
        "available_categories": List[str]  # All available categories
    },
    "rag_debug": {
        "retrieved": [                # Retrieved chunks with full content
            {
                "chunk_id": str,
                "content": str,       # Full text of chunk
                "source_file": str,   # Document source
                "section_title": str, # Section in document
                "distance": float,    # Similarity score
                "snippet": str,       # Preview text
                "metadata": Dict      # Additional metadata
            }
        ]
    },
    "debug_steps": [                  # Workflow execution steps
        {
            "node": str,
            "step": str,
            "status": str,
            "timestamp": str,
            # ... step-specific metadata
        }
    ],
    "api_info": {                     # API call metadata
        "endpoint": str,              # e.g., "/api/chat"
        "method": str,                # e.g., "POST"
        "status_code": int,           # e.g., 200
        "response_time_ms": float     # Total API response time
    }
}
```

## Testing Checklist

- [ ] Validate input initializes all logging fields
- [ ] Tool execution includes _time_ms in output
- [ ] Error detection in process_tool_results works for all error types
- [ ] Retry logic exponentially backs off
- [ ] handle_errors_node makes correct routing decisions
- [ ] Quality evaluation triggers fallback appropriately
- [ ] format_response_node aggregates all logs correctly
- [ ] workflow_log has all required fields
- [ ] debug_metadata includes tool failures + error context
- [ ] write_workflow_log_async creates proper directory structure
- [ ] Activity callbacks sent for all critical events
- [ ] Workflow completes even if file write fails
- [ ] JSON logs are properly formatted and readable

## Files to Create/Modify

1. `backend/services/langgraph_workflow.py`
   - Add retry_with_backoff() helper
   - Add log_and_notify() helper
   - Add write_workflow_log_async() function
   - Implement 4 @tool decorated functions with ToolRegistry
   - Implement all 7 node functions with logging
   - Extend WorkflowState TypedDict
   - Extend WorkflowOutput dataclass
   - Implement AdvancedRAGAgent class

2. `backend/main.py`
   - Update imports to use create_advanced_rag_workflow, AdvancedRAGAgent
   - Update lifespan to initialize graph + registry
   - Pass activity_callback to agent.answer_question()

## Success Criteria

✅ Hybrid workflow executes without errors  
✅ All nodes include structured logging  
✅ Retry logic handles errors gracefully  
✅ Activity callbacks provide real-time feedback  
✅ Workflow logs persisted to disk as JSON  
✅ debug_metadata includes complete error context  
✅ Code passes Python syntax validation  
✅ Integration with FastAPI complete  

---

**Note:** This prompt describes the complete implementation. If followed sequentially, it will produce a production-ready RAG workflow with comprehensive error handling, logging, and observability suitable for both user-facing applications and offline analytics.
