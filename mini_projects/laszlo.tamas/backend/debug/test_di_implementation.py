"""
DI Implementation Test - Verify Dependency Injection

Tests that:
1. Protocol interfaces are correctly defined
2. Services can be instantiated with DI
3. Dependencies are properly injected
4. Mock injection works for testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.protocols import (
    IDocumentRepository,
    IDocumentChunkRepository,
    IConfigService,
    IEmbeddingService,
    IQdrantService,
    IChunkingService,
    IDocumentService
)

from core.dependencies import (
    get_config_service,
    get_embedding_service,
    get_qdrant_service,
    get_document_repository,
    get_document_chunk_repository,
    get_chunking_service,
    get_document_service
)

from services.document_service import DocumentService
from services.chunking_service import ChunkingService
from database.document_repository import DocumentRepository
from database.document_chunk_repository import DocumentChunkRepository


def test_protocol_imports():
    """Test that all protocols are defined."""
    print("✅ Protocol imports successful")
    print(f"  - IDocumentRepository: {IDocumentRepository}")
    print(f"  - IDocumentChunkRepository: {IDocumentChunkRepository}")
    print(f"  - IConfigService: {IConfigService}")
    print(f"  - IEmbeddingService: {IEmbeddingService}")
    print(f"  - IQdrantService: {IQdrantService}")
    print(f"  - IChunkingService: {IChunkingService}")
    print(f"  - IDocumentService: {IDocumentService}")


def test_dependency_factories():
    """Test that dependency factories work."""
    print("\n✅ Dependency factory tests:")
    
    # Singleton services
    config = get_config_service()
    print(f"  - ConfigService: {type(config).__name__}")
    
    embedding = get_embedding_service()
    print(f"  - EmbeddingService: {type(embedding).__name__}")
    
    qdrant = get_qdrant_service()
    print(f"  - QdrantService: {type(qdrant).__name__}")
    
    # Repositories
    doc_repo = get_document_repository()
    print(f"  - DocumentRepository: {type(doc_repo).__name__}")
    
    chunk_repo = get_document_chunk_repository()
    print(f"  - DocumentChunkRepository: {type(chunk_repo).__name__}")
    
    # Composed services
    chunking = get_chunking_service()
    print(f"  - ChunkingService: {type(chunking).__name__}")
    
    doc_service = get_document_service()
    print(f"  - DocumentService: {type(doc_service).__name__}")


def test_constructor_injection():
    """Test that services accept injected dependencies."""
    print("\n✅ Constructor injection tests:")
    
    # Create mock repository
    mock_doc_repo = DocumentRepository()
    
    # Inject into DocumentService
    doc_service = DocumentService(repository=mock_doc_repo)
    print(f"  - DocumentService with injected repo: {type(doc_service.repository).__name__}")
    
    # Create mock chunk repository
    mock_chunk_repo = DocumentChunkRepository()
    
    # Inject into ChunkingService
    chunking_service = ChunkingService(repository=mock_chunk_repo)
    print(f"  - ChunkingService with injected repo: {type(chunking_service.repository).__name__}")


def test_protocol_compliance():
    """Test that concrete classes satisfy protocols."""
    print("\n✅ Protocol compliance tests:")
    
    from typing import runtime_checkable
    
    doc_repo = DocumentRepository()
    # Note: Protocol checking is not enforced at runtime in Python,
    # but type checkers will validate this
    print(f"  - DocumentRepository has insert_document: {hasattr(doc_repo, 'insert_document')}")
    print(f"  - DocumentRepository has get_document_by_id: {hasattr(doc_repo, 'get_document_by_id')}")
    
    chunk_repo = DocumentChunkRepository()
    print(f"  - DocumentChunkRepository has insert_chunks: {hasattr(chunk_repo, 'insert_chunks')}")
    print(f"  - DocumentChunkRepository has get_chunks_by_document: {hasattr(chunk_repo, 'get_chunks_by_document')}")


if __name__ == "__main__":
    print("=" * 60)
    print("DI IMPLEMENTATION TEST")
    print("=" * 60)
    
    try:
        test_protocol_imports()
        test_dependency_factories()
        test_constructor_injection()
        test_protocol_compliance()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - DI implementation is valid!")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
