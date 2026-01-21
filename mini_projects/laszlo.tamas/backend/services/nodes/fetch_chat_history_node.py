"""
Fetch Chat History Node - Retrieves conversation history.
"""
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.workflow_schemas import ChatState, ContextData

logger = logging.getLogger(__name__)


def fetch_chat_history_node(state: "ChatState", config) -> "ChatState":
    """
    Node 2c: Fetch chat history (configurable short-term memory).
    
    Args:
        state: Current workflow state
        config: Config service instance
    
    Returns:
        Updated state with chat_history
    """
    start_time = time.time()
    logger.info("[NODE 2c: fetch_chat_history] Fetching chat history")
    
    try:
        user_ctx = state["user_context"]
        session_id = state["session_id"]
        
        short_term_limit = config.get_int('memory', 'SHORT_TERM_MEMORY_MESSAGES', default=30)
        short_term_scope = config.get('memory', 'SHORT_TERM_MEMORY_SCOPE', default='session').lower()
        
        history_start = time.time()
        if short_term_scope == 'user':
            from database.pg_init import get_last_messages_for_user_pg
            messages = get_last_messages_for_user_pg(
                user_id=user_ctx["user_id"], tenant_id=user_ctx["tenant_id"], limit=short_term_limit
            )
        else:
            from database.pg_init import get_session_messages_pg
            messages = get_session_messages_pg(
                session_id=session_id, limit=short_term_limit
            )
        
        # Convert to simple format: [{role, content}]
        chat_history = [
            {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            for msg in messages
        ]
        
        total_time = time.time() - start_time
        logger.info(f"✅ [NODE 2c: fetch_chat_history] {len(chat_history)} messages in {total_time:.2f}s")
        
        # Update nested ContextData structure
        existing_context = state.get("context", {})
        if existing_context is None:
            existing_context = {}
        
        updated_context: "ContextData" = {
            **existing_context,
            "chat_history": messages
        }
        
        return {
            **state,
            "context": updated_context
        }
    
    except Exception as e:
        logger.error(f"[NODE 2c] Chat history fetch failed: {e}", exc_info=True)
        
        # Update nested ContextData structure (error case)
        existing_context = state.get("context", {})
        if existing_context is None:
            existing_context = {}
        
        updated_context: "ContextData" = {
            **existing_context,
            "chat_history": []
        }
        
        return {
            **state,
            "context": updated_context,
            "error": f"Chat history fetch error: {str(e)}"
        }
