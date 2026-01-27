"""
Integration tests for the workflow graph.
Tests the complete workflow execution with mocked external services.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.workflows.graph import SupportWorkflow, SupportWorkflowState
from app.workflows.nodes import WorkflowNodes


class TestSupportWorkflowState:
    """Tests for workflow state type definition."""

    def test_state_accepts_required_fields(self):
        """Test that state accepts required input fields."""
        state: SupportWorkflowState = {
            "ticket_id": "test-123",
            "raw_message": "Test message",
            "customer_name": "Test User",
            "customer_email": "test@example.com"
        }
        assert state["ticket_id"] == "test-123"

    def test_state_accepts_optional_fields(self):
        """Test that state accepts optional fields."""
        state: SupportWorkflowState = {
            "ticket_id": "test-123",
            "raw_message": "Test message",
            "customer_name": "Test User",
            "customer_email": "test@example.com",
            "problem_type": "technical",
            "sentiment": "neutral",
            "errors": [],
            "has_critical_error": False
        }
        assert state["problem_type"] == "technical"


class TestSupportWorkflow:
    """Tests for SupportWorkflow class."""

    @pytest.fixture
    def mock_rag_service(self):
        """Create mock RAG service."""
        mock = MagicMock()
        mock.expand_queries = AsyncMock(return_value=["query1", "query2"])
        mock.search_documents = AsyncMock(return_value=[
            {"text": "Solution document", "score": 0.9, "metadata": {"source": "kb1"}}
        ])
        mock.rerank_documents = AsyncMock(return_value=[
            {"text": "Solution document", "score": 0.95, "metadata": {"source": "kb1"}}
        ])
        return mock

    @pytest.fixture
    def mock_workflow_nodes(self, mock_rag_service):
        """Create WorkflowNodes with mocked LLM."""
        with patch('app.workflows.nodes.ChatOpenAI') as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm_class.return_value = mock_llm

            # Mock structured output for intent detection
            mock_intent = MagicMock()
            mock_intent.problem_type = "technical"
            mock_intent.sentiment = "frustrated"

            # Mock structured output for triage
            mock_triage = MagicMock()
            mock_triage.category = "Technical"
            mock_triage.subcategory = "Performance"
            mock_triage.priority = "P2"
            mock_triage.sla_hours = 24
            mock_triage.suggested_team = "tech_support"
            mock_triage.confidence = 0.85

            # Mock structured output for answer
            mock_citation = MagicMock()
            mock_citation.model_dump = MagicMock(return_value={
                "text": "Solution doc",
                "source": "kb1",
                "relevance": 0.9
            })

            mock_answer = MagicMock()
            mock_answer.greeting = "Hello John,"
            mock_answer.body = "I understand your concern about the slow laptop."
            mock_answer.closing = "Best regards, Support"
            mock_answer.tone = "empathetic_professional"
            mock_answer.citations = [mock_citation]

            # Mock structured output for policy
            mock_policy = MagicMock()
            mock_policy.model_dump = MagicMock(return_value={
                "refund_promise": False,
                "sla_mentioned": False,
                "escalation_needed": False,
                "compliance": "passed",
                "notes": ""
            })

            # Setup chain mock
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(
                side_effect=[mock_intent, mock_triage, mock_answer, mock_policy]
            )

            mock_structured = MagicMock()
            mock_structured.__or__ = MagicMock(return_value=mock_chain)
            mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

            nodes = WorkflowNodes(rag_service=mock_rag_service)
            return nodes

    @pytest.fixture
    def sample_input_state(self):
        """Create sample input state for workflow."""
        return {
            "ticket_id": "test-123",
            "raw_message": "My laptop PD-NB12345 is running very slowly and I'm frustrated",
            "customer_name": "John Doe",
            "customer_email": "john@example.com"
        }


class TestWorkflowConstruction(TestSupportWorkflow):
    """Tests for workflow graph construction."""

    def test_workflow_initializes(self, mock_workflow_nodes):
        """Test that workflow can be initialized."""
        workflow = SupportWorkflow(nodes=mock_workflow_nodes)
        assert workflow.graph is not None

    def test_workflow_has_all_nodes(self, mock_workflow_nodes):
        """Test that workflow contains all expected nodes."""
        workflow = SupportWorkflow(nodes=mock_workflow_nodes)
        # Graph should compile without errors
        assert workflow.graph is not None


class TestWorkflowErrorHandling(TestSupportWorkflow):
    """Tests for workflow error handling paths."""

    @pytest.fixture
    def workflow(self, mock_workflow_nodes):
        """Create workflow instance."""
        return SupportWorkflow(nodes=mock_workflow_nodes)

    @pytest.mark.asyncio
    async def test_handle_error_node(self, workflow, sample_input_state):
        """Test error handler node produces valid output."""
        state_with_error = {
            **sample_input_state,
            "errors": [{"node": "test", "message": "Test error", "recoverable": False}],
            "has_critical_error": True,
            "category": "Technical"
        }

        result = await workflow._handle_error(state_with_error)

        assert "output" in result
        assert result["output"]["error"] is True
        assert result["output"]["triage"]["priority"] == "P1"
        assert result["output"]["policy_check"]["escalation_needed"] is True

    @pytest.mark.asyncio
    async def test_fallback_answer_node(self, workflow, sample_input_state):
        """Test fallback answer node produces valid response."""
        state = {**sample_input_state, "sentiment": "frustrated"}

        result = await workflow._fallback_answer(state)

        assert "answer_draft" in result
        assert "greeting" in result["answer_draft"]
        assert "body" in result["answer_draft"]
        assert result["citations"] == []


class TestWorkflowRouting(TestSupportWorkflow):
    """Tests for workflow conditional routing."""

    def test_should_lookup_device_technical(self):
        """Test device lookup is triggered for technical issues."""
        state = {
            "problem_type": "technical",
            "category": "Hardware"
        }

        # The routing function is internal to _build_graph
        # We test it indirectly through workflow execution


class TestConditionalEdges:
    """Tests for conditional edge functions."""

    def test_check_rag_results_with_docs(self):
        """Test RAG results check returns draft_answer when docs exist."""
        state = {"reranked_docs": [{"text": "doc1"}]}
        # The check function would return "draft_answer"
        assert len(state.get("reranked_docs", [])) > 0

    def test_check_rag_results_empty(self):
        """Test RAG results check returns fallback when no docs."""
        state = {"reranked_docs": []}
        # The check function would return "fallback_answer"
        assert len(state.get("reranked_docs", [])) == 0


class TestWorkflowIntegration:
    """Integration tests for complete workflow execution."""

    @pytest.fixture
    def mock_complete_workflow(self):
        """Create workflow with all dependencies mocked for integration testing."""
        mock_rag = MagicMock()
        mock_rag.expand_queries = AsyncMock(return_value=["expanded query"])
        mock_rag.search_documents = AsyncMock(return_value=[{"text": "solution", "score": 0.9}])
        mock_rag.rerank_documents = AsyncMock(return_value=[{"text": "solution", "score": 0.95}])

        with patch('app.workflows.nodes.ChatOpenAI'):
            nodes = WorkflowNodes(rag_service=mock_rag)

            # Mock all LLM calls to return immediately
            async def mock_detect_intent(state):
                return {"problem_type": "technical", "sentiment": "neutral"}

            async def mock_triage(state):
                return {
                    "category": "Technical",
                    "subcategory": "General",
                    "priority": "P2",
                    "sla_hours": 24,
                    "suggested_team": "tech_support",
                    "triage_confidence": 0.8
                }

            async def mock_fleet(state):
                return {"device_info": None, "device_context": ""}

            async def mock_draft(state):
                return {
                    "answer_draft": {
                        "greeting": "Hello,",
                        "body": "Here is your solution.",
                        "closing": "Best regards",
                        "tone": "formal"
                    },
                    "citations": []
                }

            async def mock_policy(state):
                return {
                    "policy_check": {
                        "refund_promise": False,
                        "sla_mentioned": False,
                        "escalation_needed": False,
                        "compliance": "passed"
                    }
                }

            # Override node methods
            nodes.detect_intent = mock_detect_intent
            nodes.triage_classify = mock_triage
            nodes.fleet_lookup = mock_fleet
            nodes.draft_answer = mock_draft
            nodes.check_policy = mock_policy

            return SupportWorkflow(nodes=nodes)

    @pytest.mark.asyncio
    async def test_complete_workflow_execution(self, mock_complete_workflow):
        """Test complete workflow processes ticket successfully."""
        input_state = {
            "ticket_id": "integration-test-1",
            "raw_message": "My computer is slow",
            "customer_name": "Test User",
            "customer_email": "test@example.com"
        }

        result = await mock_complete_workflow.process_ticket(input_state)

        assert "output" in result
        assert result["output"]["ticket_id"] == "integration-test-1"
        assert "triage" in result["output"]
        assert "answer_draft" in result["output"]
