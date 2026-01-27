# Complete Graph Flow with Planner Routing

## Full Graph Visualization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RAG GRAPH WITH PLANNER                              │
└─────────────────────────────────────────────────────────────────────────────┘

                                START
                                  ↓
                           ┌──────────────┐
                           │  preprocess  │  - Validate query
                           │              │  - Generate UUID
                           └──────┬───────┘  - Initialize state
                                  ↓
                           ┌──────────────┐
                           │     plan     │  - Analyze query type
                           │ (Orchestr.)  │  - Determine execution path
                           └──────┬───────┘  - Set routing decisions
                                  ↓
                    ┌─────────────────────────┐
                    │  detect_confirmation    │  - Check for yes/no
                    │                         │  - Check pending Jira
                    └────────┬────────────────┘
                             ↓
        ╔════════════════════════════════════════════════════════╗
        ║         ROUTING DECISION POINT 1                       ║
        ║         (route_after_confirmation)                     ║
        ║                                                        ║
        ║  Uses: plan_needs_rag, skip_retrieval,                ║
        ║        jira_confirmation_detected                     ║
        ╚════════════════════════════════════════════════════════╝
                             ↓
        ┌────────────────────┼────────────────────┬───────────────────┐
        │                    │                    │                   │
        ↓                    ↓                    ↓                   ↓
   [Jira YES]          [Jira NO]           [Skip RAG]         [Normal RAG]
        │                    │                    │                   │
        ↓                    ↓                    ↓                   ↓
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │ create_jira  │    │    format    │    │    format    │    │    embed     │
 │              │    │              │    │  (fallback)  │    │              │
 └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
        │                   │                    │                   │
        ↓                   │                    │                   ↓
 ┌──────────────┐           │                    │            ┌──────────────┐
 │  send_teams  │           │                    │            │   retrieve   │
 │              │           │                    │            │              │
 └──────┬───────┘           │                    │            └──────┬───────┘
        │                   │                    │                   │
        ↓                   │                    │                   ↓
 ┌──────────────┐           │                    │            ┌──────────────┐
 │    format    │           │                    │            │build_context │
 │              │           │                    │            │              │
 └──────┬───────┘           │                    │            └──────┬───────┘
        │                   │                    │                   │
        │                   │                    │    ╔══════════════════════════╗
        │                   │                    │    ║ ROUTING DECISION POINT 2 ║
        │                   │                    │    ║ (should_generate_answer) ║
        │                   │                    │    ║                          ║
        │                   │                    │    ║ Uses: skip_llm          ║
        │                   │                    │    ╚══════════════════════════╝
        │                   │                    │                   │
        │                   │                    │         ┌─────────┴────────┐
        │                   │                    │         │                  │
        │                   │                    │         ↓                  ↓
        │                   │                    │  ┌──────────────┐  ┌──────────────┐
        │                   │                    │  │   generate   │  │    format    │
        │                   │                    │  │              │  │  (retrieval- │
        │                   │                    │  └──────┬───────┘  │   only)      │
        │                   │                    │         │          └──────┬───────┘
        │                   │                    │         ↓                 │
        │                   │                    │  ┌──────────────┐        │
        │                   │                    │  │evaluate_jira │        │
        │                   │                    │  │              │        │
        │                   │                    │  └──────┬───────┘        │
        │                   │                    │         │                │
        │                   │                    │         ↓                │
        │                   │                    │  ┌──────────────┐        │
        │                   │                    │  │    format    │        │
        │                   │                    │  │              │        │
        │                   │                    │  └──────┬───────┘        │
        │                   │                    │         │                │
        └───────────────────┴────────────────────┴─────────┴────────────────┘
                                                 ↓
                                               END


┌─────────────────────────────────────────────────────────────────────────────┐
│                      ADDITIONAL PATH: DIRECT ANSWER                          │
│                  (When skip_retrieval=True but needs LLM)                   │
└─────────────────────────────────────────────────────────────────────────────┘

                      detect_confirmation
                             ↓
                    [Skip Retrieval Path]
                             ↓
                      ┌──────────────┐
                      │   generate   │  - LLM with empty context
                      │              │  - Uses conversation history
                      └──────┬───────┘
                             ↓
                      ┌──────────────┐
                      │evaluate_jira │
                      │              │
                      └──────┬───────┘
                             ↓
                      ┌──────────────┐
                      │    format    │
                      │              │
                      └──────┬───────┘
                             ↓
                            END
```

## Path Summary

### Path 1: Jira Ticket Creation (User Confirmed)
```
preprocess → plan → detect_confirmation → create_jira → send_teams → format → END
```
**Triggers**: User says "yes" to pending Jira suggestion
**Nodes**: 6 total
**Duration**: ~500-1500ms (depending on Jira/Teams APIs)

### Path 2: Jira Declined
```
preprocess → plan → detect_confirmation → format → END
```
**Triggers**: User says "no" to pending Jira suggestion
**Nodes**: 4 total
**Duration**: ~100-300ms (very fast)

### Path 3: Planner Skips RAG (Simple Query)
```
preprocess → plan → detect_confirmation → format → END
```
**Triggers**: `plan_needs_rag = False`
**Nodes**: 4 total
**Duration**: ~300-500ms (includes planner LLM call)
**Example**: "What's your name?", "Hello", meta-questions

### Path 4: Direct Answer (Skip Retrieval)
```
preprocess → plan → detect_confirmation → generate → evaluate_jira → format → END
```
**Triggers**: `skip_retrieval = True` (followup questions)
**Nodes**: 6 total
**Duration**: ~1000-2000ms (LLM generation only)
**Example**: "Explain more", "Can you clarify?"

### Path 5: Full RAG Pipeline
```
preprocess → plan → detect_confirmation → embed → retrieve → build_context →
generate → evaluate_jira → format → END
```
**Triggers**: `plan_needs_rag = True`, `skip_retrieval = False`
**Nodes**: 10 total
**Duration**: ~2000-5000ms (full pipeline)
**Example**: "What's the vacation policy?", "How do I deploy?"

### Path 6: Retrieval-Only (No LLM)
```
preprocess → plan → detect_confirmation → embed → retrieve → build_context →
format → END
```
**Triggers**: `skip_llm = True`
**Nodes**: 7 total
**Duration**: ~500-1000ms
**Usage**: Rare, for when you only want to see retrieved documents

## Routing Decision Logic

### Decision Point 1: After `detect_confirmation`

```python
if jira_confirmation_detected:
    if user_said_yes:
        return "create_jira"  # Path 1
    else:
        return "format"        # Path 2

if not plan_needs_rag:
    return "format"            # Path 3

if skip_retrieval:
    return "direct_answer"     # Path 4

return "rag_flow"              # Path 5 or 6
```

### Decision Point 2: After `build_context`

```python
if skip_llm:
    return "format"    # Path 6 (retrieval-only)

return "generate"      # Path 5 (full RAG)
```

## Node Execution Matrix

| Node | Path 1 | Path 2 | Path 3 | Path 4 | Path 5 | Path 6 |
|------|--------|--------|--------|--------|--------|--------|
| preprocess | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| plan | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| detect_confirmation | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| create_jira | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| send_teams | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| embed | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| retrieve | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| build_context | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| generate | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ |
| evaluate_jira | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ |
| format | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

✓ = Executed, ✗ = Skipped

## Performance Comparison

| Path | Typical Duration | API Calls | Cost |
|------|-----------------|-----------|------|
| Path 1 (Jira + Teams) | 500-1500ms | Jira API, Teams API | $ |
| Path 2 (Decline) | 100-300ms | None | Free |
| Path 3 (Skip RAG) | 300-500ms | 1 LLM (planner) | $ |
| Path 4 (Direct Answer) | 1000-2000ms | 2 LLM (planner + generate) | $$ |
| Path 5 (Full RAG) | 2000-5000ms | 3 LLM (planner + embed + generate) | $$$ |
| Path 6 (Retrieval Only) | 500-1000ms | 2 LLM (planner + embed) | $$ |

## State Variables by Path

### Path 1 (Jira Confirmed)
```python
{
  "jira_confirmation_detected": True,
  "create_jira_task": True,
  "jira_task_key": "DEV-123",
  "jira_task_url": "https://...",
  "teams_notification": {"sent": True, "channel": "dev"}
}
```

### Path 3 (Skip RAG)
```python
{
  "plan_needs_rag": False,
  "plan_query_type": "informational",
  "plan_reasoning": "Simple meta-question...",
  "skip_retrieval": True,
  "generated_answer": "I understand you're asking..." # Fallback
}
```

### Path 4 (Direct Answer)
```python
{
  "plan_needs_rag": True,
  "skip_retrieval": True,
  "retrieved_context": [],  # Empty
  "generated_answer": "Based on our previous conversation..."
}
```

### Path 5 (Full RAG)
```python
{
  "plan_needs_rag": True,
  "skip_retrieval": False,
  "query_embedding": [...],
  "cosine_results": [...],
  "knn_results": [...],
  "retrieved_context": ["chunk1", "chunk2", ...],
  "generated_answer": "Based on the documentation...",
  "jira_suggested": True  # Maybe
}
```

## Debugging Tips

### Check Which Path Was Taken

Look for these log messages:

```
# Path 1
INFO - Routing: User confirmed Jira → create_jira

# Path 2
INFO - Routing: User declined Jira → format

# Path 3
INFO - Routing: Planner says skip RAG → format
INFO - Planner skipped RAG - no retrieval validation needed

# Path 4
INFO - Routing: Planner says skip retrieval, direct to LLM → direct_answer

# Path 5
INFO - Routing: Normal RAG flow → embed
```

### Verify Node Execution

Check `step_timings` in final state:

```python
# Path 3 (Skip RAG)
assert "planning_ms" in state["step_timings"]
assert "embedding_ms" not in state["step_timings"]

# Path 4 (Direct Answer)
assert "generation_ms" in state["step_timings"]
assert "retrieval_ms" not in state["step_timings"]

# Path 5 (Full RAG)
assert all(k in state["step_timings"] for k in
    ["planning_ms", "embedding_ms", "retrieval_ms", "generation_ms"])
```

## Adding New Paths

To add a new execution path:

1. **Add routing logic** in `route_after_confirmation()`:
   ```python
   if state.get("my_condition"):
       return "my_new_path"
   ```

2. **Add edge mapping** in graph builder:
   ```python
   workflow.add_conditional_edges(
       "detect_confirmation",
       route_after_confirmation,
       {
           "my_new_path": "my_new_node"
       }
   )
   ```

3. **Create the node** if it doesn't exist

4. **Update planner** to set the condition based on query analysis

---

This routing architecture provides maximum flexibility while maintaining clear decision logic and excellent debugging capabilities.
