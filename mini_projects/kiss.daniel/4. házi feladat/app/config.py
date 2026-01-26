"""
Configuration module using Pydantic Settings.
Loads all settings from .env file with sensible defaults.
"""

from enum import Enum
from functools import lru_cache
from typing import Optional
import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AgentProfile(str, Enum):
    """Agent profile determines model selection strategy."""
    FAST = "FAST"
    BALANCED = "BALANCED"
    QUALITY = "QUALITY"


# Model mappings per profile
PROFILE_MODELS = {
    AgentProfile.QUALITY: {
        "planner": "gpt-oss:20b",
        "extractor": "gpt-oss:20b",
        "summarizer": "gpt-oss:20b",
        "final": "llama3.1:8b",
    },
    AgentProfile.BALANCED: {
        "planner": "qwen2.5:14b-instruct",
        "extractor": "qwen2.5:14b-instruct",
        "summarizer": "llama3.1:8b",
        "final": "llama3.1:8b",
    },
    AgentProfile.FAST: {
        "planner": "phi3.5:latest",
        "extractor": "phi3.5:latest",
        "summarizer": "llama3.2:3b",
        "final": "llama3.2:3b",
    },
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Ollama settings
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_timeout_s: int = Field(default=60, alias="OLLAMA_TIMEOUT_S")
    ollama_temperature: float = Field(default=0.2, alias="OLLAMA_TEMPERATURE")
    
    # Agent profile
    agent_profile: AgentProfile = Field(default=AgentProfile.BALANCED, alias="AGENT_PROFILE")
    
    # Model overrides (if not set, uses profile defaults)
    ollama_model_planner: Optional[str] = Field(default=None, alias="OLLAMA_MODEL_PLANNER")
    ollama_model_extractor: Optional[str] = Field(default=None, alias="OLLAMA_MODEL_EXTRACTOR")
    ollama_model_summarizer: Optional[str] = Field(default=None, alias="OLLAMA_MODEL_SUMMARIZER")
    ollama_model_final: Optional[str] = Field(default=None, alias="OLLAMA_MODEL_FINAL")
    
    # Embedding model
    ollama_embed_model: str = Field(default="mxbai-embed-large:latest", alias="OLLAMA_EMBED_MODEL")
    
    # Fallback models (CSV)
    ollama_model_fallbacks: str = Field(
        default="gpt-oss:20b,qwen2.5:14b-instruct,llama3.1:8b,phi3.5:latest,llama3.2:3b",
        alias="OLLAMA_MODEL_FALLBACKS"
    )
    
    # Google Calendar settings
    google_calendar_id: str = Field(default="primary", alias="GOOGLE_CALENDAR_ID")
    
    # Service account auth
    google_service_account_file: Optional[str] = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_FILE")
    google_service_account_json: Optional[str] = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_JSON")
    google_impersonate_user: Optional[str] = Field(default=None, alias="GOOGLE_IMPERSONATE_USER")
    
    # OAuth auth
    google_oauth_client_id: Optional[str] = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_oauth_redirect_uri: str = Field(default="http://localhost:8080", alias="GOOGLE_OAUTH_REDIRECT_URI")
    google_oauth_token_path: str = Field(default=".google_token.json", alias="GOOGLE_OAUTH_TOKEN_PATH")
    
    # General settings
    app_timezone: str = Field(default="Europe/Budapest", alias="APP_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Memory store path
    memory_store_path: str = Field(default=".memory_store.json", alias="MEMORY_STORE_PATH")
    
    # Retry settings
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    retry_base_delay: float = Field(default=1.0, alias="RETRY_BASE_DELAY")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
    
    @property
    def fallback_models(self) -> list[str]:
        """Parse fallback models from CSV string."""
        return [m.strip() for m in self.ollama_model_fallbacks.split(",") if m.strip()]
    
    def get_model_for_task(self, task: str) -> str:
        """
        Get the appropriate model for a given task.
        
        Args:
            task: One of 'planner', 'extractor', 'summarizer', 'final'
            
        Returns:
            Model name string
        """
        # Check for explicit override first
        override_map = {
            "planner": self.ollama_model_planner,
            "extractor": self.ollama_model_extractor,
            "summarizer": self.ollama_model_summarizer,
            "final": self.ollama_model_final,
        }
        
        override = override_map.get(task)
        if override:
            return override
        
        # Fall back to profile default
        return PROFILE_MODELS[self.agent_profile].get(task, "llama3.1:8b")
    
    def has_google_service_account(self) -> bool:
        """Check if service account credentials are configured."""
        return bool(self.google_service_account_file or self.google_service_account_json)
    
    def has_google_oauth(self) -> bool:
        """Check if OAuth credentials are configured."""
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)
    
    def mask_sensitive(self, value: str) -> str:
        """Mask sensitive values for logging."""
        if not value:
            return "<not set>"
        if len(value) <= 8:
            return "****"
        return f"{value[:4]}...{value[-4:]}"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
