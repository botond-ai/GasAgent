import pytest
from unittest.mock import AsyncMock, MagicMock

from core.rag_engine import RAGEngine, RAGResult
from infrastructure.vector_store import VectorStore, SearchResult, Domain


@pytest.fixture
def mock_vector_store():
    return MagicMock(spec=VectorStore)


@pytest.fixture
def rag_engine(mock_vector_store):
    return RAGEngine(vector_store=mock_vector_store, relevance_threshold=0.7)


class TestRAGEngineInit:
    def test_init_sets_vector_store(self, rag_engine, mock_vector_store):
        assert rag_engine.vector_store == mock_vector_store

    def test_init_sets_default_relevance_threshold(self, mock_vector_store):
        engine = RAGEngine(vector_store=mock_vector_store)
        assert engine.relevance_threshold == 0.7

    def test_init_sets_custom_relevance_threshold(self, mock_vector_store):
        engine = RAGEngine(vector_store=mock_vector_store, relevance_threshold=0.5)
        assert engine.relevance_threshold == 0.5


class TestRetrieveForQuery:
    @pytest.mark.asyncio
    async def test_returns_rag_result(self, rag_engine, mock_vector_store):
        mock_result = SearchResult(
            text="Test content",
            doc_id="doc1",
            title="Test Doc",
            score=0.85,
            source="/path/to/doc.md",
            domain=Domain.HR
        )

        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await rag_engine.retrieve_for_query("test query", Domain.HR)

        assert isinstance(result, RAGResult)
        assert isinstance(result.context, str)
        assert isinstance(result.citations, list)

    @pytest.mark.asyncio
    async def test_calls_vector_store_search_with_correct_params(self, rag_engine, mock_vector_store):
        mock_vector_store.search = AsyncMock(return_value=[])

        await rag_engine.retrieve_for_query("test query", Domain.IT, top_k=10)

        mock_vector_store.search.assert_called_once_with("test query", Domain.IT, top_k=10)

    @pytest.mark.asyncio
    async def test_filters_results_below_relevance_threshold(self, rag_engine, mock_vector_store):
        high_score_result = SearchResult(
            text="Relevant content",
            doc_id="doc1",
            title="Relevant Doc",
            score=0.85,
            source="/path/doc1.md",
            domain=Domain.HR
        )

        low_score_result = SearchResult(
            text="Irrelevant content",
            doc_id="doc2",
            title="Irrelevant Doc",
            score=0.5,
            source="/path/doc2.md",
            domain=Domain.HR
        )

        mock_vector_store.search = AsyncMock(return_value=[high_score_result, low_score_result])

        result = await rag_engine.retrieve_for_query("test query", Domain.HR)

        assert len(result.citations) == 1
        assert result.citations[0]["doc_id"] == "doc1"

    @pytest.mark.asyncio
    async def test_includes_results_at_exact_threshold(self, rag_engine, mock_vector_store):
        exact_threshold_result = SearchResult(
            text="Threshold content",
            doc_id="doc1",
            title="Threshold Doc",
            score=0.7,  # Exactly at threshold
            source="/path/doc.md",
            domain=Domain.HR
        )

        mock_vector_store.search = AsyncMock(return_value=[exact_threshold_result])

        result = await rag_engine.retrieve_for_query("test query", Domain.HR)

        assert len(result.citations) == 1

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_relevant_results(self, rag_engine, mock_vector_store):
        low_score_result = SearchResult(
            text="Low score content",
            doc_id="doc1",
            title="Low Score Doc",
            score=0.3,
            source="/path/doc.md",
            domain=Domain.HR
        )

        mock_vector_store.search = AsyncMock(return_value=[low_score_result])

        result = await rag_engine.retrieve_for_query("test query", Domain.HR)

        assert result.context == ""
        assert result.citations == []


class TestBuildContext:
    def test_builds_context_from_results(self, rag_engine):
        result1 = SearchResult(
            text="First document content",
            doc_id="doc1",
            title="First Doc",
            score=0.9,
            source="/path/doc1.md",
            domain=Domain.HR
        )

        result2 = SearchResult(
            text="Second document content",
            doc_id="doc2",
            title="Second Doc",
            score=0.85,
            source="/path/doc2.md",
            domain=Domain.HR
        )

        context = rag_engine._build_context([result1, result2])

        assert "[doc1] First Doc:" in context
        assert "First document content" in context
        assert "[doc2] Second Doc:" in context
        assert "Second document content" in context
        assert "\n\n" in context  # Separator between docs

    def test_returns_empty_string_for_no_results(self, rag_engine):
        context = rag_engine._build_context([])
        assert context == ""


class TestFormatCitations:
    def test_formats_citations_correctly(self, rag_engine):
        result = SearchResult(
            text="Content",
            doc_id="doc123",
            title="My Document",
            score=0.92,
            source="/path/doc.md",
            domain=Domain.FINANCE
        )

        citations = rag_engine._format_citations([result])

        assert len(citations) == 1
        assert citations[0] == {
            "doc_id": "doc123",
            "title": "My Document",
            "score": 0.92
        }

    def test_formats_multiple_citations(self, rag_engine):
        result1 = SearchResult(
            text="Content 1",
            doc_id="doc1",
            title="Doc One",
            score=0.9,
            source="/path/doc1.md",
            domain=Domain.HR
        )

        result2 = SearchResult(
            text="Content 2",
            doc_id="doc2",
            title="Doc Two",
            score=0.8,
            source="/path/doc2.md",
            domain=Domain.HR
        )

        citations = rag_engine._format_citations([result1, result2])

        assert len(citations) == 2
        assert citations[0]["doc_id"] == "doc1"
        assert citations[1]["doc_id"] == "doc2"

    def test_returns_empty_list_for_no_results(self, rag_engine):
        citations = rag_engine._format_citations([])
        assert citations == []


class TestRAGResult:
    def test_rag_result_dataclass(self):
        result = RAGResult(
            context="Test context",
            citations=[{"doc_id": "1", "title": "Test", "score": 0.9}]
        )
        assert result.context == "Test context"
        assert len(result.citations) == 1
        assert result.citations[0]["doc_id"] == "1"
