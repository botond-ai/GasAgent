"""
Build System Prompt Node - Prepares context for prompt building.

ARCHITECTURE NOTE (2026-01-20):
This node ONLY prepares the context (extracts tenant/user prompts, updates user_context).
The ACTUAL prompt building happens in agent_decide_node for cache optimization.
This ensures OpenAI Prompt Cache can work properly with identical prefix.
"""
import logging
import time
from typing import TYPE_CHECKING, Optional, Dict, Any, Tuple

if TYPE_CHECKING:
    from services.workflow_schemas import ChatState, ContextData

logger = logging.getLogger(__name__)


def build_system_prompt_node(
    state: "ChatState",
    get_or_build_prompt_fn  # DEPRECATED: Not used anymore, kept for backward compatibility
) -> "ChatState":
    """
    Node 2d: Prepare context for system prompt building.
    
    REFACTORED (2026-01-20):
    - This node NO LONGER builds the prompt
    - It only extracts and prepares context data
    - Actual prompt building moved to agent_decide_node for cache optimization
    
    Prepares:
    - Tenant-level prompt extraction
    - User-level prompt extraction
    - User context enrichment (firstname, lastname, email, role)
    
    Args:
        state: Current workflow state (must have tenant_data, user_data, user_context)
        get_or_build_prompt_fn: DEPRECATED - kept for backward compatibility
    
    Returns:
        Updated state with enriched user_context (prompt building deferred to agent_decide)
    """
    start_time = time.time()
    logger.info("[NODE 2d: build_system_prompt] Preparing context for prompt building")
    
    try:
        user_ctx = state["user_context"]
        
        # Read from nested ContextData structure
        context_data = state.get("context", {})
        tenant_data = context_data.get("tenant_data")
        user_data = context_data.get("user_data")
        
        # Extract prompts
        tenant_prompt = tenant_data.get("system_prompt") if tenant_data else None
        user_prompt = user_data.get("system_prompt") if user_data else None
        user_language = user_data.get("default_lang", "en") if user_data else "en"
        
        # Update user_context with extracted info (used by agent_decide_node)
        updated_user_ctx = {
            **user_ctx,
            "tenant_prompt": tenant_prompt,
            "user_prompt": user_prompt,
            "user_language": user_language,
            "firstname": user_data.get("firstname") if user_data else None,
            "lastname": user_data.get("lastname") if user_data else None,
            "email": user_data.get("email") if user_data else None,
            "role": user_data.get("role") if user_data else None
        }
        
        total_time = time.time() - start_time
        logger.info(
            f"✅ [NODE 2d: build_system_prompt] Context prepared in {total_time:.2f}s "
            f"(prompt building deferred to agent_decide)"
        )
        
        # Update nested ContextData structure - NO system_prompt here anymore
        # system_prompt will be built in agent_decide_node
        existing_context = state.get("context", {})
        if existing_context is None:
            existing_context = {}
        
        updated_context: "ContextData" = {
            **existing_context,
            # Mark that context is ready for prompt building
            "prompt_context_ready": True,
            "system_prompt_cached": False,  # Will be determined in agent_decide
            "cache_source": "agent_decide"  # Prompt built in agent_decide
        }
        
        return {
            **state,
            "user_context": updated_user_ctx,
            "context": updated_context
        }
    
    except Exception as e:
        logger.error(f"[NODE 2d] Context preparation failed: {e}", exc_info=True)
        
        # Update nested ContextData structure (error case)
        existing_context = state.get("context", {})
        if existing_context is None:
            existing_context = {}
        
        updated_context: "ContextData" = {
            **existing_context,
            "prompt_context_ready": False,
            "system_prompt_cached": False,
            "cache_source": "error"
        }
        
        return {
            **state,
            "context": updated_context,
            "error": f"Context preparation error: {str(e)}"
        }
