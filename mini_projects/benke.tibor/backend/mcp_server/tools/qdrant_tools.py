"""
Qdrant MCP Tools - Wraps QdrantRAGClient for MCP protocol.

Tools:
- search: Semantic search in knowledge base
- retrieve_by_ids: Retrieve specific points by ID
"""

import logging
from typing import Dict, Any, List

try:
    from mcp.types import Tool, TextContent
except ImportError:
    Tool = None
    TextContent = None

logger = logging.getLogger(__name__)


def search_tool() -> Tool:
    """
    Semantic search tool.
    
    MCP Tool definition for Qdrant semantic search.
    """
    return Tool(
        name="qdrant_search",
        description="Semantic search in the knowledge base (Qdrant)",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (natural language)"
                },
                "domain": {
                    "type": "string",
                    "enum": ["hr", "it", "marketing", "finance", "legal", "general"],
                    "description": "Domain filter"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results (default: 5)"
                }
            },
            "required": ["query"]
        }
    )


async def search(
    query: str,
    domain: str = "general",
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Semantic search via QdrantRAGClient.
    
    Args:
        query: Search query
        domain: Domain filter (hr, it, marketing, etc.)
        top_k: Number of results
    
    Returns:
        Search results {citations: [...], total, latency_ms}
    """
    try:
        from infrastructure.qdrant_rag_client import QdrantRAGClient
        from domain.models import DomainType
        
        logger.info(f"🔍 Qdrant search: '{query}' in {domain}")
        
        rag_client = QdrantRAGClient()
        citations = await rag_client.retrieve(
            query=query,
            domain=DomainType(domain.upper()),
            top_k=top_k
        )
        
        results = [
            {
                "title": c.title,
                "content": c.content[:200],  # Preview
                "score": c.score,
                "url": c.url
            }
            for c in citations
        ]
        
        logger.info(f"✅ Found {len(results)} results")
        return {
            "success": True,
            "citations": results,
            "total": len(results)
        }
        
    except Exception as e:
        logger.error(f"❌ Qdrant search failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def retrieve_by_ids_tool() -> Tool:
    """
    Retrieve points by ID.
    
    MCP Tool definition for retrieving specific points.
    """
    return Tool(
        name="qdrant_retrieve_by_ids",
        description="Retrieve knowledge base points by their IDs",
        inputSchema={
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of point IDs to retrieve"
                }
            },
            "required": ["ids"]
        }
    )


async def retrieve_by_ids(ids: List[str]) -> Dict[str, Any]:
    """
    Retrieve specific points by ID via QdrantRAGClient.
    
    Args:
        ids: List of point IDs
    
    Returns:
        Points data {points: [...], total}
    """
    try:
        from infrastructure.qdrant_rag_client import QdrantRAGClient
        
        logger.info(f"🔍 Retrieving {len(ids)} points from Qdrant")
        
        rag_client = QdrantRAGClient()
        points = await rag_client.retrieve_by_ids(ids)
        
        logger.info(f"✅ Retrieved {len(points)} points")
        return {
            "success": True,
            "points": points,
            "total": len(points)
        }
        
    except Exception as e:
        logger.error(f"❌ Qdrant retrieve failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
