# KnowledgeRouter - Consolidated Changelog

All version changes consolidated for easy tracking.

---

## Version 2.9.0 (2026-01-21) - Production Hardening

**Critical Bugfixes:**
- ✅ **LangChain with_structured_output() Bug Fix**: Replaced all `with_structured_output()` calls with manual JSON text parsing
  - Affected 6 nodes: intent_detection, plan, tool_selection, observation_check, generation (2x)
  - Pattern: Prompt + JSON format instruction → Regex extract ```json...``` or {...} → json.loads()
  - Root cause: LangChain returning empty dicts {} for all Pydantic models

- ✅ **LangGraph State Management Violations Fixed**:
  - Decision functions now read-only (no state mutations)
  - State mutations moved to nodes (e.g., plan_node increments replan_count)
  - Node "observation" renamed to "observation_check" (conflict with state field)

- ✅ **None-Safe replan_count**: Changed `state.get("replan_count", 0)` to `state.get("replan_count") or 0`
  - Handles both missing key AND None value scenarios

- ✅ **GraphRecursionError Fix**: Increased recursion_limit from 25 to 50
  - Config in `ainvoke(config={"recursion_limit": 50})`, NOT in `compile()`
  - Supports complex workflows with replanning (up to ~24 steps)

- ✅ **IT Domain UX Guarantee**: Jira ticket question now automatically appended
  - Before: LLM-dependent (not guaranteed)
  - After: Hardcoded append in generation_node (guaranteed)

**Test Coverage:**
- Added `test_bugfixes_v2_9.py` with 12 tests
- JSON parsing validation
- None-safe replan_count logic
- Jira question auto-append
- Decision function read-only enforcement
- Node name uniqueness verification

**Performance:**
- Latency: 30-50 sec normal for complex queries with replanning
- OpenAI processing: 2-11 sec per LLM call (6-8 calls total)

---

## Version 2.8.0 (2026-01-20) - Tool Executor & Observation Node

**Features:**
- ✅ **Tool Executor Loop**: Iterative tool execution with asyncio timeout (10s/tool)
  - Non-blocking error handling
  - ToolResult Pydantic validation
  - Success/error/timeout state tracking

- ✅ **Observation Node + Replan Loop**:
  - LLM-based evaluation: sufficient info? → generate OR replan
  - Max 2 replan attempts
  - Gap detection with detailed reasoning
  - Automatic force generate after 2 replans

**Graph Updates:**
- 11 nodes total (intent, plan, select_tools, tool_executor, retrieval, observation, generation, guardrail, feedback_metrics, workflow, memory)
- Conditional routing: rag_only, tools_only, rag_and_tools
- Replan loop: observation → plan → ... → observation (max 2x)

**Test Coverage:**
- 6 tests for tool executor (timeout, error, multiple tools)
- 6 tests for observation + replan (LLM evaluation, max limit)
- 7 E2E integration tests

---

## Version 2.7.0 (2025-12-17) - Memory Reducer & Idempotency

**Features:**
- ✅ **Memory Reducer Pattern**: Cumulative memory summarization
  - Previous summary + new messages → merged summary
  - Semantic fact compression (max 8 relevant facts)
  - Conflict resolution: recent facts override old

- ✅ **Request Idempotency**: X-Request-ID header support
  - Redis cache (5 min TTL)
  - Duplicate requests return cached response instantly
  - X-Cache-Hit: true header on cache hits

**Memory Strategy:**
- Overwrite mode → Reducer mode
- Multi-level summarization ready (short/medium/long)
- LLM-based semantic filtering

---

## Version 2.6.0 (2025-12-16) - Memory System

**Features:**
- ✅ **Memory Update Node**: Conversation tracking
  - Rolling window (last 8 messages)
  - LLM-generated summary (3-5 sentences)
  - Known facts extraction (max 5)
  - SHA256 message deduplication

**Integration:**
- Summary + facts in generation prompt
- RAG query rewrite with facts (top 3)
- Non-blocking (errors logged, not thrown)

**Config:**
- MEMORY_MAX_MESSAGES=8

---

## Version 2.5.0 (2025-12-15) - Guardrail & Telemetry

**Features:**
- ✅ **Guardrail Node**: Citation validation
  - IT domain section ID format check (IT-KB-XXX)
  - Automatic retry loop (max 2x)
  - Hallucination detection

- ✅ **Feedback Metrics Node**: Telemetry collection
  - Latency tracking (total, LLM)
  - Retrieval quality (top-1 score, citation count)
  - Token estimates
  - Cache flags (embedding, query result)

**Graph Updates:**
- 7 nodes total: intent, retrieval, generation, guardrail, feedback_metrics, workflow, memory
- Guardrail conditional routing: retry or continue

---

## Version 2.4.0 (2025-12-10) - LangGraph Core

**Features:**
- ✅ **LangGraph StateGraph**: 11-node workflow orchestration
- ✅ **Multi-domain RAG**: IT, HR, Finance, Legal, Marketing, General
- ✅ **Intent Detection**: LLM-based domain classification
- ✅ **Confluence/Jira Integration**: IT Policy auto-sync
- ✅ **Google Drive Integration**: Marketing document sync

**Architecture:**
- SOLID principles with ABC interfaces
- Health check system (OpenAI, Qdrant, Redis, Postgres)
- Debug CLI for RAG testing

---

## Version 2.3.0 (2025-12-05) - RAG Optimization

**Features:**
- ✅ **Content Deduplication**: PDF/DOCX duplicate removal
- ✅ **IT Domain Overlap Boost**: Lexical token matching (0-20%)
- ✅ **Feedback-Weighted Ranking**: Tiered boost system
  - >70% positive: +30% boost
  - <40% positive: -20% penalty

**Performance:**
- Redis L1/L2 cache: 54% hit rate
- Hybrid search support (semantic + BM25 ready)

---

## Version 2.2.0 (2025-11-28) - Initial Production Release

**Features:**
- ✅ **Django Backend**: REST API
- ✅ **Qdrant Vector DB**: Self-hosted
- ✅ **OpenAI GPT-4o Mini**: LLM (gpt-4o-mini)
- ✅ **PostgreSQL**: Feedback system
- ✅ **Docker Compose**: Multi-container deployment

**Frontend:**
- Tailwind CSS ChatGPT-style UI
- Citation display
- Workflow support (HR, IT tickets)

---

## Archived Changelogs

Older detailed changelogs moved to `docs/archive/`:
- CHANGELOG_v2.4.md
- CHANGELOG_v2.5.md
- DOCUMENTATION_UPDATE_2025-12-17.md

For historical details, see archive folder.
