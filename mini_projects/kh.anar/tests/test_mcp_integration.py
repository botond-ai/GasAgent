"""
Comprehensive test suite for MCP servers.
Tests Memory, Brave Search, and Filesystem MCP server integration.
"""

import asyncio
import httpx
import json
from typing import Dict, Any

# Server URLs
MEMORY_URL = "http://localhost:3100"
BRAVE_URL = "http://localhost:3101"
FILESYSTEM_URL = "http://localhost:3102"

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def pass_test(self, name: str):
        print(f"{GREEN}✓{RESET} {name}")
        self.passed += 1
    
    def fail_test(self, name: str, error: str):
        print(f"{RED}✗{RESET} {name}: {error}")
        self.failed += 1
        self.errors.append(f"{name}: {error}")
    
    def print_summary(self):
        print("\n" + "="*50)
        print("Test Summary")
        print("="*50)
        print(f"{GREEN}Passed: {self.passed}{RESET}")
        print(f"{RED}Failed: {self.failed}{RESET}")
        
        if self.errors:
            print(f"\n{YELLOW}Errors:{RESET}")
            for error in self.errors:
                print(f"  - {error}")
        
        print("="*50)
        
        if self.failed == 0:
            print(f"{GREEN}All tests passed! ✓{RESET}")
            return 0
        else:
            print(f"{YELLOW}Some tests failed.{RESET}")
            return 1


results = TestResult()


async def test_endpoint(client: httpx.AsyncClient, name: str, method: str, url: str, data: Dict = None):
    """Test an HTTP endpoint."""
    try:
        if method == "GET":
            response = await client.get(url)
        elif method == "POST":
            response = await client.post(url, json=data)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        if response.status_code == 200:
            results.pass_test(name)
            return response.json()
        else:
            results.fail_test(name, f"HTTP {response.status_code}")
            return None
            
    except httpx.ConnectError:
        results.fail_test(name, "Connection refused - server not running?")
        return None
    except Exception as e:
        results.fail_test(name, str(e))
        return None


async def main():
    print("="*50)
    print("MCP Server Integration Test Suite (Python)")
    print("="*50)
    print()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test 1: Server Health
        print("1. Testing Server Health")
        print("-" * 50)
        await test_endpoint(client, "Memory MCP health", "GET", f"{MEMORY_URL}/health")
        await test_endpoint(client, "Brave MCP health", "GET", f"{BRAVE_URL}/health")
        await test_endpoint(client, "Filesystem MCP health", "GET", f"{FILESYSTEM_URL}/health")
        print()
        
        # Test 2: List Available Tools
        print("2. Testing Tool Discovery")
        print("-" * 50)
        await test_endpoint(client, "Memory tools list", "GET", f"{MEMORY_URL}/tools")
        await test_endpoint(client, "Brave tools list", "GET", f"{BRAVE_URL}/tools")
        await test_endpoint(client, "Filesystem tools list", "GET", f"{FILESYSTEM_URL}/tools")
        print()
        
        # Test 3: Memory Operations
        print("3. Testing Memory Operations")
        print("-" * 50)
        
        # Store a memory
        store_result = await test_endpoint(
            client,
            "Store memory entry",
            "POST",
            f"{MEMORY_URL}/tools/store",
            {"conversation_id": "test-123", "key": "user_name", "value": "Alice"}
        )
        
        # Retrieve the memory
        retrieve_result = await test_endpoint(
            client,
            "Retrieve memory entry",
            "POST",
            f"{MEMORY_URL}/tools/retrieve",
            {"conversation_id": "test-123", "key": "user_name"}
        )
        
        # Verify the value
        if retrieve_result and retrieve_result.get("data", {}).get("value") == "Alice":
            results.pass_test("Memory value verification")
        else:
            results.fail_test("Memory value verification", "Value mismatch")
        
        # List all memories
        list_result = await test_endpoint(
            client,
            "List all memories",
            "POST",
            f"{MEMORY_URL}/tools/list",
            {"conversation_id": "test-123"}
        )
        
        # Store another memory
        await test_endpoint(
            client,
            "Store second memory",
            "POST",
            f"{MEMORY_URL}/tools/store",
            {"conversation_id": "test-123", "key": "user_age", "value": "25"}
        )
        
        # Delete a memory
        await test_endpoint(
            client,
            "Delete memory entry",
            "POST",
            f"{MEMORY_URL}/tools/delete",
            {"conversation_id": "test-123", "key": "user_age"}
        )
        print()
        
        # Test 4: Brave Search
        print("4. Testing Brave Search")
        print("-" * 50)
        search_result = await test_endpoint(
            client,
            "Web search query",
            "POST",
            f"{BRAVE_URL}/tools/search",
            {"query": "OpenAI GPT", "count": 3}
        )
        
        if search_result and "data" in search_result:
            if "results" in search_result["data"]:
                results.pass_test("Search results structure")
            else:
                results.fail_test("Search results structure", "No results field")
        
        local_result = await test_endpoint(
            client,
            "Local search query",
            "POST",
            f"{BRAVE_URL}/tools/local_search",
            {"query": "coffee shops", "count": 2}
        )
        print()
        
        # Test 5: Filesystem Operations
        print("5. Testing Filesystem Operations")
        print("-" * 50)
        
        # List docs directory
        list_dir_result = await test_endpoint(
            client,
            "List docs directory",
            "POST",
            f"{FILESYSTEM_URL}/tools/list_directory",
            {"path": "docs"}
        )
        
        if list_dir_result and "data" in list_dir_result:
            if "items" in list_dir_result["data"]:
                results.pass_test("Directory listing structure")
                items = list_dir_result["data"]["items"]
                print(f"  Found {len(items)} items in docs/")
            else:
                results.fail_test("Directory listing structure", "No items field")
        
        # Write a test file
        write_result = await test_endpoint(
            client,
            "Write test file",
            "POST",
            f"{FILESYSTEM_URL}/tools/write_file",
            {"path": "data/test_mcp.txt", "content": "MCP test successful!"}
        )
        
        # Read the test file
        read_result = await test_endpoint(
            client,
            "Read test file",
            "POST",
            f"{FILESYSTEM_URL}/tools/read_file",
            {"path": "data/test_mcp.txt"}
        )
        
        if read_result and read_result.get("data", {}).get("content") == "MCP test successful!":
            results.pass_test("File content verification")
        else:
            results.fail_test("File content verification", "Content mismatch")
        
        # Search for files
        search_result = await test_endpoint(
            client,
            "Search for .md files",
            "POST",
            f"{FILESYSTEM_URL}/tools/search",
            {"path": "docs", "pattern": "*.md"}
        )
        print()
        
        # Test 6: Integration Test - Multi-step workflow
        print("6. Testing Multi-step Workflow")
        print("-" * 50)
        
        # Scenario: User asks about docs, we search, read, and remember
        workflow_conv_id = "workflow-test"
        
        # Step 1: Search for docs
        search_docs = await test_endpoint(
            client,
            "Search docs directory",
            "POST",
            f"{FILESYSTEM_URL}/tools/search",
            {"path": "docs", "pattern": "*.md"}
        )
        
        # Step 2: Store the search result in memory
        if search_docs and search_docs.get("success"):
            num_results = len(search_docs.get("data", {}).get("results", []))
            await test_endpoint(
                client,
                "Remember search results",
                "POST",
                f"{MEMORY_URL}/tools/store",
                {
                    "conversation_id": workflow_conv_id,
                    "key": "last_search",
                    "value": f"Found {num_results} markdown files"
                }
            )
        
        # Step 3: Retrieve what we remembered
        memory_check = await test_endpoint(
            client,
            "Recall search results",
            "POST",
            f"{MEMORY_URL}/tools/retrieve",
            {"conversation_id": workflow_conv_id, "key": "last_search"}
        )
        
        if memory_check and "Found" in str(memory_check.get("data", {}).get("value", "")):
            results.pass_test("Workflow memory persistence")
        else:
            results.fail_test("Workflow memory persistence", "Memory not persisted correctly")
        
        print()
    
    # Print summary
    return results.print_summary()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
