"""
Query Rewrite Node - Semantic expansion and intent classification.

PASSTHROUGH PATTERN: Always runs, but performs noop if disabled.

Feature flags:
- Config: system.ini [features] QUERY_REWRITE_ENABLED
- Runtime: state["query_rewrite_enabled"] (API override for A/B testing)
"""
import logging
import time
import json
import re
from typing import TYPE_CHECKING, Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage

if TYPE_CHECKING:
    from services.workflow_schemas import ChatState
    from services.workflow_schemas import QueryRewriteResult

logger = logging.getLogger(__name__)


def format_chat_history_for_rewrite(messages: List[Dict[str, str]]) -> str:
    """
    Format recent chat history for query rewrite prompt context.
    
    Args:
        messages: Last N messages from chat history
    
    Returns:
        Formatted string for prompt injection
    """
    if not messages:
        return "(nincs előzmény)"
    
    formatted = []
    for msg in messages:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "").strip()
        if content:
            formatted.append(f'{role}: "{content}"')
    
    return "\n".join(formatted) if formatted else "(nincs előzmény)"


def parse_query_rewrite_response(content: str, original_query: str) -> Dict[str, Any]:
    """
    Parse LLM JSON response for query rewrite.
    
    Handles:
    - Code fence stripping
    - JSON parsing with error recovery
    - Schema validation
    - Fallback values
    
    Args:
        content: LLM response content (potentially wrapped in markdown)
        original_query: Fallback query if parsing fails
    
    Returns:
        Dict with keys: rewritten_query, intent, reasoning, transformations
    """
    try:
        # Strip markdown code fences
        content = content.strip()
        if content.startswith("```"):
            # Extract JSON from code block
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                # Remove language identifier (e.g., "json")
                if content.startswith("json"):
                    content = content[4:]
        
        # Parse JSON
        result = json.loads(content.strip())
        
        # Validate required fields
        if "rewritten_query" not in result:
            logger.warning("[parse_rewrite] Missing 'rewritten_query', using original")
            result["rewritten_query"] = original_query
        
        if "intent" not in result:
            logger.warning("[parse_rewrite] Missing 'intent', defaulting to 'search_knowledge'")
            result["intent"] = "search_knowledge"
        
        # Ensure transformations is a list
        if "transformations" in result and not isinstance(result["transformations"], list):
            result["transformations"] = []
        
        return result
        
    except json.JSONDecodeError as e:
        logger.warning(f"[parse_rewrite] JSON parse failed: {e}, attempting text extraction")
        
        # Fallback: Extract rewritten query from text (last resort)
        match = re.search(r'"rewritten_query":\s*"([^"]+)"', content)
        if match:
            rewritten = match.group(1)
            logger.info(f"[parse_rewrite] Extracted via regex: {rewritten}")
            return {
                "rewritten_query": rewritten,
                "intent": "search_knowledge",
                "reasoning": "Extracted from malformed JSON",
                "transformations": []
            }
        
        # Ultimate fallback: use original query
        logger.error(f"[parse_rewrite] All parsing attempts failed, using original query")
        return {
            "rewritten_query": original_query,
            "intent": "search_knowledge",
            "reasoning": "Parse failed, using original query",
            "transformations": []
        }


def query_rewrite_node(state: "ChatState", config, invoke_llm_fn) -> "ChatState":
    """
    Node 1.5: Query Rewrite - Semantic expansion + intent classification.
    
    Args:
        state: Current workflow state
        config: Config service instance
        invoke_llm_fn: LLM invocation function with retry logic
    
    Returns:
        Updated state with rewritten query
    """
    node_start = time.time()
    logger.info("[NODE 1.5: query_rewrite] Starting query rewrite node")
    
    try:
        # Check feature flags: config AND runtime override
        config_enabled = config.get_query_rewrite_enabled()
        runtime_override = state.get("query_rewrite_enabled")  # None, True, or False
        
        # Runtime override takes precedence if explicitly set
        enabled = runtime_override if runtime_override is not None else config_enabled
        
        if not enabled:
            # PASSTHROUGH: Feature disabled
            duration_ms = int((time.time() - node_start) * 1000)
            logger.info(
                "[NODE 1.5] Query rewrite SKIPPED (disabled)",
                extra={
                    "config_enabled": config_enabled,
                    "runtime_override": runtime_override,
                    "session_id": state.get("session_id"),
                    "duration_ms": duration_ms
                }
            )
            
            # Return NESTED QueryRewriteResult structure
            query_rewrite_result: "QueryRewriteResult" = {
                "rewritten_query": state["query"],  # Identity transformation
                "original_query": state["query"],
                "intent": "search_knowledge",  # Default assumption
                "transformations": [],
                "reasoning": "Query rewrite disabled by feature flag",
                "skipped": True,
                "duration_ms": duration_ms
            }
            
            return {
                **state,
                "query_rewrite": query_rewrite_result
            }
        
        # ACTIVE PATH: Perform LLM-based rewrite
        logger.info("[NODE 1.5] Query rewrite ACTIVE - invoking light LLM")
        
        # Format chat history (last 3 messages for context)
        chat_history = state.get("chat_history", [])
        formatted_history = format_chat_history_for_rewrite(chat_history[-3:] if chat_history else [])
        
        # Get language from user context
        user_language = state.get("user_context", {}).get("user_language", "en")
        
        # Build prompt
        from config.prompts import QUERY_REWRITE_PROMPT
        prompt = QUERY_REWRITE_PROMPT.format(
            chat_history=formatted_history,
            query=state["query"],
            language=user_language
        )
        
        # LLM invocation (light model for cost optimization)
        messages = [
            SystemMessage(content="You are a query optimization assistant for a RAG knowledge base. Return JSON only."),
            HumanMessage(content=prompt)
        ]
        
        try:
            # Use light model with retry protection
            response = invoke_llm_fn(
                messages=messages,
                state=state,
                use_light=True  # Explicitly use lightweight model
            )
            
            # Parse JSON response
            result = parse_query_rewrite_response(response.content, state["query"])
            
            duration_ms = int((time.time() - node_start) * 1000)
            
            logger.info(
                "[NODE 1.5] Query rewrite SUCCESS",
                extra={
                    "original_query": state["query"],
                    "rewritten_query": result["rewritten_query"],
                    "intent": result.get("intent", "unknown"),
                    "transformations_count": len(result.get("transformations", [])),
                    "duration_ms": duration_ms,
                    "session_id": state.get("session_id")
                }
            )
            
            # Return NESTED QueryRewriteResult structure
            query_rewrite_result: "QueryRewriteResult" = {
                "rewritten_query": result["rewritten_query"],
                "original_query": state["query"],
                "intent": result.get("intent"),
                "transformations": result.get("transformations", []),
                "reasoning": result.get("reasoning"),
                "skipped": False,
                "duration_ms": duration_ms
            }
            
            return {
                **state,
                "query_rewrite": query_rewrite_result
            }
            
        except Exception as e:
            # LLM invocation failed → fallback to passthrough
            duration_ms = int((time.time() - node_start) * 1000)
            logger.error(
                f"[NODE 1.5] Query rewrite FAILED, falling back to passthrough: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "session_id": state.get("session_id"),
                    "duration_ms": duration_ms
                }
            )
            
            # Return NESTED QueryRewriteResult structure (fallback)
            query_rewrite_result: "QueryRewriteResult" = {
                "rewritten_query": state["query"],  # Fallback: use original
                "original_query": state["query"],
                "intent": "search_knowledge",
                "transformations": [],
                "reasoning": f"Rewrite failed: {str(e)}, using original query",
                "skipped": True,
                "duration_ms": duration_ms
            }
            
            return {
                **state,
                "query_rewrite": query_rewrite_result
            }
    
    except Exception as e:
        # Unexpected error in node logic
        duration_ms = int((time.time() - node_start) * 1000)
        logger.error(f"[NODE 1.5] Query rewrite node error: {e}", exc_info=True)
        
        # Return NESTED QueryRewriteResult structure (error fallback)
        query_rewrite_result: "QueryRewriteResult" = {
            "rewritten_query": state["query"],
            "original_query": state["query"],
            "intent": "search_knowledge",
            "transformations": [],
            "reasoning": f"Node error: {str(e)}",
            "skipped": True,
            "duration_ms": duration_ms
        }
        
        return {
            **state,
            "query_rewrite": query_rewrite_result
        }
