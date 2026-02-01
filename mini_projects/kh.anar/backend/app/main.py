from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .api.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Alkalmazás-életciklus kezelő az indulási/leállási hook-okhoz.
    
    Induláskor:
    - Inicializálja a tudástár indexelőt, ha konfigurálva van
    - Futtatja az inkrementális tudástár-betöltést, ha engedélyezett
    
    Tervezési megjegyzés:
    - Az életciklus gondoskodik róla, hogy a tudástár indexelve legyen a kérések előtt.
    - Éles környezetben érdemes aszinkron/háttérben futtatni, hogy ne blokkolja az indulást.
    """
    from rag.config import default_config
    from rag.ingestion.kb_indexer import KBIndexer
    from rag.ingestion.version_store import VersionStore
    from rag.embeddings.embedder import HashEmbedder
    from rag.retrieval.dense import DenseRetriever
    from rag.retrieval.sparse import SparseRetriever
    from pathlib import Path
    
    if default_config.ingest_on_startup:
        logger.info("KB ingest_on_startup enabled; initializing indexer")
        try:
            # Megosztott RAG példányok importálása
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
            logger.info(f"Startup KB ingestion complete: {stats}")
        except Exception as e:
            logger.error(f"Startup KB ingestion failed: {e}", exc_info=True)
    else:
        logger.info("KB ingest_on_startup disabled")
    
    yield
    
    # Leállítás: szükség esetén takarítás
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeRouter API", version="0.1.0", lifespan=lifespan)
    app.include_router(router, prefix="/api")
    # Az admin útvonalak regisztrálása az /admin előtag alatt
    from .api import admin as admin_router
    app.include_router(admin_router.router, prefix="/admin")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
