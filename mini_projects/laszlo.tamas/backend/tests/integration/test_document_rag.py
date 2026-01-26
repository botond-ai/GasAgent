"""
Integration Test: Document RAG Pipeline
Knowledge Router PROD

Tests the complete document processing pipeline:
1. Document upload
2. Chunking
3. Embedding generation
4. Qdrant storage
5. Retrieval via chat query

Priority: HIGH (core RAG functionality)
"""

import pytest
import os
from services.embedding_service import EmbeddingService
from services.qdrant_service import QdrantService
from database.pg_init import (
    create_document,
    create_document_chunk,
    get_chunks_for_document,
    update_chunk_embedding
)
from config.settings import get_embedding_dimensions


@pytest.mark.integration
class TestDocumentRAGPipeline:
    """Test complete document RAG pipeline."""
    
    @pytest.fixture(scope="class")
    def embedding_service(self):
        """Create EmbeddingService instance."""
        return EmbeddingService()
    
    @pytest.fixture(scope="class")
    def qdrant_service(self):
        """Create QdrantService instance."""
        return QdrantService()
    
    # ========================================================================
    # DOCUMENT & CHUNK CREATION
    # ========================================================================
    
    def test_insert_document(self, db_session, test_tenant_user):
        """Test document insertion to PostgreSQL."""
        doc_id = create_document(
            tenant_id=test_tenant_user["tenant_id"],
            user_id=test_tenant_user["user_id"],
            visibility="private",
            source="upload",
            title="Integration Test Document",
            content="This is a test document for integration testing. It contains test data."
        )
        
        assert doc_id is not None, "Document ID should not be None"
        assert isinstance(doc_id, int), "Document ID should be integer"
    
    def test_insert_document_chunk(self, db_session, test_document):
        """Test document chunk insertion."""
        # Use chunk_index=10 to avoid collision with test_document fixture chunks (0,1,2)
        chunk_id = create_document_chunk(
            tenant_id=test_document["tenant_id"],
            document_id=test_document["document_id"],
            chunk_index=10,  # Avoid collision with fixture chunks
            start_offset=0,
            end_offset=100,
            content="This is a test chunk for integration testing.",
            chapter_name="Test Section"
        )
        
        assert chunk_id is not None, "Chunk ID should not be None"
        assert isinstance(chunk_id, int), "Chunk ID should be integer"
    
    def test_get_chunks_for_document(self, db_session, test_document):
        """Test retrieving chunks for a document."""
        chunks = get_chunks_for_document(test_document["document_id"])
        
        assert chunks is not None, "Chunks should not be None"
        assert isinstance(chunks, list), "Chunks should be a list"
        assert len(chunks) > 0, "Should have at least one chunk"
    
    # ========================================================================
    # EMBEDDING GENERATION
    # ========================================================================
    
    @pytest.mark.openai
    def test_generate_embedding_real(self, embedding_service):
        """
        Test embedding generation with real OpenAI API.
        
        Real OpenAI call - costs ~$0.0001
        """
        text = "This is a test document for embedding generation."
        embedding = embedding_service.generate_embedding(text)
        
        expected_dims = get_embedding_dimensions()
        assert embedding is not None, "Embedding should not be None"
        assert isinstance(embedding, list), "Embedding should be a list"
        assert len(embedding) == expected_dims, f"Should return {expected_dims} dimensions (from env OPENAI_MODEL_EMBEDDING)"
        assert all(isinstance(x, float) for x in embedding), "Embedding values should be floats"
    
    @pytest.mark.skip(reason="OpenAI SDK v1+ requires client.embeddings.create patch, not openai.Embedding.create")
    def test_generate_embedding_mocked(self, embedding_service, mock_openai_embedding):
        """Test embedding generation with mocked OpenAI (no cost)."""
        text = "This is a test document for embedding generation."
        embedding = embedding_service.generate_embedding(text)
        
        expected_dims = get_embedding_dimensions()
        assert embedding is not None, "Embedding should not be None"
        assert isinstance(embedding, list), "Embedding should be a list"
        assert len(embedding) == expected_dims, f"Should return {expected_dims} dimensions (from env OPENAI_MODEL_EMBEDDING)"
        assert mock_openai_embedding.called, "OpenAI mock should be called"
    
    # ========================================================================
    # QDRANT OPERATIONS
    # ========================================================================
    
    def test_qdrant_connection(self, qdrant_client):
        """Test Qdrant client connection."""
        collections = qdrant_client.get_collections()
        assert collections is not None, "Should be able to list collections"
    
    @pytest.mark.openai
    def test_upload_chunk_to_qdrant_real(
        self, 
        qdrant_service, 
        embedding_service,
        test_document,
        clean_qdrant_collection
    ):
        """
        Test uploading chunk to Qdrant with real embedding.
        
        Real OpenAI call - costs ~$0.0001
        """
        # Get first chunk
        chunks = get_chunks_for_document(test_document["document_id"])
        assert len(chunks) > 0, "Should have chunks"
        chunk = chunks[0]
        
        # Generate real embedding
        embedding = embedding_service.generate_embedding(chunk["content"])
        
        # Upload to Qdrant (use test collection)
        point_id = qdrant_service.upsert_document_chunk(
            chunk_id=chunk["id"],
            embedding=embedding,
            tenant_id=test_document["tenant_id"],
            metadata={
                "document_id": test_document["document_id"],
                "chunk_index": chunk["chunk_index"]
            },
            collection_name=clean_qdrant_collection
        )
        
        assert point_id is not None, "Point ID should not be None"
    
    @pytest.mark.openai
    def test_search_qdrant_real(
        self,
        qdrant_service,
        embedding_service,
        test_document,
        clean_qdrant_collection
    ):
        """
        Test searching Qdrant with real query.
        
        Real OpenAI call - costs ~$0.0002 (upload + search)
        """
        # First upload a chunk
        chunks = get_chunks_for_document(test_document["document_id"])
        chunk = chunks[0]
        
        embedding = embedding_service.generate_embedding(chunk["content"])
        qdrant_service.upsert_document_chunk(
            chunk_id=chunk["id"],
            embedding=embedding,
            tenant_id=test_document["tenant_id"],
            user_id=test_document["user_id"],
            visibility="private",  # Match fixture document visibility
            metadata={
                "document_id": test_document["document_id"],
                "chunk_index": chunk["chunk_index"]
            },
            collection_name=clean_qdrant_collection
        )
        
        # Now search with similar query
        query = "test document pytest"
        query_embedding = embedding_service.generate_embedding(query)
        
        from services.qdrant_service import SearchDocumentChunksRequest
        search_request = SearchDocumentChunksRequest(
            query_vector=query_embedding,
            tenant_id=test_document["tenant_id"],
            user_id=test_document["user_id"],
            limit=5,
            score_threshold=0.0,  # Accept all results for test
            collection_name=clean_qdrant_collection  # Use isolated test collection
        )
        
        results = qdrant_service.search_document_chunks(search_request)
        
        assert results is not None, "Results should not be None"
        assert isinstance(results, list), "Results should be a list"
        assert len(results) > 0, "Should find at least one result"
        assert results[0]["chunk_id"] == chunk["id"], "Should find our uploaded chunk"
    
    # ========================================================================
    # FULL RAG PIPELINE
    # ========================================================================
    
    @pytest.mark.openai
    @pytest.mark.slow
    def test_full_rag_pipeline(
        self,
        db_session,
        embedding_service,
        qdrant_service,
        test_tenant_user,
        clean_qdrant_collection
    ):
        """
        Test complete RAG pipeline: upload → chunk → embed → store → retrieve.
        
        Real OpenAI calls - costs ~$0.001
        """
        # 1. Create document
        doc_id = create_document(
            tenant_id=test_tenant_user["tenant_id"],
            user_id=test_tenant_user["user_id"],
            visibility="private",
            source="upload",
            title="RAG Pipeline Test Document",
            content="This document contains information about pytest integration testing for RAG systems."
        )
        assert doc_id is not None
        
        # 2. Create chunks
        chunk_id = create_document_chunk(
            tenant_id=test_tenant_user["tenant_id"],
            document_id=doc_id,
            chunk_index=0,
            start_offset=0,
            end_offset=100,
            content="This document contains information about pytest integration testing for RAG systems.",
            chapter_name="Introduction"
        )
        assert chunk_id is not None
        
        # 3. Generate embedding
        embedding = embedding_service.generate_embedding(
            "This document contains information about pytest integration testing for RAG systems."
        )
        expected_dims = get_embedding_dimensions()
        assert len(embedding) == expected_dims, f"Expected {expected_dims} dimensions from env"
        
        # 4. Upload to Qdrant
        point_id = qdrant_service.upsert_document_chunk(
            chunk_id=chunk_id,
            embedding=embedding,
            tenant_id=test_tenant_user["tenant_id"],
            user_id=test_tenant_user["user_id"],
            visibility="private",  # Private test document
            metadata={
                "document_id": doc_id,
                "chunk_index": 0
            },
            collection_name=clean_qdrant_collection
        )
        assert point_id is not None
        
        # 5. Update PostgreSQL with Qdrant ID
        update_chunk_embedding(chunk_id, point_id)
        
        # 6. Search (simulate user query)
        query = "pytest RAG testing"
        query_embedding = embedding_service.generate_embedding(query)
        
        from services.qdrant_service import SearchDocumentChunksRequest
        search_request = SearchDocumentChunksRequest(
            query_vector=query_embedding,
            tenant_id=test_tenant_user["tenant_id"],
            user_id=test_tenant_user["user_id"],
            limit=5,
            score_threshold=0.0,
            collection_name=clean_qdrant_collection  # Use isolated test collection
        )
        
        results = qdrant_service.search_document_chunks(search_request)
        
        # 7. Verify retrieval
        assert len(results) > 0, "Should retrieve at least one chunk"
        assert results[0]["chunk_id"] == chunk_id, "Should retrieve our uploaded chunk"
        assert results[0]["score"] > 0.5, "Score should be reasonably high for exact match"
