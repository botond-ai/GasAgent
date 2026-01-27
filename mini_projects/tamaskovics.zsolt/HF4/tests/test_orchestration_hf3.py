from unittest.mock import Mock

from app.config import AppConfig
from app.openai_client import OpenAICompatClient
from app.graph import build_graph
from app.log import get_logger
from app.state import KRState
from rag.ingest import index_docs
from tools.public_api import OpenMeteoClient, ToolError, WeatherQuery
from tools.ticket_api import TicketApiClient


class MeteoOk(OpenMeteoClient):
    def get_current_weather(self, q: WeatherQuery, log):
        return super().get_current_weather(q, log)


class MeteoFail(OpenMeteoClient):
    def get_current_weather(self, q: WeatherQuery, log):
        raise ToolError("open_meteo", "timeout", "boom")


def _setup(tmp_path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "it").mkdir(parents=True)
    (docs_dir / "it" / "policy.md").write_text("VPN: step1 internet\n\nstep2 client\n\nstep3 dns", encoding="utf-8")

    out_dir = tmp_path / "index"
    cfg = AppConfig(_env_file=None)
    cfg.dev_mode = True
    cfg.rag_index_dir = str(out_dir)
    cfg.rag_top_k = 2

    log = get_logger("test", "INFO")
    llm = OpenAICompatClient("", "gpt-4o-mini", "text-embedding-3-small", 5.0, True)
    index_docs(str(docs_dir), str(out_dir), llm, log)
    return cfg, llm


def test_hf3_mixed_success(tmp_path):
    cfg, llm = _setup(tmp_path)
    meteo = MeteoOk("x", "y", 1.0, True)
    cfg.data_dir = str(tmp_path / 'data')
    (tmp_path / 'data').mkdir(exist_ok=True)
    tickets = TicketApiClient(base_url='http://ticket-api:9000', timeout_s=1.0, dry_run=True)
    graph = build_graph(cfg, llm, meteo, tickets)

    out = graph.invoke(KRState(query="A dokumentum szerint mit tegyek VPN hibánál, és milyen az időjárás Budapesten?"))
    assert out.route in ("mixed", "rag_only")  # heuristic
    assert out.tool_results.get("open_meteo") is not None
    assert out.answer


def test_hf3_mixed_fail_safe(tmp_path):
    cfg, llm = _setup(tmp_path)
    meteo = MeteoFail("x", "y", 1.0, True)
    cfg.data_dir = str(tmp_path / 'data')
    (tmp_path / 'data').mkdir(exist_ok=True)
    tickets = TicketApiClient(base_url='http://ticket-api:9000', timeout_s=1.0, dry_run=True)
    graph = build_graph(cfg, llm, meteo, tickets)

    out = graph.invoke(KRState(query="A dokumentum szerint mit tegyek VPN hibánál, és milyen az időjárás Budapesten?"))
    assert out.answer
    assert any(e.startswith("open_meteo:") for e in out.errors)
