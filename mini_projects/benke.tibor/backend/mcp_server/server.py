"""
MCP Server implementation for KnowledgeRouter.
Wraps existing infrastructure clients (Jira, Qdrant, PostgreSQL) as MCP tools.

Architecture:
- Standalone Python process (can run in separate container)
- Exposes tools via MCP protocol (stdio, HTTP, SSE)
- Zero modifications to existing backend code
- Can be queried by LLM agents via tool calling
"""

import logging
import sys
from typing import Any

# MCP SDK - install via: pip install mcp
try:
    from mcp.server import Server, Request
    from mcp.types import Tool, TextContent, ToolResult
except ImportError:
    print("ERROR: MCP SDK not installed. Run: pip install mcp")
    sys.exit(1)

from .tools import jira_tools, qdrant_tools, postgres_tools

logger = logging.getLogger(__name__)


class MCPServer:
    """
    KnowledgeRouter MCP Server.
    
    Exposes infrastructure operations as standardized tools:
    - Jira: Create tickets, search issues
    - Qdrant: Semantic search, vector operations
    - PostgreSQL: Feedback, analytics queries
    """
    
    def __init__(self, name: str = "knowledgerouter"):
        """Initialize MCP server."""
        self.server = Server(name)
        self.name = name
        self.tool_defs = {}
        self.tool_handlers = {}
        self._setup_tools()
        self._setup_handlers()
    
    def _setup_tools(self):
        """Register all available tools."""
        logger.info("📋 Registering MCP tools...")
        
        # Jira tools
        self.tool_defs.update({
            "jira_create_ticket": jira_tools.create_ticket_tool(),
            "jira_search_issues": jira_tools.search_issues_tool(),
        })
        self.tool_handlers.update({
            "jira_create_ticket": jira_tools.create_ticket,
            "jira_search_issues": jira_tools.search_issues,
        })
        
        # Qdrant tools
        self.tool_defs.update({
            "qdrant_search": qdrant_tools.search_tool(),
            "qdrant_retrieve_by_ids": qdrant_tools.retrieve_by_ids_tool(),
        })
        self.tool_handlers.update({
            "qdrant_search": qdrant_tools.search,
            "qdrant_retrieve_by_ids": qdrant_tools.retrieve_by_ids,
        })
        
        # PostgreSQL tools
        self.tool_defs.update({
            "postgres_get_feedback": postgres_tools.get_feedback_tool(),
            "postgres_get_analytics": postgres_tools.get_analytics_tool(),
        })
        self.tool_handlers.update({
            "postgres_get_feedback": postgres_tools.get_feedback,
            "postgres_get_analytics": postgres_tools.get_analytics,
        })
        
        logger.info(f"✅ Registered {len(self.tool_defs)} tools")
    
    def _setup_handlers(self):
        """Setup MCP protocol handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """Return available tools."""
            return list(self.tool_defs.values())
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> ToolResult:
            """Execute a tool."""
            logger.info(f"🔧 Calling tool: {name} with args: {arguments}")
            
            if name not in self.tool_handlers:
                return ToolResult(
                    isError=True,
                    content=[TextContent(type="text", text=f"Tool '{name}' not found")]
                )
            
            try:
                tool_func = self.tool_handlers[name]
                result = await tool_func(**arguments)
                
                return ToolResult(
                    isError=False,
                    content=[TextContent(type="text", text=str(result))]
                )
            except Exception as e:
                logger.error(f"❌ Tool error: {e}", exc_info=True)
                return ToolResult(
                    isError=True,
                    content=[TextContent(type="text", text=f"Error: {str(e)}")]
                )
    
    async def run(self):
        """Start MCP server (stdio mode by default)."""
        logger.info(f"🚀 Starting {self.name} MCP server (stdio mode)...")
        async with self.server:
            # stdio mode: reads from stdin, writes to stdout
            await self.server.run()


def main():
    """Entry point for MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    server = MCPServer()
    
    try:
        import asyncio
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("⏹️ MCP server stopped")


if __name__ == "__main__":
    main()
