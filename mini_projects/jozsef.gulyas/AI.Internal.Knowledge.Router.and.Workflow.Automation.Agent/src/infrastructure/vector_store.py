from dataclasses import dataclass
from typing import Dict, Optional, List
import uuid
import chromadb
from chromadb.config import Settings
from enum import Enum


class Domain(str, Enum):
    HR = "hr"
    IT = "it"
    FINANCE = "finance"
    LEGAL = "legal"
    MARKETING = "marketing"
    GENERAL = "general"


@dataclass
class SearchResult:
    text: str
    doc_id: str
    title: str
    score: float
    source: str
    domain: Domain


class VectorStore:
    def __init__(self, openai_gateway, persist_path: Optional[str] = None):
        self.openai_gateway = openai_gateway
        settings = Settings(anonymized_telemetry=True)

        if persist_path:
            self.client = chromadb.PersistentClient(
                path=persist_path,
                settings=settings)
        else:
            self.client = chromadb.Client(settings=settings)

        self.collections = {
            domain: self.client.get_or_create_collection(
                name=f"{domain.value}_kb",
                metadata={"hnsw:space": "cosine"}
            )
            for domain in Domain
        }

    async def add_document_chunk(self, text: str, domain: Domain, metadata: Dict) -> str:
        """Add a single document chunk to a domain's collection."""
        doc_id = metadata.get("doc_id", str(uuid.uuid4()))
        embedding = await self.openai_gateway.get_embedding(text)

        self.collections[domain].add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "doc_id": doc_id,
                "title": metadata.get("title", ""),
                "source": metadata.get("source", ""),
                "hash": metadata.get("hash", ""),
            }]
        )
        return doc_id

    def find_by_title(self, title: str, domain: Domain) -> Optional[Dict]:
        """
        Find a document by title in a domain's collection.
        Returns the first matching document's metadata or None if not found.
        """
        results = self.collections[domain].get(
            where={"title": title},
            include=["metadatas"]
        )

        if results["ids"] and len(results["ids"]) > 0:
            return {
                "ids": results["ids"],
                "metadata": results["metadatas"][0] if results["metadatas"] else {}
            }
        return None

    def delete_by_title(self, title: str, domain: Domain) -> int:
        """
        Delete all chunks belonging to a document by title.
        Returns the number of chunks deleted.
        """
        results = self.collections[domain].get(
            where={"title": title},
            include=["metadatas"]
        )

        if results["ids"] and len(results["ids"]) > 0:
            self.collections[domain].delete(ids=results["ids"])
            return len(results["ids"])
        return 0

    async def search(self, query: str, domain: Domain, top_k: int = 5) -> List[SearchResult]:
        """Search within a specific domain's collection."""
        embedding = await self.openai_gateway.get_embedding(query)

        results = self.collections[domain].query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        return [
            SearchResult(
                text=results["documents"][0][i],
                doc_id=results["metadatas"][0][i]["doc_id"],
                title=results["metadatas"][0][i]["title"],
                score=1 - results["distances"][0][i],  # cosine distance -> similarity
                source=results["metadatas"][0][i]["source"],
                domain=domain
            )
            for i in range(len(results["ids"][0]))
        ]

    async def search_all(self, query: str, top_k: int = 3) -> Dict[Domain, List[SearchResult]]:
        """Search across ALL domains (useful for comparison/debugging)."""
        results = {}
        for domain in Domain:
            results[domain] = await self.search(query, domain, top_k)
        return results
