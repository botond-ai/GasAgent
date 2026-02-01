#!/bin/bash

# Start MCP servers using HTTP-based mock servers
# This script starts Memory, Brave Search, and Filesystem MCP servers

set -e

echo "Starting MCP Servers..."
echo "======================"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check for Brave API key
if [ -z "$BRAVE_API_KEY" ]; then
    echo "WARNING: BRAVE_API_KEY not found in .env file - Brave search may not work"
fi

# Create data directories
mkdir -p data/mcp/memory
mkdir -p docs
mkdir -p data
mkdir -p logs

# Kill any existing processes on these ports
echo "Cleaning up existing processes..."
lsof -ti:3100 | xargs kill -9 2>/dev/null || true
lsof -ti:3101 | xargs kill -9 2>/dev/null || true
lsof -ti:3102 | xargs kill -9 2>/dev/null || true

sleep 2

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is required but not found"
    exit 1
fi

# Start Memory MCP Server
echo "Starting Memory MCP Server on port 3100..."
PORT=3100 python3 backend/mock_mcp_memory.py > logs/mcp-memory.log 2>&1 &
MEMORY_PID=$!
echo "  Memory MCP PID: $MEMORY_PID"

sleep 2

# Start Brave Search MCP Server
echo "Starting Brave Search MCP Server on port 3101..."
PORT=3101 BRAVE_API_KEY=$BRAVE_API_KEY python3 backend/mock_mcp_brave.py > logs/mcp-brave.log 2>&1 &
BRAVE_PID=$!
echo "  Brave MCP PID: $BRAVE_PID"

sleep 2

# Start Filesystem MCP Server
echo "Starting Filesystem MCP Server on port 3102..."
PORT=3102 python3 backend/mock_mcp_filesystem.py > logs/mcp-filesystem.log 2>&1 &
FILESYSTEM_PID=$!
echo "  Filesystem MCP PID: $FILESYSTEM_PID"

sleep 3

# Save PIDs to file for later cleanup
echo $MEMORY_PID > .mcp-pids
echo $BRAVE_PID >> .mcp-pids
echo $FILESYSTEM_PID >> .mcp-pids

echo ""
echo "All MCP servers started!"
echo "========================"
echo "Memory MCP:     http://localhost:3100 (PID: $MEMORY_PID)"
echo "Brave MCP:      http://localhost:3101 (PID: $BRAVE_PID)"
echo "Filesystem MCP: http://localhost:3102 (PID: $FILESYSTEM_PID)"
echo ""
echo "Logs are in ./logs/ directory"
echo "To stop servers, run: ./stop-mcp-servers.sh"
echo ""

# Wait a bit for servers to fully start
sleep 2

# Quick health check
echo "Performing quick health check..."
for port in 3100 3101 3102; do
    if nc -z localhost $port 2>/dev/null; then
        echo "  ✓ Port $port is listening"
    else
        echo "  ✗ Port $port is NOT listening"
    fi
done

echo ""
echo "Run ./test-mcp-servers.sh to run full integration tests"
