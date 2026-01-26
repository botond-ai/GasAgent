"""
Unified Chat Endpoint

Handles conversational interactions with agent-based routing (LangGraph).
Routes requests to: CHAT (personal) | RAG (document search) | LIST (metadata).
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Response, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.helpers import handle_api_error
from api.dependencies import get_chat_workflow, require_chat_workflow
from api.schemas import UnifiedChatRequest, UnifiedChatResponse, ErrorResponse
from api.middleware.request_context import set_request_context
from database.pg_init import (
    create_session_pg,
    insert_message_pg
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiter (uses default from main.py)
limiter = Limiter(key_func=get_remote_address)


@router.post("", response_model=UnifiedChatResponse, responses={
    200: {"description": "Existing session - chat response generated"},
    201: {"description": "New session created - chat response generated"},
    400: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
    429: {"description": "Too many requests - rate limit exceeded"}
})
@limiter.limit("60/minute")  # Explicit limit for chat endpoint (critical path)
@handle_api_error("process chat request")
async def chat_unified(
    request: Request,
    chat_request: UnifiedChatRequest,
    background_tasks: BackgroundTasks,
    workflow = Depends(require_chat_workflow)
):
    """
    Unified chat endpoint with agent-based routing (LangGraph workflow).
    
    Pipeline:
    1. Session management (create/validate session)
    2. Execute UnifiedChatWorkflow (agent decides: CHAT | RAG | LIST)
    3. Persist user message (AFTER workflow to prevent chat_history duplication)
    4. Persist assistant message (async background task for faster response)
    5. Return response with session context
    
    Agent routes:
    - CHAT: Personal conversation with user context + chat history
    - RAG: Document search (embedding -> Qdrant -> PostgreSQL -> LLM)
    - LIST: Document listing (metadata + titles)
    
    Returns:
        UnifiedChatResponse with answer, source document IDs, session_id, and error (if any)
    
    Raises:
        400: Invalid input
        503: Workflow not available (OPENAI_API_KEY missing)
        500: Workflow execution error
    
    Use case: Main chat interface (ChatGPT-style)
    """
    # Step 1: Session management
    session_id = chat_request.session_id or str(uuid.uuid4())
    session_created = False  # Track if new session for 201 status
    
    # ========================================================================
    # INJECT session_id, tenant_id, user_id INTO REQUEST CONTEXT
    # (Makes them available throughout the request lifecycle via ContextVars)
    # ========================================================================
    set_request_context(
        session_id=session_id,
        tenant_id=chat_request.user_context.tenant_id,
        user_id=chat_request.user_context.user_id
    )
    
    try:
        create_session_pg(session_id, chat_request.user_context.tenant_id, chat_request.user_context.user_id)
        session_created = True  # New session created → 201 Created
        logger.info(f"✨ New session created: {session_id} for user {request.user_context.user_id}")
    except Exception as e:
        # Session might already exist, which is fine → 200 OK
        session_created = False
        logger.debug(f"Session already exists: {e}")
    
    logger.info(
        f"Chat request: user_id={chat_request.user_context.user_id}, tenant_id={chat_request.user_context.tenant_id}, "
        f"session_id={session_id}, query='{chat_request.query[:50]}...'"
    )
    
    # Step 1.5: Fetch user details from database (for location, timezone, firstname, etc.)
    from database.pg_connection import get_db_connection
    user_data = {}
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT firstname, lastname, default_location, timezone, default_lang
                    FROM users 
                    WHERE user_id = %s AND tenant_id = %s
                """, (chat_request.user_context.user_id, chat_request.user_context.tenant_id))
                user_row = cur.fetchone()
                if user_row:
                    user_data = {
                        "firstname": user_row['firstname'],
                        "lastname": user_row['lastname'],
                        "default_location": user_row['default_location'],
                        "timezone": user_row['timezone'],
                        "default_lang": user_row['default_lang']
                    }
                    logger.info(f"User loaded: {user_data['firstname']} from {user_data.get('default_location', 'Unknown')}")
    except Exception as e:
        logger.warning(f"Failed to load user details: {e}")
    
    # Step 2: Execute UnifiedChatWorkflow (agent-based routing)
    # NOTE: User message is persisted AFTER workflow to avoid duplication in chat_history
    # Enable WebSocket broadcast for real-time debug panel updates
    workflow.enable_websocket_broadcast(session_id, True)
    
    result = workflow.execute(
        query=chat_request.query,
        session_id=session_id,
        user_context={
            "tenant_id": chat_request.user_context.tenant_id,
            "user_id": chat_request.user_context.user_id,
            "query_rewrite_enabled": chat_request.enable_query_rewrite  # NEW: A/B testing flag
        },
        search_mode=chat_request.search_mode.value,  # Enum to string
        vector_weight=chat_request.vector_weight,
        keyword_weight=chat_request.keyword_weight
    )
    
    logger.info(
        f"Unified workflow complete: answer_len={len(result['final_answer'])}, "
        f"sources={result['sources']}, actions={result.get('actions_taken', [])}"
    )
    
    assistant_answer = result["final_answer"]
    prompt_details = result.get("prompt_details")
    
    logger.info(f"Prompt details available: {prompt_details is not None}")
    if prompt_details:
        logger.info(f"Prompt details keys: {list(prompt_details.keys())}")
    
    # Step 3: Persist user message (AFTER workflow to prevent chat_history duplication)
    # Background task for faster response
    def save_user_message():
        try:
            insert_message_pg(session_id, chat_request.user_context.tenant_id, chat_request.user_context.user_id, "user", chat_request.query)
            logger.info(f"[BG] User message saved to session {session_id}")
        except Exception as e:
            logger.error(f"[BG] Failed to save user message: {e}")
    
    background_tasks.add_task(save_user_message)
    
    # Step 4: Persist assistant message with metadata (async background task)
    def save_assistant_message():
        try:
            insert_message_pg(
                session_id=session_id,
                tenant_id=chat_request.user_context.tenant_id,
                user_id=chat_request.user_context.user_id,
                role="assistant",
                content=assistant_answer,
                metadata={
                    "execution_id": result.get("execution_id"),  # NEW: Workflow execution tracking
                    "sources": result.get("sources", []),
                    "rag_params": result.get("rag_params"),
                    "actions_taken": result.get("actions_taken"),
                    "workflow_path": result.get("workflow_path", "UNKNOWN")
                }
            )
            logger.info(f"[BG] Assistant message saved to session {session_id} (execution_id={result.get('execution_id')})")
        except Exception as e:
            logger.error(f"[BG] Failed to save assistant message: {e}")
    
    background_tasks.add_task(save_assistant_message)
    
    # Return with appropriate status code (201 for new session, 200 for existing)
    response_data = UnifiedChatResponse(
        answer=assistant_answer,
        sources=result["sources"],
        error=result.get("error"),
        session_id=session_id,
        execution_id=result.get("execution_id"),  # NEW: Include execution_id in response
        prompt_details=prompt_details,
        rag_params=result.get("rag_params"),
        llm_cache_info=result.get("llm_cache_info")
    )
    
    # Return 201 Created if new session, 200 OK if existing session
    if session_created:
        return Response(
            content=response_data.model_dump_json(),
            status_code=status.HTTP_201_CREATED,
            media_type="application/json"
        )
    
    return response_data  # 200 OK (default)
