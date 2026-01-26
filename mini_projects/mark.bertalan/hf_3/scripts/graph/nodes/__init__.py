"""
RAG Graph Nodes.

Export all node functions and dependency setter.
"""

from scripts.graph.nodes.preprocess import preprocess_query_node
from scripts.graph.nodes.embedding import embed_query_node, set_embedder
from scripts.graph.nodes.retrieval import retrieve_chunks_node, set_vector_store
from scripts.graph.nodes.context import build_context_node
from scripts.graph.nodes.generation import generate_answer_node, set_llm as set_generation_llm
from scripts.graph.nodes.response import format_response_node

# Jira nodes
from scripts.graph.nodes.jira_detect import detect_jira_intent_node
from scripts.graph.nodes.jira_confirm import detect_jira_confirmation_node
from scripts.graph.nodes.jira_evaluate import evaluate_jira_need_node, set_llm as set_evaluation_llm
from scripts.graph.nodes.jira_extract import extract_jira_details_node, set_llm as set_extraction_llm
from scripts.graph.nodes.jira_create import create_jira_task_node, set_jira_config


def set_dependencies(embedder, vector_store, llm, jira_config=None):
    """
    Set service dependencies for all nodes.

    Args:
        embedder: Embedder implementation (e.g., OpenAIEmbeddingClient)
        vector_store: VectorDB implementation (e.g., ChromaVectorStore)
        llm: LLM implementation (e.g., OpenAILLMClient)
        jira_config: Optional Config object with Jira settings
    """
    set_embedder(embedder)
    set_vector_store(vector_store)
    set_generation_llm(llm)
    set_evaluation_llm(llm)
    set_extraction_llm(llm)
    if jira_config:
        set_jira_config(jira_config)


__all__ = [
    "preprocess_query_node",
    "embed_query_node",
    "retrieve_chunks_node",
    "build_context_node",
    "generate_answer_node",
    "format_response_node",
    "detect_jira_intent_node",
    "detect_jira_confirmation_node",
    "evaluate_jira_need_node",
    "extract_jira_details_node",
    "create_jira_task_node",
    "set_dependencies"
]
