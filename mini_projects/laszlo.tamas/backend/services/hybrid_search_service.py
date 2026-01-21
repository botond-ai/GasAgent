"""
Hybrid search service combining vector and keyword search with weighted ranking.

SOLID Compliance:
- Single Responsibility: Merge and rank search results from multiple sources
- Open/Closed: Extensible to new search backends
- Dependency Inversion: Depends on abstractions (services), not implementations
"""

import logging
from typing import List, Dict, Any, Optional
from services.qdrant_service import QdrantService, SearchDocumentChunksRequest
from database.document_chunk_repository import DocumentChunkRepository
from database.document_repository import DocumentRepository
from config.config_service import get_config_value

logger = logging.getLogger(__name__)


class HybridSearchService:
    """
    Combines vector search (Qdrant) and keyword search (PostgreSQL) with weighted ranking.
    
    Layer: Service Layer (Business Logic)
    Responsibility: Multi-source search orchestration and result merging
    
    Architecture:
    - Executes both searches in parallel (or sequentially)
    - Normalizes scores to [0, 1] range
    - Applies configurable weights (vector_weight, keyword_weight)
    - Merges and re-ranks results by weighted score
    - Deduplicates by chunk_id
    """
    
    def __init__(
        self,
        qdrant_service: QdrantService,
        chunk_repo: DocumentChunkRepository,
        document_repo: DocumentRepository
    ):
        """
        Initialize with service dependencies and configuration.
        
        Args:
            qdrant_service: Vector search service (Qdrant)
            chunk_repo: Keyword search repository (PostgreSQL)  
            document_repo: Document metadata repository (PostgreSQL)
        """
        self.qdrant_service = qdrant_service
        self.chunk_repo = chunk_repo
        self.document_repo = document_repo
        
        # Load weights from config (system.ini)
        self.vector_weight = float(get_config_value('rag', 'DEFAULT_VECTOR_WEIGHT', 0.7))
        self.keyword_weight = float(get_config_value('rag', 'DEFAULT_KEYWORD_WEIGHT', 0.3))
        
        logger.info(
            f"HybridSearchService initialized: "
            f"vector_weight={self.vector_weight}, keyword_weight={self.keyword_weight}"
        )
    
    def search(
        self,
        query: str,
        query_embedding: List[float],
        tenant_id: int,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Execute hybrid search combining vector and keyword results.
        
        Args:
            query: Query string for keyword search
            query_embedding: Query vector for semantic search
            tenant_id: Tenant ID for access control
            user_id: User ID for access control
            limit: Maximum results to return
            
        Returns:
            List of merged and ranked search results with:
            - chunk_id, document_id, content (full text from PostgreSQL)
            - score: Weighted combined score [0, 1]
            - source: "vector", "keyword", or "hybrid"
            - source_title: Document title
        """
        logger.info(
            f"[HYBRID SEARCH] Starting: tenant={tenant_id}, user={user_id}, limit={limit}"
        )
        
        # 1. Execute vector search (Qdrant)
        try:
            request = SearchDocumentChunksRequest(
                query_vector=query_embedding,
                tenant_id=tenant_id,
                user_id=user_id,
                limit=limit * 2  # Get more candidates for merging
            )
            vector_results = self.qdrant_service.search_document_chunks(request)
            
            # Enrich vector results with document titles
            vector_results = self._enrich_with_document_titles(vector_results)
            
            logger.info(f"[HYBRID SEARCH] Vector search: {len(vector_results)} results")
        except Exception as e:
            logger.error(f"[HYBRID SEARCH] Vector search failed: {e}")
            vector_results = []
        
        # 2. Execute keyword search (PostgreSQL)
        try:
            keyword_results = self.chunk_repo.search_fulltext(
                query_text=query,
                tenant_id=tenant_id,
                limit=limit * 2
            )
            logger.info(f"[HYBRID SEARCH] Keyword search: {len(keyword_results)} results")
        except Exception as e:
            logger.error(f"[HYBRID SEARCH] Keyword search failed: {e}")
            keyword_results = []
        
        # 3. Normalize and weight scores
        vector_scored = self._normalize_and_weight(
            vector_results, self.vector_weight, source="vector"
        )
        keyword_scored = self._normalize_and_weight(
            keyword_results, self.keyword_weight, source="keyword"
        )
        
        # 4. Merge and deduplicate by chunk_id
        merged = self._merge_results(vector_scored, keyword_scored)
        
        # 5. Sort by weighted score descending and limit
        merged.sort(key=lambda x: x["score"], reverse=True)
        final_results = merged[:limit]
        
        # 6. Enrich with full content from PostgreSQL (source of truth)
        final_results = self._enrich_with_full_content(final_results)
        
        logger.info(
            f"[HYBRID SEARCH] Merged: {len(merged)} total, returning top {len(final_results)} with full content"
        )
        
        return final_results
    
    def _normalize_and_weight(
        self,
        results: List[Dict[str, Any]],
        weight: float,
        source: str
    ) -> List[Dict[str, Any]]:
        """
        Normalize scores to [0, 1] and apply weight.
        
        Args:
            results: Search results with "score" field
            weight: Weight multiplier (0.0 - 1.0)
            source: Source identifier ("vector" or "keyword")
            
        Returns:
            Results with normalized and weighted scores
        """
        if not results:
            return []
        
        # Find min/max for normalization
        scores = [r["score"] for r in results]
        min_score = min(scores)
        max_score = max(scores)
        
        # Normalize to [0, 1] and apply weight
        normalized = []
        for result in results:
            if max_score > min_score:
                norm_score = (result["score"] - min_score) / (max_score - min_score)
            else:
                norm_score = 1.0  # All scores are equal
            
            weighted_score = norm_score * weight
            
            normalized.append({
                **result,
                "score": weighted_score,
                "source": source,
                "original_score": result["score"]  # Keep for debugging
            })
        
        return normalized
    
    def _merge_results(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge and deduplicate results by chunk_id, combining scores.
        
        Args:
            vector_results: Weighted vector search results
            keyword_results: Weighted keyword search results
            
        Returns:
            Merged list with combined scores for duplicates
        """
        merged_dict = {}
        
        # Add vector results
        for result in vector_results:
            chunk_id = result["chunk_id"]
            merged_dict[chunk_id] = result
        
        # Add/merge keyword results
        for result in keyword_results:
            chunk_id = result["chunk_id"]
            if chunk_id in merged_dict:
                # Chunk appears in both: combine scores
                merged_dict[chunk_id]["score"] += result["score"]
                merged_dict[chunk_id]["source"] = "hybrid"  # Mark as hybrid
            else:
                merged_dict[chunk_id] = result
        
        return list(merged_dict.values())
    
    def _enrich_with_document_titles(
        self, 
        vector_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich vector search results with document titles by looking up document_id.
        
        Args:
            vector_results: Results from Qdrant (missing source_title)
            
        Returns:
            Enhanced results with source_title field added
        """
        if not vector_results:
            return vector_results
            
        enriched = []
        for result in vector_results:
            document_id = result.get("document_id")
            if document_id:
                try:
                    document = self.document_repo.get_document_by_id(document_id)
                    source_title = document.get("title", "Unknown Document") if document else "Unknown Document"
                except Exception as e:
                    logger.error(f"[HYBRID SEARCH] Failed to fetch document {document_id}: {e}")
                    source_title = "Unknown Document"
            else:
                source_title = "Unknown Document"
            
            enriched_result = {
                **result,
                "source_title": source_title
            }
            enriched.append(enriched_result)
            
        return enriched
    def _enrich_with_full_content(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich results with full content from PostgreSQL (source of truth).
        
        Qdrant only stores content_preview (200 chars) for efficiency.
        PostgreSQL has the full chunk content needed for LLM synthesis.
        
        Args:
            results: Search results with chunk_id (may have content_preview only)
            
        Returns:
            Results with full 'content' field from PostgreSQL
        """
        if not results:
            return results
        
        # Collect chunk_ids that need full content
        chunk_ids = [r["chunk_id"] for r in results if r.get("chunk_id")]
        
        if not chunk_ids:
            return results
        
        # Batch fetch from PostgreSQL
        try:
            chunks_by_id = self.chunk_repo.get_chunks_by_ids(chunk_ids)
            logger.info(f"[HYBRID SEARCH] Enriched {len(chunks_by_id)} chunks with full content")
        except Exception as e:
            logger.error(f"[HYBRID SEARCH] Failed to fetch full content: {e}")
            return results
        
        # Merge full content into results
        enriched = []
        for result in results:
            chunk_id = result.get("chunk_id")
            full_chunk = chunks_by_id.get(chunk_id)
            
            if full_chunk:
                enriched_result = {
                    **result,
                    "content": full_chunk["content"],  # Full content from PG
                    "source_title": full_chunk.get("source_title") or result.get("source_title", "Unknown")
                }
            else:
                # Fallback: keep original (content_preview if available)
                enriched_result = result
                
            enriched.append(enriched_result)
        
        return enriched