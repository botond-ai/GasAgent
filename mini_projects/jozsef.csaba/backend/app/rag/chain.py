"""
RAG chain for question answering.

Why this module exists:
- Orchestrates RAG pipeline: retrieve chunks, build prompt, call LLM
- Provides clean interface for chat endpoint
- Separates RAG logic from API handler logic

Design decisions:
- No conversation history (stateless RAG)
- Returns answer + source attributions
- Injectable LLM allows testing with FakeLLM
"""

from typing import Any, List

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.core.logging import get_logger
from app.rag.prompts import build_rag_prompt
from app.rag.vectorstore import load_vectorstore, retrieve_chunks
from app.schemas.chat import SourceAttribution

logger = get_logger(__name__)


def create_chat_llm(settings: Settings) -> Any:
    """
    Create ChatOpenAI instance for RAG.

    Why this function: Factory pattern allows:
    1. Dependency injection (tests can inject FakeLLM)
    2. Configuration from Settings
    3. LangSmith tracing (if enabled)

    Args:
        settings: Application settings

    Returns:
        Any: LangChain LLM instance (typed as Any for fake compatibility)
    """
    # Assert: API key must be present
    assert settings.OPENAI_API_KEY, "OPENAI_API_KEY must be set"

    logger.info(f"Creating ChatOpenAI with model: {settings.OPENAI_CHAT_MODEL}")

    # Why ChatOpenAI: LangChain's wrapper for OpenAI chat models
    # Handles API calls, streaming, and LangSmith tracing
    llm = ChatOpenAI(
        openai_api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_CHAT_MODEL,
    )

    return llm


def answer_question(
    query: str,
    top_k: int,
    temperature: float,
    settings: Settings,
    embeddings: Any,
    llm: Any,
    enable_query_expansion: bool = False,
    num_expansions: int = 2,
) -> tuple[str, List[SourceAttribution], List[str] | None]:
    """
    Answer a question using RAG with optional query expansion.

    Why this function: Core RAG logic that:
    1. Loads vector store
    2. (Optional) Expands query into alternative phrasings
    3. Retrieves relevant chunks (using expanded queries if enabled)
    4. Merges and deduplicates chunks from multiple queries
    5. Builds prompt with context
    6. Calls LLM to generate answer
    7. Formats source attributions

    Why injectable embeddings and llm: Allows tests to inject fakes
    (no OpenAI API calls during testing).

    Why stateless: No conversation history; each question is independent.
    Simplifies implementation and matches demo requirements.

    Why query expansion parameter: Allows A/B testing and gradual rollout.
    Users can compare performance with/without expansion.

    Why configurable num_expansions: Different queries benefit from different
    numbers of expansions; flexibility enables experimentation.

    Args:
        query: User's question
        top_k: Number of chunks to retrieve
        temperature: LLM sampling temperature
        settings: Application settings
        embeddings: Embeddings instance (real or fake)
        llm: LLM instance (real or fake)
        enable_query_expansion: Enable query expansion for improved retrieval
        num_expansions: Number of query variations to generate (0-4)

    Returns:
        Tuple of (answer string, list of source attributions, expanded queries used or None)

    Raises:
        RuntimeError: If vector store not found or RAG pipeline fails
    """
    # Assert: Query must not be empty
    assert query.strip(), "Query must not be empty"

    logger.info(f"Answering question (top_k={top_k}, temperature={temperature}, expansion={enable_query_expansion})")

    # Step 1: Load vector store
    # Why load per request: Could cache in memory for production,
    # but loading is fast enough for demo and avoids stale index issues
    vectorstore = load_vectorstore(embeddings, settings)

    # Step 2: Retrieve relevant chunks (WITH or WITHOUT expansion)
    expanded_queries_used = None

    if enable_query_expansion and num_expansions > 0:
        # Import query expansion functions
        from app.rag.query_expansion import expand_query, merge_retrieved_chunks

        # Generate expanded queries
        queries = expand_query(query, llm, num_expansions)
        expanded_queries_used = queries
        logger.info(f"Expanded to {len(queries)} queries: {queries}")

        # Retrieve chunks for each query
        chunks_per_query = []
        for q in queries:
            chunks = retrieve_chunks(vectorstore, q, top_k)
            chunks_per_query.append(chunks)

        # Merge and deduplicate
        context_chunks = merge_retrieved_chunks(chunks_per_query, top_k)
        logger.info(f"Merged to {len(context_chunks)} unique chunks")
    else:
        # Original behavior: single query retrieval
        # Why similarity search: Finds chunks with embeddings closest to query
        context_chunks = retrieve_chunks(vectorstore, query, top_k)

    if not context_chunks:
        logger.warning("No context chunks retrieved")
        return "I don't know based on the provided documentation.", [], expanded_queries_used

    # Step 3: Build prompt with context
    # Why system + human messages: Modern chat models expect message format
    messages = build_rag_prompt(query, context_chunks)

    # Step 4: Call LLM with temperature
    # Why invoke: Synchronous call to LLM (could use ainvoke for async)
    # Why temperature parameter: Allows caller to control response variability
    llm_with_temp = llm.bind(temperature=temperature)
    response = llm_with_temp.invoke(messages)

    # Extract answer text
    # Why .content: ChatOpenAI returns AIMessage with content attribute
    answer = response.content if hasattr(response, "content") else str(response)

    logger.info(f"Generated answer ({len(answer)} chars)")

    # Step 5: Format source attributions
    # Why snippet: Provides preview of source content in response
    # Why 240 chars: Enough to preview, not so long that response is huge
    sources = []
    for chunk in context_chunks:
        source_id = chunk.metadata.get("chunk_id", "unknown")
        filename = chunk.metadata.get("filename", "unknown")
        snippet = chunk.page_content[:240]  # First 240 chars

        sources.append(
            SourceAttribution(
                source_id=source_id,
                filename=filename,
                snippet=snippet,
            )
        )

    logger.debug(f"Created {len(sources)} source attributions")

    return answer, sources, expanded_queries_used
