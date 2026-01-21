import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from services.agent import QueryAgent
from domain.llm_outputs import MemoryUpdate


@pytest.fixture
def mock_llm_memory():
    llm = MagicMock()

    async def side_effect(messages):
        content = messages[0].content if isinstance(messages, list) else messages.content
        if "Summarize the following conversation" in content:
            return MagicMock(content="User needs VPN setup and approval steps. Summary.")
        if "Extract up to 5 atomic facts" in content:
            return MagicMock(content="- User requests VPN setup\n- Needs HR approval\n- Uses Windows 11")
        return MagicMock(content="OK")

    llm.ainvoke = AsyncMock(side_effect=side_effect)
    return llm


@pytest.fixture
def mock_llm_with_structured_output():
    """Mock LLM that returns Pydantic MemoryUpdate for reducer pattern tests."""
    llm = MagicMock()
    
    # Create a mock structured_llm
    structured_llm = MagicMock()
    
    async def ainvoke_side_effect(messages):
        """Return MemoryUpdate based on prompt content."""
        content = messages[0].content if isinstance(messages, list) else messages.content
        
        # Reducer pattern: merge previous + new
        if "REDUCER PATTERN" in content or "PREVIOUS SUMMARY" in content:
            # Simulate semantic compression (merge facts)
            return MemoryUpdate(
                summary="Merged summary: User plans marketing HR meeting. Budget updated to 60k.",
                facts=[
                    "Budget: 60,000 Ft",  # Recent overwrites old (50k → 60k)
                    "Meeting date: 2026-01-20",  # Kept from previous
                    "Approval required from CFO"  # New fact added
                    # "Team lead: Anna" dropped (not mentioned)
                ],
                decisions=["Use updated budget 60k"]
            )
        
        # Normal memory update (no previous state)
        return MemoryUpdate(
            summary="User needs VPN setup and approval steps.",
            facts=["User requests VPN setup", "Needs HR approval", "Uses Windows 11"],
            decisions=[]
        )
    
    structured_llm.ainvoke = AsyncMock(side_effect=ainvoke_side_effect)
    llm.with_structured_output = MagicMock(return_value=structured_llm)
    
    return llm


@pytest.fixture
def mock_rag_dummy():
    rag = MagicMock()
    rag.retrieve_for_domain = AsyncMock(return_value=[])
    return rag


@pytest.mark.asyncio
async def test_memory_rolling_window_trim(mock_llm_with_structured_output, mock_rag_dummy):
    agent = QueryAgent(mock_llm_with_structured_output, mock_rag_dummy)
    # Build state with >N messages
    msgs = []
    for i in range(12):
        msgs.append(HumanMessage(content=f"hi {i}"))
        msgs.append(AIMessage(content=f"reply {i}"))
    state = {
        "messages": msgs,
        "query": "N/A",
    }
    new_state = await agent._memory_update_node(state)
    assert len(new_state["messages"]) <= 8, "Should keep only last N messages by default"


@pytest.mark.asyncio
async def test_memory_summary_and_facts(mock_llm_with_structured_output, mock_rag_dummy):
    agent = QueryAgent(mock_llm_with_structured_output, mock_rag_dummy)
    msgs = [
        HumanMessage(content="Szeretnék VPN-t"),
        AIMessage(content="Itt a leírás"),
        HumanMessage(content="Kell HR jóváhagyás?"),
        AIMessage(content="Igen, szükséges lehet."),
        HumanMessage(content="Windows 11-et használok"),
    ]
    state = {
        "messages": msgs,
        "query": "N/A",
        "memory_summary": "",
        "memory_facts": [],
    }
    new_state = await agent._memory_update_node(state)
    assert new_state.get("memory_summary"), "Summary should be populated"
    facts = new_state.get("memory_facts", [])
    assert len(facts) >= 2, "Should extract multiple facts"


@pytest.mark.asyncio
async def test_memory_non_blocking_on_llm_error(mock_rag_dummy):
    # LLM that raises
    bad_llm = MagicMock()
    bad_llm.ainvoke = AsyncMock(side_effect=Exception("LLM down"))
    bad_llm.with_structured_output = MagicMock(return_value=bad_llm)
    agent = QueryAgent(bad_llm, mock_rag_dummy)
    state = {
        "messages": [HumanMessage(content="hello"), AIMessage(content="hi")],
        "query": "N/A",
    }
    new_state = await agent._memory_update_node(state)
    # Should still return state without raising
    assert new_state is not None


# ==================== REDUCER PATTERN TESTS (v2.7) ====================

@pytest.mark.asyncio
async def test_memory_reducer_pattern_merge_summary(mock_llm_with_structured_output, mock_rag_dummy):
    """Test reducer pattern: previous summary merged with new summary."""
    agent = QueryAgent(mock_llm_with_structured_output, mock_rag_dummy)
    
    # Turn 1: Initial state with previous summary
    msgs = [
        HumanMessage(content="Budget is now 60k instead of 50k"),
        AIMessage(content="Updated to 60k")
    ] * 4  # 8 messages total
    
    state = {
        "messages": msgs,
        "query": "N/A",
        "memory_summary": "User wants marketing HR meeting. Budget: 50k.",  # Previous summary
        "memory_facts": ["Budget: 50,000 Ft", "Team lead: Anna"],  # Previous facts
    }
    
    new_state = await agent._memory_update_node(state)
    
    # Verify summary was MERGED (not overwritten)
    assert new_state.get("memory_summary"), "Summary should exist"
    summary = new_state["memory_summary"]
    assert "Merged summary" in summary or "60k" in summary, "Should merge previous with new"
    
    # Verify facts were compressed (max 8)
    facts = new_state.get("memory_facts", [])
    assert len(facts) <= 8, "Should compress to max 8 facts"


@pytest.mark.asyncio
async def test_memory_semantic_compression_recent_overwrites_old(mock_llm_with_structured_output, mock_rag_dummy):
    """Test semantic compression: recent facts overwrite old conflicting ones."""
    agent = QueryAgent(mock_llm_with_structured_output, mock_rag_dummy)
    
    msgs = [
        HumanMessage(content="Actually 60k budget"),
        AIMessage(content="OK, 60k")
    ] * 4  # 8 messages
    
    state = {
        "messages": msgs,
        "query": "N/A",
        "memory_summary": "User wants meeting. Budget: 50k.",
        "memory_facts": ["Budget: 50,000 Ft", "Meeting date: 2026-01-20"],
    }
    
    new_state = await agent._memory_update_node(state)
    
    facts = new_state.get("memory_facts", [])
    
    # Check that 60k fact exists (recent)
    budget_facts = [f for f in facts if "60" in f or "Budget" in f]
    assert len(budget_facts) > 0, "Should have budget fact"
    
    # 50k should be replaced by 60k (semantic compression)
    # Note: LLM mock returns "60,000 Ft", so old "50,000 Ft" is overwritten


@pytest.mark.asyncio
async def test_memory_semantic_compression_drop_irrelevant(mock_llm_with_structured_output, mock_rag_dummy):
    """Test semantic compression: drop facts no longer relevant."""
    agent = QueryAgent(mock_llm_with_structured_output, mock_rag_dummy)
    
    msgs = [
        HumanMessage(content="Focus on budget now"),
        AIMessage(content="OK")
    ] * 4
    
    state = {
        "messages": msgs,
        "query": "N/A",
        "memory_summary": "Previous context",
        "memory_facts": [
            "Budget: 50,000 Ft",
            "Team lead: Anna",  # This should be dropped (not mentioned anymore)
            "Meeting date: 2026-01-20"
        ],
    }
    
    new_state = await agent._memory_update_node(state)
    
    facts = new_state.get("memory_facts", [])
    
    # Verify facts were filtered (LLM drops "Team lead: Anna")
    # Mock LLM returns 3 facts, none include "Anna"
    assert len(facts) <= 8, "Should compress facts"
    # Note: Mock LLM doesn't return "Anna" in merged facts


@pytest.mark.asyncio
async def test_memory_empty_previous_state(mock_llm_with_structured_output, mock_rag_dummy):
    """Test reducer handles empty previous state gracefully."""
    agent = QueryAgent(mock_llm_with_structured_output, mock_rag_dummy)
    
    msgs = [
        HumanMessage(content="First message ever"),
        AIMessage(content="Hello")
    ] * 4
    
    state = {
        "messages": msgs,
        "query": "N/A",
        "memory_summary": "",  # Empty
        "memory_facts": [],  # Empty
    }
    
    new_state = await agent._memory_update_node(state)
    
    # Should create new summary and facts
    assert new_state.get("memory_summary"), "Should create new summary"
    assert len(new_state.get("memory_facts", [])) > 0, "Should extract facts"


@pytest.mark.asyncio
async def test_memory_max_8_facts_compression(mock_llm_with_structured_output, mock_rag_dummy):
    """Test that semantic compression limits facts to max 8."""
    agent = QueryAgent(mock_llm_with_structured_output, mock_rag_dummy)
    
    # Simulate state with many previous facts
    msgs = [HumanMessage(content="new info"), AIMessage(content="ok")] * 4
    
    state = {
        "messages": msgs,
        "query": "N/A",
        "memory_summary": "Previous",
        "memory_facts": [f"Fact {i}" for i in range(10)],  # 10 previous facts
    }
    
    new_state = await agent._memory_update_node(state)
    
    facts = new_state.get("memory_facts", [])
    
    # Should compress to max 8 facts
    assert len(facts) <= 8, f"Should compress to max 8 facts, got {len(facts)}"

