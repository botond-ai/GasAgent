# 🔄 LangGraph Workflow Documentation

## SupportAI - Multi-Tool Agent System

This document provides a comprehensive analysis of the LangGraph-based AI agent system that powers the SupportAI application. The system implements a sophisticated workflow that processes user support requests through a predefined sequence of tools.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [LangGraph State Machine](#langgraph-state-machine)
3. [Workflow Modes](#workflow-modes)
4. [Tool Sequence (Support Feedback)](#tool-sequence-support-feedback)
5. [Complete Tool Reference](#complete-tool-reference)
6. [JSON Schemas](#json-schemas)
7. [Data Flow Diagrams](#data-flow-diagrams)
8. [Database Schema](#database-schema)
9. [API Endpoints](#api-endpoints)

---

## 🏗️ Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Chat Window │  │ View Tickets│  │ Debug Panel │  │ File Upload │ │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └──────┬──────┘ │
└─────────┼────────────────┼──────────────────────────────────┼───────┘
          │                │                                  │
          ▼                ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                            │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      ChatService                                 ││
│  │  • Process messages    • Manage sessions    • Build memory      ││
│  └──────────────────────────────┬──────────────────────────────────┘│
│                                 │                                    │
│  ┌──────────────────────────────▼──────────────────────────────────┐│
│  │                        AIAgent (LangGraph)                       ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  ││
│  │  │agent_decide │──│ tool_nodes  │──│   agent_finalize        │  ││
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                 │                                    │
│  ┌──────────────────────────────▼──────────────────────────────────┐│
│  │                          TOOLS (13+)                             ││
│  │  Weather│Translator│Documents│Sentiment│FX_Rates│Guardrails│JSON_Creator││
│  │  SQLite_Save│Photo_Upload│Email_Send│Radio│Crypto│Geocode       ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ SQLite   │    │  pCloud  │    │  Gmail   │    │ External │
    │ Database │    │ Storage  │    │  SMTP    │    │   APIs   │
    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, CSS |
| Backend | FastAPI, Python 3.11 |
| AI Framework | LangGraph, LangChain |
| LLM | OpenAI GPT-4 Turbo |
| Vector DB | FAISS |
| Database | SQLite |
| Cloud Storage | pCloud API |
| Email | Gmail SMTP |
| Containerization | Docker, Docker Compose |

---

## 🔄 LangGraph State Machine

### AgentState Definition

```python
class AgentState(TypedDict, total=False):
    """State object for LangGraph agent."""
    messages: Sequence[BaseMessage]      # Conversation messages
    memory: Memory                        # User memory context
    tools_called: List[ToolCall]         # Tools executed in this run
    current_user_id: str                 # Current user identifier
    next_action: str                     # Next action to take
    tool_decision: Dict[str, Any]        # Current tool decision
    iteration_count: int                 # Iteration counter (max 10)
    is_support_feedback: bool            # Support workflow flag
    translated_user_message: str         # English translation for RAG
```

### Graph Structure

```
                    ┌──────────────────┐
                    │   Entry Point    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
            ┌───────│  agent_decide    │◄──────────────────┐
            │       └────────┬─────────┘                   │
            │                │                             │
            │    ┌───────────┼───────────┐                 │
            │    │           │           │                 │
            ▼    ▼           ▼           ▼                 │
    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
    │tool_   │ │tool_   │ │tool_   │ │tool_   │           │
    │weather │ │docs    │ │fx_rates│ │ ...    │           │
    └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘           │
        │          │          │          │                 │
        └──────────┴──────────┴──────────┘                 │
                             │                             │
                             └─────────────────────────────┘
                             │
                             ▼ (when action = "final_answer")
                    ┌──────────────────┐
                    │ agent_finalize   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │       END        │
                    └──────────────────┘
```

### Routing Logic

```python
def _route_decision(self, state: AgentState) -> str:
    # Check iteration limit (max 10)
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return "final_answer"
    
    action = state.get("next_action", "final_answer")
    
    if action == "call_tool" and "tool_decision" in state:
        tool_name = state["tool_decision"].get("tool_name")
        if tool_name in self.tools:
            return f"tool_{tool_name}"
    
    return "final_answer"
```

---

## 🔀 Workflow Modes

### Mode 1: Support Feedback Workflow (Forced Sequence)

When a user message is detected as a support issue, the system forces a predefined tool sequence:

```
User Message
     │
     ▼
┌─────────────────────┐
│ Detect Support Issue│ ◄── Keyword matching + short message detection
└──────────┬──────────┘
           │ YES
           ▼
┌─────────────────────┐
│ 1. Translator       │ ◄── Translate to English if needed
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 2. Sentiment        │ ◄── Analyze emotional tone
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 3. Weather          │ ◄── Get weather for greeting
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 4. Documents (RAG)  │ ◄── Identify issue type from knowledge base
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 5. FX Rates USD→EUR │ ◄── Convert cost to EUR
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 6. FX Rates USD→HUF │ ◄── Convert cost to HUF
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 7. Final Response   │ ◄── Generate warm, helpful response
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 8. Guardrails       │ ◄── Mask PII for GDPR/legal compliance (emails, phones, IDs → ###)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 9. JSON Creator     │ ◄── Create structured ticket (with masked PII)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 10. Photo Upload    │ ◄── Upload attachments to pCloud (if any)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 11. SQLite Save     │ ◄── Save ticket to database
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 12. Email Send      │ ◄── Notify team via email
└──────────┴──────────┘
```

### Mode 2: General Query Workflow (LLM-Driven)

For non-support queries, the LLM decides which tools to use:

```
User Message
     │
     ▼
┌─────────────────────┐
│ LLM Decision        │ ◄── GPT-4 analyzes request
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌─────────┐ ┌─────────┐
│ Tool(s) │ │ Direct  │
│ Needed  │ │ Answer  │
└────┬────┘ └────┬────┘
     │           │
     ▼           │
┌─────────┐      │
│ Execute │      │
│ Tool(s) │      │
└────┬────┘      │
     │           │
     └─────┬─────┘
           ▼
┌─────────────────────┐
│ Generate Response   │
└─────────────────────┘
```

---

## 🛠️ Tool Sequence (Support Feedback)

### Step-by-Step Breakdown

| Step | Tool | Purpose | Input | Output |
|------|------|---------|-------|--------|
| 1 | **Translator** | Detect & translate to English | User message | English text for RAG |
| 2 | **Sentiment** | Analyze emotional tone | User message | positive/neutral/frustrated + confidence |
| 3 | **Weather** | Get weather for greeting | City (Budapest) | Current temp, forecast |
| 4 | **Documents** | Identify issue from KB | English query | Issue type, priority, SLA, cost |
| 5 | **FX Rates** | Convert USD to EUR | base=USD, target=EUR | Exchange rate |
| 6 | **FX Rates** | Convert USD to HUF | base=USD, target=HUF | Exchange rate |
| 7 | **Finalize** | Generate response | All tool results | Warm, helpful response |
| 8 | **Guardrails** | Mask PII for GDPR compliance | All conversation data | Masked text with ###PII### |
| 9 | **JSON Creator** | Create ticket | All data (with masked PII) | TK### ticket JSON |
| 10 | **Photo Upload** | Upload attachments | Files, ticket# | pCloud folder |
| 11 | **SQLite Save** | Persist to database | Ticket data | Database record |
| 12 | **Email Send** | Notify team | Ticket data | Email confirmation |

---

## 📚 Complete Tool Reference

### 1. Weather Tool
```python
class WeatherTool:
    name = "weather"
    description = "Get weather forecast for a city or coordinates"
    
    async def execute(
        city: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> Dict[str, Any]
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| city | string | No* | City name (e.g., "Budapest") |
| lat | float | No* | Latitude coordinate |
| lon | float | No* | Longitude coordinate |

*Either city OR lat/lon required

---

### 2. Translator Tool
```python
class TranslatorTool:
    name = "translator"
    SUPPORTED_LANGUAGES = ['en', 'hu', 'de', 'fr', 'es', 'it', 'pt', 'ru']
    
    async def execute(
        action: str = "detect",
        text: Optional[str] = None,
        target_language: Optional[str] = None,
        source_language: Optional[str] = None
    ) -> Dict[str, Any]
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| action | string | Yes | "detect" or "translate" |
| text | string | Yes | Text to process |
| target_language | string | For translate | Target language code |
| source_language | string | No | Source language (auto-detected) |

---

### 3. Sentiment Tool
```python
class SentimentTool:
    name = "sentiment"
    
    async def execute(text: str) -> Dict[str, Any]
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| text | string | Yes | Text to analyze |

**Output Values:**
- `sentiment`: "positive", "neutral", or "frustrated"
- `confidence`: 0.0 - 1.0
- `explanation`: Brief analysis

---

### 4. Documents Tool (RAG)
```python
class DocumentsTool:
    name = "documents"
    
    async def execute(
        action: str = "query",
        question: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| action | string | Yes | "query" or "info" |
| question | string | For query | Question about support issues |
| top_k | int | No | Number of sources to retrieve (default: 5) |

**RAG Pipeline:**
1. Detect question language
2. Translate to English (if needed)
3. Vector search in FAISS
4. Generate answer with GPT-4
5. Translate answer back to original language

---

### 5. FX Rates Tool
```python
class FXRatesTool:
    name = "fx_rates"
    
    async def execute(
        base: str,
        target: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| base | string | Yes | Base currency (e.g., "USD") |
| target | string | Yes | Target currency (e.g., "EUR") |
| date | string | No | Date for historical rate |

---

### 6. JSON Creator Tool
```python
class JSONCreatorTool:
    name = "json_creator"
    
    async def execute(
        user_name: str,
        contact_time: str,
        original_language: str,
        original_message: str,
        issue_type: str,
        potential_issue: str,
        owning_team: str,
        xlsx_file_name: str,
        priority: str,
        acknowledgement_time: str,
        resolve_time: str,
        cost_usd: str,
        eur_per_usd: str,
        huf_per_usd: str,
        notes_and_dependencies: str,
        sentiment: str,
        sentiment_confidence: float,
        full_conversation: str,
        file_names: list
    ) -> Dict[str, Any]
```

---

### 7. SQLite Save Tool
```python
class SQLiteSaveTool:
    name = "sqlite_save"
    
    async def execute(ticket_data: Dict[str, Any]) -> Dict[str, Any]
```

---

### 8. Photo Upload Tool
```python
class PhotoUploadTool:
    name = "photo_upload"
    
    async def execute(
        action: str = "upload",
        ticket_number: Optional[str] = None,
        file_paths: Optional[list] = None,
        file_names: Optional[list] = None,
        file_data: Optional[list] = None
    ) -> Dict[str, Any]
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| action | string | Yes | "upload" or "list" |
| ticket_number | string | For upload | Ticket number for folder name |
| file_paths | list | For upload* | List of file paths |
| file_names | list | For upload | Original file names |
| file_data | list | For upload* | List of file bytes |

*Either file_paths OR file_data required

---

### 9. Email Send Tool
```python
class EmailSendTool:
    name = "send_ticket_via_email"
    
    async def execute(ticket_data: Dict[str, Any]) -> Dict[str, Any]
```

---

### 10. Radio Tool
```python
class RadioTool:
    name = "radio"
    
    async def execute(
        action: str = "search",
        country_code: Optional[str] = None,
        country: Optional[str] = None,
        name: Optional[str] = None,
        language: Optional[str] = None,
        tag: Optional[str] = None,
        by: str = "votes",
        limit: int = 10
    ) -> Dict[str, Any]
```

---

### 11. Crypto Price Tool
```python
class CryptoPriceTool:
    name = "crypto_price"
    
    async def execute(
        symbol: str,
        fiat: str = "USD"
    ) -> Dict[str, Any]
```

---

### 12. Guardrails Tool
```python
class GuardrailsTool:
    name = "guardrails"
    
    async def execute(
        text: str = None,
        action: str = "mask",
        include_audit: bool = True
    ) -> Dict[str, Any]
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| text | string | Yes | Text to scan for PII |
| action | string | No | "mask" or "detect" (default: "mask") |
| include_audit | bool | No | Include audit log (default: True) |

**PII Types Detected & Masked:**
- Email addresses → `###EMAIL###`
- Phone numbers → `###PHONE###`
- Credit card numbers → `###CREDIT_CARD###`
- Social Security Numbers → `###SSN###`
- National IDs → `###NATIONAL_ID###`
- IP addresses → `###IP###`
- IBAN bank accounts → `###IBAN###`
- Dates of birth → `###DOB###`
- Passport numbers → `###PASSPORT###`
- Physical addresses → `###ADDRESS###`
- Tax IDs → `###TAX_ID###`

---

### 13. Geocode Tool
```python
class GeocodeTool:
    name = "geocode"
    
    async def execute(
        address: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> Dict[str, Any]
```

---

## 📊 JSON Schemas

### Ticket JSON Schema

```json
{
  "ticket_number": "TK001",
  "user_name": "string",
  "contact_time": "2024-01-15 14:30:00",
  "original_language": "hu",
  "original_message": "string",
  "issue_type": "Billing Issues",
  "potential_issue": "Incorrect charge amount",
  "owning_team": "Billing Team",
  "xlsx_file_name": "Billing_Issues.xlsx",
  "priority": "P1",
  "acknowledgement_time": "1 hour",
  "resolve_time": "24 hours",
  "cost_to_customer": {
    "usd": "50",
    "eur_rate": "0.92",
    "huf_rate": "355.50"
  },
  "notes_and_dependencies": "string",
  "sentiment_analysis": {
    "sentiment": "frustrated",
    "confidence": 0.85
  },
  "full_conversation": "User: ...\n\nAssistant: ...",
  "files": ["screenshot.png", "invoice.pdf"],
  "created_at": "2024-01-15 14:35:00"
}
```

### Tool Response Schema

```json
{
  "success": true,
  "message": "Human-readable message with formatting",
  "data": {
    // Tool-specific data
  },
  "system_message": "Brief message for LLM context",
  "error": null  // Only present if success=false
}
```

### Chat Request Schema

```json
{
  "message": "User's message text",
  "session_id": "optional-session-id",
  "user_id": "user-identifier"
}
```

### Chat Response Schema

```json
{
  "final_answer": "Assistant's response",
  "tools_used": [
    {
      "name": "tool_name",
      "arguments": {},
      "success": true,
      "system_message": "Brief result"
    }
  ],
  "memory_snapshot": {
    "preferences": {},
    "workflow_state": {},
    "message_count": 5
  },
  "logs": ["Tools called: 3"]
}
```

---

## 🔄 Data Flow Diagrams

### Support Ticket Creation Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        USER MESSAGE RECEIVED                              │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1: LANGUAGE DETECTION & TRANSLATION                                 │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Detect Language │───▶│ If not English  │───▶│ Translate to EN │       │
│ │ (lingua)        │    │                 │    │ (GPT-4)         │       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 2: SENTIMENT ANALYSIS                                               │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Analyze Text    │───▶│ Classify:       │───▶│ Return:         │       │
│ │ (GPT-4)         │    │ pos/neu/frus    │    │ sentiment + %   │       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 3: WEATHER (for greeting)                                           │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Call Weather API│───▶│ Get Budapest    │───▶│ Current temp +  │       │
│ │ (Open-Meteo)    │    │ forecast        │    │ tomorrow        │       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 4: DOCUMENTS RAG QUERY                                              │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Vector Search   │───▶│ Retrieve Top 5  │───▶│ Generate Answer │       │
│ │ (FAISS)         │    │ Documents       │    │ (GPT-4)         │       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
│                                                                          │
│ Extracts: Issue Type, Priority, Owning Team, SLA, Cost                  │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 5-6: CURRENCY CONVERSION                                            │
│ ┌─────────────────┐    ┌─────────────────┐                              │
│ │ USD → EUR       │    │ USD → HUF       │                              │
│ │ (FrankfurterAPI)│    │ (FrankfurterAPI)│                              │
│ └─────────────────┘    └─────────────────┘                              │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 7: GENERATE FINAL RESPONSE                                          │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Combine all tool results into warm, helpful response                 │ │
│ │ - Weather-based greeting                                             │ │
│ │ - Issue acknowledgment                                               │ │
│ │ - Details from documents (priority, SLA, cost)                       │ │
│ │ - Currency conversions                                               │ │
│ │ - Reassurance                                                        │ │
│ │ - Translate to user's language if needed                             │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 8: GUARDRAILS - PII MASKING                                          │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Scan for PII    │───▶│ Mask with ###   │───▶| Generate audit  │       │
│ │ (Regex patterns)│    │ placeholders     │    │ log for compliance│       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
│                                                                          │
│ Masks: emails, phones, credit cards, SSN, IDs, addresses, etc.          │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 9: CREATE JSON TICKET                                               │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Get next TK###  │───▶│ Build JSON      │───▶│ Save to file    │       │
│ │ number          │    │ structure       │    │ data/tickets/   │       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 10: UPLOAD ATTACHMENTS (if any)                                     │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Create folder   │───▶│ Upload files    │───▶│ Return links    │       │
│ │ Tickets/TK###   │    │ to pCloud       │    │                 │       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 11: SAVE TO DATABASE                                                │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Connect SQLite  │───▶│ INSERT ticket   │───▶│ INSERT files    │       │
│ │ tickets.db      │    │ record          │    │ records         │       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 12: SEND EMAIL NOTIFICATION                                         │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │
│ │ Format HTML     │───▶│ Send via Gmail  │───▶│ Confirm sent    │       │
│ │ email           │    │ SMTP            │    │                 │       │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema

### SQLite Tables

#### tickets
```sql
CREATE TABLE tickets (
    ticket_number TEXT PRIMARY KEY,
    user_name TEXT NOT NULL,
    contact_time TEXT NOT NULL,
    original_language TEXT,
    original_message TEXT,
    issue_type TEXT,
    potential_issue TEXT,
    owning_team TEXT,
    xlsx_file_name TEXT,
    priority TEXT,
    acknowledgement_time TEXT,
    resolve_time TEXT,
    cost_usd TEXT,
    cost_eur_rate TEXT,
    cost_huf_rate TEXT,
    notes_and_dependencies TEXT,
    sentiment TEXT,
    sentiment_confidence REAL,
    full_conversation TEXT,
    created_at TEXT NOT NULL
);
```

#### ticket_files
```sql
CREATE TABLE ticket_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT NOT NULL,
    file_name TEXT NOT NULL,
    FOREIGN KEY (ticket_number) REFERENCES tickets(ticket_number)
);
```

---

## 🌐 API Endpoints

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message and get response |
| POST | `/api/chat/with-files` | Send message with file attachments |
| GET | `/api/session` | Get current session info |
| POST | `/api/reset` | Reset conversation context |

### Tickets Dashboard Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tickets` | Tickets dashboard HTML page |
| GET | `/api/tickets/count` | Get total ticket count |
| GET | `/api/tickets/filter` | Filter tickets with parameters |

### Filter Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| ticket_number | string | Filter by ticket number |
| user_name | string | Filter by user name |
| sentiment | string | positive/neutral/frustrated |
| contact_time | string | Date in YYYY.MM.DD format |
| issue_type | string | Billing/Account/Technical/Feature |
| potential_issue | string | Specific issue description |
| owning_team | string | Responsible team |
| priority | string | P1/P2/P3 |

---

## 🔐 Support Issue Detection

The system uses keyword matching and message length analysis to detect support issues:

### Keyword Categories

1. **Account Issues**: locked, password, reset, mfa, sso, permissions, login
2. **Billing Issues**: charged, invoice, refund, payment, subscription, discount
3. **Technical Issues**: outage, error, bug, crash, timeout, performance
4. **Feature Requests**: integration, enhancement, custom, advanced, mobile

### Detection Logic

```python
def _is_support_feedback_message(self, message: str) -> bool:
    # 1. Check for non-support patterns (greetings)
    if any(pattern in message_lower for pattern in non_support_patterns):
        return False
    
    # 2. Check for support keywords
    if any(keyword in message_lower for keyword in support_keywords):
        return True
    
    # 3. Short messages (1-4 words) treated as support topics
    if word_count <= 4:
        return True
    
    return False
```

---

## 📝 Summary

The SupportAI LangGraph system provides:

1. **Intelligent Routing**: Automatically detects support issues vs general queries
2. **Forced Tool Sequence**: Ensures consistent data collection for support tickets
3. **Multi-language Support**: Detects and responds in user's language
4. **Complete Ticket Lifecycle**: From detection to email notification
5. **Persistent Storage**: SQLite database + pCloud file storage
6. **Real-time Dashboard**: Filter and view all tickets

### Key Files

| File | Purpose |
|------|---------|
| `services/agent.py` | LangGraph workflow and agent logic |
| `services/tools.py` | All tool implementations |
| `services/chat_service.py` | Message processing service |
| `domain/models.py` | Pydantic data models |
| `templates/tickets.html` | Tickets dashboard UI |
| `main.py` | FastAPI application entry point |

---

*Generated: 2026-01-26 | SupportAI v1.0*
