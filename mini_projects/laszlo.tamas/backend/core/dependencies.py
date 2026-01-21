"""
Dependency Injection Container for FastAPI.

Provides centralized factory functions for all services and repositories,
enabling testability and loose coupling through constructor injection.
"""

import logging
from functools import lru_cache
from typing import Optional

# Import concrete implementations
from database.document_repository import DocumentRepository
from database.document_chunk_repository import DocumentChunkRepository
from services.config_service import ConfigService
from services.embedding_service import EmbeddingService
from services.qdrant_service import QdrantService
from services.chunking_service import ChunkingService
from services.document_service import DocumentService
from services.unified_chat_workflow import UnifiedChatWorkflow

# Import protocols (for type hints)
from services.protocols import (
    IDocumentRepository,
    IDocumentChunkRepository,
    IConfigService,
    IEmbeddingService,
    IQdrantService,
    IChunkingService,
    IDocumentService
)

logger = logging.getLogger(__name__)


# ===== SINGLETON FACTORIES (Stateless Services) =====

@lru_cache(maxsize=1)
def get_config_service() -> IConfigService:
    """
    Get singleton ConfigService instance.
    
    Stateless service, safe to cache.
    """
    return ConfigService()


@lru_cache(maxsize=1)
def get_embedding_service() -> IEmbeddingService:
    """
    Get singleton EmbeddingService instance.
    
    Uses OpenAI API, stateless except for client connection.
    """
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_qdrant_service() -> IQdrantService:
    """
    Get singleton QdrantService instance.
    
    Manages Qdrant client connection, safe to reuse.
    """
    return QdrantService()


# ===== REPOSITORY FACTORIES (Stateless) =====

def get_document_repository() -> IDocumentRepository:
    """
    Get DocumentRepository instance.
    
    Stateless repository, uses context manager for connections.
    No caching needed - lightweight instantiation.
    """
    return DocumentRepository()


def get_document_chunk_repository() -> IDocumentChunkRepository:
    """
    Get DocumentChunkRepository instance.
    
    Stateless repository, uses context manager for connections.
    """
    return DocumentChunkRepository()


# ===== COMPOSED SERVICE FACTORIES (Dependencies Injected) =====

def get_chunking_service(
    chunk_repository: Optional[IDocumentChunkRepository] = None
) -> IChunkingService:
    """
    Get ChunkingService with injected dependencies.
    
    Args:
        chunk_repository: Optional repository override (for testing)
    
    Returns:
        Configured ChunkingService instance
    """
    if chunk_repository is None:
        chunk_repository = get_document_chunk_repository()
    
    return ChunkingService(repository=chunk_repository)


def get_document_service(
    doc_repository: Optional[IDocumentRepository] = None
) -> IDocumentService:
    """
    Get DocumentService with injected dependencies.
    
    Args:
        doc_repository: Optional repository override (for testing)
    
    Returns:
        Configured DocumentService instance
    """
    if doc_repository is None:
        doc_repository = get_document_repository()
    
    return DocumentService(repository=doc_repository)


@lru_cache(maxsize=1)
def get_unified_chat_workflow() -> UnifiedChatWorkflow:
    """
    Get singleton UnifiedChatWorkflow instance.
    
    Workflow holds session state, but is safe to cache as singleton
    because it manages multiple sessions internally.
    """
    return UnifiedChatWorkflow()


# ===== FACTORY RESET (For Testing) =====

def reset_singletons():
    """
    Clear all singleton caches.
    
    WARNING: Use only in tests or during application restart.
    """
    get_config_service.cache_clear()
    get_embedding_service.cache_clear()
    get_qdrant_service.cache_clear()
    
    logger.warning("🔄 All singleton caches cleared")
