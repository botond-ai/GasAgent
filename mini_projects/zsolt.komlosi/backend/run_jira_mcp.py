#!/usr/bin/env python
"""
Run the Jira MCP server.

Usage:
    python run_jira_mcp.py

The server communicates via stdin/stdout using the MCP protocol.
Configure in Claude Code or other MCP clients to use this server.
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Run the server
from app.integrations.jira_mcp_server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
