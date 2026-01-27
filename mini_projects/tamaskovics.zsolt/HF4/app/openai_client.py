from __future__ import annotations

import hashlib
import math
import os
import random
import time
from dataclasses import dataclass
from typing import List, Sequence, Dict, Any

import numpy as np

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


@dataclass
class ChatMessage:
    role: str
    content: str


class OpenAICompatClient:
    """Small wrapper with DEV_MODE deterministic fallback."""

    def __init__(self, api_key: str, model: str, embedding_model: str, timeout_s: float, dev_mode: bool):
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.timeout_s = timeout_s
        self.dev_mode = dev_mode

        self._client = None
        if not dev_mode:
            if OpenAI is None:
                raise RuntimeError("openai package is missing")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is empty but DEV_MODE=0")
            self._client = OpenAI(api_key=api_key, timeout=timeout_s)

        # deterministic seed for DEV_MODE
        random.seed(1337)

    def embed(self, texts: Sequence[str], dim: int = 256) -> np.ndarray:
        if self.dev_mode:
            return np.vstack([self._fake_embed(t, dim) for t in texts]).astype("float32")
        assert self._client is not None
        t0 = time.time()
        resp = self._client.embeddings.create(model=self.embedding_model, input=list(texts))
        # OpenAI returns embeddings aligned with input order
        embs = [d.embedding for d in resp.data]
        arr = np.array(embs, dtype="float32")
        # normalize
        arr = arr / (np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12)
        return arr

    def chat(self, messages: Sequence[ChatMessage]) -> str:
        if self.dev_mode:
            # very small deterministic "LLM": return last user content plus a hint.
            user = "\n".join([m.content for m in messages if m.role == "user"])[-2000:]
            ctx = "\n".join([m.content for m in messages if m.role == "system"])[-2000:]
            return f"[DEV_MODE válasz]\n{user}\n\n(Context hint: {ctx[:200]}...)".strip()

        assert self._client is not None
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()

    def _fake_embed(self, text: str, dim: int) -> np.ndarray:
        # hash -> pseudo-random unit vector (deterministic)
        h = hashlib.blake2b(text.encode("utf-8"), digest_size=32).digest()
        rnd = random.Random(h)
        v = np.array([rnd.uniform(-1.0, 1.0) for _ in range(dim)], dtype="float32")
        v = v / (np.linalg.norm(v) + 1e-12)
        return v
