# API Hívások és LangGraph Workflow Elemzés

## ✅ IGEN - Az API hívások már LangGraph alapúak!

### 🔄 LangGraph Workflow Architektúra

```
┌─────────────────────────────────────────────────────────────────┐
│                    POST /api/query/                              │
│                 (QueryAPIView.post())                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
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
        ║   LangGraph StateGraph (7 nodes)      ║
        ╚═══════════════════════════════════════╝
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       │
   🔍 Node 1: intent_detection                 │
        │ (detect domain: IT/HR/Finance/...)   │
        ▼                                       │
   📚 Node 2: retrieval                         │
        │ (Qdrant RAG search)                  │
        ▼                                       │
   🤖 Node 3: generation                        │
        │ (OpenAI GPT-4o-mini LLM)             │
        ▼                                       │
   ✅ Node 4: guardrail ────────────────────┐  │
        │                                   │  │
        │ (validation passed?)              │  │
        ├─ NO (retry count < 2) ───────────┘  │
        │                                      │
        ▼ YES                                  │
   📊 Node 5: collect_metrics                  │
        │ (telemetry: latency, tokens)        │
        ▼                                      │
   ⚙️  Node 6: execute_workflow  ◄─────────────┘
        │                        
        │ ┌─ IF domain == IT ─────────────────────┐
        │ │                                        │
        │ │  Prepare Jira ticket draft:            │
        │ │   - summary                            │
        │ │   - description                        │
        │ │   - citations                          │
        │ │   - user_id                            │
        │ │                                        │
        │ │  state["workflow"] = {                 │
        │ │    "action": "it_support_ready",       │
        │ │    "jira_available": True,             │
        │ │    "ticket_draft": {...}               │
        │ │  }                                     │
        │ └────────────────────────────────────────┘
        │
        ▼
   💾 Node 7: memory_update
        │ (conversation summary + facts)
        ▼
      END
        │
        ▼
   Return QueryResponse to frontend
        │
        └─► Frontend displays:
            - Answer
            - Citations
            - **Jira ticket button** (if IT domain)
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
