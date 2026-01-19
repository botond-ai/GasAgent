import pytest

from services.agent import QueryAgent
from infrastructure.tool_registry import ToolRegistry


class DummyLLM:
    def with_structured_output(self, model):  # pragma: no cover - not used here
        return self

    async def ainvoke(self, *_args, **_kwargs):  # pragma: no cover
        return None


@pytest.mark.asyncio
async def test_tool_executor_runs_registered_tools_successfully():
    """Test successful tool execution with ToolResult validation."""
    registry = ToolRegistry.default()
    agent = QueryAgent(DummyLLM(), rag_client=None, tool_registry=registry)

    state = {
        "tool_selection": {
            "route": "tools_only",
            "selected_tools": [
                {"tool_name": "calculator", "arguments": {"expression": "2+2"}}
            ]
        },
        "workflow": {}
    }

    new_state = await agent._tool_executor_node(state)
    results = new_state.get("workflow", {}).get("tool_results", [])
    
    assert len(results) == 1
    result = results[0]
    assert result["status"] == "success"
    assert result["tool_name"] == "calculator"
    assert result["result"] is not None
    assert result["latency_ms"] >= 0
    assert result["retry_count"] == 0


@pytest.mark.asyncio
async def test_tool_executor_handles_missing_tool_name():
    """Test error handling when tool_name is missing."""
    registry = ToolRegistry.default()
    agent = QueryAgent(DummyLLM(), rag_client=None, tool_registry=registry)

    state = {
        "tool_selection": {
            "route": "tools_only",
            "selected_tools": [
                {"arguments": {"expression": "2+2"}}  # Missing tool_name
            ]
        },
        "workflow": {}
    }

    new_state = await agent._tool_executor_node(state)
    results = new_state.get("workflow", {}).get("tool_results", [])
    
    assert len(results) == 1
    result = results[0]
    assert result["status"] == "error"
    assert result["tool_name"] == "unknown"
    assert "Missing tool_name" in result["error"]
    assert result["latency_ms"] == 0.0


@pytest.mark.asyncio
async def test_tool_executor_handles_timeout():
    """Test timeout handling (10s limit)."""
    registry = ToolRegistry.default()
    
    # Register a mock tool that times out
    def slow_tool(**kwargs):
        import time
        time.sleep(15)  # Longer than 10s timeout
        return {"result": "never reached"}
    
    registry.register("slow_tool", slow_tool, "A slow tool", {})
    
    agent = QueryAgent(DummyLLM(), rag_client=None, tool_registry=registry)

    state = {
        "tool_selection": {
            "route": "tools_only",
            "selected_tools": [
                {"tool_name": "slow_tool", "arguments": {}}
            ]
        },
        "workflow": {}
    }

    new_state = await agent._tool_executor_node(state)
    results = new_state.get("workflow", {}).get("tool_results", [])
    
    assert len(results) == 1
    result = results[0]
    assert result["status"] == "timeout"
    assert result["tool_name"] == "slow_tool"
    assert "timeout" in result["error"].lower()
    assert result["retry_count"] == 0
    assert result["latency_ms"] > 0


@pytest.mark.asyncio
async def test_tool_executor_handles_multiple_tools():
    """Test execution of multiple tools sequentially."""
    registry = ToolRegistry.default()
    agent = QueryAgent(DummyLLM(), rag_client=None, tool_registry=registry)

    state = {
        "tool_selection": {
            "route": "rag_and_tools",
            "selected_tools": [
                {"tool_name": "calculator", "arguments": {"expression": "10+5"}},
                {"tool_name": "calculator", "arguments": {"expression": "20*3"}},
            ]
        },
        "workflow": {}
    }

    new_state = await agent._tool_executor_node(state)
    results = new_state.get("workflow", {}).get("tool_results", [])
    
    assert len(results) == 2
    assert all(r["status"] == "success" for r in results)
    assert all(r["tool_name"] == "calculator" for r in results)
    assert all(r["latency_ms"] >= 0 for r in results)


@pytest.mark.asyncio
async def test_tool_executor_handles_tool_error():
    """Test error handling when tool execution fails."""
    registry = ToolRegistry.default()
    
    # Register a mock tool that raises an error
    def error_tool(**kwargs):
        raise ValueError("Simulated tool error")
    
    registry.register("error_tool", error_tool, "A tool that errors", {})
    
    agent = QueryAgent(DummyLLM(), rag_client=None, tool_registry=registry)

    state = {
        "tool_selection": {
            "route": "tools_only",
            "selected_tools": [
                {"tool_name": "error_tool", "arguments": {}}
            ]
        },
        "workflow": {}
    }

    new_state = await agent._tool_executor_node(state)
    results = new_state.get("workflow", {}).get("tool_results", [])
    
    assert len(results) == 1
    result = results[0]
    assert result["status"] == "error"
    assert result["tool_name"] == "error_tool"
    assert "Simulated tool error" in result["error"]
    assert result["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_tool_executor_mixed_success_and_failure():
    """Test handling of mixed successful and failed tool executions."""
    registry = ToolRegistry.default()
    
    # Register an error tool
    def error_tool(**kwargs):
        raise ValueError("Error tool failed")
    
    registry.register("error_tool", error_tool, "Error tool", {})
    
    agent = QueryAgent(DummyLLM(), rag_client=None, tool_registry=registry)

    state = {
        "tool_selection": {
            "route": "tools_only",
            "selected_tools": [
                {"tool_name": "calculator", "arguments": {"expression": "5+5"}},
                {"tool_name": "error_tool", "arguments": {}},
                {"tool_name": "calculator", "arguments": {"expression": "10-3"}},
            ]
        },
        "workflow": {}
    }

    new_state = await agent._tool_executor_node(state)
    results = new_state.get("workflow", {}).get("tool_results", [])
    
    assert len(results) == 3
    assert results[0]["status"] == "success"
    assert results[1]["status"] == "error"
    assert results[2]["status"] == "success"
    
    # Verify non-blocking: all tools attempted despite middle failure
    success_count = sum(1 for r in results if r["status"] == "success")
    assert success_count == 2

