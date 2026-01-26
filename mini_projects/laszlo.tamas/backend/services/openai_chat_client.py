"""
OpenAI Chat Completions client (native HTTP).

Single Responsibility: build/send OpenAI chat.completions requests.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx


class OpenAIChatClient:
    def __init__(self, api_key: str, timeout: int = 60, http_client: httpx.Client | None = None):
        self._api_key = api_key
        self._timeout = timeout
        self._client = http_client or httpx.Client(timeout=timeout)

    def create_chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        
        # Extract extra_body params and merge into main payload
        extra_body = payload.pop("extra_body", {})
        final_payload = {**payload, **extra_body}
        
        # Debug logging
        print(f"[DEBUG] OpenAI Request - Cache params in final payload: {final_payload.get('prompt_cache_key', 'MISSING')}")
        
        response = self._client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=final_payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def parse_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        parsed: List[Dict[str, Any]] = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            function = tc.get("function") or {}
            name = function.get("name") or tc.get("name")
            raw_args = function.get("arguments") or tc.get("args") or "{}"
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {}
            else:
                args = raw_args
            parsed.append({
                "id": tc.get("id"),
                "type": "tool_call",
                "name": name,
                "args": args,
            })
        return parsed

    @staticmethod
    def extract_usage(data: Dict[str, Any]) -> Dict[str, Any]:
        return data.get("usage", {}) or {}

    @staticmethod
    def extract_message(data: Dict[str, Any]) -> Dict[str, Any]:
        choices = data.get("choices", [])
        if not choices:
            return {}
        return choices[0].get("message", {}) or {}

    @staticmethod
    def extract_finish_reason(data: Dict[str, Any]) -> Optional[str]:
        choices = data.get("choices", [])
        if not choices:
            return None
        return choices[0].get("finish_reason")
