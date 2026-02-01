from fastapi.testclient import TestClient
from app.main import app
import os
 

def test_admin_add_and_reindex(monkeypatch):
    client = TestClient(app)
    # állítsuk be a várt admin tokent
    os.environ["ADMIN_TOKEN"] = "testtoken"
    payload = {
        "doc_id": "admin-doc",
        "title": "Admin Doc",
        "source": "tests",
        "doc_type": "note",
        "version": "1",
        "access_scope": "private",
        "text": "ADMIN_CANARY"
    }

    r = client.post("/admin/rag/add", json=payload, headers={"token": "testtoken"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"]

    # a tartósított fájlnak léteznie kell a DATA_DIR/rag_documents alatt
    from pathlib import Path
    dd = Path(".") / "rag_documents" / "admin-doc.json"
    assert dd.exists(), f"expected persisted doc at {dd}"

    r2 = client.post("/admin/rag/reindex", headers={"token": "testtoken"})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["success"]

    # jogosulatlan kérés
    r3 = client.post("/admin/rag/add", json=payload, headers={"token": "bad"})
    assert r3.status_code == 401
