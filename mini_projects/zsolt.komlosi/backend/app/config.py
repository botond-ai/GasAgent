"""
Application configuration with Pydantic Settings.
Extends HF1 config with Qdrant, Jira, and RAG settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-large"

    # External APIs (from HF1)
    ip_api_url: str = "http://ip-api.com/json"
    holidays_api_url: str = "https://date.nager.at/api/v3/PublicHolidays"

    # Qdrant Vector Database
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: Optional[str] = None
    qdrant_collection_kb: str = "knowledge_base"
    qdrant_collection_tickets: str = "tickets"

    # SQLite Database
    database_url: str = "sqlite:///./data/sessions.db"

    # Jira Integration
    jira_url: Optional[str] = None
    jira_user_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    jira_webhook_secret: Optional[str] = None

    # RAG Settings
    rag_chunk_size: int = 600
    rag_chunk_overlap: int = 80
    rag_top_k: int = 10
    rag_rerank_top_k: int = 3
    rag_vector_weight: float = 0.5
    rag_bm25_weight: float = 0.5
    rag_max_context_tokens: int = 6000
    rag_min_score_threshold: float = 0.7

    # Memory Settings
    memory_rolling_summary_interval: int = 10
    memory_max_history: int = 50

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def jira_configured(self) -> bool:
        """Check if Jira integration is configured."""
        return all([self.jira_url, self.jira_user_email, self.jira_api_token])


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (singleton)."""
    return Settings()
