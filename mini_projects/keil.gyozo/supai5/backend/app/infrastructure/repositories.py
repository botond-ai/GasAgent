"""
Repository abstractions following SOLID principles.

Provides interface-based access to data persistence, allowing
different implementations (in-memory, database, JSON file, etc.) without
affecting business logic.
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import uuid
import json
import asyncio
from filelock import FileLock

from app.models.schemas import Ticket, TicketCreate
from app.core.logging import get_logger

logger = get_logger(__name__)


class ITicketRepository(ABC):
    """Interface for ticket persistence (Interface Segregation Principle).
    
    Clients depend only on this interface, not concrete implementations.
    """

    @abstractmethod
    async def create(self, ticket_data: TicketCreate) -> Ticket:
        """Create a new ticket.
        
        Args:
            ticket_data: Ticket creation data
            
        Returns:
            Created ticket with ID and metadata
        """
        pass

    @abstractmethod
    async def get(self, ticket_id: str) -> Optional[Ticket]:
        """Retrieve a ticket by ID.
        
        Args:
            ticket_id: Unique ticket identifier
            
        Returns:
            Ticket if found, None otherwise
        """
        pass

    @abstractmethod
    async def list(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Ticket]:
        """List tickets with optional filtering.
        
        Args:
            status: Filter by ticket status
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of tickets matching criteria
        """
        pass

    @abstractmethod
    async def update(self, ticket_id: str, ticket: Ticket) -> bool:
        """Update an existing ticket.
        
        Args:
            ticket_id: Ticket identifier
            ticket: Updated ticket data
            
        Returns:
            True if successful, False if not found
        """
        pass

    @abstractmethod
    async def delete(self, ticket_id: str) -> bool:
        """Delete a ticket.
        
        Args:
            ticket_id: Ticket identifier
            
        Returns:
            True if successful, False if not found
        """
        pass


class InMemoryTicketRepository(ITicketRepository):
    """In-memory ticket repository implementation.
    
    Suitable for development and testing.
    Thread-safe using dictionary.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._tickets: dict[str, Ticket] = {}

    async def create(self, ticket_data: TicketCreate) -> Ticket:
        """Create and store a new ticket."""
        ticket = Ticket(
            id=str(uuid.uuid4()),
            customer_name=ticket_data.customer_name,
            customer_email=ticket_data.customer_email,
            subject=ticket_data.subject,
            message=ticket_data.message,
            created_at=datetime.utcnow(),
            status="new"
        )
        self._tickets[ticket.id] = ticket
        return ticket

    async def get(self, ticket_id: str) -> Optional[Ticket]:
        """Retrieve a ticket by ID."""
        return self._tickets.get(ticket_id)

    async def list(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Ticket]:
        """List tickets with optional filtering."""
        tickets = list(self._tickets.values())
        
        # Filter by status if provided
        if status:
            tickets = [t for t in tickets if t.status == status]
        
        # Sort by created_at descending
        tickets.sort(key=lambda t: t.created_at, reverse=True)
        
        # Apply pagination
        return tickets[offset:offset + limit]

    async def update(self, ticket_id: str, ticket: Ticket) -> bool:
        """Update an existing ticket."""
        if ticket_id not in self._tickets:
            return False
        self._tickets[ticket_id] = ticket
        return True

    async def delete(self, ticket_id: str) -> bool:
        """Delete a ticket."""
        if ticket_id not in self._tickets:
            return False
        del self._tickets[ticket_id]
        return True


class JsonFileTicketRepository(ITicketRepository):
    """JSON file-based ticket repository implementation.

    Persists tickets to a JSON file for durability across restarts.
    Thread-safe using file locking.
    """

    def __init__(self, file_path: str = "data/tickets.json"):
        """Initialize JSON file storage.

        Args:
            file_path: Path to the JSON file for persistence
        """
        self._file_path = Path(file_path)
        self._lock_path = Path(f"{file_path}.lock")
        self._lock = FileLock(self._lock_path)

        # Ensure directory exists
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file if it doesn't exist
        if not self._file_path.exists():
            self._save_tickets({})
            logger.info(f"Created new tickets file: {self._file_path}")
        else:
            logger.info(f"Using existing tickets file: {self._file_path}")

    def _load_tickets(self) -> dict[str, dict]:
        """Load tickets from JSON file."""
        try:
            with self._lock:
                if not self._file_path.exists():
                    return {}
                with open(self._file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {self._file_path}, returning empty dict")
            return {}
        except Exception as e:
            logger.error(f"Error loading tickets: {e}")
            return {}

    def _save_tickets(self, tickets: dict[str, dict]) -> None:
        """Save tickets to JSON file."""
        try:
            with self._lock:
                with open(self._file_path, 'w', encoding='utf-8') as f:
                    json.dump(tickets, f, indent=2, default=str, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving tickets: {e}")
            raise

    def _ticket_to_dict(self, ticket: Ticket) -> dict:
        """Convert Ticket model to dictionary for JSON storage."""
        return ticket.model_dump(mode='json')

    def _dict_to_ticket(self, data: dict) -> Ticket:
        """Convert dictionary to Ticket model."""
        return Ticket.model_validate(data)

    async def create(self, ticket_data: TicketCreate) -> Ticket:
        """Create and persist a new ticket."""
        ticket = Ticket(
            id=str(uuid.uuid4()),
            customer_name=ticket_data.customer_name,
            customer_email=ticket_data.customer_email,
            subject=ticket_data.subject,
            message=ticket_data.message,
            created_at=datetime.utcnow(),
            status="new"
        )

        # Run file I/O in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._create_sync, ticket)

        logger.info(f"Created and persisted ticket {ticket.id}")
        return ticket

    def _create_sync(self, ticket: Ticket) -> None:
        """Synchronous create operation."""
        tickets = self._load_tickets()
        tickets[ticket.id] = self._ticket_to_dict(ticket)
        self._save_tickets(tickets)

    async def get(self, ticket_id: str) -> Optional[Ticket]:
        """Retrieve a ticket by ID from file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_sync, ticket_id)

    def _get_sync(self, ticket_id: str) -> Optional[Ticket]:
        """Synchronous get operation."""
        tickets = self._load_tickets()
        data = tickets.get(ticket_id)
        if data:
            return self._dict_to_ticket(data)
        return None

    async def list(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Ticket]:
        """List tickets with optional filtering from file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._list_sync, status, limit, offset)

    def _list_sync(
        self,
        status: Optional[str],
        limit: int,
        offset: int
    ) -> List[Ticket]:
        """Synchronous list operation."""
        tickets_data = self._load_tickets()
        tickets = [self._dict_to_ticket(data) for data in tickets_data.values()]

        # Filter by status if provided
        if status:
            tickets = [t for t in tickets if t.status == status]

        # Sort by created_at descending
        tickets.sort(key=lambda t: t.created_at, reverse=True)

        # Apply pagination
        return tickets[offset:offset + limit]

    async def update(self, ticket_id: str, ticket: Ticket) -> bool:
        """Update an existing ticket in file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._update_sync, ticket_id, ticket)

    def _update_sync(self, ticket_id: str, ticket: Ticket) -> bool:
        """Synchronous update operation."""
        tickets = self._load_tickets()
        if ticket_id not in tickets:
            return False
        tickets[ticket_id] = self._ticket_to_dict(ticket)
        self._save_tickets(tickets)
        logger.info(f"Updated ticket {ticket_id}")
        return True

    async def delete(self, ticket_id: str) -> bool:
        """Delete a ticket from file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._delete_sync, ticket_id)

    def _delete_sync(self, ticket_id: str) -> bool:
        """Synchronous delete operation."""
        tickets = self._load_tickets()
        if ticket_id not in tickets:
            return False
        del tickets[ticket_id]
        self._save_tickets(tickets)
        logger.info(f"Deleted ticket {ticket_id}")
        return True
