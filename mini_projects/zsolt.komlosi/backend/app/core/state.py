"""
Agent state definition for LangGraph.
"""

from typing import Annotated, Optional, TypedDict, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State for the SupportAI LangGraph agent.
    Extended from HF1 with RAG and memory fields.
    """

    # Messages (for LangGraph message handling)
    messages: Annotated[list[BaseMessage], add_messages]

    # Input
    ticket_text: str
    ip_address: Optional[str]
    session_id: str
    customer_name: Optional[str]

    # Triage analysis results
    language: Optional[str]
    sentiment: Optional[str]
    category: Optional[str]
    subcategory: Optional[str]
    priority: Optional[str]
    routing: Optional[str]
    confidence: Optional[float]

    # Location data
    location_info: Optional[dict]
    holidays: Optional[list]

    # SLA data
    sla_info: Optional[dict]

    # RAG fields
    query_original: Optional[str]
    query_expanded: Optional[list[str]]
    query_english: Optional[str]
    retrieved_documents: Optional[list[dict]]
    reranked_documents: Optional[list[dict]]

    # Answer generation
    answer_draft: Optional[dict]
    citations: Optional[list[dict]]

    # Policy check
    policy_check: Optional[dict]

    # Similar tickets (optional feature)
    similar_tickets: Optional[list[dict]]

    # Memory
    rolling_summary: Optional[str]
    conversation_history: Optional[list[dict]]

    # PII
    pii_filtered: Optional[bool]
    pii_matches: Optional[list[dict]]

    # Output
    final_response: Optional[dict]

    # Metadata
    retry_count: int
    top_score: Optional[float]
