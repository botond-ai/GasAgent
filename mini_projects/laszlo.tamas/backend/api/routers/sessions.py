"""
Session Management Endpoints (ChatGPT-style)

Handles session CRUD operations and session-message relationships.
Session creation is implicit (via workflow), but management is explicit here.

Sessions follow RESTful patterns:
- Collection: /sessions (list)
- Resource: /sessions/{id} (get/update/delete)
- Sub-resource: /sessions/{id}/messages (chat history)
"""

import logging
from fastapi import APIRouter, HTTPException, Query, status, Response
from pydantic import BaseModel
from typing import Optional
from api.helpers import handle_api_error
from database.pg_init import (
    get_user_sessions,
    update_session_title,
    soft_delete_session,
    get_session_messages_pg,
    insert_message_pg
)
from services.memory_consolidation_service import get_consolidation_service
from api.schemas import ConsolidateSessionRequest

logger = logging.getLogger(__name__)
router = APIRouter()


class UpdateTitleRequest(BaseModel):
    title: str


class AddSystemMessageRequest(BaseModel):
    """Request body for adding system/assistant messages to chat history."""
    tenant_id: int
    user_id: int
    role: str  # "assistant" or "system"
    content: str
    metadata: Optional[dict] = None


@router.get("")
@handle_api_error("list user sessions")
async def list_user_sessions(user_id: int = Query(..., description="User ID")):
    """
    Get all sessions for a user, ordered by most recent activity.
    
    Returns sessions with:
        - id, title, created_at, last_message_at
        - message_count, is_deleted, processed_for_ltm
    
    Title fallback: "Új beszélgetés" if no title set
    
    Use case: ChatGPT-style sidebar with conversation list
    """
    sessions = get_user_sessions(user_id, include_deleted=False)
    
    # Format response: title fallback
    for session in sessions:
        if not session.get('title'):
            session['title'] = "Új beszélgetés"
    
    logger.info(f"Listed {len(sessions)} sessions for user_id={user_id}")
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/{session_id}/messages")
@handle_api_error("fetch session messages")
async def get_session_messages(
    session_id: str,
    user_id: int = Query(..., description="User ID for security check")
):
    """
    Get all messages for a specific session.
    
    Returns messages in chronological order with:
        - message_id, role, content, created_at, metadata
    
    Use case:
        - Load conversation history when user opens a session
        - Frontend chat display
    """
    messages = get_session_messages_pg(session_id)
    
    logger.info(f"Fetched {len(messages)} messages for session {session_id}")
    return {"messages": messages, "count": len(messages)}


@router.post("/{session_id}/messages")
@handle_api_error("add system message")
async def add_system_message(
    session_id: str,
    request: AddSystemMessageRequest
):
    """
    Add a system or assistant message to session history.
    
    Use case:
        - Manually inject system messages
        - Record assistant responses (if not done by workflow)
    
    Note: User messages are added by /chat workflow, not here.
    """
    logger.info(f"Adding {request.role} message to session {session_id}")
    
    insert_message_pg(
        session_id=session_id,
        role=request.role,
        content=request.content,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        metadata=request.metadata
    )
    
    return {"status": "message_added", "session_id": session_id}


@router.patch("/{session_id}/title")
@handle_api_error("update session title")
async def update_session_title_endpoint(
    session_id: str,
    update_data: UpdateTitleRequest
):
    """
    Update session title.
    
    Use case:
        - User renames conversation
        - Auto-title generation from first message
    """
    logger.info(f"Updating title for session {session_id}: '{update_data.title}'")
    
    update_session_title(session_id, update_data.title)
    
    return {
        "status": "title_updated",
        "session_id": session_id,
        "new_title": update_data.title
    }


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_api_error("delete session")
async def delete_session(session_id: str):
    """
    Soft delete a session.
    
    Sets is_deleted=True, doesn't actually delete data.
    
    Returns:
        204 No Content (empty body) on success
    
    Status Codes:
        204: Session successfully deleted (no content returned)
        404: Session not found
    
    Use case:
        - User deletes conversation from sidebar
        - Hide from session list but preserve for recovery
    """
    logger.info(f"✅ Soft deleted session {session_id}")
    
    soft_delete_session(session_id)
    
    # 204 No Content - empty body (REST best practice)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{session_id}/consolidate")
@handle_api_error("consolidate session memory")
async def consolidate_session_memory(
    session_id: str,
    request: ConsolidateSessionRequest
):
    """
    Consolidate session STM → LTM.
    
    Extracts key facts from conversation and stores as long-term memories.
    
    Use case:
        - Manual memory extraction
        - End of long conversation
        - Triggered by frontend "remember this" button
    
    Request body:
        {"user_context": {"tenant_id": 1, "user_id": 1}}
    
    Returns:
        {"status": "...", "memories_created": int}
    """
    user_id = request.user_context.user_id
    tenant_id = request.user_context.tenant_id
    logger.info(f"Starting memory consolidation for session {session_id} (user={user_id}, tenant={tenant_id})")
    
    # Fetch session to verify ownership
    from database.pg_init import get_session_by_id
    from api.helpers.error_handlers import NotFoundError
    session = get_session_by_id(session_id)
    if not session:
        raise NotFoundError("Session", session_id)
    
    # Verify tenant isolation and ownership
    if session["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    if session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Session belongs to different user")
    
    consolidation_service = get_consolidation_service()
    result = await consolidation_service.consolidate_session(
        session_id=session_id,
        user_id=user_id,
        tenant_id=tenant_id
    )
    
    return {
        "status": result["status"],
        "memories_created": result.get("memories_created", 0),
        "session_id": session_id
    }
