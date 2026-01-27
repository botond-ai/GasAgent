"""LangGraph-based AI weather agent."""
import json
from typing import Literal
from langgraph.graph import StateGraph, END
from pydantic import ValidationError

from .state import AgentState, Decision, ToolResult
from .llm import OllamaClient
from .prompts import DECISION_PROMPT, ANSWER_PROMPT
from .tools import geocode_city, get_weather, parse_time


# Maximum number of tool call iterations to prevent infinite loops
MAX_ITERATIONS = 3


def read_user_prompt_node(state: AgentState) -> AgentState:
    """Node 1: Read user prompt (already provided via state initialization)."""
    # The user prompt is already set during initialization
    # This node exists for graph structure completeness
    return state


def decision_node(state: AgentState) -> AgentState:
    """Node 2: LLM decides whether to call a tool or provide final answer."""
    llm = OllamaClient()
    
    # Format tool results for LLM with clear status
    tool_status = {
        "parse_time": False,
        "geocode_city": False,
        "get_weather": False
    }
    
    tool_results_str = ""
    if state.get("tool_results"):
        for result in state["tool_results"]:
            if result.success:
                tool_status[result.tool_name] = True
            tool_results_str += f"\n{result.tool_name}: {'✓ SIKERES' if result.success else '✗ SIKERTELEN'}"
            if result.success and result.data:
                tool_results_str += f" (adat: {json.dumps(result.data, ensure_ascii=False)})"
            elif result.error_message:
                tool_results_str += f" ({result.error_message})"
    else:
        tool_results_str = "NINCS MÉG"
    
    # Add clear summary
    tool_results_str = f"""DONE: parse_time={tool_status['parse_time']}, geocode_city={tool_status['geocode_city']}, get_weather={tool_status['get_weather']}

DETAILS:{tool_results_str}"""
    
    # Create decision prompt
    prompt = DECISION_PROMPT.format(
        user_prompt=state["user_prompt"],
        tool_results=tool_results_str,
        iteration_count=state.get("iteration_count", 0)
    )
    
    try:
        # Get LLM decision (JSON only)
        response_dict = llm.invoke_json("You must respond with valid JSON only. No other text.", prompt)
        decision = Decision(**response_dict)
        
        # Validate decision
        if decision.action not in ["call_tool", "final_answer"]:
            # Fallback to final answer on invalid action
            decision = Decision(
                action="final_answer",
                reason="Invalid action from LLM, falling back to final answer"
            )
        
        if decision.action == "call_tool":
            if not decision.tool_name or decision.tool_name not in ["parse_time", "geocode_city", "get_weather"]:
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


def tool_node(state: AgentState) -> AgentState:
    """Node 3: Execute the requested tool."""
    decision = state.get("decision")
    
    if not decision or not decision.tool_name or not decision.tool_input:
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
    tool_input = decision.tool_input
    
    # Execute the appropriate tool
    try:
        if tool_name == "parse_time":
            result = parse_time(**tool_input)
            tool_result = ToolResult(
                tool_name=tool_name,
                success=result.success,
                data={
                    "date": result.date,
                    "days_from_now": result.days_from_now,
                    "time_type": result.time_type,
                    "description": result.description
                } if result.success else None,
                error_message=result.error_message
            )
        elif tool_name == "geocode_city":
            result = geocode_city(**tool_input)
            tool_result = ToolResult(
                tool_name=tool_name,
                success=result.success,
                data={
                    "name": result.name,
                    "country": result.country,
                    "latitude": result.latitude,
                    "longitude": result.longitude,
                    "admin1": result.admin1,
                    "timezone": result.timezone
                } if result.success else None,
                error_message=result.error_message
            )
        elif tool_name == "get_weather":
            result = get_weather(**tool_input)
            tool_result = ToolResult(
                tool_name=tool_name,
                success=result.success,
                data={
                    "temperature_c": result.temperature_c,
                    "description": result.description,
                    "wind_speed": result.wind_speed,
                    "humidity": result.humidity,
                    "location_name": result.location_name,
                    "date": result.date,
                    "is_forecast": result.is_forecast
                } if result.success else None,
                error_message=result.error_message
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
    llm = OllamaClient()
    
    # Check if weather tool was called successfully
    has_weather_data = False
    if state.get("tool_results"):
        for result in state["tool_results"]:
            if result.tool_name == "get_weather" and result.success:
                has_weather_data = True
                break
    
    # If no weather data, return default message
    if not has_weather_data:
        return {
            **state,
            "final_answer": "Sajnos nem tudok válaszolni erre a kérdésre, add meg a pontos időpontot és helyet."
        }
    
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
        answer = llm.invoke("Te egy barátságos időjárás asszisztens vagy.", prompt)
        return {**state, "final_answer": answer.strip()}
    except Exception as e:
        # Fallback answer on error
        return {
            **state,
            "final_answer": "Sajnos hiba történt a válasz generálása során. Kérlek, próbáld újra később."
        }


def should_continue(state: AgentState) -> Literal["tool_node", "answer_node"]:
    """Router function: decide whether to call tool or provide answer."""
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
    """Create and compile the LangGraph StateGraph."""
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("read_user_prompt", read_user_prompt_node)
    workflow.add_node("decision_node", decision_node)
    workflow.add_node("tool_node", tool_node)
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
    workflow.add_edge("tool_node", "decision_node")
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
