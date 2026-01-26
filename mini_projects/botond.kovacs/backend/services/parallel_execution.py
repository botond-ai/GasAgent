import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

async def execute_parallel_mcp_tools(tasks: List[Dict[str, Any]], mcp_client) -> List[Dict[str, Any]]:
    async def _run(task):
        try:
            result = await mcp_client.call_tool(task["tool_name"], task["arguments"])
            return {
                "tool_name": task["tool_name"],
                "arguments": task["arguments"],
                "result": result,
                "success": True
            }
        except Exception as e:
            logger.error(f"MCP tool error: {e}")
            return {"tool_name": task["tool_name"], "arguments": task["arguments"], "success": False, "error": str(e)}

    logger.info(f"Executing {len(tasks)} MCP tools in parallel...")
    results = await asyncio.gather(*[_run(t) for t in tasks], return_exceptions=False)
    return results
