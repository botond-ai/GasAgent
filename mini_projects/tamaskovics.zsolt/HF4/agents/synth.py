from __future__ import annotations

from app.state import KRState

def synth_node(state: KRState, log) -> KRState:
    if state.blocked:
        return state

    parts: list[str] = []
    if state.answer:
        parts.append(state.answer.strip())

    meteo = state.tool_results.get("open_meteo")
    if isinstance(meteo, dict) and meteo.get("ok"):
        parts.append(f"\nIdőjárás: {meteo.get('summary','')}".strip())

    ticket = state.tool_results.get("ticket_api")
    if isinstance(ticket, dict) and ticket.get("ok"):
        parts.append(f"\nTicket: {ticket.get('ticket_id','')}".strip())
    hrfile = state.tool_results.get("file_write")
    if isinstance(hrfile, dict) and hrfile.get("ok"):
        parts.append(f"\nHR JSON mentve: {hrfile.get('path','')}".strip())
    mail = state.tool_results.get("email_draft")
    if isinstance(mail, dict) and mail.get("ok"):
        parts.append(f"\nLegal email draft: {mail.get('path','')}".strip())

    state.answer = "\n".join([p for p in parts if p])
    log.info("synth_done", run_id=state.run_id)
    return state
