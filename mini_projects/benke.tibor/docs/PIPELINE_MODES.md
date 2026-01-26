# Pipeline Modes - Simple vs Complex

## Overview

A KnowledgeRouter két pipeline mode-dal rendelkezik:
- **SIMPLE**: Gyors RAG-only pipeline (15-20 sec)
- **COMPLEX**: Teljes LangGraph workflow (30-90 sec)

## 🚀 Simple Pipeline (Fast)

**Használat:**
```bash
export USE_SIMPLE_PIPELINE=True  # vagy .env fájlban
```

**Flow:**
```
Intent Detection (keyword-based, ~10ms)
    ↓
RAG Retrieval (~500ms Qdrant)
    ↓
Generation (~10-15 sec LLM)
    ↓
Guardrail (IT domain only, ~500ms)
    ↓
Response (15-20 sec total)
```

**Jellemzők:**
- ✅ Gyors (15-20 sec átlag)
- ✅ Egyszerű, megbízható
- ✅ Alacsony LLM cost (1-2 hívás)
- ❌ Nincs tool execution (Jira, email, stb.)
- ❌ Nincs replan mechanizmus
- ❌ Nincs workflow automation

**Mikor használd:**
- IT/Marketing domain egyszerű query-k
- Gyors válaszidő kritikus
- Csak RAG-based kérdések (policies, guidelines)

---

## 🔄 Complex Pipeline (Full Workflow)

**Használat:**
```bash
export USE_SIMPLE_PIPELINE=False  # default
```

**Flow:**
```
Intent Detection (LLM-based, ~2-3 sec)
    ↓
Plan Node (execution planning, ~5-6 sec)
    ↓
Tool Selection (tool routing, ~3-4 sec)
    ↓
Tool Executor (RAG/Jira/Email/Calculator, ~5-10 sec)
    ↓
Observation Node (evaluation, ~3 sec) ──┐
    ↓                                     │
    Sufficient? ────NO──> Replan ────────┘
    ↓ YES                 (max 2×)
Generation (~10-15 sec LLM)
    ↓
Guardrail (~500ms)
    ↓
Workflow Automation (Jira ticket create, ~2-5 sec)
    ↓
Memory Update (~1 sec)
    ↓
Response (30-90 sec total)
```

**Jellemzők:**
- ✅ Teljes workflow automation
- ✅ Multi-tool execution (RAG + Jira + Email)
- ✅ Replan mechanizmus (ha nincs elég info)
- ✅ Memory management
- ❌ Lassú (30-90 sec, optimalizált: 30-50 sec)
- ❌ Magas LLM cost (5-10 hívás, optimalizált: 4-6 hívás)

**Mikor használd:**
- Bonyolult multi-step task-ok
- Workflow automation szükséges (Jira ticket)
- Több tool kombinációja kell
- Replan/retry mechanizmus fontos

### 🔍 Miért Lassabb a Complex Workflow?

**Részletes Iterációs Breakdown:**

#### 1. LLM-based Intent Detection (2-3 sec)
- **Mit csinál**: GPT-4o-mini szemantikus elemzés
- **Input**: Query string
- **Output**: Domain (it/hr/finance/marketing/legal/general) + complexity score
- **Miért szükséges**: Pontos domain routing komplex query-knél
- **Simple pipeline**: Keyword matching (~10ms)

#### 2. Plan Node (5-6 sec)
- **Mit csinál**: Execution plan generálás LLM-mel
- **Input**: Query + domain + user context
- **Output**: JSON plan (steps, estimated_time, tool_requirements)
- **Iteráció**: `replan_count++` (state mutation)
- **Miért szükséges**: Multi-step task orchestration
- **Simple pipeline**: Nincs planning

#### 3. Tool Selection (3-4 sec)
- **Mit csinál**: LLM eldönti tool routing strategy-t
- **Input**: Plan + available tools
- **Output**: `rag_only` / `tools_only` / `rag_and_tools`
- **Miért szükséges**: Dynamic tool composition
- **Simple pipeline**: Mindig RAG-only

#### 4. Tool Executor (5-10 sec)
- **Mit csinál**: Async tool execution loop
- **Timeout**: 10 sec per tool (asyncio.wait_for)
- **Tools**: RAG search, Jira API, email sender, calculator
- **Sequential**: RAG → tool1 → tool2 (future: parallel)
- **Validation**: ToolResult schema validation
- **Miért szükséges**: External system integration
- **Simple pipeline**: Csak RAG (~500ms)

#### 5. Observation Node (3 sec)
- **Mit csinál**: LLM evaluálja a retrieval adequacy-t
- **Input**: Retrieved chunks + query + plan
- **Output**: `sufficient: bool`, `gaps: [...]`, `next_action`
- **Optimalizáció**: IT/Marketing domain ≥3 citations → auto-skip LLM call
- **Miért szükséges**: Detect retrieval gaps
- **Simple pipeline**: Nincs evaluation

#### 6. Replan Loop (10-20 sec IF TRIGGERED)
- **Trigger**: `sufficient == False` AND `replan_count < 2`
- **Mit csinál**: Visszamegy Plan Node-hoz új strategy-vel
- **Max iterációk**: 2× (3× total execution)
- **State tracking**: `replan_count` increment
- **Optimalizáció**: IT/Marketing 1. replan után force generate
- **Miért szükséges**: Handle incomplete information
- **Simple pipeline**: Nincs replan

**Replan Loop Példa (VPN query):**
```
1. Attempt: RAG search "VPN" → 2 results → insufficient
   replan_count = 1
2. Replan: RAG search "VPN setup FortiClient" → 5 results → sufficient
   replan_count = 2
3. Generate final answer
```

#### 7. Generation (10-15 sec)
- **Mit csinál**: GPT-4o-mini final answer generation
- **Input**: RAG context + query + plan + memory summary
- **Output**: Comprehensive answer with citations
- **IT domain**: Auto-append Jira ticket question (guaranteed UX)
- **Tokens**: ~1500 prompt + ~500 response
- **Miért szükséges**: Human-readable answer
- **Simple pipeline**: Ugyanez (nincs különbség)

#### 8. Guardrail (0.5 sec)
- **Mit csinál**: IT domain citation validation
- **Pattern**: Regex check `[IT-KB-\d+]` format
- **Retry**: Max 2× regeneration ha missing citations
- **Miért szükséges**: IT policy compliance
- **Simple pipeline**: Ugyanez

#### 9. Workflow Node (2-5 sec)
- **IT domain**: Jira ticket draft preparation
  - Summary: "IT Support: {query}"
  - Description: Query + answer + citations
  - Metadata: user_id, domain, priority
- **State mutation**: `state["workflow"] = {...}`
- **Miért szükséges**: Workflow automation (ticket creation)
- **Simple pipeline**: Nincs workflow automation

#### 10. Memory Update (1 sec)
- **Mit csinál**: LLM conversation summary + facts extraction
- **Input**: Previous summary + current Q&A
- **Output**: Updated summary (3-4 sentences) + facts (max 8)
- **Deduplication**: SHA256 on normalized content
- **Rolling window**: Last 8 messages only
- **Miért szükséges**: Multi-turn conversation context
- **Simple pipeline**: Nincs memory management

---

### 📊 Total Load Analysis

**Complex Pipeline Overhead:**

| Component | Simple | Complex | Overhead |
|-----------|--------|---------|----------|
| LLM Round Trips | 1-2 | 4-6 | **3-4× more** |
| State Mutations | 3 | 10+ | **3× more** |
| Async Operations | 1 (RAG) | 4-6 (tools) | **4-6× more** |
| Replan Iterations | 0 | 0-2 | **+20-40 sec** |
| Network Calls | 2-3 | 8-12 | **3-4× more** |
| JSON Parsing | 1 | 6 | **6× more** |

**Why 30-50 sec (instead of 60-90 sec)?**

✅ **Optimizations Applied:**
1. PostgreSQL eager init (-5-10 sec startup penalty)
2. Observation auto-skip for IT/Marketing ≥3 citations (-3 sec)
3. Replan limit after 1st iteration for simple domains (-10-15 sec)
4. IT overlap boost (lexical matching, minimal overhead)

❌ **Future Optimizations (Not Yet Implemented):**
- Parallel tool execution (RAG + Jira + Email async) → -5-8 sec
- LLM streaming responses (perceived latency reduction)
- Memory summary caching (skip LLM call if no new facts)

---

---

## ⚡ Optimalizációk (Complex Workflow)

### 1. Auto-Generate IT/Marketing Domain

**Probléma:** Observation node feleslegesen hív LLM-et ha már van RAG result.

**Megoldás:**
```python
# services/agent.py:_observation_node()
if domain in ["it", "marketing"] and len(retrieved) >= 3:
    # Skip LLM evaluation, auto-generate
    return {"sufficient": True, "next_action": "generate"}
```

**Eredmény:** −3 sec (1 LLM hívás kevesebb)

---

### 2. Disable Replan Simple Queries

**Probléma:** Replan loop felesleges VPN/brand query-knél.

**Megoldás:**
```python
# services/agent.py:_observation_decision()
if domain in ["it", "marketing"] and replan_count >= 1:
    # Force generate after first replan
    return "generate"
```

**Eredmény:** −10-15 sec (replan loop skip)

---

### 3. Parallel Tool Execution

**Future optimization:**
```python
# Execute RAG + Jira lookup parallel
results = await asyncio.gather(
    rag_search(query),
    jira_search(query)
)
```

**Eredmény:** −5-8 sec (sequential → parallel)

---

## 📊 Performance Comparison

| Metric | Simple Pipeline | Complex Pipeline | Complex Optimized |
|--------|----------------|------------------|-------------------|
| **Avg Latency** | 15-20 sec | 60-90 sec | 30-45 sec |
| **LLM Calls** | 1-2 | 8-10 | 4-6 |
| **LLM Cost** | $0.002 | $0.015 | $0.008 |
| **Tool Support** | RAG only | All tools | All tools |
| **Replan** | ❌ No | ✅ Yes (max 2) | ✅ Limited (1) |
| **Workflow** | ❌ No | ✅ Yes | ✅ Yes |

---

## 🧪 Testing

### Test Simple Pipeline

```bash
export USE_SIMPLE_PIPELINE=True
docker-compose restart backend

curl -X POST http://localhost:8001/api/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "session_id": "perf_test",
    "query": "Mi a VPN beállítás?",
    "domain": "it"
  }'
```

**Expected:**
- Latency: 15-20 sec
- Workflow mode: `simple_pipeline`
- Log: `⚡ SIMPLE PIPELINE completed in 18000ms`

---

### Test Complex Pipeline

```bash
export USE_SIMPLE_PIPELINE=False
docker-compose restart backend

# Same query as above
```

**Expected (with optimization):**
- Latency: 30-45 sec (was 60-90 sec before)
- Workflow mode: `complex` vagy `null`
- Log: `🔄 Using COMPLEX pipeline (full LangGraph workflow)`
- Log: `⚡ FAST PATH: Auto-generating for it domain (skip observation LLM call)`

---

## 🔧 Configuration

### Environment Variables

```bash
# .env file
USE_SIMPLE_PIPELINE=False  # default: complex workflow
STRICT_RAG_MODE=true       # default: refuse answer without RAG context (NEW in v2.12)

# Or Docker Compose
environment:
  - USE_SIMPLE_PIPELINE=True  # override to simple
  - STRICT_RAG_MODE=${STRICT_RAG_MODE:-true}  # default to strict mode
```

**STRICT_RAG_MODE Feature (NEW in v2.12):**
- **true** (default): Refuses to answer when RAG returns 0 documents
  - Response: "Sajnálom, nem találtam releváns információt..."
  - Use case: Production, compliance-critical domains (Legal, Finance, HR)
  - Safety: Prevents LLM hallucination, ensures factual accuracy

- **false**: Allows LLM general knowledge with ⚠️ warning prefix
  - Response: "⚠️ A következő információ általános tudásomon alapul..."
  - Use case: Development, general knowledge queries ("What is an IP address?")
  - Safety: Clear warning that info is not from company docs

**Important:**
- Environment variable changes require: `docker-compose up -d --force-recreate backend`
- Simple `restart` does NOT reload env vars (Docker caches them)
- See [FEATURES.md](FEATURES.md#-strict_rag_mode-feature-flag-new-in-v212) for full details

### Runtime Switch (Django settings)

```python
# core/settings.py
USE_SIMPLE_PIPELINE = os.getenv('USE_SIMPLE_PIPELINE', 'False') == 'True'
```

### Service Layer

```python
# services/chat_service.py
if settings.USE_SIMPLE_PIPELINE:
    response = await self.agent.run_simple(query, user_id, session_id)
else:
    response = await self.agent.run(query, user_id, session_id)
```

---

## 📈 Metrics

### Performance Tracking

Minden kérés log-olja a telemetry-t:

```python
# Simple pipeline
INFO: ⚡ SIMPLE PIPELINE completed in 18000ms

# Complex pipeline  
INFO: 🔍 Qdrant search latency: 128ms (domain=it, results=5)
INFO: 🎯 IT overlap boost latency: 0ms (citations=5)
INFO: 🤖 LLM generation latency: 12720ms (domain=it)
INFO: Metrics collected: 5 citations, tokens=1213, latency=45500ms
```

### Debug Panel

Frontend debug info mutatja:
- `Pipeline Latency`: total execution time
- `Workflow`: `{"mode": "simple_pipeline"}` vagy complex steps
- `Next`: tool execution plan (complex only)

---

## 🎯 Recommendation

**Általános használat:**
```
Marketing/IT simple queries → USE_SIMPLE_PIPELINE=True
Complex multi-tool tasks → USE_SIMPLE_PIPELINE=False
```

**Production:**
```
Default: False (complex workflow capabilities)
Override: True per-request header vagy user setting
```

**Load testing:**
```bash
# Benchmark simple
ab -n 100 -c 10 -p query.json \
   -H "X-Pipeline-Mode: simple" \
   http://localhost:8001/api/query/

# Benchmark complex
ab -n 100 -c 10 -p query.json \
   -H "X-Pipeline-Mode: complex" \
   http://localhost:8001/api/query/
```

---

**Verzió:** v2.12.0  
**Utoljára frissítve:** 2026-01-23  
**Kapcsolódó:** [PERFORMANCE_ANALYSIS.md](archive/PERFORMANCE_ANALYSIS.md), [FEATURES.md](FEATURES.md#-strict_rag_mode-feature-flag-new-in-v212)
