"""ChromaDB vector store implementation with BM25 keyword search."""

import os
from typing import List, Dict
import chromadb
from rank_bm25 import BM25Okapi

from domain.models import Chunk, RetrievedChunk
from domain.interfaces import VectorStore


class ChromaVectorStore(VectorStore):
    """Vector store using ChromaDB persistent storage with BM25 hybrid search."""

    def __init__(self, persist_directory: str = "data/chroma_db"):
        os.makedirs(persist_directory, exist_ok=True)
        # Use the new Chroma client API
        self.client = chromadb.PersistentClient(path=persist_directory)
        # Cache for BM25 indexes per collection
        self._bm25_indexes: Dict[str, BM25Okapi] = {}
        self._collection_docs: Dict[str, List[str]] = {}


    async def create_collection(self, collection_name: str) -> None:
        """Create or get a collection."""
        self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    async def add_chunks(
        self, collection_name: str, chunks: List[Chunk],
        embeddings: List[List[float]] = None
    ) -> None:
        """Add chunks to a collection with optional embeddings."""
        await self.create_collection(collection_name)
        collection = self.client.get_collection(collection_name)

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [
            {
                "upload_id": chunk.upload_id,
                "category": chunk.category,
                "source_file": chunk.source_file,
                "chunk_index": str(chunk.chunk_index),
                "start_char": str(chunk.start_char),
                "end_char": str(chunk.end_char),
                "section_title": chunk.section_title or "",
                # Merge other metadata but exclude 'embedding' key
                **{k: v for k, v in chunk.metadata.items() if k != "embedding"},
            }
            for chunk in chunks
        ]

        # Use embeddings if provided, otherwise ChromaDB will compute them
        if embeddings:
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        else:
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

    async def query(
        self, collection_name: str, query_embedding: List[float],
        top_k: int = 5, similarity_threshold: float = 0.6
    ) -> List[RetrievedChunk]:
        """Query top-k similar chunks with similarity threshold."""
        collection = self.client.get_collection(collection_name)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        retrieved = []
        if results["ids"] and len(results["ids"]) > 0:
            for i, chunk_id in enumerate(results["ids"][0]):
                doc = results["documents"][0][i]
                distance = results["distances"][0][i]
                metadata = results["metadatas"][0][i]

                # Filter by similarity threshold
                # ChromaDB uses distance metric (lower = more similar)
                # 0.6 distance threshold filters out less relevant chunks
                if distance > similarity_threshold:
                    continue

                # Create snippet from first 200 chars
                snippet = doc[:200] + "..." if len(doc) > 200 else doc

                retrieved.append(
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        content=doc,
                        distance=distance,
                        metadata=metadata,
                        snippet=snippet,
                    )
                )

        return retrieved

    async def keyword_search(
        self, collection_name: str, query_text: str, top_k: int = 5
    ) -> List[RetrievedChunk]:
        """Keyword-based search using BM25 algorithm. ✅ SUGGESTION #5: HYBRID SEARCH"""
        collection = self.client.get_collection(collection_name)
        
        # Get all documents if index doesn't exist yet
        if collection_name not in self._bm25_indexes:
            # Retrieve all documents from collection
            results = collection.get()
            
            if not results["ids"]:
                return []
            
            # Build BM25 index from documents
            documents = results["documents"]
            tokenized_docs = [doc.lower().split() for doc in documents]
            self._bm25_indexes[collection_name] = BM25Okapi(tokenized_docs)
            self._collection_docs[collection_name] = documents
            # Also store metadata for retrieval
            self._collection_metadata = {
                cid: results["metadatas"][i] 
                for i, cid in enumerate(results["ids"])
            }
            self._collection_ids = results["ids"]
        
        # Get BM25 scores for query
        tokenized_query = query_text.lower().split()
        bm25 = self._bm25_indexes[collection_name]
        scores = bm25.get_scores(tokenized_query)
        
        # Get top-k results by BM25 score
        top_indices = sorted(
            range(len(scores)), 
            key=lambda i: scores[i], 
            reverse=True
        )[:top_k]
        
        retrieved = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include positive scores
                doc = self._collection_docs[collection_name][idx]
                chunk_id = self._collection_ids[idx]
                metadata = self._collection_metadata[chunk_id]
                
                snippet = doc[:200] + "..." if len(doc) > 200 else doc
                
                # Normalize BM25 score to 0-1 range (approximate)
                normalized_distance = 1.0 - min(scores[idx] / 10.0, 1.0)
                
                retrieved.append(
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        content=doc,
                        distance=normalized_distance,
                        metadata=metadata,
                        snippet=snippet,
                    )
                )
        
        return retrieved

    async def delete_chunks(
        self, collection_name: str, chunk_ids: List[str]
    ) -> None:
        """Delete chunks by IDs."""
        collection = self.client.get_collection(collection_name)
        collection.delete(ids=chunk_ids)
        # Invalidate BM25 index for this collection
        if collection_name in self._bm25_indexes:
            del self._bm25_indexes[collection_name]
            del self._collection_docs[collection_name]

    async def delete_collection(self, collection_name: str) -> None:
        """Delete an entire collection."""
        try:
            self.client.delete_collection(name=collection_name)
        except Exception as e:
            # Collection might not exist, which is fine
            print(f"Note: Collection '{collection_name}' deletion: {e}")

