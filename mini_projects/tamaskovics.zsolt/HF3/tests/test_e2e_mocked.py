from app.config import AppConfig
from app.openai_client import OpenAICompatClient
from app.graph import build_graph
from app.log import get_logger
from app.state import KRState
from rag.ingest import index_docs
from tools.public_api import OpenMeteoClient


def test_graph_returns_answer_with_citations(tmp_path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "hr").mkdir(parents=True)
    (docs_dir / "hr" / "policy.md").write_text("Onboarding: belépési dátum, manager, eszközigény.", encoding="utf-8")

    out_dir = tmp_path / "index"

    cfg = AppConfig(_env_file=None)
    cfg.dev_mode = True
    cfg.rag_index_dir = str(out_dir)
    cfg.rag_top_k = 2

    log = get_logger("test", "INFO")
    llm = OpenAICompatClient("", "gpt-4o-mini", "text-embedding-3-small", 5.0, True)
    index_docs(str(docs_dir), str(out_dir), llm, log)

    meteo = OpenMeteoClient("x", "y", 1.0, True)
    from tools.ticket_api import TicketApiClient
    tickets = TicketApiClient(base_url='http://ticket-api:9000', timeout_s=1.0, dry_run=True)
    cfg.data_dir = str(tmp_path / 'data')
    (tmp_path / 'data').mkdir(exist_ok=True)
    graph = build_graph(cfg, llm, meteo, tickets)

    out = graph.invoke(KRState(query="Mi kell onboardinghoz?"))
    assert out.answer
    assert out.citations
    assert out.domain in ("hr", "general")
