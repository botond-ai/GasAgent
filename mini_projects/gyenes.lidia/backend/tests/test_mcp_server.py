import importlib
import sys
import types

import pytest


@pytest.fixture
def fake_mcp(monkeypatch):
    """Provide lightweight MCP stubs so imports do not require real SDK."""
    mcp_module = types.ModuleType("mcp")
    mcp_server_module = types.ModuleType("mcp.server")
    mcp_types_module = types.ModuleType("mcp.types")

    class Tool:  # minimal container used by tool factories
        def __init__(self, name: str, description: str = "", inputSchema: dict | None = None):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema or {}

    class TextContent:
        def __init__(self, type: str, text: str):
            self.type = type
            self.text = text

    class ToolResult:
        def __init__(self, isError: bool, content):
            self.isError = isError
            self.content = content

    class Server:
        def __init__(self, name: str):
            self.name = name
            self.list_tools_handler = None
            self.call_tool_handler = None

        def list_tools(self):
            def decorator(fn):
                self.list_tools_handler = fn
                return fn

            return decorator

        def call_tool(self):
            def decorator(fn):
                self.call_tool_handler = fn
                return fn

            return decorator

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def run(self):
            return None

    mcp_server_module.Server = Server
    mcp_server_module.Request = None
    mcp_types_module.Tool = Tool
    mcp_types_module.TextContent = TextContent
    mcp_types_module.ToolResult = ToolResult
    mcp_module.server = mcp_server_module
    mcp_module.types = mcp_types_module

    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.server", mcp_server_module)
    monkeypatch.setitem(sys.modules, "mcp.types", mcp_types_module)

    yield

    for mod in ["mcp", "mcp.server", "mcp.types"]:
        sys.modules.pop(mod, None)


@pytest.mark.asyncio
async def test_mcp_server_lists_and_calls_tools(monkeypatch, fake_mcp):
    # Reload tool modules so they bind to the stubbed MCP types.
    from mcp_server import tools

    importlib.reload(tools.jira_tools)
    importlib.reload(tools.qdrant_tools)
    importlib.reload(tools.postgres_tools)
    importlib.reload(tools)

    async def fake_create_ticket(**kwargs):
        return {"success": True, "ticket_key": "SCRUM-1", "kwargs": kwargs}

    async def fake_search_issues(**kwargs):
        return {"success": True, "issues": []}

    async def fake_qdrant_search(**kwargs):
        return {"success": True, "citations": [], "total": 0}

    async def fake_qdrant_retrieve_by_ids(**kwargs):
        return {"success": True, "points": [], "total": 0}

    async def fake_get_feedback(**kwargs):
        return {"success": True, "feedback": {}, "total": 0}

    async def fake_get_analytics(**kwargs):
        return {"success": True, "metric": kwargs.get("metric", "query_count"), "data": {}, "time_range_hours": kwargs.get("time_range_hours", 24)}

    monkeypatch.setattr(tools.jira_tools, "create_ticket", fake_create_ticket)
    monkeypatch.setattr(tools.jira_tools, "search_issues", fake_search_issues)
    monkeypatch.setattr(tools.qdrant_tools, "search", fake_qdrant_search)
    monkeypatch.setattr(tools.qdrant_tools, "retrieve_by_ids", fake_qdrant_retrieve_by_ids)
    monkeypatch.setattr(tools.postgres_tools, "get_feedback", fake_get_feedback)
    monkeypatch.setattr(tools.postgres_tools, "get_analytics", fake_get_analytics)

    from mcp_server import server as server_module

    importlib.reload(server_module)

    mcp_server = server_module.MCPServer(name="test-mcp")

    available_tools = await mcp_server.server.list_tools_handler()
    tool_names = {tool.name for tool in available_tools}

    assert tool_names == {
        "jira_create_ticket",
        "jira_search_issues",
        "qdrant_search",
        "qdrant_retrieve_by_ids",
        "postgres_get_feedback",
        "postgres_get_analytics",
    }

    call_result = await mcp_server.server.call_tool_handler(
        "jira_create_ticket", {"summary": "s", "description": "d"}
    )

    assert call_result.isError is False
    assert call_result.content
    assert "SCRUM-1" in call_result.content[0].text

    missing_result = await mcp_server.server.call_tool_handler("missing_tool", {})
    assert missing_result.isError is True
    assert "not found" in missing_result.content[0].text
