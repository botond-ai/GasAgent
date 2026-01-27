from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import hashlib

# --- PromptLineage dataclass ---
@dataclass
class PromptLineage:
    prompt_hash: str
    request_id: str
    agent_execution_id: str
    model_name: str
    timestamp: str
    prompt_version: Optional[str] = None
    message_count: int = 0
    total_chars: int = 0

# --- PromptLineageTracker ---
class PromptLineageTracker:
    def __init__(self):
        self._lineage_records: List[PromptLineage] = []

    def _messages_to_text(self, messages) -> str:
        return "\n".join(str(m) for m in messages)

    def _hash_prompt(self, prompt_text: str) -> str:
        return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    def track_prompt(
        self,
        messages,
        model_name: str,
        agent_execution_id: str,
        prompt_version: Optional[str] = None
    ) -> PromptLineage:
        prompt_text = self._messages_to_text(messages)
        prompt_hash = self._hash_prompt(prompt_text)
        lineage = PromptLineage(
            prompt_hash=prompt_hash,
            request_id=get_request_id(),
            agent_execution_id=agent_execution_id,
            model_name=model_name,
            timestamp=datetime.utcnow().isoformat(),
            prompt_version=prompt_version,
            message_count=len(messages),
            total_chars=len(prompt_text)
        )
        self._lineage_records.append(lineage)
        return lineage

# --- Singleton tracker getter ---
_prompt_tracker = None

def get_prompt_tracker():
    global _prompt_tracker
    if _prompt_tracker is None:
        _prompt_tracker = PromptLineageTracker()
    return _prompt_tracker

# --- Dummy get_request_id (should be replaced with real request context) ---
def get_request_id() -> str:
    return f"req_{datetime.utcnow().timestamp()}"
