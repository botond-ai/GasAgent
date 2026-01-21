"""State model for the AI weather agent."""
from typing import Annotated, TypedDict, Sequence
from operator import add
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Result of a tool execution."""
    tool_name: str
    success: bool
    data: dict | None = None
    error_message: str | None = None


class Decision(BaseModel):
    """LLM decision about the next action."""
    action: str = Field(description="One of: call_tool, final_answer")
    tool_name: str | None = Field(default=None, description="One of: geocode_city, get_weather")
    tool_input: dict | None = Field(default=None, description="Tool parameters")
    reason: str = Field(default="", description="Internal reasoning")


class AgentState(TypedDict):
    """State maintained throughout the agent execution."""
    user_prompt: str
    tool_results: Annotated[Sequence[ToolResult], add]
    iteration_count: int
    decision: Decision | None
    final_answer: str | None
