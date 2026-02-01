"""
MCP Tools for LangGraph agent integration.
Provides tool wrappers for accessing Memory, Brave Search, and Filesystem via MCP servers.
"""

from typing import Any, Dict, List, Optional
import json

from .mcp_client import mcp_client


def create_mcp_tools() -> List[Dict[str, Any]]:
    """Create tool definitions for MCP servers.
    
    Returns a list of tool dictionaries compatible with OpenAI function calling.
    """
    
    tools = [
        # Memory tools
        {
            "name": "memory_store",
            "description": "Store a memory entry for the current conversation. Use this to remember important facts, preferences, or context from the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string", "description": "The conversation ID"},
                    "key": {"type": "string", "description": "Memory key"},
                    "value": {"type": "string", "description": "Memory value"},
                },
                "required": ["conversation_id", "key", "value"],
            },
        },
        {
            "name": "memory_retrieve",
            "description": "Retrieve a previously stored memory entry. Use this to recall information from earlier in the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string", "description": "The conversation ID"},
                    "key": {"type": "string", "description": "Memory key to retrieve"},
                },
                "required": ["conversation_id", "key"],
            },
        },
        {
            "name": "memory_list",
            "description": "List all stored memories for the current conversation. Use this to get an overview of what has been remembered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string", "description": "The conversation ID"},
                },
                "required": ["conversation_id"],
            },
        },
        
        # Brave Search tools
        {
            "name": "brave_search",
            "description": "Search the web using Brave Search. Use this when you need current information, facts, or answers that aren't in the knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {"type": "integer", "description": "Number of results (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
        {
            "name": "brave_local_search",
            "description": "Search for local places, businesses, or locations using Brave. Use when the user asks about nearby places.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for local places"},
                    "count": {"type": "integer", "description": "Number of results (default 3)", "default": 3},
                },
                "required": ["query"],
            },
        },
        
        # Filesystem tools
        {
            "name": "filesystem_read",
            "description": "Read the contents of a file from the knowledge base directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "filesystem_list",
            "description": "List files in a directory of the knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "filesystem_search",
            "description": "Search for files matching a pattern in the knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Base directory path"},
                    "pattern": {"type": "string", "description": "File pattern to search for"},
                },
                "required": ["path", "pattern"],
            },
        },
    ]
    
    return tools


async def execute_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Execute an MCP tool and return the result as a string."""
    
    try:
        if tool_name == "memory_store":
            result = await mcp_client.memory_store(
                arguments["conversation_id"],
                arguments["key"],
                arguments["value"]
            )
        elif tool_name == "memory_retrieve":
            result = await mcp_client.memory_retrieve(
                arguments["conversation_id"],
                arguments["key"]
            )
        elif tool_name == "memory_list":
            result = await mcp_client.memory_list(arguments["conversation_id"])
        elif tool_name == "brave_search":
            result = await mcp_client.brave_search(
                arguments["query"],
                arguments.get("count", 5)
            )
        elif tool_name == "brave_local_search":
            result = await mcp_client.brave_local_search(
                arguments["query"],
                arguments.get("count", 3)
            )
        elif tool_name == "filesystem_read":
            result = await mcp_client.filesystem_read(arguments["path"])
        elif tool_name == "filesystem_list":
            result = await mcp_client.filesystem_list(arguments["path"])
        elif tool_name == "filesystem_search":
            result = await mcp_client.filesystem_search(
                arguments["path"],
                arguments["pattern"]
            )
        else:
            return f"Unknown tool: {tool_name}"
        
        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                return json.dumps(data, indent=2)
            return str(data)
        else:
            return f"Tool error: {result.get('error', 'Unknown error')}"
    
    except Exception as e:
        return f"Exception executing tool {tool_name}: {str(e)}"

