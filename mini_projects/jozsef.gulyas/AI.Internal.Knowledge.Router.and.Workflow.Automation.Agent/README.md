# Knowledge Router

An enterprise multi-domain knowledge retrieval and workflow automation agent built with LangGraph.

## Overview

Knowledge Router is an AI-powered assistant that:
- **Routes queries** to the appropriate domain (HR, IT, Finance, Legal, Marketing, General)
- **Retrieves relevant information** from domain-specific vector stores using RAG
- **Executes workflows** through integrated tools (Jira, Slack, currency conversion, holiday lookup)
- **Provides structured responses** with source citations

## Usage

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key

### Installation

```bash
# Clone and navigate to the project
cd AI.Internal.Knowledge.Router.and.Workflow.Automation.Agent

# Install dependencies
uv sync
```

### Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
EMBEDDING_MODEL=text-embedding-3-small
COMPLETION_MODEL=gpt-4o-mini
```

### Adding Knowledge Base Documents

Place markdown files in the `data/` directory, organized by domain:

```
data/
├── hr/
│   └── vacations_policy.md
├── it/
│   ├── vpn_issues.md
│   └── printers.md
├── finance/
├── legal/
├── marketing/
└── general/
```

The loader automatically detects domains from folder names and indexes all `.md` files.

### Running the Application

```bash
uv run python -m src.main
```

The assistant will:
1. Load and index all documents from the `data/` folder
2. Start an interactive CLI session
3. Accept natural language queries and respond with relevant information

### Example Queries

```
You: What is the vacation policy?
[Domain: hr]
Assistant: According to the vacation policy, employees are entitled to...
Sources:
  - Vacation Policy (relevance: 0.94)

You: How do I fix VPN connection issues?
[Domain: it]
Assistant: Here are common VPN troubleshooting steps...
Sources:
  - VPN Troubleshooting Guide (relevance: 0.91)

You: Convert 100 USD to EUR
[Domain: general]
Assistant: 100 USD is approximately 92.50 EUR based on current exchange rates.
```

Type `quit` or `exit` to end the session.

## Technical Details

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                        │
│                         (CLI Interface)                          │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                         Workflow Layer                           │
│                    (LangGraph State Machine)                     │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐   │
│  │  Route  │ → │ Retrieve │ → │ Generate │ ⇄ │ Tool Execute│   │
│  └─────────┘   └──────────┘   └──────────┘   └─────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                          Core Layer                              │
│   ┌─────────────────┐  ┌────────────┐  ┌────────────────────┐   │
│   │ KnowledgeLoader │  │ RAG Engine │  │ Document Processor │   │
│   └─────────────────┘  └────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                        │
│   ┌────────────────┐  ┌─────────────┐  ┌───────────────────┐    │
│   │ OpenAI Gateway │  │ VectorStore │  │   Tool Executor   │    │
│   │ (Embeddings +  │  │ (ChromaDB)  │  │ (Jira, Slack,     │    │
│   │  Completions)  │  │             │  │  Holidays, FX)    │    │
│   └────────────────┘  └─────────────┘  └───────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### LangGraph Workflow

The application uses a LangGraph state machine with the following flow:

```
Route → Retrieve → Generate ⇄ Execute Tools → END
```

1. **Route Node**: Classifies the user query into one of 6 domains using LLM
2. **Retrieve Node**: Searches the domain-specific vector store using RAG
3. **Generate Node**: Produces a response using retrieved context and available tools
4. **Tool Node**: Executes tool calls (Jira, Slack, etc.) when requested by the LLM

The workflow supports a tool-calling loop where the LLM can request multiple tool executions before producing a final response.

### Domain Routing

Queries are classified into domains using LLM-based intent detection:

| Domain | Topics |
|--------|--------|
| HR | Vacation, benefits, hiring, payroll, onboarding |
| IT | VPN, software, hardware, network, access |
| Finance | Invoices, expenses, budgets, payments |
| Legal | Contracts, compliance, policies |
| Marketing | Brand, campaigns, content |
| General | Everything else |

### Vector Store

- **Engine**: ChromaDB (in-memory by default)
- **Collections**: One per domain (`hr_kb`, `it_kb`, etc.)
- **Similarity**: Cosine distance
- **Embeddings**: OpenAI `text-embedding-3-small`

### Available Tools

| Tool | Function | Description |
|------|----------|-------------|
| `convert_currency` | Currency conversion | Converts between currencies using live exchange rates |
| `is_us_holiday` | Holiday check | Checks if a specific date is a US holiday |
| `list_us_holidays` | Holiday list | Lists all US holidays for a given year |
| `create_jira_ticket` | Jira integration | Creates a Jira ticket with specified details |
| `send_slack_message` | Slack integration | Sends a message to a Slack channel |

## Implementation Decisions

### Why LangGraph?

LangGraph was chosen over plain LangChain for:
- **Explicit state management**: Clear data flow through `WorkflowState` dataclass
- **Conditional routing**: Easy branching based on domain classification
- **Tool loop support**: Built-in pattern for LLM ⇄ Tool execution cycles
- **Debuggability**: Visual graph representation and state inspection

### Why ChromaDB?

- **Zero configuration**: In-memory mode requires no external services
- **Namespace support**: Natural fit for multi-domain collections
- **Python-native**: Simple integration without network overhead
- **Switchable**: Can be replaced with Pinecone/Weaviate for production

### Layered Architecture

The codebase follows clean architecture principles:

- **Presentation**: CLI interface, display abstractions
- **Workflows**: LangGraph nodes and state definitions
- **Core**: Business logic (RAG engine, document processing, chunking)
- **Infrastructure**: External service integrations (OpenAI, ChromaDB, tools)

This separation enables:
- Unit testing with mocked dependencies
- Swapping implementations (e.g., different LLM providers)
- Clear responsibility boundaries

### Document Processing

- **Chunking**: Markdown-aware chunking that respects header boundaries
- **Deduplication**: Hash-based detection to avoid re-indexing unchanged documents
- **Metadata**: Each chunk retains source file, title, and domain information

### RAG Strategy

- **Relevance threshold**: 0.7 (configurable) - filters low-quality matches
- **Top-K retrieval**: 5 documents per query
- **Citation tracking**: All retrieved documents are returned as citations

## Project Structure

```
src/
├── main.py                    # Application entry point
├── core/
│   ├── document_processor.py  # Document ingestion and chunking
│   ├── knowledge_base_loader.py # Folder traversal and domain detection
│   ├── markdown_chunker.py    # Structure-aware text chunking
│   └── rag_engine.py          # Retrieval and context building
├── infrastructure/
│   ├── openai_gateway.py      # OpenAI API wrapper
│   ├── vector_store.py        # ChromaDB integration
│   └── tools/
│       ├── tool_executor.py   # Tool dispatch and execution
│       ├── exchange_rates.py  # Currency conversion tool
│       ├── holidays.py        # US holiday tools
│       ├── jira.py            # Jira ticket creation
│       └── slack.py           # Slack messaging
├── presentation/
│   ├── cli_interface.py       # Command-line interface
│   └── display_writer_interface.py # Output abstraction
└── workflows/
    ├── knowledge_workflow.py  # LangGraph workflow definition
    ├── state.py               # Workflow state dataclass
    └── nodes/
        ├── router_node.py     # Domain classification
        ├── retrieve_node.py   # RAG retrieval
        ├── generate_node.py   # LLM response generation
        └── tool_node.py       # Tool execution
```

## Testing

Run the test suite:

```bash
uv run pytest
```

Tests cover:
- Vector store operations
- Document processing
- RAG retrieval
- Tool execution
- Individual workflow components

## Dependencies

Core dependencies (see `pyproject.toml`):

- `langgraph` - Workflow orchestration
- `chromadb` - Vector storage
- `httpx` - Async HTTP client for API calls

Dev dependencies:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
