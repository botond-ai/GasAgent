"""Document chunks repository for PostgreSQL operations."""

import logging
from typing import List, Optional, Dict
from database.pg_connection import get_db_connection
from services.protocols import DocumentChunkDict

logger = logging.getLogger(__name__)


class DocumentChunkRepository:
    """Repository for document_chunks table operations."""
    
    def insert_chunks(
        self,
        tenant_id: int,
        document_id: int,
        chunks: List[dict]
    ) -> List[int]:
        """
        Insert multiple document chunks into the database.
        
        Args:
            tenant_id: Tenant identifier
            document_id: Document identifier (FK to documents.id)
            chunks: List of chunk dictionaries with keys:
                - chunk_index: Sequential index (0-based)
                - start_offset: Start position in original text
                - end_offset: End position in original text
                - content: Chunk text content
                - source_title: Optional document title
                - chapter_name: Optional chapter/section name (NEW)
                - page_start: Optional starting page number (NEW)
                - page_end: Optional ending page number (NEW)
                - section_level: Optional hierarchy level (NEW)
        
        Returns:
            List of inserted chunk IDs
        
        Raises:
            Exception: If database insert fails
        """
        chunk_ids = []
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            for chunk in chunks:
                cursor.execute(
                    """
                    INSERT INTO document_chunks (
                        tenant_id,
                        document_id,
                        chunk_index,
                        start_offset,
                        end_offset,
                        content,
                        source_title,
                        chapter_name,
                        page_start,
                        page_end,
                        section_level
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        tenant_id,
                        document_id,
                        chunk["chunk_index"],
                        chunk["start_offset"],
                        chunk["end_offset"],
                        chunk["content"],
                        chunk.get("source_title"),
                        chunk.get("chapter_name"),
                        chunk.get("page_start"),
                        chunk.get("page_end"),
                        chunk.get("section_level")
                    )
                )
                
                chunk_id = cursor.fetchone()["id"]
                chunk_ids.append(chunk_id)
            
            conn.commit()
        
        logger.info(f"Inserted {len(chunk_ids)} chunks for document_id={document_id}")
        return chunk_ids
    
    def get_chunks_by_document(self, document_id: int) -> List[DocumentChunkDict]:
        """
        Retrieve all chunks for a specific document.
        
        Args:
            document_id: Document identifier
        
        Returns:
            List of chunk dictionaries
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT 
                    id,
                    tenant_id,
                    document_id,
                    chunk_index,
                    start_offset,
                    end_offset,
                    content,
                    source_title,
                    chapter_name,
                    page_start,
                    page_end,
                    section_level,
                    qdrant_point_id,
                    embedded_at,
                    created_at
                FROM document_chunks
                WHERE document_id = %s
                ORDER BY chunk_index
                """,
                (document_id,)
            )
            
            rows = cursor.fetchall()
            
            chunks = []
            for row in rows:
                chunks.append({
                    "id": row["id"],
                    "tenant_id": row["tenant_id"],
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "start_offset": row["start_offset"],
                    "end_offset": row["end_offset"],
                    "content": row["content"],
                    "source_title": row["source_title"],
                    "chapter_name": row.get("chapter_name"),
                    "page_start": row.get("page_start"),
                    "page_end": row.get("page_end"),
                    "section_level": row.get("section_level"),
                    "qdrant_point_id": row["qdrant_point_id"],
                    "embedded_at": row["embedded_at"],
                    "created_at": row["created_at"]
                })
            
            return chunks
    
    def get_chunk_by_id(self, chunk_id: int) -> Optional[DocumentChunkDict]:
        """
        Retrieve a single chunk by its ID.
        
        Args:
            chunk_id: Chunk identifier
        
        Returns:
            Chunk dictionary or None if not found
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT 
                    id,
                    tenant_id,
                    document_id,
                    chunk_index,
                    start_offset,
                    end_offset,
                    content,
                    source_title,
                    qdrant_point_id,
                    embedded_at,
                    created_at
                FROM document_chunks
                WHERE id = %s
                """,
                (chunk_id,)
            )
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                "id": row["id"],
                "tenant_id": row["tenant_id"],
                "document_id": row["document_id"],
                "chunk_index": row["chunk_index"],
                "start_offset": row["start_offset"],
                "end_offset": row["end_offset"],
                "content": row["content"],
                "source_title": row["source_title"],
                "qdrant_point_id": row["qdrant_point_id"],
                "embedded_at": row["embedded_at"],
                "created_at": row["created_at"]
            }
    
    def get_chunks_by_ids(self, chunk_ids: List[int]) -> dict[int, dict]:
        """
        Retrieve multiple chunks by their IDs in a single batch query.
        
        Args:
            chunk_ids: List of chunk identifiers
        
        Returns:
            Dictionary mapping chunk_id to chunk data (only found chunks included)
        """
        if not chunk_ids:
            return {}
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Use IN clause for batch retrieval
            placeholders = ','.join(['%s'] * len(chunk_ids))
            cursor.execute(
                f"""
                SELECT 
                    id,
                    tenant_id,
                    document_id,
                    chunk_index,
                    start_offset,
                    end_offset,
                    content,
                    source_title,
                    qdrant_point_id,
                    embedded_at,
                    created_at
                FROM document_chunks
                WHERE id IN ({placeholders})
                """,
                chunk_ids
            )
            
            rows = cursor.fetchall()
            
            # Return as dict for fast lookup by chunk_id
            result = {}
            for row in rows:
                result[row["id"]] = {
                    "id": row["id"],
                    "tenant_id": row["tenant_id"],
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "start_offset": row["start_offset"],
                    "end_offset": row["end_offset"],
                    "content": row["content"],
                    "source_title": row["source_title"],
                    "qdrant_point_id": row["qdrant_point_id"],
                    "embedded_at": row["embedded_at"],
                    "created_at": row["created_at"]
                }
            
            return result
    
    def get_chunks_not_embedded(self, document_id: int = None) -> List[dict]:
        """
        Retrieve chunks that don't have embeddings yet.
        
        Args:
            document_id: Optional document ID filter
        
        Returns:
            List of chunk dictionaries (id, content)
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if document_id:
                cursor.execute(
                    """
                    SELECT id, content, tenant_id, document_id
                    FROM document_chunks
                    WHERE document_id = %s AND qdrant_point_id IS NULL
                    ORDER BY chunk_index
                    """,
                    (document_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, content, tenant_id, document_id
                    FROM document_chunks
                    WHERE qdrant_point_id IS NULL
                    ORDER BY document_id, chunk_index
                    """
                )
            
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "tenant_id": row["tenant_id"],
                    "document_id": row["document_id"]
                }
                for row in rows
            ]
    
    def update_chunk_embedding(
        self,
        chunk_id: int,
        qdrant_point_id: str
    ) -> None:
        """
        Update chunk with Qdrant point ID and embedding timestamp.
        
        Args:
            chunk_id: Chunk ID
            qdrant_point_id: UUID from Qdrant
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                UPDATE document_chunks
                SET qdrant_point_id = %s,
                    embedded_at = now()
                WHERE id = %s
                """,
                (qdrant_point_id, chunk_id)
            )
            
            conn.commit()
        
        logger.info(f"Updated chunk {chunk_id} with Qdrant point {qdrant_point_id}")
    
    def update_chunks_embedding_batch(
        self,
        updates: List[Dict]
    ) -> None:
        """
        Batch update chunks with Qdrant point IDs.
        
        Args:
            updates: List of {"chunk_id": int, "qdrant_point_id": str}
        """
        if not updates:
            return
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            for update in updates:
                cursor.execute(
                    """
                    UPDATE document_chunks
                    SET qdrant_point_id = %s,
                        embedded_at = now()
                    WHERE id = %s
                    """,
                    (update["qdrant_point_id"], update["chunk_id"])
                )
            
            conn.commit()
        
        logger.info(f"Batch updated {len(updates)} chunks with Qdrant point IDs")    
    def search_chunks_fulltext(
        self,
        candidate_chunk_ids: List[int],
        query_text: str,
        tenant_id: int,
        limit: int = 10,
        language: str = 'hungarian'
    ) -> List[Dict]:
        """
        Full-text search on document chunks using PostgreSQL tsvector.
        
        This method performs lexical (keyword-based) search on chunk content
        using PostgreSQL's built-in full-text search capabilities. It's designed
        for the second stage of hybrid search (Qdrant pre-filter + PostgreSQL re-rank).
        
        Args:
            candidate_chunk_ids: Pre-filtered chunk IDs from Qdrant vector search
            query_text: User's search query (plain text, will be converted to tsquery)
            tenant_id: Tenant ID for additional filtering (security)
            limit: Maximum number of results to return
            language: PostgreSQL text search language config ('hungarian', 'english', etc.)
        
        Returns:
            List of dictionaries with keys:
                - chunk_id: Chunk ID
                - content: Full chunk text
                - rank: Relevance score (higher = more relevant)
                - document_id: Source document ID
                - source_title: Document title (if available)
        
        Example:
            >>> repo = DocumentChunkRepository()
            >>> # Stage 1: Qdrant vector search → candidate_ids
            >>> candidate_ids = [1, 5, 12, 34, 67]
            >>> # Stage 2: PostgreSQL full-text re-ranking
            >>> results = repo.search_chunks_fulltext(
            ...     candidate_chunk_ids=candidate_ids,
            ...     query_text="kubernetes cluster deployment",
            ...     tenant_id=1,
            ...     limit=5
            ... )
            >>> print(results[0]['rank'])  # 0.87
        
        Note:
            - Uses ts_rank() for relevance scoring (BM25-like algorithm)
            - Query is processed with plainto_tsquery() for natural language input
            - Stemming: "running" matches "run", "runs", "ran" (language-dependent)
            - Stop words: common words like "the", "is", "and" are ignored
        """
        if not candidate_chunk_ids:
            return []
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Build SQL query with full-text search and ranking
            placeholders = ','.join(['%s'] * len(candidate_chunk_ids))
            
            cursor.execute(
                f"""
                SELECT 
                    id as chunk_id,
                    content,
                    document_id,
                    source_title,
                    ts_rank(
                        to_tsvector(%s, content),
                        plainto_tsquery(%s, %s)
                    ) as rank
                FROM document_chunks
                WHERE 
                    id IN ({placeholders})
                    AND tenant_id = %s
                    AND to_tsvector(%s, content) @@ plainto_tsquery(%s, %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                [
                    language,  # to_tsvector language (SELECT clause)
                    language,  # plainto_tsquery language (SELECT clause)
                    query_text,  # query for ranking
                    *candidate_chunk_ids,  # IN clause values
                    tenant_id,  # tenant filter
                    language,  # to_tsvector language (WHERE clause)
                    language,  # plainto_tsquery language (WHERE clause)
                    query_text,  # query for matching
                    limit
                ]
            )
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    "chunk_id": row["chunk_id"],
                    "content": row["content"],
                    "document_id": row["document_id"],
                    "source_title": row["source_title"],
                    "rank": float(row["rank"])  # Convert to float for JSON serialization
                })
            
            logger.info(
                f"Full-text search: {len(results)}/{len(candidate_chunk_ids)} matches "
                f"(query='{query_text[:30]}...', lang={language})"
            )
            
            return results

    def search_fulltext(
        self,
        query_text: str,
        tenant_id: int,
        limit: int = 10,
        language: str = 'simple'
    ) -> List[Dict]:
        """
        Simple full-text search on all document chunks (no candidate pre-filtering).
        
        Args:
            query_text: User's search query (plain text)
            tenant_id: Tenant ID for filtering
            limit: Maximum number of results
            language: PostgreSQL text search language config
        
        Returns:
            List of dictionaries with chunk_id, content, document_id, source_title, rank
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT 
                    id as chunk_id,
                    content,
                    document_id,
                    source_title,
                    ts_rank(
                        to_tsvector(%s, content),
                        plainto_tsquery(%s, %s)
                    ) as rank
                FROM document_chunks
                WHERE 
                    tenant_id = %s
                    AND to_tsvector(%s, content) @@ plainto_tsquery(%s, %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                [
                    language,  # to_tsvector language (SELECT clause)
                    language,  # plainto_tsquery language (SELECT clause)
                    query_text,  # query for ranking
                    tenant_id,  # tenant filter
                    language,  # to_tsvector language (WHERE clause)
                    language,  # plainto_tsquery language (WHERE clause)
                    query_text,  # query for matching
                    limit
                ]
            )
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    "chunk_id": row["chunk_id"],
                    "content": row["content"],
                    "document_id": row["document_id"],
                    "source_title": row["source_title"],
                    "rank": float(row["rank"]),
                    "score": float(row["rank"])  # Alias for hybrid_search_service compatibility
                })
            
            logger.info(
                f"Simple full-text search: {len(results)} matches "
                f"(query='{query_text[:30]}...', lang={language})"
            )
            
            return results