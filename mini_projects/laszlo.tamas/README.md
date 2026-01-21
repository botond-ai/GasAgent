# Knowledge Router

> Multi-tenant RAG rendszer LangGraph workflow-val és real-time chat interface

## Gyors indítás

```bash
cp .env.example .env
# Állítsd be az OPENAI_API_KEY-t az .env fájlban
docker-compose up --build
```

**Hozzáférés:** http://localhost:3000 (Frontend) | http://localhost:8000/docs (API)

## Fő funkciók

- **Multi-tenant Chat** - Tenant és user szintű elkülönítés → [részletek](docs/features/chat-workflow.md)
- **Dokumentum feldolgozás** - Upload, chunking, RAG indexing → [részletek](docs/features/document-processing.md)
- **Hibrid keresés** - Vector + keyword search kombinációja → [részletek](docs/features/hybrid-search.md)
- **Hosszútávú memória** - User context + memory consolidation → [részletek](docs/features/memory-management.md)
- **Excel integráció** - MCP server Excel műveletek → [részletek](docs/features/excel-tools.md)
- **Külső API-k** - Időjárás, deviza, GitHub → [részletek](docs/features/external-apis.md)
- **Query optimalizáció** - Automatic query rewriting → [részletek](docs/features/query-optimization.md)
- **Workflow tracking** - Node-level execution monitoring → [részletek](docs/features/workflow-tracking.md)

## Architektúra

**4-rétegű LangGraph design:** Reasoning → Tool Execution → Operational → Memory
[Teljes architektúra →](docs/architecture/SYSTEM_OVERVIEW.md)

## API

- **Chat endpoint:** `POST /api/chat/`
- **Document upload:** `POST /api/workflows/document-processing`
- **Session management:** `/api/sessions/{id}/messages`
- **[Teljes API referencia →](docs/api/API_REFERENCE.md)**

## Konfiguráció

| Környezeti változó | Leírás |
|-------------------|--------|
| `OPENAI_API_KEY` | OpenAI API kulcs (kötelező) |
| `OPENAI_MODEL_HEAVY` | Heavy model - komplex reasoning, RAG szintézis |
| `OPENAI_MODEL_MEDIUM` | Medium model - standard RAG, kiegyensúlyozott |
| `OPENAI_MODEL_LIGHT` | Light model - routing, tool selection |
| `QDRANT_URL` | Vector database URL |
| `POSTGRES_DB` | PostgreSQL database név |

[Teljes konfigurációs útmutató →](docs/operations/DEPLOYMENT.md)