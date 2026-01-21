# Database Schema - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A Knowledge Router PostgreSQL adatbázis sémája teljes multi-tenant izolációt biztosít minden tábla szintjén. Támogatja a real-time chat, dokumentum kezelést, hosszútávú memória tárolást és workflow execution tracking-et.

## Használat

### Adatbázis kapcsolat
```python
# Backend connection
from database.pg_connection import get_db_connection
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tenants WHERE is_active = true")
```

### Multi-tenant query patterns
```sql
-- Tenant-specific queries ALWAYS include tenant_id
SELECT * FROM documents WHERE tenant_id = %s AND visibility = 'tenant';

-- User-specific private data
SELECT * FROM documents WHERE tenant_id = %s AND user_id = %s AND visibility = 'private';
```

### Seeded test data használat
```json
{
  "tenant_id": 1,  // ACME Corporation
  "user_id": 1     // Alice Johnson (Hungarian, timezone: Europe/Budapest)
}
```

## Technikai implementáció

### Core Tables - Multi-Tenant Foundation

#### tenants table
```sql
CREATE TABLE tenants (
    tenant_id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,              -- URL-safe identifier
    name TEXT NOT NULL,                    -- Display name
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    system_prompt TEXT,                    -- Tenant-specific AI prompt
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Purpose:** Root isolation boundary
**Seed data:**
- tenant_id=1, key='acme-corp', name='ACME Corporation'

#### users table
```sql
CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,             -- Multi-tenant FK
    firstname TEXT NOT NULL,
    lastname TEXT NOT NULL,
    nickname TEXT NOT NULL,                -- Unique display name
    email TEXT NOT NULL,
    role TEXT NOT NULL,                    -- 'developer', 'manager', etc.
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    default_lang TEXT NOT NULL DEFAULT 'en', -- 'en', 'hu'
    system_prompt TEXT,                    -- User-specific AI prompt
    default_location TEXT,                 -- For weather queries
    timezone TEXT,                         -- e.g., 'Europe/Budapest'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_users_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenants (tenant_id) 
        ON DELETE CASCADE
);
```

**Purpose:** User management with tenant isolation
**Key features:**
- Hierarchical prompts (tenant + user system_prompt)
- Timezone support for LLM context
- Language preferences

**Seed data:**
- user_id=1: Alice Johnson (Hungarian, Budapest timezone)
- user_id=2: Bob Smith (English, New York timezone)

### Chat & Session Management

#### chat_sessions table
```sql
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,                   -- UUID for security
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,                  -- Session termination
    processed_for_ltm BOOLEAN NOT NULL DEFAULT FALSE, -- LTM consolidation flag
    title TEXT,                            -- Auto-generated or user-set
    last_message_at TIMESTAMPTZ,           -- Activity tracking
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE, -- Soft delete
    
    CONSTRAINT fk_chat_sessions_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenants (tenant_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_chat_sessions_user 
        FOREIGN KEY (user_id) 
        REFERENCES users (user_id) 
        ON DELETE CASCADE
);
```

**Purpose:** Chat conversation boundaries
**Lifecycle:**
1. Created on first message
2. Auto-ended after inactivity or explicit close
3. LTM processing triggered when ended
4. Soft delete for data retention

#### chat_messages table  
```sql
CREATE TABLE chat_messages (
    message_id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,             -- Denormalized for performance
    session_id UUID NOT NULL,
    user_id BIGINT NOT NULL,               -- Denormalized for performance  
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT NULL,           -- LLM costs, model info, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_chat_messages_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenants (tenant_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_chat_messages_session 
        FOREIGN KEY (session_id) 
        REFERENCES chat_sessions (id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_chat_messages_user 
        FOREIGN KEY (user_id) 
        REFERENCES users (user_id) 
        ON DELETE CASCADE
);
```

**Purpose:** Complete chat message log
**Metadata examples:**
```json
{
  "llm_model": "gpt-4o-2024-11-20",
  "tokens_used": 245,
  "estimated_cost_usd": 0.00123,
  "workflow_path": "RAG",
  "sources_used": [{"doc_id": 15, "title": "Policy Manual"}]
}
```

### Document Management & RAG

#### documents table
```sql
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT,                        -- NULL for tenant-wide docs
    visibility TEXT NOT NULL CHECK (visibility IN ('private', 'tenant')),
    source TEXT NOT NULL,                  -- 'upload', 'api', 'scrape'
    title TEXT,
    content TEXT NOT NULL,                 -- Full document text
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_documents_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenants (tenant_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_documents_user 
        FOREIGN KEY (user_id) 
        REFERENCES users (user_id) 
        ON DELETE SET NULL,
        
    -- Visibility business rule enforcement
    CONSTRAINT documents_visibility_user_check 
        CHECK (
            (visibility = 'private' AND user_id IS NOT NULL) OR
            (visibility = 'tenant' AND user_id IS NULL)
        )
);
```

**Purpose:** Document storage with access control
**Visibility rules:**
- `private`: user_id required, only accessible to that user
- `tenant`: user_id must be NULL, accessible to all tenant users

#### document_chunks table
```sql
CREATE TABLE document_chunks (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,             -- Denormalized for performance
    document_id BIGINT NOT NULL,
    chunk_index INTEGER NOT NULL,          -- 0, 1, 2, ...
    start_offset INTEGER NOT NULL,         -- Character position in doc
    end_offset INTEGER NOT NULL,           -- Character position in doc
    content TEXT NOT NULL,                 -- Actual chunk text
    source_title TEXT,                     -- Document title (denormalized)
    chapter_name TEXT,                     -- Table of contents extraction
    page_start INTEGER,                    -- PDF page reference
    page_end INTEGER,                      -- PDF page reference
    section_level INTEGER,                 -- Heading hierarchy (1=chapter, 2=section)
    qdrant_point_id UUID,                  -- Vector DB reference
    embedded_at TIMESTAMPTZ,               -- Embedding timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_chunks_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenants (tenant_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_chunks_document 
        FOREIGN KEY (document_id) 
        REFERENCES documents (id) 
        ON DELETE CASCADE,
    CONSTRAINT uq_document_chunk 
        UNIQUE (document_id, chunk_index)   -- Prevent duplicate chunks
);

-- Full-text search index (Hungarian language support)
CREATE INDEX idx_document_chunks_content_fts
ON document_chunks
USING GIN (to_tsvector('hungarian', content));

-- TOC-based querying indexes
CREATE INDEX idx_document_chunks_chapter 
ON document_chunks(document_id, chapter_name);

CREATE INDEX idx_document_chunks_pages 
ON document_chunks(document_id, page_start, page_end);
```

**Purpose:** RAG chunk storage with metadata
**Key features:**
- Heuristic chunking (chapters, sections, pages)
- Full-text search in Hungarian
- Vector embeddings stored in Qdrant
- Source attribution for citations

### Long-Term Memory System

#### long_term_memories table
```sql
CREATE TABLE long_term_memories (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,               -- User-specific memories
    source_session_id UUID,                -- Optional session reference
    content TEXT NOT NULL,                 -- Memory text content
    memory_type TEXT CHECK (memory_type IN ('session_summary', 'explicit_fact')),
    qdrant_point_id UUID,                  -- Vector embedding reference
    embedded_at TIMESTAMPTZ,               -- Embedding creation time
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_ltm_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenants (tenant_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_ltm_user 
        FOREIGN KEY (user_id) 
        REFERENCES users (user_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_ltm_session 
        FOREIGN KEY (source_session_id) 
        REFERENCES chat_sessions (id) 
        ON DELETE SET NULL
);

-- Query optimization indexes
CREATE INDEX idx_ltm_user_type ON long_term_memories(user_id, memory_type);
CREATE INDEX idx_ltm_tenant_type ON long_term_memories(tenant_id, memory_type);
```

**Purpose:** User long-term memory storage
**Memory types:**
- `session_summary`: Auto-generated chat summaries
- `explicit_fact`: User-requested "jegyezd meg" facts

**Lifecycle:**
1. Creation: Manual (explicit) or automatic (session consolidation)
2. Embedding: Content vectorized and stored in Qdrant
3. Retrieval: Semantic search during chat workflows

### Workflow Execution Tracking

#### workflow_executions table
```sql
CREATE TABLE workflow_executions (
    execution_id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    
    -- Input tracking
    query TEXT NOT NULL,                   -- Original user query
    query_rewritten TEXT,                  -- LLM-optimized query
    query_intent TEXT,                     -- Classified intent
    
    -- Execution timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'error', 'timeout')),
    
    -- Output tracking  
    final_answer TEXT,
    error_message TEXT,
    
    -- Metrics
    total_nodes_executed INTEGER DEFAULT 0,
    iteration_count INTEGER DEFAULT 0,      -- Agent decision loops
    reflection_count INTEGER DEFAULT 0,     -- Quality check iterations
    tools_called JSONB,                    -- Tool invocation log
    llm_tokens_total INTEGER,              -- Token usage tracking
    llm_cost_usd DECIMAL(10,6),            -- Cost tracking
    
    -- Correlation
    request_id TEXT,                       -- HTTP request correlation
    trace_id TEXT,                         -- Distributed tracing
    final_state JSONB,                     -- Complete workflow state
    
    CONSTRAINT fk_workflow_session 
        FOREIGN KEY (session_id) 
        REFERENCES chat_sessions (id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_workflow_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenants (tenant_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_workflow_user 
        FOREIGN KEY (user_id) 
        REFERENCES users (user_id) 
        ON DELETE CASCADE
);
```

**Purpose:** Complete workflow execution audit trail
**Analytics use cases:**
- Performance monitoring
- Cost tracking
- Error analysis
- User behavior insights

#### node_executions table
```sql
CREATE TABLE node_executions (
    node_execution_id BIGSERIAL PRIMARY KEY,
    execution_id UUID NOT NULL,
    node_name TEXT NOT NULL,               -- e.g., 'agent_decide', 'tools'
    node_index INTEGER NOT NULL,          -- Execution order (0, 1, 2, ...)
    
    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms FLOAT,
    status TEXT NOT NULL CHECK (status IN ('success', 'error', 'skipped')),
    error_message TEXT,
    
    -- State tracking
    state_before JSONB,                    -- ChatState before node execution
    state_after JSONB,                     -- ChatState after node execution
    state_diff JSONB,                      -- Computed state changes
    
    -- Node-specific metadata
    metadata JSONB,                        -- Tool results, LLM responses, etc.
    parent_node TEXT,                      -- For tool child nodes (parent: "tools")
    
    CONSTRAINT fk_node_execution 
        FOREIGN KEY (execution_id) 
        REFERENCES workflow_executions (execution_id) 
        ON DELETE CASCADE
);
```

**Purpose:** Node-level execution debugging
**Key features:**
- Complete state snapshots before/after each node
- Tool execution results in metadata
- Parent-child relationships for complex tools

### Auxiliary Tables

#### user_prompt_cache table
```sql
CREATE TABLE user_prompt_cache (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    cached_prompt TEXT NOT NULL,           -- Hierarchical prompt (tenant + user)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_prompt_cache_user 
        FOREIGN KEY (user_id) 
        REFERENCES users (user_id) 
        ON DELETE CASCADE
);
```

**Purpose:** Performance optimization for system prompt assembly

## Funkció-specifikus konfiguráció

### Multi-Tenant Isolation Patterns

**Query patterns (enforced in application layer):**
```sql
-- ALWAYS include tenant_id in WHERE clauses
SELECT * FROM chat_messages 
WHERE tenant_id = %s AND session_id = %s;

-- Cross-tenant queries FORBIDDEN
-- This would violate isolation:
SELECT * FROM documents WHERE user_id = %s; -- Missing tenant_id!
```

**Database-level isolation:** 
- Row Level Security (RLS) could be added for extra protection
- Currently enforced at application layer for performance

### Performance Optimization

**Indexes for common queries:**
```sql
-- Chat history fetching
CREATE INDEX idx_chat_messages_session_created 
ON chat_messages(session_id, created_at);

-- Document search
CREATE INDEX idx_documents_tenant_visibility 
ON documents(tenant_id, visibility);

-- Workflow analytics  
CREATE INDEX idx_workflow_executions_tenant_started 
ON workflow_executions(tenant_id, started_at);
```

**Query optimization:**
- Denormalized tenant_id in child tables
- JSONB indexes on metadata fields
- GIN indexes for full-text search

### Migration Strategy

**Migration files:** `backend/database/migrations/`
```
001_initial_schema.sql           # Base tables
002_add_explicit_memory_type.sql # LTM memory_type column
003_add_workflow_tracking.sql    # Workflow execution tables
004_add_node_execution.sql       # Node-level tracking
005_add_user_timezone.sql        # User timezone support
006_add_document_toc_indexes.sql # TOC-based searching
```

**Fresh deployment:**
```python
from database.pg_init import init_postgres_schema, seed_default_data
init_postgres_schema()  # Creates all tables
seed_default_data()     # Inserts test tenants/users
```

**Data retention policies:**
- Chat messages: Indefinite (or configurable)
- Workflow executions: 90 days (configurable)
- Node executions: 30 days (configurable)
- Long-term memories: Indefinite (user-controlled)