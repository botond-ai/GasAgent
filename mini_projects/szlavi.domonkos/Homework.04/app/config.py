"""Configuration loader.

Loads settings from a .env file using python-dotenv and exposes
typed configuration values.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    openai_api_key: str
    embedding_model: str
    chroma_persist_dir: str
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    google_calendar_credentials_file: str | None = None
    google_calendar_token_file: str | None = None
    openweather_api_key: str | None = None
    exchangerate_api_key: str | None = None


def load_config(env_path: str | None = None) -> Config:
    """Load configuration from `.env` or environment.

    Args:
        env_path: Optional path to .env file. If None, dotenv searches for `.env`.
    """
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Copy .env.example -> .env and set the key.")

    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    llm_model_name = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
    llm_temp = float(os.getenv("OPENAI_LLM_TEMPERATURE", "0.7"))
    llm_tokens = int(os.getenv("OPENAI_LLM_MAX_TOKENS", "1024"))
    
    # Google Calendar configuration (optional)
    google_creds_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", None)
    google_token_file = os.getenv("GOOGLE_CALENDAR_TOKEN_FILE", "./token.pickle")
    
    # External API keys (optional)
    openweather_key = os.getenv("OPENWEATHER_API_KEY", None)
    exchangerate_key = os.getenv("EXCHANGERATE_API_KEY", None)

    return Config(
        openai_api_key=api_key,
        embedding_model=model,
        chroma_persist_dir=chroma_dir,
        llm_model=llm_model_name,
        llm_temperature=llm_temp,
        llm_max_tokens=llm_tokens,
        google_calendar_credentials_file=google_creds_file,
        google_calendar_token_file=google_token_file,
        openweather_api_key=openweather_key,
        exchangerate_api_key=exchangerate_key,
    )
