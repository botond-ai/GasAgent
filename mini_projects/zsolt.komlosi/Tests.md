# SupportAI - Teszt Dokumentáció

Ez a dokumentum részletesen bemutatja a SupportAI projekt tesztelési stratégiáját, a teszt struktúrát és a futtatási útmutatót.

## Teszt Áttekintés

A projekt pytest keretrendszert használ a teszteléshez. A tesztek három kategóriába sorolhatók:

| Kategória | Leírás | Mappa |
|-----------|--------|-------|
| **Unit tesztek** | Egyedi komponensek tesztelése izoláltan | `tests/unit/` |
| **Integrációs tesztek** | API végpontok és komponens együttműködés | `tests/integration/` |
| **E2E tesztek** | Teljes workflow tesztelés (tervezett) | `tests/e2e/` |

## Teszt Statisztika

```
Összes teszt: 142
├── Unit tesztek: 127
└── Integrációs tesztek: 15

Lefedettség: ~80% (core komponensek)
```

## Teszt Futtatás

### Összes teszt futtatása

```bash
cd backend
pytest tests/ -v
```

### Csak unit tesztek

```bash
pytest tests/unit/ -v
```

### Csak integrációs tesztek

```bash
pytest tests/integration/ -v
```

### Specifikus teszt fájl

```bash
pytest tests/unit/test_agent.py -v
```

### Coverage riport generálás

```bash
pytest tests/ --cov=app --cov-report=html
# Eredmény: htmlcov/index.html
```

## Teszt Fájlok Részletezése

### 1. `tests/unit/test_agent.py`

A SupportAIAgent osztály tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestSupportAIAgent` | 4 | Agent inicializálás, analyze metódus |
| `TestAgentNodes` | 3 | Egyedi node-ok működése |
| `TestAgentState` | 2 | State TypedDict validáció |

**Fontos tesztek:**

```python
def test_agent_initialization():
    """Ellenőrzi, hogy az agent megfelelően inicializálódik."""

def test_analyze_with_customer_name():
    """Ellenőrzi, hogy a customer_name átadódik az agent-nek."""

def test_should_get_location_with_ip():
    """Teszteli a conditional routing-ot IP cím alapján."""
```

### 2. `tests/unit/test_jira_routes.py`

A Jira webhook route logika tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestFormatCustomerResponse` | 4 | Ügyfél válasz formázás |
| `TestFormatInternalNote` | 6 | Belső megjegyzés formázás |
| `TestPriorityMapping` | 1 | Prioritás konverzió |
| `TestWebhookPayloadParsing` | 4 | Jira payload feldolgozás |
| `TestDueDateExtraction` | 3 | Határidő kinyerés |

**Fontos tesztek:**

```python
def test_format_customer_response_with_full_draft():
    """Ellenőrzi, hogy az ügyfél válasz megfelelően formázódik."""

def test_format_internal_note_high_confidence_recommendation():
    """Teszteli a magas confidence-nél az auto-respond javaslat megjelenését."""

def test_extract_reporter_name_display_name():
    """Ellenőrzi a reporter név kinyerését a Jira payload-ból."""
```

### 3. `tests/unit/test_chat_routes.py`

A chat API tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestChatRequest` | 5 | Request modell validáció |
| `TestChatResponse` | 2 | Response modell |
| `TestChatEndpoint` | 3 | Endpoint működés |
| `TestSessionHandling` | 2 | Session kezelés |

**Fontos tesztek:**

```python
def test_request_empty_message_fails():
    """Üres üzenet esetén ValidationError-t kell dobni."""

def test_chat_request_rejects_invalid_source():
    """Érvénytelen source értéket el kell utasítani."""
```

### 4. `tests/unit/test_document_routes.py`

A dokumentum kezelés tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestDocumentUploadRequest` | 6 | Upload request validáció |
| `TestDocumentUploadResponse` | 2 | Response modell |
| `TestDocumentListResponse` | 2 | Lista response |
| `TestDocumentProcessing` | 2 | Fájl típus detekció |
| `TestDocumentChunking` | 3 | Chunk ID formátum |
| `TestDocumentTranslation` | 2 | Fordítás logika |
| `TestKeywordExtraction` | 2 | Kulcsszó kinyerés |

### 5. `tests/unit/test_prompts.py`

Az LLM promptok tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestAnalysisPrompt` | 4 | Ticket elemzés prompt |
| `TestQueryExpansionPrompt` | 3 | Query bővítés prompt |
| `TestAnswerGenerationPrompt` | 3 | Válasz generálás prompt |
| `TestPolicyCheckPrompt` | 4 | Policy ellenőrzés prompt |
| `TestCustomerResponsePrompt` | 8 | Ügyfél válasz prompt |
| `TestRollingSummaryPrompt` | 3 | Összefoglaló prompt |
| `TestRerankingPrompt` | 4 | Reranking prompt |
| `TestPromptConsistency` | 2 | Általános prompt validáció |

**Fontos tesztek:**

```python
def test_prompt_instructs_same_language_response():
    """Ellenőrzi, hogy a prompt utasítja az LLM-et az eredeti nyelven válaszolni."""

def test_prompt_forbids_question_repetition():
    """Ellenőrzi, hogy a prompt tiltja a kérdés ismétlését."""

def test_prompt_can_be_formatted():
    """Teszteli, hogy a prompt összes placeholder-e kitölthető."""
```

### 6. `tests/unit/test_chunker.py`

A dokumentum darabolás tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestDocumentChunker` | 7 | Chunking logika |

**Fontos tesztek:**

```python
def test_chunk_document_creates_chunks():
    """Ellenőrzi, hogy a dokumentum megfelelően darabolódik."""

def test_token_count_respects_limit():
    """Teszteli a token limit betartását."""

def test_singleton_pattern():
    """Ellenőrzi a singleton pattern működését."""
```

### 7. `tests/unit/test_pii_filter.py`

A PII szűrés tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestPIIFilter` | 9 | PII detekció és maszkolás |

**Fontos tesztek:**

```python
def test_detect_email():
    """Email cím felismerés tesztelése."""

def test_detect_hungarian_phone():
    """Magyar telefonszám felismerés tesztelése."""

def test_detect_credit_card():
    """Bankkártya szám felismerés tesztelése."""

def test_filter_masks_all_pii():
    """Teljes PII maszkolás tesztelése."""
```

### 8. `tests/unit/test_models.py`

A Pydantic modellek tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestTicketAnalysis` | 5 | Ticket elemzés modell |
| `TestTriage` | 2 | Triage modell |
| `TestAnswerDraft` | 2 | Válasz draft modell |
| `TestCitation` | 2 | Citáció modell |
| `TestPolicyCheck` | 2 | Policy check modell |
| `TestPIIMatch` | 1 | PII match modell |
| `TestMessage` | 2 | Message modell |

### 9. `tests/unit/test_jira_client.py`

A Jira API kliens tesztelése.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestJiraIssue` | 2 | Issue dataclass |
| `TestJiraComment` | 1 | Comment dataclass |
| `TestJiraClient` | 5 | API kliens metódusok |
| `TestJiraTools` | 1 | LangChain tools |

### 10. `tests/integration/test_api_integration.py`

API integrációs tesztek.

| Teszt Osztály | Tesztek | Leírás |
|---------------|---------|--------|
| `TestHealthEndpoint` | 2 | Health check |
| `TestChatIntegration` | 2 | Chat API |
| `TestJiraWebhookIntegration` | 3 | Jira webhook |
| `TestDocumentIntegration` | 1 | Document API |
| `TestJiraStatusEndpoint` | 1 | Jira status |
| `TestErrorHandling` | 3 | Hibakezelés |

## Teszt Fixture-ök

A `tests/conftest.py` fájlban definiált közös fixture-ök:

```python
@pytest.fixture
def sample_ticket_text():
    """Minta magyar support ticket."""
    return "Nem tudok bejelentkezni a fiókba..."

@pytest.fixture
def sample_document_content():
    """Minta dokumentum tartalma."""
    return "# Bejelentkezési problémák megoldása..."

@pytest.fixture
def sample_pii_text():
    """PII-t tartalmazó minta szöveg."""
    return "Az e-mail címem kovacs.janos@example.com..."
```

## Mocking Stratégia

### OpenAI API Mock

```python
@patch("langchain_openai.ChatOpenAI")
def test_with_mocked_llm(mock_chat):
    mock_instance = MagicMock()
    mock_instance.invoke.return_value = MagicMock(content="Mocked response")
    mock_chat.return_value = mock_instance
```

### Qdrant Mock

```python
@patch("app.rag.vectorstore.QdrantClient")
def test_with_mocked_qdrant(mock_qdrant):
    mock_instance = MagicMock()
    mock_instance.search.return_value = []
    mock_qdrant.return_value = mock_instance
```

### FastAPI Dependency Override

```python
@pytest.fixture
def client(app, mock_settings):
    from app.config import get_settings
    app.dependency_overrides[get_settings] = lambda: mock_settings
    return TestClient(app)
```

## Környezeti Változók Teszteléshez

A `conftest.py` beállítja a teszt környezetet:

```python
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"
os.environ["DATABASE_URL"] = "sqlite:///./test_sessions.db"
os.environ["JIRA_WEBHOOK_SECRET"] = ""  # Disable webhook auth
```

## CI/CD Integráció

### GitHub Actions

A projekt tartalmaz teljes CI pipeline-t: `.github/workflows/ci.yml`

**Főbb jellemzők:**
- Manuális indítás (`workflow_dispatch`) - nem fut automatikusan push-ra
- Backend tesztek pytest-tel és coverage riporttal
- Ruff linter a kód minőség ellenőrzésére
- Frontend build ellenőrzés
- Docker image build teszt

**Indítás:** GitHub → Actions → CI Pipeline → "Run workflow"

```yaml
# A CI workflow vázlata
name: CI Pipeline

on:
  workflow_dispatch:  # Manuális indítás

jobs:
  backend-tests:      # pytest tests/ -v --cov=app
  backend-lint:       # ruff check app/
  frontend-build:     # npm run build
  docker-build:       # Docker image-ek build tesztje
```

## Manuális Tesztelési Útmutató

### 1. Chat API Tesztelés

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Nem tudok belépni a fiókomba", "source": "web"}'
```

### 2. Jira Webhook Tesztelés

```bash
curl -X POST http://localhost:8000/api/v1/jira/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "webhookEvent": "jira:issue_created",
    "issue": {
      "key": "TEST-123",
      "fields": {
        "summary": "Bejelentkezési probléma",
        "description": "Nem tudok belépni a fiókomba.",
        "reporter": {"displayName": "Teszt Felhasználó"}
      }
    }
  }'
```

### 3. Dokumentum Feltöltés Tesztelés

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@test_document.md" \
  -F "doc_type=faq"
```

## Demó Dokumentumok Tesztelése

A RAG funkciók teszteléséhez használhatod a `backend/data/demo_docs/` mappában található demó dokumentumokat:

| Dokumentum | Tartalom | Tesztelhető kérdések |
|------------|----------|---------------------|
| `aszf.md` | ÁSZF, előfizetések | "Mennyibe kerül a Pro csomag?" |
| `faq.md` | GYIK | "Hogyan változtatom meg a jelszavam?" |
| `user_guide.md` | Felhasználói útmutató | "Hogyan hozok létre új projektet?" |
| `policy.md` | Support policy | "Mi az SLA a P1 ticketekre?" |

### Dokumentumok betöltése

```bash
cd backend
python scripts/ingest_documents.py
```

## Ismert Limitációk

1. **E2E tesztek hiányoznak** - A teljes workflow tesztelés még nincs implementálva
2. **OpenAI API mock** - A tesztek nem használnak valódi OpenAI API-t
3. **Qdrant mock** - A vector search tesztek mock-olt adatokkal működnek
4. **Jira mock** - A Jira integráció tesztek nem csatlakoznak valódi Jira-hoz

## Tervezett Fejlesztések

- [ ] E2E tesztek implementálása
- [ ] Performance tesztek (load testing)
- [ ] RAG minőség tesztek (relevancia mérés)
- [ ] Multilingual tesztek bővítése
- [ ] Automatikus coverage riport CI-ban
