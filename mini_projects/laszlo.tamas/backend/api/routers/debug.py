"""
Debug Endpoints

System reset utilities for development/testing.
"""

from fastapi import APIRouter, HTTPException, status
from api.helpers import handle_api_error
from database.pg_connection import get_connection_params
from services.qdrant_service import QdrantService
from services.config_service import get_config_service
from services.cache_service import simple_cache, get_context_cache
import logging
import psycopg2

logger = logging.getLogger(__name__)

router = APIRouter()

config = get_config_service()


@router.post("/reset/postgres")
@handle_api_error("reset postgres")
async def reset_postgres():
    """
    Reset PostgreSQL database - delete all documents and chunks.
    
    ⚠️ WARNING: Destructive operation!
    - Deletes all document_chunks
    - Deletes all documents
    - Resets ID sequences
    
    Use case: Clean slate for testing
    """
    conn = None
    cur = None
    try:
        params = get_connection_params()
        conn = psycopg2.connect(**params)
        cur = conn.cursor()
        
        # Delete in correct order (foreign key constraints)
        cur.execute("DELETE FROM document_chunks;")
        chunks_deleted = cur.rowcount
        
        cur.execute("DELETE FROM documents;")
        docs_deleted = cur.rowcount
        
        # Reset sequences
        cur.execute("ALTER SEQUENCE documents_id_seq RESTART WITH 1;")
        cur.execute("ALTER SEQUENCE document_chunks_id_seq RESTART WITH 1;")
        
        conn.commit()
        
        logger.info(f"PostgreSQL reset: {docs_deleted} docs, {chunks_deleted} chunks deleted")
        
        return {
            "status": "success",
            "documents_deleted": docs_deleted,
            "chunks_deleted": chunks_deleted
        }
        
    except Exception as e:
        logger.error(f"PostgreSQL reset failed: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset PostgreSQL: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@router.post("/reset/qdrant")
@handle_api_error("reset qdrant")
async def reset_qdrant():
    """
    Reset Qdrant - delete all points from document_chunks collection.
    
    ⚠️ WARNING: Destructive operation!
    - Deletes all vectors for tenants 1-20
    
    Use case: Clean slate for testing
    """
    qdrant = QdrantService()
    collection_name = "r_d_ai_chat_document_chunks"
    
    # Skip count check, just try to delete all points directly
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        
        # Try to delete all points using a broad tenant_id filter
        # This will delete points for tenants 1-20
        deleted_info = qdrant.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchAny(any=list(range(1, 21)))
                    )
                ]
            )
        )
        
        logger.info(f"Qdrant reset: delete operation executed")
        
        return {
            "status": "success",
            "message": "Delete operation completed",
            "collection": collection_name,
            "operation": str(deleted_info)
        }
        
    except Exception as delete_error:
        logger.error(f"Could not delete points: {delete_error}")
        return {
            "status": "error",
            "message": str(delete_error),
            "collection": collection_name
        }


@router.post("/reset/cache")
@handle_api_error("reset cache")
async def reset_cache():
    """
    Clear all cache layers.
    
    ⚠️ WARNING: Affects all tenants/users!
    - Memory cache: All entries cleared
    - Context cache: Cleared
    
    Use case: Cache invalidation during testing
    """
    # Clear both cache layers
    simple_cache.clear()
    get_context_cache().clear()
    
    logger.info("Cache reset: both cache layers cleared")
    
    return {
        "status": "success",
        "message": "All caches cleared"
    }
