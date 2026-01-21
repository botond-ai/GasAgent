"""Embedding CLI application entrypoint.

Usage:
1. Copy `.env.example` -> `.env` and set `OPENAI_API_KEY`.
2. Build (optional): `docker build -t embedding-demo .`
3. Run local (without Docker): `python -m app.main`
4. Run in Docker: `docker run -it --env-file .env embedding-demo`

The app starts in batch or interactive mode depending on whether a `data/` directory exists.
If RAG agent is configured (via env vars), retrieval results are augmented with LLM responses.
If Google Calendar is configured, calendar commands are available in interactive mode.
"""
from __future__ import annotations

import logging
import sys
import os

from .config import load_config
from .embeddings import OpenAIEmbeddingService
from .vector_store import ChromaVectorStore
from .cli import CLI
from .rag_agent import RAGAgent
from .google_calendar import GoogleCalendarService


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Load configuration (reads .env)
    try:
        cfg = load_config()
    except Exception as exc:
        logging.error("Configuration error: %s", exc)
        return 1

    # Instantiate services (dependencies injected)
    emb_service = OpenAIEmbeddingService(api_key=cfg.openai_api_key, model=cfg.embedding_model)
    vector_store = ChromaVectorStore(persist_dir=cfg.chroma_persist_dir)

    # Optionally instantiate RAG agent
    rag_agent = None
    try:
        rag_agent = RAGAgent(
            api_key=cfg.openai_api_key,
            llm_model=cfg.llm_model,
            temperature=cfg.llm_temperature,
            max_tokens=cfg.llm_max_tokens,
        )
        logging.info("RAG agent initialized: %s", cfg.llm_model)
    except Exception as exc:
        logging.warning("RAG agent not available: %s", exc)

    # Optionally instantiate Google Calendar service
    calendar_service = None
    try:
        if cfg.google_calendar_credentials_file and os.path.exists(cfg.google_calendar_credentials_file):
            calendar_service = GoogleCalendarService(
                credentials_file=cfg.google_calendar_credentials_file,
                token_file=cfg.google_calendar_token_file,
            )
            logging.info("Google Calendar service initialized")
        else:
            logging.debug("Google Calendar credentials not configured")
    except Exception as exc:
        logging.warning("Google Calendar service not available: %s", exc)

    cli = CLI(emb_service=emb_service, vector_store=vector_store, rag_agent=rag_agent, calendar_service=calendar_service)
    # If a `data/` directory exists in the current working directory, process files in batch mode.
    data_dir = os.path.join(os.getcwd(), "data")
    try:
        if os.path.isdir(data_dir) and any(os.scandir(data_dir)):
            # batch processing from data directory
            cli.process_directory(data_dir)
        else:
            cli.run()
    except KeyboardInterrupt:
        print("\nExiting...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
