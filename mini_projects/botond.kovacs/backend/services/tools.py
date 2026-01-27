"""
Service layer - LangGraph agent tools implementation.
Following SOLID: Single Responsibility - each tool wrapper has one clear purpose.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError
from pathlib import Path
import json
from datetime import datetime
import logging

from domain.interfaces import (
    IRegulationRAGClient,
    IGasExportClient
)

logger = logging.getLogger(__name__)


class RegulationToolArgs(BaseModel):
    action: str = Field(default="query", description="'query' or 'info'")
    question: Optional[str] = Field(default=None, description="Question to ask about the regulation")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of relevant passages to retrieve")


class RegulationTool:
    """
    Regulation Q&A tool using RAG (Retrieval-Augmented Generation) pipeline.
    
    This tool allows users to ask questions about the content of a regulation (PDF).
    It uses vector similarity search to find relevant passages and generates
    answers based on the retrieved context.
    """
    
    def __init__(self, client: IRegulationRAGClient):
        self.client = client
        self.name = "regulation"
        self.description = """Ask questions about the regulation '2008. évi LX. Gáztörvény'.
This tool uses RAG (Retrieval-Augmented Generation) to search through the regulation content and provide answers.
Useful when user asks about:
- Sections in the regulation (e.g. 1. §, 2. §, etc.)
- Legal requirements and obligations
- Definitions and terms
- Specific paragraphs or chapters
- Quotes or passages from the regulation
Actions: 'query' (ask a question), 'info' (get regulation information)"""
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute regulation-related actions.
        
        Args:
            action: 'query' to ask questions, 'info' to get regulation information
            question: The question to ask about the regulation (required for 'query' action)
            top_k: Number of relevant passages to retrieve (default: 5)
        
        Returns:
            Dict with answer, sources, and metadata
        """
        from observability.metrics import record_tool_call
        try:
            args = RegulationToolArgs(**kwargs)
        except ValidationError as e:
            logger.error(f"RegulationTool argument validation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": "RegulationTool argument validation failed"
            }
        logger.info(f"Regulation tool called: action={args.action}, question={args.question[:50] if args.question else 'None'}...")
        try:
            with record_tool_call("regulation"):
                if args.action == "query":
                    if not args.question:
                        return {
                            "success": False,
                            "error": "Question is required for query action",
                            "system_message": "Regulation query failed: no question provided"
                        }
                    result = await self.client.query(args.question, args.top_k)
                    if "error" in result:
                        return {
                            "success": False,
                            "error": result["error"],
                            "system_message": f"Regulation query failed: {result['error']}"
                        }
                    answer = result.get("answer", "No answer found")
                    sources = result.get("sources", [])
                    regulation_title = result.get("regulation_title", "Unknown")
                    source_refs = []
                    for i, src in enumerate(sources[:3], 1):
                        page = src.get("page", "?")
                        preview = src.get("content_preview", "")[:100]
                        source_refs.append(f"[Page {page}]: {preview}...")
                    summary = f"📚 **Answer from '{regulation_title}':**\n\n{answer}"
                    if source_refs:
                        summary += f"\n\n**Sources:**\n" + "\n".join(source_refs)
                    return {
                        "success": True,
                        "message": summary,
                        "data": result,
                        "system_message": f"Found answer from regulation '{regulation_title}' using {len(sources)} source passages"
                    }
                elif args.action == "info":
                    result = await self.client.get_regulation_info()
                    if "error" in result:
                        return {
                            "success": False,
                            "error": result["error"],
                            "system_message": f"Failed to get regulation info: {result['error']}"
                        }
                    title = result.get("title", "Unknown")
                    chunks = result.get("chunks_count", 0)
                    pages = result.get("pages_count", "N/A")
                    status = result.get("status", "unknown")
                    summary = f"📖 **Regulation Information:**\n"
                    summary += f"- **Title:** {title}\n"
                    summary += f"- **Pages:** {pages}\n"
                    summary += f"- **Indexed chunks:** {chunks}\n"
                    summary += f"- **Status:** {status}"
                    return {
                        "success": True,
                        "message": summary,
                        "data": result,
                        "system_message": f"Regulation '{title}' is loaded with {chunks} indexed chunks"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Unknown action: {args.action}",
                        "system_message": f"Unknown regulation action: {args.action}. Use: query, info"
                    }
        except Exception as e:
            logger.error(f"Regulation tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Regulation tool failed: {e}"
            }


class GasExportToolArgs(BaseModel):
    pointLabel: str = Field(..., description="Export point label (e.g. 'VIP Bereg')")
    from_: str = Field(..., alias="from", description="Start date (YYYY-MM-DD)")
    to: str = Field(..., description="End date (YYYY-MM-DD)")


class GasExportTool:
    """
    Gas Exported Quantity tool using Transparency.host API.
    This tool allows users to query exported gas quantity (kWh) for a given point and date range.
    """
    def __init__(self, client: IGasExportClient):
        self.client = client
        self.name = "gas_exported_quantity"
        self.description = (
            "Get exported gas quantity (kWh) for a given point and date range using Transparency.host. "
            "Params: pointLabel (e.g. 'VIP Bereg'), from (YYYY-MM-DD), to (YYYY-MM-DD). "
            "Lists daily values and total for the period."
        )

    async def execute(self, **kwargs) -> dict:
        """
        Execute gas export query. Accepts both 'from'/'to' and 'periodFrom'/'periodTo' for compatibility.
        """
        from observability.metrics import record_tool_call
        try:
            args = GasExportToolArgs(**kwargs)
        except ValidationError as e:
            logger.error(f"GasExportTool argument validation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": "GasExportTool argument validation failed"
            }
        try:
            with record_tool_call("gas_exported_quantity"):
                result = await self.client.get_exported_quantity(args.pointLabel, args.from_, args.to)
                if not result.get("success"):
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                        "system_message": f"Gas export query failed: {result.get('error', 'Unknown error')}"
                    }
                # Format the response
                total = result.get("total", 0)
                results = result.get("results", [])
                point = result.get("point_label", args.pointLabel)
                period_from = result.get("period_from", args.from_)
                period_to = result.get("period_to", args.to)
                summary = f"⛽ **Gas Exported Quantity for '{point}':**\n\n"
                summary += f"Period: {period_from} to {period_to}\n"
                summary += f"Total: {total:,.0f} kWh\n\n"
                summary += "**Details:**\n"
                for r in results:
                    summary += f"- Date: {r.get('date')} | Value: {r.get('value'):,.0f} {r.get('unit', 'kWh')} | Indicator: {r.get('indicator')} | Operator: {r.get('operatorLabel')} | Status: {r.get('flowStatus')}\n"
                return {
                    "success": True,
                    "message": summary,
                    "data": result,
                    "system_message": result.get("system_message", "Gas export query succeeded.")
                }
        except Exception as e:
            logger.error(f"GasExportTool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"GasExportTool failed: {e}"
            }
