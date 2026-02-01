#!/bin/bash

# Complete test script for docker-compose MCP integration

echo "======================================================"
echo "Docker Compose MCP Integration - Complete Test"
echo "======================================================"
echo ""

# Check if docker-compose is running
echo "1. Checking Docker Compose Status..."
echo "------------------------------------------------------"
if docker-compose ps | grep -q "Up"; then
    echo "✓ Docker containers are running"
    docker-compose ps
else
    echo "✗ Docker containers not running"
    echo ""
    echo "Starting containers with: docker-compose up -d"
    docker-compose up -d
    echo ""
    echo "Waiting for containers to be healthy..."
    sleep 15
fi

echo ""
echo "2. Testing MCP Server Health..."
echo "------------------------------------------------------"

# Test Memory MCP
if curl -s http://localhost:3100/health | grep -q "ok"; then
    echo "✓ Memory MCP (3100) - Healthy"
else
    echo "✗ Memory MCP (3100) - Not responding"
fi

# Test Brave MCP
if curl -s http://localhost:3101/health | grep -q "ok"; then
    echo "✓ Brave MCP (3101) - Healthy"
else
    echo "✗ Brave MCP (3101) - Not responding"
fi

# Test Filesystem MCP
if curl -s http://localhost:3102/health | grep -q "ok"; then
    echo "✓ Filesystem MCP (3102) - Healthy"
else
    echo "✗ Filesystem MCP (3102) - Not responding"
fi

echo ""
echo "3. Running Comprehensive Integration Tests..."
echo "------------------------------------------------------"

# Run Python integration tests
if command -v python3 &> /dev/null; then
    python3 test_mcp_integration.py
else
    echo "✗ Python3 not found - skipping integration tests"
fi

echo ""
echo "4. Container Resource Usage..."
echo "------------------------------------------------------"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -6

echo ""
echo "5. Container Logs (last 5 lines each)..."
echo "------------------------------------------------------"
echo "--- Memory MCP ---"
docker-compose logs --tail=5 mcp-memory | tail -5
echo ""
echo "--- Brave MCP ---"
docker-compose logs --tail=5 mcp-brave | tail -5
echo ""
echo "--- Filesystem MCP ---"
docker-compose logs --tail=5 mcp-filesystem | tail -5

echo ""
echo "======================================================"
echo "Test Complete!"
echo "======================================================"
echo ""
echo "Services running at:"
echo "  Frontend:  http://localhost:4000"
echo "  Backend:   http://localhost:8000"
echo "  Memory:    http://localhost:3100"
echo "  Brave:     http://localhost:3101"
echo "  Filesystem: http://localhost:3102"
echo ""
echo "To stop: docker-compose down"
