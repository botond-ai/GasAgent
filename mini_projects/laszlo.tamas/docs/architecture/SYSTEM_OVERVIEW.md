# System Overview - Knowledge Router

## Mit csinál (felhasználói nézőpont)

Multi-tenant RAG (Retrieval-Augmented Generation) rendszer, amely vállalati tudásbázis kezelésre és intelligent chat assistant funkcióra szolgál. Tenant és user szintű elkülönítéssel, dokumentum feldolgozással, hibrid kereséssel és hosszútávú memória kezeléssel.

## Használat

### Core Use Cases
- **Document Q&A:** "Mi a szabadság policy a cégben?" → RAG search + kontextuális válasz
- **Multi-step Tasks:** "Keresd meg a Q3 sales reportot és készíts Excel summary-t" → Tool orchestration
- **External Data:** "Mi az időjárás Budapesten?" → External API integration
- **Memory Management:** "Jegyezd meg, hogy új lakásba költözöm" → Long-term memory storage

### API használat
```bash
curl -X POST "http://localhost:8000/api/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Milyen dokumentumok vannak feltöltve?",
    "user_context": {"tenant_id": 1, "user_id": 1}
  }'
```

### Frontend használat
- Real-time chat interface: http://localhost:3000
- Document upload panel
- Workflow execution tracking
- Debug panel fejlesztőknek

## Technikai működés

### 4-Rétegű Architektúra

```
┌─────────────────────────────────────────────┐
│              REASONING LAYER                │
│                                             │
│  ┌─────────────────┐ ┌─────────────────────┐ │
│  │  agent_decide   │ │  agent_finalize     │ │
│  │                 │ │                     │ │
│  │ • LLM planning  │ │ • Answer synthesis  │ │
│  │ • Tool selection│ │ • Source citations  │ │
│  │ • Multi-step    │ │ • Response format   │ │
│  │   reasoning     │ │ • Quality check     │ │
│  └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│             TOOL EXECUTION LAYER            │
│                                             │
│  ┌─────────────────┐ ┌─────────────────────┐ │
│  │ Knowledge Tools │ │ External APIs       │ │
│  │                 │ │                     │ │
│  │ • Vector search │ │ • Weather API       │ │
│  │ • Fulltext      │ │ • Currency API      │ │
│  │ • Doc listing   │ │ • GitHub API        │ │
│  │ • Embedding     │ │ • Excel MCP         │ │
│  └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│              OPERATIONAL LAYER              │
│                                             │
│  ┌─────────────────┐ ┌─────────────────────┐ │
│  │ Input/Output    │ │ State Management    │ │
│  │                 │ │                     │ │
│  │ • Validation    │ │ • Query rewrite     │ │
│  │ • Error handling│ │ • Context assembly  │ │
│  │ • Rate limiting │ │ • Cache control     │ │
│  │ • Security      │ │ • Flow control      │ │
│  └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│                MEMORY LAYER                 │
│                                             │
│  ┌─────────────────┐ ┌─────────────────────┐ │
│  │ Context System  │ │ LTM Management      │ │
│  │                 │ │                     │ │
│  │ • Tenant context│ │ • Consolidation     │ │
│  │ • User profile  │ │ • Explicit facts    │ │
│  │ • Chat history  │ │ • Session summaries │ │
│  │ • System prompt │ │ • Memory search     │ │
│  └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────┘
```

### LangGraph Workflow Flow

```
START
  ↓
┌─────────────────┐
│ validate_input  │ ← Input validation, state preparation
└─────────────────┘
  ↓
┌─────────────────┐
│ query_rewrite   │ ← Semantic expansion, intent classification
└─────────────────┘
  ↓
┌─────────────────┐┌─────────────────┐
│ fetch_tenant    ││ fetch_user      │ ← PARALLEL EXECUTION
└─────────────────┘└─────────────────┘
  ↓
┌─────────────────┐
│ fetch_history   │ ← Chat context loading
└─────────────────┘
  ↓
┌─────────────────┐
│build_prompt     │ ← System prompt assembly
└─────────────────┘
  ↓
┌─────────────────┐
│ agent_decide    │ ← LLM reasoning + tool selection
└─────────────────┘
  ↓
  ├─ tool_calls detected? ────┐
  │                           ↓
  │                    ┌─────────────────┐
  │                    │     tools       │ ← ToolNode parallel execution
  │                    │   (ToolNode)    │
  │                    └─────────────────┘
  │                           ↓
  │                    ┌─────────────────┐
  │                    │ agent_decide    │ ← LOOP: Multi-step reasoning
  │                    └─────────────────┘
  └─ no tools? ───────────────┐
                              ↓
                       ┌─────────────────┐
                       │ agent_finalize  │ ← Final answer synthesis
                       └─────────────────┘
                              ↓
                            END
```

### Tech Stack Core Components

**Backend Framework:**
- FastAPI 0.104.1 - Modern async API framework
- Uvicorn - ASGI server with hot reload
- Pydantic 2.7.4+ - Type validation and settings

**LLM & AI Stack:**
- OpenAI 1.54.0 - GPT-4 models (primary + light)
- LangChain Core 0.2.27+ - LLM abstraction layer
- LangGraph 0.2.0 - Workflow orchestration
- ToolNode pattern - Automatic tool execution

**Data Layer:**
- PostgreSQL 15 - Multi-tenant structured data
- Qdrant - Vector database for embeddings
- Tenant isolation - Row-level security patterns

**External Integrations:**
- MCP (Model Context Protocol) - Excel operations
- OpenMeteo - Weather API
- ExchangeRate API - Currency data
- GitHub API - Repository information

### Input/Output Flow

**Request Processing:**
```
HTTP Request → FastAPI → ChatState validation → LangGraph workflow execution → Response assembly
```

**State Management:**
```python
class ChatState(TypedDict):
    # Input
    query: str
    user_context: Dict[str, Any]
    session_id: Optional[str]
    
    # Processing
    query_rewritten: Optional[str]
    system_prompt: Optional[str] 
    chat_history: List[Dict]
    
    # Tool Execution
    messages: List[BaseMessage]  # LangGraph conversation
    tools_called: List[Dict]     # Tool invocation log
    
    # Output
    final_answer: Optional[str]
    sources: List[Dict]
    workflow_execution_id: Optional[str]
```

### Multi-Tenant Architecture

**Isolation Strategy:**
- Database level: tenant_id foreign keys on all tables
- API level: user_context validation in all endpoints  
- Workflow level: tenant context injection in system prompts
- Vector DB: Qdrant collections with tenant filtering

**Security Model:**
- No cross-tenant data access
- User-level permissions within tenants
- Private vs tenant-wide document visibility
- Rate limiting per tenant

## Függőségek

### Core Dependencies
- **Python 3.11+** - Runtime environment
- **PostgreSQL 15** - Primary database
- **Qdrant** - Vector database for RAG
- **OpenAI API** - LLM services (GPT-4, embeddings)

### Connected Services
- **Excel MCP Server** - Excel file operations
- **External APIs** - Weather, currency, GitHub
- **Frontend React App** - User interface
- **Prometheus** - Metrics collection (optional)
- **Grafana** - Monitoring dashboards (optional)

### Network Dependencies
- Internet access for OpenAI API calls
- Docker network for service communication
- WebSocket support for real-time frontend updates

## Konfiguráció

### Environment Variables (Critical)
```env
OPENAI_API_KEY=sk-...                     # Required
OPENAI_MODEL_PRIMARY=gpt-4o-2024-11-20   # Primary reasoning model
OPENAI_MODEL_LIGHT=gpt-4o-mini           # Fast operations model

POSTGRES_DB=k_r_                         # Database name
QDRANT_URL=http://qdrant:6333             # Vector DB connection
EXCEL_MCP_SERVER_URL=http://excel-mcp-server:8017  # MCP integration
```

### system.ini Feature Flags
```ini
[rag]
DEFAULT_SEARCH_MODE=hybrid               # hybrid|vector|keyword
DEFAULT_VECTOR_WEIGHT=0.7               # Vector search importance
DEFAULT_KEYWORD_WEIGHT=0.3              # Keyword search importance

[memory]
ENABLE_LONGTERM_CHAT_STORAGE=true       # Auto LTM creation
CONSOLIDATE_AFTER_MESSAGES=20           # LTM trigger threshold

[cache]
ENABLE_RESPONSE_CACHE=false             # Response caching
CACHE_TTL_SECONDS=3600                  # Cache lifetime
```

### Docker Compose Integration
```yaml
services:
  backend:
    depends_on: [postgres, qdrant, excel-mcp-server]
    environment:
      - POSTGRES_HOST=postgres
      - QDRANT_URL=http://qdrant:6333
    ports: ["8000:8000"]
    
  frontend:
    depends_on: [backend]
    ports: ["3000:3000"]
```

**Port mapping:**
- Backend API: 8000
- Frontend: 3000  
- PostgreSQL: 5432
- Qdrant HTTP: 6333, gRPC: 6334
- Excel MCP: 8017