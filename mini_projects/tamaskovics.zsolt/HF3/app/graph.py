from __future__ import annotations

import uuid

from langgraph.graph import StateGraph, END

from app.state import KRState
from app.config import AppConfig
from app.openai_client import OpenAICompatClient
from app.log import get_logger

from agents.knowledge import knowledge_node
from agents.triage import triage_decide
from agents.action import open_meteo_node, ticket_create_node
from tools.public_api import OpenMeteoClient
from tools.ticket_api import TicketApiClient


def _need_ticket(state: KRState) -> bool:
    if state.domain != "it":
        return False
    q = state.query.lower()
    return any(k in q for k in ["nem működik", "nem mukodik", "hiba", "vpn", "ticket", "jira"])


def build_graph(cfg: AppConfig, llm: OpenAICompatClient, meteo: OpenMeteoClient, tickets: TicketApiClient):
    log = get_logger("graph", cfg.log_level)

    def triage_node(state: KRState) -> KRState:
        if not state.run_id:
            state.run_id = str(uuid.uuid4())
        decision = triage_decide(state.query)
        state.domain = decision.domain
        state.route = decision.route
        state.tool_results["triage"] = {"domain": decision.domain, "route": decision.route, "city": decision.city}
        log.info("triage", run_id=state.run_id, domain=decision.domain, route=decision.route, city=decision.city)
        return state

    def synth_node(state: KRState) -> KRState:
        # minimal synthesis: keep RAG answer if present, add weather if available
        weather = (state.tool_results.get("open_meteo") or {}).get("summary")
        if state.route == "api_only":
            if weather:
                state.answer = f"Időjárás (Open-Meteo): {weather}"
            else:
                state.answer = "Időjárás lekérdezés nem sikerült."
            return state

        if state.route == "mixed":
            base = state.answer.strip() or "Policy válasz nem elérhető."
            if weather:
                state.answer = base + f"\n\nIdőjárás (Open-Meteo): {weather}"
            else:
                state.answer = base + "\n\nIdőjárás lekérdezés nem sikerült."
            return state

        # rag_only: knowledge_node already sets answer
        return state

    g = StateGraph(KRState)
    g.add_node("triage", triage_node)
    g.add_node("knowledge", lambda s: knowledge_node(s, cfg, llm, log))
    g.add_node("open_meteo", lambda s: open_meteo_node(s, cfg, meteo, log))
    g.add_node("ticket_api", lambda s: ticket_create_node(s, cfg, tickets, log))
    g.add_node("synth", synth_node)

    g.set_entry_point("triage")

    def route_after_triage(state: KRState) -> str:
        if state.route == "api_only":
            return "open_meteo"
        return "knowledge"

    g.add_conditional_edges("triage", route_after_triage, {"knowledge": "knowledge", "open_meteo": "open_meteo"})

    def after_knowledge(state: KRState) -> str:
        # HF3: mixed -> orchestrate RAG + Open-Meteo
        if state.route == "mixed":
            return "open_meteo"
        # optional proof action for IT
        return "ticket_api" if _need_ticket(state) else "synth"

    g.add_conditional_edges(
        "knowledge",
        after_knowledge,
        {"open_meteo": "open_meteo", "ticket_api": "ticket_api", "synth": "synth"},
    )

    def after_open_meteo(state: KRState) -> str:
        return "ticket_api" if _need_ticket(state) else "synth"

    g.add_conditional_edges("open_meteo", after_open_meteo, {"ticket_api": "ticket_api", "synth": "synth"})
    g.add_edge("ticket_api", "synth")
    g.add_edge("synth", END)

compiled = g.compile()

class _GraphWrapper:
    def __init__(self, inner):
        self._inner = inner

    def invoke(self, *args, **kwargs):
        res = self._inner.invoke(*args, **kwargs)
        if isinstance(res, KRState):
            return res
        if hasattr(KRState, "model_validate"):  # pydantic v2
            return KRState.model_validate(res)
        return KRState(**res)

    def __getattr__(self, name):
        return getattr(self._inner, name)

return _GraphWrapper(compiled)
