# Meeting Minutes Embedding CLI (Homework.04)

AI Meeting Assistant app 2.0 that creates OpenAI embeddings for company meeting minutes (or any text files), stores them in a local ChromaDB vector store, performs nearest-neighbor retrieval, and optionally generates LLM-augmented responses using a RAG (Retrieval-Augmented Generation) pattern. The project supports two modes of operation:

- Batch mode (default when a `data/` directory exists): reads `.md`/`.txt` files from `./data`, embeds and indexes them, and prints nearest neighbors (and optionally generated responses) for each file.
- Interactive mode: when no `data/` folder is present, the app starts an interactive prompt where you can enter free-text queries which are embedded, stored, searched and optionally augmented with LLM responses.

**NEW in Homework.04:** 
- Multi-step agent orchestration using **LangGraph** with intelligent tool routing, RAG-informed planning, and automated meeting summarization
- **AI Metrics Monitoring** — tracks inference count, tokens (in/out), cost in USD, and latency (p95/p50/mean) following SOLID principles
- Integration with Google Calendar API, IP Geolocation service, and Vector Database for comprehensive multi-tool workflows

Quick overview
- Language: Python 3.11+
- Vector DB: ChromaDB (duckdb+parquet persistence)
- Embeddings: OpenAI Embeddings API (model configurable via `.env`)
- CLI: interactive terminal loop and batch `data/` processing
- **NEW:** LangGraph multi-step agent orchestration with tool routing
- **NEW:** RAG-informed execution planning and meeting summarization
- **NEW:** AI Metrics Monitoring with comprehensive tracking
- **NEW:** Integration with Google Calendar and IP Geolocation services

Files
- `app/config.py` — loads `.env` and exposes typed configuration
- `app/embeddings.py` — `EmbeddingService` abstraction and `OpenAIEmbeddingService` implementation with metrics integration
- `app/vector_store.py` — `VectorStore` abstraction and `ChromaVectorStore` implementation (semantic + hybrid search)
- `app/rag_agent.py` — `RAGAgent` LLM response generation using retrieved documents with metrics integration
- `app/langgraph_workflow.py` — **NEW** `MeetingAssistantWorkflow` with 7-node LangGraph orchestration
- `app/metrics.py` — **NEW** AI Metrics Monitoring module with SOLID principles (pricing calculator, collectors, middleware)
- `app/cli.py` — `EmbeddingApp` orchestration, interactive CLI and `process_directory` for batch processing, integrated with RAG, LangGraph, and Metrics
- `app/main.py` — application entrypoint wiring dependencies and auto-detecting `data/` folder
- `requirements.txt` — Python dependencies
- `.env.example` — example environment variables
- `docs/METRICS.md` — **NEW** comprehensive metrics monitoring documentation


Getting started
---------------

1. Copy `.env.example` to `.env` and fill in your OpenAI API key:

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

2. Install dependencies (local development):

```bash
pip install -r requirements.txt
```

3. Prepare data (batch mode):

Place your meeting minute files under `data/` in the project root. Supported file extensions: `.md`, `.txt`.

Example:

```
mini_projects/szlavi.domonkos/Homework.02/data/meeting01.md
mini_projects/szlavi.domonkos/Homework.02/data/meeting02.txt
```

4a. Run in batch mode (auto-detects `./data`):

```bash
python -m app.main
```

4b. Run interactive mode (no `data/` present):

```bash
python -m app.main
```

Or build and run in Docker (mount data dir):

```bash
docker build -t embedding-demo .
docker run -it --env-file .env -v "$PWD/data":/app/data embedding-demo
```

Usage
-----

Batch mode (default when `./data` exists): the app will process each `.md`/`.txt` file in `data/`, embed its contents, store the document and run the configured retrieval (semantic/hybrid/BM25) for that document. Results are printed per file.

Interactive mode: type a free-text prompt and press Enter. The app will:
1. Create an embedding for your prompt using the configured OpenAI model.
2. Store the prompt + embedding in the local ChromaDB collection.
3. Run a nearest-neighbor search and display the top results with scores.

Example output:

```
Stored prompt id: 4f2a1b...
Retrieved nearest neighbors:
1. (score=0.987654) "the current text itself..."
2. (score=0.712345) "previous similar text..."
3. (score=0.456789) "another somewhat related text..."
```

Hybrid & search modes
--------------

This project includes a hybrid search that combines semantic similarity (OpenAI embeddings + ChromaDB) with lexical BM25 ranking using `rank-bm25`.

- Default mode: `hybrid` (weighted combination).
- You can switch modes at runtime using CLI commands (interactive mode):

	- `/mode hybrid` — Combine semantic + BM25 (default)
	- `/mode semantic` — Semantic search only (Chroma similarity)
	- `/mode bm25` — BM25-only lexical search
	- `/k N` — set number of returned neighbors
	- `/alpha X` — set hybrid semantic weight (0.0..1.0)
	- `/rag on|off` — enable/disable RAG response generation

Example commands while running the interactive CLI:

```text
/mode hybrid
/k 5
/alpha 0.7
/rag on
What did we decide in the last planning meeting?
```

For batch mode, hybrid parameters are applied to each file using the defaults (mode=`hybrid`, k=3, alpha=0.5). If you need per-file control, consider running interactive mode or extending the batch API.

RAG (Retrieval-Augmented Generation)
-------------------------------------

The app includes an optional RAG agent that generates contextual responses using an LLM. When enabled, the RAG agent:

1. Retrieves the top-k documents using your configured search mode (semantic/hybrid/BM25).
2. Passes the query and retrieved documents to an OpenAI LLM (configurable model, default: `gpt-4o-mini`).
3. The LLM generates a response based on the retrieved context.

**Configuration:**

Set these in `.env` to customize RAG behavior:

```bash
OPENAI_LLM_MODEL=gpt-4o-mini          # Model for response generation
OPENAI_LLM_TEMPERATURE=0.7            # Creativity (0.0..2.0)
OPENAI_LLM_MAX_TOKENS=1024            # Max response length
```

**Response Caching:**

The RAG agent automatically caches LLM responses to reduce API costs. Cached responses are stored in `./response_cache/` and keyed by a hash of the query + retrieved document texts. When an identical query with the same documents is processed again, the cached response is returned instead of calling the LLM API.

- Cache is enabled by default.
- Cached responses are marked with `(cached)` prefix.
- To clear the cache, delete the `./response_cache/` directory.

Example cost savings: with caching, 100 similar queries using the same 5 documents results in ~1 LLM call instead of 100, reducing costs by ~99%.

**Interactive usage:**

```
/rag on                    # Enable RAG response generation
/rag off                   # Disable RAG (show only retrieval results)
What did we discuss?       # Generates LLM response based on retrieved docs
```

The RAG response includes a formatted display of retrieved context followed by the generated answer.

**Example RAG output:**

```
Stored query id: abc123...

--- Retrieved Context ---
[1] (relevance: 0.9234)
    Meeting on Q1 planning. Topics: budget allocation, hiring...

[2] (relevance: 0.8123)
    Previous minutes from Dec meeting. Action items...

--- Generated Response ---
Based on the retrieved company documents, we discussed Q1 planning 
including budget allocation for engineering and hiring plans for 
the new team...
```

Google Calendar Integration
----------------------------

The app includes optional Google Calendar integration for retrieving and viewing calendar events. When configured, calendar commands are available in interactive mode.

**Setup:**

1. Create a Google Cloud project and enable the Google Calendar API:
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Google Calendar API
   - Create an OAuth 2.0 Desktop Application credential
   - Download the credentials as `client_credentials.json`

2. Copy the credentials file to your project directory:
   ```bash
   cp /path/to/client_credentials.json ./
   ```

3. Set the path in `.env`:
   ```bash
   GOOGLE_CALENDAR_CREDENTIALS_FILE=./client_credentials.json
   GOOGLE_CALENDAR_TOKEN_FILE=./token.pickle
   ```

**Interactive usage:**

Once configured, calendar commands are available:

```
/calendar events              # Show next 5 upcoming events
/calendar today              # Show events for today
/calendar range 2026-01-20 2026-02-01   # Show events in date range
```

**Example output:**

```
Upcoming Events (3):

[1] Team Meeting
    Start: 2026-01-20T10:00:00Z
    End: 2026-01-20T11:00:00Z
    Location: Conference Room A
    Description: Discuss Q1 roadmap...

[2] Project Review
    Start: 2026-01-21T14:00:00Z
    End: 2026-01-21T15:30:00Z
    Location: Zoom
    Description: Monthly project update...
```

The calendar service uses OAuth2 authentication and caches tokens locally for future use.

IP Geolocation API Integration
-------------------------------

The app includes optional IP Geolocation functionality for retrieving geographic information based on IP addresses. This feature allows you to look up details such as country, city, region, latitude, longitude, timezone, ISP, and other location-based data.

**Setup:**

1. Obtain an IP Geolocation API key from a geolocation service provider (e.g., ip-api.com, MaxMind, or similar).

2. Set the API key in `.env`:
   ```bash
   IP_GEOLOCATION_API_KEY=your_api_key_here
   ```

**Interactive usage:**

Once configured, geolocation commands are available:

```
/geoip 8.8.8.8              # Look up geolocation for a specific IP address
/geoip                      # Look up geolocation for your current IP address
```

**Example output:**

```
IP Geolocation Information:

IP Address: 8.8.8.8
Country: United States
Country Code: US
Region: California
City: Mountain View
Latitude: 37.3861
Longitude: -122.0839
Timezone: America/Los_Angeles
ISP: Google LLC
Organization: Google
```

**Features:**

- **IP lookup:** Query any public IP address for its geographic location
- **Current IP detection:** Automatically detect and look up your machine's public IP
- **Comprehensive data:** Returns country, region, city, coordinates, timezone, and ISP information
- **Error handling:** Gracefully handles invalid IPs or API errors
- **Response caching:** Geolocation results are cached to minimize API calls

**Configuration:**

Set these in `.env` to customize geolocation behavior:

```bash
IP_GEOLOCATION_API_KEY=your_api_key      # API key for geolocation service
IP_GEOLOCATION_CACHE_ENABLED=true        # Enable/disable response caching
IP_GEOLOCATION_TIMEOUT=10                # Request timeout in seconds
```

**Limitations and considerations:**

- Some IP geolocation APIs have rate limits; check your provider's documentation
- Private/internal IP addresses (10.x.x.x, 192.168.x.x, 172.16.x.x) may not resolve
- Accuracy varies depending on the geolocation data provider
- Consider caching results locally to reduce API usage and improve response times

AI Metrics Monitoring (Homework.04 NEW)
---------------------------------------

**NEW FEATURE:** Comprehensive AI metrics monitoring system that tracks API usage, costs, and performance metrics following SOLID design principles.

### Overview

The Metrics Monitoring module automatically tracks:
- **Inference Count**: Total number of API calls
- **Tokens In/Out**: Total input and output tokens
- **Cost in USD**: Total cost based on real OpenAI pricing
- **Latency p95/p50/mean**: Request latency percentiles

### Architecture

The metrics system follows SOLID principles:

**Components:**
- `MetricCollector` (ABC) — Interface for metric collection
- `InMemoryMetricsCollector` — In-memory storage with JSON export/import
- `OpenAIPricingCalculator` — Accurate cost calculation for all OpenAI models
- `MetricsMiddleware` — Wrapper for automatic metric recording
- `APICallMetric` — Dataclass for individual metric data

**Supported Models:**

*Embeddings:*
- `text-embedding-3-small`: $0.02 per 1M tokens
- `text-embedding-3-large`: $0.13 per 1M tokens

*LLMs:*
- `gpt-4o-mini`: $0.15 in / $0.60 out per 1M tokens
- `gpt-4o`: $2.5 in / $10.0 out per 1M tokens
- `gpt-4-turbo`: $10.0 in / $30.0 out per 1M tokens
- `gpt-3.5-turbo`: $0.50 in / $1.50 out per 1M tokens

*Vector Database:*
- `vector_db_load`: Free (no per-operation cost)
  - Tracks: Documents retrieved, latency, search operation type (semantic/BM25/hybrid)

### Interactive Usage

Use these commands in interactive mode:

```bash
# Display metrics summary
/metrics

# Export metrics to JSON file (./metrics_export.json)
/metrics export
```

### Example Output

```
--- AI Metrics Summary ---
Total Inferences: 52
Total Tokens In: 15,234
Total Tokens Out: 8,567
Total Cost: $0.024700

Latency Statistics (milliseconds):
  p95: 125.30ms
  p50 (median): 68.50ms
  Mean: 72.10ms

Breakdown by Operation:
  embedding:
    Calls: 32
    Tokens In: 12,500
    Tokens Out: 0
    Cost: $0.000250
    Latency p95: 52.10ms

  llm_completion:
    Calls: 10
    Tokens In: 2,734
    Tokens Out: 8,567
    Cost: $0.024450
    Latency p95: 98.50ms

  vector_db_load:
    Calls: 10
    Documents Retrieved: 127
    Cost: $0.000000
    Latency p95: 35.20ms

Breakdown by Model:
  text-embedding-3-small:
    Calls: 32
    Cost: $0.000250
    Latency p95: 52.10ms

  gpt-4o-mini:
    Calls: 10
    Cost: $0.024450
    Latency p95: 98.50ms

  vector_db:
    Calls: 10
    Latency p95: 35.20ms
```

### JSON Export Format

Exported metrics include:
- Individual call records with all metrics
- Aggregated summary statistics
- Breakdown by operation type and model
- Complete audit trail for cost analysis

**Example:**
```json
{
  "timestamp": "2026-01-25T13:45:00",
  "total_calls": 42,
  "calls": [
    {
      "timestamp": "2026-01-25T13:40:15",
      "model": "text-embedding-3-small",
      "tokens_in": 250,
      "tokens_out": 0,
      "latency_ms": 45.3,
      "cost_usd": 0.0000063,
      "operation_type": "embedding",
      "success": true
    },
    ...
  ],
  "summary": {
    "total_inferences": 42,
    "total_tokens_in": 15234,
    "total_tokens_out": 8567,
    "total_cost_usd": 0.024700,
    "latency_p95_ms": 125.30,
    "latency_p50_ms": 68.50,
    "latency_mean_ms": 72.10,
    "by_operation": {...},
    "by_model": {...}
  }
}
```

### Testing

Comprehensive test suite with 29 tests covering:
- Metric collection and aggregation
- Cost calculation for all supported models
- Latency percentile calculations (p95, p50, mean)
- Error rate tracking across all operation types
- Agent execution latency measurement
- JSON export/import functionality
- Vector DB load metrics tracking
- Integration with embedding and LLM services

```bash
# Run all metrics tests
pytest tests/test_metrics.py -v

# Run specific test class
pytest tests/test_metrics.py::TestErrorRateMetrics -v

# Run agent execution tests
pytest tests/test_metrics.py::TestMetricsMiddleware::test_record_agent_execution -v

# With coverage
pytest tests/test_metrics.py --cov=app.metrics
```

### Error Rate Metric

**NEW FEATURE:** Automatic tracking of operation success/failure rates.

The error rate metric monitors the percentage of failed API calls and operations:
- **Formula**: `(failed_calls / total_calls) × 100`
- **Range**: 0-100%
- **Tracked For**: All operation types (embedding, LLM, vector DB, agent execution)

**Example:**
```python
# Record successful operation
middleware.record_embedding_call(
    model="text-embedding-3-small",
    tokens_in=100,
    latency_ms=50.0,
    success=True  # Mark as successful
)

# Record failed operation
middleware.record_embedding_call(
    model="text-embedding-3-small",
    tokens_in=100,
    latency_ms=102.5,
    success=False,  # Mark as failed
    error_message="API rate limit exceeded"
)

# View error metrics
summary = collector.get_summary()
print(f"Error Rate: {summary.error_rate:.2f}%")  # e.g., 50.0%
print(f"Total Errors: {summary.total_errors}")    # e.g., 1
```

**Use Cases:**
- System reliability monitoring and alerting
- Detecting API degradation or service issues
- Tracking failure patterns by operation type
- SLA compliance verification

### Agent Execution Latency Metric

**NEW FEATURE:** Automatic tracking of complete agent workflow execution time.

Agent execution latency measures the time from agent start to completion:
- **Statistics**: p95, p50 (median), mean
- **Unit**: Milliseconds
- **Granularity**: Per workflow execution
- **Includes**: Both successful and failed executions

**Example:**
```python
import time

# Measure agent execution
start_time = time.time()
result = agent.execute(request)
latency_ms = (time.time() - start_time) * 1000

# Record the execution
middleware.record_agent_execution(
    latency_ms=latency_ms,
    success=True,  # or False if execution failed
    error_message=None  # Include if failed
)

# View agent latency metrics
summary = collector.get_summary()
print(f"Agent p95 Latency: {summary.agent_execution_latency_p95_ms:.0f}ms")
print(f"Agent Mean Latency: {summary.agent_execution_latency_mean_ms:.0f}ms")

# Detailed breakdown
if "agent_execution" in summary.by_operation:
    agent_stats = summary.by_operation["agent_execution"]
    print(f"Total Executions: {agent_stats['count']}")
    print(f"p95 Latency: {agent_stats['latency_p95_ms']:.0f}ms")
```

**Use Cases:**
- Workflow performance monitoring
- Identifying performance bottlenecks
- SLA tracking and compliance
- Workflow optimization insights

### Complete Metrics Example Output

```
--- AI Metrics Summary ---
Total Inferences: 52
Total Tokens In: 15,234
Total Tokens Out: 8,567
Total Cost: $0.024700

Error Rate: 3.85% (2 errors)

Latency Statistics (milliseconds):
  p95: 125.30ms
  p50 (median): 68.50ms
  Mean: 72.10ms

Agent Execution Latency (milliseconds):
  p95: 1500.00ms
  Mean: 1200.00ms

Breakdown by Operation:
  embedding:
    Calls: 32
    Tokens In: 12,500
    Tokens Out: 0
    Cost: $0.000250
    Latency p95: 52.10ms

  llm_completion:
    Calls: 10
    Tokens In: 2,734
    Tokens Out: 8,567
    Cost: $0.024450
    Latency p95: 98.50ms

  vector_db_load:
    Calls: 10
    Documents Retrieved: 127
    Cost: $0.000000
    Latency p95: 35.20ms

  agent_execution:
    Calls: 5
    Latency p95: 1500.00ms

Breakdown by Model:
  text-embedding-3-small:
    Calls: 32
    Cost: $0.000250
    Latency p95: 52.10ms

  gpt-4o-mini:
    Calls: 10
    Cost: $0.024450
    Latency p95: 98.50ms

  vector_db:
    Calls: 10
    Latency p95: 35.20ms

  agent:
    Calls: 5
    Latency p95: 1500.00ms
```

### JSON Export Format

Exported metrics include:
- Individual call records with success/failure status and error messages
- Error rate and count across all operations
- Agent execution latency statistics
- Aggregated summary statistics
- Breakdown by operation type and model
- Complete audit trail for cost analysis and troubleshooting

**Example:**
```json
{
  "timestamp": "2026-01-25T13:45:00",
  "total_calls": 52,
  "calls": [
    {
      "timestamp": "2026-01-25T13:40:15",
      "model": "text-embedding-3-small",
      "tokens_in": 250,
      "tokens_out": 0,
      "latency_ms": 45.3,
      "cost_usd": 0.0000063,
      "operation_type": "embedding",
      "success": true
    },
    {
      "timestamp": "2026-01-25T13:40:30",
      "model": "text-embedding-3-small",
      "tokens_in": 150,
      "tokens_out": 0,
      "latency_ms": 102.5,
      "cost_usd": 0.0000038,
      "operation_type": "embedding",
      "success": false,
      "error_message": "API rate limit exceeded"
    },
    {
      "timestamp": "2026-01-25T13:42:00",
      "model": "agent",
      "tokens_in": 0,
      "tokens_out": 0,
      "latency_ms": 1500.0,
      "cost_usd": 0.0,
      "operation_type": "agent_execution",
      "success": true
    }
  ],
  "summary": {
    "total_inferences": 52,
    "total_tokens_in": 15234,
    "total_tokens_out": 8567,
    "total_cost_usd": 0.024700,
    "latency_p95_ms": 125.30,
    "latency_p50_ms": 68.50,
    "latency_mean_ms": 72.10,
    "error_rate": 3.85,
    "total_errors": 2,
    "agent_execution_latency_p95_ms": 1500.0,
    "agent_execution_latency_mean_ms": 1200.0,
    "by_operation": {...},
    "by_model": {...}
  }
}
```

### Documentation

For detailed metrics documentation, see:

- **[docs/METRICS.md](docs/METRICS.md)** — Complete metrics architecture and reference
- **[ERROR_RATE_AND_AGENT_LATENCY_METRICS.md](ERROR_RATE_AND_AGENT_LATENCY_METRICS.md)** — Error rate and agent latency detailed guide
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — Quick start and common patterns
- **[ENHANCEMENT_SUMMARY.md](ENHANCEMENT_SUMMARY.md)** — Implementation summary

**Documentation covers:**
- Architecture and SOLID principles
- API reference with code examples
- Integration patterns and usage
- Performance benchmarks
- Monitoring and alerting strategies
- Troubleshooting and error handling

LangGraph Multi-Step Agent Workflow
------------------------------------

**NEW FEATURE:** Homework.04 includes a sophisticated LangGraph-based workflow orchestration system for complex multi-step agent operations.

### Overview

The LangGraph workflow provides intelligent orchestration of multi-step tasks involving planning, tool routing, execution, observation, and summarization. It enables autonomous decision-making with RAG-informed context awareness.

### Seven Workflow Nodes

1. **plan_node** — Generates execution plan from user input
   - Analyzes user request
   - Retrieves relevant context from RAG database
   - Uses LLM to create structured execution plan

2. **executor_loop** — Orchestrates step-by-step execution
   - Manages step iteration
   - Routes to tool_router or summary_node

3. **tool_router** — Intelligently routes steps to appropriate tools
   - Calendar operations → Google Calendar tool
   - IP lookup → IP Geolocation tool
   - Document search → RAG search tool

4. **action_node** — Executes selected tool
   - Calls appropriate service
   - Handles errors gracefully

5. **observation_node** — Validates and updates state
   - Records action results
   - Updates workflow state
   - Moves to next step

6. **summary_node** — Generates comprehensive meeting summary
   - Combines execution results
   - Uses LLM for natural language summary

7. **final_answer_node** — Formats complete final report
   - Lists all executed steps with status
   - Includes meeting summary and errors

### Interactive Usage

Use the `/workflow` command in interactive mode:

```bash
# Example: Multi-tool research request
/workflow show my calendar and find related project documents

# Example: Geolocation and infrastructure query
/workflow Where are our servers? Check IP 8.8.8.8 and find infrastructure docs

# Example: Meeting preparation
/workflow Prepare for tomorrow's meetings: show calendar and find project documents
```

### Workflow Output

```
Execution Plan (2 steps):
  ✓ Step 1: Retrieve calendar events (google_calendar) - completed
  ✓ Step 2: Search project documentation (rag_search) - completed

Meeting Summary:
Tomorrow's schedule includes 2 meetings. Related project documents found:
- Project Charter (relevance: 0.96)
- Technical Requirements (relevance: 0.93)

Final Answer:
[Complete formatted report with execution steps and results]
```

### Documentation

Comprehensive documentation is available for the LangGraph workflow:

- **[LANGGRAPH_WORKFLOW.md](docs/LANGGRAPH_WORKFLOW.md)** — Architecture guide, node descriptions, state management patterns, tool integration details
- **[LANGGRAPH_QUICKSTART.md](docs/LANGGRAPH_QUICKSTART.md)** — Installation, CLI usage, programmatic usage, 3 detailed example workflows, troubleshooting
- **[LANGGRAPH_IMPLEMENTATION.md](docs/LANGGRAPH_IMPLEMENTATION.md)** — Implementation details, component descriptions, testing coverage, performance characteristics
- **[LANGGRAPH_CHECKLIST.md](LANGGRAPH_CHECKLIST.md)** — Complete verification checklist, feature summary, node execution flow diagram

### Configuration

Enable LangGraph workflow automatically when running with RAG agent:

```bash
OPENAI_API_KEY=your-key          # Required for LLM planning
OPENAI_LLM_MODEL=gpt-4o-mini     # Model for planning/summarization
OPENAI_LLM_TEMPERATURE=0.7       # Creativity level
OPENAI_LLM_MAX_TOKENS=1024       # Response length limit

# Optional tools
GOOGLE_CALENDAR_CREDENTIALS_FILE=./client_credentials.json
IP_GEOLOCATION_API_KEY=your-key
```

### Key Features

- **Autonomous Planning**: LLM generates execution plans from natural language requests
- **RAG-Informed**: Retrieves context from vector database for intelligent decision-making
- **Multi-Tool Integration**: Routes tasks to Calendar, Geolocation, and RAG Search tools
- **Error Resilience**: Continues execution despite individual tool failures
- **Complete Audit Trail**: Logs all steps, results, and observations
- **Natural Language Output**: Generates readable meeting summaries

### Examples

See the documentation files for detailed examples:
- Check Calendar and Search Documents
- Multi-Tool Research Request  
- Meeting Preparation Workflow

Testing
--------------

Unit and integration tests use `pytest`. To run the tests locally:

```bash
pip install -r requirements.txt
pytest -q
```

Tests cover:
- Embedding service behavior
- Vector store operations (semantic, BM25, hybrid search)
- RAG agent response generation and caching
- **LangGraph workflow components** (plan generation, tool routing, execution)
- **Workflow node tests** (all 7 nodes thoroughly tested)
- CLI output formatting
- Integration with mocked OpenAI and ChromaDB

Run LangGraph workflow tests specifically:

```bash
pytest tests/test_langgraph_workflow.py -v
```

Notes and next steps
- The code follows SOLID-aligned abstractions so different embedding providers, vector stores, LLM backends, or calendar services can be swapped in.
- The BM25 index is maintained incrementally in memory for demo-sized datasets; for large corpora, use a dedicated lexical index (Whoosh/Elasticsearch) or persist BM25 between runs.
- RAG generation currently uses a simple system prompt; consider extending with domain-specific instructions or chains of thought.
- Consider adding CLI flags to configure batch behavior (e.g., `--mode`, `--k`, `--alpha`, `--rag`) or support recursive directory traversal.
- Calendar integration can be extended to create events, search by organizer, or fetch specific calendar resources.

**LangGraph Workflow Enhancements:**
- Parallel execution of independent workflow steps for improved performance
- Conditional branching based on tool execution results
- Tool chaining with data passing between steps
- Workflow state persistence and recovery
- Multi-turn conversation support for iterative refinement
- Custom tool framework for user-defined operations
- Advanced caching strategies for frequently used queries

Documentation Reference
------------------------

Complete documentation for all features is available:

**Core Features:**
- [README.md](README.md) — This file, project overview

**LangGraph Workflow (Homework.04 NEW):**
- [docs/LANGGRAPH_WORKFLOW.md](docs/LANGGRAPH_WORKFLOW.md) — Architecture guide and node descriptions
- [docs/LANGGRAPH_QUICKSTART.md](docs/LANGGRAPH_QUICKSTART.md) — Quick start guide with examples
- [docs/LANGGRAPH_IMPLEMENTATION.md](docs/LANGGRAPH_IMPLEMENTATION.md) — Implementation summary
- [LANGGRAPH_CHECKLIST.md](LANGGRAPH_CHECKLIST.md) — Verification checklist

**Other Resources:**
- [IP Geolocation README](IP_GEOLOCATION_README.md) — IP geolocation service details
- [Google Calendar README](GOOGLE_CALENDAR_README.md) — Calendar integration setup
- [Tool Clients Guide](docs/TOOL_CLIENTS_GUIDE.md) — External API client documentation
- [Tool Clients Summary](docs/TOOL_CLIENTS_SUMMARY.md) — Implementation summary and architecture

**Test Suite:**
- [tests/test_langgraph_workflow.py](tests/test_langgraph_workflow.py) — Comprehensive tests and examples
