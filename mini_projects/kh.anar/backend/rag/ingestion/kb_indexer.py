"""Tudástár-indexelő orkesztrátor.

Tervezési indoklás:
- A teljes tudástár-betöltési folyamatot vezérli: scan → parse → chunk → embed → index.
- SRP: minden lépést dedikált modulokra bíz (scanner, parser, chunker, retrieverek).
- DIP: interfészekre/konfigurációra támaszkodik, nem konkrét implementációkra.
- Inkrementális frissítéseket kezel: csak a változott dokumentumokat indexeli újra.

Életciklus:
1. kb-data mappa átvizsgálása dokumentumokért
2. Összevetés a verziótárral az új/módosult/törölt dokumentumok felismeréséhez
3. Módosultaknál: régi darabok törlése, újradarabolás, újrabeágyazás, újraindexelés
4. Törölteknél: darabok eltávolítása az indexekből
5. Verziótár frissítése

Miért ez a megközelítés:
- Determinisztikus: ugyanazok a fájlok => ugyanaz az indexállapot.
- Inkrementális: gyors frissítések; csak a változott fájlokat dolgozza fel.
- Megfigyelhető: minden műveletet naplóz darabszámmal és időzítéssel.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import logging
import time
from datetime import datetime, timezone

from rag.config import RAGConfig
from rag.chunking.chunker import DeterministicChunker
from rag.embeddings.embedder import Embedder
from rag.retrieval.dense import DenseRetriever
from rag.retrieval.sparse import SparseRetriever
from rag.ingestion.scanner import scan_kb_folder
from rag.ingestion.pdf_parser import parse_pdf
from rag.ingestion.version_store import VersionStore

logger = logging.getLogger(__name__)


class KBIndexer:
    """A tudástári dokumentumok betöltését és indexelését szervezi.
    
    Tervezés:
    - Állapot nélküli orkesztrátor; az állapot a version_store-ban és a retrieverekben él.
    - Minden betöltés összehangolja a mappa állapotát az index állapotával.
    - Egyfolyamatú használatnál szálbiztos.
    """
    
    def __init__(
        self,
        config: RAGConfig,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
        embedder: Embedder,
        version_store: VersionStore,
        chunker: Optional[DeterministicChunker] = None,
    ):
        self.config = config
        self.dense = dense_retriever
        self.sparse = sparse_retriever
        self.embedder = embedder
        self.version_store = version_store
        self.chunker = chunker or DeterministicChunker(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
        self.kb_dir = Path(config.kb_data_dir)
    
    def ingest_incremental(self) -> dict:
        """Inkrementális betöltés: csak az új/módosult dokumentumokat dolgozza fel.
        
        Returns:
            Dict statisztikákkal: new, updated, removed, total_chunks
        """
        start_time = time.time()
        logger.info(f"Starting incremental KB ingestion from {self.kb_dir}")
        
        # Mappa átvizsgálása
        discovered = scan_kb_folder(self.kb_dir)
        discovered_ids = {d["doc_id"] for d in discovered}
        
        # Összevetés a verziótárral
        tracked_ids = set(self.version_store.get_all_doc_ids())
        
        new_docs = [d for d in discovered if d["doc_id"] not in tracked_ids]
        updated_docs = [
            d for d in discovered 
            if d["doc_id"] in tracked_ids and self.version_store.has_changed(d["doc_id"], d["version_hash"])
        ]
        removed_ids = tracked_ids - discovered_ids
        
        logger.info(f"KB scan: {len(new_docs)} new, {len(updated_docs)} updated, {len(removed_ids)} removed")
        
        total_chunks = 0
        
        # Új dokumentumok feldolgozása
        for doc_meta in new_docs:
            chunks = self._process_document(doc_meta)
            total_chunks += len(chunks)
            self.version_store.update(
                doc_meta["doc_id"],
                doc_meta["version_hash"],
                doc_meta["file_path"],
                len(chunks),
            )
        
        # Módosult dokumentumok feldolgozása (előbb a régi darabok törlése)
        for doc_meta in updated_docs:
            self._delete_document_chunks(doc_meta["doc_id"])
            chunks = self._process_document(doc_meta)
            total_chunks += len(chunks)
            self.version_store.update(
                doc_meta["doc_id"],
                doc_meta["version_hash"],
                doc_meta["file_path"],
                len(chunks),
            )
        
        # Törölt dokumentumok feldolgozása
        for doc_id in removed_ids:
            self._delete_document_chunks(doc_id)
            self.version_store.remove(doc_id)
        
        elapsed = time.time() - start_time
        logger.info(f"KB ingestion complete: {total_chunks} chunks indexed in {elapsed:.2f}s")
        
        return {
            "new": len(new_docs),
            "updated": len(updated_docs),
            "removed": len(removed_ids),
            "total_chunks": total_chunks,
            "elapsed_s": elapsed,
        }
    
    def ingest_full_reindex(self) -> dict:
        """Teljes újraindexelés: verziótár törlése és minden dokumentum újraindexelése.
        
        Akkor használd, ha:
        - Megváltozott a darabolási konfiguráció
        - Megváltozott a beágyazó modell
        - Indexsérülés gyanítható
        
        Returns:
            Dict statisztikákkal: total_docs, total_chunks, elapsed_s
        """
        start_time = time.time()
        logger.info(f"Starting full KB reindex from {self.kb_dir}")
        
        # Verziótár törlése
        self.version_store.clear()
        
        # Megjegyzés: itt nem töröljük a sűrű/ritka indexeket, mert kézzel hozzáadott
        # dokumentumokat tartalmazhatnak. Teljes tiszta induláshoz a hívónak törölnie kell
        # a chroma_dir-t és újrainicializálnia. Inkrementális működéshez a
        # delete_document_chunks-re támaszkodunk a régi adatok eltávolításához.
        
        # Minden dokumentum átvizsgálása és feldolgozása
        discovered = scan_kb_folder(self.kb_dir)
        total_chunks = 0
        
        for doc_meta in discovered:
            chunks = self._process_document(doc_meta)
            total_chunks += len(chunks)
            self.version_store.update(
                doc_meta["doc_id"],
                doc_meta["version_hash"],
                doc_meta["file_path"],
                len(chunks),
            )
        
        elapsed = time.time() - start_time
        logger.info(f"Full reindex complete: {len(discovered)} docs, {total_chunks} chunks in {elapsed:.2f}s")
        
        return {
            "total_docs": len(discovered),
            "total_chunks": total_chunks,
            "elapsed_s": elapsed,
        }
    
    def _process_document(self, doc_meta: dict) -> List:
        """Egyetlen dokumentum feldolgozása: parse, darabolás, beágyazás, indexelés.
        
        Returns:
            A beindexelt darabok listája
        """
        file_path = Path(doc_meta["file_path"])
        doc_id = doc_meta["doc_id"]
        ext = doc_meta["extension"]
        
        logger.debug(f"Processing document: {doc_id} ({ext})")
        
        # Kiterjesztés alapján történő feldolgozás
        if ext == ".pdf":
            parse_result = parse_pdf(file_path)
            text = parse_result.text
            doc_metadata = {
                "doc_id": doc_id,
                "title": parse_result.metadata.get("title") or file_path.name,
                "source": str(file_path),
                "doc_type": "pdf",
                "version_hash": doc_meta["version_hash"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        elif ext in [".txt", ".md"]:
            text = file_path.read_text(encoding="utf-8")
            doc_metadata = {
                "doc_id": doc_id,
                "title": file_path.name,
                "source": str(file_path),
                "doc_type": ext.lstrip("."),
                "version_hash": doc_meta["version_hash"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            logger.warning(f"Unsupported file type: {ext} for {doc_id}")
            return []
        
        # Darabolás
        chunks = self.chunker.chunk(doc_id, text, doc_metadata)
        
        if not chunks:
            logger.warning(f"No chunks generated for {doc_id}")
            return []
        
        # Beágyazás és indexelés
        chunk_texts = [c.text for c in chunks]
        chunk_ids = [c.chunk_id for c in chunks]
        chunk_metas = [c.metadata for c in chunks]
        
        embeddings = self.embedder.embed_batch(chunk_texts)
        
        # Hozzáadás a sűrű indexhez
        self.dense.add_chunks(chunk_ids, embeddings, chunk_texts, chunk_metas)
        
        # Hozzáadás a ritka indexhez
        for chunk_id, text, meta in zip(chunk_ids, chunk_texts, chunk_metas):
            self.sparse.add_chunk(chunk_id, text, meta)
        
        logger.debug(f"Indexed {len(chunks)} chunks for {doc_id}")
        
        return chunks
    
    def _delete_document_chunks(self, doc_id: str) -> None:
        """Törli az adott dokumentumhoz tartozó összes darabot az indexekből.
        
        Tervezési megjegyzés:
        - doc_id prefix egyezéssel keressük és töröljük a darabokat.
        - Chroma esetén metadata.doc_id alapján szűrünk.
        - Ritka indexnél a chunk_id prefix alapján törlünk.
        """
        logger.debug(f"Deleting chunks for doc_id: {doc_id}")
        
        # Törlés a sűrű indexből (ChromaDB)
        # Megjegyzés: ehhez a sűrű keresőnek támogatnia kell a metaadat-szűrős törlést.
        # Hozzá fogjuk adni a delete_by_doc_id metódust a DenseRetrieverhez.
        try:
            self.dense.delete_by_doc_id(doc_id)
        except AttributeError:
            logger.warning("DenseRetriever does not support delete_by_doc_id; skipping dense deletion")
        
        # Törlés a ritka indexből
        # Megjegyzés: a SparseRetrievernek is szüksége van delete_by_doc_id metódusra.
        try:
            self.sparse.delete_by_doc_id(doc_id)
        except AttributeError:
            logger.warning("SparseRetriever does not support delete_by_doc_id; skipping sparse deletion")
