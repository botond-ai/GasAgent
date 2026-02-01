"""Megosztott RAG példányok az alkalmazáshoz.

Ez a modul singleton-szerű megosztott RAG komponenseket ad, hogy az
alkalmazás minden része ugyanazokat a keresőket használja.

Különösen fontos a BM25 ritka keresőnél, ami memóriában él és nem tartós:
- Ha minden végpont saját SparseRetrievert hoz létre, az adatok elkülönülnek
- A tudástár-betöltésnek UGYANAZOKAT a példányokat kell feltöltenie, mint amit a chat ügynök használ

Tervezés:
- Egyszer inicializáljuk modulbetöltéskor
- Innen importáljuk a routes.py, admin.py, main.py életciklusából
- Biztosítja a következetes állapotot a kérések között
"""
from rag.config import default_config
from rag.embeddings.embedder import HashEmbedder
from rag.retrieval.dense import DenseRetriever
from rag.retrieval.sparse import SparseRetriever
from rag.retrieval.hybrid import HybridRetriever
from rag.service import RAGService

# Megosztott példányok - egyszer inicializálva modulimportkor
embedder = HashEmbedder()
dense_retriever = DenseRetriever(default_config, embedder=embedder)
sparse_retriever = SparseRetriever()
hybrid_retriever = HybridRetriever(dense_retriever, sparse_retriever, default_config)
rag_service = RAGService(embedder, hybrid_retriever, default_config)
