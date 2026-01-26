from __future__ import annotations

import json
from typing import Dict, List, Tuple, Any

import faiss
import numpy as np


def load_index(index_path: str, meta_path: str) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
    index = faiss.read_index(index_path)
    meta: List[Dict[str, Any]] = []
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            meta.append(json.loads(line))
    return index, meta


def search(index: faiss.Index, meta: List[Dict[str, Any]], query_vec: np.ndarray, top_k: int) -> List[Dict[str, Any]]:
    q = query_vec.astype("float32").reshape(1, -1)
    scores, idxs = index.search(q, top_k)

    out: List[Dict[str, Any]] = []
    for score, i in zip(scores[0].tolist(), idxs[0].tolist()):
        if i < 0:
            continue
        m = meta[i].copy()
        m["score"] = float(score)
        out.append(m)

    # low-score cutoff ("no answer" mode). DEV_MODE random vectors are low-sim by nature.
    if out and out[0]["score"] < 0.05:
        return []
    return out
