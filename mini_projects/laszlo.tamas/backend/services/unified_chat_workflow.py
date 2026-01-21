"""
Unified Chat Workflow - ToolNode-based agent with LangGraph.

LLM-driven tool calling workflow using LangGraph's official ToolNode pattern.
The agent decides which tools to call, ToolNode executes them automatically.

Architecture (REFACTORED - ToolNode Pattern):
START → validate_input → combine_context → agent_decide
  ├─ tool_calls detected? → tools (ToolNode) → agent_decide (loop)
  └─ no tool_calls? → agent_finalize → END

Pattern: Prompt → Tool Calls (AIMessage) → ToolNode Execution → Observation → Loop

Tools (Layer 3):
- generate_embedding: Text vectorization
- search_vectors: Qdrant semantic search
- search_fulltext: PostgreSQL fulltext search
- list_documents: Document inventory
"""

import logging
import time
import json
import uuid
import asyncio  # CRITICAL FIX 1.1: Required for asyncio.create_task() in closures
import threading  # Required for background logging from sync context
import copy  # For deep copying state snapshots
from pathlib import Path
import httpx
from datetime import datetime
from typing import List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage, BaseMessage

from services.embedding_service import EmbeddingService
from services.qdrant_service import QdrantService
from services.config_service import get_config_service
from services.cache_service import get_context_cache
from services.knowledge_tools import create_knowledge_tools
from services.excel_tools import EXCEL_TOOLS
from services.retry_helper import retry_with_backoff, retry_on_rate_limit
from services.workflow_tracking_config_service import workflow_tracking_config_service
from services.openai_chat_client import OpenAIChatClient
from services.exceptions import (
    ServiceError, QdrantServiceError, EmbeddingServiceError, 
    DatabaseError, WorkflowError
)
from database.document_chunk_repository import DocumentChunkRepository
from database.repositories.workflow_tracking_repository import workflow_tracking_repo
from database.pg_init import (
    get_tenant_by_id, 
    get_user_by_id_pg,
    get_latest_cached_prompt,
    save_cached_prompt,
    get_session_messages_pg
)
from config.prompts import build_system_prompt, APPLICATION_SYSTEM_PROMPT

# Import node functions from separate files (clean architecture)
from services.nodes import (
    validate_input_node,
    query_rewrite_node,
    fetch_tenant_context_node,
    fetch_user_context_node,
    fetch_chat_history_node
    # build_system_prompt_node imported dynamically in closure
)

# Import new schemas (WORKFLOW_REFACTOR_PLAN Step 1.2)
from services.workflow_schemas import (
    ChatState,
    UserContext,
    DocumentChunk,
    QueryRewriteResult,
    SearchResult,
    ReflectionResult,
    ContextData,
    AgentControl,
    TelemetryData
)
from services.state_helpers import (
    get_query_rewrite,
    get_rewritten_query,
    get_agent_iteration,
    get_search_chunks,
    serialize_state_for_db,
    export_telemetry
)

logger = logging.getLogger(__name__)

# Safety: Maximum agent iterations to prevent infinite loops
MAX_ITERATIONS = 10


# ===== UNIFIED CHAT WORKFLOW =====

class UnifiedChatWorkflow:
    """
    LangGraph workflow with ToolNode for automatic tool execution.
    
    Architecture (ToolNode Pattern):
    START → validate_input → combine_context → agent_decide
      ├─ tool_calls? → tools (ToolNode) → agent_decide (loop)
      └─ no tools? → agent_finalize → END
    
    Key Components:
    - validate_input: State preparation & validation
    - combine_context: System prompt building with cache
    - agent_decide: LLM reasoning with tool_calls generation
    - tools: ToolNode (automatic parallel tool execution)
    - agent_finalize: Extract final answer from conversation
    
    Pattern Compliance:
    ✓ Pydantic input schemas on all tools
    ✓ LLM generates AIMessage.tool_calls
    ✓ ToolNode executes → ToolMessage observations
    ✓ State reducer: messages (add), tools_called (add)
    """
    
    def __init__(self, openai_api_key: str):
        self.config = get_config_service()
        self.openai_api_key = openai_api_key
        
        # Initialize services using DI container (singleton reuse)
        from core.dependencies import get_embedding_service, get_qdrant_service, get_document_chunk_repository
        
        self.embedding_service = get_embedding_service()
        self.qdrant_service = get_qdrant_service()
        self.chunk_repo = get_document_chunk_repository()
        
        # Initialize OpenAI HTTP client (outbound payload logging)
        self._init_openai_http_client()

        # Native OpenAI client (bypass LangChain for cache accuracy)
        self._use_native_openai_client = self.config.get_bool(
            'llm',
            'USE_NATIVE_OPENAI_CLIENT',
            default=False
        )
        self._openai_client = OpenAIChatClient(
            api_key=self.openai_api_key,
            timeout=self.config.get_openai_timeout(),
            http_client=self._openai_http_client
        )

        # Initialize Model Pool - Context-specific LLM optimization
        self._init_llm_pool()
        
        # Backward compatibility (deprecated, use specific contexts)
        self.llm = self.llm_heavy_rag  # Default to RAG context
        self.llm_heavy = self.llm_heavy_rag  # Backward compatibility
        self.llm_light = self.llm_light_chat  # Backward compatibility
        
        # Set to True to re-enable reflection node (1-minute rollback)
        self.reflection_enabled = False  # DEPRECATED: Use natural LLM self-correction
        
        # WORKFLOW_REFACTOR_PLAN Step 3: State accessor for tools (DI pattern)
        self._current_state = None  # Thread-safe current state reference
        
        def state_accessor():
            """Provide current state to tools (SOLID DIP compliance)."""
            if self._current_state is None:
                raise RuntimeError("No active workflow execution - state accessor called outside workflow")
            return self._current_state
        
        # Create knowledge tools with state accessor (Layer 3: Tool Execution Layer)
        knowledge_tools = create_knowledge_tools(state_accessor)
        
        # Add Excel MCP tools (external tool integration)
        all_tools = knowledge_tools + EXCEL_TOOLS
        
        self.tools = all_tools
        # FIXED: Use plain ToolNode directly instead of TrackedToolNode
        self.tool_node = ToolNode(self.tools)
        logger.info(f"Initialized {len(knowledge_tools)} knowledge tools + {len(EXCEL_TOOLS)} Excel tools = {len(all_tools)} total tools")
        
        # Bind tools to router-context LLM (cost-optimized, deterministic tool selection)
        self.llm_light_with_tools = self.llm_light_router.bind_tools(self.tools)
        logger.info(f"Router LLM bound with {len(self.tools)} tools for tool calling")
        
        # Bind tools to heavy LLM (backup, for complex reasoning if needed)
        self.llm_heavy_with_tools = self.llm_heavy_rag.bind_tools(self.tools)
        
        # Backward compatibility
        self.llm_with_tools = self.llm_light_with_tools
        
        # Build workflow graph
        self.graph = self._build_graph()
        
        # Store LLM messages per session for prompt inspection (outside state to avoid validation errors)
        self._llm_messages_by_session = {}
        # Store LLM payload details per session (tools + extra_body)
        self._llm_payload_by_session = {}
        # Store LLM usage details per session (cache metrics fallback)
        self._llm_usage_by_session = {}

        # Thread-local correlation for outbound HTTP payload logging
        self._http_request_context = threading.local()
        
        # WebSocket state broadcasting (optional, enabled per session)
        self._enable_ws_broadcast = {}  # session_id -> bool
        
        logger.info(
            f"UnifiedChatWorkflow initialized with dual-model architecture: "
            f"Heavy={self.config.get_heavy_model()}, Light={self.config.get_light_model()}"
        )
        
    def _init_llm_pool(self):
        """Initialize context-specific LLM pool for optimized performance.
        
        Model Pool Pattern:
        - LIGHT_CHAT: Conversational responses (balanced creativity)
        - LIGHT_ROUTER: Tool selection, routing (deterministic)
        - HEAVY_RAG: RAG synthesis (balanced accuracy)
        - HEAVY_BIG_THINK: Complex reasoning (very precise)
        """
        # Use the API key from __init__ parameter
        openai_api_key = self.openai_api_key
        
        # Light model contexts (gpt-4.1-mini)
        self.llm_light_chat = ChatOpenAI(
            model=self.config.get_light_model(),
            temperature=self.config.get_light_chat_temperature(),
            max_completion_tokens=self.config.get_light_chat_max_tokens(),
            api_key=openai_api_key,
            timeout=self.config.get_openai_timeout(),
            http_client=self._openai_http_client
        )
        
        self.llm_light_router = ChatOpenAI(
            model=self.config.get_light_model(),
            temperature=self.config.get_light_router_temperature(),
            max_completion_tokens=self.config.get_light_router_max_tokens(),
            api_key=openai_api_key,
            timeout=self.config.get_openai_timeout(),
            http_client=self._openai_http_client
        )
        
        # Heavy model contexts (gpt-4.1)
        self.llm_heavy_rag = ChatOpenAI(
            model=self.config.get_heavy_model(),
            temperature=self.config.get_heavy_rag_temperature(),
            max_completion_tokens=self.config.get_heavy_rag_max_tokens(),
            api_key=openai_api_key,
            timeout=self.config.get_openai_timeout(),
            http_client=self._openai_http_client
        )
        
        self.llm_heavy_big_think = ChatOpenAI(
            model=self.config.get_heavy_model(),
            temperature=self.config.get_heavy_big_think_temperature(),
            max_completion_tokens=self.config.get_heavy_big_think_max_tokens(),
            api_key=openai_api_key,
            timeout=self.config.get_openai_timeout(),
            http_client=self._openai_http_client
        )

    def _init_openai_http_client(self):
        """Initialize shared OpenAI HTTP client with outbound payload logging."""
        self._log_openai_payloads = self.config.get_bool(
            'debug',
            'LOG_OPENAI_OUTBOUND_PAYLOAD',
            default=False
        )

        def _log_request(request: httpx.Request):
            if not self._log_openai_payloads:
                return

            try:
                host = request.url.host or ""
                if "openai.com" not in host:
                    return

                body_bytes = request.content or b""
                body_text = body_bytes.decode("utf-8", errors="replace")

                try:
                    body_json = json.loads(body_text)
                except json.JSONDecodeError:
                    body_json = None

                session_id = getattr(self._http_request_context, "session_id", None)
                request_id = getattr(self._http_request_context, "request_id", None)

                log_record = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "session_id": session_id,
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "body": body_json if body_json is not None else body_text
                }

                debug_dir = Path(__file__).parent.parent / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                log_path = debug_dir / "openai_outbound_payload.jsonl"

                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(log_record, ensure_ascii=False) + "\n")
            except Exception as exc:
                logger.warning(f"[OPENAI_PAYLOAD] Failed to log outbound payload: {exc}")

        def _log_response(response: httpx.Response):
            if not self._log_openai_payloads:
                return

            try:
                host = response.request.url.host or ""
                if "openai.com" not in host:
                    return

                body_text = response.text
                try:
                    body_json = response.json()
                except Exception:
                    body_json = None

                session_id = getattr(self._http_request_context, "session_id", None)
                request_id = getattr(self._http_request_context, "request_id", None)

                log_record = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "session_id": session_id,
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "url": str(response.request.url),
                    "body": body_json if body_json is not None else body_text
                }

                debug_dir = Path(__file__).parent.parent / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                log_path = debug_dir / "openai_outbound_payload.jsonl"

                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"response": log_record}, ensure_ascii=False) + "\n")
            except Exception as exc:
                logger.warning(f"[OPENAI_PAYLOAD] Failed to log response: {exc}")

        self._openai_http_client = httpx.Client(event_hooks={"request": [_log_request], "response": [_log_response]})

    def _select_llm_for_context(self, context: str) -> ChatOpenAI:
        """Select appropriate LLM instance based on context.
        
        Args:
            context: 'chat', 'router', 'rag', 'big_think'
            
        Returns:
            Context-optimized ChatOpenAI instance
        """
        context_mapping = {
            'chat': self.llm_light_chat,
            'router': self.llm_light_router, 
            'rag': self.llm_heavy_rag,
            'big_think': self.llm_heavy_big_think
        }
        
        if context not in context_mapping:
            logger.warning(f"Unknown context '{context}', defaulting to RAG")
            return self.llm_heavy_rag
            
        return context_mapping[context]

    def _serialize_openai_messages(self, messages: List[BaseMessage], enable_cache: bool = False) -> List[Dict[str, Any]]:
        """Serialize LangChain messages to OpenAI-compatible dicts (incl. cache_control)."""
        serialized: List[Dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                role = "system"
            elif isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, ToolMessage):
                role = "tool"
            else:
                role = "user"

            msg_dict: Dict[str, Any] = {
                "role": role,
                "content": str(msg.content)
            }

            # Tool message correlation
            if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id

            # Mark system prefix as cacheable for OpenAI prompt cache
            if enable_cache and role == "system" and "cache_control" not in msg_dict:
                msg_dict["cache_control"] = {"type": "ephemeral"}

            # Cache control for system prefix (prompt caching)
            if enable_cache and role == "system" and "cache_control" not in msg_dict:
                msg_dict["cache_control"] = {"type": "ephemeral"}

            # Tool calls (assistant message)
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                normalized_tool_calls = []
                for tc in msg.tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    tc_id = tc.get("id")
                    tc_name = tc.get("name") or (tc.get("function") or {}).get("name")
                    tc_args = tc.get("args") or (tc.get("function") or {}).get("arguments")
                    if isinstance(tc_args, str):
                        args_str = tc_args
                    else:
                        try:
                            args_str = json.dumps(tc_args or {}, ensure_ascii=False)
                        except Exception:
                            args_str = "{}"

                    normalized_tool_calls.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": tc_name,
                            "arguments": args_str
                        }
                    })
                if normalized_tool_calls:
                    msg_dict["tool_calls"] = normalized_tool_calls

            if hasattr(msg, "additional_kwargs") and isinstance(msg.additional_kwargs, dict):
                cache_control = msg.additional_kwargs.get("cache_control")
                if cache_control and "cache_control" not in msg_dict:
                    msg_dict["cache_control"] = cache_control

                tool_calls = msg.additional_kwargs.get("tool_calls")
                if tool_calls and "tool_calls" not in msg_dict:
                    normalized_tool_calls = []
                    for tc in tool_calls:
                        if not isinstance(tc, dict):
                            continue
                        tc_id = tc.get("id")
                        tc_name = tc.get("name") or (tc.get("function") or {}).get("name")
                        tc_args = tc.get("args") or (tc.get("function") or {}).get("arguments")
                        if isinstance(tc_args, str):
                            args_str = tc_args
                        else:
                            try:
                                args_str = json.dumps(tc_args or {}, ensure_ascii=False)
                            except Exception:
                                args_str = "{}"

                        normalized_tool_calls.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc_name,
                                "arguments": args_str
                            }
                        })
                    if normalized_tool_calls:
                        msg_dict["tool_calls"] = normalized_tool_calls

            serialized.append(msg_dict)

        return serialized


        # Set to True to re-enable reflection node (1-minute rollback)
        self.reflection_enabled = False  # DEPRECATED: Use natural LLM self-correction
        
        # WORKFLOW_REFACTOR_PLAN Step 3: State accessor for tools (DI pattern)
        self._current_state = None  # Thread-safe current state reference
        
        def state_accessor():
            """Provide current state to tools (SOLID DIP compliance)."""
            if self._current_state is None:
                raise RuntimeError("No active workflow execution - state accessor called outside workflow")
            return self._current_state
        
        # Create knowledge tools with state accessor (Layer 3: Tool Execution Layer)
        knowledge_tools = create_knowledge_tools(state_accessor)
        
        # Add Excel MCP tools (external tool integration)
        all_tools = knowledge_tools + EXCEL_TOOLS
        
        self.tools = all_tools
        # FIXED: Use plain ToolNode directly instead of TrackedToolNode
        self.tool_node = ToolNode(self.tools)
        logger.info(f"Initialized {len(knowledge_tools)} knowledge tools + {len(EXCEL_TOOLS)} Excel tools = {len(all_tools)} total tools")
        
        # Bind tools to router-context LLM (cost-optimized, deterministic tool selection)
        self.llm_light_with_tools = self.llm_light_router.bind_tools(self.tools)
        logger.info(f"Router LLM bound with {len(self.tools)} tools for tool calling")
        
        # Bind tools to heavy LLM (backup, for complex reasoning if needed)
        self.llm_heavy_with_tools = self.llm_heavy_rag.bind_tools(self.tools)
        
        # Backward compatibility
        self.llm_with_tools = self.llm_light_with_tools
        
        # Build workflow graph
        self.graph = self._build_graph()
        
        # Store LLM messages per session for prompt inspection (outside state to avoid validation errors)
        self._llm_messages_by_session = {}
        
        # WebSocket state broadcasting (optional, enabled per session)
        self._enable_ws_broadcast = {}  # session_id -> bool
        
        logger.info(
            f"UnifiedChatWorkflow initialized with dual-model architecture: "
            f"Heavy={self.config.get_heavy_model()}, Light={self.config.get_light_model()}"
        )
    
    def _build_graph(self) -> Any:
        """
        Build LangGraph workflow with ToolNode integration (REFACTORED).
        
        New Pattern: Prompt → Tool Calls → ToolNode → Observation → Agent Loop
        
        Flow:
        START → validate → query_rewrite → combine_context → agent_decide
          ├─ tool_calls? → tools (ToolNode) → agent_decide (loop)
          └─ no tools? → agent_finalize → END
        
        Query Rewrite Node:
        - Feature flag controlled (system.ini + runtime override)
        - Passthrough pattern (always runs, noop if disabled)
        - LLM-based semantic expansion + intent classification
        
        ARCHITECTURE:
        - Simple nodes: Imported from services/nodes/ (clean separation)
        - Complex nodes: Closures (access to self for helper methods)
        """
        workflow = StateGraph(ChatState)
        
        # CLOSURE PATTERN: Create node functions that close over self
        # (For complex nodes that need access to helper methods)
        
        def validate_input_closure(state: ChatState) -> ChatState:
            """Closure wrapper for validate_input_node with tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                result = validate_input_node(state)
                duration_ms = (time.time() - start_time) * 1000
                # Schedule async logging in thread pool (sync context, can't use asyncio.create_task)
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("validate_input", 0, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("validate_input", 0, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def query_rewrite_closure(state: ChatState) -> ChatState:
            """Closure wrapper for query_rewrite_node with dependencies and tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                result = query_rewrite_node(state, self.config, self._invoke_llm_with_retry)
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("rewrite_query", 4, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("rewrite_query", 4, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def fetch_tenant_closure(state: ChatState) -> ChatState:
            """Closure wrapper for fetch_tenant_context_node with tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                cache = get_context_cache()
                result = fetch_tenant_context_node(state, cache, self._get_tenant_with_retry)
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("fetch_tenant", 1, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("fetch_tenant", 1, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def fetch_user_closure(state: ChatState) -> ChatState:
            """Closure wrapper for fetch_user_context_node with tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                cache = get_context_cache()
                result = fetch_user_context_node(state, cache, self._get_user_with_retry)
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("fetch_user", 2, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("fetch_user", 2, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def fetch_history_closure(state: ChatState) -> ChatState:
            """Closure wrapper for fetch_chat_history_node with tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                result = fetch_chat_history_node(state, self.config)
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("fetch_history", 3, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("fetch_history", 3, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def build_prompt_closure(state: ChatState) -> ChatState:
            """Closure wrapper for build_system_prompt_node with tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                from services.nodes.build_system_prompt_node import build_system_prompt_node
                # NOTE: get_or_build_prompt_fn deprecated - prompt building moved to agent_decide_node
                result = build_system_prompt_node(state, None)
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("build_system_prompt", 5, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("build_system_prompt", 5, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def agent_decide_closure(state: ChatState) -> ChatState:
            """Complex node with full self access and tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                result = self._agent_decide_node(state)
                duration_ms = (time.time() - start_time) * 1000
                from services.state_helpers import get_agent_iteration
                node_index = 6 + get_agent_iteration(result)  # Dynamic index based on iteration
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("agent_decide", node_index, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("agent_decide", 6, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def agent_finalize_closure(state: ChatState) -> ChatState:
            """Complex node with full self access and tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                result = self._agent_finalize_node(state)
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("agent_finalize", 99, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("agent_finalize", 99, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def agent_reflection_closure(state: ChatState) -> ChatState:
            """Complex node with full self access - reflection & self-correction with tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                result = self._agent_reflection_node(state)
                duration_ms = (time.time() - start_time) * 1000
                from services.state_helpers import get_agent_iteration
                node_index = 7 + get_agent_iteration(result)  # After agent_decide
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("agent_reflection", node_index, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("agent_reflection", 7, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        def agent_error_handler_closure(state: ChatState) -> ChatState:
            """Complex node with full self access and tracking"""
            start_time = time.time()
            state_before = copy.deepcopy(state)
            try:
                result = self._agent_error_handler_node(state)
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("agent_error_handler", 98, state_before, result, duration_ms, "success", None, None, start_time),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=("agent_error_handler", 98, state_before, state, duration_ms, "error", str(e), None, start_time),
                    daemon=True
                ).start()
                raise
        
        # WORKFLOW_REFACTOR_PLAN Step 3: tools_with_context_injection REMOVED
        # Replaced with state accessor DI pattern for clean architecture
        
        # Add nodes (using closures)
        workflow.add_node("validate_input", validate_input_closure)
        workflow.add_node("rewrite_query", query_rewrite_closure)  # RENAMED: avoid conflict with state key
        workflow.add_node("fetch_tenant", fetch_tenant_closure)
        workflow.add_node("fetch_user", fetch_user_closure)
        workflow.add_node("fetch_history", fetch_history_closure)
        workflow.add_node("build_system_prompt", build_prompt_closure)
        workflow.add_node("agent_decide", agent_decide_closure)
        workflow.add_node("tools", self._execute_tools_with_tracking)  # Use wrapper function instead of TrackedToolNode
        # DEPRECATED 2026-01-17: Reflection node disabled (WORKFLOW_REFACTOR_PLAN Step 2)
        # ROLLBACK: Uncomment line below to re-enable reflection
        # workflow.add_node("agent_reflection", agent_reflection_closure)  # NEW: Quality check & self-correction
        workflow.add_node("agent_finalize", agent_finalize_closure)
        workflow.add_node("agent_error_handler", agent_error_handler_closure)
        
        # Define edges - SEQUENTIAL CONTEXT BUILDING
        # CRITICAL ORDER: fetch nodes BEFORE query_rewrite for user_language access
        workflow.set_entry_point("validate_input")
        workflow.add_edge("validate_input", "fetch_tenant")
        workflow.add_edge("fetch_tenant", "fetch_user")
        workflow.add_edge("fetch_user", "fetch_history")
        workflow.add_edge("fetch_history", "rewrite_query")  # MOVED: after fetch nodes
        workflow.add_edge("rewrite_query", "build_system_prompt")
        workflow.add_edge("build_system_prompt", "agent_decide")
        
        # Conditional routing from agent_decide
        workflow.add_conditional_edges(
            "agent_decide",
            self._should_continue,
            {
                "tools": "tools",              # Has tool_calls → execute tools
                # DEPRECATED 2026-01-17: Reflection disabled (WORKFLOW_REFACTOR_PLAN Step 2)
                # ROLLBACK: Uncomment line below to re-enable reflection routing
                # "reflect": "agent_reflection", # NEW: Tool executed → quality check
                "finalize": "agent_finalize",  # No tool_calls → final answer
                "error": "agent_error_handler" # Error occurred → error handling
            }
        )
        
        # Direct tools → agent_decide (bypass reflection for natural LLM self-correction)
        workflow.add_edge("tools", "agent_decide")
        # DEPRECATED 2026-01-17: Direct reflection route disabled
        # ROLLBACK: Comment out line above and uncomment line below
        # workflow.add_edge("tools", "agent_reflection")
        
        # DEPRECATED 2026-01-17: Reflection routing disabled (WORKFLOW_REFACTOR_PLAN Step 2)
        # ROLLBACK: Uncomment block below to re-enable reflection routing
        # Reflection routing:
        # - If issues found → retry with guidance
        # - If quality OK → go back to agent_decide for answer synthesis
        # workflow.add_conditional_edges(
        #     "agent_reflection",
        #     self._should_retry,
        #     {
        #         "retry": "agent_decide",       # Issues found → retry with guidance
        #         "continue": "agent_decide"     # Quality OK → synthesize answer from tool results
        #     }
        # )
        
        # Finalize and error handler end workflow
        workflow.add_edge("agent_finalize", END)
        workflow.add_edge("agent_error_handler", END)
        
        logger.info("✅ Graph built: validate → rewrite_query → context → agent_decide ↔ tools (reflection bypassed) → finalize")
        return workflow.compile()
    
    def _execute_tools_with_tracking(self, state: ChatState) -> ChatState:
        """
        Execute tools with comprehensive tracking (SOLID: Orchestration).
        
        Responsibilities:
        1. Execute ToolNode
        2. Log aggregate tools node execution
        3. Delegate individual tool logging
        """
        start_time = time.time()
        node_name = "tools"
        execution_id = state.get("request_context", {}).get("execution_id")
        
        try:
            # Execute ToolNode using invoke() method
            result = self.tool_node.invoke(state)
            
            # CRITICAL: ToolNode returns DELTA (only new ToolMessages), not full state
            # Manually combine messages lists (LangGraph reducer would do this automatically)
            output_state = {**state}
            output_state["messages"] = state.get("messages", []) + result.get("messages", [])
            
            # Extract tool execution metadata (pure function)
            duration_ms = (time.time() - start_time) * 1000
            try:
                tools_metadata = self._extract_tool_metadata(state, output_state)
            except Exception as extract_error:
                logger.error(f"[TOOLS] Failed to extract tool metadata: {extract_error}", exc_info=True)
                tools_metadata = []
            
            # Log aggregate tools node execution (FIXED: use 'state' with user_context)
            # Use SYNC logging here (no thread) to ensure metadata is persisted before node returns
            logger.info(f"[TOOLS] Starting aggregate logging for {len(tools_metadata)} tools...")
            try:
                self._sync_log_node_execution(
                    node_name, 
                    50, 
                    state,  # state_before
                    output_state,  # state_after
                    duration_ms,
                    "success",
                    None,
                    {"tools_called": tools_metadata},
                    start_time
                )
                logger.info(f"[TOOLS] Aggregate logging completed")
            except Exception as log_error:
                logger.warning(f"[TOOLS] Failed to log aggregate node execution: {log_error}")
            
            # Log individual tool executions (SOLID: Separated responsibility)
            logger.info(f"[TOOLS] Starting individual tool logging...")
            try:
                self._log_individual_tool_executions(state, output_state, tools_metadata, execution_id, start_time)
                logger.info(f"[TOOLS] Individual tool logging completed")
            except Exception as log_error:
                logger.warning(f"[TOOLS] Failed to log individual tool executions: {log_error}")
            
            logger.info(f"[TOOLS] Executed {len(tools_metadata)} tools in {duration_ms:.1f}ms")
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            try:
                self._sync_log_node_execution(
                    node_name, 
                    50, 
                    state,  # state_before
                    state,  # state_after (unchanged due to error)
                    duration_ms, 
                    "error", 
                    str(e),
                    None,
                    start_time
                )
            except Exception as log_error:
                logger.warning(f"[TOOLS] Failed to log error: {log_error}")
            raise

    def _extract_tool_metadata(self, input_state: ChatState, output_state: ChatState) -> List[Dict[str, Any]]:
        """
        Extract tool execution metadata from state transition (SOLID: Pure function).
        
        Returns list of tool metadata dictionaries without side effects.
        """
        tool_executions = []
        
        input_messages = input_state.get("messages", [])
        output_messages = output_state.get("messages", [])
        
        # Find new ToolMessage objects added by ToolNode
        new_messages = output_messages[len(input_messages):]
        
        for msg in new_messages:
            if hasattr(msg, 'tool_call_id') and hasattr(msg, 'content'):
                tool_name = self._get_tool_name_by_call_id(input_state, msg.tool_call_id)
                status = "success" if not str(msg.content).startswith("Error") else "error"
                
                content_str = str(msg.content)
                preview_max = 200
                
                tool_meta = {
                    "tool_name": tool_name or "unknown",
                    "tool_call_id": msg.tool_call_id,
                    "status": status,
                    "output_full": content_str  # Always present (persistent data)
                }
                
                # Preview only if content is too long (UI optimization)
                if len(content_str) > preview_max:
                    tool_meta["output_preview"] = content_str[:preview_max] + "..."
                
                tool_executions.append(tool_meta)
        
        return tool_executions
    
    def _log_individual_tool_executions(
        self, 
        input_state: ChatState, 
        output_state: ChatState, 
        tools_metadata: List[Dict[str, Any]],
        execution_id: Optional[str],
        tools_start_time: float  # NEW: tools node start time for timestamp
    ) -> None:
        """
        Log each tool as separate node execution (SOLID: Single Responsibility).
        
        Creates individual node executions for workflow inspector granularity.
        Uses input_state to preserve user_context.
        """
        logger.info(f"[TOOLS] _log_individual_tool_executions called with {len(tools_metadata)} tools")
        
        tool_index = 51  # Start after aggregate tools node (50)
        
        for tool_meta in tools_metadata:
            try:
                tool_name = tool_meta["tool_name"]
                status = tool_meta["status"]
                
                logger.info(f"[TOOLS] Processing individual tool: {tool_name}, status: {status}")
                
                # CRITICAL: Use input_state (has user_context) for logging
                threading.Thread(
                    target=self._sync_log_node_execution,
                    args=(
                        f"tool_{tool_name}",  # node_name
                        tool_index,           # node_index
                        input_state,          # state_before (input state)
                        output_state,         # state_after (output state)  
                        50.0,                 # duration_ms (estimated)
                        status,               # status
                        None if status == "success" else tool_meta["output_full"],  # error_message
                        {
                            "tool_call_id": tool_meta["tool_call_id"],
                            "output_preview": tool_meta.get("output_preview"),  # Optional field
                            "parent_node": "tools",
                            "execution_id": execution_id
                        },                    # metadata
                        tools_start_time      # started_at
                    ),
                    daemon=True
                ).start()
                
                logger.info(f"[TOOLS] Started thread for tool: {tool_name}")
                tool_index += 1
            except Exception as e:
                logger.warning(f"[TOOLS] Failed to log individual tool {tool_meta.get('tool_name', 'unknown')}: {e}")
                import traceback
                logger.warning(f"[TOOLS] Traceback: {traceback.format_exc()}")
    
    def _get_tool_name_by_call_id(self, state: ChatState, tool_call_id: str) -> Optional[str]:
        """Find tool name by tool_call_id from previous AIMessage."""
        messages = state.get("messages", [])
        
        # Look for AIMessage with tool_calls containing this ID
        for msg in reversed(messages):
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.get('id') == tool_call_id:
                        return tool_call.get('name')
        
        return None
    
    def _should_continue(self, state: ChatState) -> str:
        """
        Routing logic: Check if agent wants to call tools, finalize, or handle errors.
        
        Inspects last message in state["messages"]:
        - If errors in state → route to "error"
        - If AIMessage with tool_calls → route to "tools"
        - If no tool_calls or next_action="FINAL_ANSWER" → route to "finalize"
        
        Returns:
            "tools" | "finalize" | "error"
        """
        # Check for accumulated errors first
        errors = state.get("errors", [])
        if errors and len(errors) > 3:  # More than 3 errors → error handling
            logger.error(f"[ROUTING] {len(errors)} errors accumulated → error")
            return "error"
            
        next_action = state.get("next_action")
        
        # Check explicit FINAL_ANSWER signal from agent_decide
        if next_action == "FINAL_ANSWER":
            logger.info("[ROUTING] next_action=FINAL_ANSWER → finalize")
            return "finalize"
        
        # Check last message for tool_calls
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
                logger.info(f"[ROUTING] {len(last_message.tool_calls)} tool_calls detected → tools")
                return "tools"
        
        # Default: no tool calls, go to finalize
        logger.info("[ROUTING] No tool_calls → finalize")
        return "finalize"
    
    def _should_retry(self, state: ChatState) -> str:
        """
        Routing logic after reflection: decide if retry or continue to answer synthesis.
        
        Checks reflection_decision and iteration limits.
        
        Returns:
            "retry" | "continue"
        """
        decision = state.get("reflection_decision", "continue")
        
        # Read iteration and reflection counts from nested AgentControl structure
        agent = state.get("agent", {})
        iteration = agent.get("iteration_count", 0)
        reflection_count = agent.get("reflection_count", 0)
        
        # Max 5 total iterations (including retries)
        if iteration >= 5 or reflection_count >= 2:
            logger.warning(
                f"[ROUTING] Max iterations reached (iter={iteration}, reflect={reflection_count}) → continue"
            )
            return "continue"
        
        logger.info(f"[ROUTING] Reflection decision: {decision}")
        return decision  # "retry" or "continue"
    
    async def _broadcast_state(self, node_name: str, state: ChatState):
        """
        Broadcast workflow state to WebSocket clients if enabled for this session.
        
        Args:
            node_name: Current node name
            state: Current workflow state
        """
        session_id = state.get("session_id")
        if not session_id or not self._enable_ws_broadcast.get(session_id, False):
            return
        
        try:
            from services.websocket_manager import websocket_manager
            
            # Read iteration_count from nested AgentControl structure
            agent = state.get("agent", {})
            
            # Serialize state (exclude non-serializable fields)
            state_snapshot = {
                "query": state.get("query"),
                "session_id": session_id,
                "next_action": state.get("next_action"),
                "iteration_count": agent.get("iteration_count", 0),
                "actions_taken": state.get("actions_taken", []),
                "retrieved_chunks_count": len(state.get("retrieved_chunks", [])),
                "listed_documents_count": len(state.get("listed_documents", [])),
                "intermediate_results_count": len(state.get("intermediate_results", [])),
                "system_prompt_cached": state.get("context", {}).get("system_prompt_cached", False),
                "cache_source": state.get("context", {}).get("cache_source"),
                "error": state.get("error")
            }
            
            await websocket_manager.broadcast_state(session_id, node_name, state_snapshot)
        
        except Exception as e:
            logger.error(f"Failed to broadcast state: {e}")
    
    def _add_error(self, state: ChatState, error_type: str, error_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Helper: Add structured error to state errors list.
        
        Args:
            state: Current workflow state
            error_type: Error category (api_timeout, openai_error, qdrant_error, etc.)
            error_message: Human-readable error description
            context: Additional context (operation, retry_attempt, etc.)
            
        Returns:
            Updated state dict with error appended
        """
        error_entry = {
            "type": error_type,
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {}
        }
        
        current_errors = state.get("errors", [])
        
        logger.warning(f"[ERROR] {error_type}: {error_message}", extra={
            "error_type": error_type,
            "error_count": len(current_errors) + 1,
            "context": context
        })
        
        return {
            **state,
            "errors": current_errors + [error_entry]
        }

    def _combine_messages_for_llm(self, messages: List[BaseMessage]) -> str:
        """Combine all LLM messages into a single ordered text block for cache testing."""
        lines = []
        for idx, msg in enumerate(messages, 1):
            msg_type = type(msg).__name__
            role_map = {
                "SystemMessage": "SYSTEM",
                "HumanMessage": "USER",
                "AIMessage": "ASSISTANT",
                "ToolMessage": "TOOL",
            }
            role_label = role_map.get(msg_type, msg_type)
            header = f"[{idx}] {role_label}"
            annotation = getattr(msg, "annotation", None)
            if annotation:
                header += f" [{annotation}]"
            tool_call_id = getattr(msg, "tool_call_id", None)
            if tool_call_id:
                header += f" (tool_call_id={tool_call_id})"
            lines.append(header)
            lines.append(str(msg.content))
            lines.append("")
        return "\n".join(lines).strip()
    
    @retry_on_rate_limit(max_attempts=3, base_delay=2.0, max_delay=30.0)
    def _invoke_llm_with_retry(self, messages: List[BaseMessage], state: ChatState, use_light: bool = False, context: str = None) -> AIMessage:
        """
        Retry-protected LLM invocation with context-specific model selection + metrics instrumentation.
        
        Handles:
        - Rate limits (429)
        - API timeouts
        - Connection errors
        - Invalid responses
        - Prometheus metrics (tokens, cost, latency)
        
        Args:
            messages: Message list for LLM
            state: Current workflow state (for context)
            use_light: If True, use lightweight model (backward compatibility)
                      If False, use heavy model (backward compatibility)
            context: Context-specific selection ('chat', 'router', 'rag', 'big_think')
                    Overrides use_light when provided
            
        Returns:
            AIMessage with LLM response
            
        Raises:
            WorkflowError: After all retries exhausted
        """
        from observability.ai_metrics import record_llm_call
        
        # Select model based on context or backward compatibility
        if context:
            # Context-specific selection (preferred)
            llm = self._select_llm_for_context(context)
            # Add tools if needed (router context needs tools)
            if context == 'router':
                llm = self.llm_light_with_tools
            elif context == 'rag':
                llm = self.llm_heavy_with_tools
            elif context == 'big_think':
                # CACHE TEST: big_think context uses vanilla LLM (no tools)
                llm = self.llm_heavy  # No tools for cache testing
                logger.info(f"[CACHE_TEST] big_think context using vanilla LLM (no tools)")
            else:
                # Other contexts default to tools
                llm = self.llm_heavy_with_tools
                
            model_name = llm.model_name if hasattr(llm, 'model_name') else 'unknown'
            logger.info(f"[LLM] Using {context} context model ({model_name})")
        else:
            # Backward compatibility mode
            if use_light:
                llm = self.llm_light_with_tools
                model_name = self.config.get_light_model()
                logger.info(f"[LLM] Using Light model ({model_name}) for tool selection [BACKWARD]")
            else:
                llm = self.llm_heavy_with_tools
                model_name = self.config.get_heavy_model()
                logger.info(f"[LLM] Using Heavy model ({model_name}) for synthesis [BACKWARD]")
        
        try:
            # Build cache params (OpenAI prompt caching)
            invoke_kwargs = {}
            if self.config.get_bool('cache', 'ENABLE_LLM_CACHE', default=False):
                user_ctx = state.get("user_context", {})
                tenant_id = user_ctx.get("tenant_id")
                user_id = user_ctx.get("user_id")

                key_scope = self.config.get('cache', 'LLM_PROMPT_CACHE_KEY_SCOPE', 'tenant')
                if key_scope == 'user' and user_id is not None:
                    cache_key = f"user:{user_id}:model:{model_name}"
                elif key_scope == 'tenant' and tenant_id is not None:
                    cache_key = f"tenant:{tenant_id}:model:{model_name}"
                else:
                    cache_key = f"global:model:{model_name}"

                retention = self.config.get('cache', 'LLM_PROMPT_CACHE_RETENTION', 'in_memory')

                invoke_kwargs["prompt_cache_key"] = cache_key

                supports_retention = "mini" not in str(model_name).lower()
                if supports_retention:
                    invoke_kwargs["prompt_cache_retention"] = retention
                    retention_log = retention
                else:
                    retention_log = "omitted"

                logger.info(
                    f"[LLM_CACHE] prompt_cache_key={cache_key}, retention={retention_log}, model={model_name}"
                )

            # Store payload details for prompt inspection/debugging
            session_id = state.get("session_id")
            explicit_max_completion_tokens = self.config.get_llm_max_completion_tokens()
            if explicit_max_completion_tokens and hasattr(llm, "max_completion_tokens"):
                llm.max_completion_tokens = explicit_max_completion_tokens
            if session_id:
                llm_kwargs = getattr(llm, "kwargs", {}) if hasattr(llm, "kwargs") else {}
                tools_payload = llm_kwargs.get("tools") if isinstance(llm_kwargs, dict) else None
                tool_choice = llm_kwargs.get("tool_choice") if isinstance(llm_kwargs, dict) else None
                self._llm_payload_by_session[session_id] = {
                    "model": model_name,
                    "tools": tools_payload,
                    "tool_choice": tool_choice,
                    "extra_body": invoke_kwargs or None,
                    "temperature": getattr(llm, "temperature", None),
                    "max_completion_tokens": explicit_max_completion_tokens or getattr(llm, "max_completion_tokens", None),
                    "max_tokens": getattr(llm, "max_tokens", None),
                    "n": getattr(llm, "n", None),
                    "stream": False
                }

            # Force cache_control into outbound HTTP payload (OpenAI prompt caching)
            cache_enabled = self.config.get_bool('cache', 'ENABLE_LLM_CACHE', default=False)
            combine_messages = self.config.get_bool('cache', 'LLM_COMBINE_MESSAGES', default=False)

            combined_messages = None
            if combine_messages:
                combined_text = self._combine_messages_for_llm(messages)
                combined_msg = SystemMessage(content=combined_text)
                if cache_enabled:
                    if not hasattr(combined_msg, "additional_kwargs") or not isinstance(combined_msg.additional_kwargs, dict):
                        combined_msg.additional_kwargs = {}
                    combined_msg.additional_kwargs["cache_control"] = {"type": "ephemeral"}
                combined_messages = [combined_msg]

            serialized_messages = None
            if cache_enabled:
                messages_for_serialization = combined_messages or messages
                serialized_messages = self._serialize_openai_messages(messages_for_serialization, enable_cache=True)

            use_native_client = self._use_native_openai_client or cache_enabled

            # Wrap LLM call with metrics instrumentation
            with record_llm_call(model=model_name, operation="chat") as metrics:
                session_id = state.get("session_id")
                request_id = str(uuid.uuid4())
                self._http_request_context.session_id = session_id
                self._http_request_context.request_id = request_id
                try:
                    if use_native_client:
                        payload = {
                            "model": model_name,
                            "messages": serialized_messages or self._serialize_openai_messages(combined_messages or messages, enable_cache=cache_enabled),
                            "temperature": getattr(llm, "temperature", None),
                            "max_completion_tokens": explicit_max_completion_tokens or getattr(llm, "max_completion_tokens", None),
                            "n": getattr(llm, "n", 1),
                            "stream": False,
                        }
                        if tools_payload:
                            payload["tools"] = tools_payload
                        if tool_choice:
                            payload["tool_choice"] = tool_choice
                        if invoke_kwargs:
                            # Add cache params to top-level, not extra_body
                            payload.update({k: v for k, v in invoke_kwargs.items() if k != "messages"})

                        data = self._openai_client.create_chat_completion(payload)
                        msg = self._openai_client.extract_message(data)
                        usage = self._openai_client.extract_usage(data)
                        finish_reason = self._openai_client.extract_finish_reason(data)

                        tool_calls_raw = msg.get("tool_calls") or []
                        tool_calls = self._openai_client.parse_tool_calls(tool_calls_raw)

                        response = AIMessage(
                            content=msg.get("content") or "",
                            tool_calls=tool_calls or [],
                            response_metadata={
                                "token_usage": usage,
                                "model_name": data.get("model"),
                                "finish_reason": finish_reason,
                            },
                            usage_metadata={
                                "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
                                "output_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
                                "total_tokens": usage.get("total_tokens", 0),
                            }
                        )
                    else:
                        invoke_messages = combined_messages or messages
                        if invoke_kwargs:
                            response = llm.invoke(invoke_messages, extra_body=invoke_kwargs)
                        else:
                            response = llm.invoke(invoke_messages)
                finally:
                    self._http_request_context.session_id = None
                    self._http_request_context.request_id = None

                # Debug: persist raw response metadata for cache diagnosis
                if self._log_openai_payloads and session_id:
                    try:
                        debug_dir = Path(__file__).parent.parent / "debug"
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        log_path = debug_dir / "openai_response_metadata.jsonl"
                        record = {
                            "timestamp": datetime.utcnow().isoformat(),
                            "session_id": session_id,
                            "request_id": request_id,
                            "model": model_name,
                            "response_metadata": getattr(response, "response_metadata", None),
                            "usage_metadata": getattr(response, "usage_metadata", None),
                        }
                        with log_path.open("a", encoding="utf-8") as f:
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    except Exception as exc:
                        logger.warning(f"[OPENAI_PAYLOAD] Failed to log response metadata: {exc}")
                
                # Extract token usage from LangChain response (cache-aware)
                usage = None
                if hasattr(response, 'response_metadata'):
                    usage = response.response_metadata.get('token_usage') or response.response_metadata.get('usage')

                if not usage and hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata

                if usage:
                    logger.info(f"[LLM_CACHE] usage keys: {list(usage.keys())}")
                    if session_id:
                        self._llm_usage_by_session[session_id] = usage
                    prompt_tokens = usage.get('prompt_tokens', usage.get('input_tokens', 0))
                    completion_tokens = usage.get('completion_tokens', usage.get('output_tokens', 0))
                    
                    # Extract cached tokens from OpenAI API response
                    # Structure: usage.prompt_tokens_details.cached_tokens
                    prompt_tokens_details = usage.get('prompt_tokens_details') or usage.get('input_tokens_details', {})
                    cached_tokens = prompt_tokens_details.get('cached_tokens', 0)
                    logger.info(
                        f"[LLM_CACHE] cached_tokens={cached_tokens}, prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}"
                    )
                    
                    # Calculate cache metrics
                    uncached_tokens = prompt_tokens - cached_tokens
                    cache_hit_rate = (cached_tokens / prompt_tokens * 100) if prompt_tokens > 0 else 0.0
                    
                    # Record metrics (cost will be calculated automatically with cache discount)
                    if metrics:
                        metrics.set_tokens(prompt_tokens, completion_tokens, cached_tokens)
                        
                        if cached_tokens > 0:
                            logger.info(
                                f"[METRICS] LLM call: {uncached_tokens} uncached + {cached_tokens} cached "
                                f"({cache_hit_rate:.1f}% hit rate) + {completion_tokens} completion tokens"
                            )
                        else:
                            logger.info(f"[METRICS] LLM call: {prompt_tokens} prompt + {completion_tokens} completion tokens")
                else:
                    logger.warning("[METRICS] No token usage found in LLM response")
            
            # Validate response structure
            if not hasattr(response, 'content') and not (hasattr(response, 'tool_calls') and response.tool_calls):
                raise WorkflowError(
                    "Invalid LLM response: no content or tool_calls",
                    context={"response_type": type(response).__name__}
                )
            
            return response
            
        except Exception as e:
            # Convert any exception to WorkflowError for consistent handling
            if isinstance(e, (QdrantServiceError, EmbeddingServiceError, DatabaseError)):
                raise e  # Re-raise service errors as-is
            else:
                raise WorkflowError(
                    f"LLM invocation failed: {str(e)}",
                    context={
                        "error_type": type(e).__name__,
                        "messages_count": len(messages),
                        "session_id": state.get("session_id")
                    }
                ) from e
    
    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def _get_tenant_with_retry(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Retry-protected tenant lookup."""
        try:
            from database.pg_init import get_tenant_by_id
            return get_tenant_by_id(tenant_id)
        except Exception as e:
            raise DatabaseError(
                f"Failed to fetch tenant {tenant_id}",
                context={"tenant_id": tenant_id}
            ) from e
    
    # ===== NODE-LEVEL TRACKING (Runtime-configurable) =====
    
    def _extract_node_metadata(
        self, 
        node_name: str, 
        state: ChatState,
        started_at: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Extract node-specific metadata for tracking.
        
        Args:
            node_name: Node identifier
            state: Current workflow state
            started_at: Unix timestamp when node started
        
        Returns:
            Dict with node-specific metrics (~2KB)
        """
        from datetime import timezone
        
        # Base metadata with accurate timestamps
        metadata = {
            "node_name": node_name,
        }
        
        # Add timestamps if provided
        if started_at is not None:
            metadata["started_at"] = datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat()
        
        # Node-specific metadata extraction
        if node_name == "agent_decide":
            from services.state_helpers import get_agent_iteration
            agent = state.get("agent", {})
            iteration = get_agent_iteration(state)
            
            # Use actual model from state (stored during LLM invocation)
            # Fallback to light model if not set (for backward compatibility)
            llm_model_used = agent.get("llm_model_used", self.config.get_light_model())
            
            metadata.update({
                "llm_model": llm_model_used,
                "iteration": iteration,
                "decision": agent.get("decision"),
                "has_tool_calls": bool(agent.get("tools_called"))
            })
        
        elif node_name == "agent_reflection":
            agent = state.get("agent", {})
            metadata.update({
                "reflection_count": agent.get("reflection_count", 0),
                "quality_issues_found": bool(agent.get("reflection_feedback"))
            })
        
        elif node_name == "tools":
            from services.state_helpers import get_search_chunks
            chunks = get_search_chunks(state)
            metadata.update({
                # "tools_called" removed - now provided by _execute_tools_with_tracking
                "chunks_retrieved": len(chunks) if chunks else 0,
            })
        
        elif node_name == "rewrite_query":
            from services.state_helpers import get_query_rewrite, get_rewritten_query
            query_rewrite = get_query_rewrite(state)
            # Note: QueryRewriteResult has "skipped" field, not "enabled"
            # enabled = NOT skipped (i.e., if not skipped, then it was enabled and executed)
            skipped = query_rewrite.get("skipped", True) if query_rewrite else True
            
            # LLM model used (light model if executed, "none" if skipped)
            llm_model_used = self.config.get_light_model() if not skipped else "none"
            
            metadata.update({
                "enabled": not skipped,  # Invert: enabled = NOT skipped
                "llm_model": llm_model_used,
                "intent": query_rewrite.get("intent") if query_rewrite else None,
                "query_changed": get_rewritten_query(state) != state.get("query")
            })
        
        elif node_name in ["fetch_tenant", "fetch_user"]:
            context_data = state.get("context", {})
            cache_key = "tenant_data" if node_name == "fetch_tenant" else "user_data"
            metadata.update({
                "cached": context_data.get(f"{cache_key}_cached", False),
                "cache_source": context_data.get("cache_source")
            })
        
        elif node_name == "fetch_history":
            context_data = state.get("context", {})
            history = context_data.get("chat_history", [])
            metadata.update({
                "messages_loaded": len(history)
            })
        
        elif node_name == "build_system_prompt":
            context_data = state.get("context", {})
            metadata.update({
                "system_prompt_cached": context_data.get("system_prompt_cached", False),
                "prompt_length": len(context_data.get("system_prompt", ""))
            })
        
        return metadata
    
    def _log_node_execution(
        self,
        node_name: str,
        node_index: int,
        state_before: ChatState,
        state_after: ChatState,
        duration_ms: float,
        status: str = "success",
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        started_at: Optional[float] = None  # NEW: Unix timestamp of node start
    ):
        """
        Synchronous node execution logging.
        
        Called from daemon thread context, safe to block without affecting workflow performance.
        
        Args:
            node_name: Node identifier
            node_index: Node execution order
            state_before: State before node execution
            state_after: State after node execution
            duration_ms: Node execution duration
            status: "success" | "error" | "skipped"
            error_message: Error message if failed
            metadata: Optional additional metadata
            started_at: Unix timestamp when node started (for accurate ordering)
        """
        try:
            logger.info(f"[_log_node_execution] START for {node_name}")
            user_context = state_after.get("user_context", {})
            tenant_id = user_context.get("tenant_id")
            logger.info(f"[_log_node_execution] tenant_id={tenant_id}")
            
            if not tenant_id:
                logger.warning(f"[_log_node_execution] SKIP: No tenant_id")
                return  # Skip if no tenant context
            
            # Check if tracking enabled for this node
            should_track, tracking_level = workflow_tracking_config_service.should_track_node(
                tenant_id=tenant_id,
                node_name=node_name
            )
            logger.info(f"[_log_node_execution] should_track={should_track}, level={tracking_level}")
            
            if not should_track:
                logger.info(f"[_log_node_execution] SKIP: Tracking disabled for {node_name}")
                return  # Tracking disabled
            
            # Extract execution_id from telemetry
            telemetry = state_after.get("telemetry", {})
            execution_id = telemetry.get("execution_id") if isinstance(telemetry, dict) else getattr(telemetry, "execution_id", None)
            logger.info(f"[_log_node_execution] execution_id={execution_id}")
            
            if not execution_id:
                logger.warning(f"[TRACKING] No execution_id found in state for node {node_name}")
                return  # Skip tracking if no execution_id
            
            # Merge extracted metadata with provided metadata
            # CRITICAL: provided metadata (from function param) takes precedence
            extracted_metadata = self._extract_node_metadata(node_name, state_after, started_at=started_at)
            
            # Add completed_at if we have started_at and duration
            if started_at is not None:
                from datetime import timezone
                completed_timestamp = started_at + (duration_ms / 1000.0)
                extracted_metadata["completed_at"] = datetime.fromtimestamp(completed_timestamp, tz=timezone.utc).isoformat()
            
            final_metadata = {**extracted_metadata, **(metadata or {})}  # metadata param wins conflicts
            logger.info(f"[_log_node_execution] metadata keys: {list(final_metadata.keys())}")
            
            # Extract state snapshots if FULL_STATE level
            state_snapshot_before = None
            state_snapshot_after = None
            if tracking_level == "FULL_STATE":
                state_snapshot_before = {
                    "query": state_before.get("query"),
                    "session_id": state_before.get("session_id"),
                    "agent": state_before.get("agent"),
                    "context": state_before.get("context"),
                    "query_rewrite": state_before.get("query_rewrite"),
                    "search": state_before.get("search"),
                }
                state_snapshot_after = {
                    "query": state_after.get("query"),
                    "session_id": state_after.get("session_id"),
                    "agent": state_after.get("agent"),
                    "context": state_after.get("context"),
                    "query_rewrite": state_after.get("query_rewrite"),
                    "search": state_after.get("search"),
                }
            
            # Direct sync call (thread-safe, called from daemon thread)
            if execution_id:
                logger.info(f"[_log_node_execution] CALLING repository._insert_node_execution_sync")
                workflow_tracking_repo._insert_node_execution_sync(
                    execution_id=execution_id,
                    node_name=node_name,
                    node_index=node_index,
                    duration_ms=duration_ms,
                    status=status,
                    error_message=error_message,
                    metadata=final_metadata,
                    state_snapshot_before=state_snapshot_before,
                    state_snapshot_after=state_snapshot_after
                )
                logger.info(f"[_log_node_execution] Repository call COMPLETED")
                
        except Exception as e:
            # Never fail workflow due to tracking errors
            logger.error(f"❌ Failed to log node execution: {e}", exc_info=True)
    
    def _sync_log_node_execution(self, node_name: str, node_index: int, state_before: ChatState, state_after: ChatState, duration_ms: float, status: str = "success", error_message: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, started_at: Optional[float] = None):
        """
        Synchronous node logging wrapper.
        
        Used from sync node closures running in daemon threads.
        Delegates to _log_node_execution which is now sync.
        """
        logger.info(f"🧵 [THREAD] _sync_log_node_execution START: node={node_name}, index={node_index}, status={status}")
        try:
            self._log_node_execution(node_name, node_index, state_before, state_after, duration_ms, status, error_message, metadata, started_at)
            logger.info(f"✅ [THREAD] _sync_log_node_execution SUCCESS: node={node_name}")
        except Exception as e:
            # Never fail workflow due to tracking errors
            logger.error(f"❌ Failed to sync log node execution: {e}", exc_info=True)
    
    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def _get_tenant_with_retry(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Retry-protected tenant lookup."""
        try:
            from database.pg_init import get_tenant_by_id
            return get_tenant_by_id(tenant_id)
        except Exception as e:
            raise DatabaseError(
                f"Failed to fetch tenant {tenant_id}",
                context={"tenant_id": tenant_id}
            ) from e
    
    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def _get_user_with_retry(self, user_id: int, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Retry-protected user lookup."""
        try:
            from database.pg_init import get_user_by_id_pg
            return get_user_by_id_pg(user_id, tenant_id)
        except Exception as e:
            raise DatabaseError(
                f"Failed to fetch user {user_id} for tenant {tenant_id}",
                context={"user_id": user_id, "tenant_id": tenant_id}
            ) from e
    
    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def _get_system_prompt_with_retry(self, user_id: int) -> Optional[str]:
        """Retry-protected system prompt lookup."""
        try:
            from database.pg_init import get_latest_cached_prompt
            return get_latest_cached_prompt(user_id)
        except Exception as e:
            raise DatabaseError(
                f"Failed to fetch system prompt for user {user_id}",
                context={"user_id": user_id}
            ) from e
    
    
    # ===== NODE IMPLEMENTATIONS (Complex nodes only - simple nodes in services/nodes/) =====
    # NOTE: validate_input, query_rewrite, fetch_*, build_system_prompt moved to services/nodes/
    #       Only agent_decide, agent_finalize, agent_error_handler remain here (complex dependencies)
    
    # DEPRECATED (2026-01-20): _get_or_build_system_prompt removed
    # Prompt building now happens ONLY in _agent_decide_node for OpenAI cache optimization
    # The build_system_prompt_node now only prepares context, doesn't build prompts
    
    def _should_use_light_model(
        self, 
        has_tool_results: bool,
        iteration_count: int
    ) -> bool:
        """
        Intelligent model selection based on workflow context (SOLID: DIP-compliant).
        
        Pure function without state coupling - depends on primitives, not concrete State.
        
        Rules:
        - Tool results present (ToolMessage) → HEAVY (RAG synthesis needed)
        - First iteration (no tools called yet) → LIGHT (tool selection)
        - Default → LIGHT (cost optimization)
        
        Args:
            has_tool_results: Whether tool execution results are available
            iteration_count: Current agent iteration number
            
        Returns:
            True if light model should be used, False for heavy model
        """
        if has_tool_results:
            logger.info("[MODEL_SELECT] Tool results present → HEAVY for RAG synthesis")
            return False  # Heavy model for synthesis
        
        if iteration_count == 0:
            logger.info("[MODEL_SELECT] First iteration → LIGHT for tool selection")
            return True  # Light model for tool calling
        
        logger.info("[MODEL_SELECT] Default → LIGHT (cost optimization)")
        return True  # Light model by default
    
    def _agent_decide_node(self, state: ChatState) -> ChatState:
        """
        Node 3: Agent reasoning with LLM tool calling.
        
        REFACTORED TO: Prompt → Tool Call (AIMessage.tool_calls) → ToolNode → Observation
        
        Flow:
        1. Build messages from state (system prompt + chat history + current query)
        2. LLM decides: call tools OR final answer
        3. If tool_calls generated → ToolNode will execute them
        4. If no tool_calls → direct answer (finalize)
        """
        # Read iteration from nested AgentControl structure
        iteration = get_agent_iteration(state)
        logger.info(f"[NODE 3: agent_decide] Iteration {iteration} (LLM tool calling mode)")
        
        if iteration >= MAX_ITERATIONS:
            logger.warning(f"Max iterations ({MAX_ITERATIONS}) reached, forcing finalize")
            return {**state, "next_action": "FINAL_ANSWER"}
        
        try:
            # Build message history for LLM
            messages = list(state.get("messages", []))
            
            user_ctx = state["user_context"]
            user_lang = user_ctx.get("user_language", "en")
            
            # === UNIFIED PROMPT STRATEGY (CACHE-OPTIMIZED) ===
            # Single prompt structure for ALL iterations to maximize OpenAI Prompt Cache hits
            # Static prefix (>1024 tokens) + Dynamic suffix (date/time at END)
            
            # First iteration: Build full message structure
            if iteration == 0:
                logger.info("[NODE 3] Building UNIFIED prompt (cache-optimized)")
                
                # Extract tenant and user prompts
                tenant_prompt = user_ctx.get("tenant_prompt")
                user_prompt = user_ctx.get("user_prompt")
                
                # Load tool routing instructions from external file (601 tokens - critical for cache!)
                from config.config_service import get_tool_routing_instructions, get_rag_guidelines
                tool_routing_text = get_tool_routing_instructions()
                
                if not tool_routing_text:
                    logger.warning("Tool routing instructions file not found - using empty (will break cache optimization!)")
                    tool_routing_text = ""
                
                # ALWAYS load RAG guidelines (cache stability - same prompt structure regardless of RAG)
                rag_guidelines_text = get_rag_guidelines(user_lang)
                if not rag_guidelines_text:
                    logger.warning(f"[NODE 3] RAG guidelines not found for language: {user_lang}")
                    rag_guidelines_text = ""
                
                # Get request context for datetime
                request_context = state.get("request_context", {})
                current_date = request_context.get("current_date")
                current_time = request_context.get("current_time")
                current_location = request_context.get("effective_location")
                
                # Read from nested ContextData structure for user data
                context_data = state.get("context", {})
                user_data = context_data.get("user_data", {})
                
                # Build UNIFIED prompt (RAG guidelines always included, rag_active=False initially)
                # CACHE OPTIMIZATION: Returns (system_prompt, datetime_context) tuple
                unified_system_prompt, datetime_context = build_system_prompt(
                    user_context=user_data,
                    tenant_prompt=tenant_prompt,
                    user_prompt=user_prompt,
                    current_date=current_date,
                    current_time=current_time,
                    current_location=current_location,
                    mode="unified",  # Deprecated param, ignored
                    rag_guidelines_text=rag_guidelines_text,
                    tool_routing_instructions=tool_routing_text,
                    rag_active=False  # Will be updated in subsequent iterations if RAG is used
                )
                
                # Build component list for metadata
                components = ["app_prompt", "tool_routing", "rag_guidelines", "current_context"]
                if tenant_prompt and tenant_prompt.strip():
                    components.append("tenant_policy")
                if user_prompt and user_prompt.strip():
                    components.append("user_preferences")
                components.append("current_user")
                
                # Create system message with cache control
                system_msg = SystemMessage(content=unified_system_prompt)
                if self.config.get_bool('cache', 'ENABLE_LLM_CACHE', default=False):
                    if not hasattr(system_msg, "additional_kwargs") or not isinstance(system_msg.additional_kwargs, dict):
                        system_msg.additional_kwargs = {}
                    system_msg.additional_kwargs["cache_control"] = {"type": "ephemeral"}
                system_msg.annotation = "unified_system_prompt"
                system_msg.metadata = {
                    "iteration": iteration,
                    "source": "agent_decide_node",
                    "type": "unified",
                    "components": components,
                    "has_tenant_policy": bool(tenant_prompt and tenant_prompt.strip()),
                    "has_user_preferences": bool(user_prompt and user_prompt.strip()),
                    "rag_active": False,
                    "tenant_policy_length": len(tenant_prompt) if tenant_prompt else 0,
                    "user_preferences_length": len(user_prompt) if user_prompt else 0
                }
                messages.append(system_msg)
                
                # Add intent hint from query rewrite (if available)
                query_rewrite = state.get("query_rewrite", {})
                detected_intent = query_rewrite.get("intent")
                if detected_intent == "chat":
                    hint_msg = SystemMessage(content="HINT: User query is conversational/greeting. Respond directly in a natural, friendly way. DO NOT call any tools.")
                    hint_msg.annotation = "chat_intent_hint"
                    hint_msg.metadata = {"detected_intent": detected_intent, "source": "query_rewrite_node"}
                    messages.append(hint_msg)
                
                # Add current query FIRST (use rewritten query if available)
                query_to_use = get_rewritten_query(state)
                is_rewritten = query_to_use != state["query"]
                if is_rewritten:
                    logger.info(
                        "[NODE 3] Using REWRITTEN query",
                        extra={
                            "original": state["query"],
                            "rewritten": query_to_use,
                            "session_id": state.get("session_id")
                        }
                    )
                
                # CACHE-FRIENDLY: Include chat history IN the user message (not as separate AIMessage)
                # This prevents cache invalidation from the variable-length history message
                context_data = state.get("context", {})
                recent_history = context_data.get("chat_history", [])[-5:]
                
                user_query_content = query_to_use
                if recent_history:
                    # Format chat history as context prefix in user message
                    history_lines = ["[Previous conversation context:]"]
                    for idx, msg in enumerate(recent_history):
                        role_label = "User" if msg["role"] == "user" else "Assistant"
                        history_lines.append(f"{role_label}: {msg['content']}")
                    history_lines.append("\n[Current question:]")
                    history_lines.append(query_to_use)
                    user_query_content = "\n".join(history_lines)
                
                # CACHE OPTIMIZATION: Prepend datetime context to user message
                # This keeps system prompt static and cacheable
                if datetime_context:
                    user_query_content = f"{datetime_context}\n\n{user_query_content}"
                
                query_msg = HumanMessage(content=user_query_content)
                query_msg.annotation = "rewritten_query" if is_rewritten else "original_query"
                query_msg.metadata = {
                    "original_query": state["query"],
                    "was_rewritten": is_rewritten,
                    "source": "query_rewrite_node" if is_rewritten else "user_input",
                    "has_history_context": bool(recent_history),
                    "history_count": len(recent_history)
                }
                messages.append(query_msg)
                
                logger.info(f"[NODE 3] Unified prompt: {len(messages)} messages, system_prompt={len(unified_system_prompt)} chars")
            
            # Subsequent iterations: Update RAG status in system prompt if needed
            elif iteration > 0:
                logger.info(f"[NODE 3] Iteration {iteration}: Checking for RAG results")
                
                # Check if RAG-specific tools were called
                has_rag_results = False
                for msg in messages[-10:]:
                    if isinstance(msg, ToolMessage):
                        tool_name = msg.name if hasattr(msg, 'name') else None
                        if tool_name in ['search_vectors', 'search_fulltext', 'search_hybrid']:
                            has_rag_results = True
                            msg.annotation = "tool_result_rag"
                            msg.metadata = {"tool_name": tool_name, "result_type": "document_chunks"}
                        elif tool_name in ['get_weather', 'get_currency_rate']:
                            msg.annotation = "tool_result_api"
                            msg.metadata = {"tool_name": tool_name, "result_type": "external_api"}
                        elif tool_name and 'excel' in tool_name.lower():
                            msg.annotation = "tool_result_excel"
                            msg.metadata = {"tool_name": tool_name, "result_type": "spreadsheet"}
                        else:
                            msg.annotation = "tool_result_other"
                            msg.metadata = {"tool_name": tool_name or "unknown"}
                
                # If RAG results found, update the system prompt to activate RAG guidelines
                if has_rag_results and messages and isinstance(messages[0], SystemMessage):
                    old_content = messages[0].content
                    # Replace INACTIVE with ACTIVE in RAG guidelines header
                    new_content = old_content.replace(
                        "RAG ANSWER GUIDELINES [INACTIVE (no document search performed)]:",
                        "RAG ANSWER GUIDELINES [ACTIVE]:"
                    )
                    if new_content != old_content:
                        messages[0] = SystemMessage(content=new_content)
                        messages[0].annotation = "unified_system_prompt_rag_active"
                        messages[0].metadata = {
                            "iteration": iteration,
                            "rag_active": True,
                            "source": "agent_decide_node"
                        }
                        if self.config.get_bool('cache', 'ENABLE_LLM_CACHE', default=False):
                            messages[0].additional_kwargs = {"cache_control": {"type": "ephemeral"}}
                        logger.info(f"[NODE 3] Activated RAG guidelines in system prompt")
            
            # Call LLM with tools bound (LLM decides: call tools OR answer directly)
            logger.info(f"[NODE 3] Calling LLM with {len(messages)} messages")
            
            # Store messages for Prompt Inspector (Debug Modal)
            session_id = state.get("session_id")
            if session_id:
                self._llm_messages_by_session[session_id] = messages
                logger.info(f"[NODE 3] Stored {len(messages)} messages for session {session_id} (Prompt Inspector)")
            
            try:
                # CACHE TEST: Tools kikommentezve, csak LLM model használat
                # =======================================================
                # Retry-protected LLM call with intelligent model selection
                # Extract conditions for DIP compliance (pure function)
                has_tool_results = bool(messages and isinstance(messages[-1], ToolMessage))
                use_light = self._should_use_light_model(has_tool_results, iteration)

                # Cache validation mode: force a single model to avoid cross-model cache fragmentation
                if self.config.get_bool('cache', 'ENABLE_LLM_CACHE', default=False) and \
                   self.config.get_bool('cache', 'LLM_CACHE_FORCE_SINGLE_MODEL', default=True):
                    use_light = False
                
                # Model selection logic:
                # - Tool results present → HEAVY (RAG synthesis)
                # - First iteration → LIGHT (tool selection)
                # - Default → LIGHT (cost optimization)
                response = self._invoke_llm_with_retry(messages, state, use_light=use_light)
                # Store actual model used for metadata tracking
                actual_model_used = self.config.get_light_model() if use_light else self.config.get_heavy_model()
                
                # Extract cache info from OpenAI response (for cost tracking UI)
                cache_info = {}
                usage = None
                token_usage = None
                if hasattr(response, 'response_metadata'):
                    token_usage = response.response_metadata.get('token_usage') or response.response_metadata.get('usage')
                    usage = token_usage

                if not usage and hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata

                if usage:
                    prompt_tokens = usage.get('prompt_tokens', usage.get('input_tokens', 0))
                    prompt_tokens_details = usage.get('prompt_tokens_details') or usage.get('input_tokens_details', {})
                    cached_tokens = prompt_tokens_details.get('cached_tokens', 0)
                    if not cached_tokens and token_usage:
                        token_details = token_usage.get('prompt_tokens_details') or token_usage.get('input_tokens_details', {})
                        cached_tokens = token_details.get('cached_tokens', cached_tokens)
                    if not cached_tokens:
                        cached_tokens = usage.get('cached_tokens', cached_tokens)
                    completion_tokens = usage.get('completion_tokens', usage.get('output_tokens', 0))
                    
                    cache_info = {
                        "prompt_tokens": prompt_tokens,
                        "cached_tokens": cached_tokens,
                        "uncached_tokens": prompt_tokens - cached_tokens,
                        "cache_hit_rate": (cached_tokens / prompt_tokens * 100) if prompt_tokens > 0 else 0.0,
                        "completion_tokens": completion_tokens
                    }
                
            except Exception as e:
                # LLM call failed after retries
                error_state = self._add_error(
                    state, 
                    "openai_error", 
                    f"LLM invocation failed: {str(e)}", 
                    {"iteration": iteration, "messages_count": len(messages)}
                )
                
                # Return error state to trigger error routing
                return error_state
            
            # Check if LLM wants to call tools
            has_tool_calls = hasattr(response, "tool_calls") and len(response.tool_calls) > 0
            
            if has_tool_calls:
                logger.info(f"[NODE 3] LLM generated {len(response.tool_calls)} tool calls")
                for tc in response.tool_calls:
                    logger.info(f"  - Tool: {tc.get('name', 'unknown')} with args: {tc.get('args', {})}")
                
                # Update nested AgentControl structure
                agent = state.get("agent", {})
                updated_agent: AgentControl = {
                    **agent,
                    "iteration_count": iteration + 1,
                    "next_action": "CALL_TOOLS",
                    "llm_model_used": actual_model_used,  # Store actual model for tracking
                    "cache_info": cache_info  # Store cache metrics for UI
                }
                
                # Append AI message with tool_calls to state
                return {
                    **state,
                    "messages": messages + [response],
                    "agent": updated_agent,
                    "next_action": "CALL_TOOLS"  # Route to ToolNode
                }
            else:
                # No tool calls - provide direct answer
                logger.info(f"[NODE 3] No tool calls, providing direct answer")
                
                # Update nested AgentControl structure
                agent = state.get("agent", {})
                updated_agent: AgentControl = {
                    **agent,
                    "iteration_count": iteration + 1,
                    "next_action": "FINAL_ANSWER",
                    "llm_model_used": actual_model_used,  # Store actual model for tracking
                    "cache_info": cache_info  # Store cache metrics for UI
                }
                
                return {
                    **state,
                    "messages": messages + [response],
                    "agent": updated_agent,
                    "next_action": "FINAL_ANSWER",
                    "final_answer": response.content
                }
        
        except Exception as e:
            logger.error(f"[NODE 3] Agent decision failed: {e}", exc_info=True)
            return {
                **state,
                "next_action": "FINAL_ANSWER",
                "error": f"Agent decision error: {str(e)}",
                "final_answer": "Sorry, I encountered an error processing your request."
            }
    
    
    # ===== REFLECTION NODE =====
    
    # @deprecated("Reflection node disabled in WORKFLOW_REFACTOR_PLAN Step 2. Use natural LLM self-correction instead.")
    def _agent_reflection_node(self, state: ChatState) -> ChatState:
        """
        Node: Reflection - evaluate tool result quality and decide if retry needed.
        
        DEPRECATED: 2026-01-17 (WORKFLOW_REFACTOR_PLAN Step 2)
        Reason: CORE compliance violation (hardcoded domain rules)
        Alternative: Natural LLM self-correction in agent loop
        
        ROLLBACK: Set self.reflection_enabled = True and uncomment graph connections
        
        This implements self-correction pattern from the course materials.
        
        Quality checks:
        - Empty/insufficient RAG results
        - Tool errors
        - Context mismatch (e.g., currency query answered with documents)
        
        Returns:
            State with reflection_decision: "retry" | "continue"
        """
        
        if not self.reflection_enabled:
            logger.warning("[DEPRECATED] Reflection node called but disabled - passing through")
            return state
            
        logger.info("[NODE: agent_reflection] Evaluating tool result quality")
        
        messages = state.get("messages", [])
        last_tool_message = None
        last_tool_name = None
        
        # Find last tool result
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                last_tool_message = msg
                last_tool_name = msg.name if hasattr(msg, 'name') else "unknown"
                break
        
        if not last_tool_message:
            logger.info("[REFLECTION] No tool message found, continuing to answer synthesis")
            return {**state, "reflection_decision": "continue"}
        
        # Parse tool output
        import json
        try:
            tool_output = json.loads(last_tool_message.content)
        except:
            # Not JSON, treat as plain text
            tool_output = {"content": last_tool_message.content}
        
        # Quality checks
        issues = []
        user_query = state.get("query", "").lower()
        original_query = state.get("original_query", user_query).lower()
        
        # Check 1: RAG returned empty results
        if last_tool_name in ["search_vectors", "search_fulltext", "search_hybrid"]:
            chunks = tool_output.get("chunks", [])
            if len(chunks) == 0:
                issues.append("rag_empty_results")
                logger.warning(f"[REFLECTION] RAG tool '{last_tool_name}' returned 0 chunks")
        
        # Check 2: Tool execution error
        if tool_output.get("success") == False:
            issues.append("tool_error")
            logger.warning(f"[REFLECTION] Tool '{last_tool_name}' returned error: {tool_output.get('error')}")
        
        # Check 3: Context mismatch - currency keywords but RAG was used
        currency_keywords = ["árfolyam", "exchange rate", "currency", "valuta", "deviza", "huf", "eur", "usd"]
        if any(kw in user_query or kw in original_query for kw in currency_keywords):
            if last_tool_name in ["search_vectors", "search_fulltext", "search_hybrid"]:
                issues.append("context_mismatch_currency")
                logger.warning("[REFLECTION] Currency-related query answered with document search")
        
        # Check 4: Weather keywords but RAG was used
        weather_keywords = ["időjárás", "weather", "hőmérséklet", "temperature", "eső", "rain"]
        if any(kw in user_query or kw in original_query for kw in weather_keywords):
            if last_tool_name in ["search_vectors", "search_fulltext", "search_hybrid"]:
                issues.append("context_mismatch_weather")
                logger.warning("[REFLECTION] Weather-related query answered with document search")
        
        # Check 5: Follow-up query without context resolution
        # (Implicit pronoun or temporal reference without explicit entity)
        implicit_references = ["hogyan alakult", "mi a trend", "listázva", "naponta", "havi", "daily", "monthly"]
        if any(ref in user_query for ref in implicit_references):
            # Check if previous tool was currency/weather
            prev_tool_names = [msg.name for msg in reversed(messages[:-1]) if isinstance(msg, ToolMessage)]
            if prev_tool_names and prev_tool_names[0] in ["get_currency_rate", "get_weather"]:
                if last_tool_name not in ["get_currency_rate", "get_weather"]:
                    issues.append("context_continuation_broken")
                    logger.warning("[REFLECTION] Follow-up query lost context of previous tool")
        
        # Decision logic
        if issues:
            # Read reflection_count from nested AgentControl structure
            agent = state.get("agent", {})
            reflection_count = agent.get("reflection_count", 0)
            logger.warning(f"[REFLECTION] Quality issues detected: {issues} (reflection #{reflection_count + 1})")
            
            # Build reflection guidance prompt
            guidance_parts = []
            
            if "rag_empty_results" in issues:
                guidance_parts.append("- Document search returned no results. Consider if this is actually a currency rate, weather, or list documents query instead.")
            
            if "tool_error" in issues:
                guidance_parts.append(f"- Tool '{last_tool_name}' encountered an error. Try a different approach or tool.")
            
            if "context_mismatch_currency" in issues:
                guidance_parts.append("- This appears to be a currency/exchange rate query. Use 'get_currency_rate' tool instead of document search.")
            
            if "context_mismatch_weather" in issues:
                guidance_parts.append("- This appears to be a weather query. Use 'get_weather' tool instead of document search.")
            
            if "context_continuation_broken" in issues:
                prev_context = []
                for msg in reversed(messages):
                    if isinstance(msg, ToolMessage) and msg.name in ["get_currency_rate", "get_weather"]:
                        prev_context.append(f"Previous tool: {msg.name}")
                        break
                guidance_parts.append(f"- This is a follow-up query. {prev_context[0] if prev_context else 'Continue with same tool type'}.")
            
            guidance = "\n".join(guidance_parts)
            
            reflection_prompt = f"""🔄 **REFLECTION - Quality Check Failed**

Original query: "{state.get('original_query', state.get('query'))}"
Latest query: "{state.get('query')}"
Tool used: {last_tool_name}

Issues detected:
{guidance}

Please select the CORRECT tool and try again. Consider:
- Is this about currency rates? → use get_currency_rate
- Is this about weather? → use get_weather  
- Is this a follow-up to a previous tool? → use same tool family
- Is this asking for available documents? → use list_documents
- Only use search_vectors/search_fulltext for actual document content questions"""
            
            # Append reflection message
            messages_copy = list(messages)
            messages_copy.append(HumanMessage(content=reflection_prompt))
            
            # Update nested AgentControl structure
            updated_agent: AgentControl = {
                **agent,
                "reflection_count": reflection_count + 1
            }
            
            return {
                **state,
                "messages": messages_copy,
                "agent": updated_agent,
                "reflection_decision": "retry",
                "reflection_issues": issues
            }
        
        # No issues, proceed to answer synthesis
        logger.info("[REFLECTION] Quality check passed, continuing to answer synthesis")
        return {
            **state,
            "reflection_decision": "continue"
        }
  
    # ===== FINALIZE NODE =====
    
   
    def _agent_finalize_node(self, state: ChatState) -> ChatState:
        """
        Node: Finalize response - extracts final answer from conversation.
        
        REFACTORED: Works with messages-based conversation flow.
        
        The final answer is either:
        1. Already set in state["final_answer"] by agent_decide
        2. Last AI message content
        """
        logger.info("[NODE: agent_finalize] Finalizing response")
        
        # Build actions_taken from tool usage in messages
        logger.info("[DEBUG] Calling _extract_actions_from_messages...")
        actions_taken = self._extract_actions_from_messages(state)
        logger.info(f"[DEBUG] Got actions_taken: {actions_taken}")
        
        # Check if answer already prepared
        final_answer = state.get("final_answer")
        
        if not final_answer:
            # Extract from last AI message
            messages = state.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    final_answer = msg.content
                    break
            
            if not final_answer:
                final_answer = "No response generated"
        
        # Extract sources from tools_called
        sources = self._extract_sources_from_tools(state)
        
        logger.info(f"[NODE: agent_finalize] Final answer: {len(final_answer)} chars, {len(sources)} sources, actions: {actions_taken}")
        
        return {
            **state,
            "final_answer": final_answer,
            "sources": sources,
            "actions_taken": actions_taken
        }
    
    def _agent_error_handler_node(self, state: ChatState) -> ChatState:
        """
        Node: Handle accumulated errors and provide fallback response.
        
        Analyzes accumulated errors and generates user-friendly fallback response.
        Implements graceful degradation patterns.
        """
        from datetime import datetime
        
        errors = state.get("errors", [])
        session_id = state.get("session_id", "unknown")
        
        logger.error(f"[NODE: agent_error_handler] Processing {len(errors)} errors for session {session_id}")
        
        # Analyze error types
        error_types = {}
        latest_error = None
        
        for error in errors:
            error_type = error.get("type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
            if not latest_error or error.get("timestamp", "") > latest_error.get("timestamp", ""):
                latest_error = error
        
        # Generate fallback response based on error patterns
        if "api_timeout" in error_types:
            fallback_response = ("Elnézést, jelenleg túlterhelt a rendszer. "
                               "Kérjük próbálja meg újra néhány perc múlva.")
        elif "openai_error" in error_types:
            fallback_response = ("Jelenleg nem tudom elérni a nyelvi modellt. "
                               "Kérjük próbálja meg később!")
        elif "qdrant_error" in error_types:
            fallback_response = ("A dokumentum keresés jelenleg nem elérhető. "
                               "Próbálja meg a kérdést átfogalmazni vagy várjon egy kicsit.")
        elif "database_error" in error_types:
            fallback_response = ("Adatbázis kapcsolat probléma. "
                               "Kérjük próbálja meg később!")
        else:
            fallback_response = ("Váratlan hiba történt. Kérjük próbálja meg újra "
                               "vagy vegye fel a kapcsolatot az ügyfélszolgálattal.")
        
        # Extract actions taken before errors
        actions_taken = state.get("actions_taken", [])
        
        logger.info(f"[NODE: agent_error_handler] Generated fallback response: {len(fallback_response)} chars")
        
        return {
            **state,
            "final_answer": fallback_response,
            "sources": [],
            "actions_taken": actions_taken + ["ERROR_RECOVERY"],
            "error": f"Recovered from {len(errors)} errors: {', '.join(error_types.keys())}"
        }
    
    def _extract_sources_from_tools(self, state: ChatState) -> List[Dict[str, Any]]:
        """
        Extract sources from tool execution results in messages.
        
        Inspects ToolMessage-ek for document references from search tools.
        """
        from langchain_core.messages import ToolMessage
        
        sources = []
        messages = state.get("messages", [])
        
        logger.info(f"[DEBUG] Scanning {len(messages)} messages for tool results")
        
        # Scan messages for ToolMessage from search tools
        for i, message in enumerate(messages):
            logger.info(f"[DEBUG] Message {i}: type={type(message)}, has_tool_call_id={hasattr(message, 'tool_call_id')}")
            
            # Check if this is a ToolMessage from search_vectors or search_fulltext
            if isinstance(message, ToolMessage):
                logger.info(f"[DEBUG] Found ToolMessage with tool_call_id={getattr(message, 'tool_call_id', 'N/A')}")
                logger.info(f"[DEBUG] Content preview: {str(message.content)[:200]}...")
                
                # Parse the tool result content
                try:
                    if isinstance(message.content, str):
                        # Try to parse as JSON (ToolMessage content)
                        import json
                        result = json.loads(message.content)
                        logger.info(f"[DEBUG] Parsed JSON result: type={type(result)}, len={len(result) if isinstance(result, list) else 'N/A'}")
                        
                        if isinstance(result, list):
                            for item in result:
                                if isinstance(item, dict):
                                    doc_id = item.get("document_id")
                                    if doc_id:
                                        # Try to get document title from metadata
                                        title = item.get("source_title", "Unknown Document")
                                        
                                        # Avoid duplicates
                                        if not any(s.get("id") == doc_id for s in sources):
                                            sources.append({
                                                "type": "document",
                                                "id": doc_id,
                                                "title": title
                                            })
                                            logger.info(f"[DEBUG] Added document source: id={doc_id}, title={title}")
                    elif isinstance(message.content, list):
                        # Handle list directly
                        logger.info(f"[DEBUG] Content is already list: len={len(message.content)}")
                        for item in message.content:
                            if isinstance(item, dict):
                                doc_id = item.get("document_id")
                                if doc_id:
                                    title = item.get("source_title", "Unknown Document")
                                    if not any(s.get("id") == doc_id for s in sources):
                                        sources.append({
                                            "type": "document",
                                            "id": doc_id,
                                            "title": title
                                        })
                                        logger.info(f"[DEBUG] Added document source from list: id={doc_id}, title={title}")
                        
                except (json.JSONDecodeError, ValueError) as e:
                    logger.info(f"[DEBUG] Failed to parse tool result as JSON: {e}")
                    # If not JSON, check for alternative formats
                    pass
        
        # Scan messages for ToolMessage from search tools
        for message in messages:
            # Check if this is a ToolMessage from search_vectors or search_fulltext
            if hasattr(message, 'tool_call_id') and hasattr(message, 'content'):
                # Parse the tool result content
                try:
                    if isinstance(message.content, str):
                        # Try to parse as JSON (ToolMessage content)
                        import json
                        result = json.loads(message.content)
                        if isinstance(result, list):
                            for item in result:
                                if isinstance(item, dict):
                                    doc_id = item.get("document_id")
                                    if doc_id:
                                        # Try to get document title from metadata
                                        title = item.get("source_title", "Unknown Document")
                                        
                                        # Avoid duplicates
                                        if not any(s.get("id") == doc_id for s in sources):
                                            sources.append({
                                                "type": "document",
                                                "id": doc_id,
                                                "title": title
                                            })
                except (json.JSONDecodeError, ValueError):
                    # If not JSON, check for alternative formats
                    pass
        
        logger.info(f"Extracted {len(sources)} unique document sources")
        return sources
    
    def _extract_actions_from_messages(self, state: ChatState) -> List[str]:
        """
        Extract actions taken based on tool calls in messages.
        
        Maps tool usage to high-level actions for test compatibility:
        - search_vectors/search_fulltext/search_hybrid -> RAG
        - list_documents -> LIST  
        - No tools used -> CHAT
        """
        actions = []
        messages = state.get("messages", [])
        has_tools = False
        
        logger.info(f"[DEBUG] Extracting actions from {len(messages)} messages")
        
        # Scan messages for tool calls
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                logger.info(f"[DEBUG] Found tool calls in message: {msg.tool_calls}")
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name", "")
                    logger.info(f"[DEBUG] Processing tool: {tool_name}")
                    
                    if tool_name in ["search_vectors", "search_fulltext", "search_hybrid"]:
                        if "RAG" not in actions:
                            actions.append("RAG")
                        has_tools = True
                    elif tool_name == "list_documents":
                        if "LIST" not in actions:
                            actions.append("LIST")  
                        has_tools = True
                    # Add other tool mappings as needed
        
        # If no tools were used, it's a direct chat
        if not has_tools:
            actions.append("CHAT")
            logger.info("[DEBUG] No tools used, adding CHAT action")
        
        logger.info(f"[DEBUG] Final actions: {actions}")
        return actions
    
    # ===== PUBLIC INTERFACE =====
    
    def enable_websocket_broadcast(self, session_id: str, enabled: bool = True):
        """
        Enable/disable WebSocket broadcasting for a specific session.
        
        Args:
            session_id: Session to control
            enabled: Whether to broadcast state updates
        """
        self._enable_ws_broadcast[session_id] = enabled
        logger.info(f"WebSocket broadcast {'enabled' if enabled else 'disabled'} for session {session_id}")
    
    def execute(
        self,
        query: str,
        session_id: str,
        user_context: Dict[str, Any],
        search_mode: str = "hybrid",
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> Dict[str, Any]:
        """
        Execute unified chat workflow.
        
        Args:
            query: User question
            session_id: Chat session ID
            user_context: Dict with tenant_id, user_id
            search_mode: "vector" | "keyword" | "hybrid" (default: hybrid)
            vector_weight: Weight for vector search in hybrid mode (default: 0.7)
            keyword_weight: Weight for keyword search in hybrid mode (default: 0.3)
        
        Returns:
            Dict with final_answer, sources, error (if any)
        """
        logger.info(f"[WORKFLOW] Starting unified execution: query='{query[:50]}...', session={session_id}, tenant={user_context.get('tenant_id')}")
        
        # Generate request context (MONITORING_IMPLEMENTATION_PLAN Phase 1.1)
        request_id = str(uuid.uuid4())
        trace_id = ""  # Will be set by OpenTelemetry middleware (future)
        started_at = datetime.utcnow()
        
        # CRITICAL FIX 1.3: Create workflow execution record for tracking
        execution_id = None
        try:
            execution_id = str(uuid.uuid4())
            workflow_tracking_repo.create_workflow_execution(
                execution_id=execution_id,
                session_id=session_id,
                tenant_id=user_context["tenant_id"],
                user_id=user_context["user_id"],
                query=query,
                request_id=request_id
            )
            logger.info(f"[TRACKING] Created workflow execution: {execution_id}")
        except Exception as e:
            logger.warning(f"[TRACKING] Failed to create workflow execution: {e}")
        
        # REAL-TIME DATETIME: Use actual current time with user timezone support
        from datetime import timezone
        from zoneinfo import ZoneInfo
        
        now_utc = datetime.now(timezone.utc)
        current_datetime_iso = now_utc.strftime("%Y-%m-%dT%H:%M")
        current_date_human = now_utc.strftime("%Y-%m-%d (%A)")
        current_time_human = now_utc.strftime("%H:%M UTC")
        
        # User timezone support
        user_tz = user_context.get("timezone", "Europe/Budapest")
        try:
            user_tz_obj = ZoneInfo(user_tz)
            now_local = datetime.now(user_tz_obj)
            local_time_human = now_local.strftime("%H:%M")
            current_time_human += f" / {local_time_human} local"
        except Exception:
            pass  # Fallback to UTC only
        
        # Resolve effective location
        default_location = user_context.get("default_location")  # From DB (if exists)
        current_location = None  # Will be set by chat override (e.g., "most Mohács-on vagyok")
        effective_location = current_location or default_location or "Unknown"
        
        # Initialize state with NEW nested structure (WORKFLOW_REFACTOR_PLAN Step 1.6)
        initial_state: ChatState = {
            # Input
            "query": query,
            "session_id": session_id,
            "user_context": {
                "tenant_id": user_context["tenant_id"],
                "user_id": user_context["user_id"],
                "tenant_prompt": None,
                "user_prompt": None,
                "user_language": "en",
                "firstname": None,
                "lastname": None,
                "email": None,
                "role": None,
                "default_location": default_location,
                "timezone": user_context.get("timezone")
            },
            
            # Feature flags (runtime overrides from API request)
            "query_rewrite_enabled": user_context.get("query_rewrite_enabled"),  # None/True/False
            
            # Request context (captured at workflow start)
            "request_context": {
                "current_datetime": current_datetime_iso,
                "current_date": current_date_human,
                "current_time": current_time_human,
                "current_location": current_location,
                "effective_location": effective_location
            },
            
            # Processing groups (initialized as None, filled by nodes)
            "query_rewrite": None,  # Will be filled by query_rewrite_node
            "search_result": None,  # Will be filled by tool nodes
            "reflection": None,  # Will be filled by reflection node (DEPRECATED)
            "context": None,  # Will be filled by context building nodes
            "agent": AgentControl(
                iteration_count=0,
                next_action=None,
                actions_taken=[],
                tools_called=[],
                max_iterations_reached=False
            ),
            
            # Telemetry (MONITORING INTEGRATION)
            "telemetry": TelemetryData(
                request_id=request_id,
                trace_id=trace_id,
                execution_id=execution_id,  # CRITICAL FIX 1.3: Add execution_id to state
                started_at=started_at,
                completed_at=None,
                total_duration_ms=0,
                node_durations={},
                llm_calls=[],
                total_llm_tokens=0,
                total_llm_cost_usd=0.0,
                errors_encountered=[],
                success=False,
                empty_rag_result=False,
                fallback_used=False,
                serializable=True
            ),
            
            # LangChain messages
            "messages": [],
            
            # Search config
            "search_mode": search_mode,
            "vector_weight": vector_weight,
            "keyword_weight": keyword_weight,
            
            # Long-term memory
            "ltm_read_results": None,
            "ltm_write_fact": None,
            
            # Output
            "final_answer": None,
            "sources": [],
            "errors": [],
            "actions_taken": [],  # High-level workflow path tracking
            
            # Legacy/intermediate (temporary backward compatibility)
            "intermediate_results": []
        }
        
        # Execute workflow
        try:
            # WORKFLOW_REFACTOR_PLAN Step 3: Set current state for tool access
            self._current_state = initial_state
            
            logger.info(f"[WORKFLOW] About to invoke graph with initial_state...")
            logger.info(f"[DEBUG] initial_state keys: {list(initial_state.keys())}")
            
            # Use stream mode to capture intermediate states for WebSocket broadcast
            final_state = None
            
            for event in self.graph.stream(initial_state):
                # event is a dict: {node_name: state_update}
                for node_name, state_update in event.items():
                    # WORKFLOW_REFACTOR_PLAN Step 3: Update current state reference
                    self._current_state = state_update
                    # Broadcast state if enabled for this session
                    if self._enable_ws_broadcast.get(session_id, False):
                        try:
                            # Skip asyncio.create_task in sync context to avoid RuntimeError
                            logger.debug(f"[WORKFLOW] State updated: {node_name}")
                        except RuntimeError:
                            # No event loop running (sync context), skip broadcast
                            pass
                    
                    final_state = state_update
            
            if not final_state:
                # Fallback to invoke if stream didn't work
                final_state = self.graph.invoke(initial_state)
            
            logger.info(f"[WORKFLOW] Execution complete: answer_len={len(final_state.get('final_answer', ''))}, sources={final_state.get('sources', [])}, actions={final_state.get('actions_taken', [])}")
            logger.info(f"[DEBUG] final_state keys: {list(final_state.keys())}")
            logger.info(f"[DEBUG] final_state actions_taken: {final_state.get('actions_taken')}")
            # Build prompt_details for frontend "Prompt" button
            prompt_details = None
            # Read from nested ContextData structure
            context_data = final_state.get("context", {})
            
            # Get actual LLM messages first (SINGLE SOURCE OF TRUTH for prompt)
            session_id = initial_state.get("session_id")
            actual_messages = self._llm_messages_by_session.get(session_id, [])
            
            # Extract system_prompt from ACTUAL messages (not from context - that's deprecated)
            # The first SystemMessage in actual_messages is the REAL prompt sent to OpenAI
            system_prompt = None
            for msg in actual_messages:
                if type(msg).__name__ == "SystemMessage":
                    system_prompt = str(msg.content)
                    break
            
            # Fallback to context for backward compatibility
            if not system_prompt:
                system_prompt = context_data.get("system_prompt")
            
            if system_prompt or actual_messages:
                user_ctx = final_state.get("user_context", {})
                chat_history = context_data.get("chat_history", [])
                llm_payload = self._llm_payload_by_session.get(session_id, {})
                
                # Get memory config
                config_service = get_config_service()
                short_term_limit = config_service.get_int('memory', 'SHORT_TERM_MEMORY_MESSAGES', default=30)
                short_term_scope = config_service.get('memory', 'SHORT_TERM_MEMORY_SCOPE', default='session')
                
                # Convert actual LLM messages to EXACT format for frontend prompt inspection
                # This is EXACTLY what was sent to the LLM - character by character
                actual_messages_formatted = []
                for msg in actual_messages:
                    msg_type = type(msg).__name__  # SystemMessage, HumanMessage, AIMessage
                    # CRITICAL: Use msg.content to get the exact string sent to LLM
                    msg_dict = {
                        "type": msg_type,
                        "content": str(msg.content)  # Explicit string conversion for safety
                    }

                    # Include cache_control if present (prompt cache debugging)
                    if hasattr(msg, "additional_kwargs") and isinstance(msg.additional_kwargs, dict):
                        cache_control = msg.additional_kwargs.get("cache_control")
                        if cache_control:
                            msg_dict["cache_control"] = cache_control

                        tool_calls = msg.additional_kwargs.get("tool_calls")
                        if tool_calls:
                            msg_dict["tool_calls"] = tool_calls

                    # Include tool_calls if present (needed for tool message replay)
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        msg_dict.setdefault("tool_calls", msg.tool_calls)

                    # Include tool_call_id for ToolMessage
                    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                        msg_dict["tool_call_id"] = msg.tool_call_id
                    
                    # Add annotation if exists (newly added for prompt structure debugging)
                    if hasattr(msg, 'annotation'):
                        msg_dict["annotation"] = msg.annotation
                    
                    # Add metadata if exists (context about message origin/purpose)
                    if hasattr(msg, 'metadata'):
                        msg_dict["metadata"] = msg.metadata
                    
                    actual_messages_formatted.append(msg_dict)

                # Build a single combined block (exact order) for quick inspection
                combined_llm_content_lines = []
                for idx, msg in enumerate(actual_messages_formatted, 1):
                    msg_type = msg.get("type", "UnknownMessage")
                    annotation = msg.get("annotation")
                    header = f"#{idx} {msg_type}"
                    if annotation:
                        header += f" [{annotation}]"
                    combined_llm_content_lines.append(header)
                    combined_llm_content_lines.append(msg.get("content", ""))
                    combined_llm_content_lines.append("")
                combined_llm_content = "\n".join(combined_llm_content_lines).strip()
                
                # Extract agent info for cache metrics
                agent_info = final_state.get("agent", {})
                logger.info(f"[DEBUG] agent_info keys: {list(agent_info.keys()) if agent_info else 'EMPTY'}")
                logger.info(f"[DEBUG] agent_info.cache_info: {agent_info.get('cache_info', 'NOT FOUND')}")
                
                prompt_details = {
                    "system_prompt": system_prompt,
                    "chat_history": chat_history,  # Show ALL messages that were fetched from DB
                    "current_query": initial_state.get("query"),
                    "system_prompt_cached": context_data.get("system_prompt_cached", False),
                    "cache_source": context_data.get("cache_source"),
                    "user_firstname": user_ctx.get("firstname"),
                    "user_lastname": user_ctx.get("lastname"),
                    "user_email": user_ctx.get("email"),
                    "user_role": user_ctx.get("role"),
                    "user_language": user_ctx.get("user_language"),
                    "chat_history_count": len(chat_history),
                    "actions_taken": final_state.get("actions_taken", []),
                    "short_term_memory_messages": short_term_limit,
                    "short_term_memory_scope": short_term_scope,
                    "actual_llm_messages": actual_messages_formatted,  # ACTUAL messages sent to LLM!
                    "actual_llm_messages_combined": combined_llm_content,
                    "llm_payload": llm_payload,
                    "llm_model": agent_info.get("llm_model_used") or llm_payload.get("model"),
                    "llm_cache_info": agent_info.get("cache_info", {})  # OpenAI prompt cache metrics
                }

                # Fallback: derive cache info from last recorded usage if missing
                if session_id and not prompt_details["llm_cache_info"]:
                    usage = self._llm_usage_by_session.get(session_id, {})
                    if usage:
                        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
                        prompt_tokens_details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details", {})
                        cached_tokens = prompt_tokens_details.get("cached_tokens", 0) or usage.get("cached_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
                        prompt_details["llm_cache_info"] = {
                            "prompt_tokens": prompt_tokens,
                            "cached_tokens": cached_tokens,
                            "uncached_tokens": prompt_tokens - cached_tokens,
                            "cache_hit_rate": (cached_tokens / prompt_tokens * 100) if prompt_tokens > 0 else 0.0,
                            "completion_tokens": completion_tokens
                        }
            
            # Get RAG parameters from config
            config = get_config_service()
            top_k = config.get("rag", "TOP_K_DOCUMENTS", 5)
            min_score = config.get("rag", "MIN_SCORE_THRESHOLD", 0.1)
            
            # Include RAG params if there are sources
            sources = final_state.get("sources", [])
            
            # Workflow completion telemetry (MONITORING_IMPLEMENTATION_PLAN Phase 1.8.1)
            completed_at = datetime.utcnow()
            total_duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            
            if final_state:
                # Update telemetry
                telemetry = final_state.get("telemetry", {})
                telemetry["completed_at"] = completed_at
                telemetry["total_duration_ms"] = total_duration_ms
                telemetry["success"] = final_state.get("final_answer") is not None
                final_state["telemetry"] = telemetry
                
                # Export to Prometheus (MONITORING_IMPLEMENTATION_PLAN Phase 1.2)
                try:
                    export_telemetry(final_state)
                except Exception as e:
                    logger.warning(f"[TELEMETRY] Prometheus export failed: {e}")
                
                # Store in PostgreSQL (MONITORING_IMPLEMENTATION_PLAN Phase 4)
                # TODO: Implement when WorkflowTrackingRepository is ready
                # try:
                #     from database.repositories.workflow_tracking_repository import WorkflowTrackingRepository
                #     repo = WorkflowTrackingRepository()
                #     repo.insert_workflow_execution(serialize_state_for_db(final_state))
                # except Exception as e:
                #     logger.warning(f"[TELEMETRY] PostgreSQL tracking failed: {e}")
            
            # CRITICAL FIX 1.3: Complete workflow execution tracking
            if execution_id and final_state:
                try:
                    workflow_tracking_repo.complete_workflow_execution(
                        execution_id=execution_id,
                        final_answer=final_state.get("final_answer"),
                        total_duration_ms=total_duration_ms,
                        success=final_state.get("final_answer") is not None,
                        actions_taken=final_state.get("actions_taken", []),
                        tools_called=final_state.get("agent", {}).get("tools_called", [])
                    )
                    logger.info(f"[TRACKING] Completed workflow execution: {execution_id}")
                except Exception as e:
                    logger.warning(f"[TRACKING] Failed to complete workflow execution: {e}")
            
            return {
                "final_answer": final_state.get("final_answer", ""),
                "sources": sources,
                "actions_taken": final_state.get("actions_taken", []),
                "llm_cache_info": final_state.get("agent", {}).get("cache_info", {}),
                "prompt_details": prompt_details,
                "error": final_state.get("error"),
                "request_id": request_id,  # NEW: client-side tracking
                "trace_id": trace_id,  # NEW: distributed tracing
                "execution_id": execution_id,  # CRITICAL FIX 1.3: Add execution_id to response
                "duration_ms": total_duration_ms,  # NEW: latency tracking
                "rag_params": {
                    "top_k": int(top_k),
                    "min_score_threshold": float(min_score)
                } if sources else None
            }
        
        except Exception as e:
            logger.error(f"[WORKFLOW] Execution failed: {e}", exc_info=True)
            
            # CRITICAL FIX 1.3: Complete workflow execution on error
            if execution_id:
                try:
                    workflow_tracking_repo.complete_workflow_execution(
                        execution_id=execution_id,
                        final_answer=None,
                        total_duration_ms=int((datetime.utcnow() - started_at).total_seconds() * 1000),
                        success=False,
                        error_message=str(e),
                        actions_taken=[],
                        tools_called=[]
                    )
                    logger.info(f"[TRACKING] Completed failed workflow execution: {execution_id}")
                except Exception as track_error:
                    logger.warning(f"[TRACKING] Failed to complete error workflow execution: {track_error}")
            
            return {
                "final_answer": f"Workflow execution error: {str(e)}",
                "sources": [],
                "actions_taken": [],
                "llm_cache_info": {},
                "error": str(e),
                "request_id": request_id,
                "execution_id": execution_id,  # CRITICAL FIX 1.3: Add execution_id to error response
                "duration_ms": int((datetime.utcnow() - started_at).total_seconds() * 1000)
            }
        
        finally:
            # WORKFLOW_REFACTOR_PLAN Step 3: Clean up state reference
            self._current_state = None
