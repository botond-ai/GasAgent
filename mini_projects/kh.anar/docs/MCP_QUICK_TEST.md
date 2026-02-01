# MCP Servers - Quick Start & Testing Guide

## Quick Start (2 commands)

```bash
# 1. Start all MCP servers
./start-mcp-servers.sh

# 2. Run all tests
python3 test_mcp_integration.py
```

## What Gets Started

Three HTTP-based MCP servers:
- **Memory MCP** (port 3100) - Conversation memory storage
- **Brave Search MCP** (port 3101) - Web search integration
- **Filesystem MCP** (port 3102) - Document access

## Verify Everything is Working

### Quick Health Check
```bash
curl http://localhost:3100/health  # Memory
curl http://localhost:3101/health  # Brave
curl http://localhost:3102/health  # Filesystem
```

### See Available Tools
```bash
curl http://localhost:3100/tools | python3 -m json.tool
curl http://localhost:3101/tools | python3 -m json.tool
curl http://localhost:3102/tools | python3 -m json.tool
```

### Test a Memory Operation
```bash
# Store
curl -X POST http://localhost:3100/tools/store \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test","key":"name","value":"Alice"}' | python3 -m json.tool

# Retrieve
curl -X POST http://localhost:3100/tools/retrieve \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test","key":"name"}' | python3 -m json.tool
```

### Test Brave Search
```bash
curl -X POST http://localhost:3101/tools/search \
  -H "Content-Type: application/json" \
  -d '{"query":"OpenAI","count":3}' | python3 -m json.tool
```

### Test Filesystem
```bash
# List directory
curl -X POST http://localhost:3102/tools/list_directory \
  -H "Content-Type: application/json" \
  -d '{"path":"docs"}' | python3 -m json.tool

# Read file
curl -X POST http://localhost:3102/tools/read_file \
  -H "Content-Type: application/json" \
  -d '{"path":"docs/MCP_SETUP.md"}' | python3 -m json.tool
```

## Run Comprehensive Tests

### Python Test Suite (Recommended)
```bash
python3 test_mcp_integration.py
```

**Tests 25 scenarios:**
- Server health (3 tests)
- Tool discovery (3 tests)
- Memory operations (6 tests)
- Brave search (3 tests)
- Filesystem operations (6 tests)
- Multi-step workflows (4 tests)

### Shell Test Script
```bash
./test-mcp-servers.sh
```

## Stop Servers

```bash
./stop-mcp-servers.sh
```

## Troubleshooting

### Servers won't start
```bash
# Check if ports are in use
lsof -i :3100 -i :3101 -i :3102

# Kill any processes using the ports
./stop-mcp-servers.sh
```

### Check server logs
```bash
tail -f logs/mcp-memory.log
tail -f logs/mcp-brave.log
tail -f logs/mcp-filesystem.log
```

### Verify server processes
```bash
ps aux | grep mock_mcp
```

### Test fails - "Connection refused"
Servers aren't running. Run `./start-mcp-servers.sh` first.

### Brave search fails
Check that `BRAVE_API_KEY` is set in `.env` file.

## Server Architecture

```
┌─────────────────────────────────┐
│  MCP Servers (HTTP/REST)        │
├─────────────────────────────────┤
│                                 │
│  Memory (3100)                  │
│  - Store/retrieve memories      │
│  - In-memory storage            │
│                                 │
│  Brave (3101)                   │
│  - Web search                   │
│  - Local search                 │
│                                 │
│  Filesystem (3102)              │
│  - Read/write files             │
│  - Search documents             │
│  - Access: docs/, data/         │
│                                 │
└─────────────────────────────────┘
          ↑
          │ HTTP/JSON
          │
┌─────────────────────────────────┐
│  Backend (FastAPI)              │
│  - mcp_client.py                │
│  - mcp_tools.py                 │
│  - agent.py                     │
└─────────────────────────────────┘
```

## Test Results Summary

Last test run: **February 1, 2026**

```
✅ 25 tests passed
❌ 0 tests failed

Test coverage: 100%
```

See [MCP_TEST_REPORT.md](MCP_TEST_REPORT.md) for detailed results.

## What's Next?

1. ✅ **DONE:** MCP servers running and tested
2. **TODO:** Integrate with LangGraph agent
3. **TODO:** Add to agent tool set
4. **TODO:** Test end-to-end chat with MCP tools

## Files Reference

| File | Purpose |
|------|---------|
| `start-mcp-servers.sh` | Start all MCP servers |
| `stop-mcp-servers.sh` | Stop all servers |
| `test_mcp_integration.py` | Comprehensive test suite |
| `test-mcp-servers.sh` | Quick shell tests |
| `backend/mock_mcp_*.py` | Server implementations |
| `logs/mcp-*.log` | Server logs |
| `.mcp-pids` | Running process IDs |

---

**Quick reminder:** Always start servers before testing!

```bash
./start-mcp-servers.sh && python3 test_mcp_integration.py
```
