# API Hívások és LangGraph Workflow Elemzés

**Version:** 2.12.0 (STRICT_RAG_MODE Feature)  
**Last Updated:** 2026-01-23  
**Breaking Changes:** Manual JSON parsing (LangChain structured_output bug), 50 recursion limit, STRICT_RAG_MODE feature flag

---

## ⚠️ CRITICAL NOTES (v2.12.0)

**STRICT_RAG_MODE Feature Flag** (NEW in v2.12):
- **Purpose**: Controls LLM fallback behavior when RAG returns 0 documents
- **Environment Variable**: `STRICT_RAG_MODE=true` (default) or `false`
- **Strict Mode (true)**: Refuses to answer if no documents found (original behavior)
- **Relaxed Mode (false)**: Allows LLM general knowledge with ⚠️ warning prefix
- **Affected Node**: `generation` (Node 6)
- **See**: [FEATURES.md STRICT_RAG_MODE section](./FEATURES.md#-strict_rag_mode-feature-flag-new-in-v212) for full details

**LangChain Structured Output Bug**: All `with_structured_output()` calls replaced with manual JSON parsing:
- **Affected Nodes**: intent_detection, plan, tool_selection, observation_check, generation (2x)
- **Pattern**: Prompt + JSON format → Regex extract ```json...``` or {...} → json.loads()
- **Impact**: Stable, but verbose. Monitor LangChain updates for fix.

**LangGraph State Management**:
- **Decision Functions**: Read-only (no state mutations)
- **State Mutations**: In nodes only (e.g., plan_node increments replan_count)
- **Recursion Limit**: 50 (config in ainvoke, NOT compile)

**See**: [házi feladatok/3.md](./házi%20feladatok/3.md#kritikus-bugfixek-2026-01-21) for full technical details.

---

## ✅ IGEN - Az API hívások már LangGraph alapúak!

### � Pipeline Mode Routing (v2.10)

```
┌─────────────────────────────────────────────────────────────────┐
│                    POST /api/query/                              │
│                 (QueryAPIView.post())                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│           chat_service.process_query()                           │
│                                                                  │
│   if settings.USE_SIMPLE_PIPELINE:                               │
│       ├─► agent.run_simple() ────► Simple RAG Pipeline          │
│       │   (15 sec, 1-2 LLM calls)                                │
│   else:                                                          │
│       └─► agent.run() ───────────► Complex LangGraph Workflow   │
│           (30-50 sec, 4-6 LLM calls, replan loop)                │
└───────────────────────────┬─────────────────────────────────────┘
```

**USE_SIMPLE_PIPELINE=True (Fast Path):**
```
Intent (keyword) → RAG → Generation → Guardrail → Response
~15 seconds total
```

**USE_SIMPLE_PIPELINE=False (Full Workflow - Default):**
```
Intent (LLM) → Plan → Tools → Observation → [Replan Loop] → 
Generation → Guardrail → Workflow → Memory → Response
~30-50 seconds total
```

### 🔄 LangGraph Workflow Architektúra (Complex Mode)

```
┌─────────────────────────────────────────────────────────────────┐
│           chat_service.process_query()                           │
│              ↓                                                   │
│        agent.process_query()                                     │
│              ↓                                                   │
│     workflow.ainvoke(initial_state)  ← **LangGraph Entry**      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
        ╔═══════════════════════════════════════╗
        ║ LangGraph StateGraph (11 nodes + Replan Loop) ║
        ╚═══════════════════════════════════════╝
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       │
   🔍 Node 1: intent_detection                 │
        │ (detect domain: IT/HR/Finance/...)   │
        │ (JSON parsing: manual regex extract) │
        ▼                                       │
   📝 Node 2: plan                              │
        │ (execution plan, replan_count++)     │
        │ (JSON parsing: manual regex extract) │
        ▼                                       │
   🛠️ Node 3: select_tools                     │
        │ (choose route: rag_only/tools_only/rag_and_tools) │
        │ (JSON parsing: manual regex extract) │
        ▼                                       │
   ┌────┴─── Conditional Routing ─────┐        │
   │                                  │        │
   ▼                                  ▼        │
📚 Node 4a: retrieval          🔧 Node 4b: tool_executor │
   │ (Qdrant RAG search)             │ (async timeout 10s/tool) │
   │                                  ▼        │
   └────────────────► Node 5: observation_check│ ◄─┐
        │ (LLM evaluate: sufficient?)           │   │
        │ (JSON parsing: manual regex extract)  │   │
        ▼                                        │   │
   ┌────┴─── Decision: replan or generate? ────┤   │
   │                                            │   │
   │ IF insufficient (gaps detected):           │   │
   │   replan_count < 2 → REPLAN ───────────────┘   │
   │   replan_count >= 2 → FORCE GENERATE       │   │
   │                                            │   │
   ▼ GENERATE                                   │   │
   🤖 Node 6: generation                        │   │
        │ (OpenAI GPT-4o-mini LLM)             │   │
        │ (JSON parsing: manual regex extract) │   │
        │ (IT domain: auto-append Jira question) │  │
        │                                       │   │
        │ **STRICT_RAG_MODE Logic:**           │   │
        │ ┌─ IF context.strip() == "" ────────┐│   │
        │ │  (no RAG documents retrieved)      ││   │
        │ │                                    ││   │
        │ │  IF STRICT_RAG_MODE == true:       ││   │
        │ │    ├─ Use CRITICAL FAIL-SAFE INSTRUCTIONS │  │
        │ │    │  "Sajnálom, nem találtam..."  ││   │
        │ │    │  (refuse to answer)           ││   │
        │ │                                    ││   │
        │ │  IF STRICT_RAG_MODE == false:      ││   │
        │ │    └─ Use INSTRUCTIONS (relaxed)   ││   │
        │ │       "⚠️ A következő információ..."││   │
        │ │       (allow general knowledge)    ││   │
        │ └────────────────────────────────────┘│   │
        ▼                                       │   │
   ✅ Node 7: guardrail ────────────────────┐  │   │
        │                                   │  │   │
        │ (validation passed?)              │  │   │
        ├─ NO (retry count < 2) ───────────┘  │   │
        │                                      │   │
        ▼ YES                                  │   │
   📊 Node 8: collect_metrics                  │   │
        │ (telemetry: latency, tokens)        │   │
        ▼                                      │   │
   ⚙️  Node 9: execute_workflow  ◄─────────────┘   │
        │                                           │
        │ ┌─ IF domain == IT ─────────────────────┐│
        │ │                                        ││
        │ │  Prepare Jira ticket draft:            ││
        │ │   - summary                            ││
        │ │   - description                        ││
        │ │   - citations                          ││
        │ │   - user_id                            ││
        │ │                                        ││
        │ │  state["workflow"] = {                 ││
        │ │    "action": "it_support_ready",       ││
        │ │    "jira_available": True,             ││
        │ │    "ticket_draft": {...}               ││
        │ │  }                                     ││
        │ └────────────────────────────────────────┘│
        │                                           │
        ▼                                           │
   💾 Node 10: memory_update                        │
        │ (conversation summary + facts)           │
        │ (JSON parsing: manual regex extract)     │
        ▼                                           │
      END                                           │
        │                                           │
        ▼                                           │
   Return QueryResponse to frontend                │
        │                                           │
        └─► Frontend displays:                      │
            - Answer                                │
            - Citations                             │
            - **Jira ticket button** (if IT domain) │
            - Debug panel (latency, RAG context)    │
```

---

## 📋 IT Domain Jira Workflow - Lépésről Lépésre

### 1️⃣ Első API hívás: Query feldolgozás (LangGraph)

**Request:**
```http
POST /api/query/
Content-Type: application/json

{
  "user_id": "user123",
  "session_id": "session456",
  "query": "Hogyan csatlakozok a VPN-hez?",
  "organisation": "AcmeCorp"
}
```

**LangGraph Workflow végrehajtódik:**
1. **intent_detection**: `domain = "it"` (VPN kulcsszó alapján)
2. **retrieval**: Qdrant keres IT-KB dokumentumokban
3. **generation**: GPT-4o-mini válasz generál citációkkal
4. **guardrail**: Ellenőrzi IT-KB-XXX formátumot
5. **collect_metrics**: Telemetria gyűjtés
6. **execute_workflow**: 🎯 **Itt készül a Jira draft!**
   ```python
   state["workflow"] = {
       "action": "it_support_ready",
       "type": "it_support",
       "jira_available": True,
       "ticket_draft": {
           "summary": "IT Support: Hogyan csatlakozok a VPN-hez?",
           "description": "Felhasználó kérdése: ...\n\nRendszer válasza: ...\n\nForrásdokumentumok:\n1. [IT-KB-234] VPN Setup Guide",
           "issue_type": "Task",
           "priority": "Medium",
           "user_id": "user123",
           "domain": "it"
       }
   }
   ```
7. **memory_update**: Mentés session JSON-ba

**Response:**
```json
{
  "success": true,
  "data": {
    "domain": "it",
    "answer": "A VPN eléréséhez használja a Cisco AnyConnect klienst...",
    "citations": [
      {
        "section_id": "IT-KB-234",
        "title": "VPN Setup Guide",
        "content": "...",
        "score": 0.95
      }
    ],
    "workflow": {
      "action": "it_support_ready",
      "jira_available": true,
      "ticket_draft": {
        "summary": "IT Support: Hogyan csatlakozok a VPN-hez?",
        "description": "..."
      }
    }
  }
}
```

**Frontend megjelenítés:**
- ✅ Válasz megjelenik chat bubble-ban
- ✅ Citációk alján látszanak
- ✅ **"Create Jira Ticket" gomb** megjelenik (workflow alapján)

---

### 2️⃣ Második API hívás: Jira ticket létrehozás (Külön endpoint)

**Amikor user rákattint a "Create Jira Ticket" gombra:**

```http
POST /api/jira/ticket/
Content-Type: application/json

{
  "summary": "IT Support: Hogyan csatlakozok a VPN-hez?",
  "description": "Felhasználó kérdése: ...\n\nRendszer válasza: ...",
  "issue_type": "Task",
  "priority": "Medium"
}
```

**Végrehajtás:**
```python
# CreateJiraTicketAPIView.post()
result = asyncio.run(
    atlassian_client.create_jira_ticket(
        summary=summary,
        description=description,
        issue_type=issue_type,
        priority=priority
    )
)
```

**Response:**
```json
{
  "success": true,
  "ticket": {
    "key": "ITSUPPORT-1234",
    "url": "https://your-workspace.atlassian.net/browse/ITSUPPORT-1234"
  }
}
```

**Frontend:**
- ✅ Sikeres értesítés: "Jira ticket created: ITSUPPORT-1234"
- ✅ Link megjelenik a ticketre

---

## 🔍 Kulcsfontosságú Különbségek

### ❌ RÉGI (nem LangGraph)
```python
# Monolitikus endpoint
def query_view(request):
    query = request.data["query"]
    
    # Manual domain detection
    if "vpn" in query.lower():
        domain = "it"
    
    # Manual RAG
    docs = qdrant.search(query, domain)
    
    # Manual LLM call
    response = openai.chat.completions.create(...)
    
    # Manual workflow logic
    if domain == "it":
        # Create ticket draft
        pass
    
    return {"answer": response}
```

### ✅ JELENLEGI (LangGraph alapú)

```python
# Declarative workflow
graph = StateGraph(AgentState)
graph.add_node("intent_detection", self._intent_detection_node)
graph.add_node("retrieval", self._retrieval_node)
graph.add_node("generation", self._generation_node)
graph.add_node("guardrail", self._guardrail_node)
graph.add_node("collect_metrics", self._feedback_metrics_node)
graph.add_node("execute_workflow", self._workflow_node)  # ← Jira draft itt
graph.add_node("memory_update", self._memory_update_node)

# Automatic state management
final_state = await self.workflow.ainvoke(initial_state)
```

**Előnyök:**
1. ✅ **Declarative**: Workflow látható a graph definícióból
2. ✅ **State management**: LangGraph kezeli az állapotot
3. ✅ **Retry logic**: Guardrail node automatikus retry conditional edge-el
4. ✅ **Separation of concerns**: Minden node önálló felelősséggel
5. ✅ **Testable**: Minden node külön unit testelhet mock state-tel
6. ✅ **Observable**: State követhető minden node-on keresztül

---

## 🎯 Workflow Node Részletezés

### `_workflow_node` (agent.py:507-570)

```python
async def _workflow_node(self, state: AgentState) -> AgentState:
    """Execute domain-specific workflows if needed."""
    domain = state.get("domain", "general")

    if domain == DomainType.IT.value:
        logger.info("🔧 IT workflow: Preparing Jira ticket draft")
        
        # Extract data from previous nodes
        query = state.get("query", "")
        answer = state.get("llm_response", "")  # From generation node
        citations = state.get("citations", [])  # From retrieval node
        user_id = state.get("user_id", "unknown")
        
        # Build ticket payload
        ticket_summary = f"IT Support: {query[:100]}"
        ticket_description = (
            f"Felhasználó kérdése: {query}\n\n"
            f"Rendszer válasza:\n{answer}\n\n"
            f"Felhasználó ID: {user_id}\n"
        )
        
        # Add citations for context
        if citations:
            citation_refs = "\n\nForrásdokumentumok:\n"
            for i, c in enumerate(citations[:5], 1):
                section_id = c.get("section_id", "")
                title = c.get("title", "Document")
                citation_refs += f"{i}. [{section_id or title}] {title}\n"
            ticket_description += citation_refs
        
        # Store workflow state for frontend
        state["workflow"] = {
            "action": "it_support_ready",
            "type": "it_support",
            "jira_available": True,
            "ticket_draft": {
                "summary": ticket_summary,
                "description": ticket_description,
                "issue_type": "Task",
                "priority": "Medium",
                "user_id": user_id,
                "domain": "it"
            },
            "next_step": "User can confirm to create Jira ticket"
        }
    
    return state
```

**Miért nem itt történik a tényleges Jira API hívás?**

💡 **Design pattern: Command pattern / Staged execution**

1. **Workflow node role**: Előkészítés, nem végrehajtás
   - State enrichment: workflow metadata hozzáadása
   - User confirmation előtt nem commitolunk változást
   - Frontend dönthet, hogy ténylegesen létrehozza-e

2. **Actual creation**: Külön endpoint (`POST /api/jira/ticket/`)
   - User explicit confirmation kell
   - Frontend elküldi a ticket_draft-ot
   - Ekkor történik a `atlassian_client.create_jira_ticket()` hívás

**Előnyök:**
- ✅ User control: Megnézheti a draft-ot létrehozás előtt
- ✅ No side-effects: LangGraph workflow idempotens (replay safe)
- ✅ Error handling: Jira API failure nem befolyásolja a query response-t
- ✅ Audit trail: Separate ticket creation logged

---

### `_generation_node` (agent.py:959-1020)

**STRICT_RAG_MODE Feature (NEW in v2.12)**

```python
async def _generation_node(self, state: AgentState) -> AgentState:
    """
    Generate final response using LLM.
    
    STRICT_RAG_MODE controls fallback behavior when RAG returns no documents:
    - true (default): Refuses to answer without RAG context
    - false: Allows general knowledge with warning prefix
    """
    context = state.get("rag_context", "").strip()
    query = state.get("query", "")
    domain = state.get("domain", "general")
    
    # 🛡️ STRICT_RAG_MODE Logic
    strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
    logger.info(f"🔧 STRICT_RAG_MODE: {strict_rag_mode}")
    
    if not context:  # No RAG documents retrieved
        if strict_rag_mode:
            # Original behavior: Refuse to answer
            failsafe_instructions = """
CRITICAL FAIL-SAFE INSTRUCTIONS:
1. **Only use information from the retrieved documents above** - DO NOT invent facts
2. **If no relevant documents were retrieved** (empty context):
   - Respond with: "Sajnálom, nem találtam releváns információt ehhez a kérdéshez a rendelkezésre álló dokumentumokban. Kérem, próbálkozzon más kulcsszavakkal, vagy forduljon a rendszer adminisztrátorához további segítségért."
   - DO NOT answer from your general knowledge
3. **Never fabricate** email addresses, internal policies, or organization-specific details
"""
        else:
            # New behavior: Allow general knowledge with warning
            failsafe_instructions = """
INSTRUCTIONS:
1. **Prefer information from the retrieved documents above**, but you may use your general knowledge if documents are insufficient
2. **If using general knowledge (not from documents):**
   - Clearly state: "⚠️ A következő információ általános tudásomon alapul, nem pedig a szervezeti dokumentumokon:"
   - Suggest verifying with the relevant team for organization-specific details
3. **Never fabricate** email addresses, internal policies, or organization-specific details
"""
    else:
        # Normal flow: RAG context exists
        failsafe_instructions = """
Use the retrieved documents to answer accurately.
Cite sources using [section_id] format.
"""
    
    # Build LLM prompt with failsafe instructions
    prompt = f"{failsafe_instructions}\n\nContext: {context}\n\nQuery: {query}"
    
    # ... rest of generation logic (LLM call, JSON parsing, etc.)
    
    return state
```

**STRICT_RAG_MODE Behavior Comparison:**

| Scenario | STRICT_RAG_MODE=true (Default) | STRICT_RAG_MODE=false |
|----------|--------------------------------|------------------------|
| **RAG returns 3 documents** | ✅ Uses documents, cites sources | ✅ Uses documents, cites sources |
| **RAG returns 0 documents** | ❌ Refuses: "Sajnálom, nem találtam..." | ⚠️ Uses general knowledge with warning |
| **User asks: "What is an IP address?"** | ❌ Refuses (no company docs) | ✅ Answers with general knowledge + ⚠️ |
| **User asks: "What's our VPN password?"** | ❌ Refuses (no docs) | ⚠️ "General knowledge: VPNs use passwords... [but verify with IT team]" |

**Configuration:**

```bash
# .env file
STRICT_RAG_MODE=true   # Default: strict mode (refuse without docs)
STRICT_RAG_MODE=false  # Relaxed mode (allow general knowledge)
```

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - STRICT_RAG_MODE=${STRICT_RAG_MODE:-true}  # Default to true
```

**When to use each mode:**

| Mode | Use Case | Example |
|------|----------|---------|
| **Strict (true)** | Production, compliance-critical domains (Legal, Finance, HR) | "Only answer from approved company documentation" |
| **Relaxed (false)** | Development, general knowledge queries, educational chatbots | "Help users with general IT concepts even if not in company docs" |

**Important Notes:**
- Environment variable changes require: `docker-compose up -d --force-recreate backend`
- Simple `restart` does NOT reload environment variables (Docker caches them)
- Both modes still **never fabricate** organization-specific details (emails, policies)
- Relaxed mode uses ⚠️ prefix to clearly distinguish general knowledge from company docs

---

## 📊 State Flow Példa

```python
# Initial state (belépés a workflow-ba)
initial_state = {
    "query": "Hogyan csatlakozok a VPN-hez?",
    "user_id": "user123",
    "messages": []
}

# After intent_detection node
state = {
    "query": "...",
    "domain": "it",  # ← Detected
    "messages": [HumanMessage(content="...")]
}

# After retrieval node
state = {
    "query": "...",
    "domain": "it",
    "citations": [  # ← Retrieved from Qdrant
        {"section_id": "IT-KB-234", "content": "VPN setup...", "score": 0.95}
    ],
    "rag_context": "..."
}

# After generation node
state = {
    "query": "...",
    "domain": "it",
    "citations": [...],
    "llm_response": "A VPN eléréséhez...",  # ← Generated
    "llm_prompt": "...",
    "messages": [HumanMessage(...), AIMessage(...)]
}

# After execute_workflow node
state = {
    "query": "...",
    "domain": "it",
    "citations": [...],
    "llm_response": "...",
    "workflow": {  # ← Workflow enrichment!
        "action": "it_support_ready",
        "jira_available": True,
        "ticket_draft": {
            "summary": "IT Support: Hogyan csatlakozok a VPN-hez?",
            "description": "Felhasználó kérdése: ...\n\nRendszer válasza: ..."
        }
    }
}
```

---

## ✅ Összegzés

### Válasz a kérdésre: **IGEN**, az API hívások LangGraph alapúak!

**Teljes flow:**
1. `POST /api/query/` → LangGraph workflow (`workflow.ainvoke()`)
2. 7 node végrehajtódik szekvenciálisan (intent → retrieval → generation → guardrail → metrics → **workflow** → memory)
3. **Workflow node** (6. node):
   - IT domain esetén: Jira ticket draft készítés
   - State enrichment: `state["workflow"]` metadata
   - Frontend kap workflow info-t a response-ban
4. Frontend megjeleníti a "Create Jira Ticket" gombot
5. User kattintás → `POST /api/jira/ticket/` → Tényleges Jira API hívás

**Architektúra előnyei:**
- ✅ Declarative workflow (StateGraph)
- ✅ Automatic state management
- ✅ Conditional routing (guardrail retry)
- ✅ Separation of concerns (7 independent nodes)
- ✅ Testable (minden node unit testelhet)
- ✅ Observable (state követhető)
- ✅ User control (confirmation before Jira creation)

**LangGraph használat minden API hívásnál:**
- `POST /api/query/` → **TAK**, teljes 7-node workflow
- `POST /api/jira/ticket/` → **NEM**, direct Atlassian client hívás (de a draft a LangGraph workflow-ból jön!)
- `POST /api/feedback/` → NEM (egyszerű DB write)
- `POST /api/regenerate/` → **TAK**, részleges workflow (skip intent + retrieval)

---

## 🔄 Next Steps (opcionális fejlesztések)

### Jövőbeni LangGraph bővítés:

**Option 1: Jira creation is LangGraph node**
```python
# Add new node
graph.add_node("jira_execution", self._jira_execution_node)

# Conditional edge
graph.add_conditional_edges(
    "execute_workflow",
    self._should_create_jira,
    {
        "yes": "jira_execution",
        "no": "memory_update"
    }
)
```

**Option 2: Human-in-the-loop approval**
```python
# Use LangGraph's interrupt_before
graph.add_node("jira_execution", self._jira_execution_node)
compiled = graph.compile(interrupt_before=["jira_execution"])

# Frontend approval required before continuing
```

Jelenleg azonban az explicit two-step flow (draft preparation + separate creation) **szándékos design decision** a user control és error handling miatt.
