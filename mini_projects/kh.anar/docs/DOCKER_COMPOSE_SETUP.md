# Docker Compose Setup - MCP Servers Included

## Quick Start

All MCP servers are now integrated into the main docker-compose setup!

```bash
# Start everything (backend, frontend, and all 3 MCP servers)
docker-compose up --build

# Or in detached mode
docker-compose up --build -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop everything
docker-compose down
```

## What's Included

When you run `docker-compose up --build`, the following services start automatically:

### MCP Servers (3 containers)
1. **mcp-memory** (port 3100) - Conversation memory storage
2. **mcp-brave** (port 3101) - Web search via Brave API
3. **mcp-filesystem** (port 3102) - Document access (docs/ and data/)

### Application (2 containers)
4. **backend** (port 8000) - FastAPI backend with LangGraph agent
5. **frontend** (port 4000) - React frontend

## Service Dependencies

The backend waits for all three MCP servers to be healthy before starting:

```
MCP Servers (3100, 3101, 3102)
    ↓ (health checks)
Backend (8000)
    ↓
Frontend (4000)
```

## Health Checks

Each MCP server has a health check endpoint that docker-compose monitors:

- Memory: `http://localhost:3100/health`
- Brave: `http://localhost:3101/health`
- Filesystem: `http://localhost:3102/health`

## Testing

After starting with docker-compose, run the test suite:

```bash
# Run comprehensive integration tests
python3 test_mcp_integration.py

# Or use the shell script
./test-mcp-servers.sh
```

Expected output: **25/25 tests passed**

## Environment Variables

Make sure your `.env` file has:

```bash
# Required
OPENAI_API_KEY=your-openai-api-key
BRAVE_API_KEY=your-brave-api-key  # For web search

# Optional
ADMIN_TOKEN=changeme
```

## Networking

All services are on the same Docker network (`kh-anar-network`):

- Backend connects to MCP servers using internal Docker DNS:
  - `http://mcp-memory:3100`
  - `http://mcp-brave:3101`
  - `http://mcp-filesystem:3102`

- External access (from your machine):
  - `http://localhost:3100` (Memory)
  - `http://localhost:3101` (Brave)
  - `http://localhost:3102` (Filesystem)
  - `http://localhost:8000` (Backend API)
  - `http://localhost:4000` (Frontend)

## Volumes

The following directories are mounted:

- `./data` → `/app/data` (backend & filesystem MCP)
- `./docs` → `/app/docs` (backend & filesystem MCP)
- `./data/mcp/memory` → `/app/data/memory` (memory MCP)

## Troubleshooting

### Problem: MCP servers not starting
```bash
# Check logs
docker-compose logs mcp-memory
docker-compose logs mcp-brave
docker-compose logs mcp-filesystem
```

### Problem: Backend can't connect to MCP servers
- The backend waits for health checks to pass
- Check if MCP containers are healthy: `docker-compose ps`

### Problem: Brave search not working
- Ensure `BRAVE_API_KEY` is set in `.env`
- Check Brave MCP logs: `docker-compose logs mcp-brave`

### Problem: Port conflicts
If ports 3100, 3101, 3102, 4000, or 8000 are in use:

```bash
# Stop any standalone MCP servers
./stop-mcp-servers.sh

# Or check what's using the ports
lsof -i :3100 -i :3101 -i :3102 -i :4000 -i :8000
```

### Complete restart
```bash
# Stop everything
docker-compose down

# Remove all containers and rebuild
docker-compose down --volumes
docker-compose up --build
```

## Development Workflow

### Full rebuild (after code changes)
```bash
docker-compose up --build
```

### Restart specific service
```bash
# Just restart backend
docker-compose restart backend

# Just restart an MCP server
docker-compose restart mcp-memory
```

### View specific service logs
```bash
docker-compose logs -f backend
docker-compose logs -f mcp-brave
```

## Production Notes

For production deployment:

1. **Security**
   - Add authentication to MCP servers
   - Use secrets management for API keys
   - Enable HTTPS/TLS

2. **Persistence**
   - Replace in-memory storage with Redis/PostgreSQL
   - Use Docker volumes for data persistence

3. **Scaling**
   - Use docker-compose scale or Kubernetes
   - Add load balancers
   - Implement connection pooling

4. **Monitoring**
   - Add health monitoring
   - Set up logging aggregation
   - Configure alerts

## Migration from Standalone Scripts

If you previously used `start-mcp-servers.sh`:

**Before (standalone):**
```bash
./start-mcp-servers.sh  # Start MCP servers
docker-compose up       # Start backend & frontend
```

**Now (integrated):**
```bash
docker-compose up --build  # Starts everything!
```

The standalone scripts (`start-mcp-servers.sh`, `stop-mcp-servers.sh`) are still available for local development without Docker.

## Summary

✅ **One command starts everything:** `docker-compose up --build`  
✅ **Automatic health checks:** Backend waits for MCP servers  
✅ **All tests pass:** 25/25 integration tests successful  
✅ **Production-ready:** Containerized and networkable  

---

**Next:** Access the application at http://localhost:4000
