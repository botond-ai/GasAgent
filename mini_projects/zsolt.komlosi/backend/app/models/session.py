"""
Session and memory-related Pydantic models.
"""

from datetime import datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in a conversation."""

    id: Optional[int] = None
    role: Literal["user", "assistant", "system"] = Field(
        description="Message role"
    )
    content: str = Field(
        description="Message content"
    )
    content_filtered: Optional[str] = Field(
        default=None,
        description="PII-filtered version of content"
    )
    citations: list[dict] = Field(
        default_factory=list,
        description="Citations used in this message"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


class Session(BaseModel):
    """A conversation session."""

    id: str = Field(
        description="Unique session identifier (UUID)"
    )
    user_identifier: Optional[str] = Field(
        default=None,
        description="Hashed user identifier (IP or user ID)"
    )
    messages: list[Message] = Field(
        default_factory=list,
        description="Conversation messages"
    )
    rolling_summary: Optional[str] = Field(
        default=None,
        description="Rolling summary of older messages"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Session metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )


class SessionSummary(BaseModel):
    """Summary view of a session."""

    id: str
    message_count: int
    last_message_preview: Optional[str] = None
    rolling_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PIIMatch(BaseModel):
    """A detected PII match."""

    type: Literal["email", "phone", "credit_card", "name", "address", "other"] = Field(
        description="Type of PII detected"
    )
    original: str = Field(
        description="Original matched text"
    )
    masked: str = Field(
        description="Masked replacement"
    )
    start: int = Field(
        description="Start position in text"
    )
    end: int = Field(
        description="End position in text"
    )


class PIIFilterResult(BaseModel):
    """Result of PII filtering."""

    original_text: str
    filtered_text: str
    matches: list[PIIMatch] = Field(
        default_factory=list
    )
    has_pii: bool = False
