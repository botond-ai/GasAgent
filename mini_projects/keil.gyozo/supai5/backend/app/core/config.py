"""
Application configuration using Pydantic Settings.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # API Keys
    openai_api_key: str
    cohere_api_key: Optional[str] = None

    # LLM Configuration
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.7
    embedding_model: str = "text-embedding-3-large"

    # Vector Database
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "support_knowledge"

    # Cache
    redis_host: str = "localhost"
    redis_port: int = 6379
    cache_ttl_hours: int = 6

    # RAG Configuration
    score_threshold: float = 0.3  # Lowered for testing - increase once working
    top_k_retrieval: int = 10
    top_k_rerank: int = 5
    query_expansion_count: int = 3

    # FleetDM Configuration (optional)
    fleet_url: str = ""
    fleet_api_token: str = ""

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"

    @property
    def qdrant_url(self) -> str:
        """Get Qdrant connection URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}"


# Global settings instance
settings = Settings()
