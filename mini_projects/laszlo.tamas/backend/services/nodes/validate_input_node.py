"""
Validate Input Node - Input validation and state preparation.

Validates:
- query not empty
- session_id present
- tenant_id and user_id in user_context
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.unified_chat_workflow import ChatState

logger = logging.getLogger(__name__)


def validate_input_node(state: "ChatState") -> "ChatState":
    """
    Node 1: Validate input parameters.
    
    Checks:
    - query not empty
    - session_id present
    - tenant_id and user_id present
    """
    logger.info("[NODE 1: validate_input] Validating input")
    
    try:
        query = state.get("query", "").strip()
        session_id = state.get("session_id", "").strip()
        user_ctx = state.get("user_context", {})
        
        if not query:
            from services.exceptions import ValidationError
            raise ValidationError(
                "Query cannot be empty",
                context={
                    "session_id": session_id,
                    "has_user_context": bool(user_ctx),
                    "operation": "validate_input"
                }
            )
        
        if not session_id:
            from services.exceptions import ValidationError
            raise ValidationError(
                "session_id is required",
                context={
                    "query_length": len(query) if query else 0,
                    "has_user_context": bool(user_ctx),
                    "operation": "validate_input"
                }
            )
        
        if not user_ctx.get("tenant_id"):
            from services.exceptions import ValidationError
            raise ValidationError(
                "tenant_id is required in user_context",
                context={
                    "session_id": session_id,
                    "query_length": len(query),
                    "user_context_keys": list(user_ctx.keys()),
                    "operation": "validate_input"
                }
            )
        
        if not user_ctx.get("user_id"):
            from services.exceptions import ValidationError
            raise ValidationError(
                "user_id is required in user_context",
                context={
                    "session_id": session_id,
                    "query_length": len(query),
                    "tenant_id": user_ctx.get("tenant_id"),
                    "user_context_keys": list(user_ctx.keys()),
                    "operation": "validate_input"
                }
            )
        
        logger.info(f"[NODE 1] Validation passed: query_len={len(query)}, session={session_id}, tenant={user_ctx['tenant_id']}, user={user_ctx['user_id']}")
        
        return state
    
    except Exception as e:
        logger.error(f"[NODE 1] Validation failed: {e}")
        return {
            **state,
            "error": str(e),
            "final_answer": f"Validation error: {str(e)}",
            "sources": []
        }
