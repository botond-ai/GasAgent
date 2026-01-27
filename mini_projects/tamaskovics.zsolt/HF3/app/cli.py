from __future__ import annotations

import argparse

import uvicorn

from app.config import AppConfig
from app.openai_client import OpenAICompatClient
from app.graph import build_graph
from app.log import get_logger
from app.state import KRState
from tools.public_api import OpenMeteoClient
from tools.ticket_api import TicketApiClient


def _print_answer(state: KRState) -> None:
    print(state.answer.strip())
    if state.citations:
        print("\nForrások:")
        for c in state.citations:
            print(f"- {c.doc_path}#{c.chunk_id} (score={c.score:.3f})")
    if state.tool_results.get("open_meteo"):
        om = state.tool_results["open_meteo"]
        if "summary" in om:
            print(f"\nOpen-Meteo: {om['summary']}")


def chat() -> int:
    cfg = AppConfig()
    log = get_logger("cli", cfg.log_level)

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

    print("KnowledgeRouter chat. Kilépés: Ctrl+C vagy üres sor.\n")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not q:
            return 0

        state = KRState(query=q)
        out = graph.invoke(state)
        _print_answer(out)

    return 0


def serve() -> int:
    cfg = AppConfig()
    # import here to avoid loading fastapi in pure CLI runs
    uvicorn.run("app.http_app:app", host="0.0.0.0", port=8000, log_level=cfg.log_level.lower())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="knowledge-router")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("chat")
    sub.add_parser("serve")

    args = parser.parse_args(argv)
    if args.cmd == "chat":
        return chat()
    if args.cmd == "serve":
        return serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
