from __future__ import annotations

from app.config import AppConfig
from app.state import KRState
from tools.public_api import OpenMeteoClient, WeatherQuery, summarize_weather, ToolError
from tools.ticket_api import TicketApiClient, TicketCreate


def open_meteo_node(state: KRState, cfg: AppConfig, meteo: OpenMeteoClient, log) -> KRState:
    city = (state.tool_results.get("triage", {}) or {}).get("city") or cfg.default_city
    try:
        res = meteo.get_current_weather(WeatherQuery(city=city, timezone=cfg.default_tz), log)
        state.tool_results["open_meteo"] = res.model_dump()
        state.tool_results["open_meteo"]["summary"] = summarize_weather(res)
    except ToolError as e:
        log.info("tool_open_meteo_error", error_type=e.error_type)
        state.errors.append(f"open_meteo:{e.error_type}")
        state.tool_results["open_meteo"] = {"error": e.error_type, "message": e.message}
    return state


def ticket_create_node(state: KRState, cfg: AppConfig, tickets: TicketApiClient, log) -> KRState:
    # Patch #2: minimal "proof": create ticket payload from query.
    payload = TicketCreate(
        summary=f"KR IT request: {state.query[:80]}",
        description=state.query,
        priority="P3",
    )
    try:
        result = tickets.create_ticket(payload, data_dir=cfg.data_dir, log=log)
        state.tool_results["ticket_api"] = result
    except ToolError as e:
        log.info("tool_ticket_api_error", error_type=e.error_type)
        state.errors.append(f"ticket_api:{e.error_type}")
        state.tool_results["ticket_api"] = {"error": e.error_type, "message": e.message}
    return state
