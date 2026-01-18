"""
Qdrant vector store wrapper.
"""

from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from app.config import get_settings
from app.models import Chunk, SearchResult
from .embeddings import get_embedding_service


class QdrantVectorStore:
    """
    Qdrant vector store for document storage and retrieval.
    """

    # Embedding dimensions for text-embedding-3-large
    EMBEDDING_DIM = 3072

    def __init__(
        self,
        collection_name: Optional[str] = None,
        client: Optional[QdrantClient] = None,
    ):
        settings = get_settings()
        self.collection_name = collection_name or settings.qdrant_collection_kb

        if client:
            self.client = client
        else:
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key,
            )

        self.embedding_service = get_embedding_service()

    def ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            print(f"Created collection: {self.collection_name}")

    def add_chunks(self, chunks: List[Chunk]) -> int:
        """
        Add chunks to the vector store.

        Args:
            chunks: List of Chunk objects to add

        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0

        self.ensure_collection()

        # Generate embeddings for English content
        texts = [chunk.content_en for chunk in chunks]
        embeddings = self.embedding_service.embed_texts(texts)

        # Create points
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point = PointStruct(
                id=hash(chunk.chunk_id) % (2**63),  # Convert to positive int
                vector=embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "content_hu": chunk.content_hu,
                    "content_en": chunk.content_en,
                    "title": chunk.title,
                    "doc_type": chunk.doc_type,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                    "url": chunk.url,
                    "keywords": chunk.keywords,
                },
            )
            points.append(point)

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        return len(points)

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for similar documents.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_dict: Optional filter conditions

        Returns:
            List of SearchResult objects
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)

        # Build filter if provided
        qdrant_filter = None
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                if isinstance(value, list):
                    conditions.append(
                        qdrant_models.FieldCondition(
                            key=key,
                            match=qdrant_models.MatchAny(any=value),
                        )
                    )
                else:
                    conditions.append(
                        qdrant_models.FieldCondition(
                            key=key,
                            match=qdrant_models.MatchValue(value=value),
                        )
                    )
            qdrant_filter = qdrant_models.Filter(must=conditions)

        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=qdrant_filter,
        )

        # Convert to SearchResult
        search_results = []
        for result in results:
            payload = result.payload
            search_results.append(
                SearchResult(
                    chunk_id=payload.get("chunk_id", ""),
                    doc_id=payload.get("doc_id", ""),
                    content_hu=payload.get("content_hu", ""),
                    content_en=payload.get("content_en", ""),
                    title=payload.get("title", ""),
                    doc_type=payload.get("doc_type", ""),
                    score=result.score,
                    url=payload.get("url"),
                    search_type="vector",
                )
            )

        return search_results

    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        Delete all chunks for a document.

        Args:
            doc_id: Document ID to delete

        Returns:
            Number of points deleted
        """
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="doc_id",
                            match=qdrant_models.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
        )
        return result.status == "ok"

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status,
            }
        except Exception as e:
            return {
                "name": self.collection_name,
                "error": str(e),
            }

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all unique documents in the collection with chunk counts."""
        try:
            # Scroll through all points to get unique doc_ids and count chunks
            docs = {}
            offset = None

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for point in results:
                    doc_id = point.payload.get("doc_id")
                    if doc_id:
                        if doc_id not in docs:
                            docs[doc_id] = {
                                "doc_id": doc_id,
                                "title": point.payload.get("title", ""),
                                "doc_type": point.payload.get("doc_type", ""),
                                "url": point.payload.get("url", ""),
                                "chunk_count": 1,
                            }
                        else:
                            docs[doc_id]["chunk_count"] += 1

                if offset is None:
                    break

            return list(docs.values())

        except Exception as e:
            return []


# Singleton instance
_vectorstore = None


def get_vectorstore(collection_name: Optional[str] = None) -> QdrantVectorStore:
    """Get or create the vectorstore singleton."""
    global _vectorstore
    if _vectorstore is None or (collection_name and collection_name != _vectorstore.collection_name):
        _vectorstore = QdrantVectorStore(collection_name=collection_name)
    return _vectorstore
