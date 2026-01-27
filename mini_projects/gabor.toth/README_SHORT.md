# 📖 RAG Agent - Quick Reference

**Production-ready RAG alkalmazás dokumentum-alapú AI asszisztenssel**

## ✅ Status

- **Tests**: ✅ 42/42 PASSING (100%)
- **Error Handling**: ✅ 5 patterns + 19 tests
- **Deployment**: ✅ Docker + local dev ready

---

## 🚀 Quick Start (2 perc)

### 1. Setup Environment
```bash
cd /Users/tothgabor/ai-agents-hu/mini_projects/gabor.toth
cp .env.example .env
# Add OPENAI_API_KEY to .env
```

### 2. Start Application
```bash
# Option A: Recommended (local dev)
source .env && ./start-dev.sh

# Option B: Docker
docker-compose up --build

# Frontend: http://localhost:5173
# Backend: http://localhost:8000
```

---

## 🎯 Core Features

| Feature | Description | Status |
|---------|-------------|--------|
| **📄 File Upload** | Markdown, TXT, PDF support with categories | ✅ |
| **🤖 AI Routing** | LLM-based category selection | ✅ |
| **🔍 RAG Search** | Vector + keyword (hybrid) search | ✅ |
| **💬 Chat** | Multi-turn with conversation history | ✅ |
| **📋 Activity Logger** | Real-time process tracking | ✅ |
| **💾 Persistence** | JSON-based user profiles & sessions | ✅ |
| **🔄 Error Recovery** | 5 resilience patterns | ✅ |

---

## 🔌 Main API Endpoints

### Chat & Files
```
POST   /api/chat              # Ask question
POST   /api/files/upload      # Upload document
GET    /api/activities        # Activity logs
```

### Admin
```
GET    /api/health            # Server status
POST   /api/cat-match         # Category detection
POST   /api/desc-save         # Save category description
GET    /api/dev-logs          # Feature tracking logs
```

---

## 📊 Test Coverage

```bash
# Run all 42 tests
python3 -m pytest backend/tests/test_working_agent.py -v

# Quick summary
python3 -m pytest backend/tests/test_working_agent.py --tb=no
```

**Breakdown:**
- Core Workflow: 23 tests ✅
- Conversation Cache: 7 tests ✅
- **Error Handling**: 19 tests ✅
  - Guardrail Node: 6
  - Fail-Safe Recovery: 4
  - Retry with Backoff: 5
  - Fallback Model: 1
  - Planner Fallback: 3

---

## 📁 Project Structure

```
gabor.toth/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt      # Python dependencies
│   ├── services/
│   │   ├── langgraph_workflow.py  # LangGraph (11 nodes)
│   │   └── chat_service.py        # Chat orchestration
│   ├── infrastructure/      # DB, embeddings, routing
│   ├── domain/              # SOLID interfaces
│   └── tests/
│       └── test_working_agent.py  # 42 comprehensive tests
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main component
│   │   ├── components/      # React components
│   │   └── api.ts           # HTTP client
│   └── package.json
│
├── data/
│   ├── users/               # User profiles (JSON)
│   ├── sessions/            # Chat history (JSON)
│   └── chroma_db/           # Vector database
│
└── DOCUMENTATION/
    ├── ERROR_HANDLING_*.md   # Error handling docs
    ├── QUICK_START.md
    └── FULL_README.md       # Complete documentation
```

---

## 🔧 Configuration

### Environment Variables
```bash
OPENAI_API_KEY=sk-...        # Required
DEVELOPMENT=true              # Optional
```

### Retrieval Thresholds
Edit `backend/services/langgraph_workflow.py`:
```python
SEMANTIC_THRESHOLD = 0.45     # Minimum semantic score
CONTENT_THRESHOLD = 150       # Minimum content length
```

---

## 🧠 How It Works

```
1. User asks question → Input validation
2. Category routing → LLM picks best category
3. Vector search → Find relevant chunks
4. Quality check → Verify search results
5. Reranking → LLM scores relevance
6. Hybrid search (optional) → Combine semantic + BM25
7. Answer generation → LLM creates response with citations
8. Checkpoint → Save workflow state
9. Return → Send answer + metadata to frontend
```

---

## 📊 Performance

- **Test Execution**: 1.21 seconds
- **Query Processing**: 150-450ms
- **Memory Usage**: ~120-160MB typical
- **Pass Rate**: 100% (42/42 tests)

---

## 🐛 Error Handling

Application implements 5 production-ready patterns:

1. **Guardrail Node** - Input validation & quality gates
2. **Fail-Safe Recovery** - Error detection & smart retry
3. **Retry with Backoff** - Exponential backoff (1s→2s→4s)
4. **Fallback Model** - Simplified answer generation
5. **Planner Fallback** - Search quality evaluation

See [ERROR_HANDLING_TESTS_SUMMARY.md](./DOCUMENTATION/ERROR_HANDLING_TESTS_SUMMARY.md) for details.

---

## 🚀 Deployment

### Docker Compose
```bash
docker-compose up --build
```

### Production Notes
- Requires OpenAI API key
- Uses ChromaDB for vector storage
- JSON-based persistence (no external DB needed)
- Supports horizontal scaling with shared data volume

---

## 📚 Documentation

- **[FULL_README.md](./FULL_README.md)** - Complete documentation
- **[QUICK_START.md](./QUICK_START.md)** - Feature guide
- **[LANGGRAPH_QUICKSTART.md](./LANGGRAPH_QUICKSTART.md)** - LangGraph 101
- **[ERROR_HANDLING_TESTS_SUMMARY.md](./DOCUMENTATION/ERROR_HANDLING_TESTS_SUMMARY.md)** - Error handling details

---

## ❓ Common Tasks

### Add New Document Category
```bash
# 1. Upload document with new category
# 2. LLM automatically detects and creates category
# 3. Start asking questions in that category
```

### Debug Chat Response
Check `rag_debug` field in API response:
- `retrieved` - Which chunks were used
- `debug_steps` - Workflow step timeline
- `api_info` - Performance metrics

### Check Server Health
```bash
curl http://localhost:8000/api/health
```

---

**Built with**: FastAPI • React • LangGraph • OpenAI • ChromaDB  
**Status**: Production-Ready ✅  
**Last Updated**: 2026-01-27
