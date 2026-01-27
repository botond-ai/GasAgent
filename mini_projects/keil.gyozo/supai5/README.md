# SupportAI v2.0

AI-powered Customer Support Triage & Response System

## 🎯 Overview

SupportAI is a production-grade customer support platform that automatically:

- **Detects intent & sentiment** from customer messages
- **Classifies and triages** tickets (category, priority, SLA, team)
- **Generates AI draft responses** using RAG pipeline
- **Validates policy compliance** before sending
- **Provides citations** from knowledge base

## 🏗️ Architecture

```
┌─────────────────────┐     ┌──────────────┐     ┌────────────────────────────────┐
│   React UI          │────▶│  FastAPI     │────▶│  LangGraph State Machine        │
│  (Vite)             │◀────│  Backend     │◀────│  (Async LLM Nodes)             │
└─────────────────────┘     └──────────────┘     └────────────────────────────────┘
                                   │                           │
                                   ▼                           ▼
                           ┌──────────────────┐      ┌──────────────────────┐
                           │  Services Layer  │      │  External APIs       │
                           ├──────────────────┤      ├──────────────────────┤
                           │ RAG Service      │      │ OpenAI (Embeddings,  │
                           │ Cohere API       │      │ LLM)                 │
                           │ FleetDM API      │      │ Cohere (Reranker)    │
                           └──────────────────┘      │ FleetDM Device Info  │
                                   │                 └──────────────────────┘
        ┌────────────────────────┬─┴────────────────────────┐
        ▼                        ▼                          ▼
   ┌─────────────┐          ┌─────────────┐          ┌──────────┐
   │   Qdrant    │          │    Redis    │          │ OpenAI   │
   │  (Vectors)  │          │   (Cache)   │          │   API    │
   └─────────────┘          └─────────────┘          └──────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- OpenAI API key
- (Optional) Cohere API key for reranking

### 1. Environment Setup

```powershell
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
notepad .env
```

### 2. Start Services

```powershell
# Start all services
docker compose up -d

# View logs
docker logs supportai-backend -f
docker logs supportai-qdrant -f
```

### 3. Access Applications

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |

### 4. Health Check

```powershell
# Check service health
curl http://localhost:8000/health
```

## 📦 Project Structure

```
supai5/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers (/api/tickets, /health)
│   │   ├── core/             # Configuration & logging
│   │   ├── infrastructure/    # External API clients (Cohere, FleetDM)
│   │   ├── models/           # Pydantic schemas & response models
│   │   ├── prompts/          # LLM prompt templates
│   │   ├── services/         # RAG, Qdrant, Redis services
│   │   ├── workflows/        # LangGraph nodes & state graph
│   │   │   ├── graph.py      # Workflow definition & routing
│   │   │   └── nodes.py      # LLM nodes & service nodes
│   │   └── main.py           # Application entry point
│   ├── tests/                # pytest test suite
│   ├── data/                 # Runtime data (logs, caches)
│   ├── pytest.ini            # Pytest configuration
│   └── requirements.txt      # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── api/              # API client hooks
│   │   ├── components/       # React components (Chat, Ticket, etc)
│   │   ├── hooks/            # Custom React hooks
│   │   ├── pages/            # Page components
│   │   ├── styles/           # CSS stylesheets
│   │   ├── types/            # TypeScript types & interfaces
│   │   ├── App.tsx           # Main app component
│   │   └── main.tsx          # React entry point
│   ├── index.html            # HTML template
│   ├── package.json          # Node dependencies
│   ├── tsconfig.json         # TypeScript configuration
│   ├── vite.config.ts        # Vite build configuration
│   └── vite-env.d.ts         # Vite type definitions
│
├── docker/
│   ├── Dockerfile.backend    # Backend container image
│   └── Dockerfile.frontend   # Frontend container image
│
├── fleetapi/                 # FleetDM integration utilities
├── docker-compose.yml        # Service orchestration
├── .env.example              # Environment template
└── data/                     # Persistent data storage
    ├── sessions/             # Conversation history (JSON)
    └── files/                # Agent-generated files
```

## 🔧 Technology Stack

### Backend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | FastAPI | 0.115.0+ |
| LLM Orchestration | LangChain + LangGraph | 0.3+ |
| Vector DB | Qdrant | 1.15.3 |
| Cache | Redis | 7-alpine |
| Embeddings | OpenAI text-embedding-3-large | - |
| LLM | GPT-4o / Claude 3.5 Sonnet | - |
| Reranker | Cohere Rerank v3 | - |

### Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | React | 18.3+ |
| Language | TypeScript | 5.5+ |
| Build Tool | Vite | 5.3+ |
| HTTP Client | Axios | 1.7+ |
| Styling | Custom CSS | - |

## 🔄 LangGraph Workflow

The workflow processes support tickets through 11 nodes with conditional routing:

```
                    ┌──────────────────────────┐
                    │ detect_intent            │  (Intent & sentiment)
                    └──────────────┬───────────┘
                                   ▼
                    ┌──────────────────────────┐
                    │ triage_classify          │  (Category, priority, SLA)
                    └──────────────┬───────────┘
                                   ▼
                    ┌──────────────────────────────────────┐
                    │ should_lookup_device? (conditional)  │
                    └─────────┬──────────────────────┬─────┘
              Yes (technical) │                      │ No
                              ▼                      ▼
                   ┌────────────────────┐  ┌──────────────────┐
                   │ fleet_lookup       │  │ expand_queries   │
                   │ (FleetDM Device)   │  │ (Generate search)│
                   └──────────┬─────────┘  └────────┬─────────┘
                              │                     │
                              └──────────┬──────────┘
                                         ▼
                    ┌──────────────────────────┐
                    │ expand_queries           │  (Generate queries)
                    └──────────────┬───────────┘
                                   ▼
                    ┌──────────────────────────┐
                    │ search_rag               │  (Vector + BM25 search)
                    └──────────────┬───────────┘
                                   ▼
                    ┌──────────────────────────┐
                    │ rerank_docs              │  (Cohere reranker)
                    └──────────────┬───────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │ check_rag_results? (cond.)  │
                    └─────────┬──────────────┬─────┘
                   Has docs  │              │ No docs
                             ▼              ▼
                   ┌──────────────────┐  ┌────────────────────┐
                   │ draft_answer     │  │ fallback_answer    │
                   │ (RAG-based)      │  │ (Generic response) │
                   └────────┬─────────┘  └──────────┬─────────┘
                            │                       │
                            └──────────┬────────────┘
                                       ▼
                    ┌──────────────────────────┐
                    │ check_policy             │  (Compliance validation)
                    └──────────────┬───────────┘
                                   ▼
                    ┌──────────────────────────┐
                    │ validate_output          │  (Schema validation)
                    └──────────────┬───────────┘
                                   ▼
                                ┌──────┐
                                │ END  │
                                └──────┘

                    ┌──────────────────────────┐
                    │ handle_error (error path)│  (Error recovery)
                    └──────────────┬───────────┘
                                   ▼
                                ┌──────┐
                                │ END  │
                                └──────┘
```

### Node Implementation Details

| Node | Type | LLM Call | Purpose |
|------|------|----------|---------|
| `detect_intent` | LLM Node | ✓ | Structured output (problem_type, sentiment) |
| `triage_classify` | LLM Node | ✓ | Structured output (category, priority, SLA, team) |
| `fleet_lookup` | Service Node | - | Call FleetDM API for device context |
| `expand_queries` | LLM Node | ✓ | Generate 3-5 search queries |
| `search_rag` | Service Node | - | Qdrant vector + BM25 hybrid search |
| `rerank_docs` | Service Node | - | Cohere reranking of retrieved documents |
| `draft_answer` | LLM Node | ✓ | RAG-based answer with citations |
| `fallback_answer` | LLM Node | ✓ | Generic response when no RAG results |
| `check_policy` | LLM Node | ✓ | Policy compliance validation (structured output) |
| `validate_output` | Service Node | - | JSON schema validation |
| `handle_error` | Service Node | - | Generate error response |

**Key Features:**
- **Conditional Routing:** FleetDM lookup only for technical issues
- **RAG Fallback:** If no documents found, uses fallback answer generator
- **Error Handling:** Separate error path with recovery mechanism
- **Structured Outputs:** LLM nodes use Pydantic models for consistent responses

## 🔑 API Endpoints

### Tickets

- `POST /api/tickets/` - Create new ticket
- `GET /api/tickets/` - List tickets
- `GET /api/tickets/{id}` - Get ticket details
- `POST /api/tickets/{id}/process` - Process ticket with AI
- `DELETE /api/tickets/{id}` - Delete ticket

### Health

- `GET /health` - Health check with service status
- `GET /ready` - Readiness probe
- `GET /live` - Liveness probe

## 🧪 Testing

```powershell
# Run backend tests
docker exec supportai-backend pytest tests/ -v

# Run with coverage
docker exec supportai-backend pytest tests/ --cov=app --cov-report=html
```

## 🛠️ Development

### Backend Development

```powershell
# Install dependencies locally
cd backend
pip install -r requirements.txt

# Run with hot reload
uvicorn app.main:app --reload

# Format code
black app/
ruff check app/
```

### Frontend Development

```powershell
# Install dependencies
cd frontend
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

## 📊 Business Metrics

| Metric | Baseline | Target | Current |
|--------|----------|--------|---------|
| Manual triage time | - | -40% | - |
| SLA compliance | 85% | 95% | - |
| AI draft acceptance | N/A | 70%+ | - |
| Response time | 2-4h | <10min | - |

## 🐛 Troubleshooting

### Qdrant Unhealthy

```powershell
# Full reset
docker compose down -v
docker volume rm supportai_qdrant_storage
docker compose up --build
```

### Frontend Build Errors

Check that all required files exist:
- `frontend/src/styles/components.css`
- `frontend/package-lock.json`
- All TypeScript config files

### Backend API 404

Verify:
- API prefix is `/api/`
- Router registration in `main.py`
- Check Swagger UI: http://localhost:8000/docs

### Redis Connection Issues

```powershell
# Check Redis health
docker exec supportai-redis redis-cli ping
# Should return: PONG
```

## 📝 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `COHERE_API_KEY` | No | - | Cohere API key for reranking |
| `LLM_MODEL` | No | gpt-4o | LLM model name |
| `EMBEDDING_MODEL` | No | text-embedding-3-large | Embedding model |
| `QDRANT_HOST` | No | qdrant | Qdrant hostname |
| `REDIS_HOST` | No | redis | Redis hostname |
| `SCORE_THRESHOLD` | No | 0.7 | Minimum relevance score |
| `TOP_K_RETRIEVAL` | No | 10 | Documents to retrieve |
| `TOP_K_RERANK` | No | 5 | Documents after reranking |

## 🔒 Security Considerations

- API keys stored in environment variables (never commit `.env`)
- CORS configured for production domains
- Input validation with Pydantic
- Policy compliance checks before sending responses
- XSS protection headers in nginx

## 📖 Further Reading

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [React Documentation](https://react.dev/)

## 📄 License

Proprietary - All rights reserved

## 🤝 Contributing

This is an internal project. For questions or issues, contact the development team.

---

**Version:** 2.0.0
**Last Updated:** 2026-01-27
