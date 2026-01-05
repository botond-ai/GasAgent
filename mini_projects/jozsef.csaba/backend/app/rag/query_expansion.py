"""
Query expansion for improved RAG retrieval.

Why this module exists:
- Generates alternative query phrasings to improve retrieval recall
- Solves vocabulary mismatch problem (user words != document words)
- Merges results from multiple queries with deduplication

Design decisions:
- LLM-based expansion for semantic equivalence
- Round-robin merge algorithm for fair contribution balancing
- Deduplication by chunk_id to avoid redundant context
"""

from typing import Any, List

from langchain_core.documents import Document

from app.core.logging import get_logger

logger = get_logger(__name__)


def expand_query(
    original_query: str,
    llm: Any,
    num_expansions: int = 2,
) -> List[str]:
    """
    Expand a user query into multiple variations for better retrieval.

    Why this function: Query expansion improves recall by finding documents
    that might use different terminology than the user's original query.

    Why multiple variations: Different phrasings retrieve different chunks,
    increasing the chance of finding relevant information.

    Why include original: Original query captures user intent most directly;
    expansions are supplements, not replacements.

    Algorithm:
    1. Build expansion prompt asking LLM for alternative phrasings
    2. Call LLM to generate expansions
    3. Parse response (split by newlines, clean formatting)
    4. Return list with original first, then expansions

    Args:
        original_query: User's original question
        llm: LLM instance for generating expansions
        num_expansions: Number of alternative queries to generate (default 2)

    Returns:
        List[str]: [original_query, expanded_query_1, expanded_query_2, ...]
    """
    # Assert: Query must not be empty
    assert original_query.strip(), "Query must not be empty"
    assert num_expansions >= 0, "num_expansions must be non-negative"

    # If no expansions requested, return only original
    if num_expansions == 0:
        return [original_query]

    logger.info(f"Expanding query into {num_expansions} variations")

    try:
        # Import here to avoid circular dependency
        from app.rag.prompts import build_query_expansion_prompt

        # Build prompt for query expansion
        messages = build_query_expansion_prompt(original_query, num_expansions)

        # Call LLM to generate expansions
        # Why invoke: Synchronous call sufficient for query expansion
        response = llm.invoke(messages)

        # Extract text from response
        # Why .content: ChatOpenAI returns AIMessage with content attribute
        expansion_text = response.content if hasattr(response, "content") else str(response)

        # Parse expanded queries
        expanded_queries = parse_expanded_queries(expansion_text)

        # Always include original query first
        # Why first: Preserves user's original intent as primary signal
        all_queries = [original_query] + expanded_queries[:num_expansions]

        logger.info(f"Generated {len(all_queries)} total queries (1 original + {len(expanded_queries)} expansions)")
        logger.debug(f"Queries: {all_queries}")

        return all_queries

    except Exception as e:
        # Why fallback: Query expansion failure shouldn't break RAG pipeline
        # Graceful degradation: use original query only
        logger.error(f"Query expansion failed: {e}. Falling back to original query only.")
        return [original_query]


def parse_expanded_queries(llm_response: str) -> List[str]:
    """
    Parse LLM response into list of expanded queries.

    Why this function: LLM responses need robust parsing to handle
    variations in formatting (numbering, extra whitespace, etc.)

    Algorithm:
    1. Split response by newlines
    2. Strip whitespace from each line
    3. Remove common list markers (numbers, dashes, bullets)
    4. Filter out empty lines

    Args:
        llm_response: Raw LLM response text

    Returns:
        List[str]: Cleaned expanded queries
    """
    # Assert: Response should not be empty
    assert llm_response is not None, "LLM response must not be None"

    # Split on newlines and clean
    lines = [line.strip() for line in llm_response.strip().split('\n')]

    # Filter out empty lines and remove common prefixes
    queries = []
    for line in lines:
        if not line:
            continue

        # Remove common list markers
        # Why lstrip with characters: Handles "1. ", "- ", ") ", etc.
        cleaned = line.lstrip('0123456789.-) ')

        if cleaned:
            queries.append(cleaned)

    return queries


def merge_retrieved_chunks(
    chunks_per_query: List[List[Document]],
    top_k: int,
) -> List[Document]:
    """
    Merge and deduplicate chunks from multiple query retrievals.

    Why this function: Query expansion retrieves multiple sets of chunks;
    we need to combine them intelligently without duplicates.

    Why deduplicate by chunk_id: Same chunk retrieved by different queries
    should only appear once in final context.

    Why round-robin: Ensures all query variations contribute fairly;
    prevents one query from dominating the results.

    Why preserve order: Earlier queries (especially original) should be
    prioritized; first occurrence of a chunk determines its rank.

    Why respect top_k: Final context should still fit within token budget;
    limiting to top_k prevents context overflow.

    Algorithm:
    1. Initialize seen_ids set and merged_chunks list
    2. Iterate round-robin through all query result lists by position
    3. For each chunk, check if chunk_id already seen
    4. If new, add to merged_chunks and mark as seen
    5. Stop when merged_chunks reaches top_k

    Example:
        Query 1: [A, B, C, D]
        Query 2: [B, E, F, A]
        Query 3: [G, A, H, I]

        Round-robin (top_k=6):
        Position 0: A (Q1) ✓, B (Q2) ✓, G (Q3) ✓
        Position 1: B (Q1) ✗dup, E (Q2) ✓, A (Q3) ✗dup
        Position 2: C (Q1) ✓, F (Q2) ✓

        Result: [A, B, G, E, C, F]

    Args:
        chunks_per_query: List of chunk lists (one per expanded query)
        top_k: Maximum number of unique chunks to return

    Returns:
        List[Document]: Merged, deduplicated chunks (up to top_k)
    """
    # Assert: Must have at least one query result
    assert len(chunks_per_query) > 0, "Must have at least one query result"
    assert top_k > 0, "top_k must be positive"

    merged_chunks = []
    seen_ids = set()

    # Find max length of any query result
    max_len = max(len(chunks) for chunks in chunks_per_query) if chunks_per_query else 0

    if max_len == 0:
        logger.warning("All query results are empty")
        return []

    # Round-robin through positions
    for position in range(max_len):
        if len(merged_chunks) >= top_k:
            break

        # Try each query's chunk at this position
        for chunks in chunks_per_query:
            if len(merged_chunks) >= top_k:
                break

            # Check if this query has a chunk at this position
            if position < len(chunks):
                chunk = chunks[position]
                chunk_id = chunk.metadata.get("chunk_id", f"unknown_{id(chunk)}")

                # Only add if not seen before
                if chunk_id not in seen_ids:
                    merged_chunks.append(chunk)
                    seen_ids.add(chunk_id)

    total_chunks = sum(len(c) for c in chunks_per_query)
    logger.info(
        f"Merged {len(chunks_per_query)} query results into "
        f"{len(merged_chunks)} unique chunks (from {total_chunks} total)"
    )

    return merged_chunks
