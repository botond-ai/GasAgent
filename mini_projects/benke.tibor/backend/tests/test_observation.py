import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage

from services.agent import QueryAgent
from infrastructure.tool_registry import ToolRegistry
from domain.llm_outputs import ObservationOutput


class DummyLLM:
    """Dummy LLM for testing with configurable responses."""
    
    def __init__(self, observation_response=None):
        self.observation_response = observation_response or ObservationOutput(
            sufficient=True,
            next_action="generate",
            gaps=[],
            reasoning="Mock observation: sufficient info",
            tool_results_count=0,
            retrieval_count=0
        )
    
    def with_structured_output(self, model):
        """Return self to enable chaining."""
        return self
    
    async def ainvoke(self, *_args, **_kwargs):
        """Return the configured observation response."""
        return self.observation_response


@pytest.mark.asyncio
async def test_observation_sets_counts():
    """Test basic observation count tracking (backward compatibility)."""
    llm = DummyLLM()
    agent = QueryAgent(llm, rag_client=None, tool_registry=ToolRegistry.default())

    state = {
        "query": "Test query",
        "execution_plan": {},
        "workflow": {"tool_results": [
            {"tool_name": "calculator", "status": "success"},
            {"tool_name": "email_send", "status": "success"},
        ]},
        "retrieved_docs": [1, 2, 3]
    }

    new_state = await agent._observation_node(state)
    obs = new_state.get("observation", {})
    
    assert obs.get("sufficient") is True
    assert obs.get("tool_results_count") == 2
    assert obs.get("retrieval_count") == 3


@pytest.mark.asyncio
async def test_observation_sufficient_generates():
    """Test observation with sufficient info routes to generate."""
    llm = DummyLLM(
        observation_response=ObservationOutput(
            sufficient=True,
            next_action="generate",
            gaps=[],
            reasoning="All necessary info available",
            tool_results_count=2,
            retrieval_count=5
        )
    )
    agent = QueryAgent(llm, rag_client=None, tool_registry=ToolRegistry.default())

    state = {
        "query": "What is the VPN setup?",
        "execution_plan": {"reasoning": "Search IT docs"},
        "workflow": {"tool_results": [
            {"tool_name": "rag_search", "status": "success", "result": {"hits": 5}}
        ]},
        "retrieved_docs": [1, 2, 3, 4, 5],
        "replan_count": 0
    }

    new_state = await agent._observation_node(state)
    obs = new_state.get("observation", {})
    
    assert obs["sufficient"] is True
    assert obs["next_action"] == "generate"
    assert len(obs["gaps"]) == 0
    
    # Test routing decision
    decision = agent._observation_decision(new_state)
    assert decision == "generate"


@pytest.mark.asyncio
async def test_observation_insufficient_replans():
    """Test observation with insufficient info routes to replan."""
    llm = DummyLLM(
        observation_response=ObservationOutput(
            sufficient=False,
            next_action="replan",
            gaps=["Missing VPN credentials", "No server info"],
            reasoning="Critical info missing from tools",
            tool_results_count=1,
            retrieval_count=0
        )
    )
    agent = QueryAgent(llm, rag_client=None, tool_registry=ToolRegistry.default())

    state = {
        "query": "How do I setup VPN?",
        "execution_plan": {"reasoning": "Search for VPN"},
        "workflow": {"tool_results": [
            {"tool_name": "rag_search", "status": "error", "error": "Timeout"}
        ]},
        "retrieved_docs": [],
        "replan_count": 0
    }

    new_state = await agent._observation_node(state)
    obs = new_state.get("observation", {})
    
    assert obs["sufficient"] is False
    assert obs["next_action"] == "replan"
    assert len(obs["gaps"]) == 2
    assert "VPN credentials" in obs["gaps"][0]
    
    # Test routing decision
    decision = agent._observation_decision(new_state)
    assert decision == "replan"
    assert new_state["replan_count"] == 1


@pytest.mark.asyncio
async def test_observation_max_replan_limit():
    """Test max replan limit (2) enforces generate."""
    llm = DummyLLM(
        observation_response=ObservationOutput(
            sufficient=False,
            next_action="replan",
            gaps=["Still missing info"],
            reasoning="Still insufficient",
            tool_results_count=0,
            retrieval_count=0
        )
    )
    agent = QueryAgent(llm, rag_client=None, tool_registry=ToolRegistry.default())

    state = {
        "query": "Complex query",
        "execution_plan": {},
        "workflow": {"tool_results": []},
        "retrieved_docs": [],
        "observation": {
            "sufficient": False,
            "next_action": "replan",
            "gaps": ["Missing info"],
            "reasoning": "Insufficient"
        },
        "replan_count": 2  # Already hit max
    }

    # Test routing decision - should force generate despite insufficient
    decision = agent._observation_decision(state)
    assert decision == "generate"
    assert state["replan_count"] == 2  # Not incremented


@pytest.mark.asyncio
async def test_observation_gap_detection():
    """Test observation correctly identifies and lists gaps."""
    llm = DummyLLM(
        observation_response=ObservationOutput(
            sufficient=False,
            next_action="replan",
            gaps=[
                "Missing user email address",
                "No ticket priority specified",
                "Subject line unclear"
            ],
            reasoning="Multiple critical fields missing for Jira ticket",
            tool_results_count=1,
            retrieval_count=0
        )
    )
    agent = QueryAgent(llm, rag_client=None, tool_registry=ToolRegistry.default())

    state = {
        "query": "Create a ticket",
        "execution_plan": {"reasoning": "Create Jira ticket"},
        "workflow": {"tool_results": [
            {"tool_name": "jira_create", "status": "error", "error": "Missing fields"}
        ]},
        "retrieved_docs": [],
        "replan_count": 0
    }

    new_state = await agent._observation_node(state)
    obs = new_state.get("observation", {})
    
    assert obs["sufficient"] is False
    assert len(obs["gaps"]) == 3
    assert "email" in obs["gaps"][0].lower()
    assert "priority" in obs["gaps"][1].lower()
    assert "subject" in obs["gaps"][2].lower()


@pytest.mark.asyncio
async def test_observation_error_fallback():
    """Test observation fallback when LLM fails."""
    
    class FailingLLM:
        def with_structured_output(self, model):
            return self
        
        async def ainvoke(self, *args, **kwargs):
            raise ValueError("LLM failed")
    
    agent = QueryAgent(FailingLLM(), rag_client=None, tool_registry=ToolRegistry.default())

    state = {
        "query": "Test",
        "execution_plan": {},
        "workflow": {"tool_results": [{"tool_name": "test", "status": "success"}]},
        "retrieved_docs": [1, 2]
    }

    new_state = await agent._observation_node(state)
    obs = new_state.get("observation", {})
    
    # Should fallback to safe defaults
    assert obs["sufficient"] is True
    assert obs["next_action"] == "generate"
    assert "failed" in obs["reasoning"].lower()
    assert obs["tool_results_count"] == 1
    assert obs["retrieval_count"] == 2
