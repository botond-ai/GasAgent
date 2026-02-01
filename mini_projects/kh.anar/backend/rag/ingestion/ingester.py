"""Betöltő modul: dokumentummodell, betöltési folyamat, inkrementális frissítések.

Ez a modul felelős a Document -> Chunk átalakításért, az embeddingek számításáért
(vagy átvételéért), és a darabok továbbításáért a sűrű és ritka indexekbe.
SRP-t követ: a betöltés csak az átalakítást és indexhívásokat kezeli, nem a
visszakeresést vagy szintézist.
"""
from dataclasses import dataclass
from typing import Dict, Any, List
from ..chunking.chunker import DeterministicChunker


@dataclass
class Document:
    doc_id: str
    title: str
    source: str
    doc_type: str
    version: str
    access_scope: str = "public"
    text: str = ""


class Ingester:
    def __init__(self, dense_retriever, sparse_retriever, embedder, config):
        self.chunker = DeterministicChunker(config.chunk_size, config.chunk_overlap)
        self.dense = dense_retriever
        self.sparse = sparse_retriever
        self.embedder = embedder
        self.config = config

    def ingest(self, doc: Document):
        chunks = self.chunker.chunk(doc.doc_id, doc.text)
        prepared = []
        for c in chunks:
            embedding = self.embedder.embed_text(c.text) if self.embedder else None
            prepared.append({
                "id": c.chunk_id,
                "text": c.text,
                "metadata": {"doc_id": c.doc_id, "title": doc.title, "source": doc.source, "doc_type": doc.doc_type, "version": doc.version, **c.metadata},
                "embedding": embedding,
            })
        # írás mindkét indexbe
        self.dense.add_chunks(prepared)
        self.sparse.add_chunks(prepared)
        return prepared
