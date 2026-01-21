# Összetett Ágens Architektúra Elemzés - Jelenlegi Állapot

**Dátum:** 2026-01-19  
**Cél:** Analizálni a jelenlegi LangGraph implementációt a 4-rétegű ágens tervezési elvek alapján

---

## 📋 4-Rétegű Architektúra Követelmények

### 1. **Reasoning Layer** (LLM gondolkodás)
- Prompting
- Chain-of-Thought
- Triage
- Routing

### 2. **Operational Layer** (Workflow vezérlés)
- Node-ok
- Edge-ek
- State management
- Reducer pattern

### 3. **Tool Execution Layer** (Külső API-k)
- Adatlekérés
- Adatírás
- Számítás

### 4. **Memory/RAG/Context Handling**
- Stateful működés
- Retrieval-before-tools

---

## ✅ Jelenlegi Implementáció Állapota

### **1. Reasoning Layer** - ⚠️ RÉSZBEN MEGVALÓSÍTVA

#### ✅ **Prompting** - MEGVAN
- `_intent_detection_node()`: Domain klasszifikáció keyword-based + LLM fallback
- `_generation_node()`: RAG-based answer generation Pydantic structured output-tal
- `_memory_update_node()`: Reducer pattern prompt (merge previous + new)

**Példa:**
```python
# Intent detection prompt
prompt = f"""
Classify this query into ONE category:
marketing = brand, logo, visual-design
hr = vacation, employee, szabadság
it = VPN, computer, software
...
Provide: domain, confidence, reasoning
"""
```

#### ❌ **Chain-of-Thought** - HIÁNYZIK
Nincs explicit CoT (Step-by-Step reasoning) implementálva.

**Mit kellene:**
```python
# Plan node példa (HIÁNYZIK)
async def _plan_node(self, state: AgentState) -> AgentState:
    """
    LLM thinks step-by-step:
    1. What do I need to answer this query?
    2. Which tools/data sources are needed?
    3. In what order should I execute them?
    """
    prompt = """
    Think step-by-step to answer this query:
    Query: {query}
    
    Step 1: Understand the intent
    Step 2: Identify required information
    Step 3: Choose data sources (RAG, tools, memory)
    Step 4: Plan execution order
    
    Return: execution_plan as structured JSON
    """
    # Return: {"steps": [...], "tools": [...], "data_sources": [...]}
```

#### ✅ **Triage** - MEGVAN (implicit)
- `_intent_detection_node()`: Domain triage (keyword + LLM)
- `_guardrail_decision()`: Validation-based routing (retry/continue)

**Példa:**
```python
def _guardrail_decision(self, state: AgentState) -> str:
    """Triage: retry generation or continue to metrics."""
    validation_errors = state.get("validation_errors", [])
    retry_count = state.get("retry_count", 0)
    
    if validation_errors and retry_count < 2:
        return "retry"  # Go back to generation
    return "continue"  # Proceed to metrics
```

#### ✅ **Routing** - MEGVAN
- Conditional edges: `guardrail → generation` (retry) / `guardrail → metrics` (continue)
- Linear routing: `intent → retrieval → generation → guardrail → metrics → workflow → memory → END`

**Példa:**
```python
graph.add_conditional_edges(
    "guardrail",
    self._guardrail_decision,
    {
        "retry": "generation",
        "continue": "collect_metrics"
    }
)
```

#### ⚠️ **Hiányosságok:**
- ❌ Nincs **Plan Node** (LLM előre gondolkodik, hogy mit fog csinálni)
- ❌ Nincs **Observation Node** (LLM értékeli az intermediate results-ot)
- ❌ Nincs **Router Tool** (dinamikus tool selection LLM döntés alapján)
- ❌ Nincs **Action/Update ciklus** (executor loop, incremental refinement)

---

### **2. Operational Layer** - ✅ JÓL MEGVALÓSÍTVA

#### ✅ **Node-ok** - 7 node
1. `intent_detection` - Domain klasszifikáció
2. `retrieval` - RAG Qdrant-ból
3. `generation` - LLM answer generation
4. `guardrail` - Validation check
5. `collect_metrics` - Telemetria
6. `execute_workflow` - Domain-specific workflow (Jira draft)
7. `memory_update` - Reducer pattern memory

#### ✅ **Edge-ek**
- **Linear edges:** 6 darab (intent→retrieval, retrieval→generation, etc.)
- **Conditional edges:** 1 darab (guardrail→retry/continue)

#### ✅ **State Management** - `AgentState` TypedDict
```python
class AgentState(TypedDict, total=False):
    messages: Sequence[BaseMessage]
    query: str
    domain: str
    retrieved_docs: list
    output: Dict[str, Any]
    citations: list
    workflow: Dict[str, Any]
    validation_errors: list
    retry_count: int
    feedback_metrics: Dict[str, Any]
    memory_summary: str
    memory_facts: list
    rag_unavailable: bool  # Degradation flag
```

#### ✅ **Reducer Pattern** - `_memory_update_node()`
- Previous summary + new messages → merged summary
- Semantic compression (max 8 facts)

**Erősségek:**
- Tiszta state-based workflow
- Conditional routing implemented
- Retry logic guardrail-ben

**Hiányosságok:**
- ❌ Nincs **Executor Loop** (iteratív finomítás több LLM call-lal)
- ❌ Nincs **Dynamic Tool Selection** (LLM choose tools at runtime)

---

### **3. Tool Execution Layer** - ⚠️ MINIMÁLIS

#### ✅ **Adatlekérés (RAG)** - MEGVAN
- `_retrieval_node()`: Qdrant vector DB query
- Timeout + retry wrapper (`with_timeout_and_retry`)

```python
citations = await with_timeout_and_retry(
    self.rag_client.retrieve_for_domain(
        domain=state["domain"],
        query=augmented_query,
        top_k=5
    ),
    timeout=settings.RAG_TIMEOUT,
    max_retries=3
)
```

#### ⚠️ **Adatírás (Jira Ticket)** - RÉSZBEN MEGVAN
- `_workflow_node()`: Jira ticket draft készítés
- `create_jira_ticket_from_draft()`: Tényleges Jira API hívás (külön endpoint)

**Probléma:** Nincs általános tool execution framework.

#### ❌ **Számítás (Custom Tools)** - HIÁNYZIK
Nincs implementált tool registry, dinamikus tool selection, vagy executor pattern.

**Mit kellene (példa):**
```python
# Tool registry (HIÁNYZIK)
AVAILABLE_TOOLS = {
    "search_documents": qdrant_search_tool,
    "create_jira_ticket": jira_create_tool,
    "send_email": email_tool,
    "calculate_cost": cost_calculator_tool,
    "check_calendar": calendar_tool,
}

# Tool executor node (HIÁNYZIK)
async def _tool_executor_node(self, state: AgentState) -> AgentState:
    """Execute tools selected by LLM."""
    tool_calls = state.get("tool_calls", [])
    results = []
    
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["arguments"]
        
        if tool_name in AVAILABLE_TOOLS:
            result = await AVAILABLE_TOOLS[tool_name](**tool_args)
            results.append(result)
    
    state["tool_results"] = results
    return state
```

**Hiányosságok:**
- ❌ Nincs **Tool Registry** (elérhető tools katalógus)
- ❌ Nincs **Dynamic Tool Selection** (LLM választ runtime-ban)
- ❌ Nincs **Tool Executor Loop** (többszörös tool hívás refinement-tel)
- ❌ Nincs **Tool Observation** (LLM értékeli a tool eredményét)

---

### **4. Memory/RAG/Context Handling** - ✅ JÓL MEGVALÓSÍTVA

#### ✅ **Stateful Működés** - MEGVAN
- `AgentState`: Minden state mező perzisztálva a graph futás alatt
- `messages`: Conversation history rolling window (max 8)
- `memory_summary`: Reducer pattern (previous + new)
- `memory_facts`: Semantic compression (max 8 facts)

#### ✅ **Retrieval-Before-Tools** - MEGVAN
- `retrieval` node fut ELŐBB mint `generation`
- RAG context beépül a generation prompt-ba

```python
# Retrieval → Generation pipeline
graph.add_edge("retrieval", "generation")

# Generation prompt tartalmazza a RAG context-et
context_parts = [
    f"Doc: {c.title}\nContent: {c.content[:500]}"
    for c in state.get("retrieved_docs", [])
]
context = "\n\n".join(context_parts)
```

#### ✅ **Reducer Pattern Memory** - MEGVAN
- Previous summary + new conversation → merged summary
- Semantic fact compression (LLM-based filtering)

**Erősségek:**
- Rolling window memory (8 messages)
- Semantic compression (max 8 facts)
- Reducer pattern (cumulative summary)
- RAG-first architecture

**Hiányosságok:**
- ❌ Nincs **Long-Term Memory** (persistent storage, user profiles)
- ❌ Nincs **Multi-Level Summarization** (short/medium/long conversation tiers)

---

## 🔍 Hiányosságok Összefoglalása

### **Reasoning Layer Gaps:**
1. ❌ **Plan Node** - LLM előre megtervezi a lépéseket
2. ❌ **Chain-of-Thought** - Explicit step-by-step reasoning
3. ❌ **Observation Node** - LLM értékeli az intermediate results-ot
4. ❌ **Router Tool Node** - Dinamikus tool selection LLM döntés alapján

### **Operational Layer Gaps:**
5. ❌ **Executor Loop** - Iteratív finomítás több LLM call-lal (pl. plan → execute → observe → replan)

### **Tool Execution Layer Gaps:**
6. ❌ **Tool Registry** - Elérhető tools katalógus
7. ❌ **Dynamic Tool Selection** - LLM choose tools at runtime
8. ❌ **Tool Executor Node** - Általános tool execution framework
9. ❌ **Tool Observation** - LLM értékeli tool eredményét, dönt next action-ről

### **Memory/RAG/Context Gaps:**
10. ❌ **Long-Term Memory** - Persistent user profiles, preferences
11. ❌ **Multi-Level Summarization** - Short/medium/long conversation tiers

---

## 📊 Jelenlegi vs Ideális Architektúra

### **Jelenlegi Workflow (7 nodes, 1 conditional edge):**
```
User Query
    ↓
Intent Detection (keyword + LLM)
    ↓
Retrieval (Qdrant RAG)
    ↓
Generation (LLM + RAG context)
    ↓
Guardrail (validation check)
    ↓ (retry if errors)
Collect Metrics (telemetria)
    ↓
Execute Workflow (Jira draft)
    ↓
Memory Update (reducer pattern)
    ↓
END
```

### **Ideális Workflow (with missing components):**
```
User Query
    ↓
[NEW] Plan Node (LLM thinks: what do I need?)
    ↓
Intent Detection (triage)
    ↓
[NEW] Router Tool (LLM selects: RAG? API? Calculation?)
    ↓
Retrieval (if needed)
    ↓
[NEW] Tool Executor Loop (execute selected tools)
    ↓
[NEW] Observation Node (LLM evaluates: good enough?)
    ↓ (if not → replan)
Generation (LLM synthesizes final answer)
    ↓
Guardrail (validation)
    ↓
Collect Metrics
    ↓
Execute Workflow
    ↓
Memory Update
    ↓
END
```

---

## 🎯 Fejlesztési Javaslatok

### **High Priority (Reasoning Layer bővítés):**

#### 1. **Plan Node** - LLM előzetes tervezés
```python
async def _plan_node(self, state: AgentState) -> AgentState:
    """LLM generates execution plan."""
    prompt = """
    Think step-by-step to answer this query:
    Query: {query}
    Domain: {domain}
    
    Available tools:
    - search_documents (RAG)
    - create_jira_ticket
    - send_email
    - calculate_cost
    
    Plan your approach:
    1. What information do I need?
    2. Which tools should I use?
    3. In what order?
    
    Return structured plan: {{"steps": [...], "tools": [...]}}
    """
    # LLM structured output → ExecutionPlan model
    plan = await self.llm.with_structured_output(ExecutionPlan).ainvoke(...)
    state["execution_plan"] = plan
    return state
```

#### 2. **Tool Executor Loop** - Iteratív tool execution
```python
async def _tool_executor_loop_node(self, state: AgentState) -> AgentState:
    """Execute tools iteratively with observation."""
    plan = state["execution_plan"]
    results = []
    
    for step in plan["steps"]:
        # Execute tool
        tool_result = await execute_tool(step["tool"], step["args"])
        results.append(tool_result)
        
        # Observation: LLM evaluates result
        observation_prompt = f"""
        Tool: {step['tool']}
        Result: {tool_result}
        
        Is this sufficient to answer the query?
        - If YES → proceed to next step
        - If NO → suggest refinement
        """
        observation = await self.llm.ainvoke(...)
        
        if observation["needs_refinement"]:
            # Replan (close the loop)
            state["execution_plan"] = await self._plan_node(state)
    
    state["tool_results"] = results
    return state
```

#### 3. **Observation Node** - Intermediate result evaluation
```python
async def _observation_node(self, state: AgentState) -> AgentState:
    """LLM evaluates intermediate results."""
    tool_results = state.get("tool_results", [])
    
    prompt = f"""
    Query: {state['query']}
    Tools executed: {len(tool_results)}
    Results: {tool_results}
    
    Evaluate:
    1. Do I have enough information to answer?
    2. Are there any gaps or contradictions?
    3. Should I execute more tools or proceed to generation?
    
    Return: {{"sufficient": bool, "next_action": str, "reasoning": str}}
    """
    
    evaluation = await self.llm.with_structured_output(ObservationOutput).ainvoke(...)
    state["observation"] = evaluation
    return state
```

### **Medium Priority (Tool Execution bővítés):**

#### 4. **Tool Registry** - Központosított tool katalógus
```python
# tools/registry.py
from typing import Callable, Dict

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
    
    def register(self, name: str, description: str):
        def decorator(func: Callable):
            self.tools[name] = {
                "function": func,
                "description": description,
                "schema": extract_schema(func)  # Auto-generate from type hints
            }
            return func
        return decorator
    
    def get_tool_descriptions(self) -> str:
        """Return tool descriptions for LLM prompt."""
        return "\n".join([
            f"- {name}: {info['description']}"
            for name, info in self.tools.items()
        ])

# Usage
tool_registry = ToolRegistry()

@tool_registry.register("search_documents", "Search knowledge base documents")
async def search_documents(query: str, domain: str, top_k: int = 5) -> List[Citation]:
    return await qdrant_client.retrieve_for_domain(domain, query, top_k)

@tool_registry.register("create_jira_ticket", "Create IT support ticket")
async def create_jira_ticket(summary: str, description: str) -> Dict:
    return await atlassian_client.create_ticket(summary, description)
```

#### 5. **Dynamic Tool Selection** - LLM választ runtime-ban
```python
async def _tool_selection_node(self, state: AgentState) -> AgentState:
    """LLM selects which tools to use."""
    available_tools = tool_registry.get_tool_descriptions()
    
    prompt = f"""
    Query: {state['query']}
    Available tools:
    {available_tools}
    
    Select which tools you need and in what order.
    Return: {{"tools": [{{"name": str, "arguments": dict}}]}}
    """
    
    selection = await self.llm.with_structured_output(ToolSelection).ainvoke(...)
    state["tool_calls"] = selection["tools"]
    return state
```

### **Low Priority (Memory bővítés):**

#### 6. **Long-Term Memory** - Persistent user profiles
```python
# infrastructure/user_memory.py
class UserMemoryStore:
    def __init__(self, postgres_client):
        self.db = postgres_client
    
    async def get_user_profile(self, user_id: str) -> Dict:
        """Load user preferences, history, facts."""
        return await self.db.fetch_one(
            "SELECT * FROM user_profiles WHERE user_id = $1", user_id
        )
    
    async def update_user_facts(self, user_id: str, new_facts: List[str]):
        """Append new facts to user profile."""
        await self.db.execute(
            "UPDATE user_profiles SET facts = facts || $1 WHERE user_id = $2",
            new_facts, user_id
        )
```

---

## 📈 Implementációs Ütemterv

### **Fázis 1 (1-2 hét): Reasoning Layer alapok**
1. Plan Node implementáció
2. ExecutionPlan Pydantic model
3. Basic tool registry (3-5 tool)
4. Tool selection node (LLM-based)

### **Fázis 2 (2-3 hét): Tool Execution Loop**
5. Tool executor node
6. Observation node
7. Executor loop (plan → execute → observe → replan)
8. Conditional routing frissítés

### **Fázis 3 (1-2 hét): Finomítás**
9. Long-term memory (Postgres)
10. Multi-level summarization
11. Chain-of-Thought explicit prompting
12. Performance optimalizálás

### **Fázis 4 (1 hét): Tesztelés**
13. Unit tesztek (új node-ok)
14. Integration tesztek (executor loop)
15. Load testing (executor overhead)
16. Dokumentáció frissítés

---

## 🎓 Tanulságok & Best Practices

### **Mit csináltunk jól:**
✅ Tiszta state management (AgentState TypedDict)  
✅ Reducer pattern memory (cumulative summary)  
✅ Conditional routing (guardrail retry)  
✅ Timeout/retry/fallback mechanizmusok  
✅ Pydantic validation minden LLM output-on  

### **Mit kellene fejleszteni:**
⚠️ LLM előzetes tervezés (plan node)  
⚠️ Dinamikus tool selection  
⚠️ Executor loop (iteratív finomítás)  
⚠️ Tool observation (intermediate evaluation)  
⚠️ Long-term memory persistence  

### **Architectural Principles:**
1. **Separation of Concerns**: Reasoning ≠ Execution ≠ Memory
2. **Observability**: Minden node loggol + telemetria
3. **Fail-Safe**: Timeout/retry/fallback minden kritikus ponton
4. **Type Safety**: Pydantic models everywhere
5. **Idempotency**: State-based workflow, újrafuttatható
6. **Degradation**: RAG unavailable → summary-only fallback

---

## 📚 Referenciák

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [AI Agent 4-Layer Architecture](https://github.com/adrgul/ai_agent_tutorial/blob/main/docs/AI_AGENT_4_RETEG_ARCHITEKTURA.md)
- [ReAct Pattern](https://arxiv.org/abs/2210.03629) - Reasoning + Acting
- [Plan-and-Execute Pattern](https://blog.langchain.dev/planning-agents/)
- [Tool Use Best Practices](https://docs.anthropic.com/en/docs/agents/overview)

---

**Következő lépés:** Implementáljuk a Plan Node-ot és Tool Selection Node-ot (Fázis 1).
