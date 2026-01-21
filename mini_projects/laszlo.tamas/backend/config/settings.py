"""
Application Settings - Pydantic-validated configuration.

All environment variables are validated at startup using Pydantic BaseSettings.
This ensures type safety and provides clear error messages for misconfiguration.

Legacy system.ini settings are preserved for backward compatibility.
"""
import configparser
import os
from typing import Optional
from pathlib import Path
from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings

# Load legacy system.ini
config = configparser.ConfigParser()
config_path = Path(__file__).parent / "system.ini"
config.read(config_path)

# [application]
DEFAULT_LANGUAGE = config.get("application", "DEFAULT_LANGUAGE", fallback="en")
MAX_CONTEXT_TOKENS = config.getint("application", "MAX_CONTEXT_TOKENS", fallback=8000)

# [llm]
CHAT_TEMPERATURE = config.getfloat("llm", "CHAT_TEMPERATURE", fallback=0.7)
CHAT_MAX_TOKENS = config.getint("llm", "CHAT_MAX_TOKENS", fallback=500)
EMBEDDING_BATCH_SIZE = config.getint("llm", "EMBEDDING_BATCH_SIZE", fallback=100)

# [chunking]
CHUNKING_STRATEGY = config.get("chunking", "CHUNKING_STRATEGY", fallback="recursive")
CHUNK_SIZE_TOKENS = config.getint("chunking", "CHUNK_SIZE_TOKENS", fallback=500)
CHUNK_OVERLAP_TOKENS = config.getint("chunking", "CHUNK_OVERLAP_TOKENS", fallback=50)

# [retrieval]
TOP_K_DOCUMENTS = config.getint("retrieval", "TOP_K_DOCUMENTS", fallback=5)
TOP_K_PRODUCTS = config.getint("retrieval", "TOP_K_PRODUCTS", fallback=10)
SIMILARITY_METRIC = config.get("retrieval", "SIMILARITY_METRIC", fallback="cosine")
MIN_SCORE_THRESHOLD = config.getfloat("retrieval", "MIN_SCORE_THRESHOLD", fallback=0.7)

# [rag] - Search mode settings
DEFAULT_SEARCH_MODE = config.get("rag", "DEFAULT_SEARCH_MODE", fallback="hybrid")
DEFAULT_VECTOR_WEIGHT = config.getfloat("rag", "DEFAULT_VECTOR_WEIGHT", fallback=0.7)
DEFAULT_KEYWORD_WEIGHT = config.getfloat("rag", "DEFAULT_KEYWORD_WEIGHT", fallback=0.3)

# [memory]
ENABLE_LONGTERM_CHAT_STORAGE = config.getboolean("memory", "ENABLE_LONGTERM_CHAT_STORAGE", fallback=True)
ENABLE_LONGTERM_CHAT_RETRIEVAL = config.getboolean("memory", "ENABLE_LONGTERM_CHAT_RETRIEVAL", fallback=True)
CHAT_SUMMARY_MAX_TOKENS = config.getint("memory", "CHAT_SUMMARY_MAX_TOKENS", fallback=200)
CONSOLIDATE_AFTER_MESSAGES = config.getint("memory", "CONSOLIDATE_AFTER_MESSAGES", fallback=20)
MIN_MESSAGES_FOR_CONSOLIDATION = config.getint("memory", "MIN_MESSAGES_FOR_CONSOLIDATION", fallback=5)

# [rate_limiting]
REQUESTS_PER_MINUTE = config.getint("rate_limiting", "REQUESTS_PER_MINUTE", fallback=60)
MAX_CONCURRENT_REQUESTS = config.getint("rate_limiting", "MAX_CONCURRENT_REQUESTS", fallback=10)

# [cache]
ENABLE_RESPONSE_CACHE = config.getboolean("cache", "ENABLE_RESPONSE_CACHE", fallback=False)
CACHE_TTL_SECONDS = config.getint("cache", "CACHE_TTL_SECONDS", fallback=3600)

# [logging]
LOG_LLM_REQUESTS = config.getboolean("logging", "LOG_LLM_REQUESTS", fallback=True)
LOG_VECTOR_SEARCHES = config.getboolean("logging", "LOG_VECTOR_SEARCHES", fallback=True)
LOG_EMBEDDING_OPERATIONS = config.getboolean("logging", "LOG_EMBEDDING_OPERATIONS", fallback=True)

# Environment variables (from .env) - NO FALLBACK VALUES
OPENAI_MODEL_EMBEDDING = os.getenv("OPENAI_MODEL_EMBEDDING")

if not OPENAI_MODEL_EMBEDDING:
    raise ValueError("OPENAI_MODEL_EMBEDDING must be set in .env file")

# Embedding dimensions mapping
EMBEDDING_MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


# ===== PYDANTIC SETTINGS (NEW) =====

class Settings(BaseSettings):
    """
    Application configuration with Pydantic validation.
    
    All settings are loaded from environment variables.
    Use .env file for local development.
    """
    
    # ===== OpenAI Configuration =====
    openai_api_key: str = Field(
        ...,
        min_length=20,
        description="OpenAI API key (sk-...)"
    )
    
    openai_model: str = Field(
        ...,
        description="OpenAI model for chat completions"
    )
    
    embedding_model: str = Field(
        ...,
        description="OpenAI model for embeddings"
    )
    
    embedding_dimensions: int = Field(
        ...,
        ge=512,
        le=3072,
        description="Embedding vector dimensions"
    )
    
    embedding_batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Batch size for embedding operations"
    )
    
    # ===== PostgreSQL Configuration =====
    postgres_host: str = Field(
        default="localhost",
        description="PostgreSQL host"
    )
    
    postgres_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="PostgreSQL port"
    )
    
    postgres_db: str = Field(
        ...,  # Required from POSTGRES_DB env var
        min_length=1,
        description="PostgreSQL database name"
    )
    
    postgres_user: str = Field(
        default="postgres",
        min_length=1,
        description="PostgreSQL username"
    )
    
    postgres_password: str = Field(
        default="postgres",
        min_length=1,
        description="PostgreSQL password"
    )
    
    # ===== External Services Configuration =====
    excel_mcp_server_url: str = Field(
        default="http://excel-mcp-server:8017/mcp",
        description="Excel MCP server URL (streamable HTTP transport)"
    )
    
    # ===== Qdrant Configuration =====
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant server URL"
    )
    
    qdrant_api_key: Optional[str] = Field(
        default=None,
        description="Qdrant API key (optional for local)"
    )
    
    qdrant_collection_prefix: str = Field(
        default="k_r_",
        min_length=1,
        description="Prefix for Qdrant collection names"
    )
    
    qdrant_batch_size: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Batch size for Qdrant operations"
    )
    
    # ===== Application Configuration =====
    app_env: str = Field(
        default="development",
        pattern="^(development|production|test)$",
        description="Application environment"
    )
    
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level"
    )
    
    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum workflow iterations"
    )
    
    # ===== Validators =====
    
    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """Ensure OpenAI key has correct format."""
        if not v.startswith("sk-"):
            raise ValueError("OpenAI API key must start with 'sk-'")
        return v
    
    @field_validator("qdrant_url")
    @classmethod
    def validate_qdrant_url(cls, v: str) -> str:
        """Ensure Qdrant URL is valid."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Qdrant URL must start with http:// or https://")
        return v
    
    # ===== Configuration =====
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore unknown env vars
    )


# ===== Global Settings Instance =====

_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create global settings instance.
    
    This ensures settings are loaded only once and cached.
    
    Returns:
        Settings instance with validated configuration
    """
    global _settings
    
    if _settings is None:
        _settings = Settings()
    
    return _settings


# ===== Convenience Functions =====

def get_postgres_url() -> str:
    """Build PostgreSQL connection URL."""
    settings = get_settings()
    return (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


def get_qdrant_config() -> dict:
    """Get Qdrant configuration as dict."""
    settings = get_settings()
    return {
        "url": settings.qdrant_url,
        "api_key": settings.qdrant_api_key,
        "prefix": settings.qdrant_collection_prefix,
        "batch_size": settings.qdrant_batch_size
    }

def get_embedding_dimensions(model: str = None) -> int:
    """Get embedding dimensions for a model."""
    if model is None:
        model = OPENAI_MODEL_EMBEDDING
    return EMBEDDING_MODEL_DIMENSIONS.get(model, 1536)
