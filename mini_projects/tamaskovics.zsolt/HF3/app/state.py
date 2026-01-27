from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Citation:
    doc_path: str
    chunk_id: str
    score: float


@dataclass
class KRState:
    query: str
    run_id: str = ""
    domain: Optional[str] = None
    route: str = "rag_only"  # rag_only | api_only | mixed

    answer: str = ""
    citations: List[Citation] = field(default_factory=list)

    tool_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
