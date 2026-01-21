"""
State accessor helpers for nested structures.

Monitoring Integration:
- serialize_state_for_db(): PostgreSQL workflow_executions compatible
- export_telemetry(): Prometheus metrics export

WORKFLOW_REFACTOR_PLAN.md Step 1.3
"""
from typing import Optional, List, Dict, Any
from services.workflow_schemas import (
    ChatState, QueryRewriteResult, SearchResult, DocumentChunk,
    AgentControl, TelemetryData, ContextData
)
from observability.ai_metrics import (
    workflow_node_duration_seconds as workflow_duration,
    workflow_iterations_total as agent_iterations,
    tool_invocations_total as tool_usage,
    llm_tokens_total,
    qdrant_search_results_count as rag_chunks_retrieved,
)

# Legacy compatibility (workflow_requests_total removed - use llm_requests_total instead)
class LegacyMetricCompat:
    """Compatibility wrapper for removed metrics."""
    def labels(self, **kwargs):
        return self
    def inc(self, *args, **kwargs):
        pass

workflow_requests_total = LegacyMetricCompat()



# ===== STATE ACCESSORS =====

def get_query_rewrite(state: ChatState) -> Optional[QueryRewriteResult]:
    """Safe accessor for query_rewrite group."""
    return state.get("query_rewrite")


def get_rewritten_query(state: ChatState) -> Optional[str]:
    """Get rewritten query or fallback to original."""
    qr = state.get("query_rewrite")
    return qr.get("rewritten_query") if qr else state.get("query")


def get_query_intent(state: ChatState) -> Optional[str]:
    """Get query intent classification."""
    qr = state.get("query_rewrite")
    return qr.get("intent") if qr else None


def get_search_chunks(state: ChatState) -> List[DocumentChunk]:
    """Get retrieved chunks from search result."""
    sr = state.get("search_result")
    return sr.get("retrieved_chunks", []) if sr else []


def get_agent_iteration(state: ChatState) -> int:
    """Get current agent iteration count."""
    agent = state.get("agent")
    return agent.get("iteration_count", 0) if agent else 0


def get_actions_taken(state: ChatState) -> List[str]:
    """Get list of actions taken by agent."""
    agent = state.get("agent")
    return agent.get("actions_taken", []) if agent else []


def get_tools_called(state: ChatState) -> List[Dict[str, Any]]:
    """Get list of tools called by agent."""
    agent = state.get("agent")
    return agent.get("tools_called", []) if agent else []


def get_system_prompt(state: ChatState) -> Optional[str]:
    """Get system prompt from context."""
    context = state.get("context")
    return context.get("system_prompt") if context else None


def get_chat_history(state: ChatState) -> List[Dict[str, str]]:
    """Get chat history from context."""
    context = state.get("context")
    return context.get("chat_history", []) if context else []


# ===== MONITORING INTEGRATION =====

def serialize_state_for_db(state: ChatState) -> Dict[str, Any]:
    """
    Serialize ChatState for PostgreSQL workflow_executions table.
    
    MONITORING_IMPLEMENTATION_PLAN.md compatible (Phase 4).
    
    Selective persistence (exclude bloat):
    - INCLUDE: query, session_id, iteration_count, tools_called, metrics
    - EXCLUDE: messages (BaseMessage objects), query_embedding (3072 floats)
    
    Expected size: 3-10 KB per execution (vs 50-200 KB full state)
    """
    agent = state.get("agent", {})
    query_rewrite = state.get("query_rewrite", {})
    search_result = state.get("search_result", {})
    telemetry = state.get("telemetry", {})
    user_ctx = state.get("user_context", {})
    
    return {
        # Request tracking
        "request_id": telemetry.get("request_id"),
        "trace_id": telemetry.get("trace_id"),
        
        # Core tracking
        "query": state["query"],
        "session_id": state["session_id"],
        "tenant_id": user_ctx.get("tenant_id"),
        "user_id": user_ctx.get("user_id"),
        
        # Query understanding (debugging: see both original and rewritten)
        "query_original": query_rewrite.get("original_query") or state["query"],
        "query_rewritten": query_rewrite.get("rewritten_query"),
        "query_intent": query_rewrite.get("intent"),
        
        # Agent metrics
        "iteration_count": agent.get("iteration_count", 0),
        "actions_taken": agent.get("actions_taken", []),
        "tools_called": agent.get("tools_called", []),  # JSONB format
        
        # Outcome
        "final_answer": state.get("final_answer"),
        "status": "success" if telemetry.get("success") else "error",
        "error_message": state.get("errors", [])[-1].get("message") if state.get("errors") else None,
        
        # Aggregated metrics (not full data)
        "retrieved_chunks_count": len(search_result.get("retrieved_chunks", [])),
        "listed_documents_count": len(search_result.get("listed_documents", [])),
        
        # Telemetry
        "started_at": telemetry.get("started_at"),
        "completed_at": telemetry.get("completed_at"),
        "duration_ms": telemetry.get("total_duration_ms"),
        "total_llm_tokens": telemetry.get("total_llm_tokens"),
        "total_llm_cost_usd": telemetry.get("total_llm_cost_usd"),
        "node_durations": telemetry.get("node_durations", {}),  # JSONB format
    }


def export_telemetry(state: ChatState):
    """
    Export telemetry data to Prometheus from ChatState.
    
    MONITORING_IMPLEMENTATION_PLAN.md compatible (Phase 1.2).
    
    Call this at workflow completion:
    - workflow.execute() → export_telemetry(final_state)
    
    Metrics exported:
    - workflow_duration_seconds{intent, success}
    - workflow_iterations_distribution{success}
    - tool_usage_total{tool_name, status}
    - llm_tokens_total{model, operation}
    - rag_chunks_retrieved_count{search_mode}
    
    ⚠️ CRITICAL: NO high-cardinality labels (tenant_id, user_id, request_id)
    - Prometheus time series explosion: 1000 tenants × 10000 users = 10M series!
    - Tenant/user-level aggregation → PostgreSQL or Loki structured logs
    - Prometheus → Only low-cardinality: intent, model, tool_name, status
    """
    try:
        # Already imported at module level (observability.ai_metrics)
        pass
    except ImportError:
        # Prometheus metrics not yet implemented
        return
    
    telemetry = state.get("telemetry", {})
    agent = state.get("agent", {})
    query_rewrite = state.get("query_rewrite", {})
    search_result = state.get("search_result", {})
    
    # LOW-cardinality labels only (no tenant_id, user_id, request_id)
    intent = query_rewrite.get("intent", "unknown") if query_rewrite else "unknown"
    success = str(telemetry.get("success", False))
    
    # Workflow-level metrics (NO high-cardinality!)
    workflow_requests_total.labels(intent=intent).inc()
    
    workflow_duration.labels(
        intent=intent,
        success=success
    ).observe(telemetry.get("total_duration_ms", 0) / 1000.0)
    
    # Agent metrics
    agent_iterations.labels(
        success=success
    ).observe(agent.get("iteration_count", 0) if agent else 0)
    
    # Tool metrics (tool_name is low-cardinality - only ~10 tools)
    for tool_call in agent.get("tools_called", []) if agent else []:
        tool_usage.labels(
            tool_name=tool_call.get("name", "unknown"),
            status=str(tool_call.get("success", False))
        ).inc()
    
    # LLM metrics (model is low-cardinality - only ~5 models)
    for llm_call in telemetry.get("llm_calls", []):
        llm_tokens_total.labels(
            model=llm_call.get("model", "unknown"),
            operation=llm_call.get("operation", "chat")
        ).inc(llm_call.get("tokens", 0))
    
    # RAG metrics (search_mode is low-cardinality - only 3 modes)
    chunks = search_result.get("retrieved_chunks", []) if search_result else []
    if chunks:
        rag_chunks_retrieved.labels(
            search_mode=state.get("search_mode", "hybrid")
        ).observe(len(chunks))
