"""
Structured output models for LLM responses.
Ensures type safety and validation for all LLM interactions.
"""
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import re
from datetime import datetime

from domain.models import DomainType


class IntentOutput(BaseModel):
    """Intent detection structured output."""
    domain: DomainType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    reasoning: str = Field(min_length=10, max_length=500, description="Brief explanation of classification")
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is reasonable for production."""
        if v < 0.5:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Low confidence score: {v}, consider fallback to GENERAL domain")
        return round(v, 3)  # Max 3 decimal places


class MemoryUpdate(BaseModel):
    """Memory extraction structured output."""
    summary: str = Field(..., max_length=500, description="3-4 sentence conversation summary")
    facts: List[str] = Field(default_factory=list, description="Up to 5 atomic facts")
    key_decisions: List[str] = Field(default_factory=list, description="Up to 3 key user decisions")
    
    @field_validator('facts')
    @classmethod
    def limit_facts(cls, v):
        """Limit facts to 5 items."""
        return v[:5] if v else []
    
    @field_validator('key_decisions')
    @classmethod
    def limit_decisions(cls, v):
        """Limit decisions to 3 items."""
        return v[:3] if v else []
    
    @model_validator(mode='after')
    def validate_content(self) -> 'MemoryUpdate':
        """Ensure at least some meaningful content exists."""
        if not self.summary and not self.facts and not self.key_decisions:
            raise ValueError("Memory update must contain at least summary or facts or decisions")
        return self


class RAGGenerationOutput(BaseModel):
    """RAG answer generation structured output with citation validation."""
    answer: str = Field(min_length=10, description="Complete answer in Hungarian or English")
    section_ids: List[str] = Field(
        default_factory=list,
        description="Section IDs referenced (e.g., IT-KB-234, HR-KB-456)"
    )
    language: Literal["hu", "en"] = Field(default="hu", description="Response language")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8, description="Answer confidence score")
    
    @field_validator('section_ids')
    @classmethod
    def validate_section_ids(cls, v):
        """Validate section ID format: DOMAIN-KB-NUMBER"""
        pattern = r'^[A-Z]+-KB-\d+$'
        validated = []
        for sid in v:
            if sid and re.match(pattern, sid):
                validated.append(sid)
            elif sid:  # Invalid format, log warning but don't fail
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Invalid section ID format: {sid}, skipping")
        return validated


class ToolCallDecision(BaseModel):
    """LLM tool selection decision with validation."""
    action: Literal["call_tool", "call_tools_parallel", "final_answer", "mcp_tool_execution"]
    tool_name: Optional[str] = Field(None, description="Tool name for single tool execution")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="List of tools for parallel execution")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments for single execution")
    reasoning: str = Field(min_length=20, max_length=500, description="Explanation for the decision")
    
    @model_validator(mode='after')
    def validate_tool_consistency(self) -> 'ToolCallDecision':
        """Ensure tool_name or tools list matches action."""
        if self.action == "call_tool" and not self.tool_name:
            raise ValueError("call_tool action requires tool_name to be specified")
        
        if self.action == "call_tools_parallel" and len(self.tools) < 2:
            raise ValueError("call_tools_parallel action requires at least 2 tools")
        
        if self.action == "mcp_tool_execution" and not self.tool_name:
            raise ValueError("mcp_tool_execution action requires tool_name to be specified")
        
        return self


class TurnMetrics(BaseModel):
    """Per-turn metrics with validation for observability."""
    session_id: str = Field(min_length=1, description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Turn timestamp")
    messages_count: int = Field(ge=0, description="Number of messages in state")
    tools_called: int = Field(ge=0, description="Number of tools executed")
    rag_used: bool = Field(default=False, description="Whether RAG was used")
    iteration_count: int = Field(ge=1, le=20, description="Number of iterations (max 20)")
    token_estimate: int = Field(ge=0, le=200000, description="Estimated tokens used")
    latency_ms: Optional[float] = Field(None, ge=0.0, description="Turn latency in milliseconds")
    
    @field_validator('latency_ms')
    @classmethod
    def validate_latency(cls, v: Optional[float]) -> Optional[float]:
        """Warn on high latency."""
        if v and v > 30000:  # 30 seconds
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"High latency detected: {v:.0f}ms (>30s)")
        return round(v, 2) if v else None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ToolStep(BaseModel):
    """Single tool execution step in plan."""
    step_id: int = Field(ge=1, le=10, description="Step sequence number (1-10)")
    tool_name: str = Field(min_length=1, max_length=50, description="Tool to execute (e.g., 'rag_search')")
    description: str = Field(min_length=5, max_length=200, description="What this step does")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments (key-value)")
    depends_on: List[int] = Field(default_factory=list, description="Step IDs this depends on (for parallel execution)")
    required: bool = Field(default=True, description="Is this step required or optional?")


class ExecutionPlan(BaseModel):
    """LLM-generated step-by-step execution plan."""
    reasoning: str = Field(min_length=10, max_length=1000, description="Why this plan was chosen")
    steps: List[ToolStep] = Field(min_items=1, max_items=5, description="Ordered tool execution steps")
    estimated_cost: float = Field(ge=0, le=1.0, description="Estimated cost 0-1 (relative)")
    estimated_time_ms: int = Field(ge=100, le=120000, description="Estimated execution time (100ms-120s)")
    
    @field_validator('steps')
    @classmethod
    def validate_step_ids(cls, v: List[ToolStep]) -> List[ToolStep]:
        """Ensure step IDs are sequential and unique."""
        step_ids = [step.step_id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Duplicate step IDs found")
        return v
    
    @model_validator(mode='after')
    def validate_dependencies(self) -> 'ExecutionPlan':
        """Ensure all dependencies reference existing steps."""
        valid_step_ids = {step.step_id for step in self.steps}
        for step in self.steps:
            for dep_id in step.depends_on:
                if dep_id not in valid_step_ids:
                    raise ValueError(f"Step {step.step_id} depends on non-existent step {dep_id}")
        return self


class ToolCall(BaseModel):
    """Single tool call with arguments."""
    tool_name: Literal["rag_search", "jira_create", "email_send", "calculator"] = Field(
        description="Name of the tool to execute"
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool arguments as key-value pairs"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for this tool selection (0-1)"
    )
    reasoning: str = Field(
        min_length=10, max_length=200,
        description="Why this tool was selected"
    )
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        """Warn if confidence is below 0.5."""
        if v < 0.5:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Low tool selection confidence: {v:.2f}, consider alternative tools")
        return round(v, 2)


class ToolSelection(BaseModel):
    """LLM tool selection decision with multiple tools."""
    reasoning: str = Field(
        min_length=20, max_length=500,
        description="Overall reasoning for tool selection strategy"
    )
    selected_tools: List[ToolCall] = Field(
        min_items=1, max_items=3,
        description="List of selected tools (max 3)"
    )
    fallback_plan: str = Field(
        min_length=10, max_length=300,
        description="What to do if selected tools are unavailable"
    )
    route: Literal["rag_only", "tools_only", "rag_and_tools"] = Field(
        default="rag_only",
        description="Routing decision based on selected tools"
    )
    
    @model_validator(mode='after')
    def validate_route_consistency(self) -> 'ToolSelection':
        """Ensure route matches selected tools."""
        tool_names = [tool.tool_name for tool in self.selected_tools]
        has_rag = "rag_search" in tool_names
        has_other_tools = any(t != "rag_search" for t in tool_names)
        
        # Infer correct route based on tools
        if has_rag and has_other_tools:
            expected_route = "rag_and_tools"
        elif has_rag:
            expected_route = "rag_only"
        else:
            expected_route = "tools_only"
        
        # Auto-correct route if inconsistent
        if self.route != expected_route:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Route mismatch: declared '{self.route}' but tools suggest '{expected_route}'. "
                f"Auto-correcting to '{expected_route}'"
            )
            self.route = expected_route
        
        return self


class ToolResult(BaseModel):
    """Single tool execution result."""
    tool_name: str = Field(..., description="Name of the executed tool")
    status: Literal["success", "error", "timeout"] = Field(..., description="Execution outcome")
    result: Optional[Any] = Field(default=None, description="Tool output data (if successful)")
    error: Optional[str] = Field(default=None, description="Error message (if failed)")
    latency_ms: float = Field(ge=0, description="Execution time in milliseconds")
    retry_count: int = Field(default=0, ge=0, description="Number of retries attempted")
    
    @field_validator('status')
    @classmethod
    def validate_status_consistency(cls, v, info):
        """Ensure status matches error/result fields."""
        values = info.data
        if v == "success" and not values.get("result"):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Tool {values.get('tool_name')} marked success but no result provided")
        if v in ["error", "timeout"] and not values.get("error"):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Tool {values.get('tool_name')} marked {v} but no error message")
        return v


class ObservationOutput(BaseModel):
    """Observation node structured output for evaluating sufficiency."""
    sufficient: bool = Field(..., description="Do we have enough information to answer?")
    next_action: Literal["generate", "replan"] = Field(
        default="generate",
        description="Should we generate answer or replan?"
    )
    gaps: List[str] = Field(
        default_factory=list,
        description="List of missing information or gaps (max 5)"
    )
    reasoning: str = Field(
        min_length=10,
        max_length=500,
        description="Explanation for the decision"
    )
    tool_results_count: int = Field(default=0, ge=0, description="Number of executed tool results")
    retrieval_count: int = Field(default=0, ge=0, description="Number of retrieved docs (if any)")
    
    @field_validator('gaps')
    @classmethod
    def limit_gaps(cls, v: List[str]) -> List[str]:
        """Limit gaps to 5 items."""
        return v[:5] if v else []
    
    @model_validator(mode='after')
    def validate_action_consistency(self) -> 'ObservationOutput':
        """Ensure next_action matches sufficient flag."""
        if not self.sufficient and self.next_action == "generate" and self.gaps:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Observation marked insufficient with gaps but next_action=generate. "
                f"Auto-correcting to replan."
            )
            self.next_action = "replan"
        
        if self.sufficient and self.next_action == "replan":
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Observation marked sufficient but next_action=replan. "
                f"Auto-correcting to generate."
            )
            self.next_action = "generate"
        
        return self

