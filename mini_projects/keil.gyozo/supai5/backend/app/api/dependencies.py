"""
FastAPI dependency injection (Dependency Inversion Principle).

Implements service factory pattern to inject dependencies into routes,
enabling:
- Loose coupling between components
- Easy testing with mocks
- Flexible implementation switching
"""
from functools import lru_cache

from app.services.qdrant_service import QdrantService
from app.services.redis_service import RedisService
from app.services.rag_service import RAGService
from app.workflows.graph import SupportWorkflow
from app.workflows.nodes import WorkflowNodes
from app.infrastructure.repositories import (
    ITicketRepository,
    InMemoryTicketRepository,
    JsonFileTicketRepository
)
from app.core.config import settings
from app.infrastructure.cache import (
    ICacheService,
    InMemoryCacheService
)
from app.services.processors import (
    ITicketProcessor,
    WorkflowTicketProcessor
)
from app.services.ticket_service import TicketService


# Existing services (unchanged for backward compatibility)

@lru_cache()
def get_qdrant_service() -> QdrantService:
    """Get Qdrant service singleton."""
    return QdrantService()


@lru_cache()
def get_redis_service() -> RedisService:
    """Get Redis service singleton."""
    return RedisService()


@lru_cache()
def get_rag_service() -> RAGService:
    """Get RAG service singleton."""
    qdrant = get_qdrant_service()
    redis = get_redis_service()
    return RAGService(qdrant, redis)


@lru_cache()
def get_workflow() -> SupportWorkflow:
    """Get workflow singleton."""
    rag = get_rag_service()
    nodes = WorkflowNodes(rag)
    return SupportWorkflow(nodes)


# New SOLID-compliant dependencies

@lru_cache()
def get_ticket_repository() -> ITicketRepository:
    """Factory for ticket repository (Dependency Inversion Principle).

    Returns JSON file-based implementation for persistence across restarts.
    Can be swapped for database implementation without changing callers.
    """
    return JsonFileTicketRepository(file_path="data/tickets.json")


@lru_cache()
def get_cache_service() -> ICacheService:
    """Factory for cache service (Dependency Inversion Principle).
    
    Returns in-memory implementation for now.
    Can be swapped for Redis or other backend without changing callers.
    """
    return InMemoryCacheService()


@lru_cache()
def get_ticket_processor() -> ITicketProcessor:
    """Factory for ticket processor (Open/Closed Principle).
    
    Returns workflow processor for now.
    Can be extended with new processor types without modifying existing code.
    """
    workflow = get_workflow()
    return WorkflowTicketProcessor(workflow)


@lru_cache()
def get_ticket_service() -> TicketService:
    """Factory for ticket service (Dependency Injection Container).
    
    Composes dependencies and returns configured service.
    This is the central place to manage service creation and dependency wiring.
    
    Returns:
        Configured TicketService instance with all dependencies injected
    """
    repository = get_ticket_repository()
    processor = get_ticket_processor()
    cache = get_cache_service()
    
    return TicketService(
        ticket_repository=repository,
        ticket_processor=processor,
        cache_service=cache
    )
