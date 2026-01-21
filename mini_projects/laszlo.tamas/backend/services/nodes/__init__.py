"""Knowledge Router workflow nodes.

IMPORTANT: Only simple stateless nodes are extracted here.
Complex nodes (agent_decide, agent_finalize, agent_error_handler) remain 
in unified_chat_workflow.py as closures for dependency injection.

SOLID REFACTOR: Context building split into 4 sequential nodes:
- fetch_tenant_context_node
- fetch_user_context_node
- fetch_chat_history_node
- build_system_prompt_node (imported dynamically to avoid circular deps)
"""

from .validate_input_node import validate_input_node
from .query_rewrite_node import query_rewrite_node
from .fetch_tenant_context_node import fetch_tenant_context_node
from .fetch_user_context_node import fetch_user_context_node
from .fetch_chat_history_node import fetch_chat_history_node

__all__ = [
    "validate_input_node",
    "query_rewrite_node",
    "fetch_tenant_context_node",
    "fetch_user_context_node",
    "fetch_chat_history_node",
]
