from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class Citation:
    doc_path: str
    chunk_id: str
    score: float


@dataclass
class KRState:
    query: str

    run_id: str = field(default_factory=lambda: uuid4().hex[:12])

    domain: Optional[str] = None
    route: str = "rag_only"

    plan_tools: List[str] = field(default_factory=list)
    blocked: bool = False

    answer: str = ""
    citations: List[Citation] = field(default_factory=list)

    tool_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
