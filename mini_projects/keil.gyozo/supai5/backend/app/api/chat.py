"""
Chat API endpoints for session-based conversations.
Implements the Memory layer interface for the frontend.
"""
from typing import Optional, List
import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import uuid

from app.services.conversation_service import (
    ConversationService,
    ConversationMessage,
    ConversationSession,
    get_conversation_service,
)
from app.services.ticket_service import TicketService
from app.api.dependencies import get_ticket_service
from app.models.schemas import TicketCreate
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Request/Response models
class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    content: str = Field(..., min_length=1, description="Message content")
    session_id: Optional[str] = Field(None, description="Session ID (auto-created if not provided)")


class ChatMessageResponse(BaseModel):
    """Response with AI-generated reply."""
    session_id: str
    message: str
    metadata: Optional[dict] = None


class ChatHistoryResponse(BaseModel):
    """Response with conversation history."""
    session_id: str
    messages: List[dict]


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""
    user_id: Optional[str] = None
    context: Optional[dict] = None


class SessionResponse(BaseModel):
    """Response with session details."""
    session_id: str
    created: bool


# Dependency injection
async def get_conversation_service_dep() -> ConversationService:
    """Get conversation service dependency."""
    return get_conversation_service()


def extract_hostname_from_message(message: str) -> Optional[str]:
    """Extract hostname from chat message."""
    logger.info(f"Extracting hostname from message: {message[:100]}...")
    
    # Pattern 1: Look for "hostname:" or "Hostname:" followed by hostname (handles quoted versions too)
    match = re.search(r'[Hh]ostname\s*:\s*["\']?([A-Z0-9][A-Za-z0-9\-_]{1,})["\']?', message)
    if match:
        hostname = match.group(1).upper()
        logger.info(f"Found hostname via keyword pattern: {hostname}")
        return hostname
    
    # Pattern 2: Try specific corporate hostname patterns
    patterns = [r'PD-NB\d+', r'[A-Z]{2,3}-\d{5,}', r'DESKTOP-[A-Z0-9]+', r'[A-Z]+-NB\d+']
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            hostname = match.group(0).upper()
            logger.info(f"Found hostname via pattern {pattern}: {hostname}")
            return hostname
    
    # Pattern 3: Look after "gép:", "laptop:", "computer:", "pc:" keywords
    match = re.search(r'(?:gép|laptop|computer|pc|machine)\s*:\s*["\']?([A-Z0-9][A-Za-z0-9\-_]{1,})["\']?', message, re.IGNORECASE)
    if match:
        hostname = match.group(1).upper()
        logger.info(f"Found hostname via device keyword: {hostname}")
        return hostname
    
    logger.info("No hostname found in message")
    return None


async def lookup_device_info(hostname: str) -> Optional[dict]:
    """Look up device information from Fleet API."""
    try:
        from app.services.fleet import create_fleet_client
        
        fleet = create_fleet_client()
        if not fleet.enabled:
            logger.info("FleetDM not configured")
            return None
        
        logger.info(f"Looking up device: {hostname}")
        device_info = await fleet.search_host(hostname)
        
        if device_info and device_info.id:
            # Get full details
            details = await fleet.get_host_details(device_info.id)
            if details:
                device_info = details
        
        if device_info:
            device_context = fleet.format_device_context(device_info)
            
            # Add intelligent alerts for device issues (same as in nodes.py)
            alerts = _analyze_device_issues(device_info)
            if alerts:
                device_context += "\n\n**DEVICE ALERTS:**\n" + "\n".join([f"⚠️  {alert}" for alert in alerts])
            
            logger.info(f"Found device: {device_info.hostname}")
            return {
                "hostname": device_info.hostname,
                "context": device_context,
                "device_info": device_info
            }
        else:
            logger.info(f"Device not found: {hostname}")
            return None
            
    except Exception as e:
        logger.error(f"Error looking up device: {e}")
        return None


def _analyze_device_issues(device_info) -> list:
    """Analyze device info and identify potential issues with alerts."""
    alerts = []
    
    try:
        # Check disk space
        if hasattr(device_info, 'disk_space_available') and device_info.disk_space_available:
            # Typically in GB, warn if less than 10GB or less than 5%
            disk_available = device_info.disk_space_available
            if isinstance(disk_available, str):
                # Parse "7.0 GB (1%)" format
                import re
                match = re.search(r'(\d+\.?\d*)\s*GB', disk_available)
                if match:
                    disk_gb = float(match.group(1))
                    if disk_gb < 10:
                        alerts.append(f"Low disk space: Only {disk_gb}GB available. Recommend cleanup or expansion.")
        
        # Check policy failures
        if hasattr(device_info, 'policy_issues') and device_info.policy_issues:
            issues = device_info.policy_issues
            if isinstance(issues, dict):
                failing = issues.get('failing', 0)
                total = issues.get('total', 0)
                if failing > 0:
                    alerts.append(f"Security policies failing: {failing}/{total} policies. This requires immediate attention from IT.")
            elif isinstance(issues, str) and 'failing' in issues.lower():
                alerts.append(f"Security policies failing: {issues}")
        
        # Check if offline
        if hasattr(device_info, 'status') and device_info.status and device_info.status.lower() != 'online':
            alerts.append(f"Device status: {device_info.status}. May have connectivity issues.")
        
        # Check memory (if less than 4GB, could be performance issue)
        if hasattr(device_info, 'memory') and device_info.memory:
            memory_str = str(device_info.memory).lower()
            if 'gb' in memory_str:
                import re
                match = re.search(r'(\d+\.?\d*)', memory_str)
                if match:
                    memory_gb = float(match.group(1))
                    if memory_gb < 4:
                        alerts.append(f"Low memory: {memory_gb}GB RAM. May cause performance issues. Consider upgrade.")
        
    except Exception as e:
        logger.warning(f"Error analyzing device issues: {e}")
    
    return alerts


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    conversation_service: ConversationService = Depends(get_conversation_service_dep),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> ChatMessageResponse:
    """
    Send a chat message and get AI response.

    This endpoint:
    1. Creates/retrieves session
    2. Stores user message in conversation history
    3. Creates a ticket for processing
    4. Processes through AI workflow
    5. Stores AI response in conversation history
    6. Returns the response

    Args:
        request: Chat message request
        conversation_service: Injected conversation service
        ticket_service: Injected ticket service

    Returns:
        AI-generated response with session ID
    """
    # Get or create session
    session_id = request.session_id or str(uuid.uuid4())
    session = await conversation_service.get_session(session_id)

    if not session:
        session = await conversation_service.create_session(session_id)
        logger.info(f"Created new chat session: {session_id}")

    # Add user message to history
    await conversation_service.add_message(
        session_id=session_id,
        role="user",
        content=request.content
    )

    try:
        # Try to extract hostname and lookup device info
        hostname = extract_hostname_from_message(request.content)
        device_info_result = None
        
        if hostname:
            device_info_result = await lookup_device_info(hostname)
            if device_info_result:
                logger.info(f"Device info retrieved for {hostname}")
        
        # Create ticket from message
        ticket_data = TicketCreate(
            customer_name="Chat User",
            customer_email="chat@session.local",
            subject=request.content[:100],
            message=request.content
        )
        ticket = await ticket_service.create_ticket(ticket_data)

        # Link ticket to session
        context = {"last_ticket_id": ticket.id}
        if device_info_result:
            context["device_info"] = device_info_result
            context["device_context"] = device_info_result.get("context", "")
            logger.info(f"Adding device context to ticket {ticket.id}")
        
        await conversation_service.update_context(
            session_id=session_id,
            context=context
        )

        # **IMPORTANT**: Store device context in cache so workflow can access it
        if device_info_result:
            from app.api.dependencies import get_cache_service
            cache = get_cache_service()
            device_cache_key = f"device_context:{ticket.id}"
            await cache.set(device_cache_key, device_info_result, ttl=3600)
            logger.info(f"Cached device context for ticket {ticket.id}")

        # Process through AI workflow
        result = await ticket_service.process_ticket(ticket.id)

        # Debug: log citations
        logger.info(f"chat.py: result.citations = {result.citations}")
        logger.info(f"chat.py: citations count = {len(result.citations) if result.citations else 0}")

        # Format AI response
        ai_content = "\n\n".join(filter(None, [
            result.answer_draft.greeting,
            result.answer_draft.body,
            result.answer_draft.closing
        ]))

        # Append citations if available
        if result.citations:
            citations_text = "\n\n**Sources:**"
            for i, citation in enumerate(result.citations, 1):
                source = citation.source if hasattr(citation, 'source') else citation.get('source', 'Unknown')
                text = citation.text if hasattr(citation, 'text') else citation.get('text', '')
                # Truncate long citation text
                if len(text) > 150:
                    text = text[:150] + "..."
                citations_text += f"\n[{i}] {source}: {text}"
            ai_content += citations_text

        # Append device info if found
        if device_info_result:
            device_context = device_info_result.get("context", "")
            if device_context:
                ai_content += f"\n\n**Device Information:**\n{device_context}"

        # Store AI response in history
        metadata = {
            "ticket_id": ticket.id,
            "category": result.triage.category,
            "priority": result.triage.priority,
            "sentiment": result.triage.sentiment,
        }
        if device_info_result:
            metadata["device_hostname"] = device_info_result.get("hostname")
        
        await conversation_service.add_message(
            session_id=session_id,
            role="assistant",
            content=ai_content,
            metadata=metadata
        )

        return ChatMessageResponse(
            session_id=session_id,
            message=ai_content,
            metadata=metadata
        )

    except Exception as e:
        logger.error(f"Error processing chat message: {e}", exc_info=True)

        # Store error in history
        error_msg = "I apologize, but I encountered an error processing your request. Please try again."
        await conversation_service.add_message(
            session_id=session_id,
            role="assistant",
            content=error_msg,
            metadata={"error": str(e)}
        )

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_history(
    session_id: str,
    last_n: Optional[int] = None,
    conversation_service: ConversationService = Depends(get_conversation_service_dep)
) -> ChatHistoryResponse:
    """
    Get conversation history for a session.

    Args:
        session_id: Session identifier
        last_n: Limit to last N messages
        conversation_service: Injected conversation service

    Returns:
        Conversation history
    """
    messages = await conversation_service.get_history(session_id, last_n)

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[msg.model_dump(mode='json') for msg in messages]
    )


@router.post("/session", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    conversation_service: ConversationService = Depends(get_conversation_service_dep)
) -> SessionResponse:
    """
    Create a new chat session.

    Args:
        request: Session creation request
        conversation_service: Injected conversation service

    Returns:
        New session ID
    """
    session_id = str(uuid.uuid4())
    await conversation_service.create_session(
        session_id=session_id,
        user_id=request.user_id,
        context=request.context
    )

    return SessionResponse(
        session_id=session_id,
        created=True
    )


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service_dep)
) -> None:
    """
    Delete a chat session.

    Args:
        session_id: Session identifier
        conversation_service: Injected conversation service
    """
    deleted = await conversation_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
