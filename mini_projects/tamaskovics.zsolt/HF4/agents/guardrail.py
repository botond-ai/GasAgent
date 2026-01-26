from __future__ import annotations

from app.state import KRState

ALLOWED_BY_ROUTE = {
    "rag_only": {"rag"},
    "api_only": {"open_meteo"},
    "mixed": {"rag", "open_meteo"},
    "action": {"rag", "ticket_api", "file_write", "email_draft"},
}

def validate_plan(route: str, tools: list[str]) -> bool:
    allowed = ALLOWED_BY_ROUTE.get(route, set())
    return all(t in allowed for t in tools)

def guardrail_node(state: KRState, log) -> KRState:
    # Plan by route/domain (minimal deterministic)
    tools: list[str] = []
    if state.route in {"rag_only", "mixed", "action"}:
        tools.append("rag")
    if state.route in {"api_only", "mixed"}:
        tools.append("open_meteo")
    if state.route == "action":
        if state.domain == "it":
            tools.append("ticket_api")
        elif state.domain == "hr":
            tools.append("file_write")
        elif state.domain == "legal":
            tools.append("email_draft")

    state.plan_tools = tools

    if not validate_plan(state.route, tools):
        state.errors.append("guardrail_tool_block")
        state.answer = "Blokkoltam: nem engedélyezett tool a route-hoz."
        log.info("guardrail_block", run_id=state.run_id, route=state.route, tools=tools)
        state.blocked = True
        return state

    log.info("guardrail_ok", run_id=state.run_id, route=state.route, tools=tools)
    return state
