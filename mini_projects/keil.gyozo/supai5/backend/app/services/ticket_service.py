"""
Ticket service implementing business logic with SOLID principles.

Implements Single Responsibility Principle by handling only ticket
business logic orchestration, delegating persistence and processing
to injected dependencies.
"""
from typing import Optional, List
from datetime import datetime

from app.models.schemas import Ticket, TicketCreate, TriageResponse
from app.infrastructure.repositories import ITicketRepository
from app.infrastructure.cache import ICacheService
from app.services.processors import ITicketProcessor
from app.core.logging import get_logger

logger = get_logger(__name__)


class TicketService:
    """Ticket business logic service (Single Responsibility Principle).
    
    Handles ticket operations by orchestrating:
    - Repository for persistence
    - Processor for ticket processing
    - Cache for performance
    
    Dependencies are injected, not created, enabling:
    - Easy testing with mocks
    - Flexible implementation switching
    - Clear separation of concerns
    """

    def __init__(
        self,
        ticket_repository: ITicketRepository,
        ticket_processor: ITicketProcessor,
        cache_service: ICacheService
    ):
        """Initialize service with dependencies (Dependency Inversion Principle).
        
        Args:
            ticket_repository: Ticket persistence interface
            ticket_processor: Ticket processing interface
            cache_service: Cache service interface
        """
        self.repository = ticket_repository
        self.processor = ticket_processor
        self.cache = cache_service
        logger.info("Initialized TicketService")

    async def create_ticket(self, ticket_data: TicketCreate) -> Ticket:
        """Create a new support ticket.
        
        Single responsibility: Only creates tickets.
        Persistence delegated to repository.
        
        Args:
            ticket_data: Ticket creation data
            
        Returns:
            Created ticket with ID and metadata
        """
        logger.info(f"Creating ticket for {ticket_data.customer_email}")
        
        ticket = await self.repository.create(ticket_data)
        logger.info(f"Created ticket {ticket.id}")
        
        return ticket

    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Retrieve a ticket by ID.
        
        Single responsibility: Only retrieves tickets.
        Caching not needed for single ticket retrieval.
        
        Args:
            ticket_id: Unique ticket identifier
            
        Returns:
            Ticket if found, None otherwise
        """
        logger.info(f"Retrieving ticket {ticket_id}")
        
        ticket = await self.repository.get(ticket_id)
        if not ticket:
            logger.warning(f"Ticket not found: {ticket_id}")
        
        return ticket

    async def list_tickets(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Ticket]:
        """List tickets with optional filtering.
        
        Single responsibility: Only lists tickets.
        
        Args:
            status: Filter by ticket status
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of tickets matching criteria
        """
        logger.info(f"Listing tickets (status={status}, limit={limit}, offset={offset})")
        
        tickets = await self.repository.list(
            status=status,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Retrieved {len(tickets)} tickets")
        return tickets

    async def process_ticket(self, ticket_id: str) -> TriageResponse:
        """Process a support ticket through AI workflow.
        
        Orchestrates: retrieve → cache check → process → cache → return.
        Single responsibility: Only orchestrates ticket processing.
        
        Args:
            ticket_id: Ticket identifier
            
        Returns:
            Triage response with AI analysis and recommendations
            
        Raises:
            ValueError: If ticket not found
            Exception: If processing fails
        """
        logger.info(f"Processing ticket {ticket_id}")
        
        # Step 1: Retrieve ticket
        ticket = await self.repository.get(ticket_id)
        if not ticket:
            logger.error(f"Ticket not found: {ticket_id}")
            raise ValueError(f"Ticket not found: {ticket_id}")
        
        # Step 2: Check cache
        cache_key = f"triage:{ticket_id}"
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached result for ticket {ticket_id}")
            # Reconstruct TriageResponse from cached data
            return TriageResponse(**cached_result)
        
        # Step 3: Update status to processing
        ticket.status = "processing"
        await self.repository.update(ticket_id, ticket)
        logger.info(f"Updated ticket {ticket_id} status to processing")
        
        try:
            # Step 4: Process ticket
            response = await self.processor.process(ticket)
            
            # Step 5: Cache result
            await self.cache.set(
                cache_key,
                response.model_dump(),
                ttl=None  # Cache indefinitely, but could add TTL
            )
            logger.info(f"Cached triage result for ticket {ticket_id}")
            
            # Step 6: Update ticket with result
            ticket.status = "completed"
            ticket.triage_result = response
            await self.repository.update(ticket_id, ticket)
            logger.info(f"Updated ticket {ticket_id} status to completed")
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing ticket {ticket_id}: {e}", exc_info=True)
            
            # Update ticket status to error
            ticket.status = "error"
            await self.repository.update(ticket_id, ticket)
            logger.info(f"Updated ticket {ticket_id} status to error")
            
            raise

    async def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket.
        
        Single responsibility: Only deletes tickets.
        
        Args:
            ticket_id: Ticket identifier
            
        Returns:
            True if deleted successfully, False if not found
        """
        logger.info(f"Deleting ticket {ticket_id}")
        
        success = await self.repository.delete(ticket_id)
        if success:
            # Clear cache
            cache_key = f"triage:{ticket_id}"
            await self.cache.delete(cache_key)
            logger.info(f"Deleted ticket {ticket_id}")
        else:
            logger.warning(f"Ticket not found for deletion: {ticket_id}")
        
        return success

    async def update_ticket_status(
        self,
        ticket_id: str,
        status: str
    ) -> bool:
        """Update ticket status.
        
        Single responsibility: Only updates ticket status.
        
        Args:
            ticket_id: Ticket identifier
            status: New status value
            
        Returns:
            True if updated successfully, False if not found
        """
        logger.info(f"Updating ticket {ticket_id} status to {status}")
        
        ticket = await self.repository.get(ticket_id)
        if not ticket:
            logger.warning(f"Ticket not found: {ticket_id}")
            return False
        
        ticket.status = status
        success = await self.repository.update(ticket_id, ticket)
        
        if success:
            logger.info(f"Updated ticket {ticket_id} status to {status}")
        
        return success
