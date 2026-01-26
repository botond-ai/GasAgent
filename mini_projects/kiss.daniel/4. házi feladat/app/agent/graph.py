"""
LangGraph workflow definition.
Defines the agent graph with nodes, edges, and conditional routing.
"""

import logging
from typing import Literal, Optional

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState, MeetingNotesInput
from app.agent.nodes import NodeExecutor, create_node_executor
from app.llm.ollama_client import OllamaClient
from app.memory.store import MemoryStore
from app.tools.google_calendar import GoogleCalendarTool

logger = logging.getLogger(__name__)


def create_agent_graph(
    llm_client: Optional[OllamaClient] = None,
    memory_store: Optional[MemoryStore] = None,
    calendar_tool: Optional[GoogleCalendarTool] = None,
    use_mock_calendar: bool = False,
) -> StateGraph:
    """
    Create the LangGraph agent workflow.
    
    Architecture:
    
    User Input → Planner → Router ─┬→ Summarizer → Router
                    ↑              ├→ Extractor → Router
                    │              ├→ Validator → Router
                    │              ├→ Guardrail → Router
                    │              ├→ Tool → Router
                    │              └→ Final Answer → END
                    │
                    └── (replan) ──┘
    
    Args:
        llm_client: Optional Ollama client instance
        memory_store: Optional memory store instance
        calendar_tool: Optional calendar tool instance
        use_mock_calendar: If True, use mock calendar for testing
        
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create node executor with dependencies
    executor = create_node_executor(
        llm_client=llm_client,
        memory_store=memory_store,
        calendar_tool=calendar_tool,
        use_mock_calendar=use_mock_calendar,
    )
    
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planner", executor.planner_node)
    workflow.add_node("router", lambda state: state)  # Router is a decision point
    workflow.add_node("summarizer", executor.summarizer_node)
    workflow.add_node("extractor", executor.extractor_node)
    workflow.add_node("validator", executor.validator_node)
    workflow.add_node("guardrail", executor.guardrail_node)
    workflow.add_node("tool", executor.tool_node)
    workflow.add_node("final_answer", executor.final_answer_node)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Add edge from planner to router
    workflow.add_edge("planner", "router")
    
    # Add conditional edges from router
    def route_from_router(state: AgentState) -> str:
        """Determine next node based on current step."""
        return executor.router_node(state)
    
    workflow.add_conditional_edges(
        "router",
        route_from_router,
        {
            "summarizer": "summarizer",
            "extractor": "extractor",
            "validator": "validator",
            "guardrail": "guardrail",
            "tool": "tool",
            "final_answer": "final_answer",
            "planner": "planner",  # For replan
        }
    )
    
    # Add edges from processing nodes back to router
    def should_continue(state: AgentState) -> Literal["continue", "end"]:
        """Check if should continue to next step."""
        return executor.should_continue(state)
    
    for node in ["summarizer", "extractor", "validator", "guardrail", "tool"]:
        workflow.add_conditional_edges(
            node,
            should_continue,
            {
                "continue": "router",
                "end": "final_answer",
            }
        )
    
    # Final answer goes to END
    workflow.add_edge("final_answer", END)
    
    return workflow


def compile_agent(
    llm_client: Optional[OllamaClient] = None,
    memory_store: Optional[MemoryStore] = None,
    calendar_tool: Optional[GoogleCalendarTool] = None,
    use_mock_calendar: bool = False,
):
    """
    Compile and return the agent graph.
    
    Returns:
        Compiled graph ready for invocation
    """
    workflow = create_agent_graph(
        llm_client=llm_client,
        memory_store=memory_store,
        calendar_tool=calendar_tool,
        use_mock_calendar=use_mock_calendar,
    )
    return workflow.compile()


def run_agent(
    notes_text: str,
    user_timezone: str = "Europe/Budapest",
    calendar_id: str = "primary",
    dry_run: bool = False,
    use_mock_calendar: bool = False,
    llm_client: Optional[OllamaClient] = None,
    memory_store: Optional[MemoryStore] = None,
) -> AgentState:
    """
    Run the agent on meeting notes.
    
    Args:
        notes_text: The meeting notes to process
        user_timezone: User's timezone
        calendar_id: Google Calendar ID
        dry_run: If True, don't create calendar event
        use_mock_calendar: If True, use mock calendar
        llm_client: Optional Ollama client
        memory_store: Optional memory store
        
    Returns:
        Final AgentState with results
    """
    # Create input
    input_data = MeetingNotesInput(
        notes_text=notes_text,
        user_timezone=user_timezone,
        calendar_id=calendar_id,
        dry_run=dry_run,
    )
    
    # Create initial state
    initial_state = AgentState(input=input_data)
    
    logger.info(f"Starting agent run {initial_state.run_id}")
    logger.info(f"Dry run: {dry_run}, Timezone: {user_timezone}")
    
    # Compile and run
    agent = compile_agent(
        llm_client=llm_client,
        memory_store=memory_store,
        use_mock_calendar=use_mock_calendar or dry_run,
    )
    
    # Execute
    result = agent.invoke(initial_state)
    
    # LangGraph returns a dict, convert back to AgentState
    if isinstance(result, dict):
        final_state = AgentState(**result)
    else:
        final_state = result
    
    logger.info(f"Agent run {final_state.run_id} completed")
    
    return final_state
