# SupportAI - Ügyfélszolgálati Triage és Válaszoló Agent

**Projekt típus:** Tanfolyami projekt (RoboDreams "AI Agents" kurzus)
**Cél:** AI agent fejlesztési technikák elsajátítása gyakorlati projekten keresztül

## Projekt Áttekintés

A SupportAI egy mesterséges intelligencia alapú ügyfélszolgálati asszisztens, amely automatizálja a support ticketek feldolgozását. A projekt egy fiktív SaaS alkalmazás (TaskFlow - projektmenedzsment eszköz) ügyfélszolgálatát támogatja.

### Főbb Funkciók

| Funkció | Leírás |
|---------|--------|
| **Ticket Triage** | Automatikus kategorizálás, prioritás meghatározás |
| **RAG válaszgenerálás** | Tudásbázis alapú válaszok citációkkal |
| **Többnyelvű támogatás** | Bármilyen nyelvű ticketek kezelése, válasz az eredeti nyelven |
| **Jira integráció** | Webhook alapú automatizálás, kommentek visszaírása |
| **Policy Check** | Válaszok ellenőrzése céges szabályok alapján |
| **PII szűrés** | Személyes adatok felismerése és maszkolása |

## Tanulási Célok és Felhasznált Technikák

Ez a projekt a következő AI agent fejlesztési technikákat demonstrálja:

### 1. LangGraph Workflow Orchestráció

A ticket feldolgozás LangGraph StateGraph-ot használ:

```
Input → PII Filter → Analyze Ticket → [IP?] → Get Location → Get Holidays
                                         ↓                         ↓
                                    Calculate SLA ←────────────────┘
                                         ↓
                            Generate Customer Response → Output
```

**Tanulság:** A LangGraph lehetővé teszi komplex, elágazó workflow-k definiálását, ahol minden node független feladatot végez.

### 2. RAG (Retrieval-Augmented Generation)

A projekt teljes RAG pipeline-t implementál:

| Komponens | Technika | Fájl |
|-----------|----------|------|
| **Chunking** | RecursiveCharacterTextSplitter (600 token, 80 overlap) | `rag/chunker.py` |
| **Embedding** | OpenAI text-embedding-3-large | `rag/embeddings.py` |
| **Vector Store** | Qdrant (Docker) | `rag/vectorstore.py` |
| **Sparse Search** | BM25 kulcsszó alapú keresés | `rag/bm25.py` |
| **Hybrid Search** | RRF (Reciprocal Rank Fusion) - 0.5/0.5 súlyozás | `rag/hybrid_search.py` |
| **Reranking** | LLM-based újrarangsorolás | `rag/reranker.py` |
| **Query Expansion** | 3 keresési query generálása | `rag/query_expansion.py` |

**Tanulság:** A hybrid search (vector + BM25) és reranking jelentősen javítja a találati pontosságot.

### 3. Dokumentum Feldolgozás

A tudásbázis dokumentumok feldolgozása:

1. **Chunkolás** - Magyar nyelvű dokumentumok feldarabolása
2. **Fordítás** - Chunk-onként angol nyelvre fordítás (jobb embedding minőség)
3. **Kulcsszó kinyerés** - AI alapú keyword extraction
4. **Embedding** - OpenAI text-embedding-3-large
5. **Tárolás** - Qdrant vector database + BM25 index

### 4. Structured Output (Pydantic)

Az LLM válaszok validálása Pydantic modellekkel:

```python
class TicketAnalysis(BaseModel):
    language: str
    sentiment: Literal["frustrated", "neutral", "satisfied"]
    category: Literal["Billing", "Technical", "Account", "Feature Request", "General"]
    priority: Literal["P1", "P2", "P3", "P4"]
    confidence: float = Field(ge=0.0, le=1.0)

# Használat
analysis_llm = llm.with_structured_output(TicketAnalysis)
```

**Tanulság:** A structured output garantálja a válasz formátumát és csökkenti a parsing hibákat.

### 5. Memory és Session Kezelés

A memory komponensek teljes mértékben implementálva vannak (`backend/app/memory/`), de az agent workflow-ba való integráció még folyamatban van (TODO).

| Komponens | Leírás | Fájl |
|-----------|--------|------|
| **Session Store** | SQLite alapú perzisztencia (CRUD műveletek, üzenet tárolás) | `session_store.py` |
| **Rolling Summary** | N üzenetenként LLM-alapú összefoglalás készítés | `rolling_summary.py` |
| **PII Filter** | Email, telefon, bankkártya, adószám, IBAN maszkolás | `pii_filter.py` |

**Implementált PII típusok:**
- Email címek
- Magyar és nemzetközi telefonszámok
- Bankkártya számok
- Magyar adószámok
- Személyi igazolvány számok
- IBAN számlaszámok
- IP címek

### 6. Jira Service Management Integráció

A rendszer Jira webhook-on keresztül fogadja az új ticketeket:

1. **Webhook fogadás** → Ticket elemzés indítása
2. **AI elemzés** → Triage + válasz generálás
3. **Belső megjegyzés** → Részletes elemzés a support csapat számára
4. **Ügyfél válasz** → Ha confidence >= 85%, automatikus válasz
5. **Mezők frissítése** → Priority, Due Date, Labels

## Demó Alkalmazás: TaskFlow

A projekt egy fiktív TaskFlow nevű projektmenedzsment SaaS alkalmazás ügyfélszolgálatát szimulálja.

### Demó Dokumentumok (RAG Tudásbázis)

A `backend/data/demo_docs/` mappában magyar nyelvű dokumentumok találhatók a RAG teszteléséhez:

| Dokumentum | Leírás | Fájl |
|------------|--------|------|
| **ÁSZF** | Általános Szerződési Feltételek - előfizetések, díjak, felmondás | `aszf.md` |
| **FAQ** | Gyakran Ismételt Kérdések - általános használat | `faq.md` |
| **User Guide** | Felhasználói Útmutató - funkciók részletes leírása | `user_guide.md` |
| **Policy** | Támogatási Szabályzat - SLA, prioritások, csatornák | `policy.md` |

### Dokumentumok betöltése

```bash
cd backend
python scripts/ingest_documents.py
```

Ez a parancs:
- Beolvassa a demó dokumentumokat
- Chunk-okra bontja (600 token)
- Angolra fordítja (embedding-hez)
- Kulcsszavakat generál
- Qdrant-ba tölti

## Architektúra

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Chat UI    │  │  Admin UI   │  │  Document Management    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ /api/v1/chat│  │/api/v1/jira │  │   /api/v1/documents     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   SupportAI Agent (LangGraph)              │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │  │
│  │  │ Analyze  │→│   RAG    │→│ Generate │→│ Policy Check │  │  │
│  │  │ Ticket   │ │  Search  │ │ Response │ │              │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │  Qdrant  │   │  SQLite  │   │  OpenAI  │
        │ (Vector) │   │ (Memory) │   │   API    │
        └──────────┘   └──────────┘   └──────────┘
```

## Projekt Struktúra

```
hf_1/
├── backend/                        # FastAPI backend
│   ├── app/
│   │   ├── api/routes/            # API végpontok
│   │   │   ├── chat.py            # Chat endpoint
│   │   │   ├── jira.py            # Jira webhook
│   │   │   └── documents.py       # Dokumentum kezelés
│   │   ├── core/                  # LangGraph agent
│   │   │   ├── agent.py           # Fő agent osztály
│   │   │   ├── state.py           # Agent state definíció
│   │   │   └── prompts.py         # LLM promptok
│   │   ├── rag/                   # RAG komponensek
│   │   │   ├── chunker.py         # Dokumentum darabolás
│   │   │   ├── embeddings.py      # OpenAI embeddings
│   │   │   ├── vectorstore.py     # Qdrant integráció
│   │   │   ├── bm25.py            # Sparse retrieval
│   │   │   ├── hybrid_search.py   # RRF fusion
│   │   │   ├── reranker.py        # LLM reranking
│   │   │   └── query_expansion.py # Query bővítés
│   │   ├── memory/                # Session kezelés
│   │   │   ├── session_store.py   # SQLite perzisztencia
│   │   │   ├── rolling_summary.py # Összefoglaló generálás
│   │   │   └── pii_filter.py      # PII maszkolás
│   │   ├── integrations/          # Külső integrációk
│   │   │   └── jira_client.py     # Jira REST API kliens
│   │   ├── models/                # Pydantic modellek
│   │   └── tools/                 # LangChain tools
│   ├── data/demo_docs/            # Demó tudásbázis dokumentumok
│   ├── tests/                     # Pytest tesztek
│   └── scripts/                   # Segéd scriptek
├── frontend/                       # React + Vite + Tailwind
│   ├── src/
│   │   ├── components/chat/       # Chat komponensek
│   │   ├── pages/                 # Oldalak
│   │   ├── store/                 # Zustand state
│   │   └── services/              # API kliens
│   └── Dockerfile                 # Nginx production build
├── docker-compose.yml              # Multi-service setup
├── CLAUDE.md                       # Claude Code instrukciók
├── README.md                       # Ez a fájl
└── Tests.md                        # Teszt dokumentáció
```

## Telepítés és Futtatás

### Előfeltételek

- Docker és Docker Compose
- OpenAI API kulcs
- (Opcionális) Jira Cloud account webhook integrációhoz

### Docker Compose (Ajánlott)

```bash
# 1. Környezeti változók beállítása
cp backend/.env.example backend/.env
# Szerkeszd a .env fájlt és add meg az OPENAI_API_KEY-t

# 2. Szolgáltatások indítása
docker-compose up -d

# 3. Dokumentumok betöltése (első indításnál)
docker-compose exec backend python scripts/ingest_documents.py
```

A szolgáltatások:
- **Frontend:** http://localhost:3005
- **Backend API:** http://localhost:8000
- **Qdrant UI:** http://localhost:6333/dashboard

### Lokális Fejlesztés

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Használt API-k és Szolgáltatások

| Szolgáltatás | Cél | Megjegyzés |
|--------------|-----|------------|
| **OpenAI GPT-4** | LLM (elemzés, válasz generálás) | API kulcs szükséges |
| **OpenAI Embeddings** | text-embedding-3-large | API kulcs szükséges |
| **Qdrant** | Vector adatbázis | Docker (lokális) |
| **ip-api.com** | IP geolokáció | Ingyenes (45 req/min) |
| **Nager.Date** | Munkaszüneti napok | Ingyenes |
| **Jira Cloud** | Ticket kezelés | Opcionális |

## Jira Integráció Beállítása

### 1. Jira Webhook Konfiguráció

Jira Admin → System → Webhooks → Create webhook:
- **URL:** `https://your-domain/api/v1/jira/webhook`
- **Events:** Issue created, Issue updated
- **JQL filter (opcionális):** `project = SUPPORT`

### 2. Backend Konfiguráció (.env)

```env
JIRA_URL=https://your-domain.atlassian.net
JIRA_USER_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_WEBHOOK_SECRET=optional-secret
```

### 3. Tesztelés ngrok-kal

```bash
ngrok http 8000
# Használd az ngrok URL-t a Jira webhook-ban
```

## Output Példa

```json
{
  "session_id": "abc-123",
  "triage": {
    "category": "Technical",
    "subcategory": "Login Issue",
    "priority": "P2",
    "sla_hours": 8,
    "suggested_team": "IT Support",
    "sentiment": "frustrated",
    "language": "Hungarian",
    "confidence": 0.92
  },
  "answer_draft": {
    "greeting": "Kedves Kovács János!",
    "body": "Köszönjük megkeresését! A bejelentkezési problémával kapcsolatban...",
    "closing": "Üdvözlettel, TaskFlow Support",
    "tone": "empathetic_professional"
  },
  "citations": [
    {"id": 1, "doc_id": "KB-002", "title": "FAQ - Bejelentkezés", "score": 0.89}
  ],
  "policy_check": {
    "refund_promise": false,
    "sla_mentioned": true,
    "escalation_needed": false,
    "compliance": "passed"
  },
  "should_auto_respond": true
}
```

## Tesztelés

```bash
cd backend
pytest tests/ -v
```

Részletes teszt dokumentáció: [Tests.md](Tests.md)

## CI/CD (GitHub Actions)

A projekt tartalmaz GitHub Actions CI pipeline-t (`.github/workflows/ci.yml`).

### CI Pipeline Lépések

| Job | Leírás |
|-----|--------|
| **backend-tests** | Pytest tesztek futtatása coverage riporttal |
| **backend-lint** | Ruff linter kód minőség ellenőrzés |
| **frontend-build** | React/Vite build és TypeScript ellenőrzés |
| **docker-build** | Docker image-ek build tesztje |

### Indítás

A CI alapértelmezetten **nem fut automatikusan** push-ra (tanfolyami projekt). Indítási lehetőségek:

1. **Manuális indítás:** GitHub → Actions → CI Pipeline → "Run workflow"
2. **Pull Request:** Kommentezd be a `pull_request` triggert a ci.yml-ben

```yaml
# Manuális indítás engedélyezve
on:
  workflow_dispatch:

# Pull request trigger (opcionális)
# pull_request:
#   branches: [main]
```

## Technikák

| Technika | Implementáció | Leírás |
|----------|---------------|--------|
| **Hybrid Search** | `rag/hybrid_search.py` | BM25 + Vector, RRF fusion |
| **Reranking** | `rag/reranker.py` | LLM-based újrarangsorolás |
| **Query Expansion** | `rag/query_expansion.py` | 3 keresési query generálása |
| **Rolling Summary** | `memory/rolling_summary.py` | 10 üzenetenként összefoglalás |
| **PII Filtering** | `memory/pii_filter.py` | Email, telefon, bankkártya maszkolás |
| **Structured Output** | Pydantic modellek | Validált LLM kimenet |
| **Multilingual** | Bármilyen nyelv detektálása | Válasz az eredeti nyelven |
| **Confidence-based routing** | 85% threshold | Auto-respond vs manual review |

## Fejlesztési Tervek (Nem implementált)

A következő funkciók nincsenek még implementálva, mivel ez csak egy projektfeladat és ezeknek a megvalósítása és tesztelése sok időt venne igénybe, de a tervek szerint:

### Ticket Hasonlóság Keresés
- Hasonló korábbi ticketek keresése
- Megoldás javaslat korábbi esetek alapján
- Belső hivatkozások régi ticketekre

### Confluence/SharePoint Integráció
- Automatikus tudásbázis szinkronizálás
- Dokumentum verziókezelés

### Slack/Teams Integráció
- Real-time értesítések
- Eszkaláció workflow

### Analytics Dashboard
- Ticket statisztikák
- RAG találati pontosság mérése
- SLA compliance riportok

## Licensz

Ez a projekt oktatási célokat szolgál a RoboDreams AI Agents tanfolyam keretében.
