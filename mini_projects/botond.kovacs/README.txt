
# AI Agent Demo - LangGraph + FastAPI + React + MCP


## 🔥 Key Capabilities

- **Regulation Tool**: RAG (Retrieval-Augmented Generation) for querying the 2008. évi LX. Gáztörvény using FAISS vectorstore and OpenAI embeddings
- **GasExportTool**: Query exported gas quantities (kWh) for cross-border points using Transparency.host API (ENTSOG)
- **MCP Server Integration**: EIA (Energy Information Administration) natural gas data via JSON-RPC 2.0 over stdio
- **Multi-language Support**: Automatic language detection (Hungarian/English) with context-aware responses
- **Persistent Memory**: User profiles and conversation history with file-based storage

## 🎯 Overview

This application demonstrates the **Agent Workflow Cycle**:

```
Prompt → Decision → Tool → Observation → Memory → Response
```

**Workflow**: `Agent → Tool → Agent → User`

The agent uses **LangGraph** for orchestration, **OpenAI GPT-4** for reasoning, and provides a **ChatGPT-like interface** for interaction.

## 📑 Table of Contents

- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Tool Implementations](#-tool-implementations)
  - [RegulationTool (RAG Pipeline)](#1-regulationtool-rag-pipeline)
  - [GasExportTool (ENTSOG API)](#2-gasexporttool-entsog-transparency-api)
  - [MCP Server (EIA Data)](#3-mcp-server-eia-natural-gas-data)
- [LangGraph Agent Workflow](#-langgraph-agent-workflow)
- [Pydantic Validation](#-pydantic-validation--data-models-202601)
- [Getting Started](#-getting-started)
- [API Endpoints](#-api-endpoints)
- [SOLID Principles](#-solid-principles-applied)
- [Technologies](#-technologies)
- [Environment Variables](#-environment-variables)

## ✨ Key Features

### Advanced Orchestration

- **Plan-and-Execute Workflow**: The agent now uses a planner-executor architecture:
  - **PlannerNode**: Generates structured execution plans in JSON format.
  - **ExecutorLoop**: Iterates over planned steps, routes tasks, and handles retries.
- **Parallel Execution**: Supports fan-out and fan-in patterns for concurrent task execution.
- **Dynamic Routing**: Decides at runtime which nodes/tools to execute, with explainable decisions.
- **Aggregation and Reducers**: Safely merges results from parallel nodes using reusable reducers.

### Agent Capabilities

- **LangGraph-based orchestration**: StateGraph with conditional edges for agent reasoning and tool execution
- **Regulation RAG**: Query the 2008. évi LX. Gáztörvény using FAISS vectorstore with OpenAI embeddings
- **Gas Export Tool**: Query exported gas quantities from Transparency.host (ENTSOG) API
- **MCP Server Integration**: EIA natural gas data (prices, storage, production) via JSON-RPC 2.0
- **Memory management**: Maintains user preferences, conversation history, and workflow state
- **Multi-language support**: Automatic language detection and response in Hungarian/English
- **Iteration control**: MAX_ITERATIONS limit prevents infinite loops in multi-step workflows

### Persistence

- ✅ **All conversation messages** persisted to JSON files in `data/sessions/`
- ✅ **User profiles** stored separately in `data/users/` (never deleted)
- ✅ **Reset context** command: Clears conversation but preserves profile
- ✅ **File-based storage**: Simple, transparent, and easy to inspect
- ✅ **Pydantic validation**: All data models validated on read/write

### Architecture

- 🏗️ **SOLID principles** applied throughout
- 📦 **Clean architecture**: Domain → Services → Infrastructure → API layers
- 🔌 **Dependency Inversion**: Abstract interfaces for all external dependencies
- 🎯 **Single Responsibility**: Each class/module has one clear purpose
- 🔓 **Open/Closed**: Easy to extend with new tools without modifying existing code

## 🏛️ Architecture

### Backend Structure

```
backend/
├── domain/                 # Domain layer - Core business entities
│   ├── models.py          # Pydantic models (Message, UserProfile, Memory, ToolCall, MCPTool)
│   └── interfaces.py      # Abstract interfaces (IUserRepository, IConversationRepository, IToolClient)
├── infrastructure/        # Infrastructure layer - External implementations
│   ├── repositories.py    # File-based persistence (JSON storage)
│   └── tool_clients.py    # Tool implementations (RegulationRAGClient, GasExportClient, MCPClient)
├── services/              # Service layer - Business logic
│   ├── agent.py           # LangGraph agent with StateGraph workflow
│   ├── tools.py           # Tool wrappers (RegulationTool, GasExportTool)
│   └── chat_service.py    # Chat workflow orchestration
├── eia_mcp/              # MCP Server for EIA data
│   └── server.py         # JSON-RPC 2.0 server over stdio
└── main.py               # API layer - FastAPI endpoints
```

### LangGraph Workflow Architecture

The agent uses a **StateGraph** with the following structure:

```
         ┌─────────────────┐
         │  agent_decide   │ ← Entry point: LLM analyzes request and decides action
         └────────┬────────┘
                  │
                  ├─→ [conditional routing based on decision]
                  │
     ┌────────────┼────────────┬─────────────┐
     │            │            │             │
     ▼            ▼            ▼             ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐
│  tool_  │  │  tool_  │  │  tool_  │  │   final     │
│regulation│  │   gas   │  │  (MCP)  │  │   answer    │
└────┬────┘  └────┬────┘  └────┬────┘  └─────────────┘
     │            │            │             │
     └────────────┴────────────┘             │
              │                              │
              ▼                              ▼
     ┌─────────────────┐              ┌──────────┐
     │  agent_decide   │              │   END    │
     │   (loop back)   │              └──────────┘
     └─────────────────┘
```

**Key Features:**
- **Conditional routing**: Agent decides whether to call a tool or finalize response
- **Tool execution loop**: Agent can call multiple tools sequentially
- **Iteration limit**: MAX_ITERATIONS = 10 prevents infinite loops
- **State management**: AgentState tracks messages, memory, tools_called, and iteration_count

## 🛠️ Examples and Demonstrations

### Full Workflow Example

1. **Plan Generation**:
   - The `PlannerNode` generates a structured plan in JSON format.
   - Example Plan:
     ```json
     [
       {"step": 1, "action": "fetch_data", "params": {"source": "api1"}},
       {"step": 2, "action": "process_data", "params": {"method": "aggregation"}},
       {"step": 3, "action": "store_results", "params": {"destination": "db"}}
     ]
     ```

2. **Dynamic Routing**:
   - The `DynamicRouter` selects nodes/tools to execute based on the plan.
   - Example Routing Decision:
     ```json
     {
       "next_nodes": ["node_a", "node_b"],
       "execution_mode": "parallel"
     }
     ```

3. **Parallel Execution**:
   - The `FanOutNode` triggers multiple tasks simultaneously.
   - Example Tasks:
     ```json
     [
       {"task": "Task 1", "status": "completed"},
       {"task": "Task 2", "status": "completed"}
     ]
     ```

4. **Aggregation**:
   - The `FanInNode` aggregates results deterministically.
   - Example Aggregated Results:
     ```json
     {
       "aggregated_key": ["value1", "value2"]
     }
     ```

5. **Execution**:
   - The `ExecutorLoop` executes each step, updating state dynamically.

---

### Key Features Recap

- **Retries and Failure Handling**: Ensures robustness in the `ExecutorLoop`.
- **Explainable Decisions**: Logs all routing and execution decisions.
- **Dynamic State Updates**: State is updated after each step.
- **Parallel Execution**: Fan-out and fan-in patterns enable concurrent task execution.
- **Robust Aggregation**: Reducers merge results safely, supporting lists, maps, and typed states.

For more details, see the `backend/advanced_agents/` folder.

## 🛠️ Tool Implementations

### 1. RegulationTool (RAG Pipeline)

Provides RAG-based Q&A for the **2008. évi LX. Gáztörvény** (Hungarian Gas Act).

**Technology Stack:**
- **FAISS**: Vector database for similarity search
- **OpenAI Embeddings**: Text-to-vector conversion
- **LangChain**: Document loading and text splitting
- **PyPDFLoader**: PDF document processing

**Main actions:**
- `query`: Ask a question about the regulation
- `info`: Get metadata about the loaded regulation

**Parameters:**
- `action` (string, required): 'query' or 'info'
- `question` (string, required for query): The user's question
- `top_k` (int, optional): Number of relevant chunks to retrieve (default: 5, max: 20)

**Initialization:**
```python
RegulationRAGClient(
    pdf_path="path/to/gaztorveny.pdf",
    openai_api_key="sk-...",
    persist_directory="./data/regulation_vectordb",
    chunk_size=100000,
    chunk_overlap=200
)
```

**Processing Pipeline:**
1. PDF is loaded and split into chunks (max 300,000 tokens)
2. Chunks are embedded using OpenAI's text-embedding-ada-002
3. FAISS index is created and persisted to disk
4. On subsequent runs, index is loaded from cache (fast startup)

**Query Flow:**
1. User question is embedded
2. FAISS retrieves top_k most similar chunks
3. Chunks + question are sent to GPT-4
4. GPT-4 generates answer with source references

**Example output:**
```
📚 **Answer from 'gaztorveny':**

A Magyar Energetikai és Közmű-szabályozási Hivatal (MEKH) felhatalmazásai...

**Sources:**
[Page 146]: 2008. évi XL. törvény - a földgázellátásról...
[Page 145]: Hivatal felhatalmazást kap...
```

---

### 2. GasExportTool (ENTSOG Transparency API)

Queries exported gas quantity (kWh) for cross-border points using the **Transparency.host (ENTSOG)** API.

**Purpose:**
- Get daily and total exported gas quantities for specific cross-border points and periods
- Historical data retrieval for gas flow analysis

**Parameters:**
- `pointLabel` (string, required): Name of the export point (e.g., 'VIP Bereg', 'Interconnection HU-UA')
- `from` or `periodFrom` (string, required): Start date (YYYY-MM-DD format)
- `to` or `periodTo` (string, required): End date (YYYY-MM-DD format)

**API Flow:**
1. Query `/api/v1/connectionPoints` to resolve pointLabel → pointKey
2. Query `/api/v1/operationaldatas` with:
   - `pointKey`: Resolved from step 1
   - `periodFrom`, `periodTo`: Date range
   - `indicator`: "Physical Flow"
   - `directionKey`: "exit" (for export)
   - `periodType`: "day"
3. Aggregate daily values and return total

**Response fields:**
- `date`: Gas day (YYYY-MM-DD)
- `value`: Quantity in kWh
- `indicator`: "Physical Flow"
- `unit`: "kWh"
- `operatorLabel`: TSO name (e.g., "FGSZ")
- `flowStatus`: "Confirmed" or "Estimated"
- `pointLabel`: Connection point name
- `total`: Sum of all values in period

**Example output:**
```
⛽ **Gas Exported Quantity for 'VIP Bereg':**

Period: 2025-12-01 to 2025-12-07
Total: 12,345,678 kWh

**Details:**
- 2025-12-01: 1,234,567 kWh | Export | FGSZ | Confirmed
- 2025-12-02: 1,234,567 kWh | Export | FGSZ | Confirmed
...
```

**Error handling:**
- Missing parameters → error message
- Point not found → error message
- API timeout → httpx.AsyncClient(timeout=20)
- HTTP errors → logged and returned to user

---

### 3. MCP Server (EIA Natural Gas Data)

**MCP (Model Context Protocol)** server providing access to U.S. Energy Information Administration (EIA) natural gas data via JSON-RPC 2.0 over stdio.

#### Server Architecture

**File**: `backend/eia_mcp/server.py`

**Communication**: JSON-RPC 2.0 over **stdio** (stdin/stdout)
- Server runs as subprocess: `python -m eia_mcp.server`
- Client sends JSON-RPC requests to stdin
- Server responds with JSON-RPC responses to stdout

**Protocol Version**: `2024-11-05`

**Capabilities**: Tools (natural gas data queries)

#### Server Implementation

```python
class EIAMCPServer:
    def __init__(self):
        self.api_key = os.environ.get("EIA_API_KEY", "")
        self.base_url = "https://api.eia.gov/v2"
```

**Supported JSON-RPC Methods:**

| Method | Description | Parameters |
|--------|-------------|------------|
| `initialize` | Initialize MCP session | `protocolVersion`, `capabilities`, `clientInfo` |
| `initialized` | Notification after init | (none) |
| `tools/list` | List available tools | (none) |
| `tools/call` | Execute a tool | `name`, `arguments` |

#### Available Tools

**1. natural_gas.prices**
- **Description**: Query natural gas prices from EIA API
- **Parameters**:
  - `series` (required): Price series (e.g., "henry_hub_spot")
  - `start` (optional): Start date (YYYY-MM-DD)
  - `end` (optional): End date (YYYY-MM-DD)
  - `frequency` (optional): Data frequency ("daily", "weekly", "monthly")
- **Returns**: JSON with series data and values

**2. natural_gas.storage**
- **Description**: Query natural gas storage data from EIA API
- **Parameters**:
  - `region` (required): Region (e.g., "lower48")
  - `start` (optional): Start date (YYYY-MM-DD)
  - `end` (optional): End date (YYYY-MM-DD)
  - `frequency` (optional): Data frequency
- **Returns**: JSON with storage data by date

**3. natural_gas.production**
- **Description**: Query natural gas production data from EIA API
- **Parameters**:
  - `region` (optional): Region
  - `start` (optional): Start date (YYYY-MM-DD)
  - `end` (optional): End date (YYYY-MM-DD)
- **Returns**: JSON with production data

#### MCP Client Integration

**File**: `backend/infrastructure/tool_clients.py`

```python
class MCPClient:
    """JSON-RPC 2.0 MCP client with stdio transport."""
    
    def __init__(self, command: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None):
        self.command = command or ["python", "-m", "eia_mcp.server"]
        self.env = env or os.environ
        self.env["EIA_API_KEY"] = "your_api_key_here"
        self.proc = None
        self.connected = False
        self.session_id: Optional[str] = None
```

**Client Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `connect()` | Start server subprocess and initialize | session_id |
| `initialize()` | Send initialize request | session_id |
| `list_tools()` | Get available tools | List[Dict] |
| `call_tool(name, arguments)` | Execute a tool | Dict (result) |
| `_rpc(method, params, id_)` | Low-level JSON-RPC call | Dict (response) |

**Usage Example:**

```python
# Initialize client
client = MCPClient()
await client.connect()

# List available tools
tools = await client.list_tools()
# Returns: [{"name": "natural_gas.prices", "description": "...", "inputSchema": {...}}, ...]

# Call a tool
result = await client.call_tool(
    "natural_gas.prices",
    {"series": "henry_hub_spot", "start": "2024-01-01", "end": "2024-12-31"}
)
# Returns: {"content": [{"type": "text", "text": "{...}"}]}
```

**Environment Variables:**
- `EIA_API_KEY`: Required for EIA API access (get from https://www.eia.gov/opendata/)

**Error Handling:**
- JSON-RPC errors returned with error codes
- Tool execution errors wrapped in `{"isError": True, "content": [...]}`
- Process communication errors logged and raised

**Integration with Agent:**

```python
# In agent.py
from infrastructure.tool_clients import MCPClient

# Initialize in agent
self.mcp_client = MCPClient()
await self.mcp_client.connect()

# List tools and add to agent's tool registry
eia_tools = await self.mcp_client.list_tools()
self.eia_tools = [MCPTool(**t) for t in eia_tools]
```

---

### Tool Argument Validation

All tools use **Pydantic models** for argument validation:

```python
# GasExportTool arguments
class GasExportedQuantityArgs(BaseModel):
    pointLabel: str = Field(..., description="Export point label")
    from_: str = Field(..., description="Start date (YYYY-MM-DD)")
    to: str = Field(..., description="End date (YYYY-MM-DD)")

# RegulationTool arguments
class RegulationQueryArgs(BaseModel):
    question: str = Field(..., description="Question about regulation")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of sources")
```

**Benefits:**
- Type safety and validation
- Automatic error messages for invalid input
- Self-documenting tool interfaces
- IDE autocomplete support

## 🔄 LangGraph Agent Workflow

### State Management

**AgentState** (TypedDict):
```python
class AgentState(TypedDict, total=False):
    messages: Sequence[BaseMessage]           # LangChain messages (Human, AI, System)
    memory: Memory                            # User preferences + conversation history
    tools_called: List[ToolCall]             # History of tool executions
    current_user_id: str                     # Current user identifier
    next_action: str                         # Routing decision ("call_tool" | "final_answer")
    tool_decision: Dict[str, Any]            # Tool name + arguments for execution
    iteration_count: int                     # Loop counter (MAX_ITERATIONS = 10)
```

### Workflow Nodes

**1. agent_decide**
- **Purpose**: LLM analyzes user request and decides next action
- **Input**: Current state with messages and memory
- **Process**:
  - Builds system prompt with user preferences and tool descriptions
  - Sends decision prompt to GPT-4
  - Parses JSON response for action decision
  - Increments iteration_count if calling tool
- **Output**: Updated state with `next_action` and `tool_decision`

**2. tool_{tool_name}** (dynamic nodes)
- **Purpose**: Execute specific tool (regulation, gas_exported_quantity, MCP)
- **Input**: State with tool_decision (name + arguments)
- **Process**:
  - Calls tool's `execute(**arguments)` method
  - Creates ToolCall record (success/error)
  - Adds SystemMessage with tool result
- **Output**: State with updated messages and tools_called

**3. agent_finalize**
- **Purpose**: Generate natural language response to user
- **Input**: State with conversation history and tool results
- **Process**:
  - Detects user's language (Hungarian/English)
  - Builds final prompt with conversation context
  - Generates conversational response
  - Adds AIMessage to conversation
- **Output**: State with final answer

### Conditional Routing

**_route_decision(state) → str**:
- Checks `iteration_count` < MAX_ITERATIONS (prevent infinite loops)
- If `next_action == "call_tool"`:
  - Returns `f"tool_{tool_name}"` (e.g., "tool_regulation")
- Else:
  - Returns `"final_answer"` (route to finalize node)

### Decision Logic

The agent's decision prompt enforces critical rules:

```json
{
    "action": "call_tool" | "final_answer",
    "tool_name": "TOOL_NAME",
    "arguments": {...},
    "reasoning": "brief explanation"
}
```

**Rules:**
1. **Never call the same tool with same arguments twice** (prevents loops)
2. **If tool failed, move to final_answer** (don't retry)
3. **If task is impossible, explain in final_answer** (e.g., future predictions)
4. **Execute multiple tasks ONE AT A TIME** (sequential tool calls)
5. **Only finalize when ALL tasks complete OR a task is impossible**

**Example Decision:**
```json
{
    "action": "call_tool",
    "tool_name": "gas_exported_quantity",
    "arguments": {
        "pointLabel": "VIP Bereg",
        "from": "2025-01-01",
        "to": "2025-12-31"
    },
    "reasoning": "get gas export data for the specified period"
}
```

### Language Detection

**Automatic language detection** in `agent_finalize_node`:

```python
# Regex-based word matching
hungarian_words = r'\b(ki|mi|hol|mikor|miért|hogyan|van|törvény|szabályozás)\b'
english_words = r'\b(who|what|where|when|why|how|is|are|regulation|law)\b'

# Count matches
hungarian_matches = len(re.findall(hungarian_words, user_message_lower))
english_matches = len(re.findall(english_words, user_message_lower))

# Set language instruction
if hungarian_matches > english_matches:
    language_instruction = "Válaszolj magyarul. A válasznak magyar nyelvűnek kell lennie."
else:
    language_instruction = "You MUST respond in English. Translate any Hungarian content to English."
```

### Tool Selection Logic

**Gas Export Queries:**
- Keywords: "gas export", "gas flow", "quantity between countries", "HU>UA"
- **ALWAYS** use `gas_exported_quantity` tool
- **NEVER** answer from regulation or history

**Regulation Queries:**
- Keywords: "regulation", "law", "act", "MEKH", "felhatalmazás", "törvény"
- Use `regulation` tool with `action="query"`

**EIA Data (via MCP):**
- Keywords: "natural gas prices", "storage", "production", "henry hub"
- Call MCP tools via `mcp_client.call_tool()`

### Iteration Limit

**MAX_ITERATIONS = 10** prevents infinite loops:

```python
def _route_decision(self, state: AgentState) -> str:
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        logger.warning(f"Max iterations ({MAX_ITERATIONS}) reached, forcing finalize")
        return "final_answer"
    # ... normal routing
```

**Use Cases:**
- User asks multiple related questions → agent loops through tools
- Tool returns partial data → agent may call another tool
- Agent gets stuck in decision loop → forced to finalize after 10 iterations


## 🛡️ Latest Changes: Full Pydantic Validation (2026.01)

### What’s new?
- ✅ **Pydantic validation** is now used everywhere: domain models, API schemas, tool arguments, persistence, and ToolNode wrappers
- ✅ **Explicit Pydantic argument models** for all tools (see `services/tools.py`, `infrastructure/tool_clients.py`)
- ✅ **Automatic validation** for all incoming API requests and tool calls
- ✅ **Detailed error messages** for invalid input (type errors, missing fields, constraint violations)
- ✅ **Consistent serialization**: all models use `.model_dump()` / `.model_dump_json()` for persistence and API responses
- ✅ **Developer experience**: type-safe, documented, and IDE-friendly codebase

### Example: Tool Argument Validation
```python
from pydantic import BaseModel, Field, ValidationError

class GasExportedQuantityArgs(BaseModel):
  pointLabel: str = Field(..., description="Export point label (e.g. 'VIP Bereg')")
  from_: str = Field(..., description="Start date (YYYY-MM-DD)")
  to: str = Field(..., description="End date (YYYY-MM-DD)")

async def gas_exported_quantity(pointLabel: str, from_: str, to: str) -> str:
  try:
    args = GasExportedQuantityArgs(pointLabel=pointLabel, from_=from_, to=to)
  except ValidationError as e:
    return f"Invalid parameters: {e}"
  # ...
```

### API & Persistence
- All FastAPI endpoints use Pydantic request/response models (automatic validation)
- All file-based persistence uses `.model_dump_json()` and loads with Pydantic validation

### Developer Benefits
- Type safety everywhere
- Automatic OpenAPI documentation
- Easy error handling and debugging
- No more silent data corruption or missing fields

See the README “Pydantic Használat az Alkalmazásban” section for full patterns and best practices!

### Persistence Model

#### User Profile (`data/users/{user_id}.json`)
```json
{
  "user_id": "user_123",
  "language": "hu",
  "default_city": "Budapest",
  "created_at": "2025-12-08T10:00:00",
  "updated_at": "2025-12-08T10:30:00",
  "preferences": {}
}
```

**Behavior**:
- ✅ Created automatically on first interaction
- ✅ Updated when preferences change
- ❌ **Never deleted** - persists across all sessions


#### Conversation History (`data/sessions/{session_id}.json`)
```json
{
  "session_id": "session_1767436277743_e72yl3tzd",
  "messages": [
    {
      "role": "user",
      "content": "Mire van felhatalmazása a MEKH-nek (Hivatal) és mely pontok szerint?",
      "timestamp": "2026-01-03T15:58:57.179776",
      "metadata": null
    },
    {
      "role": "system",
      "content": "📚 **Answer from 'gaztorveny':**\n\nA Magyar Energetikai és Közmű-szabályozási Hivatal (MEKH) felhatalmazásai a 2008. évi XL. törvény - a földgázellátásról szóló törvény alapján széleskörűek és részletesen meghatározottak. Ezek közé tartoznak a földgázpiac szabályozásával, felügyeletével és a piaci szereplők tevékenységének ellenőrzésével kapcsolatos feladatok. A törvény alapján a MEKH felhatalmazást kap többek között:\n\n1. A földgázellátás keretszabályainak, árszabályozási ciklusainak meghatározására, a csatlakozási díjak és a külön díjak fizetésére kötelezettek körének, valamint az alkalmazásuk feltételeinek meghatározására.\n\n2. A földgázrendszerre történő csatlakozás részletes szabályainak, beleértve a műszaki-gazdasági feltételeket és azok közzétételét, valamint a földgázelosztó és földgázszállító csatlakozással kapcsolatos együttműködés szabályait.\n\n3. A szállítási rendszerüzemeltetési díjból származó árbevétel szállítási rendszerüzemeltetők közötti megosztására vonatkozó kiegyenlítő fizetések számítási módszerének és részletes szabályainak meghatározására.\n\n4. A rendszeregyensúlyozásra vonatkozó módszertan és részletszabályok, beleértve a rendszerüzemeltetői adatszolgáltatásokat és egyensúlytartási szolgáltatásokat.\n\n5. A rendszer-összekötési pontokra vonatkozó szabályok alkalmazását harmadik országok felől való betáplálási és kiadási pontokra.\n\n6. Az adatszolgáltatásra kötelezettek által szolgáltatandó adatok körének, az adatszolgáltatás teljesítésének módjára és esedékességére vonatkozó követelmények meghatározására.\n\n7. A válsághelyzeti monitoringrendszer működésének részletszabályainak, valamint a védett felhasználók és a szolidaritási alapon védett felhasználók földgáz felhasználásának meghatározására.\n\n8. Az energetikai szabályozási tesztkörnyezet által támogatott célok, a kérelem benyújtására jogosultak körének és a kérelem elbírálásával kapcsolatos szabályok meghatározására.\n\nEzen felül a MEKH felhatalmazást kap a műszaki-biztonsági szempontból jelentős munkakörök betöltéséhez szükséges szakmai képesítés és gyakorlat, valamint a továbbképzésekkel kapcsolatos szabályok meghatározására, a gázszerelők és gázkészülék-javítók tevékenységének részletes feltételeire, a műszaki biztonsági követelményekre, valamint a gázfogyasztó készülékek forgalomba hozatalára és üzembe helyezésére vonatkozó szabályokra.\n\n**Sources:**\n[Page 146]: 2008. évi XL. törvény - a földgázellátásról \nHatály: 2025.VIII.1. -   Jogtár \n  147/165 oldal \nkeret...\n[Page 145]: 2008. évi XL. törvény - a földgázellátásról \nHatály: 2025.VIII.1. -   Jogtár \n  146/165 oldal \nHivat...\n[Page 136]: 2008. évi XL. törvény - a földgázellátásról \nHatály: 2025.VIII.1. -   Jogtár \n  137/165 oldal \n(4) A...",
      "timestamp": "2026-01-03T15:59:42.883731",
      "metadata": null
    },
    {
      "role": "assistant",
      "content": "A Magyar Energetikai és Közmű-szabályozási Hivatal (MEKH) számos fontos és részletesen meghatározott feladattal rendelkezik a földgázellátás szabályozása terén, a 2008. évi XL. törvény alapján. Ezek a feladatok magukban foglalják a piac szabályozását, felügyeletét és a piaci szereplők ellenőrzését. A MEKH felhatalmazásai között szerepelnek például a földgázellátás keretszabályainak meghatározása, a csatlakozási díjak szabályozása, a rendszerüzemeltetési díjak megosztása, adatszolgáltatási követelmények meghatározása és a válsághelyzeti intézkedések szabályozása. Emellett a MEKH felel a műszaki biztonsági előírások, a gázszerelők és javítók tevékenységének szabályozása, valamint a gázfogyasztó készülékek forgalomba hozatalára és üzembe helyezésére vonatkozó előírások megállapításáért is. Ezek a felhatalmazások biztosítják a földgázpiac zökkenőmentes és biztonságos működését.",
      "timestamp": "2026-01-03T15:59:42.890939",
      "metadata": null
    }
  ],
  "summary": null,
  "created_at": "2026-01-03T15:58:57.176536",
  "updated_at": "2026-01-03T15:59:42.903534"
}
```

**Behavior**:
- ✅ All messages (user, assistant, system, tool) are persisted
- ✅ Can be cleared with "reset context" command
- ✅ User profile remains intact after reset

### Frontend Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ChatWindow.tsx      # Scrollable message list
│   │   ├── MessageBubble.tsx   # Individual message display
│   │   ├── ChatInput.tsx       # User input field
│   │   └── DebugPanel.tsx      # Tools & memory viewer
│   ├── App.tsx                 # Main application
│   ├── api.ts                  # Backend API client
│   ├── types.ts                # TypeScript interfaces
│   └── utils.ts                # Utility functions
├── index.html
├── vite.config.ts
└── package.json
```

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **Docker & Docker Compose** (for containerized deployment)
- **OpenAI API Key** (required)
- **EIA API Key** (optional, for MCP natural gas data)

### Quick Start: Docker (Recommended)

1. **Clone and navigate**:
   ```bash
   git clone <repository>
   cd dored2
   ```

2. **Set up environment**:
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=sk-your-key-here" > .env
   echo "EIA_API_KEY=your-eia-key-here" >> .env  # Optional
   ```

3. **Run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

4. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Test MCP Server (Standalone)

The MCP server can be tested independently:

```bash
cd backend
python -m eia_mcp.server
```

Send JSON-RPC requests via stdin:
```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}
{"jsonrpc": "2.0", "id": 2, "method": "initialized", "params": {}}
{"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "natural_gas.prices", "arguments": {"series": "henry_hub_spot"}}}
```

### Local Development (Option 2)

#### Backend

1. **Navigate to backend**:
   ```bash
   cd backend
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**:
   ```bash
   # Windows PowerShell:
   $env:OPENAI_API_KEY="sk-your-key-here"
   $env:EIA_API_KEY="your-eia-key-here"
   
   # Linux/Mac:
   export OPENAI_API_KEY='sk-your-key-here'
   export EIA_API_KEY='your-eia-key-here'
   ```

5. **Run the server**:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend

1. **Navigate to frontend**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Run development server**:
   ```bash
   npm run dev
   ```

4. **Access**: http://localhost:3000

## 📚 API Endpoints

### `POST /api/chat`
Process chat message or reset context.

**Request**:
```json
{
  "user_id": "user_123",
  "message": "Mire van felhatalmazása a MEKH-nek (Hivatal) és mely pontok szerint?",
  "session_id": "session_1767436277743_e72yl3tzd"
}
```

**Response**:
```json
{
  "final_answer": "A Magyar Energetikai és Közmű-szabályozási Hivatal (MEKH) számos fontos és részletesen meghatározott feladattal rendelkezik a földgázellátás szabályozása terén, a 2008. évi XL. törvény alapján. Ezek a feladatok magukban foglalják a piac szabályozását, felügyeletét és a piaci szereplők ellenőrzését. A MEKH felhatalmazásai között szerepelnek például a földgázellátás keretszabályainak meghatározása, a csatlakozási díjak szabályozása, a rendszerüzemeltetési díjak megosztása, adatszolgáltatási követelmények meghatározása és a válsághelyzeti intézkedések szabályozása. Emellett a MEKH felel a műszaki biztonsági előírások, a gázszerelők és javítók tevékenységének szabályozása, valamint a gázfogyasztó készülékek forgalomba hozatalára és üzembe helyezésére vonatkozó előírások megállapításáért is. Ezek a felhatalmazások biztosítják a földgázpiac zökkenőmentes és biztonságos működését.",
  "tools_used": [
    {
      "name": "regulation",
      "arguments": {
        "action": "query",
        "question": "Mire van felhatalmazása a MEKH-nek (Hivatal) és mely pontok szerint?",
        "top_k": 5
      },
      "success": true,
      "result": {
        "answer": "A Magyar Energetikai és Közmű-szabályozási Hivatal (MEKH) felhatalmazásai a 2008. évi XL. törvény - a földgázellátásról szóló törvény alapján széleskörűek és részletesen meghatározottak. Ezek közé tartoznak a földgázpiac szabályozásával, felügyeletével és a piaci szereplők tevékenységének ellenőrzésével kapcsolatos feladatok. A törvény alapján a MEKH felhatalmazást kap többek között: ...",
        "sources": [
          {"page": 146, "content_preview": "2008. évi XL. törvény - a földgázellátásról ..."},
          {"page": 145, "content_preview": "2008. évi XL. törvény - a földgázellátásról ..."},
          {"page": 136, "content_preview": "2008. évi XL. törvény - a földgázellátásról ..."}
        ],
        "regulation_title": "gaztorveny"
      }
    }
  ],
  "memory_snapshot": {
    "preferences": {
      "language": "hu"
    },
    "workflow_state": {
      "flow": null,
      "step": 0,
      "total_steps": 0
    },
    "message_count": 3
  },
  "logs": ["Tools called: 1"]
}
```

### `GET /api/session/{session_id}`
Get conversation history.

### `GET /api/profile/{user_id}`
Get user profile.

### `PUT /api/profile/{user_id}`
Update user profile.

**Request**:
```json
{
  "language": "en",
  "default_city": "Szeged"
}
```


### `GET /api/history/search?q=MEKH`
Search conversation history for regulation tool queries.

**Example Response:**
```json
{
  "results": [
    {
      "session_id": "session_1767436277743_e72yl3tzd",
      "message": {
        "role": "user",
        "content": "Mire van felhatalmazása a MEKH-nek (Hivatal) és mely pontok szerint?",
        "timestamp": "2026-01-03T15:58:57.179776"
      },
      "answer": {
        "role": "assistant",
        "content": "A Magyar Energetikai és Közmű-szabályozási Hivatal (MEKH) számos fontos és részletesen meghatározott feladattal rendelkezik a földgázellátás szabályozása terén, a 2008. évi XL. törvény alapján. ..."
      },
      "sources": [
        {"page": 146, "content_preview": "2008. évi XL. törvény - a földgázellátásról ..."},
        {"page": 145, "content_preview": "2008. évi XL. törvény - a földgázellátásról ..."}
      ]
    }
  ],
  "total": 1
}
```

### `POST /api/mcp/tool_call`
Call an MCP tool directly (for testing and development).

**Request Body**:
```json
{
  "tool_name": "natural_gas.prices",
  "arguments": {
    "series": "henry_hub_spot",
    "start": "2024-01-01",
    "end": "2024-12-31",
    "frequency": "monthly"
  }
}
```

**Response**:
```json
{
  "success": true,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"series\": \"henry_hub_spot\", \"data\": [{\"date\": \"2024-01-01\", \"value\": 3.50}, ...]}"
      }
    ]
  }
}
```

### `GET /test-regulation-tool`
Test endpoint for verifying RegulationRAGClient functionality.

**Response**:
```json
{
  "success": true,
  "result": {
    "answer": "Test query result...",
    "sources": [...]
  }
}
```

## 💡 Example Interactions


### Language Preference Update
```
User: From now on, answer in English
Agent: [Updates user profile]
Response: Understood! I will respond in English from now on.
```

### Reset Context
```
User: reset context
Agent: [Clears conversation history, keeps profile]
Response: Context has been reset. We are starting a new conversation, but your preferences are preserved.
```


## 🎨 Special Features

### Reset Context Command
When a user sends `"reset context"` (case-insensitive):
1. ✅ Conversation history is **cleared**
2. ✅ User profile is **preserved**
3. ✅ New session starts fresh
4. ✅ Preferences (language, city) remain intact

**Implementation**: Detected in `ChatService.process_message()` before agent invocation.

### User Profile Management
- **Never deleted**: Only created/loaded and updated
- **Automatic updates**: Agent detects preference changes in conversation
- **Manual updates**: Via `PUT /api/profile/{user_id}` endpoint
- **Persistent across sessions**: Stored in `data/users/{user_id}.json`

### Memory Context
The agent receives:
- **Recent messages**: Last 20 messages for context
- **User preferences**: Language, default city, custom preferences
- **Workflow state**: Multi-step process tracking (extensible)

## 🏗️ SOLID Principles Applied

### Single Responsibility Principle (SRP)
- Each class/module has **one clear purpose**
- `ChatService`: Only orchestrates chat workflow

### Open/Closed Principle (OCP)
- **Easy to add new tools** without modifying existing code
- New tool: Implement `IToolClient`, create wrapper in `tools.py`, register in `agent.py`
- **No changes needed** to agent core logic or graph structure

### Liskov Substitution Principle (LSP)
- All tool clients implement `IToolClient` interface
- Can be swapped without breaking agent functionality
- Mock implementations for testing

### Interface Segregation Principle (ISP)
- **Specific interfaces** for different concerns:
  - `IUserRepository`: User profile operations
  - `IConversationRepository`: Conversation operations
  - `IRegulationRAGClient`: Specific tool operations
- Clients only depend on methods they use

### Dependency Inversion Principle (DIP)
- High-level modules (`ChatService`, `AIAgent`) depend on **abstractions** (`IUserRepository`, `IToolClient`)
- Low-level modules (repositories, API clients) implement abstractions
- **Easy to swap implementations** (file storage → database, real APIs → mocks)

## 🛠️ Technologies

### Backend
- **FastAPI**: Modern async web framework with automatic OpenAPI documentation
- **LangGraph**: Agent orchestration with StateGraph workflow
- **LangChain**: LLM integration utilities and message abstractions
- **OpenAI GPT-4**: Language model for reasoning and natural language generation
- **Pydantic v2**: Data validation, serialization, and settings management
- **FAISS**: Vector database for similarity search (regulation RAG)
- **httpx**: Async HTTP client for external API calls
- **PyPDFLoader**: PDF document processing for RAG pipeline
- **MCP (Model Context Protocol)**: JSON-RPC 2.0 server for EIA data integration

### Frontend
- **React 18**: UI library with hooks
- **TypeScript**: Type-safe JavaScript
- **Vite**: Fast build tool and dev server
- **Axios**: HTTP client for API communication
- **CSS**: Custom ChatGPT-like styling

### Infrastructure
- **Docker**: Containerization for backend and frontend
- **Docker Compose**: Multi-container orchestration
- **Nginx**: Static file serving and reverse proxy for frontend
- **JSON files**: File-based persistence (simple, transparent, easy to inspect)

### External APIs
- **Transparency.host (ENTSOG)**: European gas transmission data
- **EIA API**: U.S. Energy Information Administration natural gas data

## 📂 Data Storage

All data is stored in JSON files for transparency and easy inspection:

```
data/
├── users/           # User profiles (never deleted)
│   └── user_123.json
├── sessions/        # Conversation histories (can be reset)
│   └── session_456.json
└── files/           # User-created files
    └── user_123/
        └── note.txt
```

## 🧪 Development

### Backend Tests
```bash
cd backend
pytest  # (Add tests in tests/ directory)
```

### Frontend Tests
```bash
cd frontend
npm test  # (Add tests with Vitest/Jest)
```

### Type Checking
```bash
cd frontend
npm run type-check
```

## 🔒 Environment Variables

### Required
- `OPENAI_API_KEY`: Your OpenAI API key (required for GPT-4 and embeddings)
  - Get from: https://platform.openai.com/api-keys

### Optional
- `EIA_API_KEY`: U.S. Energy Information Administration API key (for MCP server)
  - Get from: https://www.eia.gov/opendata/
  - Default: Test key provided in code (limited access)

### Configuration
Create a `.env` file in the project root:
```bash
OPENAI_API_KEY=sk-your-openai-api-key-here
EIA_API_KEY=your-eia-api-key-here
```
## 🧠 Hybrid Memory System (NEW)

### Overview
The Hybrid Memory system is a production-oriented, multi-layer memory architecture for conversational AI, optimized for:
- Long-running conversations
- Mixed information types (dialogue, preferences, documents)
- High context retention and reproducibility

#### Memory Layers
Hybrid memory consists of four coordinated layers:
- **Summary**: Continuously updated, versioned conversation summary (global context)
- **Facts**: Structured key–value facts (preferences, profile data, stable truths)
- **Recent Messages**: Bounded rolling window (last ~3 turns)
- **Retrieved Context (RAG)**: On-demand external knowledge, only when relevant

#### State Channels
All memory is explicit and observable via state channels:
- `messages` – trimmed recent turns
- `summary` – versioned summary
- `facts` – structured fact store
- `retrieved_context` – RAG results (optional)
- `trace` – execution trace for observability

#### Deterministic State Reduction
All channels use deterministic reducers:
- `messages_reducer()`   – deduplicate, sort, trim to N turns
- `summary_reducer()`    – replace summary, increment version
- `facts_reducer()`      – last-write-wins by timestamp
- `trace_reducer()`      – append-only, capped size

#### Hybrid Execution Flow
Entry → metrics_logger → summarizer → facts_extractor → [rag_recall?] → pii_filter → answer → END

**Conditional RAG**: Retrieval is triggered only if the user message contains recall intent (e.g., "remember", "recall", "earlier", "you said").

#### API Usage
To use hybrid memory, set `memory_mode: "hybrid"` in your chat request:

```json
POST /api/chat
{
  "session_id": "session_id",
  "user_id": "user_id",
  "message": "Remember what we discussed about pricing?",
  "memory_mode": "hybrid",
  "pii_mode": "placeholder"
}
```

The response includes:
- Generated answer
- Hybrid memory snapshot: summary version, facts count, recent message count, retrieved context flag, trace length

#### Checkpointing & Restore
Hybrid memory supports full state checkpointing and deterministic restore for rollback, debugging, and replay.

#### PII Handling
PII filtering is applied before persistence across all Hybrid layers. Supported modes: `placeholder` (default), `pseudonymize`.

#### When to Use Hybrid Memory
Use when conversations are long, user preferences must persist, or answers depend on both dialogue and documents. Avoid if minimal latency is required or conversations are short-lived.

---

**Built with ❤️ for regulatory compliance team**


## 📊 Monitoring: Prometheus & Grafana

### Telepítés és használat

- A projekt tartalmazza a Prometheus és Grafana integrációt a backend metrikák monitorozásához.
- A `docker-compose.yml` automatikusan elindítja a Prometheus-t (port: 9090) és a Grafanát (port: 3001).
- A Prometheus konfigurációja: `backend/observability/prometheus.yml` (alapértelmezett target: `backend:8000/metrics`).
- A Grafana alapértelmezett bejelentkezés: **admin / admin**

#### Indítás
```sh
docker-compose up --build
```

#### Elérés
- Prometheus UI: [http://localhost:9090](http://localhost:9090)
- Grafana UI: [http://localhost:3001](http://localhost:3001)

#### Prometheus metrikák
A backend számos egyedi metrikát exportál a `/metrics` végponton keresztül. Ezek közül néhány:

| Metrika név                    | Leírás                                      | Label(ek)         |
|-------------------------------|---------------------------------------------|-------------------|
| llm_inference_count           | Összes LLM inferencia hívás                 | model             |
| llm_inference_latency_seconds | LLM hívások késleltetése (hisztogram)       | model             |
| llm_inference_token_input_total| Összes bemeneti token                       | model             |
| llm_inference_token_output_total| Összes kimeneti token                      | model             |
| llm_cost_total_usd            | LLM költség USD-ben                         | model             |
| agent_execution_count         | Agent végrehajtások száma                   | -                 |
| tool_invocation_count         | Eszköz hívások száma                        | tool              |
| agent_errors_total            | Agent hibák száma                           | error_type, node, environment |
| agent_rag_retrievals_total    | RAG lekérések száma                         | status, environment|

#### Példa Grafana lekérdezések

- Összes LLM hívás modellek szerint:
  ```
  sum(llm_inference_count) by (model)
  ```
- Eszköz hívások száma eszközönként:
  ```
  sum(tool_invocation_count) by (tool)
  ```
- 95. percentilis LLM válaszidő:
  ```
  histogram_quantile(0.95, sum(rate(llm_inference_latency_seconds_bucket[5m])) by (le, model))
  ```

#### Új metrikák hozzáadása
Új metrikát a `backend/observability/metrics.py` fájlban lehet definiálni, és a megfelelő helyen `.inc()`, `.observe()` vagy `.set()` hívással növelni.

#### Hibakeresés
- Ha a metrikák nem jelennek meg, ellenőrizd a `/metrics` végpontot (http://localhost:8000/metrics) és a Prometheus targeteket.
- A metrikák csak akkor jelennek meg, ha legalább egyszer növelve lettek.


A complete working example demonstrating an AI Agent workflow with a Python backend (FastAPI + LangGraph), React frontend, and MCP (Model Context Protocol) server integration.