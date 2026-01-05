"""
Unit tests for query expansion module.

Why this module exists:
- Tests expand_query() function with FakeLLM
- Tests merge_retrieved_chunks() deduplication logic
- Tests edge cases (empty results, LLM failures)

Design decisions:
- Use FakeLLM for deterministic testing (no OpenAI API calls)
- Test deduplication by chunk_id
- Test round-robin merge algorithm
"""

from langchain_core.documents import Document

from app.rag.query_expansion import expand_query, merge_retrieved_chunks, parse_expanded_queries
from app.tests.test_fakes import FakeLLM


def test_expand_query_generates_multiple_queries():
    """
    Test that expand_query returns original + expanded queries.

    Why this test: Validates core query expansion logic with fake LLM.
    Ensures original query is preserved as first element.
    """
    # Assert: Should return [original, expansion1, expansion2]

    # FakeLLM automatically returns "Alternative phrasing 1\nAlternative phrasing 2"
    # when it detects query expansion prompts
    fake_llm = FakeLLM()

    queries = expand_query(
        original_query="What is deployment?",
        llm=fake_llm,
        num_expansions=2,
    )

    assert len(queries) == 3, "Should return original + 2 expansions"
    assert queries[0] == "What is deployment?", "First should be original"
    assert "Alternative phrasing 1" in queries, "Should include first expansion"
    assert "Alternative phrasing 2" in queries, "Should include second expansion"


def test_expand_query_includes_original_first():
    """
    Test that original query is always first in the list.

    Why this test: Original query captures user intent most directly
    and should be prioritized in retrieval.
    """
    # Assert: First query must be the original

    fake_llm = FakeLLM()

    queries = expand_query(
        original_query="How do I deploy?",
        llm=fake_llm,
        num_expansions=2,
    )

    assert queries[0] == "How do I deploy?", "Original must be first"


def test_expand_query_with_zero_expansions():
    """
    Test that num_expansions=0 returns only original query.

    Why this test: Users should be able to disable expansion by setting
    num_expansions to 0, which effectively disables the feature.
    """
    # Assert: Should return only original query

    fake_llm = FakeLLM(response="Should not be used")

    queries = expand_query(
        original_query="Test query",
        llm=fake_llm,
        num_expansions=0,
    )

    assert len(queries) == 1, "Should return only original"
    assert queries[0] == "Test query", "Should be original query"


def test_expand_query_handles_llm_failure_gracefully():
    """
    Test that expansion failures fall back to original query.

    Why this test: LLM calls can fail; system should degrade gracefully
    rather than failing completely.
    """
    # Assert: Should return original query if expansion fails

    # Create LLM that raises exception
    class FailingLLM(FakeLLM):
        def invoke(self, messages, **kwargs):
            raise Exception("LLM failed")

    failing_llm = FailingLLM()

    queries = expand_query(
        original_query="Test query",
        llm=failing_llm,
        num_expansions=2,
    )

    assert len(queries) == 1, "Should fall back to original only"
    assert queries[0] == "Test query", "Should be original query"


def test_parse_expanded_queries_handles_numbering():
    """
    Test that parse_expanded_queries removes common list markers.

    Why this test: LLMs often add numbering or bullets despite instructions.
    Parser must be robust to formatting variations.
    """
    # Assert: Should remove numbering and bullets

    llm_response = """1. First alternative
2. Second alternative
3. Third alternative"""

    queries = parse_expanded_queries(llm_response)

    assert len(queries) == 3
    assert queries[0] == "First alternative"
    assert queries[1] == "Second alternative"
    assert queries[2] == "Third alternative"


def test_parse_expanded_queries_handles_bullets():
    """
    Test that parse_expanded_queries removes bullet points.
    """
    # Assert: Should remove various bullet formats

    llm_response = """- First alternative
- Second alternative"""

    queries = parse_expanded_queries(llm_response)

    assert len(queries) == 2
    assert queries[0] == "First alternative"
    assert queries[1] == "Second alternative"


def test_parse_expanded_queries_filters_empty_lines():
    """
    Test that parse_expanded_queries filters out empty lines.
    """
    # Assert: Should skip empty lines

    llm_response = """First alternative

Second alternative


Third alternative"""

    queries = parse_expanded_queries(llm_response)

    assert len(queries) == 3
    assert queries == ["First alternative", "Second alternative", "Third alternative"]


def test_merge_retrieved_chunks_deduplicates():
    """
    Test that merge_retrieved_chunks removes duplicates by chunk_id.

    Why this test: Multiple queries may retrieve the same chunk.
    Deduplication prevents redundant context.
    """
    # Assert: Duplicate chunks should appear only once

    doc1 = Document(page_content="Doc 1", metadata={"chunk_id": "test.md:0"})
    doc2 = Document(page_content="Doc 2", metadata={"chunk_id": "test.md:1"})
    doc3 = Document(page_content="Doc 3", metadata={"chunk_id": "test.md:2"})

    chunks_per_query = [
        [doc1, doc2],  # Query 1
        [doc2, doc3],  # Query 2 (doc2 is duplicate)
    ]

    merged = merge_retrieved_chunks(chunks_per_query, top_k=4)

    assert len(merged) == 3, "Should have 3 unique chunks (doc2 deduplicated)"

    chunk_ids = [c.metadata["chunk_id"] for c in merged]
    assert len(chunk_ids) == len(set(chunk_ids)), "No duplicate chunk_ids"


def test_merge_respects_top_k_limit():
    """
    Test that merge_retrieved_chunks respects top_k parameter.

    Why this test: Final context should fit within token budget.
    Limiting to top_k prevents context overflow.
    """
    # Assert: Should return at most top_k chunks

    docs = [
        Document(page_content=f"Doc {i}", metadata={"chunk_id": f"test.md:{i}"})
        for i in range(10)
    ]

    chunks_per_query = [
        docs[:5],  # 5 chunks
        docs[5:],  # 5 more chunks (10 total unique)
    ]

    merged = merge_retrieved_chunks(chunks_per_query, top_k=6)

    assert len(merged) == 6, "Should return exactly top_k chunks"


def test_merge_round_robin_balances_contributions():
    """
    Test that round-robin merge balances contributions from all queries.

    Why this test: Validates round-robin algorithm. Ensures all query
    variations contribute to final results, not just the first query.
    """
    # Assert: Should interleave chunks from different queries

    doc_a = Document(page_content="A", metadata={"chunk_id": "a"})
    doc_b = Document(page_content="B", metadata={"chunk_id": "b"})
    doc_c = Document(page_content="C", metadata={"chunk_id": "c"})
    doc_d = Document(page_content="D", metadata={"chunk_id": "d"})
    doc_e = Document(page_content="E", metadata={"chunk_id": "e"})
    doc_f = Document(page_content="F", metadata={"chunk_id": "f"})

    chunks_per_query = [
        [doc_a, doc_b],  # Query 1
        [doc_c, doc_d],  # Query 2
        [doc_e, doc_f],  # Query 3
    ]

    merged = merge_retrieved_chunks(chunks_per_query, top_k=6)

    # Round-robin should give: A (Q1), C (Q2), E (Q3), B (Q1), D (Q2), F (Q3)
    chunk_ids = [c.metadata["chunk_id"] for c in merged]
    assert chunk_ids == ["a", "c", "e", "b", "d", "f"], "Should round-robin"


def test_merge_handles_empty_query_results():
    """
    Test that merge handles cases where some queries return no results.

    Why this test: Some expanded queries may not match any documents.
    Merge should handle empty lists gracefully.
    """
    # Assert: Should handle empty chunk lists gracefully

    doc1 = Document(page_content="Doc 1", metadata={"chunk_id": "test.md:0"})

    chunks_per_query = [
        [doc1],  # Query 1: 1 result
        [],      # Query 2: 0 results
        [],      # Query 3: 0 results
    ]

    merged = merge_retrieved_chunks(chunks_per_query, top_k=4)

    assert len(merged) == 1
    assert merged[0] == doc1


def test_merge_handles_all_empty_results():
    """
    Test that merge handles all queries returning empty results.

    Why this test: Edge case where no documents match any query.
    """
    # Assert: Should return empty list

    chunks_per_query = [
        [],  # Query 1: 0 results
        [],  # Query 2: 0 results
    ]

    merged = merge_retrieved_chunks(chunks_per_query, top_k=4)

    assert len(merged) == 0, "Should return empty list"


def test_merge_preserves_first_occurrence_priority():
    """
    Test that when a chunk appears in multiple queries, first occurrence wins.

    Why this test: Original query should be prioritized. If same chunk
    appears in both original and expansion results, its position from
    original query should determine final rank.
    """
    # Assert: Chunk position determined by first occurrence

    doc_shared = Document(page_content="Shared", metadata={"chunk_id": "shared"})
    doc_a = Document(page_content="A", metadata={"chunk_id": "a"})
    doc_b = Document(page_content="B", metadata={"chunk_id": "b"})

    chunks_per_query = [
        [doc_a, doc_shared],  # Query 1: shared is 2nd
        [doc_shared, doc_b],  # Query 2: shared is 1st (but should be ignored as duplicate)
    ]

    merged = merge_retrieved_chunks(chunks_per_query, top_k=4)

    # Round-robin: A (Q1 pos 0), shared (Q2 pos 0 but dup, skip), B (Q2 pos 1), shared (Q1 pos 1 but dup, skip)
    # Actually: A (Q1 pos 0), shared (Q2 pos 0 dup skip), A done, shared (Q1 pos 1)
    # Wait, let me reconsider: Round-robin by position
    # Position 0: A from Q1, shared from Q2 (dup? No, A is new, shared is new)
    # Position 1: shared from Q1 (dup!), B from Q2

    chunk_ids = [c.metadata["chunk_id"] for c in merged]

    # Correct sequence: pos 0 Q1=A ✓, pos 0 Q2=shared ✓, pos 1 Q1=shared ✗dup, pos 1 Q2=B ✓
    assert chunk_ids == ["a", "shared", "b"], "First occurrence determines inclusion"
