from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from tools.public_api import ToolError


class TicketCreate(BaseModel):
    summary: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    priority: str = Field(default="P3", pattern=r"^P[1-4]$")
    requester_email: Optional[str] = Field(default=None, max_length=200)
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=100)


@dataclass
class TicketApiClient:
    base_url: str
    timeout_s: float
    dry_run: bool

    def create_ticket(self, payload: TicketCreate, data_dir: str, log) -> Dict[str, Any]:
        if self.dry_run:
            os.makedirs(os.path.join(data_dir, "tickets"), exist_ok=True)
            fn = f"ticket_dryrun_{int(time.time()*1000)}.json"
            path = os.path.join(data_dir, "tickets", fn)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload.model_dump(), f, ensure_ascii=False, indent=2)
            log.info("tool_ticket_dryrun_saved", path=path)
            return {"status": "dry_run_saved", "file": path}

        t0 = time.time()
        try:
            r = requests.post(
                f"{self.base_url}/tickets",
                json=payload.model_dump(),
                timeout=self.timeout_s,
            )
        except requests.Timeout as e:
            raise ToolError("ticket_api", "timeout", "Ticket API timeout") from e
        except requests.RequestException as e:
            raise ToolError("ticket_api", "network", "Ticket API network error") from e

        if r.status_code != 200:
            raise ToolError("ticket_api", "http", f"Ticket API HTTP {r.status_code}: {r.text[:200]}")

        dt_ms = int((time.time() - t0) * 1000)
        log.info("tool_ticket_api_ok", latency_ms=dt_ms)
        return r.json()

# ---- HF4 compatibility wrapper (forced) ----
def create_ticket(query: str, cfg, log):
    """
    Minimal wrapper used by agents/action.py.
    DRY_RUN: writes payload to data/tickets.
    """
    import json, os
    from datetime import datetime
    from uuid import uuid4

    run_id = uuid4().hex[:12]
    out_dir = "data/tickets"
    os.makedirs(out_dir, exist_ok=True)

    payload = {
        "run_id": run_id,
        "ts": datetime.utcnow().isoformat() + "Z",
        "title": "IT request",
        "description": query,
        "source": "knowledge-router",
    }

    path = os.path.join(out_dir, f"ticket_{run_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    try:
        log.info("tool_ticket_dry_run", run_id=run_id, path=path)
    except Exception:
        pass

    return {"ok": True, "ticket_id": run_id, "dry_run": True, "path": path}
