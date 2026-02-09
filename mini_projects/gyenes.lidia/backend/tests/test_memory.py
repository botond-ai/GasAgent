import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from services.agent import QueryAgent


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
def mock_rag_dummy():
    rag = MagicMock()
    rag.retrieve_for_domain = AsyncMock(return_value=[])
    return rag


@pytest.mark.asyncio
async def test_memory_rolling_window_trim(mock_llm_memory, mock_rag_dummy):
    agent = QueryAgent(mock_llm_memory, mock_rag_dummy)
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
async def test_memory_summary_and_facts(mock_llm_memory, mock_rag_dummy):
    agent = QueryAgent(mock_llm_memory, mock_rag_dummy)
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
    agent = QueryAgent(bad_llm, mock_rag_dummy)
    state = {
        "messages": [HumanMessage(content="hello"), AIMessage(content="hi")],
        "query": "N/A",
    }
    new_state = await agent._memory_update_node(state)
    # Should still return state without raising
    assert new_state is not None
