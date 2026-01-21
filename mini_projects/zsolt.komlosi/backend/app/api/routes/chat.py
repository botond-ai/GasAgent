"""
Chat API endpoint.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException

from app.models import ChatRequest, ChatResponse, ErrorResponse
from app.api.deps import get_agent

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    responses={500: {"model": ErrorResponse}},
)
async def chat(
    request: ChatRequest,
    agent=Depends(get_agent),
):
    """
    Process a chat message or support ticket.

    Returns triage information, answer draft with citations,
    and policy check results.
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Process with agent
        result = agent.analyze(
            ticket_text=request.message,
            ip_address=request.ip_address,
            session_id=session_id,
        )

        return ChatResponse(
            success=True,
            data=result,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session history."""
    # TODO: Implement with memory module
    return {"session_id": session_id, "messages": []}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    # TODO: Implement with memory module
    return {"status": "deleted", "session_id": session_id}
