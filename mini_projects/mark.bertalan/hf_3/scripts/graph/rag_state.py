"""
RAG State Schema for LangGraph.

This module defines the state structure that flows through the RAG graph nodes.
Each node reads from and writes to this shared state.
"""

from typing import TypedDict, List, Dict, Any, Optional, Tuple


class RAGState(TypedDict, total=False):
    """
    State schema for RAG query processing pipeline.

    Fields are marked as total=False to allow partial state initialization.
    Nodes incrementally populate fields as they execute.
    """

    # Input fields
    query: str  # User's question or search query
    k: int  # Number of results to retrieve
    max_tokens: int  # LLM response token limit
    skip_llm: bool  # If True, skip LLM generation (retrieval-only mode)

    # Conversation history
    conversation_history: List[Dict[str, str]]  # [{"role": "user/assistant", "content": "..."}]

    # Query processing
    query_id: str  # UUID for this query
    query_embedding: List[float]  # Embedding vector for the query
    query_chunks: List[Tuple[str, List[float]]]  # List of (chunk_text, embedding) tuples

    # Retrieval results
    cosine_results: List[Tuple[str, float, float, str, Dict[str, Any]]]  # (id, dist, sim, text, metadata)
    knn_results: List[Tuple[str, float, str, Dict[str, Any]]]  # (id, dist, text, metadata)
    retrieved_context: List[str]  # Text chunks to pass to LLM

    # LLM generation
    generated_answer: str  # Final response from LLM

    # Jira integration
    pending_jira_suggestion: Dict[str, str]  # Previous suggestion waiting for confirmation
    jira_confirmation_detected: bool  # If True, query is a yes/no response
    jira_suggested: bool  # If True, system suggests creating a Jira task
    jira_suggestion_reason: str  # Why the system suggests (or doesn't suggest) a ticket
    create_jira_task: bool  # If True, create a Jira task (set by user confirmation)
    jira_department: str  # Department for the task (hr, dev, support, management)
    jira_summary: str  # Task title/summary
    jira_description: str  # Task description
    jira_priority: str  # Task priority (High, Medium, Low)
    jira_task_key: str  # Created Jira task key (e.g., "HR-123")
    jira_task_url: str  # URL to the created Jira task

    # Metrics & observability
    step_timings: Dict[str, float]  # Timing for each node (in milliseconds)
    errors: List[str]  # Error messages collected during execution
