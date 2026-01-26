# Skipped Tests Documentation

## Summary
- **Total skipped:** 11 tests
- **Passing tests:** 163 (with OpenAI enabled)
- **Policy:** All skips are intentional and documented

---

## 1. Hiányzó API Endpointok (5 tests)

### test_api_endpoints.py

**test_create_session**
- **Skip:** `POST /api/sessions/` endpoint nem létezik
- **Miért:** Sessions automatikusan jönnek létre workflow futáskor

**test_get_session**
- **Skip:** `GET /api/sessions/{id}` endpoint nem létezik
- **Miért:** Használd: `GET /api/sessions/{id}/messages`

**test_get_message_history**
- **Skip:** `GET /api/messages/` endpoint nem létezik
- **Miért:** Használd: `GET /api/sessions/{id}/messages`

**test_invalid_session_id**
- **Skip:** Validáció nem tesztelhető
- **Miért:** GET /sessions/{id} nem létezik

**test_missing_required_params**
- **Skip:** Validáció nem tesztelhető
- **Miért:** POST /sessions/ nem létezik

---

## 2. Mock Workflow Tesztek (4 tests)

### test_chat_workflow.py

**test_workflow_with_mocked_openai**
- **Skip:** Mock workflow tesztelés nem implementált
- **Miért:** Komplex DI setup + valós OpenAI tesztek működnek

**test_intent_routing_mocked** (3 parameterized)
- **Skip:** Mock intent routing nem implementált
- **Miért:** Komplex LangGraph state mock + valós tesztek működnek
- **Paraméterek:**
  - `"hello"` → CHAT
  - `"keress dokumentumban"` → RAG
  - `"listázd a fájlokat"` → LIST

---

## 3. Költséges OpenAI Teszt (1 test)

### test_sessions_crud.py

**test_consolidate_session_memory**
- **Skip:** LTM konsolidáció drága OpenAI hívás
- **Miért:** Explicit kérésre futtatandó (nem CI része)
- **Költség:** ~$0.01-0.05 / futtatás

---

## 4. Elavult Mock Embedding (1 test)

### test_document_rag.py (integration)

**test_generate_embedding_mocked**
- **Skip:** OpenAI SDK v1+ API változás
- **Miért:** Régi mock formátum + valós embedding teszt működik
- **Alternatíva:** `test_generate_embedding_real` (OpenAI marker)

---

## Policy

- ❌ **Ne enable-d:** API endpoint teszteket (endpointok nem léteznek)
- ⚠️ **Opcionális:** Mock teszteket (valós tesztek lefedik)
- 💰 **Explicit:** Költséges teszteket (csak ha szükséges)
- ♻️ **Refactor:** Elavult mock-okat (ha szükséges)
