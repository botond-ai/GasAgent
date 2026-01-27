"""
Ticket processor abstractions following SOLID principles.

Provides strategy pattern for ticket processing, allowing different
processing implementations without modifying existing code (Open/Closed Principle).
"""
from abc import ABC, abstractmethod
from typing import Any

from app.models.schemas import Ticket, TriageResponse
from app.core.logging import get_logger
from app.workflows.graph import SupportWorkflow

logger = get_logger(__name__)


class ITicketProcessor(ABC):
    """Interface for ticket processing (Open/Closed Principle).
    
    Implementations can be swapped without affecting clients.
    New processors can be added without modifying existing code.
    """

    @abstractmethod
    async def process(self, ticket: Ticket) -> TriageResponse:
        """Process a support ticket.
        
        Args:
            ticket: Ticket to process
            
        Returns:
            Triage response with AI-generated analysis and recommendations
            
        Raises:
            ProcessingError: If processing fails
        """
        pass

    @abstractmethod
    def can_process(self, ticket: Ticket) -> bool:
        """Check if this processor can handle the ticket.
        
        Args:
            ticket: Ticket to check
            
        Returns:
            True if processor can handle this ticket type
        """
        pass


class WorkflowTicketProcessor(ITicketProcessor):
    """Ticket processor using LangGraph workflow.
    
    Uses the SupportWorkflow to process tickets through
    the AI-powered triage and response generation workflow.
    """

    def __init__(self, workflow: SupportWorkflow):
        """Initialize processor with workflow.
        
        Args:
            workflow: SupportWorkflow instance for processing
        """
        self.workflow = workflow
        logger.info("Initialized WorkflowTicketProcessor")

    async def process(self, ticket: Ticket) -> TriageResponse:
        """Process ticket using workflow.
        
        Args:
            ticket: Ticket to process
            
        Returns:
            Triage response from workflow
            
        Raises:
            Exception: If workflow execution fails
        """
        logger.info(f"Processing ticket {ticket.id} with workflow")
        
        try:
            # Prepare workflow state
            state = {
                "ticket_id": ticket.id,
                "raw_message": ticket.message,
                "customer_name": ticket.customer_name,
                "customer_email": ticket.customer_email
            }
            
            # Try to load cached device context from chat API
            try:
                from app.api.dependencies import get_cache_service
                cache = get_cache_service()
                device_cache_key = f"device_context:{ticket.id}"
                device_context_data = await cache.get(device_cache_key)
                if device_context_data:
                    # Inject device context into state so fleet_lookup node skips but draft_answer uses it
                    state["device_context"] = device_context_data.get("context", "")
                    state["device_info"] = device_context_data.get("device_info")
                    logger.info(f"Loaded device context from cache for ticket {ticket.id}")
            except Exception as e:
                logger.warning(f"Could not load device context from cache: {e}")

            # Run workflow
            final_state = await self.workflow.process_ticket(state)

            # Extract and return output
            output = final_state.get("output", {})
            response = TriageResponse(**output)
            
            logger.info(f"Successfully processed ticket {ticket.id}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing ticket {ticket.id}: {e}", exc_info=True)
            raise

    def can_process(self, ticket: Ticket) -> bool:
        """Workflow processor can handle any ticket.
        
        Args:
            ticket: Ticket to check
            
        Returns:
            Always True
        """
        return True


class FastTrackTicketProcessor(ITicketProcessor):
    """Fast-track processor for simple/common issues.
    
    Processes common ticket types without full workflow
    for faster response times.
    
    This is an example of extending the system without modifying
    existing code (Open/Closed Principle).
    """

    def __init__(self):
        """Initialize fast-track processor."""
        logger.info("Initialized FastTrackTicketProcessor")

    async def process(self, ticket: Ticket) -> TriageResponse:
        """Process using fast-track rules.
        
        Args:
            ticket: Ticket to process
            
        Returns:
            Quick triage response for common issues
        """
        logger.info(f"Processing ticket {ticket.id} with fast-track processor")
        
        # Would implement fast-track logic here
        # For now, just log it
        raise NotImplementedError("Fast-track processor not yet implemented")

    def can_process(self, ticket: Ticket) -> bool:
        """Check if this is a common issue that can be fast-tracked.
        
        Args:
            ticket: Ticket to check
            
        Returns:
            True if ticket matches common patterns
        """
        # Examples of common issues that could be fast-tracked
        common_keywords = ["password reset", "account locked", "billing"]
        return any(
            keyword.lower() in ticket.message.lower()
            for keyword in common_keywords
        )


class CompositeTicketProcessor(ITicketProcessor):
    """Composite processor that tries multiple processors (Strategy Pattern).
    
    Tries each processor in order until one can handle the ticket.
    Enables flexible processor chain without modifying client code.
    """

    def __init__(self, processors: list[ITicketProcessor]):
        """Initialize with list of processors.
        
        Args:
            processors: List of processors to try in order
        """
        self.processors = processors
        logger.info(f"Initialized CompositeTicketProcessor with {len(processors)} processors")

    async def process(self, ticket: Ticket) -> TriageResponse:
        """Try processors until one succeeds.
        
        Args:
            ticket: Ticket to process
            
        Returns:
            Triage response from first processor that can handle it
            
        Raises:
            ValueError: If no processor can handle the ticket
        """
        logger.info(f"Processing ticket {ticket.id} with composite processor")
        
        for processor in self.processors:
            if processor.can_process(ticket):
                logger.info(f"Using processor {processor.__class__.__name__} for ticket {ticket.id}")
                return await processor.process(ticket)
        
        raise ValueError(f"No processor available for ticket {ticket.id}")

    def can_process(self, ticket: Ticket) -> bool:
        """Check if any processor can handle the ticket.
        
        Args:
            ticket: Ticket to check
            
        Returns:
            True if at least one processor can handle it
        """
        return any(processor.can_process(ticket) for processor in self.processors)
