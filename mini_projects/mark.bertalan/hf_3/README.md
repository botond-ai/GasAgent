# RAG System with LangGraph & Jira Integration

A production-ready Python application for answering questions using Retrieval-Augmented Generation (RAG) with **LangGraph orchestration** and **intelligent Jira ticket creation**. Built with clean architecture principles, stateful multi-turn conversations, and smart workflow automation.

## 🚀 What's New

### LangGraph Integration
- **Graph-based workflow** - Complete RAG pipeline orchestrated by LangGraph
- **Multi-turn conversations** - System remembers conversation history across queries
- **Stateful execution** - Explicit state management with typed state schema
- **Conditional routing** - Dynamic graph paths based on query type
- **Observable execution** - Built-in timing metrics for each node

### Intelligent Jira Integration
- **Smart suggestions** - LLM evaluates if issues warrant Jira tickets
- **Conversational flow** - System asks "Would you like me to create a ticket?"
- **Graph-native** - Entire Jira workflow handled by LangGraph (no CLI code)
- **Multi-turn handling** - Detects "yes/no" responses and routes accordingly
- **Auto-extraction** - Determines department, priority, and summary automatically

## Overview

This RAG system combines semantic search with large language models, enhanced by LangGraph for workflow orchestration and intelligent Jira integration for issue tracking.

### Key Features

**Core RAG:**
- ✅ Complete Retrieval-Augmented Generation pipeline
- ✅ OpenAI embeddings (text-embedding-3-small) + LLM (gpt-4o-mini)
- ✅ Smart text chunking with metadata tracking
- ✅ Dual search algorithms (cosine similarity + KNN)
- ✅ ChromaDB persistent vector storage
- ✅ Domain organization (HR, Dev, Support, Management)

**LangGraph Orchestration:**
- ✅ Stateful graph execution with conditional routing
- ✅ Multi-turn conversation support with history
- ✅ Observable execution with per-node timing metrics
- ✅ Clean state management with TypedDict schemas
- ✅ Modular node architecture for extensibility

**Jira Integration:**
- ✅ Smart ticket suggestions (LLM evaluates need)
- ✅ Conversational ticket creation flow
- ✅ Automatic department/priority detection
- ✅ Multi-turn "yes/no" confirmation handling
- ✅ Graph-native implementation (no CLI code)
- ✅ Context-rich tickets with query and answer

**Architecture:**
- ✅ SOLID principles with dependency injection
- ✅ Clean separation of concerns
- ✅ Docker support for deployment
- ✅ Production-ready error handling

## Architecture

### LangGraph Workflow

The system uses LangGraph to orchestrate the entire RAG and Jira workflow:

```
┌─────────────────────────────────────────────────────────────┐
│                     RAG WITH JIRA FLOW                       │
└─────────────────────────────────────────────────────────────┘

START → preprocess → detect_jira_confirmation
                            ↓
              [Has pending suggestion?]
                YES ↓              NO ↓
          [User said yes/no?]    Continue RAG
            ↙        ↓      ↘         ↓
    YES: create  NO: skip  NEW: RAG  embed → retrieve
         ticket              ↓               ↓
           ↓                 ↓         build_context
         format           generate          ↓
                            ↓            generate
                       evaluate_jira       ↓
                            ↓          evaluate_jira
                          format           ↓
                                        format
                                           ↓
                                         END
```

### Graph Nodes

**Core RAG Nodes:**
1. `preprocess_query` - Validates query, generates UUID, initializes state
2. `embed_query` - Generates query embeddings via OpenAI
3. `retrieve_chunks` - Dual search (cosine + KNN) on vector store
4. `build_context` - Extracts text from search results
5. `generate_answer` - LLM generates answer with conversation history
6. `format_response` - Final validation, appends Jira offers

**Jira Nodes:**
7. `detect_jira_confirmation` - Detects "yes/no" responses to pending suggestions
8. `evaluate_jira_need` - LLM evaluates if ticket should be suggested
9. `create_jira_task` - Creates Jira ticket via REST API

### State Schema

```python
class RAGState(TypedDict):
    # Input
    query: str
    k: int
    max_tokens: int

    # Multi-turn state
    conversation_history: List[Dict[str, str]]
    pending_jira_suggestion: Dict[str, str]

    # Query processing
    query_id: str
    query_embedding: List[float]

    # Retrieval
    cosine_results: List[Tuple]
    knn_results: List[Tuple]
    retrieved_context: List[str]

    # Generation
    generated_answer: str

    # Jira
    jira_suggested: bool
    jira_confirmation_detected: bool
    create_jira_task: bool
    jira_department: str
    jira_summary: str
    jira_priority: str

    # Observability
    step_timings: Dict[str, float]
    errors: List[str]
```

### Project Structure

```
mini_projects/mark.bertalan/hf_3/
├── scripts/
│   ├── graph/                    # LangGraph implementation
│   │   ├── rag_graph.py         # Graph builder and routing
│   │   ├── rag_state.py         # State schema
│   │   └── nodes/               # Graph nodes
│   │       ├── preprocess.py    # Query preprocessing
│   │       ├── embedding.py     # Query embedding
│   │       ├── retrieval.py     # Vector search
│   │       ├── context.py       # Context building
│   │       ├── generation.py    # LLM answer generation
│   │       ├── response.py      # Response formatting
│   │       ├── jira_confirm.py  # Yes/no detection
│   │       ├── jira_evaluate.py # Ticket need evaluation
│   │       └── jira_create.py   # Jira API integration
│   │
│   ├── interfaces.py            # Abstract interfaces
│   ├── embeddings.py            # OpenAI embeddings
│   ├── llm.py                   # OpenAI LLM client
│   ├── vector_store.py          # ChromaDB integration
│   ├── application.py           # App orchestrator
│   ├── config.py                # Configuration
│   └── main.py                  # Entry point
│
├── requirements.txt             # Dependencies (includes langgraph)
├── .env.example                # Config template
├── JIRA_INTEGRATION.md         # Jira setup guide
├── DEBUG_GUIDE.md              # Troubleshooting guide
└── README.md                   # This file
```

## Installation

### Prerequisites

- Python 3.11+
- OpenAI API key
- (Optional) Jira account for ticket creation
- (Optional) Docker

### Setup

1. **Clone and navigate to project**
   ```bash
   cd mini_projects/mark.bertalan/hf_3
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your keys
   ```

   Required:
   ```env
   OPENAI_API_KEY=sk-your-api-key-here
   ```

   Optional (for Jira):
   ```env
   JIRA_BASE_URL=https://your-company.atlassian.net
   JIRA_EMAIL=your.email@company.com
   JIRA_API_TOKEN=your_jira_api_token
   JIRA_DEPARTMENT_MAPPING=hr:HR,dev:DEV,support:SUP,management:MGT
   ```

4. **Prepare documents**
   ```bash
   # Place markdown files in:
   embedding_sources/
   ├── hr/
   ├── dev/
   ├── support/
   └── management/
   ```

### Docker Setup

```bash
# Build
docker build -t robotdreams-hf3 .

# Run
docker run -it --env-file .env robotdreams-hf3
```

## Usage

### Running the System

```bash
python -m scripts.main
```

### Example Session

**Turn 1 - Ask question:**
```
User: "The deployment process keeps failing with permission errors"

🤖 GENERATED ANSWER:
Based on the deployment documentation, the process requires admin privileges...
[detailed answer]

---

📋 Jira Ticket Suggestion

I can create a Jira ticket for this issue:
- Department: DEV
- Priority: High
- Summary: Deployment process failing with permission errors...

Would you like me to create this ticket? (Reply 'yes' or 'no')
```

**Turn 2 - Confirm:**
```
User: "yes"

🤖 ✓ Jira task created successfully!

Task Key: DEV-456
Department: DEV
Priority: High
Summary: Deployment process failing with permission errors

View task: https://your-company.atlassian.net/browse/DEV-456
```

**Turn 3 - Follow-up:**
```
User: "What was the error about again?"

🤖 You asked about the deployment process failing with permission errors.
Based on our previous conversation, this occurs when...
[contextual answer referencing previous conversation]
```

### Commands

- **Ask questions** - Type naturally, system retrieves relevant docs and answers
- **Confirm Jira** - Reply "yes" or "no" to ticket suggestions
- **Reset** - Type `reset` to clear conversation history
- **Exit** - Type `exit` to quit

## Jira Integration

### How It Works

1. **User asks about an issue** → System generates answer
2. **LLM evaluates** → Determines if issue warrants a ticket
3. **System offers** → "Would you like me to create a Jira ticket?"
4. **User confirms** → Graph detects "yes/no" and routes accordingly
5. **Ticket created** → Automatically with smart defaults

### Evaluation Criteria

LLM suggests tickets for:
- ✅ Bug reports
- ✅ Feature requests
- ✅ System issues
- ✅ Improvements needing tracking

LLM does NOT suggest for:
- ❌ Informational queries
- ❌ Questions with complete answers
- ❌ General knowledge

### Auto-Detection

System automatically determines:
- **Department** - hr, dev, support, or management (based on query content)
- **Priority** - High, Medium, or Low (based on severity)
- **Summary** - Concise title extracted from query
- **Description** - Includes user query and generated answer

See `JIRA_INTEGRATION.md` for detailed setup.

## Configuration

### Environment Variables

```env
# Required
OPENAI_API_KEY=sk-...

# Embedding settings
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_CHUNK_SIZE=500
OVERLAP=0

# LLM settings
LLM_MODEL=gpt-4o-mini

# Storage
CHROMA_DB_PATH=./chroma_db
DOCUMENTS_ROOT=./embedding_sources
COLLECTION_NAME=prompts

# Domains
DOMAINS=hr,dev,support,management

# Jira (optional)
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_token
JIRA_DEPARTMENT_MAPPING=hr:HR,dev:DEV,support:SUP,management:MGT
```

## API Reference

### EmbeddingApp

```python
app = EmbeddingApp(embedder, vector_store, llm, config)

# Embed documents
app.store_and_embed_documents(documents_root)

# Query with RAG (returns state with conversation history)
query_id, results, answer, state = app.process_query_with_rag(
    text="What is the vacation policy?",
    k=3,
    max_tokens=500
)

# Reset conversation
app.reset_conversation()

# Create Jira ticket manually
task_key, task_url = app.create_jira_ticket(
    department="dev",
    summary="Bug in login",
    description="Users can't log in",
    priority="High"
)
```

### Graph State Fields

Access via `state` dict:
- `state["conversation_history"]` - List of previous messages
- `state["jira_suggested"]` - Whether ticket was suggested
- `state["pending_jira_suggestion"]` - Details of pending suggestion
- `state["generated_answer"]` - LLM's answer
- `state["cosine_results"]` - Search results
- `state["step_timings"]` - Performance metrics
- `state["errors"]` - Any errors that occurred

## Debugging

Enable debug logging (already enabled in main.py):

```bash
python -m scripts.main
```

Look for:
```
INFO - ===== Evaluate Jira Need node executing =====
INFO - ✅ JIRA TICKET SUGGESTED!
INFO - ===== Application: Updated conversation history: 4 messages =====
[DEBUG] jira_suggested: True
[DEBUG] conversation_history length: 4
```

See `DEBUG_GUIDE.md` for troubleshooting.

## Features in Detail

### Conversation History

- **Multi-turn dialog** - System remembers entire conversation
- **Context awareness** - Follow-up questions reference previous answers
- **Persistent** - History maintained across queries
- **Resettable** - Use `reset` command to clear

### Jira Workflow

- **Graph-native** - Entire workflow in LangGraph (no CLI code)
- **Smart evaluation** - LLM decides if ticket warranted
- **Conversational** - Natural "yes/no" confirmation
- **Stateful** - Pending suggestions tracked across turns
- **Rich context** - Tickets include query and answer

### Observability

- **Per-node timing** - Each node reports execution time
- **Error tracking** - Errors collected in state
- **Debug logging** - Comprehensive logging throughout
- **State inspection** - Full state visible for debugging

## Performance

### RAG Query Latency

Typical breakdown:
- Embedding: ~100-200ms (OpenAI API)
- Retrieval: ~10-50ms (ChromaDB)
- Generation: ~1-3s (OpenAI LLM)
- Jira evaluation: ~1-2s (if enabled)
- **Total: ~2-5s per query**

### Optimization Tips

- Adjust `k` (retrieval count) for speed/quality tradeoff
- Use smaller `max_tokens` for faster responses
- Cache embeddings for repeated queries
- Batch document processing for ingestion

## Dependencies

Core:
- **langgraph** (≥0.0.40) - Graph orchestration
- **langchain-core** (≥0.1.0) - State management
- **requests** (≥2.31.0) - HTTP client
- **chromadb** (≥0.4.22) - Vector database
- **python-dotenv** (≥1.0.0) - Config management

## Troubleshooting

### Common Issues

**"Jira integration not configured"**
- Add `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` to `.env`

**No Jira suggestions appearing**
- Check logs for "Evaluate Jira Need node executing"
- Try clearer bug reports: "The login button is completely broken"
- Verify LLM is configured

**Conversation history not working**
- Check logs for "Updated conversation history: X messages"
- Ensure messages count increases each turn
- Don't use `reset` command unintentionally

**Missing cosine_results error**
- Fixed in latest version
- Update to latest code

See `DEBUG_GUIDE.md` for detailed troubleshooting.

## Development

### Extending the Graph

Add new nodes:
```python
# Create node function
def my_custom_node(state: Dict[str, Any]) -> Dict[str, Any]:
    # Process state
    state["custom_field"] = "value"
    return state

# Add to graph in rag_graph.py
workflow.add_node("custom", my_custom_node)
workflow.add_edge("preprocess", "custom")
```

### Adding New LLM Providers

Implement `LLM` interface in `interfaces.py`:
```python
class CustomLLM(LLM):
    def generate(self, prompt: str, context: List[str],
                 max_tokens: int = 500,
                 conversation_history: Optional[List[Dict]] = None) -> str:
        # Your implementation
        pass
```

### Custom Jira Workflows

Modify nodes in `scripts/graph/nodes/`:
- `jira_evaluate.py` - Change evaluation criteria
- `jira_create.py` - Customize ticket format
- `jira_confirm.py` - Add custom confirmation logic

## License

This project demonstrates RAG implementation with LangGraph and Jira integration for educational purposes.

## Support

- **Documentation**: See `JIRA_INTEGRATION.md` and `DEBUG_GUIDE.md`
- **Troubleshooting**: Enable debug logging and check logs
- **Issues**: Check GitHub issues or create new one

---

Built with LangGraph, OpenAI, ChromaDB, and Jira REST API.
