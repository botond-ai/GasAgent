from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class User(BaseModel):
    user_id: int
    firstname: str
    lastname: str
    nickname: str
    email: str
    role: str
    is_active: bool
    default_lang: str
    created_at: str


# ===============================
# WORKFLOW TRACKING MODELS
# ===============================

class WorkflowExecutionResponse(BaseModel):
    """Complete workflow execution details."""
    execution_id: UUID
    session_id: UUID
    tenant_id: int
    user_id: int
    
    # Input
    query: str
    query_rewritten: Optional[str] = None
    query_intent: Optional[str] = None
    
    # Execution
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: str  # running, success, error, timeout
    
    # Output
    final_answer: Optional[str] = None
    error_message: Optional[str] = None
    
    # Metrics
    total_nodes_executed: int = 0
    iteration_count: int = 0
    reflection_count: int = 0
    tools_called: Optional[List[Dict[str, Any]]] = None
    
    # Cost and tokens
    llm_tokens_total: Optional[int] = None
    llm_cost_usd: Optional[float] = None
    
    # Correlation
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    
    # State snapshot (final)
    final_state: Optional[Dict[str, Any]] = None


class NodeExecutionResponse(BaseModel):
    """Single node execution details."""
    node_execution_id: int
    execution_id: UUID
    node_name: str
    node_index: int
    
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str  # success, error, skipped
    error_message: Optional[str] = None
    
    # State snapshots
    state_before: Optional[Dict[str, Any]] = None
    state_after: Optional[Dict[str, Any]] = None
    state_diff: Optional[Dict[str, Any]] = None
    
    # Node-specific metadata
    metadata: Optional[Dict[str, Any]] = None
    
    # Hierarchy: parent_node indicates this is a child node (e.g., tool_get_weather parent is "tools")
    parent_node: Optional[str] = None


class PromptLineageResponse(BaseModel):
    """Agent decision chain and prompt lineage."""
    execution_id: UUID
    trace_id: str
    
    prompt_chain: List[Dict[str, Any]] = Field(default_factory=list)
    decision_points: List[Dict[str, Any]] = Field(default_factory=list)


class StateTimelineResponse(BaseModel):
    """State mutation timeline."""
    execution_id: UUID
    timeline: List[Dict[str, Any]] = Field(default_factory=list)


class CostBreakdownResponse(BaseModel):
    """Cost and token analysis."""
    execution_id: UUID
    total_cost_usd: float
    
    cost_by_model: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    cost_by_node: Dict[str, float] = Field(default_factory=dict)
    token_flow: Dict[str, int] = Field(default_factory=dict)
    efficiency_metrics: Dict[str, float] = Field(default_factory=dict)


class TraceContextResponse(BaseModel):
    """Distributed tracing context."""
    execution_id: UUID
    request_id: Optional[str] = ""
    trace_id: Optional[str] = ""
    session_id: Optional[str] = ""
    tenant_id: int
    user_id: int
    
    jaeger_trace_url: str
    tempo_trace_url: str
