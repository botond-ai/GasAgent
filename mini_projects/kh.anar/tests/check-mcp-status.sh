#!/bin/bash

# Quick status check for MCP servers

echo "MCP Server Status Check"
echo "======================="
echo ""

# Check if processes are running
echo "Process Status:"
if ps aux | grep -E "(mock_mcp_memory|mock_mcp_brave|mock_mcp_filesystem)" | grep -v grep > /dev/null; then
    ps aux | grep "mock_mcp" | grep -v grep | awk '{printf "  ✓ PID %s: %s\n", $2, $NF}'
else
    echo "  ✗ No MCP servers running"
    echo ""
    echo "To start servers: ./start-mcp-servers.sh"
    exit 1
fi

echo ""
echo "Port Status:"
for port in 3100 3101 3102; do
    if nc -z localhost $port 2>/dev/null; then
        echo "  ✓ Port $port is listening"
    else
        echo "  ✗ Port $port is NOT listening"
    fi
done

echo ""
echo "Server Health:"

# Memory MCP
response=$(curl -s http://localhost:3100/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  ✓ Memory MCP (3100): $(echo $response | python3 -c 'import sys, json; print(json.load(sys.stdin).get("status", "unknown"))')"
else
    echo "  ✗ Memory MCP (3100): Not responding"
fi

# Brave MCP
response=$(curl -s http://localhost:3101/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  ✓ Brave MCP (3101): $(echo $response | python3 -c 'import sys, json; print(json.load(sys.stdin).get("status", "unknown"))')"
else
    echo "  ✗ Brave MCP (3101): Not responding"
fi

# Filesystem MCP
response=$(curl -s http://localhost:3102/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  ✓ Filesystem MCP (3102): $(echo $response | python3 -c 'import sys, json; print(json.load(sys.stdin).get("status", "unknown"))')"
else
    echo "  ✗ Filesystem MCP (3102): Not responding"
fi

echo ""
echo "Quick Test:"

# Test memory operation
test_result=$(curl -s -X POST http://localhost:3100/tools/store \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"status-check","key":"test","value":"working"}' 2>/dev/null)

if echo "$test_result" | grep -q "success"; then
    echo "  ✓ Memory store/retrieve working"
else
    echo "  ✗ Memory operations failed"
fi

echo ""
echo "To run full tests: python3 test_mcp_integration.py"
echo "To stop servers: ./stop-mcp-servers.sh"
