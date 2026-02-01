#!/usr/bin/env python3
"""Test if the agent can use Brave search through MCP tools."""

import asyncio
import httpx


async def test_agent_brave_search():
    """Test agent's ability to search using Brave."""
    base_url = "http://localhost:8000"
    
    # Create a test session
    async with httpx.AsyncClient(timeout=60.0) as client:
        user_id = "test_brave_user"
        session_id = "test_session_brave"
        
        # Test 1: Ask about recent news (should trigger Brave search)
        print("\n=== Test 1: Recent News Query ===")
        response = await client.post(
            f"{base_url}/api/chat",
            json={
                "message": "What's the latest news about OpenAI?",
                "user_id": user_id,
                "session_id": session_id
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Response received (length: {len(result['reply'])} chars)")
            print(f"  First 300 chars: {result['reply'][:300]}...")
            
            # Check debug info for tool usage
            if result.get('debug'):
                debug = result['debug']
                print(f"\n  Debug Info:")
                print(f"    - RAG Context: {len(debug.get('rag_context', []))} items")
                if debug.get('rag_telemetry'):
                    print(f"    - RAG Telemetry: {debug['rag_telemetry']}")
            
            # Check if the response mentions web search or recent information
            if any(word in result['reply'].lower() for word in ['search', 'found', 'according to', 'recent', 'latest']):
                print("\n✓ Response appears to include web search results")
            else:
                print("\n⚠ Response doesn't clearly indicate web search was used")
                print(f"   Full response: {result['reply']}")
        else:
            print(f"✗ Chat failed: {response.status_code}")
            print(f"  Error: {response.text}")
        
        # Test 2: Explicitly ask to search
        print("\n=== Test 2: Explicit Search Request ===")
        response = await client.post(
            f"{base_url}/api/chat",
            json={
                "message": "Search the web for the current weather in Budapest, Hungary",
                "user_id": user_id,
                "session_id": session_id
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Response received (length: {len(result['reply'])} chars)")
            print(f"  First 300 chars: {result['reply'][:300]}...")
        else:
            print(f"✗ Chat failed: {response.status_code}")
            print(f"  Error: {response.text}")
        
        # Test 3: Simple factual query (should NOT need web search)
        print("\n=== Test 3: Simple Factual Query (No Search Expected) ===")
        response = await client.post(
            f"{base_url}/api/chat",
            json={
                "message": "What is 2+2?",
                "user_id": user_id,
                "session_id": "test_session_nosearch"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Response received: {result['reply']}")
        else:
            print(f"✗ Chat failed: {response.status_code}")


if __name__ == "__main__":
    print("Testing Agent's Brave Search Integration")
    print("=" * 50)
    asyncio.run(test_agent_brave_search())
    print("\n" + "=" * 50)
    print("Test completed!")
