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
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   React UI  │────▶│  FastAPI     │────▶│  LangGraph  │
│  (Vite)     │◀────│  Backend     │◀────│  Workflow   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                      │
                           ▼                      ▼
                    ┌─────────────┐        ┌──────────┐
                    │   Qdrant    │        │  Redis   │
                    │  (Vectors)  │        │ (Cache)  │
                    └─────────────┘        └──────────┘
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
supai4/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers
│   │   ├── core/             # Configuration & logging
│   │   ├── models/           # Pydantic schemas
│   │   ├── services/         # Qdrant, Redis, RAG
│   │   ├── workflows/        # LangGraph nodes & graph
│   │   └── main.py           # Application entry point
│   ├── tests/                # pytest tests
│   └── requirements.txt      # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── api/              # API client
│   │   ├── components/       # React components
│   │   ├── hooks/            # Custom React hooks
│   │   ├── styles/           # CSS stylesheets
│   │   ├── types/            # TypeScript types
│   │   ├── App.tsx           # Main component
│   │   └── main.tsx          # Entry point
│   ├── package.json          # Node dependencies
│   └── vite.config.ts        # Vite configuration
│
├── docker/
│   ├── Dockerfile.backend    # Backend container
│   └── Dockerfile.frontend   # Frontend container
│
├── docker-compose.yml        # Service orchestration
└── .env.example              # Environment template
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

```
┌──────────────┐
│ detect_intent│
└──────┬───────┘
       ▼
┌──────────────────┐
│ triage_classify  │
└──────┬───────────┘
       ▼
┌──────────────────┐
│ expand_queries   │
└──────┬───────────┘
       ▼
┌──────────────────┐
│ search_rag       │
└──────┬───────────┘
       ▼
┌──────────────────┐
│ rerank_docs      │
└──────┬───────────┘
       ▼
┌──────────────────┐
│ draft_answer     │
└──────┬───────────┘
       ▼
┌──────────────────┐
│ check_policy     │
└──────┬───────────┘
       ▼
┌──────────────────┐
│ validate_output  │
└──────────────────┘
```

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
**Last Updated:** 2026-01-22
