#!/usr/bin/env python3
"""Direct test of agent tool calling with visible output."""

import asyncio
import sys
sys.path.insert(0, '/Users/khanar/Library/CloudStorage/OneDrive-JKPSTATICKft/01_Munkahelyi/02_oktatás-és-képzés/AI-Agent/ai-agents-hu/mini_projects/kh.anar/backend')

from app.services.agent import AgentOrchestrator
from app.services.llm_client import LLMClient


async def test_agent_tools():
    """Test if agent actually calls tools."""
    print("Creating agent...")
    agent = AgentOrchestrator(llm_client=LLMClient())
    
    print(f"Agent has {len(agent.mcp_tools)} tools configured:")
    for tool in agent.mcp_tools:
        print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
    
    print("\n" + "="*60)
    print("Test 1: Recent news query (should trigger web search)")
    print("="*60)
    
    state = {
        "user_id": "test_user",
        "session_id": "test_session",
        "query": "What's the latest news about SpaceX?",
        "history": [],
        "rag_context": [],
        "request_metadata": {}
    }
    
    result = await agent.run(state)
    
    print(f"\nFinal response: {result.get('response_text', '')[:500]}...")
    print(f"\nTool calls made: {result.get('tool_calls', [])}")
    print(f"Tool results: {result.get('tool_results', [])}")
    
    if result.get('tool_results'):
        print("\n✓ SUCCESS: Agent called tools!")
        for tr in result['tool_results']:
            print(f"  - Called {tr['tool']} with {tr['arguments']}")
            print(f"    Result: {str(tr['result'])[:200]}...")
    else:
        print("\n✗ FAILED: Agent did not call any tools")
        print(f"Response type: {result.get('llm_response', {}).get('type')}")


if __name__ == "__main__":
    asyncio.run(test_agent_tools())
