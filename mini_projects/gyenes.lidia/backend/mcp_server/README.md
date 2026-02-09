# MCP Server - Quick Start

## What is MCP?

**MCP** (Model Context Protocol) is a standardized protocol for AI models to interact with external tools and data sources. Think of it as a bridge between LLMs and APIs.

## MCP Server Architecture

```
┌──────────────────┐
│ Client (LLM, CLI) │  ← Calls tools via MCP protocol
└────────┬─────────┘
         │
    MCP Protocol
    (stdio/HTTP/SSE)
         │
┌────────▼──────────────────────────────────────┐
│ MCP Server (this module)                       │
│                                               │
│  Exposed Tools:                               │
│  ✓ jira_create_ticket                         │
│  ✓ jira_search_issues                         │
│  ✓ qdrant_search                              │
│  ✓ qdrant_retrieve_by_ids                     │
│  ✓ postgres_get_feedback                      │
│  ✓ postgres_get_analytics                     │
│                                               │
└────────┬──────────────────────────────────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
┌───▼──┐ ┌───▼──┐ ┌──────▼─┐ ┌──────▼─────┐
│ Jira │ │Qdrant│ │Postgres│ │ PostgreSQL  │
│      │ │      │ │(Feedback)  │ (Analytics) │
└──────┘ └──────┘ └────────┘ └─────────────┘
```

## Installation

### 1. Install MCP SDK
```bash
pip install mcp
```

### 2. Verify structure
```bash
ls -la backend/mcp_server/
# __init__.py
# __main__.py
# server.py
# requirements.txt
# Dockerfile
# tools/
#   ├── __init__.py
#   ├── jira_tools.py
#   ├── qdrant_tools.py
#   └── postgres_tools.py
```

## Running the Server

### Option 1: Direct Python (Standalone)
```bash
cd backend
python -m mcp_server

# Output:
# 🚀 KnowledgeRouter MCP Server v0.1
# ==================================================
# 📋 Tools available: ['jira_create_ticket', 'jira_search_issues', ...]
# ==================================================
# 🎯 Starting server in stdio mode...
```

### Option 2: Via entrypoint script
```bash
cd backend/mcp_server
python __main__.py
```

### Option 3: Docker (future)
```bash
docker build -f backend/mcp_server/Dockerfile -t kr-mcp .
docker run -e DJANGO_SETTINGS_MODULE=core.settings \
           -e OPENAI_API_KEY=sk-... \
           kr-mcp
```

## Testing Tools

### 1. Check registered tools
```bash
python -c "
from mcp_server.server import MCPServer
import asyncio

async def test():
    server = MCPServer()
    for name, tool in server.tools_registry.items():
        print(f'✓ {tool.name}: {tool.description}')

asyncio.run(test())
"
```

### 2. List tools via MCP (with client)
```bash
# Install MCP CLI (optional)
pip install mcp-cli

# Connect to server and list tools
mcp-cli connect stdio -- python -m mcp_server
> list_tools
```

## Integration with Backend

Currently, the MCP server is **optional and standalone**. Future integration points:

### Phase 1 (Current - v0.1)
- MCP server runs independently
- Backend continues to work as-is
- No changes required to existing code

### Phase 2 (Future - HTTP Transport)
```python
# backend/services/agent.py (future)
async with MCPClient("http://localhost:5000") as client:
    result = await client.call_tool("jira_create_ticket", {
        "summary": "..." 
    })
```

### Phase 3 (LLM Tool Calling)
```python
# Agent can dynamically call tools
tools = await mcp_client.list_tools()
llm_with_tools = llm.bind_tools(tools)
# LLM decides which tool to call
```

## Tool Specifications

See [../../docs/MCP_SERVER.md](../../docs/MCP_SERVER.md) for detailed tool documentation.

### Quick Reference
- **Jira**: `jira_create_ticket`, `jira_search_issues`
- **Qdrant**: `qdrant_search`, `qdrant_retrieve_by_ids`
- **PostgreSQL**: `postgres_get_feedback`, `postgres_get_analytics`

## Non-invasive Design

✅ **Existing code: 0 changes**
- MCP server imports infrastructure clients (read-only)
- No modifications to backend API, services, or models
- Can be deployed independently
- Backend works fine without it

## Development

### Adding a New Tool

1. Create tool definition in relevant module (e.g., `tools/my_domain_tools.py`)
2. Define MCP Tool schema + async function
3. Register in `server.py` `_setup_tools()` method

```python
def my_new_tool() -> Tool:
    return Tool(
        name="my_new_tool",
        description="...",
        inputSchema={...}
    )

async def my_new_tool_impl(**kwargs):
    # Implementation
    pass
```

### Debugging

Set log level to DEBUG:
```python
logging.getLogger().setLevel(logging.DEBUG)
```

## Performance Notes

- **Latency**: MCP adds ~50-100ms overhead vs direct calls
- **Throughput**: Single process, but suitable for monitoring use case
- **Future**: Can be scaled with HTTP transport + multiple workers

## References

- [MCP Python SDK](https://github.com/anthropics/python-sdk-mcp)
- [MCP Spec](https://modelcontextprotocol.io)
- [KnowledgeRouter Documentation](../../docs/)

---

**Created**: 2026-01-15  
**Status**: Alpha (v0.1)  
**Next Steps**: HTTP transport, Grafana metrics
