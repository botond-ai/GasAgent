"""
Pydantic v2 schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


# Enums as Literals
Priority = Literal["P1", "P2", "P3"]
Sentiment = Literal["frustrated", "neutral", "satisfied"]
Tone = Literal["empathetic_professional", "formal", "casual"]
Compliance = Literal["passed", "failed", "warning"]


# Request Schemas
class TicketCreate(BaseModel):
    """Schema for creating a new support ticket."""
    customer_name: str = Field(..., min_length=1, max_length=200, description="Customer name")
    customer_email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$", description="Customer email address")
    subject: str = Field(..., min_length=1, max_length=500, description="Ticket subject")
    message: str = Field(..., min_length=1, max_length=10000, description="Detailed message/issue description")


# Response Schemas
class TriageResult(BaseModel):
    """Triage classification results."""
    category: str = Field(description="Ticket category (e.g., Billing, Technical, Product)")
    subcategory: str = Field(description="Subcategory within category")
    priority: Priority = Field(description="Priority level: P1, P2, or P3")
    sla_hours: int = Field(..., ge=0, description="SLA time in hours")
    suggested_team: str = Field(description="Team recommended to handle ticket")
    sentiment: Sentiment = Field(description="Customer sentiment: frustrated, neutral, or satisfied")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for classification")


# JAVÍTVA: Citation model az OpenAI Structured Output-hoz
class Citation(BaseModel):
    """Source citation for answer."""
    model_config = ConfigDict(extra='forbid')
    
    text: str = Field(description="Citation text excerpt")
    source: str = Field(description="Source reference")
    relevance: float = Field(description="Relevance score", ge=0.0, le=1.0)


# JAVÍTVA: AnswerDraft model a citations mezővel
class AnswerDraft(BaseModel):
    """AI-generated answer draft."""
    model_config = ConfigDict(extra='forbid')
    
    greeting: str = Field(description="Warm, personalized greeting")
    body: str = Field(description="Main response body with solution")
    closing: str = Field(description="Helpful, encouraging closing")
    tone: Tone = Field(description="Tone used: empathetic_professional, formal, or casual")
    citations: list[Citation] = Field(
        default_factory=list,
        description="List of citations with text, source, and relevance"
    )


class PolicyCheck(BaseModel):
    """Policy compliance validation."""
    refund_promise: bool = Field(description="Whether response promises unauthorized refund")
    sla_mentioned: bool = Field(description="Whether response mentions specific SLA commitment")
    escalation_needed: bool = Field(description="Whether issue needs escalation")
    compliance: Compliance = Field(description="Compliance status: passed, failed, or warning")


class TriageResponse(BaseModel):
    """Complete triage and draft response."""
    ticket_id: str = Field(description="Ticket identifier")
    timestamp: datetime = Field(description="Processing timestamp")
    triage: TriageResult = Field(description="Triage classification results")
    answer_draft: AnswerDraft = Field(description="AI-generated answer draft")
    citations: list[Citation] = Field(description="Source citations for the answer")
    policy_check: PolicyCheck = Field(description="Policy compliance check results")


class Ticket(BaseModel):
    """Full ticket model."""
    id: str = Field(description="Unique ticket identifier")
    customer_name: str = Field(description="Customer name")
    customer_email: str = Field(description="Customer email address")
    subject: str = Field(description="Ticket subject")
    message: str = Field(description="Ticket message content")
    created_at: datetime = Field(description="Ticket creation timestamp")
    status: Literal["new", "processing", "completed", "error"] = Field(
        default="new",
        description="Ticket status"
    )
    triage_result: Optional[TriageResponse] = Field(
        default=None,
        description="Triage result once processed"
    )


# Internal State Schema
class SupportTicketState(BaseModel):
    """LangGraph workflow state (Pydantic v2)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Input
    ticket_id: str = Field(description="Ticket ID")
    raw_message: str = Field(description="Original customer message")
    customer_name: str = Field(description="Customer name")
    customer_email: str = Field(description="Customer email")

    # Intent Detection
    problem_type: Optional[str] = Field(default=None, description="Detected problem type")
    sentiment: Optional[Sentiment] = Field(default=None, description="Customer sentiment")

    # Triage
    category: Optional[str] = Field(default=None, description="Triage category")
    subcategory: Optional[str] = Field(default=None, description="Triage subcategory")
    priority: Optional[Priority] = Field(default=None, description="Priority level")
    sla_hours: Optional[int] = Field(default=None, description="SLA hours")
    suggested_team: Optional[str] = Field(default=None, description="Suggested team")
    triage_confidence: Optional[float] = Field(default=None, description="Triage confidence")

    # RAG
    search_queries: list[str] = Field(default_factory=list, description="Generated search queries")
    retrieved_docs: list[dict] = Field(default_factory=list, description="Retrieved documents")
    reranked_docs: list[dict] = Field(default_factory=list, description="Reranked documents")

    # Output
    answer_draft: Optional[dict] = Field(default=None, description="Generated answer draft")
    citations: list[dict] = Field(default_factory=list, description="Answer citations")
    policy_check: Optional[dict] = Field(default=None, description="Policy check results")
    output: Optional[dict] = Field(default=None, description="Final output")

    # REMOVED: old Config class - now using ConfigDict above

# Knowledge Base Document
class KnowledgeDocument(BaseModel):
    """Document for ingestion into vector database."""
    id: str = Field(description="Document identifier")
    title: str = Field(description="Document title")
    content: str = Field(description="Document content")
    category: str = Field(description="Document category")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")