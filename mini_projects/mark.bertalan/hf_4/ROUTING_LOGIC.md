# Graph Routing Logic - How the Planner Controls Execution

This document explains how the planner node's decisions actually control the graph execution flow.

## Overview

The planner node analyzes the query and sets state variables that are **actively used** by routing functions to determine which nodes execute. This allows the graph to dynamically adapt to different query types.

## State Variables Set by Planner

The planner sets these key state variables:

```python
state["plan_needs_rag"] = True/False           # Should we do RAG retrieval?
state["plan_is_jira_confirmation"] = True/False  # Is this a yes/no response?
state["plan_intent"] = "search|create_ticket|..."  # What does user want?
state["execution_plan"]["parameters"]["skip_retrieval"] = True/False
```

## Routing Decision Points

### 1. After `detect_confirmation` Node

**Routing Function**: `route_after_confirmation(state)`

This is the main orchestration point that uses the planner's decisions:

```python
def route_after_confirmation(state):
    # Priority 1: Check if user is confirming/declining Jira
    if state.get("jira_confirmation_detected"):
        if state.get("create_jira_task"):
            return "create_jira"  # → create_jira → send_teams → format → END
        else:
            return "format"  # → format → END

    # Priority 2: Check planner's decision - does this need RAG?
    if not state.get("plan_needs_rag", True):
        state["skip_retrieval"] = True
        return "format"  # → format → END (skips all RAG)

    # Priority 3: Check if planner wants to skip retrieval but use LLM
    if state["execution_plan"]["parameters"]["skip_retrieval"]:
        state["skip_retrieval"] = True
        return "direct_answer"  # → generate → evaluate_jira → format → END

    # Default: Full RAG flow
    return "rag_flow"  # → embed → retrieve → build_context → ...
```

#### Possible Routes

1. **`create_jira`**: User confirmed Jira ticket creation
   - Flow: `create_jira` → `send_teams` → `format` → END

2. **`format`**: User declined Jira OR planner says skip RAG entirely
   - Flow: `format` → END
   - Response node generates a simple fallback message

3. **`direct_answer`**: Planner says skip retrieval but use LLM
   - Flow: `generate` → `evaluate_jira` → `format` → END
   - LLM generates answer without document context

4. **`rag_flow`**: Normal RAG pipeline
   - Flow: `embed` → `retrieve` → `build_context` → `generate` → `evaluate_jira` → `format` → END

### 2. After `build_context` Node

**Routing Function**: `should_generate_answer(state)`

```python
def should_generate_answer(state):
    if state.get("skip_llm", False):
        return "format"  # Skip to format (retrieval-only mode)
    return "generate"  # Continue to LLM generation
```

This routing point respects the `skip_llm` parameter (set by planner or application).

## Example Scenarios

### Scenario 1: Simple Confirmation Query

**User Query**: "yes"

**Planner Decision**:
```json
{
  "query_type": "confirmation",
  "plan_needs_rag": false,
  "plan_is_jira_confirmation": true
}
```

**Execution Flow**:
```
preprocess → plan → detect_confirmation
                    ↓ (jira_confirmation_detected=true)
                    create_jira → send_teams → format → END
```

**Nodes Skipped**: embed, retrieve, build_context, generate, evaluate_jira

---

### Scenario 2: Query That Doesn't Need RAG

**User Query**: "What's your name?"

**Planner Decision**:
```json
{
  "query_type": "informational",
  "plan_needs_rag": false,
  "reasoning": "Simple meta-question that doesn't require document retrieval"
}
```

**Execution Flow**:
```
preprocess → plan → detect_confirmation
                    ↓ (plan_needs_rag=false)
                    format → END
```

**Nodes Skipped**: embed, retrieve, build_context, generate, evaluate_jira

**Response**: Format node generates a simple fallback response.

---

### Scenario 3: Followup Question (Skip Retrieval, Use LLM)

**User Query**: "Can you explain that in simpler terms?"

**Planner Decision**:
```json
{
  "query_type": "followup",
  "plan_needs_rag": true,
  "parameters": {
    "skip_retrieval": true
  },
  "reasoning": "Followup to previous answer, conversation history has context"
}
```

**Execution Flow**:
```
preprocess → plan → detect_confirmation
                    ↓ (skip_retrieval=true)
                    generate → evaluate_jira → format → END
```

**Nodes Skipped**: embed, retrieve, build_context

**Behavior**: LLM generates answer using conversation history, no new documents retrieved.

---

### Scenario 4: Issue Report (Full RAG)

**User Query**: "The deployment process is failing with permission errors"

**Planner Decision**:
```json
{
  "query_type": "issue_report",
  "plan_needs_rag": true,
  "parameters": {
    "skip_retrieval": false,
    "k": 5
  },
  "routing_decisions": {
    "needs_jira_evaluation": true
  }
}
```

**Execution Flow**:
```
preprocess → plan → detect_confirmation
                    ↓ (plan_needs_rag=true, skip_retrieval=false)
                    embed → retrieve → build_context → generate → evaluate_jira → format → END
```

**Nodes Skipped**: None (full pipeline)

**Behavior**: Complete RAG flow with Jira evaluation.

---

## Logging

Each routing decision is logged for debugging:

```
INFO - Routing: plan_needs_rag=False, plan_intent=answer_directly
INFO - Routing: Planner says skip RAG → format

INFO - Routing: plan_needs_rag=True, plan_intent=search
INFO - Routing: Planner says skip retrieval, direct to LLM → direct_answer

INFO - Routing: plan_needs_rag=True, plan_intent=search
INFO - Routing: Normal RAG flow → embed
```

## Response Node Handling

The `format_response_node` validates fields based on which path was taken:

```python
# Full RAG validation
if plan_needs_rag and not skip_retrieval:
    required_fields = ["query_id", "query", "cosine_results", "knn_results"]
    # Validate all fields

# Partial RAG validation (direct_answer path)
elif skip_retrieval:
    # Only validate query fields, not retrieval results

# No RAG validation
elif not plan_needs_rag:
    # Generate simple fallback response if needed
```

## Benefits of This Architecture

1. **Performance Optimization**: Skip expensive operations (embeddings, vector search) when not needed
2. **Cost Reduction**: Fewer API calls to OpenAI when simple queries don't need RAG
3. **Better UX**: Faster responses for simple queries
4. **Flexibility**: Easy to add new routing logic based on query analysis
5. **Debugging**: Clear logs show why each routing decision was made

## Testing Routing Logic

### Test 1: Verify RAG Skip

```python
# Query that shouldn't need RAG
query = "What's your name?"

# Check logs for:
# "Routing: Planner says skip RAG → format"

# Verify nodes skipped:
assert "embedding_ms" not in state["step_timings"]
assert "retrieval_ms" not in state["step_timings"]
assert "planning_ms" in state["step_timings"]
assert "format" was called
```

### Test 2: Verify Direct Answer

```python
# Followup query
query = "Explain more about that"

# Check logs for:
# "Routing: Planner says skip retrieval, direct to LLM → direct_answer"

# Verify nodes executed:
assert "generation_ms" in state["step_timings"]
assert "retrieval_ms" not in state["step_timings"]
```

### Test 3: Verify Full RAG

```python
# Issue report
query = "The API is returning 500 errors"

# Check logs for:
# "Routing: Normal RAG flow → embed"

# Verify all nodes executed:
assert "planning_ms" in state["step_timings"]
assert "embedding_ms" in state["step_timings"]
assert "retrieval_ms" in state["step_timings"]
assert "generation_ms" in state["step_timings"]
```

## Common Questions

**Q: What happens if the planner makes a wrong decision?**

A: The planner's `confidence` score indicates certainty. Low confidence (<0.5) means the decision is uncertain. You can add logic to always use full RAG when confidence is low.

**Q: Can I override the planner's decision?**

A: Yes, you can set `plan_needs_rag=True` manually in the application code before invoking the graph:

```python
initial_state = {
    "query": text,
    "plan_needs_rag": True,  # Force RAG
    ...
}
```

**Q: How do I add a new routing path?**

A:
1. Add a new return value in `route_after_confirmation()`
2. Add the mapping in `workflow.add_conditional_edges()`
3. Create the new node if needed

```python
# In route_after_confirmation()
if state.get("plan_intent") == "my_new_intent":
    return "my_new_path"

# In graph builder
workflow.add_conditional_edges(
    "detect_confirmation",
    route_after_confirmation,
    {
        "create_jira": "create_jira",
        "format": "format",
        "rag_flow": "embed",
        "direct_answer": "generate",
        "my_new_path": "my_new_node"  # Add here
    }
)
```

---

## Summary

The planner node is a **true orchestrator** - its decisions directly control graph execution through routing functions. The key variables (`plan_needs_rag`, `skip_retrieval`, etc.) are checked at routing decision points to determine which nodes run.

This architecture enables:
- ✅ Dynamic graph execution based on query analysis
- ✅ Performance optimization (skip unnecessary nodes)
- ✅ Clear decision logging for debugging
- ✅ Flexible extension with new routing logic
