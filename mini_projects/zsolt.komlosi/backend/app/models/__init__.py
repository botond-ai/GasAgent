"""
Models package - exports all Pydantic models.
"""

from .ticket import (
    TicketAnalysis,
    TicketInput,
    TicketMetadata,
    PRIORITY_SLA_HOURS,
    PRIORITY_NAMES,
    CATEGORY_ROUTING,
)
from .output import (
    Triage,
    AnswerDraft,
    Citation,
    PolicyCheck,
    SimilarTicket,
    SupportAIResponse,
)
from .rag import (
    Document,
    Chunk,
    SearchResult,
    RerankedResult,
    ExpandedQuery,
    DocumentUpload,
    DocumentInfo,
)
from .session import (
    Message,
    Session,
    SessionSummary,
    PIIMatch,
    PIIFilterResult,
)
from .api import (
    ChatRequest,
    ChatResponse,
    JiraWebhookPayload,
    JiraWebhookResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentListResponse,
    HealthResponse,
    ErrorResponse,
)

__all__ = [
    # Ticket models
    "TicketAnalysis",
    "TicketInput",
    "TicketMetadata",
    "PRIORITY_SLA_HOURS",
    "PRIORITY_NAMES",
    "CATEGORY_ROUTING",
    # Output models
    "Triage",
    "AnswerDraft",
    "Citation",
    "PolicyCheck",
    "SimilarTicket",
    "SupportAIResponse",
    # RAG models
    "Document",
    "Chunk",
    "SearchResult",
    "RerankedResult",
    "ExpandedQuery",
    "DocumentUpload",
    "DocumentInfo",
    # Session models
    "Message",
    "Session",
    "SessionSummary",
    "PIIMatch",
    "PIIFilterResult",
    # API models
    "ChatRequest",
    "ChatResponse",
    "JiraWebhookPayload",
    "JiraWebhookResponse",
    "DocumentUploadRequest",
    "DocumentUploadResponse",
    "DocumentListResponse",
    "HealthResponse",
    "ErrorResponse",
]
