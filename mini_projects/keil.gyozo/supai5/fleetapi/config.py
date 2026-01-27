"""
Configuration module for Fleet API client.
Uses pydantic-settings for type-safe configuration management.
"""

from typing import Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Fleet API Configuration
    fleet_api_base_url: str = Field(
        default="https://localhost:8080",
        description="Base URL for Fleet API"
    )
    fleet_api_token: Optional[str] = Field(
        default=None,
        description="API token for Fleet authentication"
    )
    
    # Application Settings
    app_name: str = Field(default="Fleet API Client")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    # Security
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for JWT encoding"
    )
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=60)
    
    # Testing
    test_mode: bool = Field(default=False)
    
    @validator("fleet_api_base_url")
    def validate_url(cls, v: str) -> str:
        """Ensure URL doesn't end with trailing slash."""
        return v.rstrip("/")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
