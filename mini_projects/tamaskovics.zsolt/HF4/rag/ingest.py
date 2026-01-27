from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import faiss
import numpy as np

from app.openai_client import OpenAICompatClient


@dataclass
class Chunk:
    doc_path: str
    chunk_id: str
    text: str


def iter_docs(input_dir: str) -> Iterable[Tuple[str, str]]:
    for root, _, files in os.walk(input_dir):
        for fn in files:
            if not (fn.endswith(".md") or fn.endswith(".txt")):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, input_dir).replace("\\", "/")
            with open(path, "r", encoding="utf-8") as f:
                yield rel, f.read()


def chunk_text(text: str, max_chars: int = 900) -> List[str]:
    # paragraph-ish splitting
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: List[str] = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = (buf + "\n\n" + p).strip()
        else:
            if buf:
                out.append(buf)
            buf = p
    if buf:
        out.append(buf)
    return out


def build_chunks(input_dir: str) -> List[Chunk]:
    chunks: List[Chunk] = []
    for rel, content in iter_docs(input_dir):
        texts = chunk_text(content)
        for i, t in enumerate(texts):
            chunks.append(Chunk(doc_path=rel, chunk_id=f"c{i:03d}", text=t))
    return chunks


def index_docs(input_dir: str, out_dir: str, client: OpenAICompatClient, log, dim: int = 256) -> None:
    os.makedirs(out_dir, exist_ok=True)

    chunks = build_chunks(input_dir)
    if not chunks:
        raise RuntimeError(f"No docs found under: {input_dir}")

    texts = [c.text for c in chunks]
    embs = client.embed(texts, dim=dim)

    if embs.dtype != np.float32:
        embs = embs.astype("float32")

    # cosine similarity via inner product on normalized vectors
    index = faiss.IndexFlatIP(embs.shape[1])
    index.add(embs)
    faiss.write_index(index, os.path.join(out_dir, "faiss.index"))

    meta_path = os.path.join(out_dir, "meta.jsonl")
    with open(meta_path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps({"doc_path": c.doc_path, "chunk_id": c.chunk_id, "text": c.text}, ensure_ascii=False) + "\n")

    log.info("rag_index_built", docs=len({c.doc_path for c in chunks}), chunks=len(chunks), out_dir=out_dir)
