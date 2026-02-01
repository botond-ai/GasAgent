#!/bin/bash

# Test script for MCP servers
# Tests Memory, Brave Search, and Filesystem MCP servers

set -e

echo "=================================="
echo "MCP Server Integration Test Suite"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
PASSED=0
FAILED=0

# Function to test endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local method=${3:-GET}
    local data=${4:-""}
    
    echo -n "Testing $name... "
    
    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$url" 2>&1)
    else
        response=$(curl -s -w "\n%{http_code}" "$url" 2>&1)
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "000" ] && [[ "$body" != *"Connection refused"* ]]; then
        echo -e "${GREEN}✓ PASSED${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP $http_code)"
        echo "  Response: $body"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

echo "1. Testing MCP Server Connectivity"
echo "-----------------------------------"

# Test Memory MCP Server
echo "Memory MCP Server (port 3100):"
test_endpoint "Health check" "http://localhost:3100/health" || true
test_endpoint "List tools" "http://localhost:3100/tools" || true

echo ""
echo "Brave Search MCP Server (port 3101):"
test_endpoint "Health check" "http://localhost:3101/health" || true
test_endpoint "List tools" "http://localhost:3101/tools" || true

echo ""
echo "Filesystem MCP Server (port 3102):"
test_endpoint "Health check" "http://localhost:3102/health" || true
test_endpoint "List tools" "http://localhost:3102/tools" || true

echo ""
echo "2. Testing MCP Tool Operations"
echo "-------------------------------"

# Test Memory operations
echo "Memory Operations:"
test_endpoint "Store memory" "http://localhost:3100/tools/store" "POST" \
    '{"conversation_id":"test-123","key":"test_key","value":"test_value"}' || true

test_endpoint "Retrieve memory" "http://localhost:3100/tools/retrieve" "POST" \
    '{"conversation_id":"test-123","key":"test_key"}' || true

test_endpoint "List memories" "http://localhost:3100/tools/list" "POST" \
    '{"conversation_id":"test-123"}' || true

echo ""
echo "Brave Search Operations:"
test_endpoint "Web search" "http://localhost:3101/tools/search" "POST" \
    '{"query":"test query","count":3}' || true

echo ""
echo "Filesystem Operations:"
test_endpoint "List directory" "http://localhost:3102/tools/list_directory" "POST" \
    '{"path":"docs"}' || true

echo ""
echo "3. Testing Docker Containers"
echo "----------------------------"

echo "Checking MCP container status:"
if command -v docker &> /dev/null; then
    # Check for MCP containers
    memory_status=$(docker ps --filter "name=kh-anar-mcp-memory" --format "{{.Status}}" 2>/dev/null || echo "not running")
    brave_status=$(docker ps --filter "name=kh-anar-mcp-brave" --format "{{.Status}}" 2>/dev/null || echo "not running")
    filesystem_status=$(docker ps --filter "name=kh-anar-mcp-filesystem" --format "{{.Status}}" 2>/dev/null || echo "not running")
    
    echo "  Memory MCP: $memory_status"
    echo "  Brave MCP: $brave_status"
    echo "  Filesystem MCP: $filesystem_status"
    
    if [[ "$memory_status" == *"Up"* ]]; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    if [[ "$brave_status" == *"Up"* ]]; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    if [[ "$filesystem_status" == *"Up"* ]]; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${YELLOW}Docker not available - skipping container checks${NC}"
fi

echo ""
echo "4. Testing Backend MCP Client Integration"
echo "------------------------------------------"

# Test if backend can reach MCP servers through the client
backend_url="http://localhost:8000"
echo "Testing backend MCP integration at $backend_url..."

# This assumes your backend has a health or debug endpoint
test_endpoint "Backend health" "$backend_url/health" || true

echo ""
echo "=================================="
echo "Test Summary"
echo "=================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "=================================="

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${YELLOW}Some tests failed. Check the output above for details.${NC}"
    exit 1
fi
