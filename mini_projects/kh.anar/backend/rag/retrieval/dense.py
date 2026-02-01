"""Sűrű kereső ChromaDB-vel.

Ez a modul elrejti a Chroma hívásokat, így az alkalmazás többi része közvetlenül
nem függ tőle. A megvalósítás támogatja az inkrementális frissítéseket
(add/update/delete), és konfigurációtól függően lemezre ment.

Miért: a Chroma robusztus, tartós vektoradatbázist ad; az interfész mögé rejtve
később cserélhető teszteknél és más driverekre.
"""
from typing import List, Dict, Optional
from uuid import uuid4

# We import lazily to avoid making Chroma a hard requirement for unit tests
# that don't touch dense retrieval. In production, Chroma client will be used.
try:
    import chromadb
except Exception:
    chromadb = None


class DenseRetriever:
    def __init__(self, config, embedder=None):
        """embedder: opcionális beágyazó, amivel kiszámítjuk azoknak a daraboknak a beágyazását,
        amelyekhez nincs előre számolt embedding (hasznos betöltésnél).
        """
        self.config = config
        self.embedder = embedder
        self.client = None
        self.collection = None
        if chromadb is not None:
            self._init_chroma()

    def _init_chroma(self):
        """A ChromaDB inicializálása az új v1.4+ API-val.
        
        PersistentClientet használunk a deprecated Client(settings=...) minta helyett.
        Lásd: https://docs.trychroma.com/deployment/migration
        """
        self.client = chromadb.PersistentClient(path=self.config.chroma_dir)
        self.collection = self.client.get_or_create_collection(name=self.config.chroma_collection)

    def add_chunks(self, chunks_or_ids, embeddings=None, texts=None, metadatas=None):
        """Darabok hozzáadása a Chromához.
        
        Két aláírás:
        1. add_chunks(chunks: List[Dict]) - minden darab: {id, text, embedding, metadata}
        2. add_chunks(ids, embeddings, texts, metadatas) - pozíciós tömbök
        
        Elfogadjuk az előre számolt embeddingeket a teszt determinisztikussághoz; élesben
        a hívó is számolhat itt embeddinget.
        """
        if self.collection is None:
            raise RuntimeError("Chroma not available")
        
        # Aláírás felismerése
        if embeddings is None and texts is None and metadatas is None:
            # Dict-alapú aláírás
            chunks = chunks_or_ids
            ids = [c["id"] for c in chunks]
            metadatas = [c.get("metadata", {}) for c in chunks]
            documents = [c.get("text", "") for c in chunks]
            embeddings = [c.get("embedding") for c in chunks]
        else:
            # Pozíciós aláírás
            ids = chunks_or_ids
            documents = texts
            metadatas = metadatas or [{} for _ in ids]
        
        # embedding számítása, ha nincs, és van beágyazó
        if any(e is None for e in embeddings):
            if not self.embedder:
                raise RuntimeError("Embeddings missing and no embedder provided")
            embeddings = [e if e is not None else self.embedder.embed_text(doc) for e, doc in zip(embeddings, documents)]
        self.collection.upsert(ids=ids, metadatas=metadatas, documents=documents, embeddings=embeddings)

    def delete_chunks(self, ids: List[str]):
        if self.collection is None:
            raise RuntimeError("Chroma not available")
        self.collection.delete(where={"id": ids})
    
    def delete_by_doc_id(self, doc_id: str):
        """Törli az összes, az adott doc_id-hez tartozó darabot.
        
        Metaadat-szűrőt használ a megfelelő doc_id-jű darabok megtalálásához.
        """
        if self.collection is None:
            raise RuntimeError("Chroma not available")
        try:
            # ChromaDB where szűrő a metadata.doc_id mezőre
            self.collection.delete(where={"doc_id": doc_id})
        except Exception as e:
            # Visszalépés: lekérdezzük a megfelelő darabokat és ID alapján töröljük
            # Ez akkor kell, ha a metaadat szerinti törlés nem támogatott
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"delete with where filter failed, using fallback: {e}")
            res = self.collection.get(where={"doc_id": doc_id})
            if res and res["ids"]:
                self.collection.delete(ids=res["ids"])

    def query(self, embedding, k=5, filters: Optional[Dict] = None):
        if self.collection is None:
            raise RuntimeError("Chroma not available")
        res = self.collection.query(query_embeddings=[embedding], n_results=k, where=filters)
        # normalizálás {id, score, metadata, document} listává
        results = []
        for ids, distances, documents, metadatas in zip(res["ids"], res["distances"], res["documents"], res["metadatas"]):
            for _id, dist, doc, meta in zip(ids, distances, documents, metadatas):
                results.append({"id": _id, "score_vector": 1 - dist, "document": doc, "metadata": meta})
        return results
