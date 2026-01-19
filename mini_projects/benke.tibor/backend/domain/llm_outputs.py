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

