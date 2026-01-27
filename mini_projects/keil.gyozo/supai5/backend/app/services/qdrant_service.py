"""
Qdrant vector database service.
"""
import uuid
from typing import Optional
from qdrant_client import AsyncQdrantClient  # Changed to Async
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class QdrantService:
    """Service for managing Qdrant vector database operations."""

    def __init__(self):
        """Initialize Qdrant client."""
        self.client = AsyncQdrantClient(  # Changed to AsyncQdrantClient
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=30
        )
        self.collection_name = settings.qdrant_collection_name
        logger.info(f"Initialized QdrantService for collection: {self.collection_name}")

    async def ensure_collection(self, vector_size: int = 3072) -> None:  # Added async
        """
        Create collection if it doesn't exist.

        Args:
            vector_size: Dimension of embedding vectors (3072 for text-embedding-3-large)
        """
        collections = await self.client.get_collections()  # Added await
        exists = any(col.name == self.collection_name for col in collections.collections)

        if not exists:
            await self.client.create_collection(  # Added await
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created collection: {self.collection_name}")
        else:
            logger.info(f"Collection already exists: {self.collection_name}")

    def generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        """
        Generate deterministic UUID for document chunk.

        Args:
            doc_id: Document identifier
            chunk_index: Index of chunk within document

        Returns:
            UUID string
        """
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}:{chunk_index}"))

    async def upsert_documents(  # Added async
        self,
        doc_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: dict
    ) -> None:
        """
        Upsert document chunks with embeddings.

        Args:
            doc_id: Document identifier
            chunks: List of text chunks
            embeddings: List of embedding vectors
            metadata: Document metadata
        """
        points = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = self.generate_chunk_id(doc_id, idx)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "doc_id": doc_id,
                        "chunk_index": idx,
                        "text": chunk,
                        **metadata
                    }
                )
            )

        await self.client.upsert(  # Added await
            collection_name=self.collection_name,
            points=points
        )
        logger.info(f"Upserted {len(points)} chunks for document: {doc_id}")

    async def search(  # Added async
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_category: Optional[str] = None
    ) -> list[dict]:
        """
        Search for similar documents.

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_category: Optional category filter

        Returns:
            List of search results with scores
        """
        query_filter = None
        if filter_category:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=filter_category)
                    )
                ]
            )

        # JAVÍTVA: search() helyett query_points() használata AsyncQdrantClient esetén
        effective_threshold = score_threshold or settings.score_threshold
        logger.info(f"Qdrant search: limit={limit}, score_threshold={effective_threshold}, filter={filter_category}")

        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,  # 'query' paraméter a 'query_vector' helyett
            limit=limit,
            score_threshold=effective_threshold,
            query_filter=query_filter
        )

        logger.info(f"Qdrant returned {len(results.points)} results")
        if results.points:
            logger.info(f"Top scores: {[r.score for r in results.points[:3]]}")

        # JAVÍTVA: results.points iterálása (az új API results objektumot ad vissza)
        return [
            {
                "id": result.id,
                "score": result.score,
                "text": result.payload.get("text", ""),
                "doc_id": result.payload.get("doc_id", ""),
                "category": result.payload.get("category", ""),
                "metadata": result.payload
            }
            for result in results.points  # results.points az új API-ban
        ]

    async def delete_collection(self) -> None:  # Added async
        """Delete the collection."""
        await self.client.delete_collection(collection_name=self.collection_name)  # Added await
        logger.info(f"Deleted collection: {self.collection_name}")

    async def get_collection_info(self) -> dict:  # Added async
        """Get collection information."""
        info = await self.client.get_collection(collection_name=self.collection_name)  # Added await
        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "status": info.status
        }
