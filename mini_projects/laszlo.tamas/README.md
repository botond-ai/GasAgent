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

- **Multi-tenant Chat** - Tenant és user szintű elkülönítés → [részletek](docs/features/CHAT_WORKFLOW.md)
- **Dokumentum feldolgozás** - Upload, chunking, RAG indexing → [részletek](docs/features/DOCUMENT_PROCESSING.md)
- **RAG keresés** - Semantic search + citations → [részletek](docs/features/RAG_SEARCH.md)
- **Hosszútávú memória** - User context + memory consolidation → [részletek](docs/features/LONG_TERM_MEMORY.md)
- **Multi-tenancy** - Tenant isolation + security → [részletek](docs/features/MULTI_TENANCY.md)
- **Query optimalizáció** - Automatic query rewriting → [részletek](docs/features/QUERY_PROCESSING.md)
- **Workflow tracking** - Node-level execution monitoring → [részletek](docs/features/WORKFLOW_TRACKING.md)
- **Error handling** - Graceful degradation + retry → [részletek](docs/features/ERROR_HANDLING.md)

## Architektúra

**4-rétegű LangGraph design:** Reasoning → Tool Execution → Operational → Memory

- [Teljes rendszer áttekintés](docs/architecture/SYSTEM_OVERVIEW.md)
- [Database schema](docs/architecture/DATABASE_SCHEMA.md)
- [Workflow diagram](docs/architecture/WORKFLOW_DIAGRAM.md)
- [Node referencia](docs/architecture/NODE_REFERENCE.md)

## API

- **Chat endpoint:** `POST /api/chat/`
- **Document upload:** `POST /api/workflows/document-processing`
- **Session management:** `/api/sessions/{id}/messages`
- **[Teljes API referencia](docs/api/API_REFERENCE.md)**
- **[API endpoints részletesen](docs/features/API_ENDPOINTS.md)**

## Konfiguráció

| Környezeti változó | Leírás |
|-------------------|--------|
| `OPENAI_API_KEY` | OpenAI API kulcs (kötelező) |
| `OPENAI_MODEL_HEAVY` | Heavy model - komplex reasoning, RAG szintézis |
| `OPENAI_MODEL_MEDIUM` | Medium model - standard RAG, kiegyensúlyozott |
| `OPENAI_MODEL_LIGHT` | Light model - routing, tool selection |
| `QDRANT_URL` | Vector database URL |
| `POSTGRES_DB` | PostgreSQL database név |

[Részletes konfiguráció →](docs/features/CONFIGURATION.md)

## Dokumentáció

- **[Teljes dokumentációs index](docs/index.md)** - Minden dokumentum egy helyen
- **[Deployment útmutató](docs/operations/DEPLOYMENT.md)** - Production telepítés
- **[Testing stratégia](docs/operations/TESTING.md)** - Unit és integrációs tesztek
- **[Troubleshooting](docs/operations/TROUBLESHOOTING.md)** - Hibakeresési útmutató

## Observability

- **[Prometheus](docs/observability/PROMETHEUS.md)** - Metrics collection
- **[Grafana](docs/observability/GRAFANA.md)** - Dashboard visualization
- **[Loki](docs/observability/LOKI.md)** - Structured logging
- **[Tempo](docs/observability/TEMPO.md)** - Distributed tracing