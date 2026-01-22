import json
from typing import Optional

from infrastructure.openai_gateway import OpenAIGateway
from infrastructure.tools.tool_executor import ToolExecutor
from workflows.state import WorkflowState, ToolCall


class GenerateNode:
    """
    Generates responses using the LLM with tool calling support.

    Single Responsibility: LLM response generation (with optional tool use).
    """

    SYSTEM_PROMPT = """
You have access to tools for:
- Currency conversion (convert_currency)
- US holiday information (is_us_holiday, list_us_holidays)
- Jira ticket creation (create_jira_ticket)
- Slack messaging (send_slack_message)

Rules:
- Use the provided context from the knowledge base when relevant
- Include citations [doc_id] when using knowledge base context
"""

    def __init__(
        self,
        openai_gateway: OpenAIGateway,
        tool_executor: Optional[ToolExecutor] = None
    ):
        self.openai_gateway = openai_gateway
        self.tool_executor = tool_executor
        self.tools = tool_executor.get_tool_definitions() if tool_executor else []

    async def __call__(self, state: WorkflowState) -> WorkflowState:
        """Generate response, potentially requesting tool calls."""
        try:
            # Build messages from state
            if not state.messages:
                state.messages = self._build_initial_messages(state)

            # Add tool results to messages if we have any
            if state.tool_results:
                for result in state.tool_results:
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": result.result
                    })
                state.tool_results = []  # Clear after adding to messages

            # Call LLM with tools
            response_message = await self.openai_gateway.get_completion_with_tools(
                messages=state.messages,
                tools=self.tools if self.tools else None
            )

            # Check if LLM wants to call tools
            if response_message.get("tool_calls"):
                # Store assistant message with tool calls
                state.messages.append(response_message)

                # Parse tool calls
                state.pending_tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=json.loads(tc["function"]["arguments"])
                    )
                    for tc in response_message["tool_calls"]
                ]
            else:
                # Final response
                state.response = response_message.get("content", "")
                state.pending_tool_calls = []

        except Exception as e:
            state.error = f"Generation error: {str(e)}"
            state.response = "An error occurred while generating the response."

        return state

    def _build_initial_messages(self, state: WorkflowState) -> list[dict]:
        """Build initial messages with system prompt, history, and user query."""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        # Add conversation history from previous turns
        if state.conversation_history:
            messages.extend(state.conversation_history)

        # Add context if available (for current query)
        if state.context:
            context_msg = self._build_context_message(state)
            messages.append({"role": "user", "content": context_msg})

        # Add current user query
        messages.append({"role": "user", "content": state.query})

        return messages

    def _build_context_message(self, state: WorkflowState) -> str:
        """Build context message from retrieved documents."""
        citations_info = "\n".join([
            f"- [{c['doc_id']}] {c['title']} (relevance: {c['score']:.2f})"
            for c in state.citations
        ])

        return f"""Here is relevant context from the knowledge base:

{state.context}

Available sources:
{citations_info}

Use this context to answer the following question if relevant."""
