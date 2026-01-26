# KnowledgeRouter - Feature List

**Version:** 2.12.0 (STRICT_RAG_MODE Feature)  
**Last Updated:** 2026-01-23  
**Breaking Changes:** 
- Removed Anthropic/Claude support - OpenAI only
- **LangChain with_structured_output() replaced with manual JSON parsing** (critical bugfix)

---

## 🐛 CRITICAL BUGFIXES (v2.9.0 - 2026-01-21)

### LangChain Structured Output Bug
- **Issue**: `with_structured_output()` returned empty dicts `{}` for all Pydantic models
- **Impact**: 6 nodes broken (intent_detection, plan, tool_selection, observation, generation x2)
- **Fix**: Manual JSON text parsing with regex extraction from LLM responses
- **Pattern**: Prompt + JSON format instruction → Extract ```json...``` or raw {...} → json.loads()

### LangGraph State Management Violations
- **Issue #1**: Decision functions mutating state (FORBIDDEN) → GraphRecursionError
- **Issue #2**: Node name "observation" conflicted with state field → Renamed to "observation_check"
- **Issue #3**: `state.get("replan_count", 0)` returning None → Changed to `or 0` (None-safe)

### Recursion Limit
- **Issue**: Default limit (25) too low for replanning workflows
- **Fix**: Increased to 50 in `ainvoke(config={"recursion_limit": 50})`

### IT Domain UX
- **Issue**: Jira ticket question not always appended (LLM-dependent)
- **Fix**: Automatic append after answer generation (guaranteed)

**See**: [házi feladatok/3.md](./házi%20feladatok/3.md#kritikus-bugfixek-2026-01-21) for full technical details.

---

## ✅ Implemented Features

### 🛡️ Quality Assurance - Response Validation & Retry Logic (NEW in v2.5)

#### Guardrail Node (Citation Validation)

#### Error Detection Capabilities

#### Test Coverage
  - IT/non-IT domain handling
  - Retry logic progression
  - Edge cases (empty citations, multiple references)
 - **Integration Ready**: Integrated into 7-node LangGraph pipeline (with memory_update)


### 📈 Telemetry & Metrics (NEW in v2.5)

#### Feedback Metrics Node
- **Latency Tracking**: End-to-end pipeline `total_latency_ms` and LLM latency
- **Retrieval Quality**: Top-1 similarity score, citation count
- **Token Estimates**: Prompt and response token estimates for budget control
- **Cache Flags**: Embedding and query cache hit indicators (placeholders)
- **Non-Blocking**: Metrics collection never blocks the workflow
- **State Integration**: Metrics exposed in API response for frontend debug panel

---

### 🧠 Memory (NEW in v2.6)

#### Memory Update Node
- **Rolling Window**: Keeps last `N` messages (default `8`) to control context size
- **SHA256 Deduplication**: Removes duplicate messages (role + normalized content)
- **Conversation Summary**: 3–4 sentence LLM summary updated as needed
- **Known Facts**: Extracts up to 5 atomic facts (short bullets) for future turns
- **Prompt Integration**: Summary + facts added to generation prompt to steer answers
- **RAG Query Rewrite**: Augments retrieval query with up to 3 facts for better recall
- **Non-Blocking**: Any LLM errors in memory stage are logged and ignored
- **Config**: `MEMORY_MAX_MESSAGES=8`

#### Tests
- backend/tests/test_memory.py: Rolling window, summary/facts extraction, non-blocking behavior
- Integration suite updated to pass with 7-node pipeline

---

### 🤖 LLM Provider

- **Provider**: OpenAI GPT-4o Mini (gpt-4o-mini)
- **Embedding**: text-embedding-3-small (1536 dimensions)
- **Config**: OPENAI_API_KEY, OPENAI_MODEL in .env
- **Factory**: OpenAIClientFactory (singleton pattern)
- **Docs**: Installation and README updated with OpenAI setup

---

### 📊 Prometheus + Grafana Monitoring & Loki Logging

**Monitoring (v2.11):** Prometheus + Grafana metrics  
**Logging (v2.12):** Loki + Promtail structured JSON logs

#### Real-Time Metrics Collection
- **11 Metric Types**:
  - `knowledgerouter_requests_total` - Counter (by domain, status, pipeline_mode)
  - `knowledgerouter_latency_seconds` - Histogram (p50/p95/p99 latency)
  - `knowledgerouter_llm_calls_total` - Counter (by model, status, purpose)
  - `knowledgerouter_llm_latency_seconds` - Histogram (LLM call latency)
  - `knowledgerouter_cache_hits_total` - Counter (by cache_type)
  - `knowledgerouter_cache_misses_total` - Counter (by cache_type)
  - `knowledgerouter_errors_total` - Counter (by error_type, component)
  - `knowledgerouter_tool_executions_total` - Counter (by tool_name, status)
  - `knowledgerouter_rag_latency_seconds` - Histogram (RAG retrieval time)
  - `knowledgerouter_active_requests` - Gauge (concurrent requests)
  - `knowledgerouter_replan_loops_total` - Counter (by reason, domain)

#### API Endpoint
- **GET /api/metrics/** - Prometheus text format endpoint
- **Auto-scraped**: Prometheus scrapes every 15 seconds
- **Format**: Standard Prometheus exposition format

#### Grafana Dashboards
- **KnowledgeRouter Monitoring** - Main dashboard
  - Request Rate (by domain)
  - Latency percentiles (p50/p95/p99)
  - LLM Call Rate (by model)
  - Cache Hit Rate
  - Active Requests (real-time)
  - Error Rate (by type)
- **Access**: http://localhost:3001 (admin/admin)
- **Datasources**: Prometheus (metrics) + Loki (logs)
- **Auto-provisioned**: Datasources + dashboard on startup
- **Log Exploration**: Explore → Loki → `{container="knowledgerouter_backend"}`

#### Debug Panel Integration
- **📊 Monitoring Stats** section in debug panel
- **Auto-refresh**: Every 10 seconds
- **Metrics displayed**:
  - Total Requests
  - Cache Hit Rate (%)
  - Avg Latency (ms)
  - LLM Calls
  - Active Requests (real-time)
  - Error Count
- **Manual refresh**: 🔄 Refresh Stats button

#### Tests
- **backend/tests/test_monitoring.py**: 22 tests (86% coverage)
  - MetricsAPIView endpoint tests
  - Metrics collection tests (all 11 types)
  - Concurrent updates
  - Edge cases (zero latency, unicode labels)
  - Integration tests

#### Implementation
- **prometheus-client**: Python client library (v0.19.0)
- **MetricsCollector**: Helper class for all metrics
- **Custom registry**: Isolated from default Prometheus registry
- **Non-blocking**: Metrics collection never blocks requests
- **Thread-safe**: Concurrent metric updates supported

#### Configuration
- **prometheus.yml**: Scrape config (15s interval)
- **loki-config.yml**: Loki server config (storage, retention)
- **promtail-config.yml**: Log scraping config (Docker containers)
- **grafana/provisioning/**:
  - `datasources/datasources.yml` - Prometheus + Loki datasources
  - `dashboards/dashboard.yml` - Dashboard provider
  - `dashboards/knowledgerouter.json` - Dashboard definition

#### Docs
- **docs/MONITORING.md**: Complete monitoring guide (Prometheus + Grafana)
  - Quick Start
  - Metric definitions
  - Dashboard panels
  - Key queries
  - Testing
  - Production recommendations
  - Troubleshooting
- **docs/LOKI_LOGGING.md**: Complete logging guide (Loki + Promtail)
  - Structured JSON logging
  - LogQL query examples
  - Integration guide
  - Grafana Explore usage
  - Troubleshooting

---

### 🧩 Optional MCP Server (v0.1 alpha)

- **Purpose**: Expose existing infra clients (Jira, Qdrant, Postgres) as Model Context Protocol tools
- **Transport**: stdio (ready for HTTP/SSE later)
- **Tools**: Jira ticket create/search, Qdrant semantic search/retrieve, Postgres feedback/analytics
- **Isolation**: Standalone module (`backend/mcp_server`), no changes to core backend
- **Getting Started**: `pip install -r backend/mcp_server/requirements.txt && python -m backend.mcp_server`

---

### ✨ Message Deduplication Reducer (NEW in v2.6)

- **SHA256-Based**: Deduplicates messages by role + normalized content
- **Applied**: After initial HumanMessage and after AIMessage append
- **Benefits**: Reduces prompt noise, stabilizes generation, lowers token usage

---

### 🧩 Resilience Improvements

- **RAG Retrieval Try/Catch**: Continues gracefully with empty citations on retrieval errors
- **Guardrail Conditional Routing**: Retry path to generation or continue to feedback_metrics

---

### 🚀 Dual Pipeline Modes (NEW in v2.10)

#### Feature Flag: USE_SIMPLE_PIPELINE

**Simple Pipeline (True):**
- **Flow**: Intent (keyword) → RAG → Generation → Guardrail
- **Latency**: ~15 seconds average
- **LLM Calls**: 1-2 (generation + guardrail)
- **Cost**: Low ($0.002 per query)
- **Use Case**: IT/Marketing simple queries, fast response critical
- **Limitations**: No tool execution, no replan, no workflow automation

**Complex Pipeline (False - Default):**
- **Flow**: Intent (LLM) → Plan → Tool Selection → Tool Executor → Observation → Replan Loop (max 2×) → Generation → Guardrail → Workflow → Memory
- **Latency**: ~30-50 seconds average (optimized from 60-90s)
- **LLM Calls**: 4-6 (intent, plan, observation, generation, memory, guardrail)
- **Cost**: Medium ($0.008 per query)
- **Use Case**: Multi-step tasks, workflow automation, tool combinations
- **Features**: Full LangGraph workflow, replan mechanism, memory management

#### Complex Workflow Iteration Details

**Why Complex Pipeline is Slower:**

1. **LLM-based Intent Detection** (2-3 sec):
   - Analyzes query semantics with GPT-4o-mini
   - Detects domain + query complexity
   - Fallback: keyword matching

2. **Plan Node** (5-6 sec):
   - LLM generates execution plan
   - Estimates steps and tool requirements
   - Increments `replan_count` state

3. **Tool Selection** (3-4 sec):
   - LLM decides: rag_only / tools_only / rag_and_tools
   - Routes to appropriate executor

4. **Tool Executor** (5-10 sec):
   - Async execution with 10s timeout per tool
   - Parallel: RAG search + Jira lookup (future)
   - Sequential currently: RAG → tool → tool

5. **Observation Node** (3 sec):
   - LLM evaluates: sufficient information?
   - Detects gaps in retrieval
   - **Optimization**: Auto-skip for IT/Marketing with ≥3 citations

6. **Replan Loop** (10-20 sec if triggered):
   - Max 2 iterations
   - Regenerates plan with adjusted strategy
   - Loops back to Tool Selection
   - **Optimization**: Force generate after 1st replan for simple domains

7. **Generation** (10-15 sec):
   - GPT-4o-mini generates final answer
   - IT domain: Auto-appends Jira ticket question
   - **STRICT_RAG_MODE** controls fallback behavior (see below)

---

### 🛡️ STRICT_RAG_MODE Feature Flag (NEW in v2.12)

#### Overview

Configurable LLM fallback behavior when RAG (Retrieval-Augmented Generation) returns no relevant documents from the knowledge base.

#### Feature Flag: STRICT_RAG_MODE

**Environment Variable:**
```bash
# .env file
STRICT_RAG_MODE=true   # Default: strict mode
STRICT_RAG_MODE=false  # Relaxed mode
```

**Docker Compose:**
```yaml
services:
  backend:
    environment:
      - STRICT_RAG_MODE=${STRICT_RAG_MODE:-true}  # Default to true
```

#### Behavior Modes

**Strict Mode (STRICT_RAG_MODE=true) - Default:**
- **Response**: Refuses to answer if RAG returns 0 documents
- **Message**: "Sajnálom, nem találtam releváns információt ehhez a kérdéshez a rendelkezésre álló dokumentumokban..."
- **LLM Prompt**: Contains `CRITICAL FAIL-SAFE INSTRUCTIONS` block
- **Use Case**: Production environments, compliance-sensitive domains (Legal, Finance)
- **Safety**: Prevents hallucination, ensures factual accuracy from known sources

**Relaxed Mode (STRICT_RAG_MODE=false):**
- **Response**: Allows LLM to use general knowledge with warning prefix
- **Message Prefix**: "⚠️ A következő információ általános tudásomon alapul, nem pedig a szervezeti dokumentumokon:"
- **LLM Prompt**: Contains `INSTRUCTIONS` block (less restrictive)
- **Use Case**: Development, general knowledge queries (e.g., "What is an IP address?")
- **Safety**: Clear warning to user that information is not from company docs

#### Prompt Differences

**Strict Mode Prompt:**
```
CRITICAL FAIL-SAFE INSTRUCTIONS:
1. **Only use information from the retrieved documents above** - DO NOT invent facts
2. **If no relevant documents were retrieved** (empty context):
   - Respond with: "Sajnálom, nem találtam releváns információt..."
```

**Relaxed Mode Prompt:**
```
INSTRUCTIONS:
1. **Prefer information from the retrieved documents above**, but you may use your general knowledge if documents are insufficient
2. **If using general knowledge (not from documents):**
   - Clearly state: "⚠️ A következő információ általános tudásomon alapul..."
   - Suggest verifying with the relevant team for organization-specific details
```

#### Implementation Details

**Code Location:** [backend/services/agent.py](../backend/services/agent.py#L963-L991)

**Logic:**
```python
strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"

if not context.strip():  # No RAG results
    if strict_rag_mode:
        # Original behavior: refuse to answer
        failsafe_instructions = "CRITICAL FAIL-SAFE..."
    else:
        # New behavior: allow general knowledge
        failsafe_instructions = "INSTRUCTIONS: ...you may use your general knowledge..."
```

**Important Notes:**
- Environment variable changes require `docker-compose up -d --force-recreate backend`
- Simple `docker-compose restart` is **not sufficient** (Docker caches env vars)
- Backend code is volume-mounted (`./backend:/app`) so code changes auto-reload via `uvicorn --reload`

#### Test Coverage

**Test File:** [tests/test_strict_rag_mode.py](../backend/tests/test_strict_rag_mode.py)

**Tests:**
- ✅ Strict mode detection (`STRICT_RAG_MODE=true`)
- ✅ Relaxed mode detection (`STRICT_RAG_MODE=false`)
- ✅ Default behavior (strict when env var not set)
- ✅ Case-insensitive values (`True`, `TRUE`, `true`, `False`, `FALSE`, `false`)
- ✅ Prompt contains strict instructions when enabled
- ✅ Prompt contains relaxed instructions when disabled

**Test Results:** 7/7 passed ✅

#### Usage Recommendations

**Use Strict Mode (true) when:**
- ✅ Production environment
- ✅ Legal/Finance/HR domains (compliance-critical)
- ✅ Want to prevent LLM hallucination
- ✅ Only trust company-approved documentation

**Use Relaxed Mode (false) when:**
- ✅ Development/testing environment
- ✅ General knowledge queries ("What is an IP address?")
- ✅ Allowing fallback to LLM training data is acceptable
- ✅ User is aware of warning prefix

#### Security Considerations

- **Strict mode** prevents information leakage from LLM training data
- **Relaxed mode** clearly marks non-company information with ⚠️ prefix
- Both modes **never fabricate** organization-specific details (emails, policies, internal procedures)

8. **Guardrail** (0.5 sec):
   - IT domain: Citation validation
   - Retry generation if citations missing (max 2×)

9. **Workflow Node** (2-5 sec):
   - IT domain: Prepare Jira ticket draft
   - Update state with workflow metadata

10. **Memory Update** (1 sec):
    - Conversation summary + facts extraction
    - SHA256 deduplication
    - Rolling window (last 8 messages)

**Total Load Breakdown:**
- **LLM Round Trips**: 4-6 (vs 1-2 in simple)
- **State Mutations**: 10+ nodes (vs 3 in simple)
- **Iteration Potential**: 2× replan = 3× workflow execution
- **Tool Overhead**: Async timeouts, validation, error handling

#### Configuration

```bash
# .env file
USE_SIMPLE_PIPELINE=False  # Default: complex workflow

# docker-compose.yml
environment:
  - USE_SIMPLE_PIPELINE=True  # Override to simple
```

#### Performance Metrics

| Metric | Simple | Complex | Complex Optimized |
|--------|--------|---------|-------------------|
| Avg Latency | 15-20s | 60-90s | 30-50s |
| LLM Calls | 1-2 | 8-10 | 4-6 |
| Replan Support | ❌ | ✅ (max 2) | ✅ (limited 1) |
| Tool Execution | RAG only | All tools | All tools |
| Workflow Automation | ❌ | ✅ | ✅ |

#### Tests
- **backend/tests/test_chat_service.py**: Pipeline mode branching logic
- **backend/tests/test_agent.py**: `run_simple()` vs `run()` method validation

**See**: [docs/PIPELINE_MODES.md](PIPELINE_MODES.md) for detailed usage guide

### 🎫 IT Domain - Qdrant Semantic Search & Jira Integration (NEW in v2.3)

#### Confluence IT Policy Indexing
- **sync_confluence_it_policy.py**: Indexing script for Confluence pages
- **Workflow**: Confluence API → HTML parsing (BeautifulSoup) → Chunking (800 chars) → Embedding (OpenAI) → Qdrant upsert
- **Domain Filtering**: `domain="it"` metadata for precise filtering
- **Confluence API**: REST API v2, HTML storage format parsing
- **Section Extraction**: h1/h2/h3 headers with sibling content collection
- **Metadata**: section_id, section_title, confluence_url, indexed_at

#### Runtime IT Query Flow
- **Semantic Search**: Qdrant retrieval with domain=`it` filter (NOT keyword matching)
- **Redis Caching**: Embedding cache + query result cache
- **LLM Generation**: IT-specific instructions with procedure/responsibility references
- **Jira Ticket Offer**: Always offered at end of IT responses
- **Chat-Based Flow**: "igen" response detection → automatic ticket creation

#### Jira Ticket Integration
- **AtlassianClient**: Singleton for Jira API v3
- **Ticket Creation**: POST `/rest/api/3/issue` (project: SCRUM)
- **API Endpoint**: POST `/api/jira/ticket/` (summary, description, issue_type, priority)
- **Frontend Flow**: `lastITContext` → "igen" detection → `createJiraTicket()` → success message
- **Response Format**: Ticket key (SCRUM-123) with clickable link

#### Architecture Benefits
- **Consistent Workflow**: Same as HR/Marketing (Qdrant semantic search)
- **No Runtime Confluence Calls**: Indexing-time only, performance boost
- **Scalable**: Multiple Confluence pages can be indexed
- **Cached**: Redis reduces OpenAI API calls and search latency

### 🏗️ Architecture & Development Tools

#### LangGraph Orchestration (Production)
- **StateGraph Workflow**: Complete agent workflow using LangGraph StateGraph
- **11 Orchestrated Nodes** (v2.8):
  - `intent_detection` - Domain classification (keyword + LLM fallback)
  - `plan_node` - Execution plan generation (steps, estimates)
  - `select_tools` - Tool selection and routing decision
  - `tool_executor` - Execute selected tools with timeout/retry (NEW v2.8)
  - `retrieval` - Qdrant RAG search with domain filtering (+ facts-based rewrite)
  - `generation` - Context-aware LLM response generation (+ memory summary & facts)
  - `guardrail` - Response validation (IT citations, contradiction detection)
  - `observation` - LLM evaluation of results, replan decision (NEW v2.8)
  - `feedback_metrics` - Telemetry collection (latency, cache hits, token usage)
  - `execute_workflow` - HR/IT workflow automation
  - `memory_update` - Rolling window, summary, facts extraction
- **State Management**: AgentState with messages, domain, citations, validation_errors, retry_count, metrics, tool_results, observation, replan_count (NEW v2.8)
- **Execution Flow**: intent → plan → select_tools → conditional → retrieval/tool_executor → observation → conditional → replan/generation → guardrail → feedback_metrics → workflow → memory_update → END
- **Conditional Routing**: 
  - `select_tools` routes `rag_only`→retrieval, `tools_only`/`rag_and_tools`→tool_executor
  - `observation` routes `replan`→plan (max 2x), `generate`→generation
  - `guardrail` can route back to generation for retries
- **Benefits**: Declarative workflow, easy debugging, state persistence, extensible graph structure, replan loop for quality

#### Enhanced ABC Interfaces
- **IEmbeddingService**: Swappable embedding providers (OpenAI/Cohere/HuggingFace)
- **IVectorStore**: Abstraction for Qdrant/Pinecone/Weaviate vector databases
- **IFeedbackStore**: Interface for PostgreSQL/MongoDB/Redis feedback persistence
- **IRAGClient**: Orchestration interface for retrieve operations
- **Benefits**: Easy mocking for tests, clear contracts, DIP compliance

#### Health Check System
- **Startup Validation**: Validates all critical services on app launch
- **Fail-Fast**: Immediate error detection for missing config
- **Graceful Degradation**: Optional services (PostgreSQL, Redis) don't block startup
- **Pretty-Printed Report**: Visual health status with ✅/⚠️ indicators
- **Environment Masking**: Secure display of sensitive API keys (sk-proj-***)

#### Debug CLI Utilities
- **Citation Formatter**: Pretty print RAG search results with scores, metadata, content preview
- **Feedback Statistics**: Visual bar charts with 🟢🟡🔴 indicators based on like percentage
- **Ranking Comparison**: Side-by-side semantic vs feedback-boosted ranking display
- **Interactive Testing**: `test_rag_search()` for live debugging
- **Command Line**: `python -m utils.debug_cli "query" domain top_k`

---

### 🔍 Core RAG & Search

#### Multi-Domain Knowledge Base
- **6 Domain Support**: HR, IT, Finance, Legal, Marketing, General
- **Single Qdrant Collection**: `multi_domain_kb` with domain filtering
- **Payload-Based Filtering**: Fast domain-specific searches without separate collections
- **Hybrid Search Ready**: Dense vectors (semantic) + metadata filtering (BM25 preparation)

#### Intent Detection (LangGraph Node)
- **Dual-Strategy Classification**: 
  - **Keyword-Based** (primary): Fast, cost-free pre-classification (20+ marketing terms, HR/IT keywords)
  - **LLM-Based** (fallback): GPT-4o-mini classification for ambiguous queries
- **State Management**: Domain stored in AgentState, passed to subsequent nodes
- **Supported Domains**: HR, IT, Finance, Legal, Marketing, General
- **Example Flow**: 
  - Query: "Mi a brand sorhossz?" → Keyword match: "brand" → Domain: marketing
  - Query: "VPN nem működik" → Keyword match: "VPN" → Domain: it
  - Query: "Contract terms" → LLM classification → Domain: legal

#### RAG Pipeline
- **Semantic Search**: OpenAI `text-embedding-3-small` (1536 dims)
- **Top-K Retrieval**: Configurable number of relevant documents
- **Citation Support**: Enhanced card display with:
  - **Relevance Score**: Percentage-based similarity score (0-100%)
  - **Document Metadata**: Section ID (IT-KB-xxx), Doc ID tracking
  - **Interactive Cards**: Hover effects, clickable URLs, emoji icons
  - **Visual Hierarchy**: Card layout with header/metadata sections
- **Context Window Management**: Auto-truncate to fit model limits (128k tokens)

---

### 💾 Caching & Performance

#### Redis Cache System
- **Embedding Cache**: Text → vector cache (reduces OpenAI API calls by 54%)
- **Query Result Cache**: Domain-specific query response caching
- **TTL Management**: Configurable expiration (default: 1 hour)
- **Memory Limits**: 512MB max with LRU eviction policy
- **Cache Stats API**: `/api/cache-stats/` endpoint for monitoring

#### Domain-Scoped Invalidation
- **Auto-Invalidation**: Document sync triggers cache clear per domain
- **Manual Invalidation**: `DELETE /api/cache-stats/?domain=marketing`
- **Selective Clearing**: Invalidate specific domains without affecting others

---

### 📊 Feedback & Analytics

#### Like/Dislike System (NEW in v2.1)
- **Citation-Level Feedback**: 👍👎 per document source
- **PostgreSQL Storage**: Async database with connection pooling
- **Background Processing**: Non-blocking feedback save (thread-safe)
- **Duplicate Handling**: ON CONFLICT update for same user/citation/session

#### Feedback Analytics
- **Domain-Scoped Stats**: Separate aggregation per domain
- **Materialized Views**: Fast query performance (`citation_stats` view)
- **API Endpoints**:
  - `POST /api/feedback/citation/` - Submit feedback
  - `GET /api/feedback/stats/` - Get aggregated statistics
  - `GET /api/feedback/stats/?domain=marketing` - Domain filtering

#### Citation Ranking (✅ IMPLEMENTED in v2.4)
- **Rank Tracking**: Store citation position (1st, 2nd, 3rd result)
- **Query Context**: Optional embedding storage for context-aware scoring
- **✅ Feedback-Weighted Re-ranking**: Live production feature
  - **Tiered Boost System**: +30% (>70% likes), +10% (40-70%), -20% (<40%)
  - **Batch PostgreSQL Queries**: Single SQL call for all citation feedback
  - **Score Formula**: `final_score = semantic_score × (1 + feedback_boost)`
  - **Adaptive Learning**: Popular content rises, poor quality demoted
- **✅ Content Deduplication**: Remove PDF/DOCX duplicates before ranking
  - **Signature-Based**: Title + content preview (80 chars)
  - **Highest Score Wins**: Keeps best-scoring duplicate
  - **Marketing Domain**: Solves Aurora Arculat kézikönyv duplicate issue
- **✅ IT Overlap Boost**: Lexical query-term matching for IT domain
  - **Generic Algorithm**: No hardcoded section IDs
  - **0-20% Score Boost**: Based on token overlap ratio
  - **Query Tokens**: Minimum 3-char tokens from user query

---

### 🔗 External Integrations

#### Google Drive (Marketing Domain)
- **OAuth 2.0 Authentication**: Service account with domain delegation
- **Folder Sync**: Auto-sync documents from specific Drive folders
- **File Parsing**: DOCX, PDF, TXT extraction
- **Metadata Preservation**: Filename, path, modification date

#### Qdrant Vector Database
- **Self-Hosted**: Docker container (port 6334)
- **Multi-Domain Collection**: Single collection with payload filtering
- **Async Client**: asyncpg for non-blocking operations
- **Health Monitoring**: Connection status checks

#### OpenAI API
- **GPT-4o-mini**: Response generation (cost-optimized)
- **text-embedding-3-small**: Document and query embeddings
- **Token Tracking**: Per-request usage logging
- **Cost Calculation**: Real-time cost estimation

---

### 🔄 Workflow Automation (LangGraph-Powered)

#### LangGraph Workflow Node
- **Integrated Node**: `execute_workflow` as final node in StateGraph
- **Domain-Specific Logic**: Different workflows per domain (HR, IT, Finance)
- **State-Based Execution**: Accesses full agent state (query, domain, citations)
- **Non-Blocking**: Workflow execution doesn't block response generation

#### Predefined Workflows
- **HR Vacation Request**: Parse dates, create workflow object
- **IT Support Ticket**: Generate ticket ID, track status
- **Extensible Framework**: Easy to add new workflow types as graph nodes

#### Workflow Structure
```json
{
  "action": "vacation_request",
  "type": "hr",
  "status": "pending",
  "next_step": "Manager approval",
  "data": {"start_date": "2024-10-03", "end_date": "2024-10-04"}
}
```

---

### ⚡ Cached Regeneration (NEW in v2.2)

**Optimize repeat queries by skipping intent detection and RAG retrieval.**

#### Architecture
- **Node Skipping**: Bypasses 2 of 4 LangGraph nodes (intent_detection + retrieval)
- **Session Cache**: Reads domain + citations from previous bot message
- **Partial Execution**: Runs ONLY generation + workflow nodes
- **State Reuse**: Injects cached data directly into AgentState

#### Performance Benefits

| Metric              | Full Pipeline (4 nodes) | Cached Regeneration (2 nodes) | Improvement |
|---------------------|-------------------------|-------------------------------|-------------|
| **Execution Time**  | ~5600ms                 | ~3500ms                       | **38% faster** |
| **Token Usage**     | ~2500 tokens            | ~500 tokens                   | **80% cheaper** |
| **LLM Calls**       | 2 (intent + generation) | 1 (generation only)           | **50% fewer** |
| **Qdrant Queries**  | 1 (RAG retrieval)       | 0 (uses session cache)        | **100% saved** |

#### Use Cases
- 🔄 **Refresh answer**: Same question, regenerate with different phrasing
- 🎯 **Refine response**: Retry generation without changing context
- 💰 **Cost optimization**: Multiple attempts at fraction of the cost
- ⚡ **Speed**: Sub-second regeneration for better UX

#### API Endpoint
```http
POST /api/regenerate/
{
  "session_id": "session_xyz",
  "query": "Mi a brand sorhossz?",
  "user_id": "user_123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "domain": "marketing",
    "answer": "Regenerated answer...",
    "citations": [...],
    "regenerated": true,
    "cache_info": {
      "skipped_nodes": ["intent_detection", "retrieval"],
      "executed_nodes": ["generation", "workflow"],
      "cached_citations_count": 5
    }
  }
}
```

#### Frontend UX
- **Dual Refresh Buttons**: ⚡ (cached) vs 🔄 (full RAG)
- **Visual Indicator**: Badge showing "⚡ Gyors újragenerálás (cached context)"
- **Color-Coded**: Green hover for cached, blue for full refresh

#### Technical Implementation
- **Backend**: `agent.regenerate()` method bypasses intent + retrieval nodes
- **Frontend**: `refreshQuery(question, useCache=true)` dual-mode function
- **Session Storage**: Message model enhanced with domain/citations/workflow fields
- **Validation**: Unit tests for node skipping + cache extraction

---

### 🛡️ Error Handling & Reliability

#### Retry Logic
- **Exponential Backoff**: 1s → 2s → 4s delays
- **Max Retries**: 3 attempts per request
- **Jitter**: Randomized delays to prevent thundering herd
- **Smart Retry**: Only retries transient errors (429, 5xx, timeouts)

#### Input Validation
- **Token Limits**: Max 10,000 input tokens (HTTP 413 if exceeded)
- **Empty Query Check**: Rejects blank requests (HTTP 400)
- **Prompt Truncation**: Auto-truncate to 100k tokens
- **SQL Injection Protection**: Parameterized queries

#### Error Status Codes
- `400` - Invalid request (empty query, missing fields)
- `413` - Payload too large (>10k tokens)
- `429` - Rate limit exceeded
- `500` - Internal server error
- `503` - OpenAI API unavailable

---

### 📈 Monitoring & Observability

#### Monitoring
- **Token Tracking**: Input + output tokens per request
- **Cost Calculation**: $0.15/1M input, $0.60/1M output (gpt-4o-mini)
- **API Endpoint**: `GET /api/usage-stats/`
- **Reset Capability**: `DELETE /api/usage-stats/`
- **Telemetry API** (NEW v2.2): Performance & debug data in `/api/query/` response
  - `total_latency_ms` - End-to-end pipeline time
  - `chunk_count` - RAG retrieval count
  - `max_similarity_score` - Top relevance score
  - `request/response/rag/llm` - Full debug payloads

#### Cache Monitoring
- **Hit Rate Tracking**: Cache hits vs misses
- **Memory Usage**: Current usage vs limit (512MB)
- **Key Count**: Total cached items
- **Connection Status**: Redis availability check

#### Logging
- **Structured Logs**: Timestamp, level, module, thread ID
- **Request Tracing**: Full request/response logging
- **Error Details**: Stack traces with context
- **Performance Metrics**: Query execution time

---

### 🎨 Frontend & UX

#### ChatGPT-Style Interface
- **Tailwind CSS**: Modern, responsive design
- **Markdown Rendering**: Rich text formatting in responses
- **Code Highlighting**: Syntax highlighting for code blocks
- **Loading States**: Skeleton loaders during processing

#### Citation Display
- **Document References**: Clickable source links
- **Citation Cards**: Title, snippet, relevance score
- **Rank Indicators**: #1, #2, #3 badges
- **Feedback Buttons**: 👍👎 per citation (NEW)

#### Conversation History
- **Session Persistence**: JSON-based storage
- **Multi-Session Support**: Isolated conversations per session
- **History Retrieval**: `GET /api/sessions/{session_id}/`
- **Context Reset**: Clear conversation context

#### Debug Panel (NEW in v2.2)
- **Real-Time Telemetry**: Live performance & pipeline metrics (bottom-right corner)
- **Performance Metrics**:
  - ⏱️ **Pipeline Latency** - Total request-response time (milliseconds)
  - 📦 **Chunk Count** - Number of retrieved RAG documents
  - 🎯 **Max Similarity Score** - Highest relevance score (0.0-1.0)
- **Collapsible Debug Sections** (scrollable, max 85vh):
  - 📤 **Request JSON** - Sent payload (user_id, session_id, query)
  - 📥 **Response JSON** - Complete API response structure
  - 🔍 **RAG Context** - Full document context sent to LLM
  - 🤖 **LLM Prompt** - Complete prompt with system message + context
  - 💬 **LLM Response** - Raw LLM output before processing
- **Auto-Update**: Refreshes on every query (new, cached ⚡, full refresh 🔄)
- **Graceful Degradation**: Shows "No RAG context" for general domain queries
- **Use Cases**: 
  - 🐛 Debug LLM prompt engineering
  - 📊 Performance monitoring & latency tracking
  - 🔬 RAG chunk quality validation
  - 🧪 End-to-end pipeline inspection

---

### 🐳 Deployment & DevOps

#### Docker Compose
- **Multi-Container**: Backend, Frontend, Qdrant, Redis, PostgreSQL
- **Hot Reload**: Uvicorn auto-reload on code changes
- **Volume Mounts**: Persistent data for Qdrant, Postgres, Redis
- **Health Checks**: Automated service health monitoring

#### ASGI Server
- **Uvicorn**: High-performance async server
- **uvloop**: Fast event loop (C-based)
- **Async Views**: Django REST Framework with async support
- **Connection Pooling**: Reusable database connections

#### Environment Configuration
- **`.env` File**: Centralized configuration
- **Environment Variables**: API keys, database credentials
- **Secrets Management**: `.env.example` template

---

### 🧪 Testing & Quality

#### Unit Tests (Updated v2.8)
- **180+ Passing Tests**: Expanded test coverage including integration tests
  - **Sprint 4 (Tool Executor)**: 6 tests ✅
  - **Sprint 5 (Observation)**: 6 tests ✅
  - **Integration I1 (E2E Workflow)**: 7 tests ✅
  - **Integration I2 (Graph Validation)**: 10 tests ✅
  - **Total Sprint 4+5+I1+I2**: 33 tests ✅
- **49% Code Coverage**: Nearly doubled from 25% baseline
- **Pytest Framework**: Modern testing with fixtures and async support
- **Mock Support**: External API mocking with pytest-mock

#### Integration Testing (NEW in v2.8)
- **End-to-End Workflow Tests** (7 tests):
  - Complete flow: Plan → Tool Selection → Executor → Observation
  - MockLLM pattern with dict-based response mapping
  - Replan loop validation (max 2 iterations)
  - Multi-tool execution (parallel tools)
  - Error handling mid-workflow
  - Tool results counting accuracy
  
- **Graph Compilation Tests** (10 tests):
  - LangGraph StateGraph compilation verification
  - 11-node structure validation
  - Conditional edge routing (_tool_selection_decision, _observation_decision, _guardrail_decision)
  - Replan loop max iteration enforcement
  - AgentState schema validation (21 fields)
  - Entry/exit point verification
  - Decision function callable checks

#### Test Categories
- **Error Handling**: Retry logic, exponential backoff (39 tests ✅)
- **OpenAI Clients**: Embedding, LLM, token tracking (24 tests ✅)
- **Redis Cache**: Hit/miss, TTL, invalidation (partial legacy)
- **Feedback Ranking**: Boost calculation, PostgreSQL batch ops (14 tests ✅)
- **Health Checks**: Startup validation, config checks (10 tests ✅ NEW)
- **Debug CLI**: Citation formatting, feedback stats (17 tests ✅ NEW)
- **Interfaces**: ABC contracts, implementation validation (15 tests ✅ NEW)
- **Telemetry**: Pipeline metrics, RAG/LLM capture (9 tests ✅ NEW v2.2)
- **Tool Executor Loop**: Tool execution, observation, replan (6 tests ✅ NEW v2.7)
- **Observation Node**: LLM evaluation, replan decision (6 tests ✅ NEW v2.8)
- **Integration E2E**: Complete workflow validation (7 tests ✅ NEW v2.8)
- **Integration Graph**: LangGraph compilation, routing (10 tests ✅ NEW v2.8)

#### Test Execution
```bash
# Run all tests with coverage
docker-compose exec backend pytest tests/ --cov=infrastructure --cov=domain --cov=utils --cov-report=html

# Run specific test suites
docker-compose exec backend pytest tests/test_health_check.py -v
docker-compose exec backend pytest tests/test_debug_cli.py -v
docker-compose exec backend pytest tests/test_interfaces.py -v
docker-compose exec backend pytest tests/test_feedback_ranking.py -v

# View HTML coverage report
# Open: backend/htmlcov/index.html
```

#### CI/CD Ready
- **pytest.ini**: Configured test settings
- **Coverage Reports**: HTML + terminal output
- **Docker Tests**: Run tests in container environment
- **Coverage Threshold**: 25% minimum (currently 49% ✅)

---

## 🚧 Planned Features (Roadmap)

### High Priority
- [ ] **Multi-Query Generation**: 5 query variations with frequency ranking
- [ ] **BM25 Sparse Vectors**: Lexical search for brand names, codes

### Medium Priority
- [ ] **PII Detection**: Automatic sensitive data filtering
- [ ] **Rate Limiting**: Per-user request limits (100/hour)
- [ ] **Prometheus Metrics**: Advanced monitoring dashboard

### Low Priority
- [ ] **Authentication**: API key or JWT token auth
- [ ] **Audit Logging**: Compliance logs for all queries
- [ ] **WebSocket Support**: Real-time streaming responses
- [ ] **Multi-Language**: Auto-detect and translate

### ✅ Recently Completed (moved from roadmap)
- [x] **Feedback-Weighted Re-ranking** (v2.4)
- [x] **Content Deduplication** (v2.4)
- [x] **IT Overlap Boost** (v2.4)
- [x] **Section ID Citations** (v2.3)
- [x] **Jira Ticket Integration** (v2.3)

---

## 📊 Feature Metrics

| Category | Features | Status |
|----------|----------|--------|
| **Core RAG** | 8 | ✅ Complete |
| **Caching** | 6 | ✅ Complete |
| **Feedback** | 7 | ✅ Backend Complete, 🚧 Frontend Testing |
| **Architecture** | 3 | ✅ Complete (NEW v2.2) |
| **Testing** | 180+ tests | ✅ 49% Coverage (NEW v2.8) |
| **Integration Tests** | 17 tests | ✅ Complete (NEW v2.8) |
| **Integrations** | 3 | ✅ Complete |
| **Workflows** | 2 types | ✅ Complete |
| **Frontend** | 12 | ✅ Complete |
| **DevOps** | 5 | ✅ Complete |

**Total Features:** 51 implemented | 10 planned

---

## 🔧 Development Tools

### Health Check System
```bash
# Health checks run automatically on startup
docker-compose up

# Example output:
# ======================================================================
# 🏥 INFRASTRUCTURE HEALTH CHECK
# ======================================================================
# 
# 📌 CRITICAL SERVICES:
#   ✅ ENV:OPENAI_API_KEY=sk-proj-***
#   ✅ OpenAI client importable
#   ✅ Qdrant URL configured: http://qdrant:6333
# 
# 📋 OPTIONAL SERVICES:
#   ⚠️ PostgreSQL will use lazy init: postgres
#   ⚠️ Redis configured: redis://redis:6379
# 
# ======================================================================
# ✅ ALL CRITICAL SERVICES READY
# ======================================================================
```

### Debug CLI
```bash
# Interactive RAG testing
docker-compose exec backend python -c "
from utils.debug_cli import quick_search
import asyncio
asyncio.run(quick_search('brand colors', 'marketing', 5))
"

# Command line usage
docker-compose exec backend python -m utils.debug_cli "szabadság igénylés" hr 5

# Example output:
# 📚 RETRIEVED 3 CITATIONS:
# ================================================================================
# 
#   [1] Score: 1.3000 | ID: 1ACEdQxgUuAsDHKPBqKyp2kt88DjfXjhv#chunk0
#       Title: Aurora_Digital_Brand_Guidelines_eng.docx
#       Content: "Brand colors are #0066CC (primary blue)..."
# 
# 📊 FEEDBACK STATISTICS (3 citations):
# ================================================================================
# 
#   🟢  85.0% [█████████████████░░░] doc_123#chunk0
#   🟡  55.0% [███████████░░░░░░░░░] doc_456#chunk1
#   🔴  25.0% [█████░░░░░░░░░░░░░░░] doc_789#chunk2
```
| **Integrations** | 3 | ✅ Complete |
| **Workflows** | 2 | ✅ Complete |
| **Error Handling** | 5 | ✅ Complete |
| **Monitoring** | 4 | ✅ Complete |
| **Frontend** | 6 | 🚧 Feedback UI Testing |
| **Deployment** | 4 | ✅ Complete |
| **Testing** | 4 | ✅ Complete |

**Overall Progress**: 47/52 features (90% complete)

---

## 🔗 Related Documentation

- [Main README](README.md) - Project overview
- [API Documentation](API.md) - Endpoint reference
- [Redis Cache](REDIS_CACHE.md) - Cache architecture
- [Installation Guide](INSTALLATION.md) - Setup instructions
- [Google Drive Setup](GOOGLE_DRIVE_SETUP.md) - Drive integration

---

**Last Updated:** 2026-01-20  
**Version:** 2.8.0 (Tool Executor Loop + Observation + Integration Tests)

---

## 🔄 Changelog v2.8.0 (2026-01-20)

### New Features
- **Tool Executor Loop** (Sprint 4):
  - Tool execution with timeout (30s default)
  - Retry logic (max 2 attempts)
  - Latency tracking per tool
  - ToolResult model with success/error handling
  - 6 comprehensive unit tests ✅

- **Observation Node** (Sprint 5):
  - LLM-based evaluation of tool/retrieval results
  - Next action decision (replan vs generate)
  - Replan count tracking (max 2 iterations)
  - Data sufficiency assessment
  - 6 comprehensive unit tests ✅

- **Integration Testing** (Sprints I1-I2):
  - **E2E Workflow Tests**: 7 tests validating complete Plan→Selection→Executor→Observation→Replan flow
  - **Graph Validation Tests**: 10 tests for LangGraph compilation, routing, state schema
  - MockLLM pattern for structured output simulation
  - Conditional edge routing validation (3 decision functions)
  - Total: 33 tests passing (Sprint 4+5+I1+I2) ✅

### Architecture Updates
- **11-Node LangGraph Workflow**:
  - Added `tool_executor` node with timeout/retry
  - Added `observation` node with LLM evaluation
  - Replan loop: observation ↔ plan (max 2 iterations)
  - Conditional routing: `_observation_decision()` (replan vs generate)
  
- **AgentState Enhancements**:
  - `tool_results`: List of ToolResult objects
  - `observation`: Observation model with next_action decision
  - `replan_count`: Iteration tracking for safety

### Test Coverage
- **180+ Total Tests**: Comprehensive coverage across all components
- **Integration Tests**: 17 new tests (7 E2E + 10 Graph)
- **Unit Tests**: 12 new tests (6 Tool Executor + 6 Observation)
- **0 IDE Errors**: All linting issues resolved ✅

### Documentation
- ✅ README.md - Updated with v2.8 features and test statistics
- ✅ docs/házi feladatok/4.md - Detailed Sprint 4, 5, I1, I2 documentation
- ✅ FEATURES.md - Integration testing section added

---

## 🔄 Changelog v2.6.1 (2026-01-10)

### Breaking Changes
- **Removed Anthropic/Claude support**: Simplified to OpenAI-only stack
- **Deleted**: `backend/infrastructure/anthropic_clients.py`
- **Removed**: `LLM_PROVIDER` environment variable (no longer needed)
- **Updated**: All documentation to reflect OpenAI-only configuration

### Bug Fixes
- **Qdrant API update**: Fixed `.search()` → `.query_points()` for qdrant-client 1.16.2
- **Embedding model**: Standardized on `text-embedding-3-small` (1536 dim)
- **Redis cache**: Added automatic flush on embedding model change

### Configuration Changes
```bash
# Before (v2.6):
LLM_PROVIDER=anthropic|openai
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# After (v2.6.1):
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

### Documentation Updates
- ✅ README.md - Tech stack and setup simplified
- ✅ INSTALLATION.md - Removed Claude/Anthropic sections
- ✅ FEATURES.md - Updated LLM provider section
- ✅ MEMORY.md - Updated configuration examples

### Test Results
- ✅ Integration tests: 11/11 passed
- ✅ Live query test: Marketing domain successful (12.73s latency)
- ✅ Qdrant API: `query_points()` working correctly


