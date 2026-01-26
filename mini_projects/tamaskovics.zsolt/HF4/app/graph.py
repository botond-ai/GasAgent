from __future__ import annotations

from langgraph.graph import StateGraph, END

from app.state import KRState
from app.log import get_logger

from agents.triage import triage_node
from agents.guardrail import guardrail_node
from agents.knowledge import knowledge_node
from agents.action import action_node
from agents.synth import synth_node


def build_graph(cfg, llm, meteo=None, tickets=None):
    # inject mocked clients for tests
    cfg.meteo_client = meteo
    cfg.ticket_client = tickets

    log = get_logger("graph", getattr(cfg, "log_level", "INFO"))

    g = StateGraph(KRState)
    g.add_node("triage", lambda s: triage_node(s, log))
    g.add_node("guardrail", lambda s: guardrail_node(s, log))
    g.add_node("knowledge", lambda s: knowledge_node(s, cfg, llm, log))
    g.add_node("action", lambda s: action_node(s, cfg, log))
    g.add_node("synth", lambda s: synth_node(s, log))

    g.set_entry_point("triage")
    g.add_edge("triage", "guardrail")
    g.add_edge("guardrail", "knowledge")
    g.add_edge("knowledge", "action")
    g.add_edge("action", "synth")
    g.add_edge("synth", END)

    return g.compile()
