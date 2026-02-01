from dataclasses import dataclass
import os

# Konfiguráció a RAG komponensekhez. Az értékek env-ből töltődnek vagy alapértelmezetten kerülnek be.
# Dataclass-t használunk, hogy a konfiguráció kvázi változatlan és könnyen továbbadható legyen,
# a DIP-hez (dependancy injection of config) igazodva.

@dataclass
class RAGConfig:
    chroma_dir: str = os.getenv("CHROMA_DIR", ".chroma")
    chroma_collection: str = os.getenv("CHROMA_COLLECTION", "kb_collection")
    embed_model: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    k: int = int(os.getenv("RAG_TOP_K", "5"))
    threshold: float = float(os.getenv("RAG_THRESHOLD", "0.25"))
    w_dense: float = float(os.getenv("RAG_W_DENSE", "0.7"))
    w_sparse: float = float(os.getenv("RAG_W_SPARSE", "0.3"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "800"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "128"))
    persist: bool = os.getenv("CHROMA_PERSIST", "true").lower() == "true"
    
    # Tudástár-mappa betöltésének konfigurációja
    kb_data_dir: str = os.getenv("KB_DATA_DIR", "docs/kb-data")
    kb_version_store: str = os.getenv("KB_VERSION_STORE", ".kb_versions.json")
    ingest_on_startup: bool = os.getenv("KB_INGEST_ON_STARTUP", "true").lower() == "true"


# Alapértelmezetten használandó egyetlen konfigurációs példány exportálása. A tesztek másikat is beinjektálhatnak.
default_config = RAGConfig()  # type: ignore
