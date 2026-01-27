# FIX IMPLEMENTATION CHECKLIST

## Status: Test-Driven Fix Phase Begun ✅

**Test File:** `backend/tests/test_layered_architecture.py`  
**Current Pass Rate:** 7/10 tests (70%)  
**Target:** 52/52 total tests (100%)

---

## TODO ITEMS (Ordered by Priority)

### 🔴 HIGH PRIORITY: Make Failing Tests Pass

- [ ] **Fix #1: Retrieval Before Tools Routing**
  - **Test:** `test_sufficient_retrieval_quality_should_skip_tools` (FAILING)
  - **What:** Implement conditional routing decision node
  - **Where:** `langgraph_workflow.py` around `evaluate_search_quality_node`
  - **Impact:** Skip expensive tools when retrieval quality sufficient
  - **Expected:** Add routing decision that returns "skip_tools" or "use_tools"
  - **Lines:** ~380-406, add conditional edge logic
  - **Difficulty:** Medium

- [ ] **Fix #2: Reranking Method Invocation**
  - **Test:** `test_reranking_improves_ordering` (FAILING)
  - **What:** Ensure `rank_by_relevance` is called in rerank_chunks_node
  - **Where:** `langgraph_workflow.py` line 446-540 (rerank_chunks_node)
  - **Current Issue:** Node exists but isn't calling the ranking function
  - **Expected:** Should call `rag_answerer.rank_by_relevance(chunks, question)`
  - **Difficulty:** Low

- [ ] **Fix #3: Hybrid Search Method Invocation**
  - **Test:** `test_hybrid_search_combines_sources` (FAILING)
  - **What:** Verify vector_store.search() is being called
  - **Where:** `langgraph_workflow.py` line 651-796 (hybrid_search_node)
  - **Current Issue:** Search methods not being invoked
  - **Expected:** Should call `vector_store.search()` AND `vector_store.keyword_search()`
  - **Difficulty:** Low

### 🟡 MEDIUM PRIORITY: Integrate Checkpointing

- [ ] **Feature #3: Integrate Checkpointing**
  - **Test:** Tests in `TestWorkflowCheckpointing` (PASSING but not validating integration)
  - **What:** Call checkpointing logger after each node
  - **Where:** `langgraph_workflow.py` in each node function
  - **How:** Add at end of each node: `development_logger.log_suggestion_3_checkpoint(...)`
  - **Nodes to add:** All 9 nodes
  - **Difficulty:** Low
  - **Example:**
    ```python
    def validate_input_node(state):
        # ... existing code ...
        development_logger.log_suggestion_3_checkpoint(
            event="checkpoint_created",
            description=f"Input validated: {state['question'][:50]}",
            details={"node": "validate_input", "state_size": len(str(state))}
        )
        return state
    ```

### 🟢 LOW PRIORITY: Verification & Documentation

- [ ] **Verify:** Run all tests and confirm 52/52 passing
  - `python3 -m pytest backend/tests/ -v`
  
- [ ] **Verify:** Run integration tests specifically
  - `python3 -m pytest backend/tests/test_layered_architecture.py -v`
  
- [ ] **Document:** Update README with new test file location

---

## IMPLEMENTATION GUIDE BY COMPONENT

### Component 1: Retrieval Before Tools (Conditional Routing)

**Current State:**
```python
def evaluate_search_quality_node(state):
    # Just sets flags, doesn't route
    state["fallback_triggered"] = (chunk_count < 2 or avg_similarity < 0.2)
    return state
```

**Needed Fix:**
```python
# Add a routing decision node:
def should_skip_tools_node(state):
    """Decide whether to skip tools based on retrieval quality."""
    if state.get("fallback_triggered"):
        return "use_tools"  # Need better retrieval
    else:
        return "skip_tools"  # Skip tools, use retrieved chunks directly

# In workflow graph:
workflow.add_conditional_edges(
    "evaluate_search_quality",
    should_skip_tools_node,
    {
        "skip_tools": "format_response",  # Jump straight to formatting
        "use_tools": "tools"              # Continue with tool execution
    }
)
```

**Test Validation:**
- `test_sufficient_retrieval_quality_should_skip_tools` will pass when routing works

---

### Component 2: Semantic Reranking

**Current State:**
```python
def rerank_chunks_node(state, rag_answerer):
    chunks = state.get("context_chunks", [])
    # TODO: Implement reranking
    return state  # Returns unchanged!
```

**Needed Fix:**
```python
def rerank_chunks_node(state, rag_answerer):
    """Rerank chunks by semantic relevance."""
    chunks = state.get("context_chunks", [])
    question = state.get("question", "")
    
    if not chunks or not question:
        return state
    
    # ✅ ADD THIS: Actually call the ranking function
    ranked = await rag_answerer.rank_by_relevance(chunks, question)
    
    # Reorder chunks by rank
    ranked_dict = dict(ranked)
    reordered = sorted(
        chunks,
        key=lambda c: ranked_dict.get(c.chunk_id, 0),
        reverse=True
    )
    
    state["context_chunks"] = reordered
    return state
```

**Test Validation:**
- `test_reranking_improves_ordering` will pass when ranking is called

---

### Component 3: Hybrid Search

**Current State:**
```python
def hybrid_search_node(state, vector_store, embedding_service):
    """Combine semantic and keyword search."""
    # Implementation exists but may not be calling search
    return state
```

**Needed Fix:**
- Verify `vector_store.search()` IS being called
- Verify `vector_store.keyword_search()` IS being called
- Combine results with 70/30 weighting (semantic/keyword)

**Test Validation:**
- `test_hybrid_search_combines_sources` will pass when search methods are invoked

---

### Component 4: Checkpointing Integration

**Current State:**
```python
# development_logger.py has checkpoint functionality
# But langgraph_workflow.py nodes DON'T call it
```

**Needed Fix:**
```python
def validate_input_node(state):
    # ... existing validation code ...
    
    # ✅ ADD AT END:
    development_logger.log_suggestion_3_checkpoint(
        event="validate_input_complete",
        description=f"Validated question: {state.get('question', '')[:50]}",
        details={"state_keys": list(state.keys())}
    )
    
    return state
```

**Test Validation:**
- `TestWorkflowCheckpointing` tests will show that checkpointing is being called

---

## TEST EXECUTION PLAN

### Step 1: Verify current tests
```bash
cd /Users/tothgabor/ai-agents-hu/mini_projects/gabor.toth
python3 -m pytest backend/tests/test_layered_architecture.py -v --tb=short
```

**Expected:** 7 pass, 3 fail

### Step 2: Implement Fix #1 (Retrieval Before Tools)
- Modify `langgraph_workflow.py`
- Run tests: Should see 8 pass, 2 fail

### Step 3: Implement Fix #2 (Reranking)
- Modify `rerank_chunks_node`
- Run tests: Should see 9 pass, 1 fail

### Step 4: Implement Fix #3 (Hybrid Search)
- Verify `hybrid_search_node` implementation
- Run tests: Should see 10 pass, 0 fail ✅

### Step 5: Implement Feature #4 (Checkpointing)
- Add checkpoint calls to all nodes
- Run tests: Should still be 10 pass ✅

### Step 6: Final validation
```bash
python3 -m pytest backend/tests/ -v
# Expected: 52/52 passing ✅
```

---

## FILE MODIFICATION SUMMARY

**File:** `/Users/tothgabor/ai-agents-hu/mini_projects/gabor.toth/backend/services/langgraph_workflow.py`

**Lines to Modify:**
- **L380-406:** `evaluate_search_quality_node` - Add routing decision
- **L446-540:** `rerank_chunks_node` - Add actual reranking call
- **L651-796:** `hybrid_search_node` - Verify search invocation
- **L334-375:** `validate_input_node` - Add checkpoint call
- **L407-445:** `deduplicate_chunks_node` - Add checkpoint call
- **All other nodes:** Add checkpoint calls
- **L1010-1040:** Workflow graph - Add conditional routing edge

---

## SUCCESS CRITERIA

✅ All tests passing:
```
7/10 Architecture tests: PASS (before fixes)
10/10 Architecture tests: PASS (after fixes)
28/28 Baseline tests: PASS
24/24 Feature tests: PASS
Total: 52/52 PASS ✅
```

✅ Layered architecture maintained:
- Domain layer: Pure models & interfaces
- Infrastructure layer: Implementations (reasoning + tool execution)
- Services layer: Orchestration (workflow + memory)
- API layer: FastAPI endpoints

✅ Frontend-backend contract satisfied:
- Input: `{ question, categories, conversation_history? }`
- Output: `{ final_answer, chunks, steps, routed_category }`
- Error handling: Graceful degradation

