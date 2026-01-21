# Fázis 1-2 Végrehajtási Terv (4-5 hét)

**Cél:** Complex Agent capabilities alapok + Tool Executor Loop MVP  
**Kimenet:** 7-node → 11-node LangGraph workflow  
**Tesztek:** +80-100 új test (test coverage 95%+)

---

## 🎯 Sprint 1: Plan Node (3-4 nap)

### S1.1 - ExecutionPlan & ToolStep Models
**Fájl:** `backend/domain/llm_outputs.py`
- [ ] ExecutionPlan Pydantic model
  ```python
  class ToolStep(BaseModel):
      step_id: int
      tool_name: str
      description: str
      arguments: Dict[str, Any]
      depends_on: List[int] = []  # Parallel execution support
      required: bool = True
  
  class ExecutionPlan(BaseModel):
      reasoning: str = Field(min_length=10, max_length=1000)
      steps: List[ToolStep] = Field(min_items=1, max_items=5)
      estimated_cost: float = Field(ge=0)
      estimated_time_ms: int = Field(ge=0)
  ```
- [ ] Validáció: max 5 steps (prevent over-planning), min 1 step
- [ ] Cost estimation field (előrejelzés)

### S1.2 - Plan Node Implementation
**Fájl:** `backend/services/agent.py`
- [ ] `_plan_node()` implementáció (async)
- [ ] Plan prompt template (CoT guidance)
  ```
  Instruction template:
  Query: {query}
  Domain: {domain}
  Available tools: {tool_list}
  
  Think step-by-step:
  1. What information do I need to answer?
  2. Which tools should I use and in what order?
  3. Are there dependencies between steps?
  4. What's the estimated cost and time?
  
  Return structured execution plan.
  ```
- [ ] LLM call: `llm.with_structured_output(ExecutionPlan)`
- [ ] Error handling: Non-blocking, fallback to RAG-only if plan fails

### S1.3 - Graph Integration
**Fájl:** `backend/services/agent.py`
- [ ] Add plan_node to graph
- [ ] Update edges: `intent_detection → plan_node → tool_selection`
- [ ] State update: `state["execution_plan"]`

### S1.4 - Testing
**Fájl:** `backend/tests/test_plan_node.py` (NEW)
- [ ] Test: Plan node generates valid ExecutionPlan
- [ ] Test: Plan respects max 5 steps limit
- [ ] Test: Plan includes all required fields
- [ ] Test: Plan with dependencies (parallel tool support)
- [ ] Test: Plan error handling (LLM fail → fallback)
- [ ] Mock LLM: 3 scenarios (simple, complex, error)

**Checkpoint:** Plan Node ready & tested ✅

---

## 🎯 Sprint 2: Tool Selection Node (3-4 nap)

### S2.1 - ToolSelection & ToolCall Models
**Fájl:** `backend/domain/llm_outputs.py`
- [ ] ToolSelection Pydantic model
  ```python
  class ToolCall(BaseModel):
      tool_name: Literal["rag", "jira_create", "email", "calculator"]
      arguments: Dict[str, Any]
      confidence: float = Field(ge=0.0, le=1.0)
  
  class ToolSelection(BaseModel):
      reasoning: str = Field(min_length=20, max_length=500)
      selected_tools: List[ToolCall] = Field(min_items=1, max_items=3)
      fallback_plan: str = Field(description="If selected tools unavailable")
  ```
- [ ] Validation: max 3 tools, confidence >= 0.5
- [ ] Fallback strategy field

### S2.2 - Tool Selection Node
**Fájl:** `backend/services/agent.py`
- [ ] `_tool_selection_node()` implementáció
- [ ] Tool availability check (which tools are enabled?)
- [ ] Tool selection prompt (with available tools list)
- [ ] LLM call: `llm.with_structured_output(ToolSelection)`
- [ ] Router logic: Based on selected_tools → different paths

### S2.3 - Conditional Routing
**Fájl:** `backend/services/agent.py`
- [ ] Update graph edges:
  ```
  plan_node → select_tools
  select_tools → conditional_edges:
    - "rag_only": retrieval
    - "rag_and_tools": tool_executor
    - "tools_only": tool_executor
  ```
- [ ] Conditional edge function: `_tool_selection_decision()`
- [ ] Route names: rag_only, rag_and_tools, tools_only

### S2.4 - Testing
**Fájl:** `backend/tests/test_tool_selection.py` (NEW)
- [ ] Test: Select RAG tool
- [ ] Test: Select multiple tools
- [ ] Test: Tool not available → fallback
- [ ] Test: Conditional routing works
- [ ] Test: Confidence threshold enforcement
- [ ] Mock LLM: 4 scenarios (rag, multi-tool, unavailable, error)

Megjegyzés: A `tool_executor` jelenleg minimális implementációval rendelkezik (pass-through és naplózás), a teljes iteratív végrehajtás a következő sprintben (`tool_executor_loop`).

**Checkpoint:** Tool Selection ready & tested ✅

---

## 🎯 Sprint 3: Tool Registry (4-5 nap)

### S3.1 - Tool Registry Foundation
**Fájl:** `backend/infrastructure/tool_registry.py` (NEW)
- [ ] ToolRegistry class
  ```python
  class ToolRegistry:
      def __init__(self):
          self.tools: Dict[str, Tool] = {}
          self.logger = logging.getLogger(__name__)
      
      def register(self, name: str, description: str, schema: Dict):
          def decorator(func):
              self.tools[name] = Tool(name, description, schema, func)
              return func
          return decorator
      
      async def execute(self, name: str, args: Dict) -> Any:
          if name not in self.tools:
              raise ValueError(f"Tool {name} not found")
          return await self.tools[name].execute(**args)
      
      def get_tool_descriptions(self) -> str:
          return "\n".join([
              f"- {tool.name}: {tool.description}"
              for tool in self.tools.values()
          ])
  ```

### S3.2 - Tool Implementations
**Fájl:** `backend/infrastructure/tool_registry.py`
- [ ] RAG Tool registration
  ```python
  @tool_registry.register(
      "rag_search",
      "Search knowledge base documents",
      schema={...}
  )
  async def rag_search(query: str, domain: str, top_k: int = 5):
      return await qdrant_client.retrieve_for_domain(domain, query, top_k)
  ```
- [ ] Jira Tool registration
  ```python
  @tool_registry.register("jira_create", "Create IT support ticket", schema={...})
  async def jira_create(summary: str, description: str, priority: str = "Medium"):
      return await atlassian_client.create_ticket(...)
  ```
- [ ] Calculator Tool (mock, for testing)
  ```python
  @tool_registry.register("calculator", "Perform calculations", schema={...})
  async def calculator(expression: str) -> Dict:
      # Parse & evaluate safely
      return {"result": eval_safe(expression)}
  ```
- [ ] Email Tool (mock, for testing)
  ```python
  @tool_registry.register("email_send", "Send email", schema={...})
  async def email_send(to: str, subject: str, body: str) -> Dict:
      # Mock: just log
      return {"status": "sent", "message_id": "mock123"}
  ```

### S3.3 - Schema Extraction
**Fájl:** `backend/infrastructure/tool_registry.py`
- [ ] Auto-generate JSON schema from type hints
  ```python
  def extract_schema(func: Callable) -> Dict:
      sig = inspect.signature(func)
      properties = {}
      required = []
      for param_name, param in sig.parameters.items():
          # Extract type hint → JSON schema
          properties[param_name] = type_to_schema(param.annotation)
          if param.default == inspect.Parameter.empty:
              required.append(param_name)
      return {
          "type": "object",
          "properties": properties,
          "required": required
      }
  ```

### S3.4 - Tool Registry Initialization
**Fájl:** `backend/core/settings.py` (or new file)
- [ ] Singleton: `tool_registry = ToolRegistry()`
- [ ] Initialize all tools at startup
- [ ] Tool health check (optional)

### S3.5 - Testing
**Fájl:** `backend/tests/test_tool_registry.py` (NEW)
- [ ] Test: Register tool
- [ ] Test: Execute tool
- [ ] Test: Get tool descriptions
- [ ] Test: Schema extraction works
- [ ] Test: Tool not found error
- [ ] Test: Tool execution timeout
- [ ] Mock tools: 3-4 mock functions

**Checkpoint:** Tool Registry ready & tested ✅

---

## 🎯 Sprint 4: Tool Executor Loop (5-6 nap)

### S4.1 - ToolResult & ExecutorState Models
**Fájl:** `backend/domain/llm_outputs.py`
- [ ] ToolResult Pydantic model
  ```python
  class ToolResult(BaseModel):
      tool_name: str
      status: Literal["success", "error", "timeout"]
      result: Optional[Any] = None
      error: Optional[str] = None
      latency_ms: float
      tokens_used: Optional[int] = None
  ```
- [ ] Add to AgentState: `tool_results: List[ToolResult]`

### S4.2 - Tool Executor Node
**Fájl:** `backend/services/agent.py`
- [ ] `_tool_executor_loop_node()` implementation (async)
- [ ] Iterate through `execution_plan.steps`
- [ ] For each step:
  - [ ] Check dependencies (all depends_on finished?)
  - [ ] Execute tool with timeout wrapper
  - [ ] Catch errors: TimeoutError, ValueError, etc.
  - [ ] Store result in `tool_results`
  - [ ] Log execution time + tokens
- [ ] Parallel execution support (optional, for now sequential)
  ```python
  async def _tool_executor_loop_node(self, state: AgentState) -> AgentState:
      plan = state.get("execution_plan")
      tool_results = []
      
      for step in plan.steps:
          try:
              result = await with_timeout_and_retry(
                  tool_registry.execute(step.tool_name, step.arguments),
                  timeout=10,
                  max_retries=2
              )
              tool_results.append(ToolResult(
                  tool_name=step.tool_name,
                  status="success",
                  result=result,
                  latency_ms=...
              ))
          except TimeoutError:
              tool_results.append(ToolResult(
                  tool_name=step.tool_name,
                  status="timeout",
                  error="Tool execution timed out"
              ))
          except Exception as e:
              tool_results.append(ToolResult(
                  tool_name=step.tool_name,
                  status="error",
                  error=str(e)
              ))
      
      state["tool_results"] = tool_results
      return state
  ```

### S4.3 - Graph Integration
**Fájl:** `backend/services/agent.py`
- [ ] Add tool_executor_loop node
- [ ] Update edges:
  ```
  tool_selection → tool_executor_loop → observation_node
  (for rag_and_tools and tools_only routes)
  ```
- [ ] Skip tool executor for "rag_only" route

### S4.4 - Error Handling Per Tool
**Fájl:** `backend/services/agent.py`
- [ ] Tool-specific timeout (10s for RAG, 30s for Jira?)
- [ ] Retry logic with backoff
- [ ] Error classification (transient vs permanent)
- [ ] Fallback: If tool fails → mark as failed, continue to generation

### S4.5 - Testing
**Fájl:** `backend/tests/test_tool_executor.py` (NEW)
- [ ] Test: Executor runs all steps
- [ ] Test: Tool success → result stored
- [ ] Test: Tool timeout → error result
- [ ] Test: Tool error → error result
- [ ] Test: Multiple tools executed in order
- [ ] Test: Max 5 steps limit respected
- [ ] Mock tools: success, timeout, error scenarios

**Checkpoint:** Tool Executor Loop ready & tested ✅

---

## 🎯 Sprint 5: Observation Node (3-4 nap)

### S5.1 - ObservationOutput Model
**Fájl:** `backend/domain/llm_outputs.py`
- [ ] ObservationOutput Pydantic model
  ```python
  class ObservationOutput(BaseModel):
      sufficient: bool = Field(description="Do we have enough info?")
      next_action: Literal["generate", "replan"] = Field(default="generate")
      gaps: List[str] = Field(default_factory=list, description="Missing info")
      reasoning: str = Field(min_length=10, max_length=500)
  ```

### S5.2 - Observation Node
**Fájl:** `backend/services/agent.py`
- [ ] `_observation_node()` implementation (async)
- [ ] Evaluate tool results:
  ```
  Prompt:
  Original Query: {query}
  Execution Plan: {plan}
  Tool Results: {tool_results}
  
  Evaluation:
  1. Do I have enough information to answer?
  2. Are there any gaps or contradictions?
  3. Should I proceed to generation or replan?
  
  Return: ObservationOutput
  ```
- [ ] LLM call: `llm.with_structured_output(ObservationOutput)`
- [ ] State update: `state["observation"]`

### S5.3 - Conditional Routing (Observation)
**Fájl:** `backend/services/agent.py`
- [ ] Add conditional edge after observation:
  ```
  observation_node → conditional_edges:
    - "generate": generation_node
    - "replan": plan_node (close the loop!)
  ```
- [ ] Max replan limit: `state["replan_count"] < 2`
- [ ] If max replan reached → force "generate" route
  ```python
  def _observation_decision(self, state: AgentState) -> str:
      observation = state.get("observation")
      replan_count = state.get("replan_count", 0)
      
      if observation["next_action"] == "replan" and replan_count < 2:
          state["replan_count"] = replan_count + 1
          return "replan"
      return "generate"
  ```

### S5.4 - Graph Structure Update
**Fájis:** `backend/services/agent.py`
- [ ] New graph structure:
  ```
  intent_detection → plan_node → tool_selection
      ↓
      ├─ [rag_only] → retrieval → generation → guardrail → metrics → workflow → memory → END
      ├─ [tools_only] → tool_executor_loop → observation_node ↔ plan_node (loop!) → generation → ...
      └─ [rag_and_tools] → retrieval + tool_executor_loop → observation_node ↔ plan_node → generation → ...
  ```

### S5.5 - Testing
**Fájl:** `backend/tests/test_observation.py` (NEW)
- [ ] Test: Observation evaluates results
- [ ] Test: Sufficient=true → generate route
- [ ] Test: Sufficient=false → replan route
- [ ] Test: Max replan limit enforced
- [ ] Test: Gaps identified correctly
- [ ] Mock LLM: 3 scenarios (sufficient, insufficient, error)

**Checkpoint:** Observation Node ready & tested ✅

---

## 🎯 Integration Sprint (3-4 nap)

### I1 - Full Workflow Integration Test
**Fájl:** `backend/tests/test_executor_loop_integration.py` (NEW)
- [ ] End-to-end test: Plan → Tool Selection → Tool Executor → Observation → Generation
- [ ] Test: RAG-only path works
- [ ] Test: Tools-only path works
- [ ] Test: RAG + Tools path works
- [ ] Test: Replan loop works (2 iterations max)
- [ ] Test: Final answer after observation
- [ ] Mock end-to-end: full workflow simulation

### I2 - Graph Compilation & Validation
**Fájl:** `backend/services/agent.py`
- [ ] Verify graph.compile() succeeds
- [ ] Check all nodes reachable
- [ ] Check END reached from all paths
- [ ] Test with real async execution (mock LLM)

### I3 - Performance Baseline
**Fájl:** `backend/tests/test_performance.py` (NEW)
- [ ] Measure latency: Plan node
- [ ] Measure latency: Tool Selection node
- [ ] Measure latency: Tool Executor (all tools)
- [ ] Measure latency: Observation node
- [ ] Total workflow latency (3-4 tools)
- [ ] Document baseline metrics

### I4 - Documentation
**Fájl:** `docs/házi feladatok/IMPLEMENTATION_PHASE_1-2.md` (NEW)
- [ ] Architecture diagrams (updated graph)
- [ ] Execution flow examples
- [ ] API changes (if any)
- [ ] Configuration options
- [ ] Troubleshooting guide

---

## 📊 Metrics & Validation

### Code Quality
- [ ] Test coverage: >= 85% (tools, nodes)
- [ ] Linting: black, flake8, mypy
- [ ] Type hints: 100% for new code

### Functionality
- [ ] All 5 sprints completed
- [ ] 80+ new tests passing
- [ ] Zero breaking changes
- [ ] Backward compatible

### Performance
- [ ] Plan node: < 2s latency (gpt-4o-mini)
- [ ] Tool Selection: < 1s latency
- [ ] Tool Executor: < 10s (3 tools sequential)
- [ ] Observation: < 1s latency
- [ ] Total workflow: < 15-20s (gpt-4o-mini)

---

## 🎯 Deliverables (Sprint feléhez)

- [x] ExecutionPlan & ToolStep models
- [x] Plan Node implementation + tests
- [x] ToolSelection model
- [x] Tool Selection Node + conditional routing + tests
- [x] Tool Registry (RAG, Jira, Calculator, Email tools)
- [x] Tool Executor Loop node + tests
- [x] ObservationOutput model
- [x] Observation Node + conditional routing + tests
- [x] Full workflow integration test
- [x] Documentation: IMPLEMENTATION_PHASE_1-2.md
- [x] Performance baseline metrics

**Total Effort:** 4-5 hét, ~1000 LOC, ~80-100 új teszt

---

## 🚀 Next Steps (After Fázis 1-2)

- Fázis 3: Error Handling (Retry, Guardian, FailSafe nodes)
- Fázis 4: Long-term Memory (UserMemoryStore)
- Fázis 5: Monitoring (Prometheus, Grafana, Loki)

---

## 📝 Notes

- **Replan Loop:** Observation node can trigger replan (plan_node again), max 2 times
- **Tool Availability:** Tool registry tracks which tools are enabled
- **Fallback:** If all tools fail → summary-only mode (existing fallback)
- **Async:** All nodes are async, uses `with_timeout_and_retry` wrapper
- **Logging:** Every node logs execution time, tokens, status
- **State:** All intermediate state persisted in AgentState TypedDict

---

**Commit Strategy:**
- Commit after each sprint (5 commits total for Fázis 1-2)
- Branch: feature/multi-tool-agent-phase-1-2
- PR: Review after all 5 sprints complete
