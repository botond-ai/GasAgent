"""LangGraph-based AI agent with ToolNode."""
import json
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from pydantic import ValidationError

from .state import AgentState, Decision, ToolResult
from .llm import GroqClient
from .prompts import DECISION_PROMPT, ANSWER_PROMPT
from .weather_graph import get_weather_via_subgraph
from .tools.time_tool import get_time


# Maximum number of tool call iterations to prevent infinite loops
MAX_ITERATIONS = 3


# Define tools using @tool decorator for LangGraph ToolNode
@tool
def get_time_tool() -> dict:
    """Get the current server time in ISO format.
    
    Returns:
        Dictionary with current_time and timezone
    """
    result = get_time()
    return {
        "current_time": result.current_time,
        "timezone": result.timezone
    }


@tool
def get_weather_tool(question: str) -> dict:
    """Get weather information by running the dedicated Weather subgraph.
    
    This tool handles:
    - Time parsing (today, tomorrow, yesterday, specific dates)
    - Location geocoding (or IP-based fallback)
    - Weather fetching from OpenWeather One Call 3.0
    
    Args:
        question: The original user question about weather
        
    Returns:
        Dictionary with weather data or error message
    """
    result = get_weather_via_subgraph(question)
    
    if result.success:
        return {
            "success": True,
            "temperature_c": result.temperature_c,
            "description": result.description,
            "wind_speed": result.wind_speed,
            "humidity": result.humidity,
            "location_name": result.location_name,
            "date": result.date,
            "is_forecast": result.is_forecast
        }
    else:
        return {
            "success": False,
            "error_message": result.error_message
        }


# Create tools list for ToolNode
tools = [get_time_tool, get_weather_tool]


def read_user_prompt_node(state: AgentState) -> AgentState:
    """Node 1: Read user prompt (already provided via state initialization)."""
    # The user prompt is already set during initialization
    # This node exists for graph structure completeness
    return state


def decision_node(state: AgentState) -> AgentState:
    """Node 2: LLM decides whether to call a tool or provide final answer."""
    llm = GroqClient()
    
    # Format tool results for LLM
    tool_results_str = ""
    if state.get("tool_results"):
        for result in state["tool_results"]:
            tool_results_str += f"\n\nEszköz: {result.tool_name}\n"
            if result.success:
                tool_results_str += f"Sikeres: {json.dumps(result.data, ensure_ascii=False)}"
            else:
                tool_results_str += f"Sikertelen: {result.error_message}"
    else:
        tool_results_str = "Még nincsenek eszköz eredmények."
    
    # Create decision prompt
    prompt = DECISION_PROMPT.format(
        user_prompt=state["user_prompt"],
        tool_results=tool_results_str,
        iteration_count=state.get("iteration_count", 0)
    )
    
    try:
        # Get LLM decision (JSON only)
        response_dict = llm.invoke_json(
            "You must respond with valid JSON only. No other text.",
            prompt
        )
        decision = Decision(**response_dict)
        
        # Validate decision
        if decision.action not in ["call_tool", "final_answer"]:
            # Fallback to final answer on invalid action
            decision = Decision(
                action="final_answer",
                reason="Invalid action from LLM, falling back to final answer"
            )
        
        if decision.action == "call_tool":
            if not decision.tool_name or decision.tool_name not in ["get_weather", "get_time"]:
                # Fallback if invalid tool
                decision = Decision(
                    action="final_answer",
                    reason="Invalid tool name, falling back to final answer"
                )
        
        return {**state, "decision": decision}
        
    except (json.JSONDecodeError, ValidationError, Exception) as e:
        # Fallback on any error
        decision = Decision(
            action="final_answer",
            reason=f"LLM response parsing failed: {str(e)}"
        )
        return {**state, "decision": decision}


def tool_execution_wrapper(state: AgentState) -> AgentState:
    """Wrapper around ToolNode execution to convert results to our ToolResult format.
    
    This node:
    1. Extracts tool_name and tool_input from decision
    2. Calls the appropriate tool
    3. Wraps result in ToolResult
    4. Increments iteration counter
    """
    decision = state.get("decision")
    
    if not decision or not decision.tool_name:
        # Safety check
        error_result = ToolResult(
            tool_name="unknown",
            success=False,
            error_message="Nincs érvényes eszköz hívás"
        )
        return {
            **state,
            "tool_results": state.get("tool_results", []) + [error_result],
            "iteration_count": state.get("iteration_count", 0) + 1
        }
    
    tool_name = decision.tool_name
    tool_input = decision.tool_input or {}
    
    # Execute the appropriate tool
    try:
        if tool_name == "get_time":
            result = get_time_tool.invoke({})
            tool_result = ToolResult(
                tool_name=tool_name,
                success=True,
                data=result
            )
        elif tool_name == "get_weather":
            # Pass the original user prompt to weather subgraph
            result = get_weather_tool.invoke({"question": state["user_prompt"]})
            
            if result.get("success"):
                tool_result = ToolResult(
                    tool_name=tool_name,
                    success=True,
                    data=result
                )
            else:
                tool_result = ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error_message=result.get("error_message", "Ismeretlen hiba")
                )
        else:
            tool_result = ToolResult(
                tool_name=tool_name,
                success=False,
                error_message=f"Ismeretlen eszköz: {tool_name}"
            )
    except Exception as e:
        tool_result = ToolResult(
            tool_name=tool_name,
            success=False,
            error_message=f"Eszköz végrehajtási hiba: {str(e)}"
        )
    
    # Update state with tool result and increment iteration count
    return {
        **state,
        "tool_results": state.get("tool_results", []) + [tool_result],
        "iteration_count": state.get("iteration_count", 0) + 1
    }


def answer_node(state: AgentState) -> AgentState:
    """Node 4: Generate final answer using LLM."""
    llm = GroqClient()
    
    # Format tool results for LLM
    tool_results_str = ""
    if state.get("tool_results"):
        for result in state["tool_results"]:
            tool_results_str += f"\n\nEszköz: {result.tool_name}\n"
            if result.success:
                tool_results_str += f"Eredmény: {json.dumps(result.data, ensure_ascii=False, indent=2)}"
            else:
                tool_results_str += f"Hiba: {result.error_message}"
    else:
        tool_results_str = "Nincsenek eszköz eredmények."
    
    # Create answer prompt
    prompt = ANSWER_PROMPT.format(
        user_prompt=state["user_prompt"],
        tool_results=tool_results_str
    )
    
    try:
        # Get final answer from LLM
        answer = llm.invoke(
            "Te egy barátságos asszisztens vagy. KÖTELEZŐ: Csak magyarul válaszolj!",
            prompt
        )
        return {**state, "final_answer": answer.strip()}
    except Exception as e:
        # Check if rate limit error
        error_msg = str(e)
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            return {
                **state,
                "final_answer": "Jelenleg túl sok kérés érkezett. Kérlek, próbáld újra pár perc múlva."
            }
        # Fallback answer on other errors
        import sys
        print(f"ERROR in answer_node: {e}", file=sys.stderr)
        return {
            **state,
            "final_answer": "Sajnos hiba történt a válasz generálása során. Kérlek, próbáld újra később."
        }


def should_continue(state: AgentState) -> Literal["tool_node", "answer_node"]:
    """Router function: decide whether to call tool or provide answer.
    
    Routes:
    - 2 -> 3 (call tool)
    - 2 -> 4 (final answer)
    """
    decision = state.get("decision")
    iteration_count = state.get("iteration_count", 0)
    
    # Check if max iterations reached
    if iteration_count >= MAX_ITERATIONS:
        return "answer_node"
    
    # Route based on LLM decision
    if decision and decision.action == "call_tool":
        return "tool_node"
    else:
        return "answer_node"


def create_graph() -> StateGraph:
    """Create and compile the LangGraph StateGraph.
    
    Graph structure:
    - Node 1: read_user_prompt
    - Node 2: decision_node
    - Node 3: tool_node (ToolNode wrapper)
    - Node 4: answer_node
    
    Edges:
    - 1 -> 2
    - 2 -> 3 (conditional)
    - 3 -> 2
    - 2 -> 4 (conditional)
    - 4 -> END
    """
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("read_user_prompt", read_user_prompt_node)
    workflow.add_node("decision_node", decision_node)
    workflow.add_node("tool_node", tool_execution_wrapper)
    workflow.add_node("answer_node", answer_node)
    
    # Add edges
    workflow.add_edge("read_user_prompt", "decision_node")
    workflow.add_conditional_edges(
        "decision_node",
        should_continue,
        {
            "tool_node": "tool_node",
            "answer_node": "answer_node"
        }
    )
    workflow.add_edge("tool_node", "decision_node")  # 3 -> 2
    workflow.add_edge("answer_node", END)
    
    # Set entry point
    workflow.set_entry_point("read_user_prompt")
    
    # Compile the graph
    return workflow.compile()


def run_agent(user_prompt: str) -> str:
    """Run the agent with a user prompt.
    
    Args:
        user_prompt: User's question or request
        
    Returns:
        Final answer from the agent
    """
    # Create graph
    graph = create_graph()
    
    # Initialize state
    initial_state = {
        "user_prompt": user_prompt,
        "tool_results": [],
        "iteration_count": 0,
        "decision": None,
        "final_answer": None
    }
    
    # Run the graph
    final_state = graph.invoke(initial_state)
    
    # Return final answer
    return final_state.get("final_answer", "Nem sikerült választ generálni.")
