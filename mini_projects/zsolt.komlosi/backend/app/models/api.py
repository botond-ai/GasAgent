"""
API request/response models.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(
        min_length=1,
        description="User message or ticket text"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for conversation continuity"
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="Customer IP address for geolocation"
    )
    source: Literal["web", "jira", "api"] = Field(
        default="web",
        description="Source of the request"
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint (wrapper for SupportAIResponse)."""

    success: bool = True
    data: dict = Field(
        description="SupportAIResponse data"
    )
    error: Optional[str] = None


class JiraWebhookPayload(BaseModel):
    """Jira webhook payload (simplified)."""

    webhookEvent: str = Field(
        description="Event type (e.g., jira:issue_created)"
    )
    issue: dict = Field(
        description="Issue data"
    )
    user: Optional[dict] = Field(
        default=None,
        description="User who triggered the event"
    )


class JiraWebhookResponse(BaseModel):
    """Response for Jira webhook."""

    status: Literal["processed", "processing", "ignored", "error"]
    ticket_id: Optional[str] = None
    message: Optional[str] = None


class DocumentUploadRequest(BaseModel):
    """Request for document upload."""

    title: str = Field(
        min_length=1,
        description="Document title"
    )
    content: str = Field(
        min_length=1,
        description="Document content (markdown or text)"
    )
    doc_type: Literal["aszf", "faq", "user_guide", "policy", "other"] = Field(
        description="Type of document"
    )
    language: str = Field(
        default="hu",
        description="Document language"
    )


class DocumentUploadResponse(BaseModel):
    """Response for document upload."""

    success: bool = True
    doc_id: str
    chunks_created: int
    message: str


class DocumentListResponse(BaseModel):
    """Response for document list."""

    documents: list[dict]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "2.0.0"
    services: dict[str, str] = Field(
        default_factory=dict,
        description="Status of dependent services"
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str
    detail: Optional[str] = None
