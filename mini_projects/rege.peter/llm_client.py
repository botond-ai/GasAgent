from __future__ import annotations

import json
import os
from typing import Any

import requests


def _ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "http://localhost:11434")


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.1:8b")


def _ollama_request(prompt: str) -> str:
    url = f"{_ollama_url()}/api/generate"
    payload = {
        "model": _ollama_model(),
        "prompt": prompt,
        "stream": False,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return str(data.get("response", "")).strip()


def llm_summarize(prompt: str, transcript: str) -> str:
    return _ollama_request(f"{prompt}\n\nLEIRAT:\n{transcript}\n\nOSSZEFOGLALO:")


def llm_extract_json_list(prompt: str, transcript: str) -> list[Any]:
    raw = _ollama_request(f"{prompt}\n\nLEIRAT:\n{transcript}\n\nVALASZ:")
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []
