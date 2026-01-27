"""
RAG Graph Builder.

Constructs and compiles the LangGraph for RAG query processing.
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Any
import logging

from scripts.graph.nodes import (
    preprocess_query_node,
    plan_query_node,
    embed_query_node,
    retrieve_chunks_node,
    build_context_node,
    generate_answer_node,
    format_response_node,
    detect_jira_confirmation_node,
    evaluate_jira_need_node,
    create_jira_task_node,
    send_teams_notification_node,
    set_dependencies
)

logger = logging.getLogger(__name__)


def create_rag_graph(embedder, vector_store, llm, jira_config=None, teams_config=None):
    """
    Create and compile the RAG query processing graph with Jira and Teams integration.

    This graph implements the following workflow:
    1. Preprocess query (validate, generate ID)
    2. Plan execution (orchestrate which nodes to run)
    3. Detect Jira confirmation (if pending suggestion exists)
    4. Embed query (generate embeddings)
    5. Retrieve chunks (dual search: cosine + KNN)
    6. Build context (extract text from results)
    7. Generate answer (with conversation history)
    8. Evaluate if Jira ticket should be suggested
    9. Create Jira ticket (if confirmed)
    10. Send Teams notification (if Jira created)
    11. Format response

    After the graph completes, if jira_suggested is True, main.py will
    offer the user the option to create a ticket.

    Args:
        embedder: Embedder implementation (e.g., OpenAIEmbeddingClient)
        vector_store: VectorDB implementation (e.g., ChromaVectorStore)
        llm: LLM implementation (e.g., OpenAILLMClient)
        jira_config: Optional Config object with Jira settings
        teams_config: Optional Config object with Teams settings

    Returns:
        Compiled LangGraph ready for execution
    """
    # Set dependencies for nodes
    set_dependencies(embedder, vector_store, llm, jira_config, teams_config)

    # Create state graph
    workflow = StateGraph(Dict[str, Any])

    # Add nodes
    workflow.add_node("preprocess", preprocess_query_node)
    workflow.add_node("plan", plan_query_node)
    workflow.add_node("detect_confirmation", detect_jira_confirmation_node)
    workflow.add_node("create_jira", create_jira_task_node)
    workflow.add_node("send_teams", send_teams_notification_node)
    workflow.add_node("embed", embed_query_node)
    workflow.add_node("retrieve", retrieve_chunks_node)
    workflow.add_node("build_context", build_context_node)
    workflow.add_node("generate", generate_answer_node)
    workflow.add_node("evaluate_jira", evaluate_jira_need_node)
    workflow.add_node("format", format_response_node)

    # Define edges
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "plan")
    workflow.add_edge("plan", "detect_confirmation")

    # Conditional routing after confirmation detection (uses planner decisions)
    workflow.add_conditional_edges(
        "detect_confirmation",
        route_after_confirmation,
        {
            "create_jira": "create_jira",  # User said yes
            "format": "format",             # User said no or planner says skip RAG
            "rag_flow": "embed",            # Normal RAG flow
            "direct_answer": "generate"     # Skip retrieval, go straight to LLM
        }
    )

    # Jira creation path -> Teams notification -> format
    workflow.add_edge("create_jira", "send_teams")
    workflow.add_edge("send_teams", "format")

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

    This function uses the planner's decisions to determine the execution path.

    Args:
        state: Current RAG state with planner decisions

    Returns:
        "create_jira" if user confirmed Jira
        "format" if user declined Jira or planner says skip everything
        "direct_answer" if planner says skip retrieval but use LLM
        "rag_flow" if normal RAG flow needed
    """
    # First check if this is a Jira confirmation
    if state.get("jira_confirmation_detected", False):
        if state.get("create_jira_task", False):
            # User said yes, create ticket
            logger.info("Routing: User confirmed Jira → create_jira")
            return "create_jira"
        else:
            # User said no, skip to format
            logger.info("Routing: User declined Jira → format")
            return "format"

    # Not a confirmation, check planner's decisions
    plan_needs_rag = state.get("plan_needs_rag", True)
    plan_intent = state.get("plan_intent", "search")
    execution_plan = state.get("execution_plan", {})

    logger.info(f"Routing: plan_needs_rag={plan_needs_rag}, plan_intent={plan_intent}")

    # If planner says we don't need RAG at all
    if not plan_needs_rag:
        logger.info("Routing: Planner says skip RAG → format")
        # Set a flag so format node knows to generate a simple response
        state["skip_retrieval"] = True
        return "format"

    # Check if planner wants to skip retrieval but still use LLM
    parameters = execution_plan.get("parameters", {})
    skip_retrieval = parameters.get("skip_retrieval", False)

    if skip_retrieval:
        logger.info("Routing: Planner says skip retrieval, direct to LLM → direct_answer")
        state["skip_retrieval"] = True
        return "direct_answer"

    # Normal RAG flow
    logger.info("Routing: Normal RAG flow → embed")
    return "rag_flow"


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
