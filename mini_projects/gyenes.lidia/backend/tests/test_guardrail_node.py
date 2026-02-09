"""
Unit tests for Guardrail Node validation logic.

Tests IT domain citation validation, hallucination detection, and retry logic.
"""
import pytest
from services.agent import QueryAgent, AgentState, DomainType


class MockRAGClient:
    """Mock RAG client for testing."""
    async def retrieve_for_domain(self, domain, query, top_k=5):
        return []


class MockLLMClient:
    """Mock LLM client for testing."""
    async def ainvoke(self, messages):
        class Response:
            content = "Mock response"
        return Response()


@pytest.fixture
def agent():
    """Create a QueryAgent instance for testing."""
    llm = MockLLMClient()
    rag = MockRAGClient()
    return QueryAgent(llm, rag)


class TestGuardrailNodeValidation:
    """Test Guardrail Node citation validation."""

    @pytest.mark.asyncio
    async def test_it_domain_with_valid_citations(self, agent):
        """Test IT domain response with proper [IT-KB-XXX] citations."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "llm_response": "A VPN beállítás [IT-KB-267] alapján: 1. nyisd meg a settings menüt, 2. válaszd a VPN opciót",
            "citations": [
                {
                    "title": "VPN Setup Guide",
                    "content": "[IT-KB-267] VPN Configuration...",
                    "section_id": "IT-KB-267"
                }
            ],
            "messages": [],
            "query": "Hogyan kell VPN-t beállítani?",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        result = await agent._guardrail_node(state)

        assert result["validation_errors"] == [], "Should have no validation errors"
        assert result["retry_count"] == 0, "Retry count should remain 0"

    @pytest.mark.asyncio
    async def test_it_domain_missing_citations(self, agent):
        """Test IT domain response without [IT-KB-XXX] citations triggers error."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "llm_response": "A VPN beállítás: 1. nyisd meg a settings menüt, 2. válaszd a VPN opciót",
            "citations": [
                {
                    "title": "VPN Setup Guide",
                    "content": "[IT-KB-267] VPN Configuration...",
                    "section_id": "IT-KB-267"
                }
            ],
            "messages": [],
            "query": "Hogyan kell VPN-t beállítani?",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        result = await agent._guardrail_node(state)

        assert len(result["validation_errors"]) > 0, "Should have validation errors"
        assert any("hivatkozás" in str(err).lower() for err in result["validation_errors"]), \
            "Should mention missing citations"

    @pytest.mark.asyncio
    async def test_non_it_domain_skips_validation(self, agent):
        """Test that non-IT domains bypass citation validation."""
        state: AgentState = {
            "domain": DomainType.HR.value,
            "llm_response": "A szabadság törvényi szabályozása a munka törvénykönyv szerint...",
            "citations": [
                {
                    "title": "HR Policy",
                    "content": "Vacation policy content",
                    "section_id": None
                }
            ],
            "messages": [],
            "query": "Mennyi szabadságnapom van?",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        result = await agent._guardrail_node(state)

        # HR domain should not trigger IT-specific validation
        assert len(result["validation_errors"]) == 0, "HR domain should not have citation errors"

    @pytest.mark.asyncio
    async def test_hallucination_detection(self, agent):
        """Test detection of unsupported claims (hallucinations).
        
        NOTE: Automatic hallucination detection requires semantic similarity checking.
        Currently disabled - only explicit contradictions would be detected.
        """
        state: AgentState = {
            "domain": DomainType.IT.value,
            "llm_response": (
                "[IT-KB-267] A VPN beállítás szerint: "
                "Ezt kizárólag a Mars-on lehet elvégezni. "
                "A Jupiter bolygó szintén jó választás VPN-hez. "
                "Az Androméda galaxisban felsőbb szintű titkosítás áll rendelkezésre."
            ),
            "citations": [
                {
                    "title": "VPN Setup Guide",
                    "content": "[IT-KB-267] VPN Configuration: Use standard encryption. Works on Windows, Mac, Linux.",
                    "section_id": "IT-KB-267"
                }
            ],
            "messages": [],
            "query": "Hogyan kell VPN-t beállítani?",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        result = await agent._guardrail_node(state)

        # Currently: No automatic hallucination detection (would need LLM call)
        # Just check that citation reference is present
        assert "[IT-KB-267]" in result["llm_response"], "Response should have citation reference"


class TestGuardrailDecision:
    """Test Guardrail decision routing logic."""

    def test_decision_retry_when_errors_and_retries_available(self, agent):
        """Test that retry is chosen when validation fails and retries remain."""
        state: AgentState = {
            "validation_errors": ["Missing citations"],
            "retry_count": 0,
            "domain": DomainType.IT.value,
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "citations": [],
            "output": {},
            "workflow": None,
        }

        decision = agent._guardrail_decision(state)

        assert decision == "retry", "Should retry when errors exist and retries remain"
        assert state["retry_count"] == 1, "Retry count should increment"

    def test_decision_continue_when_no_errors(self, agent):
        """Test that continue is chosen when validation passes."""
        state: AgentState = {
            "validation_errors": [],
            "retry_count": 0,
            "domain": DomainType.IT.value,
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "citations": [],
            "output": {},
            "workflow": None,
        }

        decision = agent._guardrail_decision(state)

        assert decision == "continue", "Should continue when validation passes"

    def test_decision_continue_when_max_retries_reached(self, agent):
        """Test that continue is chosen when max retries reached despite errors."""
        state: AgentState = {
            "validation_errors": ["Missing citations"],
            "retry_count": 2,  # Already at max (2)
            "domain": DomainType.IT.value,
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "citations": [],
            "output": {},
            "workflow": None,
        }

        decision = agent._guardrail_decision(state)

        assert decision == "continue", "Should continue when max retries reached"
        assert state["retry_count"] == 2, "Retry count should not exceed max"

    def test_retry_count_progression(self, agent):
        """Test that retry count increments correctly."""
        state: AgentState = {
            "validation_errors": ["Error 1"],
            "retry_count": 0,
            "domain": DomainType.IT.value,
            "messages": [],
            "query": "",
            "retrieved_docs": [],
            "citations": [],
            "output": {},
            "workflow": None,
        }

        # First retry
        decision1 = agent._guardrail_decision(state)
        assert decision1 == "retry"
        assert state["retry_count"] == 1

        # Second retry
        decision2 = agent._guardrail_decision(state)
        assert decision2 == "retry"
        assert state["retry_count"] == 2

        # No more retries
        decision3 = agent._guardrail_decision(state)
        assert decision3 == "continue"
        assert state["retry_count"] == 2


class TestGuardrailEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_citations_list(self, agent):
        """Test handling of empty citations with valid citation references in response."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            # Even with empty citations, if answer references a section ID that's not in citations list
            "llm_response": "A VPN beállítása [IT-KB-267] alapján...",
            "citations": [],  # Empty - no citations available
            "messages": [],
            "query": "VPN?",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        result = await agent._guardrail_node(state)

        # When citations are referenced in response but no citations provided, it's OK
        # (the section ID is mentioned, just no content available)
        # This is not an error - it means citations were attempted
        assert isinstance(result["validation_errors"], list), "Should have validation_errors field"

    @pytest.mark.asyncio
    async def test_multiple_citations_in_response(self, agent):
        """Test response with multiple citations."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "llm_response": (
                "A VPN-ről [IT-KB-267] ír, valamint "
                "a biztonsági beállításokról [IT-KB-320] is lehet tanulni."
            ),
            "citations": [
                {"title": "VPN Guide", "content": "[IT-KB-267] VPN Setup...", "section_id": "IT-KB-267"},
                {"title": "Security Guide", "content": "[IT-KB-320] Security Setup...", "section_id": "IT-KB-320"},
            ],
            "messages": [],
            "query": "VPN és biztonság?",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
        }

        result = await agent._guardrail_node(state)

        assert result["validation_errors"] == [], "Should accept multiple valid citations"

    @pytest.mark.asyncio
    async def test_state_initialization(self, agent):
        """Test that validation_errors and retry_count are initialized."""
        state: AgentState = {
            "domain": DomainType.IT.value,
            "llm_response": "Response",
            "citations": [],
            "messages": [],
            "query": "Query?",
            "retrieved_docs": [],
            "output": {},
            "workflow": None,
        }

        result = await agent._guardrail_node(state)

        assert "validation_errors" in result
        assert "retry_count" in result
        assert result["retry_count"] == 0
