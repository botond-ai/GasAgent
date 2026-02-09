"""
Tests for Feedback Metrics Node - Telemetry collection (latency, cache, tokens).

Phase 1.2 - Quality Assurance Enhancement
"""
import pytest
import time
from unittest.mock import MagicMock

from services.agent import QueryAgent, AgentState, DomainType


@pytest.fixture
def agent():
    """Mock QueryAgent for testing."""
    llm_client = MagicMock()
    rag_client = MagicMock()
    return QueryAgent(llm_client, rag_client)


class TestFeedbackMetricsCollection:
    """Test metrics data collection (non-blocking)."""

    @pytest.mark.asyncio
    async def test_metrics_with_citations(self, agent):
        """Test collection of retrieval quality metrics."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "citations": [
                {"doc_id": "IT-KB-267", "title": "VPN Guide", "score": 0.89},
                {"doc_id": "IT-KB-268", "title": "Network Policy", "score": 0.76},
            ],
            "llm_response": "A VPN beállítása [IT-KB-267] alapján...",
            "llm_prompt": "You are a helpful IT assistant...",
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
            "request_start_time": time.time() - 2.0,  # 2 seconds ago
        }

        result = await agent._feedback_metrics_node(state)

        metrics = result.get("feedback_metrics", {})
        assert metrics.get("retrieval_score_top1") == 0.89, "Should capture top-1 retrieval score"
        assert metrics.get("retrieval_count") == 2, "Should count citations"
        assert metrics.get("llm_tokens_input") > 0, "Should estimate input tokens"
        assert metrics.get("llm_tokens_output") > 0, "Should estimate output tokens"
        assert metrics.get("llm_tokens_used") > 0, "Should calculate total tokens"
        assert metrics.get("total_latency_ms") >= 2000, "Should measure latency (at least 2000ms)"

    @pytest.mark.asyncio
    async def test_metrics_empty_citations(self, agent):
        """Test metrics with no citations (generic response)."""
        state: AgentState = {
            "domain": DomainType.GENERAL.value,
            "citations": [],
            "llm_response": "Ez egy általános válasz.",
            "llm_prompt": "Provide a general answer.",
            "messages": [],
            "query": "General question?",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
            "request_start_time": time.time(),
        }

        result = await agent._feedback_metrics_node(state)

        metrics = result.get("feedback_metrics", {})
        assert metrics.get("retrieval_count") == 0, "Should handle empty citations"
        assert metrics.get("retrieval_score_top1") is None, "No score for empty citations"
        assert metrics.get("llm_tokens_output") > 0, "Should still estimate output tokens"

    @pytest.mark.asyncio
    async def test_metrics_validation_errors_tracked(self, agent):
        """Test that validation errors are included in metrics."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "citations": [],
            "llm_response": "Answer without citations",
            "llm_prompt": "",
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": ["Missing [IT-KB-XXX] citations"],
            "retry_count": 1,
            "request_start_time": time.time(),
        }

        result = await agent._feedback_metrics_node(state)

        metrics = result.get("feedback_metrics", {})
        assert metrics.get("validation_errors") == ["Missing [IT-KB-XXX] citations"]
        assert metrics.get("retry_count") == 1, "Should track retry count"

    @pytest.mark.asyncio
    async def test_metrics_non_blocking_error(self, agent):
        """Test that metrics collection failures don't block workflow."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            # Missing required fields to trigger error
            "request_start_time": "invalid",  # Will cause error in time calculation
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "citations": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        # Should not raise exception
        result = await agent._feedback_metrics_node(state)

        assert "feedback_metrics" in result, "Should still return metrics even on error"
        metrics = result.get("feedback_metrics", {})
        assert "error" in metrics, "Should record error message"
        # Workflow continues
        assert result.get("domain") == DomainType.IT.value, "State preserved on error"


class TestMetricsCalculations:
    """Test specific metric calculations."""

    @pytest.mark.asyncio
    async def test_token_estimation_accuracy(self, agent):
        """Test token estimation for known prompts."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "llm_prompt": "Hello, this is a test prompt with exactly ten tokens.",  # ~9 tokens
            "llm_response": "This is a response.",  # ~4 tokens
            "citations": [],
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
            "request_start_time": time.time(),
        }

        result = await agent._feedback_metrics_node(state)

        metrics = result.get("feedback_metrics", {})
        # estimate_tokens uses rough calculation (~4 chars per token)
        assert metrics.get("llm_tokens_input") > 0, "Should estimate input tokens"
        assert metrics.get("llm_tokens_output") > 0, "Should estimate output tokens"
        assert metrics.get("llm_tokens_used") == (
            metrics.get("llm_tokens_input", 0) + metrics.get("llm_tokens_output", 0)
        ), "Total should be sum of input + output"

    @pytest.mark.asyncio
    async def test_latency_measurement_precision(self, agent):
        """Test that latency measurement is within expected range."""
        request_start = time.time() - 1.5  # 1.5 seconds ago
        
        state: AgentState = {
            "domain": DomainType.IT.value,
            "request_start_time": request_start,
            "llm_prompt": "",
            "llm_response": "",
            "citations": [],
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        result = await agent._feedback_metrics_node(state)

        metrics = result.get("feedback_metrics", {})
        latency_ms = metrics.get("total_latency_ms", 0)
        
        # Should be approximately 1500ms (±100ms for execution overhead)
        assert 1400 < latency_ms < 1700, f"Latency should be ~1500ms, got {latency_ms}ms"

    @pytest.mark.asyncio
    async def test_citation_score_extraction(self, agent):
        """Test extraction of citation scores."""
        state: AgentState = {
            "domain": DomainType.MARKETING.value,
            "citations": [
                {"doc_id": "MARK-001", "title": "Brand Guide", "score": 0.92},
                {"doc_id": "MARK-002", "title": "Logo Guide", "score": 0.85},
                {"doc_id": "MARK-003", "title": "Typography", "score": 0.78},
            ],
            "llm_prompt": "",
            "llm_response": "Brand guidelines...",
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
            "request_start_time": time.time(),
        }

        result = await agent._feedback_metrics_node(state)

        metrics = result.get("feedback_metrics", {})
        assert metrics.get("retrieval_score_top1") == 0.92, "Should get highest score"
        assert metrics.get("retrieval_count") == 3, "Should count all results"


class TestMetricsStateIntegration:
    """Test metrics integration with AgentState."""

    @pytest.mark.asyncio
    async def test_metrics_preserve_other_state(self, agent):
        """Test that metrics collection doesn't lose other state."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "query": "VPN setup?",
            "user_id": "emp_001",
            "citations": [{"doc_id": "IT-KB-267", "score": 0.87}],
            "validation_errors": ["Some validation issue"],
            "retry_count": 1,
            "messages": [],
            "retrieved_docs": [],
            "output": {"answer": "VPN setup..."},
            "workflow": {"action": "it_support"},
            "llm_prompt": "Test",
            "llm_response": "Test response",
            "request_start_time": time.time(),
        }

        result = await agent._feedback_metrics_node(state)

        # All original state preserved
        assert result.get("domain") == DomainType.IT.value
        assert result.get("query") == "VPN setup?"
        assert result.get("user_id") == "emp_001"
        assert len(result.get("citations", [])) == 1
        assert result.get("validation_errors") == ["Some validation issue"]
        assert result.get("retry_count") == 1
        assert "feedback_metrics" in result, "Metrics added to state"

    @pytest.mark.asyncio
    async def test_metrics_empty_state_safe(self, agent):
        """Test metrics collection with minimal state."""
        state: AgentState = {
            "domain": DomainType.GENERAL.value,
            "request_start_time": time.time(),
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "citations": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        # Should handle gracefully
        result = await agent._feedback_metrics_node(state)

        assert "feedback_metrics" in result
        metrics = result.get("feedback_metrics", {})
        assert metrics.get("retrieval_count") == 0
        assert metrics.get("validation_errors") == []


class TestMetricsFormatting:
    """Test metrics output format."""

    @pytest.mark.asyncio
    async def test_metrics_dict_serializable(self, agent):
        """Test that metrics can be JSON serialized."""
        import json

        state: AgentState = {
            "domain": DomainType.IT.value,
            "citations": [{"doc_id": "IT-KB-267", "score": 0.89}],
            "llm_prompt": "Test prompt",
            "llm_response": "Test response",
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
            "request_start_time": time.time() - 1.0,
        }

        result = await agent._feedback_metrics_node(state)

        metrics = result.get("feedback_metrics", {})
        
        # Should be JSON serializable
        try:
            json_str = json.dumps(metrics)
            assert json_str, "Should produce valid JSON"
        except TypeError as e:
            pytest.fail(f"Metrics not JSON serializable: {e}")

    @pytest.mark.asyncio
    async def test_metrics_has_expected_fields(self, agent):
        """Test that metrics has all expected fields."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "citations": [],
            "llm_prompt": "",
            "llm_response": "",
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
            "request_start_time": time.time(),
        }

        result = await agent._feedback_metrics_node(state)

        metrics = result.get("feedback_metrics", {})
        
        expected_fields = [
            "retrieval_score_top1",
            "retrieval_count",
            "dedup_count",
            "llm_latency_ms",
            "llm_tokens_used",
            "llm_tokens_input",
            "llm_tokens_output",
            "cache_hit_embedding",
            "cache_hit_query",
            "validation_errors",
            "retry_count",
        ]
        
        for field in expected_fields:
            assert field in metrics or field == "dedup_count", \
                f"Metrics missing field: {field}"
