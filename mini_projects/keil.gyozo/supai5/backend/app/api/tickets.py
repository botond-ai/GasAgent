"""
Ticket management API endpoints (Single Responsibility Principle).

This module contains only HTTP request/response handling.
All business logic is delegated to TicketService.
All persistence is delegated to TicketRepository.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from app.models.schemas import Ticket, TicketCreate, TriageResponse
from app.services.ticket_service import TicketService
from app.api.dependencies import get_ticket_service
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=Ticket, status_code=201)
async def create_ticket(
    ticket_data: TicketCreate,
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Ticket:
    """Create a new support ticket.
    
    Single Responsibility: Only handles HTTP concerns.
    All business logic delegated to TicketService.

    Args:
        ticket_data: Ticket creation data
        ticket_service: Injected ticket service

    Returns:
        Created ticket with ID and metadata
    """
    logger.info(f"HTTP POST /tickets - Creating ticket for {ticket_data.customer_email}")
    
    ticket = await ticket_service.create_ticket(ticket_data)
    
    logger.info(f"HTTP 201 - Created ticket: {ticket.id}")
    return ticket


@router.get("/", response_model=list[Ticket])
async def list_tickets(
    status: Optional[str] = None,
    limit: int = 50,
    ticket_service: TicketService = Depends(get_ticket_service)
) -> list[Ticket]:
    """
    List support tickets.

    Args:
        status: Filter by status
        limit: Maximum number of tickets
        ticket_service: Injected ticket service (SRP: only HTTP handling)

    Returns:
        List of tickets
    """
    tickets = await ticket_service.list_tickets(status=status, limit=limit)
    return tickets


@router.get("/{ticket_id}", response_model=Ticket)
async def get_ticket(
    ticket_id: str,
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Ticket:
    """
    Get ticket by ID.

    Args:
        ticket_id: Ticket identifier
        ticket_service: Injected ticket service (SRP: only HTTP handling)

    Returns:
        Ticket details

    Raises:
        HTTPException: If ticket not found
    """
    ticket = await ticket_service.get_ticket(ticket_id)
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket


@router.post("/{ticket_id}/process", response_model=TriageResponse)
async def process_ticket(
    ticket_id: str,
    ticket_service: TicketService = Depends(get_ticket_service)
) -> TriageResponse:
    """
    Process ticket through AI workflow.

    Args:
        ticket_id: Ticket identifier
        ticket_service: Injected ticket service (SRP: only HTTP handling, delegates to TicketService)

    Returns:
        Triage and draft response

    Raises:
        HTTPException: If ticket not found or processing fails
    """
    try:
        ticket = await ticket_service.get_ticket(ticket_id)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        response = await ticket_service.process_ticket(ticket_id)
        logger.info(f"Successfully processed ticket: {ticket_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(
    ticket_id: str,
    ticket_service: TicketService = Depends(get_ticket_service)
) -> None:
    """
    Delete a ticket.

    Args:
        ticket_id: Ticket identifier
        ticket_service: Injected ticket service (SRP: only HTTP handling)

    Raises:
        HTTPException: If ticket not found
    """
    ticket = await ticket_service.get_ticket(ticket_id)
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await ticket_service.delete_ticket(ticket_id)
    logger.info(f"Deleted ticket: {ticket_id}")
