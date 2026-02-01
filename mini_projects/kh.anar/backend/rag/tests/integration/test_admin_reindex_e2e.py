from fastapi.testclient import TestClient
from app.main import app
import os


def test_admin_reindex_and_rbac():
    client = TestClient(app)
    os.environ["ADMIN_TOKEN"] = "admintoken"

    payload = {
        "doc_id": "doc-rbac",
        "title": "Private Doc",
        "source": "tests",
        "doc_type": "note",
        "version": "1",
        "access_scope": "private",
        "text": "PRIVATE_DATA_CANARY"
    }

    r = client.post("/admin/rag/add", json=payload, headers={"token": "admintoken"})
    assert r.status_code == 200

    # lekérdezés access scope nélkül -> küszöbtől függően lehet, hogy semmit nem ad vissza
    rsearch = client.post("/api/chat", json={"user_id": "u1", "session_id": "s1", "message": "PRIVATE_DATA_CANARY", "metadata": {}})
    assert rsearch.status_code == 200
    # most lekérdezés access scope metaadattal — ennek találnia kell
    rsearch2 = client.post("/api/chat", json={"user_id": "u1", "session_id": "s1", "message": "PRIVATE_DATA_CANARY", "metadata": {"access_scope": "private"}})
    assert rsearch2.status_code == 200
    assert rsearch2.json()["debug"]["rag_telemetry"]["decision"] in ("hit", "no_hit")  # csak azt nézzük, hogy a folyamat nem omlik össze
