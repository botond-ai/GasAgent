from __future__ import annotations

import argparse

from app.config import AppConfig
from app.log import get_logger
from app.openai_client import OpenAICompatClient
from rag.ingest import index_docs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="docs/ input dir")
    p.add_argument("--out", required=True, help="data/index output dir")
    args = p.parse_args(argv)

    cfg = AppConfig()
    log = get_logger("index_docs", cfg.log_level)

    client = OpenAICompatClient(
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        embedding_model=cfg.openai_embedding_model,
        timeout_s=cfg.http_timeout_s,
        dev_mode=cfg.dev_mode,
    )

    index_docs(input_dir=args.input, out_dir=args.out, client=client, log=log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
