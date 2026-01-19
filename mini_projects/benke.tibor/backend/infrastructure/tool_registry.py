"""Simple tool registry to manage tool metadata and execution.

Provides registration, schema lookup, descriptions, and execution with
non-blocking defaults suitable for tests and offline environments.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    schema: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """Registry pattern for tools used by the agent.

    - register: add a tool with metadata and handler
    - get_descriptions: human-readable listing for prompts
    - get_schema: return JSON-like schema (from type hints or provided dict)
    - execute: invoke handler with kwargs; wraps errors
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, name: str, handler: Callable[..., Any], description: str, schema: Optional[Dict[str, Any]] = None) -> None:
        spec = ToolSpec(name=name, description=description, handler=handler, schema=schema or {})
        self._tools[name] = spec

    def get_descriptions(self) -> List[str]:
        return [f"{spec.name}: {spec.description}" for spec in self._tools.values()]

    def get_schema(self, name: str) -> Dict[str, Any]:
        spec = self._tools.get(name)
        if not spec:
            raise ValueError(f"Tool '{name}' is not registered")
        return spec.schema

    def execute(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        spec = self._tools.get(tool_name)
        if not spec:
            raise ValueError(f"Tool '{tool_name}' is not registered")
        try:
            result = spec.handler(**kwargs)
            return {"tool": tool_name, "status": "success", "result": result}
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Tool '{tool_name}' execution failed: {exc}")
            return {"tool": tool_name, "status": "error", "error": str(exc)}

    @classmethod
    def default(cls) -> "ToolRegistry":
        """Create a registry with built-in mockable tools.

        These are lightweight handlers safe for tests and offline runs.
        """
        reg = cls()

        reg.register(
            name="rag_search",
            description="Search knowledge base documents (HR, IT, Finance, Legal, Marketing)",
            handler=lambda query="", domain="general", top_k=5: {
                "query": query,
                "domain": domain,
                "top_k": top_k,
                "hits": []
            },
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "domain": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 20}
                },
                "required": ["query", "domain"]
            }
        )

        reg.register(
            name="jira_create",
            description="Create IT support ticket",
            handler=lambda summary="", description="", priority="medium": {
                "ticket": "SCRUM-001",
                "summary": summary,
                "priority": priority,
                "description": description
            },
            schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]}
                },
                "required": ["summary", "description"]
            }
        )

        reg.register(
            name="email_send",
            description="Send email notification",
            handler=lambda to="", subject="", body="": {
                "to": to,
                "subject": subject,
                "body": body,
                "status": "queued"
            },
            schema={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"}
                },
                "required": ["to", "subject", "body"]
            }
        )

        reg.register(
            name="calculator",
            description="Perform calculations",
            handler=lambda expression="": {
                "expression": expression,
                "result": expression  # placeholder to avoid eval
            },
            schema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"]
            }
        )

        return reg