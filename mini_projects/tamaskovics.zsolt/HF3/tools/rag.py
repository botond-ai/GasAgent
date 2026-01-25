from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

import numpy as np

from rag.retrieve import load_index, search
from app.openai_client import OpenAICompatClient


def retrieve_context(
    query: str,
    index_dir: str,
    top_k: int,
    client: OpenAICompatClient,
    log,
) -> Dict[str, Any]:
    t0 = time.time()
    index_path = os.path.join(index_dir, "faiss.index")
    meta_path = os.path.join(index_dir, "meta.jsonl")

    if not (os.path.exists(index_path) and os.path.exists(meta_path)):
        log.error("rag_index_missing", index_dir=index_dir)
        return {"chunks": []}

    idx, meta = load_index(index_path=index_path, meta_path=meta_path)

    q_emb = client.embed([query])
    hits = search(idx, meta, q_emb[0], top_k=top_k)

    dt_ms = int((time.time() - t0) * 1000)
    log.info("rag_retrieve", top_k=top_k, hits=len(hits), latency_ms=dt_ms)

    return {"chunks": hits}
