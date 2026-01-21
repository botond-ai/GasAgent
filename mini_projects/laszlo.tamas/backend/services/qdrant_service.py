"""Qdrant vector database service with Pydantic validation."""

import logging
import os
import time
import uuid
from typing import List, Dict
from datetime import datetime
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from services.exceptions import QdrantServiceError
from services.resilience import retry_on_transient_error
from observability.ai_metrics import record_rag_search

logger = logging.getLogger(__name__)

# Configuration - NO DEFAULT VALUES, must be set in .env
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT_STR = os.getenv("QDRANT_PORT")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_USE_HTTPS_STR = os.getenv("QDRANT_USE_HTTPS")
QDRANT_COLLECTION_PREFIX = os.getenv("QDRANT_COLLECTION_PREFIX")

if not all([QDRANT_HOST, QDRANT_PORT_STR, QDRANT_USE_HTTPS_STR, QDRANT_COLLECTION_PREFIX]):
    raise ValueError("Qdrant configuration missing! Check .env file for: QDRANT_HOST, QDRANT_PORT, QDRANT_USE_HTTPS, QDRANT_COLLECTION_PREFIX")

QDRANT_PORT = int(QDRANT_PORT_STR)
QDRANT_USE_HTTPS = QDRANT_USE_HTTPS_STR.lower() == "true"

# Collection names
COLLECTION_DOCUMENT_CHUNKS = f"{QDRANT_COLLECTION_PREFIX}_document_chunks"
COLLECTION_LONG_TERM_MEMORIES = f"{QDRANT_COLLECTION_PREFIX}_longterm_chat_memory"
COLLECTION_PRODUCT_KNOWLEDGE = f"{QDRANT_COLLECTION_PREFIX}_product_knowledge"


# ===== REQUEST SCHEMAS =====

class SearchDocumentChunksRequest(BaseModel):
    """Request schema for document chunk search with access control."""
    query_vector: List[float] = Field(
        ...,
        min_length=1,
        description="Query vector for similarity search"
    )
    tenant_id: int = Field(
        ...,
        ge=1,
        description="Tenant ID for filtering (must be positive)"
    )
    user_id: int = Field(
        ...,
        ge=1,
        description="User ID for private document access control"
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)"
    )
    score_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0.0-1.0)"
    )
    collection_name: str | None = Field(
        default=None,
        description="Optional collection override (defaults to COLLECTION_DOCUMENT_CHUNKS)"
    )


class SearchLongTermMemoriesRequest(BaseModel):
    """Request schema for long-term memory search."""
    query_vector: List[float] = Field(
        ...,
        min_length=1,
        description="Query vector for similarity search"
    )
    tenant_id: int = Field(
        ...,
        ge=1,
        description="Tenant ID for filtering"
    )
    user_id: int = Field(
        ...,
        ge=1,
        description="User ID for filtering"
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum memories to return (1-20)"
    )


class UpsertVectorsRequest(BaseModel):
    """Request schema for upserting vectors."""
    vectors: List[List[float]] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of vectors to upsert (1-100 items)"
    )
    payloads: List[Dict] = Field(
        ...,
        min_length=1,
        description="Metadata payloads for each vector"
    )
    collection_name: str = Field(
        default=COLLECTION_DOCUMENT_CHUNKS,
        min_length=1,
        description="Qdrant collection name"
    )


# ===== SERVICE =====

class QdrantService:
    """Service for interacting with Qdrant vector database."""
    
    def __init__(self):
        from .config_service import get_config_service
        
        if not QDRANT_HOST:
            raise ValueError("QDRANT_HOST environment variable is required")
        
        # Load from system.ini
        config = get_config_service()
        self.vector_size = config.get_embedding_dimensions()
        self.default_limit = config.get_top_k_documents()
        self.default_score_threshold = config.get_min_score_threshold()
        self.upload_batch_size = config.get_qdrant_upload_batch_size()
        timeout_seconds = config.get_qdrant_timeout()
        
        # Build URL
        protocol = "https" if QDRANT_USE_HTTPS else "http"
        url = f"{protocol}://{QDRANT_HOST}:{QDRANT_PORT}"
        
        self.client = QdrantClient(
            url=url,
            api_key=QDRANT_API_KEY,
            timeout=timeout_seconds
        )
        
        logger.info(
            f"QdrantService initialized: url={url}, "
            f"prefix={QDRANT_COLLECTION_PREFIX}, "
            f"batch_size={self.upload_batch_size}, "
            f"timeout={timeout_seconds}s"
        )
        
        # Ensure collections exist
        self._ensure_collection(COLLECTION_DOCUMENT_CHUNKS)
        self._ensure_collection(COLLECTION_LONG_TERM_MEMORIES)
    
    def _ensure_collection(self, collection_name: str):
        """
        Ensure a collection exists, create if not.
        
        Args:
            collection_name: Name of the collection
        """
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            
            if not exists:
                # Try to create, but don't fail if API key lacks global access
                try:
                    logger.info(f"Creating collection: {collection_name}")
                    
                    self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=self.vector_size,
                            distance=Distance.COSINE
                        )
                    )
                    
                    logger.info(f"Collection created: {collection_name}")
                except Exception as create_error:
                    logger.warning(
                        f"Cannot create collection {collection_name}: {create_error}. "
                        f"Collection might already exist or API key lacks global access. "
                        f"Continuing..."
                    )
            else:
                logger.info(f"Collection exists: {collection_name}")
        
        except Exception as e:
            logger.error(f"Failed to ensure collection {collection_name}: {e}", exc_info=True)
            raise QdrantServiceError(
                f"Failed to ensure collection {collection_name}",
                context={
                    "collection": collection_name,
                    "operation": "ensure_collection",
                    "error_type": type(e).__name__
                }
            ) from e
    
    def upsert_document_chunks(
        self,
        chunks: List[Dict],
        batch_size: int = 50,
        collection_name: str | None = None
    ) -> List[Dict]:
        """
        Insert or update document chunks in Qdrant with batching.
        
        Args:
            chunks: List of dicts with:
                - chunk_id: int (PostgreSQL chunk ID)
                - embedding: List[float] (3072 dim)
                - tenant_id: int
                - document_id: int                - user_id: int | None (document owner for private docs)
                - visibility: str ('private' | 'tenant')                - content: str (for preview in payload)
            batch_size: Number of chunks to upload per batch (default: 50)
            collection_name: Optional collection override (defaults to COLLECTION_DOCUMENT_CHUNKS)
        
        Returns:
            List of dicts with chunk_id and qdrant_point_id
            [{"chunk_id": int, "qdrant_point_id": str}, ...]
        
        Raises:
            Exception: If upsert fails
        """
        if not chunks:
            return []
        
        # Use provided collection or default
        target_collection = collection_name or COLLECTION_DOCUMENT_CHUNKS
        
        total_chunks = len(chunks)
        logger.info(f"Upserting {total_chunks} chunks to Qdrant collection '{target_collection}' in batches of {batch_size}")
        
        all_results = []
        
        # Process in batches to avoid Qdrant payload size limit (32 MB)
        for batch_start in range(0, total_chunks, batch_size):
            batch_end = min(batch_start + batch_size, total_chunks)
            batch = chunks[batch_start:batch_end]
            
            batch_num = (batch_start // batch_size) + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)")
            
            points = []
            batch_results = []
            
            for chunk in batch:
                # Generate UUID for Qdrant point
                point_id = str(uuid.uuid4())
                
                # Create point
                point = PointStruct(
                    id=point_id,
                    vector=chunk["embedding"],
                    payload={
                        "chunk_id": chunk["chunk_id"],
                        "tenant_id": chunk["tenant_id"],
                        "document_id": chunk["document_id"],
                        "user_id": chunk.get("user_id"),  # Document owner (None for tenant docs)
                        "visibility": chunk.get("visibility", "tenant"),  # 'private' or 'tenant'
                        "content_preview": chunk["content"][:200],  # First 200 chars
                        # TOC metadata (NEW)
                        "chapter_name": chunk.get("chapter_name"),
                        "page_start": chunk.get("page_start"),
                        "page_end": chunk.get("page_end"),
                        "section_level": chunk.get("section_level")
                    }
                )
                
                points.append(point)
                batch_results.append({
                    "chunk_id": chunk["chunk_id"],
                    "qdrant_point_id": point_id
                })
            
            try:
                # Batch upsert
                self.client.upsert(
                    collection_name=target_collection,
                    points=points
                )
                
                logger.info(f"Successfully upserted batch {batch_num}/{total_batches} ({len(points)} points)")
                all_results.extend(batch_results)
                
            except Exception as e:
                logger.error(f"Qdrant upsert failed for batch {batch_num}/{total_batches}: {e}", exc_info=True)
                raise QdrantServiceError(
                    f"Qdrant upsert failed for batch {batch_num}/{total_batches}",
                    context={
                        "collection": target_collection,
                        "batch_num": batch_num,
                        "total_batches": total_batches,
                        "batch_size": len(points),
                        "operation": "upsert_document_chunks",
                        "error_type": type(e).__name__
                    }
                ) from e
        
        logger.info(f"✅ All {total_chunks} chunks successfully uploaded to Qdrant")
        return all_results

    def upsert_memories(
        self,
        memories: List[Dict]
    ) -> List[Dict]:
        """
        Insert or update user long-term memories in Qdrant.
        
        Args:
            memories: List of dicts with:
                - memory_id: int (PostgreSQL long_term_memories.id)
                - embedding: List[float] (3072 dim)
                - tenant_id: int
                - user_id: int
                - content: str (full memory text)
                - memory_type: str ('explicit_fact' | 'session_summary')
                - session_id: str (UUID of source session)
        
        Returns:
            List of dicts with memory_id and qdrant_point_id
            [{"memory_id": int, "qdrant_point_id": str}, ...]
        
        Raises:
            QdrantServiceError: If upsert fails
        """
        if not memories:
            return []
        
        logger.info(f"Upserting {len(memories)} memories to Qdrant")
        
        points = []
        results = []
        
        for memory in memories:
            # Generate UUID for Qdrant point
            point_id = str(uuid.uuid4())
            
            # Create point with memory-specific payload
            point = PointStruct(
                id=point_id,
                vector=memory["embedding"],
                payload={
                    "memory_id": memory["memory_id"],
                    "tenant_id": memory["tenant_id"],
                    "user_id": memory["user_id"],
                    "memory_type": memory.get("memory_type", "explicit_fact"),
                    "session_id": memory.get("session_id"),
                    "content_preview": memory["content"][:200]  # First 200 chars
                }
            )
            
            points.append(point)
            results.append({
                "memory_id": memory["memory_id"],
                "qdrant_point_id": point_id
            })
        
        try:
            # Single batch upsert (memories are typically few per operation)
            self.client.upsert(
                collection_name=COLLECTION_DOCUMENT_CHUNKS,  # Same collection for now
                points=points
            )
            
            logger.info(f"✅ Successfully upserted {len(points)} memories to Qdrant")
            return results
            
        except Exception as e:
            logger.error(f"Qdrant memory upsert failed: {e}", exc_info=True)
            raise QdrantServiceError(
                "Qdrant memory upsert failed",
                context={
                    "collection": COLLECTION_DOCUMENT_CHUNKS,
                    "memory_count": len(points),
                    "operation": "upsert_memories",
                    "error_type": type(e).__name__
                }
            ) from e

    def upsert_document_chunk(
        self,
        chunk_id: int,
        embedding: List[float],
        tenant_id: int,
        metadata: Dict,
        collection_name: str = None,
        user_id: int | None = None,
        visibility: str = "tenant"
    ) -> str:
        """
        Insert or update a single document chunk in Qdrant.
        
        Args:
            chunk_id: PostgreSQL chunk ID
            embedding: Vector embedding (3072 dim)
            tenant_id: Tenant ID for access control
            metadata: Additional metadata (document_id, chunk_index, etc.)
            collection_name: Override default collection name (for testing)
            user_id: Document owner user ID (for private docs)
            visibility: 'private' or 'tenant' (default: 'tenant')
        
        Returns:
            Qdrant point ID (UUID string)
        
        Raises:
            Exception: If upsert fails
        """
        # Use test collection if provided, otherwise default
        collection = collection_name or f"{self.prefix}_document_chunks"
        
        # Generate UUID for Qdrant point
        point_id = str(uuid.uuid4())
        
        # Combine metadata with access control fields
        payload = {
            "chunk_id": chunk_id,
            "tenant_id": tenant_id,
            "user_id": user_id,  # Owner user ID (None for tenant docs)
            "visibility": visibility,  # 'private' or 'tenant'
            **metadata
        }
        
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload
        )
        
        try:
            logger.info(f"Upserting single chunk to Qdrant: chunk_id={chunk_id}")
            operation_info = self.client.upsert(
                collection_name=collection,
                points=[point],
                wait=True
            )
            
            # Status check: UpdateStatus.COMPLETED is success (not string 'ok')
            from qdrant_client.models import UpdateStatus
            if hasattr(operation_info, 'status') and operation_info.status != UpdateStatus.COMPLETED:
                raise Exception(f"Qdrant upsert failed: {operation_info}")
            
            logger.info(f"✅ Chunk {chunk_id} uploaded successfully, point_id={point_id}")
            return point_id
            
        except Exception as e:
            from services.exceptions import QdrantError
            raise QdrantError(
                f"Failed to upsert single chunk {chunk_id}",
                context={
                    "collection": collection,
                    "chunk_id": chunk_id,
                    "tenant_id": tenant_id,
                    "operation": "upsert_document_chunk",
                    "error_type": type(e).__name__
                }
            ) from e
    
    @retry_on_transient_error(max_retries=3, initial_backoff=1.0, backoff_multiplier=2.0)
    def search_document_chunks(
        self,
        request: SearchDocumentChunksRequest
    ) -> List[Dict]:
        """
        Search for similar document chunks with access control (Pydantic-validated).
        
        Returns only chunks the user has permission to see:
        - Private documents owned by the user
        - Tenant-wide documents
        
        Args:
            request: Validated search request
        
        Returns:
            List of search results with chunk_id, document_id, score, content_preview
        """
        # Use defaults from service init if not provided
        limit = request.limit if request.limit != 5 else self.default_limit
        score_threshold = request.score_threshold if request.score_threshold != 0.7 else self.default_score_threshold
        target_collection = request.collection_name or COLLECTION_DOCUMENT_CHUNKS
        
        # Start timing for metrics
        start_time = time.time()
        
        try:
            results = self.client.search(
                collection_name=target_collection,
                query_vector=request.query_vector,
                query_filter={
                    "must": [
                        {
                            "key": "tenant_id",
                            "match": {"value": request.tenant_id}
                        },
                        {
                            "should": [
                                # Private doc owned by user
                                {
                                    "must": [
                                        {"key": "visibility", "match": {"value": "private"}},
                                        {"key": "user_id", "match": {"value": request.user_id}}
                                    ]
                                },
                                # Tenant-wide doc
                                {"key": "visibility", "match": {"value": "tenant"}}
                            ]
                        }
                    ]
                },
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Calculate duration
            duration_seconds = time.time() - start_time
            
            # Extract relevance scores for metrics
            relevance_scores = [hit.score for hit in results]
            
            # Emit RAG metrics to Prometheus
            record_rag_search(
                collection=target_collection,
                duration_seconds=duration_seconds,
                result_count=len(results),
                relevance_scores=relevance_scores
            )
            
            logger.info(
                f"Qdrant search: {len(results)} results "
                f"(tenant={request.tenant_id}, limit={request.limit}, threshold={score_threshold}, "
                f"duration={duration_seconds:.3f}s, avg_score={sum(relevance_scores)/len(relevance_scores) if relevance_scores else 0:.3f})"
            )
            
            return [
                {
                    "chunk_id": hit.payload["chunk_id"],
                    "document_id": hit.payload["document_id"],
                    "score": hit.score,
                    "content_preview": hit.payload.get("content_preview", "")
                }
                for hit in results
            ]
        
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}", exc_info=True)
            raise QdrantServiceError(
                "Qdrant document chunk search failed",
                context={
                    "collection": COLLECTION_DOCUMENT_CHUNKS,
                    "tenant_id": request.tenant_id,
                    "user_id": request.user_id,
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "operation": "search_document_chunks",
                    "error_type": type(e).__name__
                }
            ) from e
    
    # ===== LONG-TERM MEMORY METHODS =====
    
    def upsert_long_term_memory(
        self,
        tenant_id: int,
        user_id: int,
        session_id: str,
        memory_type: str,
        ltm_id: int,
        content_full: str,
        embedding_vector: List[float]
    ) -> str:
        """
        Store long-term memory in Qdrant.
        
        Args:
            tenant_id: Tenant ID (for filtering)
            user_id: User ID (for filtering)
            session_id: Source session ID
            memory_type: "session_summary" or "explicit_fact"
            ltm_id: PostgreSQL long_term_memories.id (for retrieval)
            content_full: Full text (preview extracted here)
            embedding_vector: Embedding of the content
        
        Returns:
            UUID of the created point
        
        Payload structure:
            {
                "tenant_id": int,
                "user_id": int,
                "session_id": str,
                "memory_type": str,
                "ltm_id": int,  # PostgreSQL reference
                "content_preview": str,  # First 200 chars (DEBUG only)
                "created_at": ISO timestamp
            }
        
        Note: content_preview is for debugging/monitoring only.
              LLM workflows must load full content from PostgreSQL via ltm_id.
        """
        from datetime import datetime
        
        point_id = str(uuid.uuid4())
        
        try:
            self.client.upsert(
                collection_name=COLLECTION_LONG_TERM_MEMORIES,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding_vector,
                        payload={
                            "tenant_id": tenant_id,
                            "user_id": user_id,
                            "session_id": session_id,
                            "memory_type": memory_type,
                            "ltm_id": ltm_id,
                            "content_preview": content_full[:200],  # Debug only
                            "created_at": datetime.now().isoformat()
                        }
                    )
                ]
            )
            
            logger.info(
                f"Long-term memory stored: ltm_id={ltm_id}, "
                f"type={memory_type}, point_id={point_id}"
            )
            return point_id
        
        except Exception as e:
            logger.error(f"Failed to store long-term memory: {e}", exc_info=True)
            raise QdrantServiceError(
                "Failed to store long-term memory in Qdrant",
                context={
                    "collection": COLLECTION_LONG_TERM_MEMORIES,
                    "ltm_id": ltm_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "memory_type": memory_type,
                    "operation": "upsert_long_term_memory",
                    "error_type": type(e).__name__
                }
            ) from e
    
    @retry_on_transient_error(max_retries=3, initial_backoff=1.0, backoff_multiplier=2.0)
    def search_long_term_memories(
        self,
        query_vector: List[float],
        user_id: int,
        limit: int = 3,
        score_threshold: float = 0.5
    ) -> List[Dict]:
        """
        Search user's long-term memories (previous session summaries + explicit facts).
        
        Args:
            query_vector: Embedding of current query
            user_id: User ID to filter memories
            limit: Max results (default: 3)
            score_threshold: Min similarity score (default: 0.5)
        
        Returns:
            List of matching memories with ltm_id for PostgreSQL batch load.
            content_preview is included for debugging but should NOT be used in LLM workflow.
        
        Example:
            [
                {
                    "ltm_id": 42,
                    "memory_type": "session_summary",
                    "score": 0.87,
                    "content_preview": "User discussed..."
                }
            ]
        """
        try:
            results = self.client.search(
                collection_name=COLLECTION_LONG_TERM_MEMORIES,
                query_vector=query_vector,
                query_filter={
                    "must": [
                        {"key": "user_id", "match": {"value": user_id}}
                    ]
                },
                limit=limit,
                score_threshold=score_threshold
            )
            
            logger.info(
                f"Long-term memory search: {len(results)} results "
                f"(user={user_id}, limit={limit}, threshold={score_threshold})"
            )
            
            return [
                {
                    "ltm_id": hit.payload["ltm_id"],
                    "memory_type": hit.payload["memory_type"],
                    "score": hit.score,
                    "content_preview": hit.payload["content_preview"]  # Debug info
                }
                for hit in results
            ]
        
        except Exception as e:
            logger.error(f"Long-term memory search failed: {e}", exc_info=True)
            raise QdrantServiceError(
                "Qdrant long-term memory search failed",
                context={
                    "collection": COLLECTION_LONG_TERM_MEMORIES,
                    "user_id": user_id,
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "operation": "search_long_term_memories",
                    "error_type": type(e).__name__
                }
            ) from e
