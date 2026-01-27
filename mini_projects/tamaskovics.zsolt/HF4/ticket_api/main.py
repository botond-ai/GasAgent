from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

app = FastAPI(title="Dummy Ticket API", version="0.1")

DATA_DIR = "/data"
TICKETS_PATH = os.path.join(DATA_DIR, "tickets.jsonl")
AUTH_TOKEN = os.getenv("TICKET_API_TOKEN", "")  # optional


class TicketCreate(BaseModel):
    summary: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    priority: str = Field(default="P3", pattern=r"^P[1-4]$")
    requester_email: Optional[str] = Field(default=None, max_length=200)
    idempotency_key: Optional[str] = Field(default=None, max_length=100)


class TicketResponse(BaseModel):
    ticket_id: str
    status: str
    stored_at_ms: int


@app.post("/tickets", response_model=TicketResponse)
def create_ticket(payload: TicketCreate, x_auth_token: str | None = Header(default=None)):
    if AUTH_TOKEN:
        if not x_auth_token or x_auth_token != AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="unauthorized")

    os.makedirs(DATA_DIR, exist_ok=True)
    ticket_id = str(uuid.uuid4())
    now_ms = int(time.time() * 1000)

    record: Dict[str, Any] = {
        "ticket_id": ticket_id,
        "status": "created",
        "stored_at_ms": now_ms,
        "payload": payload.model_dump(),
    }
    with open(TICKETS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return TicketResponse(ticket_id=ticket_id, status="created", stored_at_ms=now_ms)


@app.get("/healthz")
def healthz():
    return {"ok": True}
