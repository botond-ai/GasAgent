"""
Domain models - Pydantic data structures for requests/responses.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class DomainType(str, Enum):
    """Supported knowledge domains."""
    HR = "hr"
    IT = "it"
    FINANCE = "finance"
    LEGAL = "legal"
    MARKETING = "marketing"
    GENERAL = "general"


class Message(BaseModel):
    """Single message in conversation history."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None
    domain: Optional[str] = None  # Domain for caching (marketing, hr, it, etc.)
    citations: Optional[List[Dict[str, Any]]] = None  # Citations for caching
    workflow: Optional[Dict[str, Any]] = None  # Workflow state
    regenerated: bool = False  # Flag indicating cached regeneration


class Citation(BaseModel):
    """Source document reference."""
    doc_id: str
    title: str
    score: float  # Retrieval score (0-1)
    url: Optional[str] = None
    content: Optional[str] = None  # Document/chunk content for RAG context
    section_id: Optional[str] = None  # For IT domain: [IT-KB-234] style references


class WorkflowState(BaseModel):
    """Multi-step workflow tracking."""
    flow: Optional[str] = None  # e.g., "hr_vacation_request"
    step: int = 0
    total_steps: int = 0
    data: Optional[Dict[str, Any]] = None


class UserProfile(BaseModel):
    """User profile and preferences."""
    user_id: str
    organisation: str
    language: str = "hu"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    preferences: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "organisation": "ACME Corp",
                "language": "hu",
                "preferences": {"department": "IT", "role": "engineer"}
            }
        }


class QueryRequest(BaseModel):
    """Chat query request."""
    user_id: str
    session_id: Optional[str] = None
    query: str
    organisation: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "emp_001",
                "query": "Szeretnék szabadságot igényelni október 3-4 között"
            }
        }


class ToolCall(BaseModel):
    """Tool invocation record."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None


class ProcessingStatus(str, Enum):
    """LangGraph processing status for HTTP status code determination."""
    SUCCESS = "success"  # HTTP 200 - All nodes completed successfully
    PARTIAL_SUCCESS = "partial_success"  # HTTP 206 - Guardrail retry occurred but completed
    RAG_UNAVAILABLE = "rag_unavailable"  # HTTP 503 - RAG failed, fallback to summary-only
    GENERATION_FAILED = "generation_failed"  # HTTP 500 - LLM generation error
    VALIDATION_FAILED = "validation_failed"  # HTTP 422 - Persistent validation errors after max retries


class QueryResponse(BaseModel):
    """Structured agent response."""
    domain: DomainType
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    tools_used: List[ToolCall] = Field(default_factory=list)
    workflow: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    # LangGraph state tracking
    processing_status: ProcessingStatus = ProcessingStatus.SUCCESS
    validation_errors: List[str] = Field(default_factory=list)
    retry_count: int = 0
    # Telemetry fields (optional, for debug)
    rag_context: Optional[str] = None
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    llm_input_tokens: Optional[int] = 0
    llm_output_tokens: Optional[int] = 0
    llm_total_cost: Optional[float] = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "domain": "hr",
                "answer": "Szabadságkérelmed rögzítésre került október 3-4 között.",
                "citations": [
                    {
                        "doc_id": "HR-POL-001",
                        "title": "Vacation Policy",
                        "score": 0.94,
                        "url": "https://..."
                    }
                ],
                "workflow": {
                    "action": "hr_request_created",
                    "file": "hr_request_2025-10-03.json"
                }
            }
        }


class Memory(BaseModel):
    """Agent memory context."""
    chat_history: List[Message] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    workflow_state: WorkflowState = Field(default_factory=WorkflowState)


class FeedbackType(str, Enum):
    """Feedback types."""
    LIKE = "like"
    DISLIKE = "dislike"


class CitationFeedback(BaseModel):
    """User feedback on a specific citation."""
    id: Optional[str] = None
    citation_id: str  # Qdrant point ID
    domain: str
    user_id: str
    session_id: str
    query_text: str
    query_embedding: Optional[List[float]] = None  # 1536-dim OpenAI embedding
    feedback_type: FeedbackType
    citation_rank: Optional[int] = None  # Position in results (1-5)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "citation_id": "6519535e-e4fb-052c-4780-8f926c699e34",
                "domain": "marketing",
                "user_id": "emp_001",
                "session_id": "sess_123",
                "query_text": "Mi a brand guideline?",
                "feedback_type": "like",
                "citation_rank": 1
            }
        }


class ResponseFeedback(BaseModel):
    """User feedback on entire response."""
    id: Optional[str] = None
    user_id: str
    session_id: str
    query_text: str
    domain: str
    feedback_type: FeedbackType
    comment: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "emp_001",
                "session_id": "sess_123",
                "query_text": "Mi a brand guideline?",
                "domain": "marketing",
                "feedback_type": "like"
            }
        }


class FeedbackStats(BaseModel):
    """Aggregated feedback statistics."""
    total_feedbacks: int
    like_count: int
    dislike_count: int
    like_ratio: float
    by_domain: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    top_liked_citations: List[Dict[str, Any]] = Field(default_factory=list)
    top_disliked_citations: List[Dict[str, Any]] = Field(default_factory=list)


class FeedbackMetrics(BaseModel):
    """Pipeline execution metrics for telemetry."""
    # Retrieval metrics
    retrieval_score_top1: Optional[float] = None  # Top result semantic similarity (0-1)
    retrieval_count: int = 0  # Number of results retrieved
    dedup_count: int = 0  # Number of duplicates removed
    
    # Generation metrics
    llm_latency_ms: Optional[float] = None  # Time to generate response (milliseconds)
    llm_tokens_used: Optional[int] = None  # Tokens consumed by LLM
    llm_tokens_input: Optional[int] = None  # Input tokens
    llm_tokens_output: Optional[int] = None  # Output tokens
    
    # Cache metrics
    cache_hit_embedding: bool = False  # Embedding was from cache
    cache_hit_query: bool = False  # Query result was from cache
    
    # Validation metrics
    validation_errors: List[str] = Field(default_factory=list)
    retry_count: int = 0
    
    # Timestamps
    request_start: Optional[datetime] = None
    request_end: Optional[datetime] = None
    total_latency_ms: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "retrieval_score_top1": 0.87,
                "retrieval_count": 5,
                "dedup_count": 1,
                "llm_latency_ms": 1243.5,
                "llm_tokens_used": 156,
                "cache_hit_embedding": True,
                "cache_hit_query": False,
                "validation_errors": [],
                "retry_count": 0,
                "total_latency_ms": 2150.3
            }
        }


