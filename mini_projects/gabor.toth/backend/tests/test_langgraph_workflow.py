"""Unit tests for LangGraph workflow."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List
from pydantic import ValidationError

from domain.models import RetrievedChunk, CategoryDecision
from domain.interfaces import (
    CategoryRouter, EmbeddingService, VectorStore, RAGAnswerer, ActivityCallback
)
from services.langgraph_workflow import (
    create_advanced_rag_workflow, AdvancedRAGAgent, WorkflowState,
    SearchStrategy, SearchResult, WorkflowInput, WorkflowOutput, CitationSource
)


# Fixtures

@pytest.fixture
def mock_activity_callback():
    """Mock activity callback."""
    callback = AsyncMock(spec=ActivityCallback)
    callback.log_activity = AsyncMock()
    return callback


@pytest.fixture
def mock_category_router():
    """Mock category router."""
    router = AsyncMock(spec=CategoryRouter)
    router.decide_category = AsyncMock(
        return_value=CategoryDecision(
            category="docs",
            reason="Question is about documentation"
        )
    )
    return router


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = AsyncMock(spec=EmbeddingService)
    service.embed_text = AsyncMock(
        return_value=[0.1, 0.2, 0.3, 0.4, 0.5] * 256  # 1280-dim embedding
    )
    return service


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    store = AsyncMock(spec=VectorStore)
    
    # Create mock chunks
    mock_chunks = [
        RetrievedChunk(
            content="This is a documentation chunk",
            source="docs/readme.md",
            distance=0.95
        ),
        RetrievedChunk(
            content="Another documentation chunk",
            source="docs/guide.md",
            distance=0.92
        ),
    ]
    
    store.query = AsyncMock(return_value=mock_chunks)
    return store


@pytest.fixture
def mock_rag_answerer():
    """Mock RAG answerer."""
    answerer = AsyncMock(spec=RAGAnswerer)
    answerer.generate_answer = AsyncMock(
        return_value="This is the generated answer based on the documentation."
    )
    return answerer


@pytest.fixture
def compiled_workflow(
    mock_category_router,
    mock_embedding_service,
    mock_vector_store,
    mock_rag_answerer
):
    """Create compiled workflow."""
    return create_advanced_rag_workflow(
        category_router=mock_category_router,
        embedding_service=mock_embedding_service,
        vector_store=mock_vector_store,
        rag_answerer=mock_rag_answerer
    )


@pytest.fixture
def agent(compiled_workflow):
    """Create agent."""
    return AdvancedRAGAgent(compiled_workflow)


# Tests

class TestWorkflowValidation:
    """Tests for input validation node."""

    def test_validate_input_success(self, compiled_workflow):
        """Test successful input validation."""
        state: WorkflowState = {
            "question": "How to use the API?",
            "available_categories": ["docs", "tutorials"],
            "workflow_steps": []
        }
        
        # Get the validate_input node
        graph = compiled_workflow
        result = graph.invoke(state)
        
        assert "input_validated" in result["workflow_steps"]

    def test_validate_input_empty_question(self, compiled_workflow):
        """Test validation with empty question."""
        state: WorkflowState = {
            "question": "",
            "available_categories": ["docs"],
            "workflow_steps": []
        }
        
        result = compiled_workflow.invoke(state)
        assert "Question is empty" in result.get("error_messages", [])

    def test_validate_input_no_categories(self, compiled_workflow):
        """Test validation with no categories."""
        state: WorkflowState = {
            "question": "How to use the API?",
            "available_categories": [],
            "workflow_steps": []
        }
        
        result = compiled_workflow.invoke(state)
        assert "No categories available" in result.get("error_messages", [])


class TestCategoryRouting:
    """Tests for category routing node."""

    @pytest.mark.asyncio
    async def test_category_routing_success(
        self, agent, mock_category_router, mock_activity_callback
    ):
        """Test successful category routing."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs", "tutorials"],
            activity_callback=mock_activity_callback
        )
        
        assert result["routed_category"] == "docs"
        assert "category_routed" in result["workflow_steps"]
        assert mock_category_router.decide_category.called

    @pytest.mark.asyncio
    async def test_category_routing_with_confidence(
        self, agent, mock_activity_callback
    ):
        """Test category routing returns confidence."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=mock_activity_callback
        )
        
        assert result["routed_category"] is not None
        assert "category_routed" in result["workflow_steps"]


class TestEmbedding:
    """Tests for question embedding node."""

    @pytest.mark.asyncio
    async def test_question_embedding(
        self, agent, mock_embedding_service, mock_activity_callback
    ):
        """Test question embedding."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=mock_activity_callback
        )
        
        assert mock_embedding_service.embed_text.called
        assert "question_embedded" in result["workflow_steps"]


class TestRetrieval:
    """Tests for retrieval nodes."""

    @pytest.mark.asyncio
    async def test_category_search(
        self, agent, mock_vector_store, mock_activity_callback
    ):
        """Test category-based search."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=mock_activity_callback
        )
        
        assert result["search_strategy"] == SearchStrategy.CATEGORY_BASED
        assert len(result["context_chunks"]) > 0
        assert "category_searched" in result["workflow_steps"]

    @pytest.mark.asyncio
    async def test_search_evaluation(
        self, agent, mock_activity_callback
    ):
        """Test search quality evaluation."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=mock_activity_callback
        )
        
        assert "search_evaluated" in result["workflow_steps"]

    @pytest.mark.asyncio
    async def test_fallback_search_trigger(
        self, compiled_workflow, mock_vector_store, mock_activity_callback
    ):
        """Test fallback search is triggered when needed."""
        # Configure vector store to return no results
        mock_vector_store.query = AsyncMock(return_value=[])
        
        agent = AdvancedRAGAgent(compiled_workflow)
        
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs", "tutorials"],
            activity_callback=mock_activity_callback
        )
        
        # Fallback should be triggered when no results
        assert "fallback_searched" in result["workflow_steps"]


class TestDeduplication:
    """Tests for chunk deduplication."""

    @pytest.mark.asyncio
    async def test_chunks_deduplication(
        self, compiled_workflow, mock_activity_callback
    ):
        """Test chunk deduplication."""
        agent = AdvancedRAGAgent(compiled_workflow)
        
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=mock_activity_callback
        )
        
        assert "chunks_deduped" in result["workflow_steps"]


class TestAnswerGeneration:
    """Tests for answer generation node."""

    @pytest.mark.asyncio
    async def test_answer_generation(
        self, agent, mock_rag_answerer, mock_activity_callback
    ):
        """Test answer generation."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=mock_activity_callback
        )
        
        assert result["final_answer"] == "This is the generated answer based on the documentation."
        assert "answer_generated" in result["workflow_steps"]
        assert mock_rag_answerer.generate_answer.called


class TestResponseFormatting:
    """Tests for response formatting."""

    @pytest.mark.asyncio
    async def test_response_formatting(
        self, agent, mock_activity_callback
    ):
        """Test response formatting with citations."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=mock_activity_callback
        )
        
        assert "response_formatted" in result["workflow_steps"]
        assert "citation_sources" in result
        assert isinstance(result["citation_sources"], list)


class TestEndToEnd:
    """End-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_workflow(
        self, agent, mock_activity_callback
    ):
        """Test complete workflow execution."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs", "tutorials"],
            activity_callback=mock_activity_callback
        )
        
        # Check result structure
        assert "final_answer" in result
        assert "routed_category" in result
        assert "context_chunks" in result
        assert "citation_sources" in result
        assert "workflow_steps" in result
        assert "search_strategy" in result
        assert "memory_snapshot" in result
        
        # Check workflow steps completeness
        expected_steps = [
            "input_validated",
            "category_routed",
            "question_embedded",
            "category_searched",
            "search_evaluated",
            "chunks_deduped",
            "answer_generated",
            "response_formatted"
        ]
        
        for step in expected_steps:
            assert step in result["workflow_steps"], f"Missing step: {step}"

    @pytest.mark.asyncio
    async def test_workflow_with_activity_logging(
        self, agent, mock_activity_callback
    ):
        """Test workflow activity logging."""
        await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=mock_activity_callback
        )
        
        # Check that activity callback was called
        assert mock_activity_callback.log_activity.called
        call_count = mock_activity_callback.log_activity.call_count
        
        # Multiple logs expected (at least for routing, embedding, search, generation)
        assert call_count >= 3

    @pytest.mark.asyncio
    async def test_workflow_without_callback(self, agent):
        """Test workflow execution without activity callback."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=None
        )
        
        assert result["final_answer"] is not None
        assert len(result["workflow_steps"]) > 0


class TestSearchStrategies:
    """Tests for search strategy selection."""

    @pytest.mark.asyncio
    async def test_category_based_strategy(self, agent):
        """Test category-based search strategy."""
        result = await agent.answer_question(
            user_id="test_user",
            question="How to use the API?",
            available_categories=["docs"],
            activity_callback=None
        )
        
        assert result.search_strategy in [
            SearchStrategy.CATEGORY_BASED.value,
            SearchStrategy.FALLBACK_ALL_CATEGORIES.value
        ]


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_error_messages_on_invalid_input(self, agent):
        """Test error messages for invalid input."""
        result = await agent.answer_question(
            user_id="test_user",
            question="",  # Empty question
            available_categories=[],  # No categories
            activity_callback=None
        )
        
        assert len(result.error_messages) > 0


class TestPydanticModels:
    """Tests for Pydantic model validation."""

    def test_workflow_input_valid(self):
        """Test valid WorkflowInput."""
        input_data = WorkflowInput(
            user_id="user123",
            question="What is LangGraph?",
            available_categories=["docs", "api"]
        )
        
        assert input_data.user_id == "user123"
        assert input_data.question == "What is LangGraph?"
        assert len(input_data.available_categories) == 2

    def test_workflow_input_invalid_short_question(self):
        """Test WorkflowInput with too short question."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowInput(
                user_id="user123",
                question="Hi",  # Too short, min 5 chars
                available_categories=[]
            )
        
        assert "at least 5 characters" in str(exc_info.value)

    def test_workflow_input_invalid_empty_user_id(self):
        """Test WorkflowInput with empty user_id."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowInput(
                user_id="",  # Too short, min 1 char
                question="What is LangGraph?",
                available_categories=[]
            )
        
        assert "at least 1 character" in str(exc_info.value)

    def test_citation_source_valid(self):
        """Test valid CitationSource."""
        citation = CitationSource(
            index=1,
            source="documentation.md",
            distance=0.95,
            preview="LangGraph is a framework..."
        )
        
        assert citation.index == 1
        assert citation.distance == 0.95

    def test_citation_source_invalid_distance(self):
        """Test CitationSource with invalid distance."""
        with pytest.raises(ValidationError) as exc_info:
            CitationSource(
                index=1,
                source="docs.md",
                distance=1.5,  # Max is 1.0
                preview="..."
            )
        
        assert "less than or equal to 1" in str(exc_info.value)

    def test_citation_source_invalid_negative_index(self):
        """Test CitationSource with negative index."""
        with pytest.raises(ValidationError) as exc_info:
            CitationSource(
                index=-1,  # Must be positive
                source="docs.md",
                distance=0.9,
                preview="..."
            )
        
        assert str(exc_info.value)

    def test_search_result_valid(self):
        """Test valid SearchResult."""
        chunks = [
            RetrievedChunk(content="Test content", source="test.md", distance=0.9)
        ]
        
        result = SearchResult(
            chunks=chunks,
            strategy_used=SearchStrategy.CATEGORY_BASED,
            search_time=0.45,
            error=None
        )
        
        assert len(result.chunks) == 1
        assert result.search_time == 0.45
        assert result.error is None

    def test_search_result_invalid_negative_time(self):
        """Test SearchResult with negative search_time."""
        with pytest.raises(ValidationError) as exc_info:
            SearchResult(
                chunks=[],
                strategy_used=SearchStrategy.CATEGORY_BASED,
                search_time=-0.5,  # Must be >= 0
                error=None
            )
        
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_workflow_output_valid(self):
        """Test valid WorkflowOutput."""
        output = WorkflowOutput(
            final_answer="LangGraph is a framework...",
            answer_with_citations="LangGraph is a framework[1]...",
            citation_sources=[
                CitationSource(
                    index=1,
                    source="docs.md",
                    distance=0.95,
                    preview="LangGraph..."
                )
            ],
            workflow_steps=["validate_input", "category_routing"],
            error_messages=[],
            routed_category="docs",
            search_strategy="category_based",
            fallback_triggered=False
        )
        
        assert output.final_answer == "LangGraph is a framework..."
        assert len(output.citation_sources) == 1
        assert len(output.workflow_steps) == 2

    def test_workflow_output_json_serialization(self):
        """Test WorkflowOutput JSON serialization."""
        output = WorkflowOutput(
            final_answer="Answer",
            answer_with_citations="Answer[1]",
            citation_sources=[],
            workflow_steps=["step1"],
            error_messages=[],
            rooted_category="docs"
        )
        
        json_str = output.model_dump_json()
        assert "final_answer" in json_str
        assert "Answer" in json_str
        
        # Can be deserialized back
        import json
        data = json.loads(json_str)
        output2 = WorkflowOutput(**data)
        assert output2.final_answer == output.final_answer

    def test_workflow_output_dict_conversion(self):
        """Test WorkflowOutput dict conversion."""
        output = WorkflowOutput(
            final_answer="Answer",
            answer_with_citations="Answer[1]",
            citation_sources=[],
            workflow_steps=["step1"],
            error_messages=[]
        )
        
        output_dict = output.model_dump()
        assert isinstance(output_dict, dict)
        assert output_dict["final_answer"] == "Answer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

