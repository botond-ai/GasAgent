from __future__ import annotations

from typing import Any

from app.config import AppConfig
from app.openai_client import OpenAICompatClient, ChatMessage
from app.state import KRState, Citation
from tools.rag import retrieve_context


def knowledge_node(state: KRState, cfg: AppConfig, client: OpenAICompatClient, log) -> KRState:
    # RAG retrieve
    ctx = retrieve_context(
        query=state.query,
        index_dir=cfg.rag_index_dir,
        top_k=cfg.rag_top_k,
        client=client,
        log=log,
    )

    if not ctx["chunks"]:
        state.answer = "Nem találtam elég releváns információt a doksikban. Pontosíts: domain (IT/Legal/HR) + kulcsszavak."
        state.citations = []
        return state

    # build prompt
    context_text = "\n\n".join(
        [f"[CIT:{c['doc_path']}#{c['chunk_id']}]\n{c['text']}" for c in ctx["chunks"]]
    )

    system = "Vállalati policy alapú asszisztens vagy. Csak a megadott kontextus alapján válaszolj. " \
             "Ha nincs benne, mondd ki. A végén sorold fel a felhasznált CIT azonosítókat."
    user = f"Kérdés: {state.query}\n\nKontekstus:\n{context_text}"

    answer = client.chat([
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user),
    ])

    state.answer = answer

    state.citations = [
        Citation(doc_path=c["doc_path"], chunk_id=c["chunk_id"], score=float(c["score"]))
        for c in ctx["chunks"]
    ]
    state.tool_results["rag"] = {"top_k": cfg.rag_top_k, "hits": len(ctx["chunks"])}
    return state
