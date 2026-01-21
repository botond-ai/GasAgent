# RAG (Retrieval-Augmented Generation) System

A production-ready Python application for answering questions using Retrieval-Augmented Generation (RAG). The system processes text documents using vector embeddings, retrieves relevant context, and generates natural language answers using large language models. Built with clean architecture principles, dependency injection, and SOLID design patterns.

## Overview

This RAG system converts text documents into vector embeddings using OpenAI's API, stores them in a ChromaDB vector database, retrieves relevant documents through semantic similarity search, and generates contextual answers using OpenAI's language models (GPT-4o-mini by default).

### Key Features

- **RAG Pipeline**: Complete Retrieval-Augmented Generation workflow from query to natural language answer
- **LLM Integration**: Uses OpenAI's language models (GPT-4o-mini, GPT-3.5-turbo, etc.) for answer generation
- **Vector Embedding Generation**: Converts text to high-dimensional vectors using OpenAI's embedding models
- **Smart Text Chunking**: Automatically splits large documents into configurable chunks with optional overlap
- **Individual Chunk Storage**: Each chunk stored separately with full metadata tracking (no averaging)
- **Rich Metadata**: Tracks source document, domain, chunk position, and total chunks for each embedding
- **Multi-Algorithm Search**: Supports both cosine similarity and KNN (Euclidean distance) search methods
- **Context-Aware Answers**: LLM generates responses based on retrieved relevant document chunks
- **Domain Organization**: Processes documents from multiple domain directories (HR, Dev, Support, Management)
- **Persistent Storage**: Uses ChromaDB for efficient vector storage and retrieval
- **Clean Architecture**: Implements SOLID principles with dependency injection and abstract interfaces
- **Docker Support**: Includes containerization for consistent deployment
- **Production-Ready**: Comprehensive error handling, logging, and configuration management

### RAG Workflow

The system implements a complete RAG pipeline:

1. **Document Processing** (One-time setup):
   - Load markdown documents from domain directories (HR, Dev, Support, etc.)
   - Split documents into chunks (configurable size with optional overlap)
   - Generate vector embeddings for each chunk using OpenAI's embedding API
   - Store chunks with embeddings and metadata in ChromaDB

2. **Query Processing** (Runtime):
   - User enters a natural language question
   - Convert question to vector embedding
   - Search vector database for most similar document chunks
   - Retrieve top-k most relevant chunks (default: 3)

3. **Answer Generation** (RAG):
   - Format retrieved chunks as context
   - Send context + user question to LLM (GPT-4o-mini)
   - LLM generates natural language answer based on retrieved information
   - Display answer along with source documents for transparency

This approach combines the precision of semantic search with the natural language capabilities of large language models, ensuring answers are both accurate and well-grounded in your document collection.

## Architecture

### Design Principles

The application follows SOLID principles:

- **Single Responsibility**: Each module has one clear purpose
- **Open/Closed**: Extensible through interfaces without modifying existing code
- **Liskov Substitution**: Abstract interfaces allow swapping implementations
- **Interface Segregation**: Focused, minimal interfaces
- **Dependency Inversion**: Depends on abstractions, not concrete implementations

### Project Structure

```
mini_projects/mark.bertalan/hf_2/
├── scripts/                    # Application source code
│   ├── interfaces.py          # Abstract base classes (Embedder, VectorDB, LLM)
│   ├── embeddings.py          # OpenAI embedding implementation
│   ├── llm.py                 # OpenAI LLM implementation for RAG
│   ├── vector_store.py        # Vector database implementation
│   ├── application.py         # Main application orchestrator with RAG
│   ├── config.py              # Configuration management
│   └── main.py                # Entry point
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variable template
├── .env                      # Local environment variables (git-ignored)
├── .gitignore               # Git exclusion rules
├── Dockerfile               # Container image definition
├── docker-compose.yml       # Multi-container orchestration
└── README.md               # This documentation
```

### Component Architecture

#### 1. Interfaces Layer (`interfaces.py`)

Defines abstract contracts for core functionality:

**Embedder (Abstract Base Class)**
- `get_embedding(text: str) -> List[Tuple[str, List[float]]]`: Convert text to chunked embeddings
  - Returns list of (chunk_text, embedding_vector) tuples
  - Automatically handles text chunking based on configuration

**VectorDB (Abstract Base Class)**
- `add(id, text, embedding, metadata)`: Store vector with optional metadata
- `similarity_search(embedding, k)`: Cosine similarity search, returns results with metadata
- `knn_search(embedding, k)`: Euclidean distance search, returns results with metadata

**LLM (Abstract Base Class)**
- `generate(prompt, context, max_tokens)`: Generate natural language response
  - Takes user prompt and retrieved document chunks as context
  - Returns generated answer text from the language model

#### 2. Service Implementations

**OpenAIEmbedder** (`embeddings.py`)
- Implements `Embedder` interface
- Uses OpenAI API via direct HTTP requests (requests library)
- Configurable model selection (default: text-embedding-3-small)
- **Smart chunking**: Splits text into configurable chunks (default: 500 chars) with optional overlap
- **Individual embeddings**: Each chunk generates a separate embedding (no averaging)
- Comprehensive error handling for network/API failures
- Detailed logging for chunk processing

**Vector Store** (`vector_store.py`)
- Implements `VectorDB` interface
- ChromaDB backend for persistent vector storage
- Dual search algorithms: cosine similarity and KNN
- Automatic collection management

**OpenAI LLM Client** (`llm.py`)
- Implements `LLM` interface
- Uses OpenAI Chat Completions API (gpt-4o-mini, gpt-3.5-turbo, etc.)
- Formats retrieved context documents for the LLM
- Includes system prompt for context-based answering
- Comprehensive error handling for API failures

#### 3. Application Orchestrator (`application.py`)

**EmbeddingApp Class**

Core workflow coordinator that:
1. Loads domain configuration from environment
2. Processes markdown documents from domain directories
3. Generates embeddings for each document chunk
4. Stores each chunk separately with rich metadata (source doc, domain, chunk position)
5. Executes RAG pipeline: retrieves relevant chunks and generates natural language answers

Key Methods:
- `store_and_embed_documents(root_dir)`: Batch process documents into chunks
- `process_query(text, k)`: Embed query and search for similar chunks
- `process_query_with_rag(text, k, max_tokens)`: Complete RAG pipeline with LLM answer generation
- Helper methods for domain parsing, content normalization, and document loading

**Metadata Structure**:
Each stored chunk includes:
- `source_document_id`: Unique identifier for the original document
- `chunk_index`: Position of this chunk (0-indexed)
- `total_chunks`: Total number of chunks from source document
- `domain`: Domain name (hr, dev, support, etc.)

#### 4. Configuration Management (`config.py`)

**Config Dataclass**

Centralized configuration with environment variable support:
- `openai_api_key`: OpenAI API authentication (required)
- `embedding_model`: Model identifier (default: text-embedding-3-small)
- `llm_model`: LLM model for answer generation (default: gpt-4o-mini)
- `embedding_chunk_size`: Maximum characters per chunk (default: 500)
- `overlap`: Overlapping characters between chunks (default: 0)
- `chroma_db_path`: Database storage location (default: ./chroma_db)
- `documents_root`: Root directory for source documents (default: ./embedding_sources)
- `collection_name`: ChromaDB collection name (default: prompts)

Factory method `from_env()` loads from .env file with validation.

## Installation

### Prerequisites

- Python 3.11+
- OpenAI API key
- (Optional) Docker and Docker Compose

### Docker Setup

1. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

2. **Build and run**
   ```bash
   docker build -t embedding-hf2 .
   ```

   ```bash
   docker run -it --env-file ./.env embedding-hf2
   ```

## Text Chunking Strategy

### Why Individual Chunk Storage?

This system stores each chunk as a separate vector rather than averaging embeddings. This approach:

**Advantages:**
- **Preserves semantic meaning**: Each chunk represents a specific concept or section
- **Better retrieval precision**: Search results point to the exact relevant section
- **Avoids information loss**: Averaging embeddings of unrelated content (e.g., HR policy + technical setup) creates meaningless blended vectors
- **Enables context tracking**: Metadata shows which part of which document matched

**How It Works:**
1. Document is split into chunks of `EMBEDDING_CHUNK_SIZE` characters
2. Each chunk gets its own embedding via OpenAI API
3. Each chunk stored with metadata: `{source_document_id, chunk_index, total_chunks, domain}`
4. Search returns individual chunks with full context information

**Example:**
```
Document: "hr_benefits.md" (1500 chars)
  ↓ (chunk_size=500)
Chunk 0: "Healthcare coverage..." → Embedding A → Store with metadata
Chunk 1: "Retirement plans..."   → Embedding B → Store with metadata
Chunk 2: "Time off policies..."  → Embedding C → Store with metadata

Query: "401k matching"
  → Returns Chunk 1 with metadata showing it's from hr_benefits.md, chunk 1/3
```

## Configuration

### Environment Variables

Create a `.env` file (see `.env.example` for template):

```env
# Required
OPENAI_API_KEY=sk-your-api-key-here

# Optional (with defaults)
EMBEDDING_MODEL=text-embedding-3-small    # OpenAI embedding model name
LLM_MODEL=gpt-4o-mini                     # OpenAI LLM model for answer generation
EMBEDDING_CHUNK_SIZE=500                  # Max characters per chunk
OVERLAP=0                                 # Overlapping characters between chunks
CHROMA_DB_PATH=./chroma_db               # Database storage path
DOCUMENTS_ROOT=./embedding_sources        # Root directory for source documents
COLLECTION_NAME=prompts                  # ChromaDB collection
DOMAINS=hr,dev,support,management        # Comma-separated domain list
```

### Domain Configuration

The `DOMAINS` environment variable defines which subdirectories to process. Documents are automatically chunked based on `EMBEDDING_CHUNK_SIZE`:

```
embedding_sources/  (or your DOCUMENTS_ROOT)
├── hr/           # HR domain documents
│   ├── policy1.md    → Split into chunks → Each chunk stored with metadata
│   └── policy2.md    → Split into chunks → Each chunk stored with metadata
├── dev/          # Development domain
│   └── guidelines.md → Split into chunks → Each chunk stored with metadata
├── support/      # Support domain
└── management/   # Management domain
```

**Chunking Behavior:**
- Documents larger than `EMBEDDING_CHUNK_SIZE` are split into multiple chunks
- Each chunk is stored as a separate vector in the database
- Metadata links chunks back to their source document
- Optional `OVERLAP` allows chunks to share characters for better context preservation

## Usage

### Basic Workflow

```python
from scripts.config import Config
from scripts.embeddings import OpenAIEmbeddingClient
from scripts.vector_store import ChromaVectorStore
from scripts.llm import OpenAILLMClient
from scripts.application import EmbeddingApp
from pathlib import Path

# Load configuration
config = Config.from_env()

# Initialize components
embedder = OpenAIEmbeddingClient(
    token=config.openai_api_key,
    model_name=config.embedding_model,
    chunk_size=config.embedding_chunk_size,
    overlap=config.overlap
)
vector_db = ChromaVectorStore(
    db_path=config.chroma_db_path,
    collection_name=config.collection_name
)
llm = OpenAILLMClient(
    token=config.openai_api_key,
    model_name=config.llm_model
)

# Create application
app = EmbeddingApp(embedder, vector_db, llm)

# Process documents
app.store_and_embed_documents(config.documents_root)

# RAG Query: Get natural language answer based on relevant documents
query_id, results, answer = app.process_query_with_rag("What are the employee benefits?", k=3)
print(f"Answer: {answer}")

# Or just search without LLM generation
query_id, results = app.process_query("employee benefits policy", k=5)

# Results structure:
# {
#   'cosine': [(id, distance, similarity, text, metadata), ...],
#   'knn': [(id, euclidean_distance, text, metadata), ...]
# }
#
# Where metadata = {
#   'source_document_id': 'hr_benefits',
#   'chunk_index': 0,
#   'total_chunks': 3,
#   'domain': 'hr'
# }
```

### Running the Application

```bash
# Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Run main application
python -m scripts.main
```

The application will:
1. Load and embed all documents from your configured domains
2. Start an interactive prompt where you can ask questions
3. For each question, retrieve relevant documents and generate an AI answer
4. Display the generated answer along with the source document chunks used

### Docker Usage

#### Build the Docker Image

```bash
docker build -t embedding-demo .
```

#### Run the Application

```bash
docker run -it --env-file .env embedding-demo
```

## API Reference

### EmbeddingApp

#### `__init__(embedding_service: Embedder, vector_store: VectorDB, llm: Optional[LLM] = None)`
Initialize with dependency-injected components.

**Parameters:**
- `embedding_service`: Embedder implementation for text-to-vector conversion
- `vector_store`: VectorDB implementation for storage and retrieval
- `llm`: Optional LLM implementation for RAG answer generation

#### `store_and_embed_documents(root_dir: Path) -> None`
Process all markdown files from configured domain directories.

- Reads DOMAINS environment variable
- Scans each domain directory for .md files
- Splits documents into chunks based on `EMBEDDING_CHUNK_SIZE`
- Generates separate embeddings for each chunk
- Stores each chunk with metadata (source doc, domain, chunk position)
- Normalizes markdown content (removes extra whitespace)

#### `process_query(text: str, k: int = 3) -> Tuple[str, Dict[str, List]]`
Generate embedding for query and search for similar document chunks.

**Parameters:**
- `text`: Query text to search for
- `k`: Number of results per search method (default: 3)

**Returns:**
- Tuple of (query_id, results_dict)
  - `query_id`: UUID for this query
  - `results_dict`: Dictionary with 'cosine' and 'knn' keys
    - `cosine`: List of (id, distance, similarity, text, metadata) tuples
    - `knn`: List of (id, euclidean_distance, text, metadata) tuples
  - `metadata`: Dict with 'source_document_id', 'chunk_index', 'total_chunks', 'domain'

#### `process_query_with_rag(text: str, k: int = 3, max_tokens: int = 500) -> Tuple[str, Dict[str, List], str]`
Execute complete RAG pipeline: retrieve relevant documents and generate natural language answer.

**Parameters:**
- `text`: User's question or query
- `k`: Number of documents to retrieve for context (default: 3)
- `max_tokens`: Maximum tokens for LLM response (default: 500)

**Returns:**
- Tuple of (query_id, results_dict, generated_answer)
  - `query_id`: UUID for this query
  - `results_dict`: Search results (same format as `process_query`)
  - `generated_answer`: Natural language answer from the LLM

**Raises:**
- `ValueError`: If LLM was not provided during initialization

### OpenAIEmbedder

#### `__init__(token: str, model_name: str = "text-embedding-3-small", chunk_size: int = None, overlap: int = 0)`
Initialize OpenAI embedding service.

**Parameters:**
- `token`: OpenAI API key
- `model_name`: Model identifier (default: text-embedding-3-small)
- `chunk_size`: Maximum characters per chunk (None = no chunking)
- `overlap`: Overlapping characters between chunks (default: 0)

#### `get_embedding(text: str) -> List[Tuple[str, List[float]]]`
Generate embedding vectors for input text chunks.

**Parameters:**
- `text`: Input text (automatically chunked if needed)

**Returns:**
- List of (chunk_text, embedding_vector) tuples
  - Each chunk_text is a string segment from the original text
  - Each embedding_vector is a list of floats (1536 dimensions for default model)
  - Single-element list if text fits in one chunk

**Raises:**
- `requests.exceptions.RequestException`: Network/HTTP errors
- `KeyError/IndexError/JSONDecodeError`: Malformed API responses

### OpenAILLMClient

#### `__init__(token: str, model_name: str = "gpt-4o-mini", endpoint: str | None = None)`
Initialize OpenAI LLM service for text generation.

**Parameters:**
- `token`: OpenAI API key
- `model_name`: Chat model identifier (default: gpt-4o-mini)
  - Other options: gpt-3.5-turbo, gpt-4, gpt-4-turbo, etc.
- `endpoint`: Optional custom API endpoint

#### `generate(prompt: str, context: List[str], max_tokens: int = 500) -> str`
Generate natural language response based on prompt and retrieved context.

**Parameters:**
- `prompt`: User's question or query
- `context`: List of relevant document chunks from vector search
- `max_tokens`: Maximum tokens to generate (default: 500)

**Returns:**
- Generated answer text from the LLM

**Raises:**
- `requests.exceptions.RequestException`: Network/HTTP errors
- `KeyError/IndexError/JSONDecodeError`: Malformed API responses

### Config

#### `from_env() -> Config` (classmethod)
Load configuration from environment variables.

**Raises:**
- `ValueError`: When required OPENAI_API_KEY is missing

## Development

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Document all classes and public methods with docstrings
- Keep functions focused and single-purpose

### Testing

```bash
# Run tests (if test suite exists)
pytest tests/

# Run with coverage
pytest --cov=scripts tests/
```

### Adding New Embedding Providers

Implement the `Embedder` interface:

```python
from scripts.interfaces import Embedder
from typing import List, Tuple

class CustomEmbedder(Embedder):
    def get_embedding(self, text: str) -> List[Tuple[str, List[float]]]:
        # Your implementation here
        # Should return list of (chunk_text, embedding_vector) tuples
        # Example:
        chunks = self._split_text(text)  # Your chunking logic
        return [(chunk, self._embed(chunk)) for chunk in chunks]
```

### Adding New Vector Stores

Implement the `VectorDB` interface:

```python
from scripts.interfaces import VectorDB
from typing import List, Tuple, Optional, Dict, Any

class CustomVectorDB(VectorDB):
    def add(self, id: str, text: str, embedding: List[float],
            metadata: Optional[Dict[str, Any]] = None) -> None:
        # Store embedding with optional metadata
        pass

    def similarity_search(self, embedding: List[float], k: int = 3) -> List[Tuple]:
        # Return: List of (id, distance, similarity, text, metadata)
        pass

    def knn_search(self, embedding: List[float], k: int = 3) -> List[Tuple]:
        # Return: List of (id, distance, text, metadata)
        pass
```

### Adding New LLM Providers

Implement the `LLM` interface:

```python
from scripts.interfaces import LLM
from typing import List

class CustomLLM(LLM):
    def generate(self, prompt: str, context: List[str],
                 max_tokens: int = 500) -> str:
        # Format context and prompt for your LLM
        formatted_prompt = self._format_prompt(prompt, context)

        # Call your LLM API
        response = your_llm_api_call(formatted_prompt, max_tokens)

        # Return generated text
        return response

    def _format_prompt(self, prompt: str, context: List[str]) -> str:
        # Your custom prompt formatting logic
        pass
```

## Dependencies

### Core Dependencies

- **requests** (≥2.31.0): HTTP client for OpenAI API calls
- **chromadb** (≥0.4.22): Vector database for embeddings
- **python-dotenv** (≥1.0.0): Environment variable management

### System Requirements

- Python 3.11 or higher
- 2GB RAM minimum (4GB+ recommended for large datasets)
- Disk space for ChromaDB storage (varies by dataset size)

## Troubleshooting

### Common Issues

**"OPENAI_API_KEY not found in environment"**
- Solution: Copy `.env.example` to `.env` and add your API key

**"ModuleNotFoundError: No module named 'scripts'"**
- Solution: Run from project root, or use `python -m scripts.main`

**ChromaDB persistence errors**
- Solution: Ensure `chroma_db` directory exists and has write permissions
- Docker: Check volume mounts in `docker-compose.yml`

**API rate limits**
- Solution: Add retry logic or reduce batch sizes
- Consider implementing exponential backoff

**High memory usage**
- Solution: Process documents in smaller batches
- Adjust ChromaDB configuration for memory constraints

## Performance Considerations

### Embedding Generation

- OpenAI API has rate limits (check your tier)
- **Chunking multiplies API calls**: Each chunk requires a separate API call
  - Example: 10 documents with 3 chunks each = 30 API calls
- Each API call has latency (typically 100-500ms)
- Consider caching embeddings for frequently used texts
- Adjust `EMBEDDING_CHUNK_SIZE` to balance:
  - Smaller chunks = more precise retrieval but more API calls
  - Larger chunks = fewer API calls but less precise results

### Vector Search

- ChromaDB performance scales with dataset size (total number of chunks stored)
- **More chunks = larger search space**: Chunking increases total vectors stored
  - Example: 100 documents → 300 chunks = 3x larger search space
- Cosine similarity: O(n) for exact search
- Consider approximate nearest neighbor (ANN) for large datasets
- Metadata filtering can reduce search space if needed

