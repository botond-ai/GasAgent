"""
Unit tests for workflow nodes.
Tests individual node functionality with mocked dependencies.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.workflows.nodes import WorkflowNodes, add_error, IntentDetection, TriageClassification


class TestAddError:
    """Tests for the add_error helper function."""

    def test_add_error_to_empty_state(self):
        """Test adding error to state without existing errors."""
        state = {"ticket_id": "test-123"}
        result = add_error(state, "test_node", "Test error", recoverable=True)

        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "test_node"
        assert result["errors"][0]["message"] == "Test error"
        assert result["errors"][0]["recoverable"] is True
        assert result["has_critical_error"] is False

    def test_add_error_non_recoverable(self):
        """Test adding non-recoverable error sets critical flag."""
        state = {"ticket_id": "test-123"}
        result = add_error(state, "test_node", "Critical error", recoverable=False)

        assert result["has_critical_error"] is True

    def test_add_error_preserves_existing_errors(self):
        """Test that existing errors are preserved."""
        state = {
            "ticket_id": "test-123",
            "errors": [{"node": "previous", "message": "Old error", "recoverable": True}]
        }
        result = add_error(state, "test_node", "New error", recoverable=True)

        assert len(result["errors"]) == 2


class TestWorkflowNodes:
    """Tests for WorkflowNodes class."""

    @pytest.fixture
    def mock_rag_service(self):
        """Create mock RAG service."""
        mock = MagicMock()
        mock.expand_queries = AsyncMock(return_value=["query1", "query2"])
        mock.search_documents = AsyncMock(return_value=[{"text": "doc1", "score": 0.9}])
        mock.rerank_documents = AsyncMock(return_value=[{"text": "doc1", "score": 0.95}])
        return mock

    @pytest.fixture
    def workflow_nodes(self, mock_rag_service):
        """Create WorkflowNodes instance with mocked dependencies."""
        with patch('app.workflows.nodes.ChatOpenAI') as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance
            nodes = WorkflowNodes(rag_service=mock_rag_service)
            nodes.llm = mock_llm_instance
            return nodes

    @pytest.fixture
    def sample_state(self):
        """Create sample workflow state."""
        return {
            "ticket_id": "test-123",
            "raw_message": "My laptop is running slowly",
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "errors": []
        }


class TestDetectIntent(TestWorkflowNodes):
    """Tests for detect_intent node."""

    @pytest.mark.asyncio
    async def test_detect_intent_success(self, workflow_nodes, sample_state):
        """Test successful intent detection."""
        mock_result = IntentDetection(problem_type="technical", sentiment="neutral")
        workflow_nodes.llm.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_result
        )

        # Mock the chain
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)
        with patch.object(workflow_nodes.llm, 'with_structured_output', return_value=MagicMock()):
            with patch('app.workflows.nodes.ChatPromptTemplate') as mock_prompt:
                mock_prompt.from_messages.return_value.__or__ = MagicMock(return_value=mock_chain)

                result = await workflow_nodes.detect_intent(sample_state)

        assert result["problem_type"] == "technical"
        assert result["sentiment"] == "neutral"

    @pytest.mark.asyncio
    async def test_detect_intent_fallback_on_error(self, workflow_nodes, sample_state):
        """Test fallback values when intent detection fails."""
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM error"))

        with patch.object(workflow_nodes.llm, 'with_structured_output', return_value=MagicMock()):
            with patch('app.workflows.nodes.ChatPromptTemplate') as mock_prompt:
                mock_prompt.from_messages.return_value.__or__ = MagicMock(return_value=mock_chain)

                result = await workflow_nodes.detect_intent(sample_state)

        assert result["problem_type"] == "other"
        assert result["sentiment"] == "neutral"
        assert "errors" in result


class TestExpandQueries(TestWorkflowNodes):
    """Tests for expand_queries node."""

    @pytest.mark.asyncio
    async def test_expand_queries_success(self, workflow_nodes, sample_state, mock_rag_service):
        """Test successful query expansion."""
        result = await workflow_nodes.expand_queries(sample_state)

        assert "search_queries" in result
        assert len(result["search_queries"]) == 2
        mock_rag_service.expand_queries.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_queries_fallback_on_error(self, workflow_nodes, sample_state, mock_rag_service):
        """Test fallback to original message on error."""
        mock_rag_service.expand_queries = AsyncMock(side_effect=Exception("RAG error"))

        result = await workflow_nodes.expand_queries(sample_state)

        assert result["search_queries"] == [sample_state["raw_message"]]
        assert "errors" in result


class TestSearchRag(TestWorkflowNodes):
    """Tests for search_rag node."""

    @pytest.mark.asyncio
    async def test_search_rag_success(self, workflow_nodes, sample_state, mock_rag_service):
        """Test successful document search."""
        sample_state["search_queries"] = ["query1"]

        result = await workflow_nodes.search_rag(sample_state)

        assert "retrieved_docs" in result
        assert len(result["retrieved_docs"]) == 1
        mock_rag_service.search_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_rag_empty_on_error(self, workflow_nodes, sample_state, mock_rag_service):
        """Test empty results on search error."""
        mock_rag_service.search_documents = AsyncMock(side_effect=Exception("Search error"))

        result = await workflow_nodes.search_rag(sample_state)

        assert result["retrieved_docs"] == []
        assert "errors" in result


class TestRerankDocs(TestWorkflowNodes):
    """Tests for rerank_docs node."""

    @pytest.mark.asyncio
    async def test_rerank_docs_success(self, workflow_nodes, sample_state, mock_rag_service):
        """Test successful document reranking."""
        sample_state["retrieved_docs"] = [{"text": "doc1", "score": 0.8}]

        result = await workflow_nodes.rerank_docs(sample_state)

        assert "reranked_docs" in result
        mock_rag_service.rerank_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_rerank_docs_preserves_on_error(self, workflow_nodes, sample_state, mock_rag_service):
        """Test that original docs are preserved on rerank error."""
        original_docs = [{"text": "doc1", "score": 0.8}]
        sample_state["retrieved_docs"] = original_docs
        mock_rag_service.rerank_documents = AsyncMock(side_effect=Exception("Rerank error"))

        result = await workflow_nodes.rerank_docs(sample_state)

        assert result["reranked_docs"] == original_docs
        assert "errors" in result


class TestExtractHostname:
    """Tests for hostname extraction helper."""

    @pytest.fixture
    def workflow_nodes(self):
        """Create WorkflowNodes instance for testing helper methods."""
        mock_rag = MagicMock()
        with patch('app.workflows.nodes.ChatOpenAI'):
            return WorkflowNodes(rag_service=mock_rag)

    def test_extract_pd_nb_pattern(self, workflow_nodes):
        """Test extraction of PD-NB pattern."""
        result = workflow_nodes._extract_hostname_regex("My laptop PD-NB12345 is slow")
        assert result == "PD-NB12345"

    def test_extract_desktop_pattern(self, workflow_nodes):
        """Test extraction of DESKTOP pattern."""
        result = workflow_nodes._extract_hostname_regex("Issue with DESKTOP-ABC123")
        assert result == "DESKTOP-ABC123"

    def test_extract_case_insensitive(self, workflow_nodes):
        """Test case-insensitive extraction."""
        result = workflow_nodes._extract_hostname_regex("My laptop pd-nb12345 is slow")
        assert result == "PD-NB12345"

    def test_no_hostname_found(self, workflow_nodes):
        """Test no match returns None."""
        result = workflow_nodes._extract_hostname_regex("My computer is slow")
        assert result is None
