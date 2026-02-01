from fastapi.testclient import TestClient
from app.main import app


def test_chat_api_with_canary(monkeypatch):
    client = TestClient(app)

    # monkeypatch: az ügynök adjon vissza RAG telemetriát, hogy ne függjünk külső modellektől
    def fake_run(state):
        state["rag_context"] = [{"id": "doc-canary:0", "document": "CANARY_TOKEN document content", "metadata": {"doc_id": "doc-canary", "title": "Canary"}}]
        state["rag_telemetry"] = {"run_id": "r1", "decision": "hit", "topk": state["rag_context"], "elapsed_s": 0.01}
        state["response_text"] = "Found it in the canary doc."
        return state

    monkeypatch.setattr("app.services.agent.AgentOrchestrator.run", fake_run)

    payload = {"user_id": "u1", "session_id": "s1", "message": "Where is CANARY_TOKEN?", "metadata": {}}
    r = client.post("/chat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["debug"]["rag_telemetry"]["decision"] == "hit"
    assert "CANARY_TOKEN" in data["reply"] or "Canary" in data["debug"]["rag_context"][0]["metadata"]["title"]
