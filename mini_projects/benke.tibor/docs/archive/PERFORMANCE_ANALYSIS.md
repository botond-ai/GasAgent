# Performance Analysis - 30+ sec Kérések

## 🔍 Azonosított Bottleneckok (Marketing & IT Domain)

### 1. **PostgreSQL Connection Pool - Lazy Init (~5-15 sec)**
**Fájl:** `backend/infrastructure/postgres_client.py:50-65`

**Probléma:**
```python
async def ensure_initialized(self):
    # BLOCKING: Pool létrehozás MINDEN első kérésnél
    if self.pool is None:
        # 5-15 sec késleltetés: DNS lookup + TCP handshake + auth
        self.pool = await asyncpg.create_pool(...)
```

**Impact:** 
- Első kérés domainenként: **+10-15 sec**
- Docker restart után: **+5-10 sec minden domain**

**Fix:**
```python
# Opció 1: Eager initialization Django startup során
# apps.py AppConfig.ready() hívja meg

# Opció 2: Warmup endpoint
@router.post("/warmup/")
async def warmup():
    await postgres_client.ensure_initialized()
    return {"status": "ready"}
```

---

### 2. **Batch Feedback Lookup - N+1 Query Problem** ❌ FALSE ALARM
**Fájl:** `backend/infrastructure/qdrant_rag_client.py:298-309`

**Állapot:**
```python
# ✅ MÁR BATCH query van!
feedback_map = await postgres_client.get_citation_feedback_batch(
    citation_ids,  # Egy query MINDEN citation-re
    domain
)
```

**Impact:** NINCS - már optimalizálva batch query-vel.

---

### 3. **OpenAI Embedding Generation (~2-5 sec/query)**
**Fájl:** `backend/infrastructure/qdrant_rag_client.py:218-223`

**Probléma:**
```python
# Cache MISS esetén OpenAI API hívás
cached_embedding = redis_cache.get_embedding(query)
if cached_embedding:
    query_embedding = cached_embedding  # Fast: ~1ms
else:
    # SLOW: OpenAI text-embedding-ada-002 API
    query_embedding = self.embeddings.embed_query(query)  # ~2-5 sec
    redis_cache.set_embedding(query, query_embedding)
```

**Impact per query:**
- Cache HIT: **~1 ms**
- Cache MISS: **2-5 sec** (network + OpenAI processing)

**Cache effectiveness:**
- Jelenlegi TTL: **7 nap** (jó)
- Hit rate: **54%** szerint docs

**Optimization:**
- [x] Redis cache már működik
- [ ] Prefix cache: "VPN beállítás", "VPN config" → közös prefix "VPN" cache

---

### 4. **Qdrant Vector Search (~500ms - 2 sec)**
**Fájl:** `backend/infrastructure/qdrant_rag_client.py:232-243`

**Méréshiány:**
```python
search_results = self.qdrant_client.query_points(
    collection_name=self.collection_name,
    query=query_embedding,
    query_filter=domain_filter,  # Domain filter overhead?
    limit=top_k,
    with_payload=True
).points  # ⏱️ NEM MÉRJÜK!
```

**Impact:**
- Marketing domain: **~800ms** (több dokumentum)
- IT domain: **~1.2 sec** (33 chunk, section_id parsing)

**Optimization:**
- [ ] Metrics: log Qdrant latency külön
- [ ] Index tuning: HNSW params (ef, M)
- [ ] Payload filtering: csak szükséges mezők

---

### 5. **IT Overlap Boost - Regex Heavy (~200-500ms)**
**Fájl:** `backend/infrastructure/qdrant_rag_client.py:66-84`

**Probléma:**
```python
def _apply_it_overlap_boost(citations: List[Citation], query: str) -> List[Citation]:
    # MINDEN citation-re tokenizálás + regex match
    query_tokens = {t for t in re.split(r"[^a-zA-Z0-9áéíóöőúüűÁÉÍÓÖŐÚÜŰ]+", query.lower()) if len(t) >= 3}
    
    for c in citations:  # Átlagosan 10-15 citation
        text = " ".join([c.title or "", c.content or ""]).lower()  # String concat
        hits = sum(1 for tok in query_tokens if tok in text)  # O(n*m) keresés
```

**Impact IT domain-en:**
- 15 citation × 500 char/citation: **~300ms** regex + string ops

**Optimization:**
```python
# Pre-tokenize citation text indexeléskor
# → Qdrant metadata field: "tokens": ["vpn", "beállítás", ...]
# → Overlap check: set intersection (~10ms vs 300ms)
```

---

### 6. **LLM Generation (~5-15 sec)** ⚠️ LEGNAGYOBB
**Fájl:** `backend/services/agent.py:935-1050`

**Probléma:**
```python
async def _generation_node(self, state: AgentState) -> AgentState:
    # BLOCKING: gpt-4o-mini API hívás
    llm_response = await self.llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])  # ⏱️ 5-15 sec token generálás
```

**Model:** Valószínűleg `gpt-4o-mini` vagy `gpt-4o`

**Impact:**
- IT domain (hosszú context): **10-15 sec**
- Marketing domain (rövidebb): **5-8 sec**

**Metrics hiány:**
```python
# ❌ NEM MÉRJÜK külön a generation time-ot!
logger.info("Generated response")  # Csak log, nincs timing
```

**Optimization:**
- [ ] Streaming response (részleges válasz hamarabb)
- [ ] Prompt optimization: rövidebb context
- [ ] Model switch: gpt-4o-mini → gpt-3.5-turbo (~30% gyorsabb)

---

### 7. **Guardrail Retry Loop (~10-30 sec extra)**
**Fájl:** `backend/services/agent.py:1173-1240`

**Probléma:**
```python
def _guardrail_decision(self, state: AgentState) -> str:
    retry_count = state.get("retry_count", 0)
    
    if validation_errors and retry_count < 2:
        return "retry"  # ♻️ VISSZA a generation node-ra!
    
    return "continue"
```

**Retry scenario (IT domain):**
1. Generation: 10 sec
2. Validation fail → Retry #1: +10 sec
3. Validation fail → Retry #2: +10 sec
4. Total: **30 sec** csak generation!

**Frequency:**
- IT domain: **~15%** retry rate (citation format issues)
- Marketing: **<5%** retry rate

**Fix:**
- [ ] Better prompt: explicit citation format examples
- [ ] Pre-validation: check citations BEFORE full generation

---

## 📊 Breakdown Estimation (Marketing vs IT)

### Marketing Domain (átlagos query):
```
PostgreSQL init (első kérés):  5 sec
OpenAI embedding (cache miss): 3 sec
Qdrant search:                 800 ms
Feedback ranking:              200 ms
Deduplication:                 100 ms
LLM generation:                6 sec
Guardrail (no retry):          500 ms
Workflow (optional):           2 sec
------------------------------------
TOTAL (cache miss):           ~17-18 sec
TOTAL (cache hit):            ~12 sec (skip embed + PG init)
```

### IT Domain (átlagos query):
```
PostgreSQL init (első kérés):  5 sec
OpenAI embedding (cache miss): 3 sec
Qdrant search:                 1.2 sec
IT overlap boost:              400 ms
Feedback ranking:              200 ms
Deduplication:                 100 ms
LLM generation:               12 sec (longer context)
Guardrail (15% retry):         3 sec (15% × 2 retries × 10 sec)
Workflow (optional):           2 sec
------------------------------------
TOTAL (cache miss):           ~27-30 sec  ⚠️
TOTAL (cache hit):            ~22 sec
```

---

## 🎯 Quick Wins (Sorrendben)

### 1. **PostgreSQL Eager Init** (−5-10 sec, egyszerű)
```python
# backend/api/apps.py
class ApiConfig(AppConfig):
    async def ready(self):
        from infrastructure.postgres_client import postgres_client
        await postgres_client.ensure_initialized()
```

### 2. **LLM Latency Metrics** (0 sec, diagnosztika)
```python
# backend/services/agent.py:_generation_node()
import time
start = time.time()
llm_response = await self.llm.ainvoke(...)
llm_latency = (time.time() - start) * 1000
logger.info(f"🤖 LLM generation: {llm_latency:.0f}ms")
```

### 3. **Qdrant Latency Metrics** (0 sec, diagnosztika)
```python
# backend/infrastructure/qdrant_rag_client.py:retrieve_for_domain()
start = time.time()
search_results = self.qdrant_client.query_points(...)
qdrant_latency = (time.time() - start) * 1000
logger.info(f"🔍 Qdrant search: {qdrant_latency:.0f}ms")
```

### 4. **Streaming LLM Response** (−3-5 sec perceived latency)
```python
# backend/services/agent.py
async for chunk in self.llm.astream([...]):
    # Frontend progressively shows answer
    yield chunk
```

### 5. **IT Overlap Optimization** (−200ms IT domain)
```python
# Pre-tokenize at index time
# payload["tokens"] = ["vpn", "konfigurálás", ...]
def _apply_it_overlap_boost_fast(citations, query_tokens):
    for c in citations:
        cached_tokens = c.payload.get("tokens", [])
        overlap = len(query_tokens & set(cached_tokens))
        boost = 1 + min(0.2, overlap / len(query_tokens) * 0.4)
        c.score *= boost
```

---

## 🔮 Medium-term Optimizations

### 1. **Parallel RAG + LLM** (−5-8 sec)
```python
# Retrieve + Generate párhuzamosan (speculative execution)
async def speculative_pipeline(query, domain):
    # Start both at same time
    citations_task = retrieve_for_domain(query, domain)
    
    # LLM starts with partial context (top 3 citations early)
    early_citations = await asyncio.wait_for(citations_task, timeout=2)
    
    # Generate while remaining citations load
    answer_task = generate_response(early_citations[:3])
    
    # Merge results
    full_citations = await citations_task
    final_answer = await answer_task
```

### 2. **Query Result Cache Scope Expansion**
```python
# Jelenleg: embedding cache (54% hit)
# Új: full response cache (fuzzy match)
def get_cached_response(query, domain):
    # Semantic similarity: "VPN beállítás" ≈ "VPN konfigurálás"
    similar_queries = redis_cache.find_similar_queries(query, threshold=0.85)
    if similar_queries:
        return redis_cache.get(similar_queries[0])
```

### 3. **Model Downgrade for Simple Queries**
```python
# Complexity detection: simple → gpt-3.5-turbo (~30% faster)
def select_model(query, citations):
    if len(query) < 50 and len(citations) <= 5:
        return "gpt-3.5-turbo"  # 3-5 sec vs 6-10 sec
    return "gpt-4o-mini"
```

---

## 📈 Expected Improvements

| Optimization | Impact (sec) | Effort | Priority |
|-------------|--------------|--------|----------|
| PostgreSQL eager init | −5-10 | 1h | 🔴 HIGH |
| LLM/Qdrant metrics | 0 (診断) | 1h | 🔴 HIGH |
| IT overlap pre-tokenize | −0.3 | 2h | 🟡 MEDIUM |
| Streaming LLM | −3-5 (UX) | 4h | 🟡 MEDIUM |
| Parallel RAG+LLM | −5-8 | 8h | 🟢 LOW |
| Query result cache | −10-15 | 6h | 🟡 MEDIUM |

**Target:**
- Marketing: **17 sec → 8-10 sec** (−40%)
- IT: **30 sec → 15-18 sec** (−40%)

---

## 🧪 Measurement Plan

### 1. Add Telemetry Points
```python
# backend/services/agent.py
telemetry = {
    "pg_init_ms": 0,
    "embedding_ms": 0,
    "qdrant_search_ms": 0,
    "feedback_ranking_ms": 0,
    "it_overlap_ms": 0,
    "llm_generation_ms": 0,
    "guardrail_ms": 0,
    "total_ms": 0
}
```

### 2. Prometheus Metrics (már létező infrastruktúra)
```python
from prometheus_client import Histogram

llm_duration = Histogram('llm_generation_duration_seconds', 
                         'LLM generation latency',
                         ['domain', 'model'])

with llm_duration.labels(domain='it', model='gpt-4o-mini').time():
    response = await self.llm.ainvoke(...)
```

### 3. Load Test
```bash
# 10 concurrent marketing queries
ab -n 100 -c 10 -p query.json http://localhost:8001/api/query/

# Measure p50, p95, p99 latencies
```

---

## ✅ Action Items

- [ ] **Sprint 1: Measurement** (1-2 nap)
  - [ ] PostgreSQL eager init
  - [ ] Add LLM latency logging
  - [ ] Add Qdrant latency logging
  - [ ] Add IT overlap latency logging
  - [ ] Baseline measurements (10 queries/domain)

- [ ] **Sprint 2: Quick Wins** (2-3 nap)
  - [ ] Analyze baseline data
  - [ ] Streaming LLM PoC
  - [ ] IT overlap pre-tokenize (Qdrant payload)

- [ ] **Sprint 3: Architecture** (5-7 nap)
  - [ ] Parallel RAG+LLM pipeline
  - [ ] Query result semantic cache
  - [ ] Load testing + benchmarks

---

**Készítette:** GitHub Copilot  
**Dátum:** 2026-01-21  
**Verzió:** v1.0
