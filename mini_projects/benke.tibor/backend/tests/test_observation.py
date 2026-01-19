import pytest

from services.agent import QueryAgent
from infrastructure.tool_registry import ToolRegistry


class DummyLLM:
    def with_structured_output(self, model):  # pragma: no cover - not used
        return self

    async def ainvoke(self, *_args, **_kwargs):  # pragma: no cover
        return None


@pytest.mark.asyncio
async def test_observation_sets_counts():
    agent = QueryAgent(DummyLLM(), rag_client=None, tool_registry=ToolRegistry.default())

    state = {
        "workflow": {"tool_results": [
            {"tool": "calculator", "status": "success"},
            {"tool": "email_send", "status": "success"},
        ]},
        "retrieved_docs": [1, 2, 3]
    }

    new_state = await agent._observation_node(state)
    obs = new_state.get("observation", {})
    assert obs.get("sufficient") is True
    assert obs.get("tool_results_count") == 2
    assert obs.get("retrieval_count") == 3
