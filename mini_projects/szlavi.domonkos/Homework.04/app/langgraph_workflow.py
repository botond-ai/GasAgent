"""LangGraph workflow for AI Meeting Assistant.

Orchestrates a multi-step agent workflow with plan generation, tool routing,
execution, and summary generation using LangGraph state management.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Tuple

import openai
from langgraph.graph import END, StateGraph

from .google_calendar import GoogleCalendarService
from .rag_agent import RAGAgent
from .tool_clients import IPAPIGeolocationClient
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class ToolType(str, Enum):
    """Available tool types."""

    GOOGLE_CALENDAR = "google_calendar"
    IP_GEOLOCATION = "ip_geolocation"
    RAG_SEARCH = "rag_search"
    NONE = "none"


@dataclass
class ExecutionStep:
    """Represents a single execution step in the workflow."""

    step_id: int
    action: str
    tool: ToolType
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    status: str = "pending"  # pending, in_progress, completed, failed


@dataclass
class WorkflowState:
    """State object for LangGraph workflow."""

    user_input: str
    execution_plan: List[ExecutionStep] = field(default_factory=list)
    current_step_index: int = 0
    executed_steps: List[ExecutionStep] = field(default_factory=list)
    tool_outputs: Dict[str, Any] = field(default_factory=dict)
    observations: List[str] = field(default_factory=list)
    meeting_summary: Optional[str] = None
    final_answer: Optional[str] = None
    error_messages: List[str] = field(default_factory=list)


class MeetingAssistantWorkflow:
    """LangGraph-based workflow for meeting assistant operations."""

    def __init__(
        self,
        api_key: str,
        vector_store: VectorStore,
        rag_agent: RAGAgent,
        google_calendar_service: Optional[GoogleCalendarService] = None,
        geolocation_client: Optional[IPAPIGeolocationClient] = None,
        llm_model: str = "gpt-4o-mini",
        llm_temperature: float = 0.7,
        llm_max_tokens: int = 1024,
    ) -> None:
        """Initialize the workflow.

        Args:
            api_key: OpenAI API key
            vector_store: ChromaVectorStore instance for RAG
            rag_agent: RAGAgent for generating responses
            google_calendar_service: Optional Google Calendar service
            geolocation_client: Optional IP geolocation client
            llm_model: LLM model name
            llm_temperature: LLM temperature
            llm_max_tokens: LLM max tokens
        """
        self.api_key = api_key
        self.vector_store = vector_store
        self.rag_agent = rag_agent
        self.google_calendar_service = google_calendar_service
        self.geolocation_client = geolocation_client
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature
        self.llm_max_tokens = llm_max_tokens

        # Build the workflow graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build and return the LangGraph workflow."""
        graph = StateGraph(WorkflowState)

        # Add nodes
        graph.add_node("plan_node", self.plan_node)
        graph.add_node("executor_loop", self.executor_loop)
        graph.add_node("tool_router", self.tool_router)
        graph.add_node("action_node", self.action_node)
        graph.add_node("observation_node", self.observation_node)
        graph.add_node("summary_node", self.summary_node)
        graph.add_node("final_answer_node", self.final_answer_node)

        # Set entry point
        graph.set_entry_point("plan_node")

        # Add edges
        graph.add_edge("plan_node", "executor_loop")
        graph.add_conditional_edges(
            "executor_loop",
            self._should_continue_execution,
            {
                "continue": "tool_router",
                "done": "summary_node",
            },
        )
        graph.add_edge("tool_router", "action_node")
        graph.add_edge("action_node", "observation_node")
        graph.add_edge("observation_node", "executor_loop")
        graph.add_edge("summary_node", "final_answer_node")
        graph.add_edge("final_answer_node", END)

        return graph.compile()

    def plan_node(self, state: WorkflowState) -> WorkflowState:
        """Generate execution plan from user input and RAG context.

        This node:
        1. Analyzes the user input
        2. Retrieves relevant context from RAG database
        3. Determines required tools
        4. Creates an execution plan with steps
        """
        logger.info("Planning execution steps for input: %s", state.user_input)

        # Retrieve relevant documents from RAG
        retrieved_docs = self.vector_store.search(state.user_input, k=3)
        logger.info("Retrieved %d relevant documents", len(retrieved_docs))

        # Build context from retrieved docs
        context = self._build_rag_context(retrieved_docs)

        # Generate plan using LLM
        plan_prompt = self._create_plan_prompt(state.user_input, context)
        plan_text = self._call_llm(plan_prompt)

        # Parse plan into execution steps
        steps = self._parse_execution_plan(plan_text)
        state.execution_plan = steps

        logger.info("Generated execution plan with %d steps", len(steps))
        state.observations.append(f"Generated execution plan: {len(steps)} steps")

        return state

    def executor_loop(self, state: WorkflowState) -> WorkflowState:
        """Execute the planned steps one by one."""
        logger.info(
            "Executor loop: current_step=%d, total_steps=%d",
            state.current_step_index,
            len(state.execution_plan),
        )
        return state

    def _should_continue_execution(self, state: WorkflowState) -> str:
        """Determine if there are more steps to execute."""
        if state.current_step_index < len(state.execution_plan):
            return "continue"
        return "done"

    def tool_router(self, state: WorkflowState) -> WorkflowState:
        """Route to appropriate tool based on current step.

        Analyzes the current execution step and determines which tool should be used:
        - Google Calendar tool
        - IP Geolocation tool
        - RAG search
        - None (if it's just information gathering)
        """
        current_step = state.execution_plan[state.current_step_index]
        logger.info(
            "Tool router: processing step %d - action=%s",
            current_step.step_id,
            current_step.action,
        )

        # Determine tool based on step action
        if "calendar" in current_step.action.lower():
            current_step.tool = ToolType.GOOGLE_CALENDAR
        elif (
            "location" in current_step.action.lower()
            or "ip" in current_step.action.lower()
        ):
            current_step.tool = ToolType.IP_GEOLOCATION
        elif (
            "search" in current_step.action.lower()
            or "retrieve" in current_step.action.lower()
        ):
            current_step.tool = ToolType.RAG_SEARCH
        else:
            current_step.tool = ToolType.NONE

        logger.info("Tool selected: %s", current_step.tool.value)
        state.observations.append(f"Tool router selected: {current_step.tool.value}")

        return state

    def action_node(self, state: WorkflowState) -> WorkflowState:
        """Execute the tool action for the current step."""
        current_step = state.execution_plan[state.current_step_index]
        current_step.status = "in_progress"

        logger.info(
            "Executing action: %s with tool: %s", current_step.action, current_step.tool
        )

        try:
            if current_step.tool == ToolType.GOOGLE_CALENDAR:
                result = self._execute_calendar_action(current_step)
            elif current_step.tool == ToolType.IP_GEOLOCATION:
                result = self._execute_geolocation_action(current_step)
            elif current_step.tool == ToolType.RAG_SEARCH:
                result = self._execute_rag_search_action(current_step)
            else:
                result = {"status": "skipped", "message": "No tool action needed"}

            current_step.result = result
            current_step.status = "completed"
            state.tool_outputs[f"step_{current_step.step_id}"] = result
            logger.info("Action completed successfully: %s", current_step.action)

        except Exception as e:
            logger.error("Error executing action: %s", str(e))
            current_step.status = "failed"
            current_step.result = {"error": str(e)}
            state.error_messages.append(f"Step {current_step.step_id} failed: {str(e)}")

        return state

    def observation_node(self, state: WorkflowState) -> WorkflowState:
        """Check and update state based on action results."""
        current_step = state.execution_plan[state.current_step_index]
        logger.info(
            "Observation node: step %d status=%s",
            current_step.step_id,
            current_step.status,
        )

        # Add observation about the result
        if current_step.status == "completed":
            obs = f"Step {current_step.step_id} ({current_step.action}) completed. Result: {current_step.result}"
        else:
            obs = (
                f"Step {current_step.step_id} ({current_step.action}) failed with error"
            )

        state.observations.append(obs)

        # Move to next step
        state.executed_steps.append(current_step)
        state.current_step_index += 1

        logger.info("Moving to next step: index=%d", state.current_step_index)

        return state

    def summary_node(self, state: WorkflowState) -> WorkflowState:
        """Generate meeting summary using LLM.

        Combines:
        - Original user input
        - Retrieved documents from RAG
        - Tool execution results
        - Generated insights
        """
        logger.info("Generating meeting summary")

        # Build context for summary
        summary_context = self._build_summary_context(state)

        # Generate summary using LLM
        summary_prompt = self._create_summary_prompt(state.user_input, summary_context)
        summary = self._call_llm(summary_prompt)

        state.meeting_summary = summary
        state.observations.append(f"Meeting summary generated")

        logger.info("Summary generated: %d characters", len(summary))

        return state

    def final_answer_node(self, state: WorkflowState) -> WorkflowState:
        """Generate final answer listing all executed steps.

        Creates a comprehensive summary of:
        - What was requested
        - Steps that were executed
        - Results from each step
        - Overall meeting summary
        """
        logger.info("Generating final answer")

        final_answer = self._create_final_answer(state)
        state.final_answer = final_answer

        logger.info("Final answer prepared")

        return state

    def run(self, user_input: str) -> Dict[str, Any]:
        """Run the workflow with the given user input.

        Args:
            user_input: User query or command

        Returns:
            Final workflow output with all results
        """
        logger.info("Starting workflow with input: %s", user_input)

        initial_state = WorkflowState(user_input=user_input)
        final_state = self.graph.invoke(initial_state)

        return {
            "user_input": final_state.user_input,
            "execution_plan": [
                {
                    "step_id": step.step_id,
                    "action": step.action,
                    "tool": step.tool.value,
                    "status": step.status,
                    "result": step.result,
                }
                for step in final_state.execution_plan
            ],
            "executed_steps": len(final_state.executed_steps),
            "meeting_summary": final_state.meeting_summary,
            "final_answer": final_state.final_answer,
            "observations": final_state.observations,
            "errors": final_state.error_messages,
        }

    # ========== Helper methods ==========

    def _build_rag_context(self, retrieved_docs: List[Tuple[str, float, str]]) -> str:
        """Build context string from retrieved documents."""
        if not retrieved_docs:
            return "(No relevant documents found.)"

        context_parts = []
        for i, (doc_id, score, text) in enumerate(retrieved_docs, start=1):
            context_parts.append(f"[Doc {i} (score: {score:.4f})]\n{text[:200]}...")

        return "\n\n".join(context_parts)

    def _build_summary_context(self, state: WorkflowState) -> str:
        """Build context for summary generation."""
        parts = []

        # Add executed steps
        parts.append("Executed Steps:")
        for step in state.executed_steps:
            parts.append(f"  - {step.action} ({step.tool.value}): {step.status}")
            if step.result:
                parts.append(f"    Result: {json.dumps(step.result, indent=2)[:200]}")

        # Add observations
        parts.append("\nKey Observations:")
        for obs in state.observations[-5:]:  # Last 5 observations
            parts.append(f"  - {obs}")

        return "\n".join(parts)

    def _create_plan_prompt(self, user_input: str, context: str) -> str:
        """Create prompt for plan generation."""
        return f"""You are an AI meeting assistant. Based on the user's request and relevant context, 
generate an execution plan with specific steps.

User Request: {user_input}

Relevant Context from Documents:
{context}

Generate a JSON response with an "execution_plan" array. Each step should have:
- "step_id": number
- "action": description of what to do
- "required_tool": one of ["google_calendar", "ip_geolocation", "rag_search", "none"]
- "parameters": dict of parameters needed

Format:
{{
  "execution_plan": [
    {{"step_id": 1, "action": "...", "required_tool": "...", "parameters": {{...}}}},
    ...
  ]
}}
"""

    def _create_summary_prompt(self, user_input: str, context: str) -> str:
        """Create prompt for summary generation."""
        return f"""Generate a comprehensive meeting summary based on:

User Request: {user_input}

Workflow Execution Context:
{context}

Provide a well-structured summary that includes key decisions, action items, and next steps.
Keep it concise but complete."""

    def _parse_execution_plan(self, plan_text: str) -> List[ExecutionStep]:
        """Parse LLM response into execution steps."""
        try:
            # Extract JSON from response
            if "```json" in plan_text:
                json_str = plan_text.split("```json")[1].split("```")[0].strip()
            elif "{" in plan_text:
                json_str = plan_text[plan_text.find("{") : plan_text.rfind("}") + 1]
            else:
                json_str = plan_text

            data = json.loads(json_str)
            steps = []

            for step_data in data.get("execution_plan", []):
                tool_str = step_data.get("required_tool", "none").lower()
                try:
                    tool = ToolType[tool_str.upper().replace("-", "_")]
                except KeyError:
                    tool = ToolType.NONE

                step = ExecutionStep(
                    step_id=step_data.get("step_id", len(steps) + 1),
                    action=step_data.get("action", ""),
                    tool=tool,
                    parameters=step_data.get("parameters", {}),
                )
                steps.append(step)

            return (
                steps
                if steps
                else [ExecutionStep(1, "Default action", ToolType.NONE, {})]
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Could not parse execution plan: %s", str(e))
            # Return default step
            return [ExecutionStep(1, "Default search action", ToolType.RAG_SEARCH, {})]

    def _call_llm(self, prompt: str) -> str:
        """Call OpenAI LLM."""
        try:
            response = openai.ChatCompletion.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.llm_temperature,
                max_tokens=self.llm_max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("LLM call failed: %s", str(e))
            return "Error generating response"

    def _execute_calendar_action(self, step: ExecutionStep) -> Dict[str, Any]:
        """Execute Google Calendar action."""
        if not self.google_calendar_service:
            return {"error": "Google Calendar service not configured"}

        action_type = step.parameters.get("action_type", "list_events")

        try:
            if action_type == "list_events":
                events = self.google_calendar_service.get_upcoming_events(5)
                return {"status": "success", "events": events, "count": len(events)}
            elif action_type == "get_today":
                events = self.google_calendar_service.get_today_events()
                return {"status": "success", "events": events, "count": len(events)}
            else:
                return {"status": "unknown_action", "action": action_type}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _execute_geolocation_action(self, step: ExecutionStep) -> Dict[str, Any]:
        """Execute IP geolocation action."""
        if not self.geolocation_client:
            return {"error": "Geolocation service not configured"}

        ip_address = step.parameters.get("ip", None)

        try:
            result = self.geolocation_client.get_location_from_ip(
                ip_address or "8.8.8.8"
            )
            if result:
                return {"status": "success", "location": result}
            else:
                return {"status": "error", "message": "Could not retrieve location"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _execute_rag_search_action(self, step: ExecutionStep) -> Dict[str, Any]:
        """Execute RAG search action."""
        query = step.parameters.get("query", "")

        try:
            retrieved_docs = self.vector_store.search(query, k=3)
            return {
                "status": "success",
                "query": query,
                "results_count": len(retrieved_docs),
                "documents": [
                    {"id": doc_id, "score": score, "text": text[:150]}
                    for doc_id, score, text in retrieved_docs
                ],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _create_final_answer(self, state: WorkflowState) -> str:
        """Create comprehensive final answer."""
        lines = []

        lines.append("=" * 60)
        lines.append("MEETING ASSISTANT WORKFLOW - FINAL REPORT")
        lines.append("=" * 60)

        lines.append(f"\nUser Request: {state.user_input}")

        lines.append(f"\nExecution Plan ({len(state.execution_plan)} steps):")
        for step in state.execution_plan:
            status_icon = (
                "✓"
                if step.status == "completed"
                else "✗" if step.status == "failed" else "⏳"
            )
            lines.append(
                f"  {status_icon} Step {step.step_id}: {step.action} ({step.tool.value}) - {step.status}"
            )

        if state.meeting_summary:
            lines.append(f"\nMeeting Summary:\n{state.meeting_summary}")

        if state.error_messages:
            lines.append(f"\nWarnings/Errors:")
            for error in state.error_messages:
                lines.append(f"  ⚠ {error}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)
