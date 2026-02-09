# KnowledgeRouter v2.5 - Guardrail & Telemetry Enhancement

**Release Date:** January 9, 2026  
**Version:** 2.5.0  
**Status:** In Development (Phase 1.1 Complete)

## 🎯 Release Objectives

Improve response quality and observability by adding citation validation and structured telemetry collection.

---

## ✅ Completed (Phase 1.1)

### 🛡️ Guardrail Node Implementation

#### Features
- **Citation Validation**: Enforces `[IT-KB-XXX]` format for IT domain responses
- **Retry Logic**: Automatic regeneration on validation failure (max 2 attempts)
- **Graceful Degradation**: Best-effort answer if retries exhausted
- **Extensible Design**: Easy to add domain-specific validation rules
- **Non-Blocking**: Quality checks don't prevent user response

#### Integration
- **Graph Position**: `generation` → `guardrail` → `feedback_metrics`
- **State Fields**: Added `validation_errors`, `retry_count`, `llm_response` to AgentState
- **Conditional Routing**: Can route back to generation for retries

#### Test Coverage
- **11 Unit Tests**: 100% pass rate
  ```
  TestGuardrailNodeValidation (4 tests)
    - test_it_domain_with_valid_citations ✅
    - test_it_domain_missing_citations ✅
    - test_non_it_domain_skips_validation ✅
    - test_hallucination_detection ✅ (framework only, LLM call disabled)
  
  TestGuardrailDecision (4 tests)
    - test_decision_retry_when_errors_and_retries_available ✅
    - test_decision_continue_when_no_errors ✅
    - test_decision_continue_when_max_retries_reached ✅
    - test_retry_count_progression ✅
  
  TestGuardrailEdgeCases (3 tests)
    - test_empty_citations_list ✅
    - test_multiple_citations_in_response ✅
    - test_state_initialization ✅
  ```

#### Code Changes
- **backend/services/agent.py**
  - Added `_guardrail_node()` async method (55 lines)
  - Added `_guardrail_decision()` routing method (13 lines)
  - Updated AgentState with validation fields
  - Updated graph.add_node() and graph.add_edge() for guardrail
  
- **backend/tests/test_guardrail_node.py** (NEW)
  - 309 lines, 11 unit tests
  - Mock LLM response handling
  - Full edge case coverage

### 🔧 Infrastructure Changes

#### Windows Compatibility
- **uvloop**: Commented out in `requirements.txt` (Windows incompatible)
- **asyncio**: Uses standard library instead
- **pytest-asyncio**: Added for async test support
- **pytest.ini**: Updated with `asyncio_mode = auto`

#### Dependency Updates
- **qdrant-client**: 1.7.0 → 1.16.2 (latest stable)
- **beautifulsoup4**: Confirmed present (4.12.3)
- **asyncpg**: 0.29.0 (PostgreSQL async driver)
- **pytest-asyncio**: Latest (async test support)

#### Documentation Updates
- **INSTALLATION.md**: Added Windows-specific notes
- **FEATURES.md**: Added Guardrail Node section, updated LangGraph workflow (4 → 6 nodes)
- **README.md**: Updated workflow description (4 → 6 nodes), added v2.5 features

---

## 🚧 In Progress (Phase 1.2-1.3)

### Feedback Metrics Node (Phase 1.2)
- [ ] Implement `_feedback_metrics_node()` async method
- [ ] Collect: retrieval quality (top-1 score, dedup count), LLM latency, cache hit rate, token usage
- [ ] Non-blocking telemetry (failures don't stop workflow)
- [ ] Integration tests for metrics collection
- [ ] PostgreSQL feedback persistence

### Message Deduplication Reducer (Phase 1.3)
- [ ] SHA256-based message hashing
- [ ] Implement custom reducer for AgentState.messages
- [ ] Prevent duplicate messages in state
- [ ] Unit tests for dedup logic

### Graph Refactoring (Phase 1.4)
- [ ] Update graph.add_node() for feedback_metrics
- [ ] Update graph.add_edge() for new node connections
- [ ] Test full 6-node pipeline
- [ ] E2E integration test

---

## 📊 Metrics & Testing

### Coverage Analysis
- **test_guardrail_node.py**: 11 tests, 100% pass rate
- **Guardrail Node Lines**: 68 LOC
- **Test Code**: 309 LOC
- **Test-to-Code Ratio**: 4.5:1 (excellent coverage)

### Quality Gate
- ✅ All tests pass
- ✅ No external API calls (mocked)
- ✅ Async/await pattern compliance
- ⏳ Coverage percentage TBD (Phase 1.4+)

---

## 🔄 Workflow Architecture (Post-v2.5)

```
┌─────────────────────────────────────────────────────┐
│          LangGraph StateGraph (6 nodes)             │
└─────────────────────────────────────────────────────┘

1. intent_detection
   ↓
2. retrieval (Qdrant RAG)
   ↓
3. generation (LLM response)
   ↓
4. guardrail (validation, retry)
   ├─ If validation fails & retries available: → back to 3
   ├─ If max retries or no errors: → 5
   ↓
5. feedback_metrics (telemetry collection - NON-BLOCKING)
   ↓
6. execute_workflow (HR/IT automation)
   ↓
END
```

---

## 🎓 Key Learnings

### Hallucination Detection
- Simple word-overlap heuristics are **too noisy** for real-world LLM outputs
- Paraphrases pass through despite being semantically valid
- **Solution**: Disabled automatic detection, kept framework for future semantic validation
- **Proper detection** would require LLM embeddings or extra LLM call (cost/latency tradeoff)

### Async Test Patterns
- **pytest-asyncio**: Required `asyncio_mode = auto` in pytest.ini
- **Mock state management**: Careful null-checking for optional fields
- **Error propagation**: Validation errors accumulate, don't block immediately

### LangGraph Conditional Routing
- **String-based edges**: `graph.add_conditional_edges()` requires function returning string
- **Decision routing**: `_guardrail_decision()` determines "retry" vs "continue" path
- **State mutation**: Be careful with mutable objects in state during retries

---

## 📝 Next Steps (Phase 2)

1. **Implement Feedback Metrics Node** (1-2 days)
   - Latency measurement
   - Cache hit tracking
   - Token usage calculation
   
2. **Add Memory Strategies** (2-4 days)
   - Rolling vs Summary modes
   - Conditional routing based on message count
   
3. **QueryRewrite Node** (2-3 days)
   - Query optimization before retrieval
   - Acronym expansion, ambiguity clarification

4. **Explicit State Channels** (3-5 days)
   - Separate: messages, summary, facts, profile, trace
   - Custom reducers for deterministic merging

---

## 🔗 References

- **Test File**: [backend/tests/test_guardrail_node.py](../backend/tests/test_guardrail_node.py)
- **Implementation**: [backend/services/agent.py](../backend/services/agent.py) (lines 295-365)
- **External Reference**: [adrgul/ai_agent_tutorial](https://github.com/adrgul/ai_agent_tutorial) (guardrail pattern inspiration)

---

**Created By**: KnowledgeRouter Development Team  
**Review Status**: Phase 1.1 Complete, Ready for Phase 1.2
