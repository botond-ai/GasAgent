from dataclasses import dataclass, field
from typing import List, Optional, Any

from infrastructure.vector_store import Domain


@dataclass
class ToolCall:
    """Represents a tool call request from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Represents the result of a tool execution."""
    tool_call_id: str
    result: str


@dataclass
class WorkflowState:
    """
    State that flows through the LangGraph workflow.

    Each node reads from and writes to this state.
    """
    # Input
    query: str = ""
    conversation_history: List[dict] = field(default_factory=list)  # Previous turns

    # Router output
    detected_domain: Optional[Domain] = None
    routing_confidence: float = 0.0

    # Retrieval output
    context: str = ""
    citations: List[dict] = field(default_factory=list)

    # Tool calling
    pending_tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    messages: List[dict] = field(default_factory=list)  # Conversation history for tool loop

    # Generation output
    response: str = ""

    # Metadata
    error: Optional[str] = None
