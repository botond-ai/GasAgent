"""
PostgreSQL MCP Tools - Wraps PostgreSQL client for MCP protocol.

Tools:
- get_feedback: Retrieve user feedback scores
- get_analytics: Get usage analytics
"""

import logging
from typing import Dict, Any

try:
    from mcp.types import Tool, TextContent
except ImportError:
    Tool = None
    TextContent = None

logger = logging.getLogger(__name__)


def get_feedback_tool() -> Tool:
    """
    Get citation feedback.
    
    MCP Tool definition for retrieving feedback scores.
    """
    return Tool(
        name="postgres_get_feedback",
        description="Get user feedback scores for citations",
        inputSchema={
            "type": "object",
            "properties": {
                "citation_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Citation IDs to get feedback for"
                }
            },
            "required": ["citation_ids"]
        }
    )


async def get_feedback(citation_ids: list) -> Dict[str, Any]:
    """
    Get citation feedback via PostgreSQL client.
    
    Args:
        citation_ids: List of citation IDs
    
    Returns:
        Feedback scores {citation_id: like_percentage, ...}
    """
    try:
        from infrastructure.postgres_client import postgres_client
        
        logger.info(f"📊 Getting feedback for {len(citation_ids)} citations")
        
        feedback = await postgres_client.get_citation_feedback_batch(citation_ids)
        
        logger.info(f"✅ Retrieved feedback for {len(feedback)} citations")
        return {
            "success": True,
            "feedback": feedback,
            "total": len(feedback)
        }
        
    except Exception as e:
        logger.error(f"❌ Feedback retrieval failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_analytics_tool() -> Tool:
    """
    Get usage analytics.
    
    MCP Tool definition for analytics queries.
    """
    return Tool(
        name="postgres_get_analytics",
        description="Get usage analytics (queries, domains, cache hits, etc.)",
        inputSchema={
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["query_count", "domain_distribution", "cache_hits", "latency"],
                    "description": "Analytics metric to retrieve"
                },
                "time_range_hours": {
                    "type": "integer",
                    "description": "Time range in hours (default: 24)"
                }
            },
            "required": ["metric"]
        }
    )


async def get_analytics(
    metric: str,
    time_range_hours: int = 24
) -> Dict[str, Any]:
    """
    Get analytics via PostgreSQL.
    
    Args:
        metric: Analytics metric name
        time_range_hours: Time range for aggregation
    
    Returns:
        Analytics data {metric, value, time_range}
    """
    try:
        from infrastructure.postgres_client import postgres_client
        
        logger.info(f"📈 Getting analytics: {metric} (last {time_range_hours}h)")
        
        analytics = await postgres_client.get_analytics(
            metric=metric,
            time_range_hours=time_range_hours
        )
        
        logger.info(f"✅ Retrieved analytics: {metric}")
        return {
            "success": True,
            "metric": metric,
            "data": analytics,
            "time_range_hours": time_range_hours
        }
        
    except Exception as e:
        logger.error(f"❌ Analytics retrieval failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
