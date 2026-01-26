"""
Output models for the SupportAI response structure.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Triage(BaseModel):
    """Ticket triage information."""

    category: Literal["Billing", "Technical", "Account", "Feature Request", "General"] = Field(
        description="Main ticket category"
    )
    subcategory: Optional[str] = Field(
        default=None,
        description="More specific subcategory"
    )
    priority: Literal["P1", "P2", "P3", "P4"] = Field(
        description="Priority level: P1=Critical, P2=High, P3=Medium, P4=Low"
    )
    sla_hours: int = Field(
        description="SLA deadline in hours"
    )
    suggested_team: str = Field(
        description="Recommended team for handling"
    )
    sentiment: Literal["frustrated", "neutral", "satisfied"] = Field(
        description="Customer sentiment"
    )
    language: str = Field(
        description="Detected language of the ticket"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score of the analysis"
    )


class AnswerDraft(BaseModel):
    """Generated answer draft."""

    greeting: str = Field(
        description="Opening greeting"
    )
    body: str = Field(
        description="Main response body with [#N] citations"
    )
    closing: str = Field(
        description="Closing statement"
    )
    tone: Literal[
        "empathetic_professional",
        "formal",
        "friendly",
        "apologetic",
        "neutral"
    ] = Field(
        default="empathetic_professional",
        description="Tone of the response"
    )


class Citation(BaseModel):
    """Knowledge base citation."""

    id: int = Field(
        description="Citation reference number (used as [#N] in body)"
    )
    doc_id: str = Field(
        description="Document identifier (e.g., KB-001)"
    )
    title: str = Field(
        description="Document or section title"
    )
    excerpt: str = Field(
        description="Relevant excerpt from the document"
    )
    score: float = Field(
        ge=0.0, le=1.0,
        description="Relevance score"
    )
    url: Optional[str] = Field(
        default=None,
        description="Link to the full document"
    )


class PolicyCheck(BaseModel):
    """Policy compliance check results."""

    refund_promise: bool = Field(
        default=False,
        description="Whether the response promises a refund"
    )
    sla_mentioned: bool = Field(
        default=False,
        description="Whether SLA timeline is mentioned"
    )
    escalation_needed: bool = Field(
        default=False,
        description="Whether the ticket needs escalation"
    )
    compliance: Literal["passed", "warning", "failed"] = Field(
        default="passed",
        description="Overall compliance status"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="List of policy warnings if any"
    )


class SimilarTicket(BaseModel):
    """Similar historical ticket reference."""

    ticket_id: str = Field(
        description="Ticket identifier"
    )
    title: str = Field(
        description="Ticket title/summary"
    )
    resolution: Optional[str] = Field(
        default=None,
        description="How the ticket was resolved"
    )
    similarity_score: float = Field(
        ge=0.0, le=1.0,
        description="Similarity score"
    )


class SupportAIResponse(BaseModel):
    """Complete SupportAI response structure."""

    session_id: str = Field(
        description="Session identifier for conversation tracking"
    )
    triage: Triage = Field(
        description="Ticket triage information"
    )
    answer_draft: AnswerDraft = Field(
        description="Generated answer draft"
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Knowledge base citations used in the answer"
    )
    policy_check: PolicyCheck = Field(
        description="Policy compliance check results"
    )
    similar_tickets: list[SimilarTicket] = Field(
        default_factory=list,
        description="Similar historical tickets (if enabled)"
    )
    internal_note: Optional[str] = Field(
        default=None,
        description="Internal note for support agents (not shown to customer)"
    )
    should_auto_respond: bool = Field(
        default=False,
        description="Whether the system is confident enough to auto-respond"
    )
