"""
Ticket-related Pydantic models.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class TicketAnalysis(BaseModel):
    """
    Ticket analysis result - structured LLM output.
    Extended from HF1 with additional fields.
    """

    language: str = Field(
        description="The language of the ticket (e.g., Hungarian, English, German)"
    )
    sentiment: Literal["frustrated", "neutral", "satisfied"] = Field(
        description="The customer's sentiment"
    )
    category: Literal["Billing", "Technical", "Account", "Feature Request", "General"] = Field(
        description="The ticket category"
    )
    subcategory: Optional[str] = Field(
        default=None,
        description="More specific subcategory (e.g., 'Login Issue' for Technical)"
    )
    priority: Literal["P1", "P2", "P3", "P4"] = Field(
        description="Priority: P1=Critical, P2=High, P3=Medium, P4=Low"
    )
    routing: str = Field(
        description="Suggested team (e.g., Finance Team, IT Support)"
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0, le=1.0,
        description="Confidence score for the analysis"
    )
    key_entities: list[str] = Field(
        default_factory=list,
        description="Key entities extracted from the ticket"
    )
    summary: Optional[str] = Field(
        default=None,
        description="Brief summary of the issue"
    )


class TicketInput(BaseModel):
    """Input model for ticket analysis."""

    text: str = Field(
        min_length=1,
        description="The ticket text/description"
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="Customer IP address for geolocation"
    )
    jira_key: Optional[str] = Field(
        default=None,
        description="Jira ticket key if from Jira webhook"
    )
    customer_email: Optional[str] = Field(
        default=None,
        description="Customer email (will be masked for PII)"
    )


class TicketMetadata(BaseModel):
    """Metadata for a ticket stored in vector DB."""

    ticket_id: str
    jira_key: Optional[str] = None
    title: str
    description: str
    category: str
    priority: str
    status: str = "open"
    resolution: Optional[str] = None
    created_at: str
    resolved_at: Optional[str] = None


# Priority to SLA hours mapping
PRIORITY_SLA_HOURS: dict[str, int] = {
    "P1": 4,
    "P2": 8,
    "P3": 24,
    "P4": 72,
}

# Priority names
PRIORITY_NAMES: dict[str, str] = {
    "P1": "Critical",
    "P2": "High",
    "P3": "Medium",
    "P4": "Low",
}

# Team routing suggestions by category
CATEGORY_ROUTING: dict[str, str] = {
    "Billing": "Finance Team",
    "Technical": "IT Support",
    "Account": "Account Team",
    "Feature Request": "Product Team",
    "General": "General Support",
}
