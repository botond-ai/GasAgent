from fastapi import APIRouter, HTTPException, Header, Depends, status
from typing import Optional
from pydantic import BaseModel
import os
import json

from rag.ingestion.ingester import Ingester, Document
from rag.embeddings.embedder import HashEmbedder
from rag.retrieval.sparse import SparseRetriever
from rag.retrieval.dense import DenseRetriever
from rag.retrieval.hybrid import HybridRetriever
from rag.config import default_config
from rag.service import RAGService

router = APIRouter()

# Egyszerű adminvédelem: env változóban lévő ADMIN_TOKEN vagy 401-es hiba.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme")


def _check_admin(token: Optional[str] = Header(None)):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
    return True


class AddDocRequest(BaseModel):
    doc_id: str
    title: str
    source: str
    doc_type: str
    version: str
    access_scope: Optional[str] = "public"
    text: str


# Tartós dokumentum-nyilvántartás (egyszerű JSON tároló)
from rag.persistence.store import DocumentStore

DOC_STORE = DocumentStore(base_dir=dict(os.environ).get("DATA_DIR", "."))
# biztosítjuk, hogy a könyvtár teszt és lokális futás alatt is elérhető legyen
import logging
logger = logging.getLogger("rag.persistence")
logger.info(f"DocumentStore initialized at {DOC_STORE.base}")


@router.post("/add", dependencies=[Depends(_check_admin)])
async def add_document(req: AddDocRequest):
    """Dokumentum hozzáadása vagy frissítése a tartós tárolóban és indexelése.

    A tárolóba írás újraindítások között is megőrzi a dokumentumot, és lehetővé
    teszi a későbbi aszinkron újraindexelő feladatoknak, hogy a hiteles forrást használják.
    """
    # dokumentum tartósítása
    DOC_STORE.save_doc(req.dict())

    # keresők és beágyazó előkészítése; élesben ezek singletonok lennének
    embedder = HashEmbedder()
    dense = DenseRetriever(default_config, embedder=embedder)
    sparse = SparseRetriever()
    ingester = Ingester(dense, sparse, embedder, default_config)

    doc = Document(doc_id=req.doc_id, title=req.title, source=req.source, doc_type=req.doc_type, version=req.version, access_scope=req.access_scope, text=req.text)
    prepared = ingester.ingest(doc)

    return {"success": True, "indexed_chunks": len(prepared)}


@router.post("/reindex", dependencies=[Depends(_check_admin)])
async def reindex_all():
    """Az összes dokumentum újraindexelése a tartós tárolóból.

    Kis adathalmaznál ez a szinkron megoldás is használható.
    Nagyobb készleteknél a háttérben futó és állapotot mutató `/reindex_async` javasolt.
    """
    embedder = HashEmbedder()
    dense = DenseRetriever(default_config, embedder=embedder)
    sparse = SparseRetriever()
    ingester = Ingester(dense, sparse, embedder, default_config)

    total = 0
    for info in DOC_STORE.list_docs():
        d = Document(doc_id=info["doc_id"], title=info["title"], source=info["source"], doc_type=info["doc_type"], version=info["version"], access_scope=info.get("access_scope", "public"), text=info["text"])
        prepared = ingester.ingest(d)
        total += len(prepared)

    return {"success": True, "reindexed_chunks": total}


@router.delete("/doc/{doc_id}", dependencies=[Depends(_check_admin)])
async def delete_document(doc_id: str):
    """Töröl egy dokumentumot a tartós tárolóból és visszaadja, hogy sikerült-e."""
    ok = DOC_STORE.delete_doc(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    # Opcionálisan újraindexelést is indíthatnánk a darabok eltávolítására; itt
    # az egyszerűség kedvéért szinkron marad.
    return {"success": True, "deleted": doc_id}


@router.get("/doc/{doc_id}/versions", dependencies=[Depends(_check_admin)])
async def list_doc_versions(doc_id: str):
    versions = DOC_STORE.list_versions(doc_id)
    # fájlnevek és metaadatok (pl. verzió mezők) listáját adja vissza
    ver_files = []
    verdir = DOC_STORE.base / "versions" / doc_id
    for f in sorted(verdir.glob("*.json")):
        ver_files.append({"name": f.name, "content": json.loads(f.read_text(encoding="utf-8"))})
    return {"success": True, "versions": ver_files}


@router.post("/doc/{doc_id}/revert", dependencies=[Depends(_check_admin)])
async def revert_doc(doc_id: str, version_name: str):
    ok = DOC_STORE.revert_to_version(doc_id, version_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"success": True, "reverted_to": version_name}


@router.post("/snapshot", dependencies=[Depends(_check_admin)])
async def create_snapshot():
    """Készít egy pillanatképet (tar.gz) a tartós dokumentumtárolóról és visszaadja az elérési utat."""
    import tarfile
    import time

    snap_dir = DOC_STORE.base
    name = f"snapshot_{int(time.time())}.tar.gz"
    outp = DOC_STORE.base.parent / name
    with tarfile.open(outp, "w:gz") as tf:
        tf.add(snap_dir, arcname=snap_dir.name)
    return {"success": True, "snapshot": str(outp)}


@router.post("/reindex_async", dependencies=[Depends(_check_admin)])
async def reindex_async():
    """Elindít egy aszinkron újraindexelési feladatot és visszaad egy job_id-t az állapotlekérdezéshez."""
    # a DOC_STORE-t bezáró feladatfuttató definíciója
    def _runner():
        embedder = HashEmbedder()
        dense = DenseRetriever(default_config, embedder=embedder)
        sparse = SparseRetriever()
        ingester = Ingester(dense, sparse, embedder, default_config)

        total = 0
        for info in DOC_STORE.list_docs():
            d = Document(doc_id=info["doc_id"], title=info["title"], source=info["source"], doc_type=info["doc_type"], version=info["version"], access_scope=info.get("access_scope", "public"), text=info["text"])
            prepared = ingester.ingest(d)
            total += len(prepared)
        return {"reindexed_chunks": total}

    from rag.jobs import manager

    job_id = manager.start_reindex(_runner)
    return {"success": True, "job_id": job_id}


@router.get("/reindex_status/{job_id}", dependencies=[Depends(_check_admin)])
async def reindex_status(job_id: str):
    from rag.jobs import manager

    info = manager.get_status(job_id)
    return {"job_id": job_id, "info": info}


@router.post("/kb/ingest_incremental", dependencies=[Depends(_check_admin)])
async def kb_ingest_incremental():
    """Inkrementális tudástár-betöltés indítása mappából.
    
    Csak az új/módosult/törölt dokumentumokat dolgozza fel a kb-data mappából.
    """
    from rag.ingestion.kb_indexer import KBIndexer
    from rag.ingestion.version_store import VersionStore
    from pathlib import Path
    from app.services.rag_instance import dense_retriever, sparse_retriever, embedder
    
    version_store = VersionStore(Path(default_config.kb_version_store))
    
    indexer = KBIndexer(
        config=default_config,
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        embedder=embedder,
        version_store=version_store,
    )
    
    stats = indexer.ingest_incremental()
    return {"success": True, "stats": stats}


@router.post("/kb/reindex_full", dependencies=[Depends(_check_admin)])
async def kb_reindex_full():
    """Teljes tudástár-újraindexelés indítása mappából.
    
    Törli a verziókövetést és minden dokumentumot újraindexel.
    Akkor használd, ha a darabolási konfiguráció vagy a beágyazó modell változott.
    """
    from rag.ingestion.kb_indexer import KBIndexer
    from rag.ingestion.version_store import VersionStore
    from pathlib import Path
    from app.services.rag_instance import dense_retriever, sparse_retriever, embedder
    
    version_store = VersionStore(Path(default_config.kb_version_store))
    
    indexer = KBIndexer(
        config=default_config,
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        embedder=embedder,
        version_store=version_store,
    )
    
    stats = indexer.ingest_full_reindex()
    return {"success": True, "stats": stats}
