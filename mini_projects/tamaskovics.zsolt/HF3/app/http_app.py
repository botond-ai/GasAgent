from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import AppConfig
from app.log import get_logger
from app.openai_client import OpenAICompatClient
from tools.public_api import OpenMeteoClient
from tools.ticket_api import TicketApiClient
from app.graph import build_graph
from app.state import KRState


class RunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


def create_app() -> FastAPI:
    cfg = AppConfig()
    log = get_logger("api", cfg.log_level)

    llm = OpenAICompatClient(
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        embedding_model=cfg.openai_embedding_model,
        timeout_s=cfg.http_timeout_s,
        dev_mode=cfg.dev_mode,
    )
    meteo = OpenMeteoClient(
        geo_url=cfg.open_meteo_geo_url,
        forecast_url=cfg.open_meteo_forecast_url,
        timeout_s=cfg.http_timeout_s,
        dev_mode=cfg.dev_mode,
    )
    tickets = TicketApiClient(base_url=cfg.ticket_api_url, timeout_s=cfg.http_timeout_s, dry_run=cfg.ticket_dry_run)
    graph = build_graph(cfg, llm, meteo, tickets)

    app = FastAPI(title="KnowledgeRouter", version="0.2")

    @app.get("/", response_class=HTMLResponse)
    def home():
        return """<!doctype html>
<html><head><meta charset="utf-8"><title>KnowledgeRouter</title></head>
<body style="font-family: sans-serif; max-width: 900px; margin: 24px auto;">
<h2>KnowledgeRouter demo</h2>
<form method="post" action="/agent/run">
<textarea name="query" rows="6" style="width: 100%;" placeholder="Írj ide..."></textarea><br/>
<button type="submit">Küldés</button>
</form>
<p style="color:#555;">Tipp: kérdezz policy-t, vagy kérdezz időjárást is: „Mit mond a policy, és milyen az időjárás Budapesten?”</p>
</body></html>"""

    @app.post("/agent/run")
    async def run_agent_form(query: str = ""):
        # HTML form submit
        state = KRState(query=query or "")
        out = graph.invoke(state)
        payload = _state_to_dict(out)
        pretty = json.dumps(payload, ensure_ascii=False, indent=2)
        return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>KnowledgeRouter result</title></head>
<body style="font-family: monospace; max-width: 900px; margin: 24px auto;">
<a href="/">← back</a>
<pre>{pretty}</pre>
</body></html>""")

    @app.post("/agent/run.json")
    async def run_agent(req: RunRequest) -> Dict[str, Any]:
        state = KRState(query=req.query)
        out = graph.invoke(state)
        return _state_to_dict(out)

    return app


def _state_to_dict(s: KRState) -> Dict[str, Any]:
    return {
        "run_id": s.run_id,
        "domain": s.domain,
        "route": s.route,
        "answer": s.answer,
        "citations": [c.__dict__ for c in s.citations],
        "tool_results": s.tool_results,
        "errors": s.errors,
    }


app = create_app()
