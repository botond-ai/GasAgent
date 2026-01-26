from __future__ import annotations

import json
import os

from app.config import AppConfig
from app.log import get_logger
from app.openai_client import OpenAICompatClient
from tools.rag import retrieve_context


DEFAULT_EVALSET = [
    {"q": "Mi a VPN hibakezelés első 3 lépése?", "expect_doc": "it/policy.md"},
    {"q": "Legal: levelezőlista/jogosultság kéréshez milyen mezők kellenek?", "expect_doc": "legal/policy.md"},
    {"q": "HR onboardingnál mik a kötelező elemek?", "expect_doc": "hr/policy.md"},
]


def main() -> int:
    cfg = AppConfig()
    log = get_logger("eval_rag", cfg.log_level)

    client = OpenAICompatClient(
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        embedding_model=cfg.openai_embedding_model,
        timeout_s=cfg.http_timeout_s,
        dev_mode=cfg.dev_mode,
    )

    hits = 0
    for ex in DEFAULT_EVALSET:
        res = retrieve_context(ex["q"], cfg.rag_index_dir, cfg.rag_top_k, client, log)
        got = {c["doc_path"] for c in res.get("chunks", [])}
        if ex["expect_doc"] in got:
            hits += 1

    hit_rate = hits / len(DEFAULT_EVALSET)
    print(json.dumps({"hit_rate": hit_rate, "n": len(DEFAULT_EVALSET)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
