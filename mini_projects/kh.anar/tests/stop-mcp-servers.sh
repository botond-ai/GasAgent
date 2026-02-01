#!/bin/bash

# Stop all MCP servers

echo "Stopping MCP Servers..."
echo "======================"

# Read PIDs from file if it exists
if [ -f .mcp-pids ]; then
    while read pid; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "Killing process $pid..."
            kill $pid 2>/dev/null || true
        fi
    done < .mcp-pids
    rm .mcp-pids
fi

# Also try to kill by port
echo "Cleaning up processes on ports 3100, 3101, 3102..."
lsof -ti:3100 | xargs kill -9 2>/dev/null || true
lsof -ti:3101 | xargs kill -9 2>/dev/null || true
lsof -ti:3102 | xargs kill -9 2>/dev/null || true

echo "All MCP servers stopped."
