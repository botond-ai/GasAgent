from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dev_mode: bool = Field(default=True, validation_alias="DEV_MODE")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", validation_alias="OPENAI_EMBEDDING_MODEL")

    rag_index_dir: str = Field(default="data/index", validation_alias="RAG_INDEX_DIR")
    rag_top_k: int = Field(default=5, validation_alias="RAG_TOP_K")

    http_timeout_s: float = Field(default=10.0, validation_alias="HTTP_TIMEOUT_S")

    # HF1: Open-Meteo (public API)
    open_meteo_geo_url: str = Field(
        default="https://geocoding-api.open-meteo.com/v1/search",
        validation_alias="OPEN_METEO_GEO_URL",
    )
    open_meteo_forecast_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        validation_alias="OPEN_METEO_FORECAST_URL",
    )
    default_city: str = Field(default="Budapest", validation_alias="DEFAULT_CITY")
    default_tz: str = Field(default="Europe/Budapest", validation_alias="DEFAULT_TZ")

    # Dummy ticket API (internal)
    ticket_api_url: str = Field(default="http://ticket-api:9000", validation_alias="TICKET_API_URL")
    ticket_dry_run: bool = Field(default=True, validation_alias="TICKET_DRY_RUN")

    data_dir: str = Field(default="data", validation_alias="DATA_DIR")
