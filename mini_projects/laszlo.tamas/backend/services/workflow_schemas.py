"""
Workflow State Schemas - Grouped TypedDicts for ChatState.

SOLID Principle: Single Responsibility
- QueryRewriteResult: csak query rewrite adatok
- ReflectionResult: csak reflection adatok (DEPRECATED - Lépés 2-ben törlésre kerül)
- SearchResult: csak search pipeline adatok
- ContextData: csak context building adatok
- TelemetryData: observability metrics (Prometheus + PostgreSQL ready)

Monitoring Integration:
- Compatible with MONITORING_IMPLEMENTATION_PLAN.md
- PostgreSQL workflow_executions schema ready
- Prometheus metrics exportable
"""
from typing import TypedDict, Optional, List, Dict, Any, Literal, Annotated, Sequence
from datetime import datetime
from operator import add


# ===== USER CONTEXT =====

class UserContext(TypedDict):
    """User and tenant identification."""
    tenant_id: int
    user_id: int
    tenant_prompt: Optional[str]
    user_prompt: Optional[str]
    user_language: str  # 'hu' | 'en'
    firstname: Optional[str]
    lastname: Optional[str]
    email: Optional[str]
    role: Optional[str]
    default_location: Optional[str]  # "Nyíregyháza / Hungary" (from DB)
    timezone: Optional[str]  # "Europe/Budapest" (from DB)


# ===== REQUEST CONTEXT (Runtime Information) =====

class RequestContext(TypedDict):
    """
    Request-level context captured at workflow start.
    
    Contains:
    - Current datetime (ISO 8601)
    - Human-readable date and time
    - Current location (can override user's default_location)
    - Effective location (resolved from current_location OR default_location)
    """
    current_datetime: str  # ISO 8601: "2026-01-18T15:30:45+01:00"
    current_date: str  # Human: "2026-01-18 (szombat)"
    current_time: str  # Human: "15:30:45"
    current_location: Optional[str]  # Override: "Mohács / Hungary" (from chat)
    effective_location: str  # Resolved: current_location OR default_location


# ===== QUERY REWRITE GROUP =====

class QueryRewriteResult(TypedDict, total=False):
    """
    Query rewrite output (grouped from 8 flat fields → 1 nested).
    
    Before: 8 mezők a root state-ben
    After: 1 mező (query_rewrite: QueryRewriteResult)
    """
    rewritten_query: Optional[str]
    original_query: str  # For debugging/monitoring
    intent: Optional[str]  # "search_knowledge" | "list_documents" | "store_memory"
    transformations: List[Dict[str, Any]]
    reasoning: Optional[str]
    skipped: bool  # True if feature disabled
    enabled: bool  # Runtime override flag
    duration_ms: int


# ===== SEARCH PIPELINE GROUP =====

class DocumentChunk(TypedDict):
    """Single retrieved document chunk."""
    chunk_id: int
    document_id: int
    content: str
    metadata: Dict[str, Any]
    similarity_score: float


class SearchResult(TypedDict, total=False):
    """
    Search pipeline results (grouped from 6 flat fields → 1 nested).
    
    Before: query_embedding, vector_results, keyword_results, 
            enriched_chunks, retrieved_chunks, listed_documents
    After: 1 mező (search_result: SearchResult)
    """
    query_embedding: Optional[List[float]]
    vector_results: List[Dict[str, Any]]
    keyword_results: List[Dict[str, Any]]
    enriched_chunks: List[DocumentChunk]
    retrieved_chunks: List[DocumentChunk]
    listed_documents: List[Dict[str, Any]]


# ===== REFLECTION GROUP (DEPRECATED) =====

class ReflectionResult(TypedDict, total=False):
    """
    Reflection/quality check results (grouped from 3 flat fields → 1 nested).
    
    DEPRECATED: Will be removed in Step 2 (LLM self-correction suffices).
    
    Before: reflection_decision, reflection_issues, reflection_count
    After: 1 mező (reflection: ReflectionResult)
    """
    decision: Optional[str]  # "retry" | "continue"
    issues: List[str]  # ["rag_empty_results", "context_mismatch", ...]
    count: int


# ===== CONTEXT BUILDING GROUP =====

class ContextData(TypedDict, total=False):
    """
    Context building data (grouped from 6 flat fields → 1 nested).
    
    Before: tenant_data, user_data, chat_history, system_prompt, 
            system_prompt_cached, cache_source
    After: 1 mező (context: ContextData)
    """
    tenant_data: Optional[Dict[str, Any]]
    user_data: Optional[Dict[str, Any]]
    chat_history: List[Dict[str, str]]
    system_prompt: str
    cached: bool
    cache_source: Optional[str]  # "memory" | "database" | "llm_generated"


# ===== AGENT CONTROL GROUP =====

class AgentControl(TypedDict, total=False):
    """
    Agent execution control (grouped from 4 flat fields → 1 nested).
    
    Before: iteration_count, next_action, actions_taken, tools_called
    After: 1 mező (agent: AgentControl)
    
    Monitoring: iteration_count, tools_called tracked in Prometheus
    """
    iteration_count: int
    next_action: Optional[str]  # "CALL_TOOLS" | "FINAL_ANSWER"
    actions_taken: List[str]  # ["RAG", "CHAT", "LIST"]
    tools_called: List[Dict[str, Any]]  # [{"name": "search_vectors", "duration_ms": 123, "status": "success"}]
    max_iterations_reached: bool  # True if MAX_ITERATIONS hit
    llm_model_used: str  # Actual LLM model used (e.g., "gpt-3.5-turbo", "gpt-4o")


# ===== TELEMETRY GROUP (MONITORING INTEGRATION) =====

class TelemetryData(TypedDict, total=False):
    """
    Workflow execution telemetry for Prometheus/Grafana + PostgreSQL tracking.
    
    MONITORING_IMPLEMENTATION_PLAN.md compatible:
    - Phase 1.1: Request context (request_id, trace_id)
    - Phase 4: DB serialization (serialize_state_for_db)
    
    Prometheus metrics mapping:
    - workflow_duration_seconds{tenant_id, user_id, intent, success}
    - workflow_node_duration_seconds{node_name}
    - workflow_llm_tokens_total{model, operation}
    - workflow_errors_total{error_type, node_name}
    """
    # Request context (Phase 1.1 - Trace propagation)
    request_id: str  # UUID per API call (transient)
    trace_id: str    # OpenTelemetry trace ID (spans correlation)
    execution_id: Optional[str]  # CRITICAL FIX 1.3: Workflow execution UUID (database tracking)
    
    # Timing
    started_at: datetime
    completed_at: Optional[datetime]
    total_duration_ms: int
    
    # Node-level timing (node_name → duration_ms)
    node_durations: Dict[str, int]  # {"validate_input": 12, "query_rewrite": 45, ...}
    
    # LLM tracking
    llm_calls: List[Dict[str, Any]]  # [{"model": "gpt-4", "operation": "chat", "tokens": 234, "duration_ms": 890}]
    total_llm_tokens: int
    total_llm_cost_usd: float
    
    # Error tracking
    errors_encountered: List[str]  # ["query_rewrite_timeout", "qdrant_connection_error"]
    
    # Status flags
    success: bool
    empty_rag_result: bool  # RAG returned 0 chunks?
    fallback_used: bool     # Fallback response triggered?
    
    # DB serialization flag
    serializable: bool  # True if ready for workflow_executions table


# ===== MAIN STATE =====

class ChatState(TypedDict):
    """
    Simplified ChatState with grouped nested types + Monitoring Integration.
    
    BEFORE: 42 flat fields
    AFTER: 18 fields (7 nested groups, including telemetry)
    
    Complexity reduction: -57% field count, +100% type safety
    Monitoring: Prometheus + PostgreSQL tracking ready
    
    MONITORING_IMPLEMENTATION_PLAN.md compatible:
    - telemetry.* → Prometheus metrics export
    - serialize_state_for_db() → workflow_executions table
    """
    # Input
    query: str
    session_id: str
    user_context: UserContext
    
    # Request context (datetime, location) - captured at workflow start
    request_context: RequestContext
    
    # Processing groups (nested)
    query_rewrite: Optional[QueryRewriteResult]
    search_result: Optional[SearchResult]
    reflection: Optional[ReflectionResult]  # DEPRECATED - Lépés 2-ben törlésre kerül
    context: Optional[ContextData]
    agent: Optional[AgentControl]
    
    # Telemetry (MONITORING INTEGRATION)
    telemetry: TelemetryData  # Prometheus + PostgreSQL tracking
    
    # LangChain messages
    messages: Annotated[Sequence[Any], add]  # BaseMessage objects (HumanMessage, AIMessage, ToolMessage)
    
    # Search configuration
    search_mode: str  # "vector" | "keyword" | "hybrid"
    vector_weight: float
    keyword_weight: float
    
    # Long-term memory
    ltm_read_results: Optional[List[Dict[str, Any]]]
    ltm_write_fact: Optional[str]
    
    # Output
    final_answer: Optional[str]
    sources: List[Dict[str, Any]]
    errors: Annotated[List[Dict[str, Any]], add]
    actions_taken: List[str]  # High-level actions: ["RAG", "CHAT", "LIST"] - for observability/monitoring
    
    # Legacy/intermediate (will be migrated to nested groups)
    intermediate_results: List[Dict[str, Any]]  # Temporary backward compatibility
