import os
import tempfile

from app.config import AppConfig
from app.openai_client import OpenAICompatClient
from app.log import get_logger
from rag.ingest import index_docs
from tools.rag import retrieve_context


def test_rag_index_and_retrieve_dev_mode(tmp_path):
    # setup temp docs
    docs_dir = tmp_path / "docs"
    (docs_dir / "it").mkdir(parents=True)
    (docs_dir / "it" / "policy.md").write_text("VPN: step1 internet\n\nstep2 client\n\nstep3 dns", encoding="utf-8")

    out_dir = tmp_path / "index"

    cfg = AppConfig(_env_file=None)  # don't read local .env
    cfg.dev_mode = True
    cfg.rag_index_dir = str(out_dir)

    log = get_logger("test", "INFO")
    client = OpenAICompatClient(
        api_key="",
        model="gpt-4o-mini",
        embedding_model="text-embedding-3-small",
        timeout_s=5.0,
        dev_mode=True,
    )

    index_docs(input_dir=str(docs_dir), out_dir=str(out_dir), client=client, log=log)

    res = retrieve_context("Mi a VPN lépés 1?", str(out_dir), 3, client, log)
    assert res["chunks"], "should return at least 1 chunk"
    assert res["chunks"][0]["doc_path"].endswith("it/policy.md")
