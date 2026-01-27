"""
RAG Graph Builder.

Constructs and compiles the LangGraph for RAG query processing.
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Any
import logging

from scripts.graph.nodes import (
    preprocess_query_node,
    embed_query_node,
    retrieve_chunks_node,
    build_context_node,
    generate_answer_node,
    format_response_node,
    detect_jira_confirmation_node,
    evaluate_jira_need_node,
    create_jira_task_node,
    set_dependencies
)

logger = logging.getLogger(__name__)


def create_rag_graph(embedder, vector_store, llm, jira_config=None):
    """
    Create and compile the RAG query processing graph with Jira suggestion.

    This graph implements the following workflow:
    1. Preprocess query (validate, generate ID)
    2. Embed query (generate embeddings)
    3. Retrieve chunks (dual search: cosine + KNN)
    4. Build context (extract text from results)
    5. Generate answer (with conversation history)
    6. Evaluate if Jira ticket should be suggested
    7. Format response

    After the graph completes, if jira_suggested is True, main.py will
    offer the user the option to create a ticket.

    Args:
        embedder: Embedder implementation (e.g., OpenAIEmbeddingClient)
        vector_store: VectorDB implementation (e.g., ChromaVectorStore)
        llm: LLM implementation (e.g., OpenAILLMClient)
        jira_config: Optional Config object with Jira settings

    Returns:
        Compiled LangGraph ready for execution
    """
    # Set dependencies for nodes
    set_dependencies(embedder, vector_store, llm, jira_config)

    # Create state graph
    workflow = StateGraph(Dict[str, Any])

    # Add nodes
    workflow.add_node("preprocess", preprocess_query_node)
    workflow.add_node("detect_confirmation", detect_jira_confirmation_node)
    workflow.add_node("create_jira", create_jira_task_node)
    workflow.add_node("embed", embed_query_node)
    workflow.add_node("retrieve", retrieve_chunks_node)
    workflow.add_node("build_context", build_context_node)
    workflow.add_node("generate", generate_answer_node)
    workflow.add_node("evaluate_jira", evaluate_jira_need_node)
    workflow.add_node("format", format_response_node)

    # Define edges
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "detect_confirmation")

    # Conditional routing after confirmation detection
    workflow.add_conditional_edges(
        "detect_confirmation",
        route_after_confirmation,
        {
            "create_jira": "create_jira",  # User said yes
            "format": "format",             # User said no
            "rag_flow": "embed"            # Not a yes/no, continue normal RAG
        }
    )

    # Jira creation path
    workflow.add_edge("create_jira", "format")

    # Normal RAG flow
    workflow.add_edge("embed", "retrieve")
    workflow.add_edge("retrieve", "build_context")

    # Conditional routing after context building
    workflow.add_conditional_edges(
        "build_context",
        should_generate_answer,
        {
            "generate": "generate",
            "format": "format"
        }
    )

    # After generation, evaluate if Jira ticket should be suggested
    workflow.add_edge("generate", "evaluate_jira")
    workflow.add_edge("evaluate_jira", "format")
    workflow.add_edge("format", END)

    # Compile graph
    compiled_graph = workflow.compile()
    logger.info("RAG graph compiled successfully")

    return compiled_graph


def route_after_confirmation(state: Dict[str, Any]) -> str:
    """
    Conditional routing after Jira confirmation detection.

    Args:
        state: Current RAG state

    Returns:
        "create_jira" if user confirmed, "format" if declined, "rag_flow" if not a confirmation
    """
    if not state.get("jira_confirmation_detected", False):
        # Not a yes/no response, continue with normal RAG
        return "rag_flow"

    if state.get("create_jira_task", False):
        # User said yes, create ticket
        return "create_jira"
    else:
        # User said no, skip to format
        return "format"


def should_generate_answer(state: Dict[str, Any]) -> str:
    """
    Conditional routing: determine if we should generate answer or skip to formatting.

    Args:
        state: Current RAG state

    Returns:
        "generate" to generate answer, "format" to skip to formatting
    """
    if state.get("skip_llm", False):
        return "format"
    return "generate"
