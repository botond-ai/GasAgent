# Knowledge Router - Technical Blueprint

## 1. Rendszer célja

Multi-tenant RAG (Retrieval-Augmented Generation) rendszer LangGraph workflow orchestrációval és real-time chat interface-szel. Vállalati tudásbázis kezelés tenant és user szintű elkülönítéssel, dokumentum feldolgozással, hibrid kereséssel és hosszútávú memória kezeléssel.

**Target audience:** Enterprise teams, multi-user környezetek
**Use case:** Tudásbázis chat assistant + document Q&A + external tool integration

## 2. Tech Stack

### Backend Core
```
Python 3.11+
FastAPI 0.104.1
uvicorn[standard] 0.24.0
pydantic >=2.7.4
pydantic-settings >=2.0.0
```

### LLM & AI
```
openai 1.54.0
langchain-core >=0.2.27,<0.3.0
langchain-openai >=0.1.0
langchain-text-splitters >=0.2.0
langgraph 0.2.0
```

### Database & Storage
```
PostgreSQL 15-alpine (k_r_ database)
psycopg2-binary 2.9.9
Qdrant latest (vector database)
qdrant-client 1.7.0
```

### Document Processing
```
pypdf 5.1.0
PyMuPDF 1.23.8
chardet 5.2.0
```

### Observability
```
prometheus_client >=0.19.0
opentelemetry-api 1.21.0
opentelemetry-sdk 1.21.0
opentelemetry-exporter-otlp 1.21.0
```

### Frontend
```
React with TypeScript
Real-time WebSocket communication
```

### Infrastructure
```
Docker Compose multi-service
Excel MCP Server (Python 3.11-slim)
```

## 3. Architektúra

### 3.1 Rétegek (4-Layer Architecture)

```
┌─────────────────────────────────────────────┐
│              REASONING LAYER                │
│  ┌─────────────────┐ ┌─────────────────────┐ │
│  │  agent_decide   │ │  agent_finalize     │ │
│  │  (LLM planning) │ │  (answer synthesis) │ │
│  └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│             TOOL EXECUTION LAYER            │
│  ┌─────────────────┐ ┌─────────────────────┐ │
│  │ ToolNode        │ │ External APIs       │ │
│  │ (knowledge_tools│ │ (weather, currency, │ │
│  │  excel_tools)   │ │  github, mcp)       │ │
│  └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│              OPERATIONAL LAYER              │
│  ┌─────────────────┐ ┌─────────────────────┐ │
│  │ validate_input  │ │ query_rewrite       │ │
│  │ error_handling  │ │ state_management    │ │
│  └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│                MEMORY LAYER                 │
│  ┌─────────────────┐ ┌─────────────────────┐ │
│  │ Context Fetching│ │ LTM Management      │ │
│  │ (tenant, user,  │ │ (consolidation,     │ │
│  │  chat history)  │ │  explicit facts)    │ │
│  └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 3.2 LangGraph Workflow

```
START
  ↓
validate_input (input validation, state prep)
  ↓  
query_rewrite (semantic expansion, intent classification)
  ↓
fetch_tenant (tenant context + system prompt)
  ↓
fetch_user (user context + preferences + timezone)
  ↓
fetch_chat_history (conversation context)
  ↓
build_system_prompt (hierarchical prompt assembly)
  ↓
agent_decide (LLM reasoning + tool selection)
  ↓
  ├─ tool_calls? → tools (ToolNode parallel execution)
  │                  ↓
  │                agent_decide (loop - multi-step reasoning)
  └─ no tools? → agent_finalize → END
```

### 3.3 Database Schema

```sql
-- Multi-tenant isolation
CREATE TABLE tenants (
    tenant_id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    system_prompt TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users with tenant association
CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    firstname TEXT NOT NULL,
    lastname TEXT NOT NULL,
    nickname TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    default_lang TEXT NOT NULL DEFAULT 'en',
    system_prompt TEXT,
    default_location TEXT,
    timezone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_users_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    processed_for_ltm BOOLEAN NOT NULL DEFAULT FALSE,
    title TEXT,
    last_message_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_chat_sessions_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_sessions_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- Chat messages with metadata
CREATE TABLE chat_messages (
    message_id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    session_id UUID NOT NULL,
    user_id BIGINT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chat_messages_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_messages_session FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_messages_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- Long-term memories
CREATE TABLE long_term_memories (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    source_session_id UUID,
    content TEXT NOT NULL,
    memory_type TEXT CHECK (memory_type IN ('session_summary', 'explicit_fact')),
    qdrant_point_id UUID,
    embedded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_ltm_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    CONSTRAINT fk_ltm_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_ltm_session FOREIGN KEY (source_session_id) REFERENCES chat_sessions (id) ON DELETE SET NULL
);

-- Documents with visibility control
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT,
    visibility TEXT NOT NULL CHECK (visibility IN ('private', 'tenant')),
    source TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_documents_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    CONSTRAINT fk_documents_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL,
    CONSTRAINT documents_visibility_user_check CHECK (
        (visibility = 'private' AND user_id IS NOT NULL) OR
        (visibility = 'tenant' AND user_id IS NULL)
    )
);

-- Document chunks for RAG
CREATE TABLE document_chunks (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    document_id BIGINT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_title TEXT,
    chapter_name TEXT,
    page_start INTEGER,
    page_end INTEGER,
    section_level INTEGER,
    qdrant_point_id UUID,
    embedded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chunks_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    CONSTRAINT fk_chunks_document FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
    CONSTRAINT uq_document_chunk UNIQUE (document_id, chunk_index)
);

-- Workflow execution tracking
CREATE TABLE workflow_executions (
    execution_id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    query TEXT NOT NULL,
    query_rewritten TEXT,
    query_intent TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'error', 'timeout')),
    final_answer TEXT,
    error_message TEXT,
    total_nodes_executed INTEGER DEFAULT 0,
    iteration_count INTEGER DEFAULT 0,
    reflection_count INTEGER DEFAULT 0,
    tools_called JSONB,
    llm_tokens_total INTEGER,
    llm_cost_usd DECIMAL(10,6),
    request_id TEXT,
    trace_id TEXT,
    final_state JSONB,
    CONSTRAINT fk_workflow_session FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE,
    CONSTRAINT fk_workflow_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    CONSTRAINT fk_workflow_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- Node execution tracking
CREATE TABLE node_executions (
    node_execution_id BIGSERIAL PRIMARY KEY,
    execution_id UUID NOT NULL,
    node_name TEXT NOT NULL,
    node_index INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms FLOAT,
    status TEXT NOT NULL CHECK (status IN ('success', 'error', 'skipped')),
    error_message TEXT,
    state_before JSONB,
    state_after JSONB,
    state_diff JSONB,
    metadata JSONB,
    parent_node TEXT,
    CONSTRAINT fk_node_execution FOREIGN KEY (execution_id) REFERENCES workflow_executions (execution_id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ltm_user_type ON long_term_memories(user_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_ltm_tenant_type ON long_term_memories(tenant_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_fts ON document_chunks USING GIN (to_tsvector('hungarian', content));
CREATE INDEX IF NOT EXISTS idx_document_chunks_chapter ON document_chunks(document_id, chapter_name);
CREATE INDEX IF NOT EXISTS idx_document_chunks_pages ON document_chunks(document_id, page_start, page_end);
```

## 4. Workflow Node Catalog

### 4.1 Operational Layer Nodes

**validate_input_node**
- **Felelősség:** Input paraméter validáció
- **Input:** query, session_id, user_context (tenant_id, user_id)
- **Output:** Validated ChatState vagy error
- **Parallel:** Nem

**query_rewrite_node** 
- **Felelősség:** Query semantic expansion, intent classification
- **Input:** Original user query
- **Output:** Rewritten query + intent metadata
- **LLM:** Light model (from OPENAI_MODEL_LIGHT, temperature: 0.3, structured output)
- **Cache:** LLM query cache enabled
- **Parallel:** Nem

**handle_errors_node**
- **Felelősség:** Error recovery, fallback response generation
- **Input:** Error state + context
- **Output:** User-friendly error message
- **Parallel:** Nem

### 4.2 Memory Layer Nodes

**fetch_tenant_context_node**
- **Felelősség:** Tenant system prompt + configuration loading
- **Input:** tenant_id
- **Output:** Tenant context in state
- **Database:** tenants table query
- **Parallel:** Igen (with fetch_user_context_node)

**fetch_user_context_node**
- **Felelősség:** User preferences, timezone, system prompt loading
- **Input:** user_id, tenant_id
- **Output:** User context + preferences in state
- **Database:** users table query  
- **Parallel:** Igen (with fetch_tenant_context_node)

**fetch_chat_history_node**
- **Felelősség:** Recent conversation history loading (last 10 messages)
- **Input:** session_id, tenant_id, user_id
- **Output:** Chat history in state
- **Database:** chat_messages table query with limit
- **Parallel:** Nem (runs after context nodes)

**build_system_prompt_node**
- **Felelősség:** Hierarchical prompt assembly (default + tenant + user)
- **Input:** All context from previous nodes
- **Output:** Final system prompt in state
- **Cache:** User prompt cache table
- **Parallel:** Nem

### 4.3 Reasoning Layer Nodes

**agent_decide_node**
- **Felelősség:** LLM reasoning, tool selection, multi-step planning
- **Input:** Complete state with context + history
- **Output:** AIMessage with tool_calls vagy final answer decision
- **LLM:** Heavy model (from OPENAI_MODEL_HEAVY, temperature: 0.7)
- **Tools Available:** knowledge tools, external APIs, Excel tools
- **Loop:** Igen - can execute multiple times per workflow
- **Parallel:** Nem

**agent_finalize_node**
- **Felelősség:** Final answer synthesis from tool results + conversation
- **Input:** State with tool execution results
- **Output:** Final user response + sources
- **LLM:** Heavy model (from OPENAI_MODEL_HEAVY, temperature: 0.5, focused on synthesis)
- **Parallel:** Nem

### 4.4 Tool Execution Layer

**ToolNode (LangChain built-in)**
- **Felelősség:** Parallel tool execution based on agent_decide tool_calls
- **Input:** AIMessage.tool_calls from agent_decide
- **Output:** ToolMessage observations
- **Tools:**
  - **Knowledge Tools:** generate_embedding, search_vectors, search_fulltext, list_documents
  - **External APIs:** get_weather, get_currency_rate  
  - **Excel Tools:** create_excel_workbook, write_excel_data, read_excel_data, create_excel_chart, format_excel_range, create_excel_worksheet, get_excel_metadata
- **Parallel:** Igen (automatic parallel execution)
- **Pattern:** tool_calls → parallel execution → ToolMessage results

## 5. API Endpoints

### 5.1 Chat Endpoints

```http
POST /api/chat/
Content-Type: application/json

{
  "query": "string",
  "user_context": {
    "tenant_id": 1,
    "user_id": 1
  },
  "session_id": "uuid" // optional, auto-generated if missing
}

Response:
{
  "answer": "string",
  "sources": [{"title": "string", "content": "string"}],
  "session_id": "uuid",
  "workflow_execution_id": "uuid"
}
```

### 5.2 Document Processing

```http
POST /api/workflows/document-processing
Content-Type: multipart/form-data

tenant_id: integer
user_id: integer  
visibility: "private" | "tenant"
file: file (PDF, TXT)

Response:
{
  "document_id": integer,
  "chunks_created": integer,
  "status": "success" | "error"
}
```

### 5.3 Session Management

```http
GET /api/sessions/{session_id}/messages
Authentication: Bearer token

Response:
{
  "messages": [
    {
      "message_id": integer,
      "role": "user" | "assistant",
      "content": "string",
      "created_at": "timestamp"
    }
  ]
}
```

### 5.4 Workflow Tracking

```http
GET /api/workflows/{execution_id}/nodes
Response:
{
  "execution_id": "uuid",
  "nodes": [
    {
      "node_name": "string", 
      "duration_ms": float,
      "status": "success" | "error",
      "state_before": object,
      "state_after": object
    }
  ]
}
```

## 6. Configuration (Environment Variables)

### 6.1 Core Configuration

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-...                           # Required
OPENAI_MODEL_HEAVY=gpt-4.1                      # Heavy model: complex reasoning, RAG synthesis
OPENAI_MODEL_MEDIUM=gpt-4o                      # Medium model: standard RAG, balanced
OPENAI_MODEL_LIGHT=gpt-3.5-turbo                # Light model: routing, tool selection
OPENAI_MODEL_EMBEDDING=text-embedding-3-large   # Embeddings

# Database Configuration  
POSTGRES_DB=k_r_                               # Database name
POSTGRES_USER=postgres                          # DB user
POSTGRES_PASSWORD=postgres                      # DB password
POSTGRES_HOST=postgres                          # Docker service
POSTGRES_PORT=5432                             # Internal port
POSTGRES_EXTERNAL_PORT=5432                    # External port

# Vector Database
QDRANT_URL=http://qdrant:6333                  # Internal URL
QDRANT_HTTP_EXTERNAL_PORT=6333                 # External HTTP
QDRANT_GRPC_EXTERNAL_PORT=6334                 # External gRPC

# MCP Server Integration
EXCEL_MCP_SERVER_URL=http://excel-mcp-server:8017  # Excel tools
```

### 6.2 Feature Flags (system.ini)

```ini
[application]
DEFAULT_LANGUAGE=en
MAX_CONTEXT_TOKENS=8000

[llm]
CHAT_TEMPERATURE=0.7
CHAT_MAX_TOKENS=500
EMBEDDING_BATCH_SIZE=100

[chunking]
CHUNKING_STRATEGY=recursive
CHUNK_SIZE_TOKENS=500
CHUNK_OVERLAP_TOKENS=50

[retrieval]  
TOP_K_DOCUMENTS=5
SIMILARITY_METRIC=cosine
MIN_SCORE_THRESHOLD=0.7

[rag]
DEFAULT_SEARCH_MODE=hybrid
DEFAULT_VECTOR_WEIGHT=0.7
DEFAULT_KEYWORD_WEIGHT=0.3

[memory]
ENABLE_LONGTERM_CHAT_STORAGE=true
ENABLE_LONGTERM_CHAT_RETRIEVAL=true
CHAT_SUMMARY_MAX_TOKENS=200
CONSOLIDATE_AFTER_MESSAGES=20

[rate_limiting]
REQUESTS_PER_MINUTE=60
MAX_CONCURRENT_REQUESTS=10

[cache]
ENABLE_RESPONSE_CACHE=false
CACHE_TTL_SECONDS=3600

[logging]
LOG_LLM_REQUESTS=true
LOG_VECTOR_SEARCHES=true
LOG_EMBEDDING_OPERATIONS=true
```

## 7. Docker Infrastructure

### 7.1 docker-compose.yml Services

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-k_r_}
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "${POSTGRES_EXTERNAL_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]

  qdrant:
    image: qdrant/qdrant:latest  
    ports:
      - "${QDRANT_HTTP_EXTERNAL_PORT:-6333}:6333"
      - "${QDRANT_GRPC_EXTERNAL_PORT:-6334}:6334"
    volumes:
      - qdrant_storage:/qdrant/storage

  excel-mcp-server:
    image: python:3.11-slim
    environment:
      - EXCEL_FILES_PATH=/app/excel_files
      - FASTMCP_PORT=8017
    volumes:
      - ./data/excel_files:/app/excel_files
    ports:
      - "8017:8017"

  backend:
    build: ./backend
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - POSTGRES_HOST=postgres
      - QDRANT_URL=http://qdrant:6333
      - EXCEL_MCP_SERVER_URL=http://excel-mcp-server:8017
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - qdrant
      - excel-mcp-server

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

### 7.2 Volume Strategy

- **postgres_data:** PostgreSQL data persistence
- **qdrant_storage:** Vector database persistence  
- **./data/excel_files:** Excel file sharing between host and MCP server
- **Hot reload:** Backend code volume mount for development

## 8. Seeded Data & Testing

### 8.1 Default Test Data

```sql
-- Tenants
INSERT INTO tenants (tenant_id, key, name, system_prompt) VALUES
(1, 'acme-corp', 'ACME Corporation', 'You are a helpful AI assistant for ACME Corporation.');

-- Users  
INSERT INTO users (user_id, tenant_id, firstname, lastname, nickname, email, role, default_lang, timezone) VALUES
(1, 1, 'Alice', 'Johnson', 'alice_j', 'alice@acme.com', 'developer', 'hu', 'Europe/Budapest'),
(2, 1, 'Bob', 'Smith', 'bob_s', 'bob@acme.com', 'manager', 'en', 'America/New_York');
```

### 8.2 Recommended Test Parameters

```json
{
  "tenant_id": 1,
  "user_id": 1,
  "session_id": "auto-generated-uuid"
}
```

## 9. Migration Strategy

### 9.1 Database Migrations

Migrations located in `backend/database/migrations/`:
```
001_initial_schema.sql
002_add_explicit_memory_type.sql  
003_add_workflow_tracking_tables.sql
004_add_node_execution_tracking.sql
005_add_user_timezone_fields.sql
006_add_document_toc_indexes.sql
```

### 9.2 Fresh Build Verification

```bash
docker-compose down -v
docker-compose up --build
```

**Startup Sequence:**
1. PostgreSQL health check
2. Qdrant startup
3. Excel MCP server ready
4. Backend migration execution
5. Schema initialization + seeding
6. Frontend build + connection

## 10. Observability & Monitoring

### 10.1 Prometheus Metrics

- `workflow_execution_duration_seconds`
- `workflow_node_success_total`
- `workflow_node_error_total`
- `llm_request_duration_seconds`
- `llm_token_usage_total`
- `llm_cost_usd_total`

### 10.2 OpenTelemetry Tracing

- Request correlation via trace_id
- Node-level span tracking
- LLM call instrumentation
- External API call tracing

### 10.3 Structured Logging

JSON format with correlation IDs, user context, and performance metrics.

---

**Created:** 2026-01-21  
**Author:** GitHub Copilot  
**Version:** 1.0  
**Last Updated:** Knowledge Router PROD Implementation