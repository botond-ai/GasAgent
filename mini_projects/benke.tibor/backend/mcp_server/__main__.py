#!/usr/bin/env python3
"""
MCP Server entrypoint.

Usage:
    python -m mcp_server
    or
    python backend/mcp_server/__main__.py
"""

import logging
import sys
import asyncio

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def main():
    """Run MCP server."""
    logger.info("🚀 KnowledgeRouter MCP Server v0.1")
    logger.info("=" * 50)
    
    from mcp_server.server import MCPServer
    
    try:
        server = MCPServer(name="knowledgerouter-mcp")
        logger.info(f"📋 Tools available: {list(server.tools_registry.keys())}")
        logger.info("=" * 50)
        logger.info("🎯 Starting server in stdio mode...")
        logger.info("(Waiting for client connections...)")
        
        await server.run()
        
    except KeyboardInterrupt:
        logger.info("⏹️ Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
