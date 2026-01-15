# MCP Server Module

**Status**: Alpha (v0.1) - Non-invasive skeleton

## Overview

Standalone MCP (Model Context Protocol) server that exposes KnowledgeRouter infrastructure operations as standardized tools.

**Key Design**: Zero modifications to existing backend code. The MCP server is a pure wrapper around existing infrastructure clients.

## Architecture

```
┌─────────────────────────────────────────┐
│ MCP Server (mcp_server/)                │
│ - Runs as separate Python process       │
│ - Or in separate container              │
│                                         │
│ Tools:                                  │
│  ├── Jira (create_ticket, search)      │
│  ├── Qdrant (search, retrieve)         │
│  └── PostgreSQL (feedback, analytics)  │
└────────────┬────────────────────────────┘
             │
      ┌──────┴──────────┐
      │                 │
   Backend         Other Clients
   (optional)      (CLI, frontend, etc.)
```

## Tools Available

### Jira Tools (`jira_tools.py`)
- **`jira_create_ticket`**: Create a new Jira ticket
  - Args: summary, description, issue_type, priority
  - Returns: {success, ticket_key, ticket_url}

- **`jira_search_issues`**: Search existing issues
  - Args: jql (Jira Query Language), limit
  - Returns: {issues: [...], total}

### Qdrant Tools (`qdrant_tools.py`)
- **`qdrant_search`**: Semantic search in knowledge base
  - Args: query, domain, top_k
  - Returns: {citations: [...], total}

- **`qdrant_retrieve_by_ids`**: Retrieve specific points
  - Args: ids (list of point IDs)
  - Returns: {points: [...], total}

### PostgreSQL Tools (`postgres_tools.py`)
- **`postgres_get_feedback`**: Get citation feedback scores
  - Args: citation_ids
  - Returns: {feedback: {id: score, ...}, total}

- **`postgres_get_analytics`**: Get usage analytics
  - Args: metric (query_count, domain_distribution, etc.), time_range_hours
  - Returns: {metric, data, time_range_hours}

## Running

### Standalone (stdio mode)
```bash
cd backend
python -m mcp_server.server
```

### Docker (future)
```bash
docker run -e DJANGO_SETTINGS_MODULE=core.settings \
  -e OPENAI_API_KEY=... \
  knowledgerouter-mcp
```

### With Backend (HTTP client)
```python
# backend/services/agent.py (future integration)
from mcp.client import ClientSession

async with ClientSession(transport) as client:
    result = await client.call_tool("jira_create_ticket", {
        "summary": "Bug report",
        "description": "..."
    })
```

## Requirements

```bash
pip install mcp  # MCP SDK (Python)
```

See [../requirements.txt](../requirements.txt) for other dependencies.

## Non-invasive Design

- ✅ Existing backend code: **0 changes required**
- ✅ MCP server imports infrastructure clients (read-only)
- ✅ Can be deployed separately
- ✅ Optional for backend - backend works without it
- ✅ Future: Backend can call MCP tools via HTTP or stdio

## Future Enhancements

### Phase 2 (v0.2)
- [ ] Add HTTP transport mode (socket.io or REST)
- [ ] Grafana metrics export
- [ ] Tool call tracing and logging

### Phase 3 (v0.3)
- [ ] LLM tool calling integration (agent can call tools dynamically)
- [ ] Rate limiting per tool
- [ ] Cache layer for read-heavy operations

### Phase 4 (v1.0)
- [ ] Full monitoring integration
- [ ] Kubernetes support
- [ ] OpenAI Functions schema export

## Testing

```bash
# Test tool availability
python -c "from mcp_server.server import MCPServer; \
           server = MCPServer(); \
           print(list(server.tools_registry.keys()))"

# Output:
# ['jira_create_ticket', 'jira_search_issues', 
#  'qdrant_search', 'qdrant_retrieve_by_ids',
#  'postgres_get_feedback', 'postgres_get_analytics']
```

---

**Created**: 2026-01-15  
**Version**: 0.1 (Alpha)  
**Maintainer**: KnowledgeRouter Team
