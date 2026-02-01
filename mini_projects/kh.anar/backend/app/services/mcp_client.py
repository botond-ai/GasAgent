"""
MCP (Model Context Protocol) client integration.
Provides tools via Memory, Brave Search, and Filesystem MCP servers.
"""

import os
from typing import Any, Dict, List

import httpx


class MCPClient:
    """Client for interacting with MCP servers."""

    def __init__(self):
        self.memory_url = os.getenv("MCP_MEMORY_URL", "http://localhost:3100")
        self.brave_url = os.getenv("MCP_BRAVE_URL", "http://localhost:3101")
        self.filesystem_url = os.getenv("MCP_FILESYSTEM_URL", "http://localhost:3102")
        self.timeout = 30.0

    async def call_tool(self, server: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the specified MCP server."""
        server_urls = {
            "memory": self.memory_url,
            "brave": self.brave_url,
            "filesystem": self.filesystem_url,
        }
        
        if server not in server_urls:
            return {"success": False, "error": f"Unknown MCP server: {server}"}
        
        url = f"{server_urls[server]}/tools/{tool_name}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=arguments)
                response.raise_for_status()
                return {"success": True, "data": response.json()}
        except httpx.HTTPError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    # Memory MCP Server tools
    async def memory_store(self, conversation_id: str, key: str, value: str) -> Dict[str, Any]:
        """Store a memory entry."""
        return await self.call_tool("memory", "store", {
            "conversation_id": conversation_id,
            "key": key,
            "value": value
        })

    async def memory_retrieve(self, conversation_id: str, key: str) -> Dict[str, Any]:
        """Retrieve a memory entry."""
        return await self.call_tool("memory", "retrieve", {
            "conversation_id": conversation_id,
            "key": key
        })

    async def memory_list(self, conversation_id: str) -> Dict[str, Any]:
        """List all memories for a conversation."""
        return await self.call_tool("memory", "list", {
            "conversation_id": conversation_id
        })

    async def memory_delete(self, conversation_id: str, key: str) -> Dict[str, Any]:
        """Delete a memory entry."""
        return await self.call_tool("memory", "delete", {
            "conversation_id": conversation_id,
            "key": key
        })

    # Brave Search MCP Server tools
    async def brave_search(self, query: str, count: int = 5) -> Dict[str, Any]:
        """Search the web using Brave Search."""
        return await self.call_tool("brave", "search", {
            "query": query,
            "count": count
        })

    async def brave_local_search(self, query: str, count: int = 3) -> Dict[str, Any]:
        """Search for local places using Brave."""
        return await self.call_tool("brave", "local_search", {
            "query": query,
            "count": count
        })

    # Filesystem MCP Server tools
    async def filesystem_read(self, path: str) -> Dict[str, Any]:
        """Read a file from the filesystem."""
        return await self.call_tool("filesystem", "read_file", {
            "path": path
        })

    async def filesystem_write(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to a file."""
        return await self.call_tool("filesystem", "write_file", {
            "path": path,
            "content": content
        })

    async def filesystem_list(self, path: str) -> Dict[str, Any]:
        """List files in a directory."""
        return await self.call_tool("filesystem", "list_directory", {
            "path": path
        })

    async def filesystem_create_directory(self, path: str) -> Dict[str, Any]:
        """Create a directory."""
        return await self.call_tool("filesystem", "create_directory", {
            "path": path
        })

    async def filesystem_delete(self, path: str) -> Dict[str, Any]:
        """Delete a file or directory."""
        return await self.call_tool("filesystem", "delete", {
            "path": path
        })

    async def filesystem_move(self, source: str, destination: str) -> Dict[str, Any]:
        """Move or rename a file or directory."""
        return await self.call_tool("filesystem", "move", {
            "source": source,
            "destination": destination
        })

    async def filesystem_search(self, path: str, pattern: str) -> Dict[str, Any]:
        """Search for files matching a pattern."""
        return await self.call_tool("filesystem", "search", {
            "path": path,
            "pattern": pattern
        })


# Singleton instance
mcp_client = MCPClient()
