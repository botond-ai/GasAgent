"""
DEPRECATED - Old Workflow Node Implementations

This file contains the old manual routing-based workflow nodes that were
replaced by the LangGraph ToolNode pattern refactoring.

Kept for reference and potential reuse of specific logic.

DO NOT IMPORT OR USE THESE FUNCTIONS IN PRODUCTION CODE.

Refactored on: 2026-01-16
Reason: Migration to LangGraph ToolNode + tool_calls pattern
New implementation: unified_chat_workflow.py (agent_decide with llm_with_tools)
"""

import logging
import time
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from services.embedding_service import GenerateEmbeddingRequest
from services.qdrant_service import SearchLongTermMemoriesRequest

logger = logging.getLogger(__name__)


# ===== DEPRECATED ROUTING DECISIONS =====

def _make_initial_decision_DEPRECATED(self, state: "ChatState") -> str:
    """
    DEPRECATED: Old LLM-based routing decision.
    
    Replaced by: agent_decide node with tool_calls generation
    """
    # ... full implementation kept for reference only
    pass


def _make_continuation_decision_DEPRECATED(self, state: "ChatState") -> str:
    """
    DEPRECATED: Old continuation decision logic.
    
    Replaced by: agent_decide loop with tool execution results
    """
    return "FINAL_ANSWER"


def _route_from_agent_decide_DEPRECATED(self, state: "ChatState") -> str:
    """
    DEPRECATED: Old manual routing logic.
    
    Replaced by: _should_continue() with tool_calls detection
    """
    pass


def _route_after_tool_execution_DEPRECATED(self, state: "ChatState") -> str:
    """
    DEPRECATED: Old post-tool routing.
    
    Replaced by: ToolNode automatic routing back to agent_decide
    """
    pass


# ===== DEPRECATED EXECUTION NODES =====

def _direct_chat_node_DEPRECATED(self, state: "ChatState") -> "ChatState":
    """
    DEPRECATED: Old direct chat execution.
    
    Replaced by: LLM with tool_calls (no tools = direct answer)
    """
    pass


def _tool_executor_node_DEPRECATED(self, state: "ChatState") -> "ChatState":
    """
    DEPRECATED: Old manual tool orchestration.
    
    Replaced by: LangGraph ToolNode with automatic parallel execution
    """
    pass


# ===== DEPRECATED RAG PIPELINE NODES =====

def _enrich_chunks_node_DEPRECATED(self, state: "ChatState") -> "ChatState":
    """
    DEPRECATED: Old chunk enrichment node.
    
    May be reused in future for RAG-specific processing.
    """
    pass


def _generate_answer_node_DEPRECATED(self, state: "ChatState") -> "ChatState":
    """
    DEPRECATED: Old answer generation node.
    
    May be reused in future for RAG-specific processing.
    """
    pass


def _combine_hybrid_results_DEPRECATED(
    self,
    vector_results: List[Dict],
    keyword_results: List[Dict],
    vector_weight: float,
    keyword_weight: float
) -> List[Dict]:
    """
    DEPRECATED: Old hybrid search combination.
    
    May be reused as utility function for RAG improvements.
    """
    pass


# ===== DEPRECATED LONG-TERM MEMORY NODES =====

def _ltm_read_node_DEPRECATED(self, state: "ChatState") -> "ChatState":
    """
    DEPRECATED: Old LTM read node.
    
    May be converted to tool for future integration.
    """
    pass


def _ltm_write_node_DEPRECATED(self, state: "ChatState") -> "ChatState":
    """
    DEPRECATED: Old LTM write node.
    
    May be converted to tool for future integration.
    """
    pass


# ===== DEPRECATED HELPER FUNCTIONS =====

def _generate_answer_from_chunks_DEPRECATED(
    self,
    query: str,
    chunks: List["DocumentChunk"],
    system_prompt: str,
    user_lang: str
) -> str:
    """
    DEPRECATED: Old chunk-based answer generation.
    
    May be reused in RAG tool implementations.
    """
    pass


def _generate_no_documents_fallback_DEPRECATED(
    self,
    query: str,
    system_prompt: str,
    user_lang: str
) -> str:
    """
    DEPRECATED: Old fallback response generation.
    
    May be reused in RAG tool implementations.
    """
    pass


# ===== END OF DEPRECATED CODE =====

"""
MIGRATION NOTES:

1. Routing Decision → LLM Tool Calls
   Old: _make_initial_decision() returns string "CHAT"|"RAG"|"LIST"
   New: agent_decide generates AIMessage.tool_calls

2. Tool Execution → ToolNode
   Old: _tool_executor_node() manually calls tools
   New: ToolNode automatically handles parallel execution

3. State Tracking → tools_called
   Old: intermediate_results, actions_taken
   New: tools_called (Annotated reducer), messages

4. Multi-Step → Agent Loop
   Old: _make_continuation_decision()
   New: agent_decide inspects tools_called and decides next action

5. RAG/LTM Nodes → Future Tool Integration
   Old: Dedicated nodes (_enrich_chunks_node, _ltm_read_node, etc.)
   New: Will be converted to tools callable by LLM via tool_calls
"""
