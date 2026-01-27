```markdown
# Principles for Refactoring LangGraph Code

When refactoring LangGraph code, I apply the same core principles used for orchestration and agentic systems in general, with additional emphasis on deterministic state handling, clearly scoped node responsibilities, observability, and a strict separation between control flow (the graph) and domain logic. The following principles guide the process.

---

## 1. State Model and Invariants First

**Goal:** The graph execution should be readable and testable as a state machine.

- Define a **single, canonical State** (Pydantic model, dataclass, or TypedDict) that clearly distinguishes:
  - **Inputs** (external/user-provided)
  - **Derived fields** (computed during execution)
  - **Outputs** (final artifacts returned to the caller)
- Explicitly define **invariants**, for example:
  - `messages` is always a list
  - `user_id` is always required
  - `tools_used` is append-only
- Avoid `Dict[str, Any]` as the primary state structure; prefer a structured, versionable schema.

**Refactor smell:** Random keys in state, implicit structure, or different state shapes per node.

---

## 2. Nodes: Single Responsibility, Clean I/O, Explicit Side Effects

**Goal:** Each node should be understandable as a pure function.

- Each node should perform **one clearly defined task**, such as:
  - `rewrite_query`
  - `retrieve`
  - `grade_context`
  - `call_tools`
  - `compose_answer`
- Node input: a slice of the State  
  Node output: **only the State diff** (what it modifies)
- Side effects (DB access, file I/O, network calls) should be:
  - isolated into dedicated gateway nodes, or
  - injected via explicit service dependencies—not hidden inside logic.

**Refactor smell:** A single node handling retrieval, prompt construction, tool dispatch, logging, and persistence.

---

## 3. Separate Control Flow from Domain Logic

**Goal:** The graph definition should read like a flowchart, not business logic.

- `graph.py`:
  - Node registration
  - Edges
  - Conditional routing
- `nodes/` or `services/`:
  - Actual business logic (RAG, scoring, tool execution)
- Routing conditions should be small, explicit predicate functions.

**Refactor smell:** State, nodes, prompts, tools, and routing logic all in one file.

---

## 4. Determinism, Idempotency, and Re-runnability

**Goal:** Given the same input (and seed), execution should be reproducible.

- State should include:
  - `run_id`, `trace_id`, `turn_id`
  - optional `random_seed`
- Nodes should be **idempotent** where possible:
  - Retrieval cached by `query_hash`
  - Deterministic chunking
  - Explicit retry/backoff policies for tool calls

**Refactor smell:** Non-deterministic behavior, hidden global state, time-dependent defaults.

---

## 5. Observability as a First-Class Concern

**Goal:** Debugging and auditing should be straightforward.

- Each node should log:
  - input metadata
  - output metadata (not necessarily full text)
  - execution time
  - errors
- Use a consistent event structure (e.g. `NodeStarted`, `NodeFinished`, `NodeError`).
- Store structured trace data in the state (e.g. `debug_events`), not only free-text logs.

**Refactor smell:** Scattered `print()` statements or inconsistent logging formats.

---

## 6. Explicit Error Handling and Fallback Paths

**Goal:** The graph should degrade gracefully, not collapse.

- Model error and fallback paths explicitly:
  - `if retrieval_empty -> answer_without_context`
  - `if tool_failed -> retry_or_skip_tool`
- Persist structured error information in the state (e.g. `errors: list[ErrorEvent]`).

**Refactor smell:** `try/except` blocks deep inside nodes that swallow errors and return arbitrary strings.

---

## 7. Externalize Prompts, Policies, and Configuration

**Goal:** Reduce risk and friction when making changes.

- Prompt templates in dedicated, versioned modules (e.g. `prompts/`)
- Configuration centralized and validated (Pydantic Settings)
- Policies (e.g. “when should a tool be called?”) separated into policy modules

**Refactor smell:** Inline prompt strings and magic numbers (`k=4`, `threshold=0.72`) scattered across nodes.

---

## 8. Testability: Node Unit Tests and Graph Integration Tests

**Goal:** Refactoring without regressions.

- **Node unit tests**:
  - Fake LLMs, retrievers, and tools
  - Assert state diffs and invariants
- **Graph integration tests**:
  - 2–3 happy paths
  - 2–3 failure paths
  - Snapshot tests on stable parts of the final state

**Refactor smell:** Only end-to-end tests—or no tests at all.

---

## 9. Performance: Parallelism and Batching Where Appropriate

**Goal:** Control latency and cost.

- Batch retrieval and reranking
- Run independent tool calls in parallel (respecting rate limits)
- Minimize LLM calls (e.g. only rewrite queries when necessary)

**Refactor smell:** Every request always triggers the same fixed set of LLM calls.

---

## 10. Evolvability: Versioned State and Compatibility Layers

**Goal:** Enable safe future changes.

- Include a `state_version` field
- Provide migration functions for state schema changes
- Handle deprecated fields via aliases or compatibility layers

---

## Practical Audit Checklist

When reviewing LangGraph code, I start with these questions:

1. Is there a clear, typed State with defined invariants?
2. Are nodes small (≈20–50 lines) and single-responsibility?
3. Are routing conditions isolated as predicates?
4. Are side effects clearly separated?
5. Is node-level tracing/logging present, with timing?
6. Are errors branched explicitly, not swallowed?
7. Are prompts, config, and policies externalized?
8. Are there at least minimal unit and integration tests?
9. Are LLM and tool calls justified and minimized?
10. Can I add a new node without modifying five others?

---

If you share a small excerpt (State definition, 2–3 nodes, and graph wiring), I can apply these principles directly:
- identify the main sources of complexity and risk,
- propose concrete module boundaries,
- and provide a target architecture (file structure, node interfaces, and state schema).
```
