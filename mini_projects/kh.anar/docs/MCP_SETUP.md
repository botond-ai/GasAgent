# MCP Server Integration Guide

This application integrates three MCP (Model Context Protocol) servers:
1. **Memory MCP** - Persistent conversation memory
2. **Brave Search MCP** - Web search capabilities
3. **Filesystem MCP** - Knowledge base file access

## Quick Start

### 1. Set up environment variables

Copy `.env.example` to `.env` and configure:

```bash
# MCP Server URLs (default for local development)
MCP_MEMORY_URL=http://localhost:3100
MCP_BRAVE_URL=http://localhost:3101
MCP_FILESYSTEM_URL=http://localhost:3102

# Brave Search API Key (required for web search)
BRAVE_API_KEY=your-brave-api-key-here
```

Get a Brave API key from: https://brave.com/search/api/

### 2. Start MCP Servers

Option A: Using Docker Compose (Recommended)
```bash
docker-compose -f docker-compose.mcp.yml up -d
```

Option B: Using npm/npx (if MCP servers are installed globally)
```bash
# Memory server
npx @modelcontextprotocol/server-memory --port 3100

# Brave Search server
BRAVE_API_KEY=your-key npx @modelcontextprotocol/server-brave-search --port 3101

# Filesystem server
npx @modelcontextprotocol/server-filesystem --port 3102 --allowed-paths ./docs,./data
```

### 3. Verify MCP servers are running

```bash
curl http://localhost:3100/health  # Memory
curl http://localhost:3101/health  # Brave
curl http://localhost:3102/health  # Filesystem
```

### 4. Start your application

The backend will automatically connect to MCP servers on startup.

```bash
docker-compose up --build
```

## Available MCP Tools

### Memory Tools
- `memory_store(conversation_id, key, value)` - Store a memory
- `memory_retrieve(conversation_id, key)` - Retrieve a memory
- `memory_list(conversation_id)` - List all memories
- `memory_delete(conversation_id, key)` - Delete a memory

### Brave Search Tools
- `brave_search(query, count=5)` - Web search
- `brave_local_search(query, count=3)` - Local/places search

### Filesystem Tools
- `filesystem_read(path)` - Read file content
- `filesystem_list(path)` - List directory
- `filesystem_search(path, pattern)` - Search files by pattern

## Architecture

```
┌─────────────────┐
│   Frontend      │
│   (React)       │
└────────┬────────┘
         │
┌────────▼────────┐      ┌──────────────┐
│   Backend       │─────▶│  Memory MCP  │
│   (FastAPI)     │      │  :3100       │
│                 │      └──────────────┘
│  ┌───────────┐  │      ┌──────────────┐
│  │  Agent    │  │─────▶│  Brave MCP   │
│  │(LangGraph)│  │      │  :3101       │
│  └───────────┘  │      └──────────────┘
│                 │      ┌──────────────┐
│                 │─────▶│Filesystem MCP│
└─────────────────┘      │  :3102       │
                         └──────────────┘
```

## Troubleshooting

### MCP servers not responding
- Check if containers are running: `docker ps`
- View logs: `docker-compose -f docker-compose.mcp.yml logs`
- Verify ports aren't in use: `lsof -i :3100 -i :3101 -i :3102`

### Brave Search not working
- Ensure `BRAVE_API_KEY` is set in `.env`
- Check API quota: https://brave.com/search/api/dashboard
- Test API key manually:
  ```bash
  curl -H "X-Subscription-Token: YOUR_KEY" \
    "https://api.search.brave.com/res/v1/web/search?q=test"
  ```

### Filesystem access denied
- Verify `ALLOWED_PATHS` in docker-compose.mcp.yml
- Check volume mounts are correct
- Ensure files exist in `./docs` and `./data`

## Development Notes

- MCP client: `backend/app/services/mcp_client.py`
- MCP tools: `backend/app/services/mcp_tools.py`
- Agent integration: Update `backend/app/services/agent.py` to include MCP tools

## Production Considerations

1. **Security**: 
   - Use authentication for MCP servers
   - Restrict filesystem paths
   - Rate-limit API calls

2. **Performance**:
   - Cache frequent memory lookups
   - Implement connection pooling
   - Monitor MCP server health

3. **Scaling**:
   - Run MCP servers on separate hosts
   - Use load balancer for multiple instances
   - Implement circuit breakers for resilience
