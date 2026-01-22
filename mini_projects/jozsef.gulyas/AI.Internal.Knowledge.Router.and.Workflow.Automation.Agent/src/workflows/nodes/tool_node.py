from infrastructure.tools.tool_executor import ToolExecutor
from workflows.state import WorkflowState, ToolResult


class ToolNode:
    """
    Executes pending tool calls and stores results.

    Single Responsibility: Tool execution.
    """

    def __init__(self, tool_executor: ToolExecutor):
        self.tool_executor = tool_executor

    async def __call__(self, state: WorkflowState) -> WorkflowState:
        """Execute all pending tool calls and store results."""
        if not state.pending_tool_calls:
            return state

        results = []
        for tool_call in state.pending_tool_calls:
            result = await self.tool_executor.execute(
                function_name=tool_call.name,
                arguments=tool_call.arguments
            )
            results.append(ToolResult(
                tool_call_id=tool_call.id,
                result=result
            ))

        # Store results and clear pending calls
        state.tool_results = results
        state.pending_tool_calls = []

        return state
