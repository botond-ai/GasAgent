# Meeting Minutes Embedding CLI (Homework.02)

AI Meeting Assistant app 1.0 that creates OpenAI embeddings for company meeting minutes (or any text files), stores them in a local ChromaDB vector store, performs nearest-neighbor retrieval, and optionally generates LLM-augmented responses using a RAG (Retrieval-Augmented Generation) pattern. The project supports two modes of operation:

- Batch mode (default when a `data/` directory exists): reads `.md`/`.txt` files from `./data`, embeds and indexes them, and prints nearest neighbors (and optionally generated responses) for each file.
- Interactive mode: when no `data/` folder is present, the app starts an interactive prompt where you can enter free-text queries which are embedded, stored, searched and optionally augmented with LLM responses.

App integrates the Google Calendar API for sending meeting invites to appropriate participaants.

Quick overview
- Language: Python 3.11+
- Vector DB: ChromaDB (duckdb+parquet persistence)
- Embeddings: OpenAI Embeddings API (model configurable via `.env`)
- CLI: interactive terminal loop and batch `data/` processing

Files
- `app/config.py` — loads `.env` and exposes typed configuration
- `app/embeddings.py` — `EmbeddingService` abstraction and `OpenAIEmbeddingService` implementation
- `app/vector_store.py` — `VectorStore` abstraction and `ChromaVectorStore` implementation (semantic + hybrid search)
- `app/rag_agent.py` — `RAGAgent` LLM response generation using retrieved documents
- `app/cli.py` — `EmbeddingApp` orchestration, interactive CLI and `process_directory` for batch processing, integrated with RAG
- `app/main.py` — application entrypoint wiring dependencies and auto-detecting `data/` folder
- `requirements.txt` — Python dependencies
- `.env.example` — example environment variables


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
- CLI output formatting
- Integration with mocked OpenAI and ChromaDB

Notes and next steps
- The code follows SOLID-aligned abstractions so different embedding providers, vector stores, LLM backends, or calendar services can be swapped in.
- The BM25 index is maintained incrementally in memory for demo-sized datasets; for large corpora, use a dedicated lexical index (Whoosh/Elasticsearch) or persist BM25 between runs.
- RAG generation currently uses a simple system prompt; consider extending with domain-specific instructions or chains of thought.
- Consider adding CLI flags to configure batch behavior (e.g., `--mode`, `--k`, `--alpha`, `--rag`) or support recursive directory traversal.
- Calendar integration can be extended to create events, search by organizer, or fetch specific calendar resources.
