"""
Django app configuration.
"""
import logging
import os
from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """Initialize services on app startup."""
        logger.info("Initializing API app...")
        
        # Skip health check during migrations or management commands
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            logger.info("⏭️ Skipping initialization during migrations")
            return

        try:
            # Run health checks first
            logger.info("🏥 Running infrastructure health checks...")
            from infrastructure.health_check import validate_startup_config_sync
            
            health_ok = validate_startup_config_sync()
            if not health_ok:
                logger.warning("⚠️ Some infrastructure components unavailable - continuing anyway")
            
            # Import dependencies
            from pathlib import Path
            from infrastructure.openai_clients import OpenAIClientFactory
            from infrastructure.repositories import (
                FileUserRepository,
                FileConversationRepository,
            )
            from infrastructure.rag_client import MockQdrantClient  # Use Mock for development
            from infrastructure.postgres_client import postgres_client
            from services.agent import QueryAgent
            from services.chat_service import ChatService

            # PostgreSQL pool initialization - EAGER INIT to avoid first-request latency
            # Use thread to avoid blocking Django startup
            import asyncio
            import threading
            
            def init_postgres_pool():
                """Initialize PostgreSQL pool in background thread."""
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(postgres_client.ensure_initialized())
                    loop.close()
                    logger.info("✅ PostgreSQL pool initialized successfully (eager init)")
                except Exception as e:
                    logger.warning(f"⚠️ PostgreSQL eager init failed (will retry on first request): {e}")
            
            # Start init in background thread (non-blocking)
            init_thread = threading.Thread(target=init_postgres_pool, daemon=True)
            init_thread.start()
            logger.info("⏳ PostgreSQL pool initialization started in background...")

            # Initialize repositories
            user_repo = FileUserRepository(data_dir=settings.USERS_DIR)
            conversation_repo = FileConversationRepository(data_dir=settings.SESSIONS_DIR)

            # Initialize RAG client (QdrantRAGClient for production with feedback-weighted ranking)
            from infrastructure.qdrant_rag_client import QdrantRAGClient
            qdrant_host = os.getenv("QDRANT_HOST", "localhost")
            qdrant_port = os.getenv("QDRANT_PORT", "6333")
            rag_client = QdrantRAGClient(
                qdrant_url=f"http://{qdrant_host}:{qdrant_port}",
                collection_name="multi_domain_kb"
            )

            # Initialize LLM (OpenAI)
            llm = OpenAIClientFactory.get_llm(
                model=settings.OPENAI_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                api_key=settings.OPENAI_API_KEY,
            )

            # Initialize agent
            agent = QueryAgent(llm_client=llm, rag_client=rag_client)

            # Initialize chat service
            chat_service = ChatService(
                user_repo=user_repo,
                conversation_repo=conversation_repo,
                agent=agent,
            )

            # Store in app config for later access
            self.chat_service = chat_service
            self.user_repo = user_repo
            self.conversation_repo = conversation_repo

            logger.info("API app initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize API app: {e}", exc_info=True)
            raise
