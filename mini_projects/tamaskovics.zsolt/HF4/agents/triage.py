from __future__ import annotations

from app.state import KRState

def heuristic_domain(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ["vpn", "install", "telep", "access", "hiba", "nem működik"]):
        return "it"
    if any(k in q for k in ["jogi", "nda", "dpa", "compliance", "levelezőlista", "jogosultság"]):
        return "legal"
    if any(k in q for k in ["onboarding", "offboarding", "szabadság", "belép", "kilép"]):
        return "hr"
    return "general"

def triage_node(state: KRState, log) -> KRState:
    q = state.query.lower()
    state.domain = heuristic_domain(state.query)

    wants_weather = any(k in q for k in ["időjárás", "weather", "forecast", "hőmérséklet"])
    wants_action = any(k in q for k in ["nyiss ticket", "készíts ticket", "mentsd", "írj levelet", "email draft", "ticketet"])

    if wants_action and state.domain in {"it", "hr", "legal"}:
        state.route = "action"
    elif wants_weather and any(k in q for k in ["policy", "dokumentum", "szerint", "mit tegyek", "mi a teendő"]):
        state.route = "mixed"
    elif wants_weather:
        state.route = "api_only"
    else:
        state.route = "rag_only"

    log.info("triage", run_id=state.run_id, domain=state.domain, route=state.route)
    state.tool_results["triage"] = {"domain": state.domain, "route": state.route}
    return state
