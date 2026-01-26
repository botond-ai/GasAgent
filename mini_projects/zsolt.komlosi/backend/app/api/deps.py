"""
Dependency injection for FastAPI routes.
"""

from functools import lru_cache
from typing import Generator, Optional

from qdrant_client import QdrantClient

from app.config import Settings, get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client instance (singleton)."""
    settings = get_settings()
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )


def get_db_session():
    """Get database session (placeholder for SQLite)."""
    # Will be implemented with aiosqlite in memory module
    pass


class ServiceContainer:
    """
    Container for application services.
    Lazy-loaded to avoid circular imports.
    """

    _agent = None
    _qdrant = None

    @classmethod
    def get_agent(cls):
        """Get or create SLAAdvisorAgent instance."""
        if cls._agent is None:
            from app.core.agent import SupportAIAgent
            cls._agent = SupportAIAgent()
        return cls._agent

    @classmethod
    def get_qdrant(cls) -> QdrantClient:
        """Get or create Qdrant client."""
        if cls._qdrant is None:
            cls._qdrant = get_qdrant_client()
        return cls._qdrant

    @classmethod
    def reset(cls):
        """Reset all services (for testing)."""
        cls._agent = None
        cls._qdrant = None


def get_agent():
    """Dependency for getting the agent."""
    return ServiceContainer.get_agent()


def get_qdrant():
    """Dependency for getting Qdrant client."""
    return ServiceContainer.get_qdrant()
