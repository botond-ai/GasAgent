"""
LangGraph StateGraph ToolNode architektúra – OpenAI LLM integrációval, GasExportClient és RegulationRAGClient eszközökkel.
"""
from typing import TypedDict, Sequence, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
import asyncio
import logging

# ToolNode-kompatibilis függvények importja
from backend.infrastructure.tool_clients import gas_exported_quantity, regulation_query

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 1. Állapot típus
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next_action: Literal["call_tool", "final_answer"]
    tool_decision: str  # Add default value for tool_decision

# 2. ToolNode létrehozása
tools = [gas_exported_quantity, regulation_query]

# Wrap ToolNode execution with debugging logs
def create_debug_tool_node(tools):
    tool_node = ToolNode(tools)

    async def debug_ainvoke(state: AgentState) -> AgentState:
        logger.debug("ToolNode received state: %s", state)
        new_state = await tool_node.ainvoke(state)
        logger.debug("ToolNode returning state: %s", new_state)
        return new_state

    tool_node.ainvoke = debug_ainvoke
    return tool_node

tool_node = create_debug_tool_node(tools)

# 3. LLM node (OpenAI GPT-4)
llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.3)
llm_with_tools = llm.bind_tools(tools)

async def agent_node(state: AgentState) -> AgentState:
    """
    LLM node: eldönti, hogy kell-e eszközt hívni, vagy végső választ ad.
    """
    logger.debug("Agent node received state: %s", state)
    response = await llm_with_tools.ainvoke(state["messages"])
    # Record LLM usage metric
    from backend.observability.metrics import record_llm_usage
    # TODO: Extract real token counts and duration if available
    record_llm_usage(
        model=getattr(llm_with_tools, 'model', 'unknown'),
        prompt_tokens=0,  # Replace with actual value if available
        completion_tokens=0,  # Replace with actual value if available
        duration_seconds=0.0  # Replace with actual value if available
    )
    if hasattr(response, 'tool_calls') and response.tool_calls:
        next_action = "call_tool"
    else:
        next_action = "final_answer"
    new_state = {
        "messages": state["messages"] + [response],
        "next_action": next_action,
        "tool_decision": state.get("tool_decision")  # Restore tool_decision
    }
    logger.debug("Agent node returning state: %s", new_state)
    return new_state

# 4. Feltételes él: kell-e eszközt hívni?
def should_continue(state: AgentState) -> str:
    return state["next_action"]

# 5. Gráf építése
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.add_edge("tools", "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "call_tool": "tools",
        "final_answer": END
    }
)
workflow.set_entry_point("agent")

# 6. Futtatás példa (async)
async def main():
    initial_state = {
        "messages": [HumanMessage(content="Mennyi gáz ment ki a VIP Bereg ponton 2025 januárban?")],
        "next_action": "call_tool",
        "tool_decision": None  # Restore tool_decision
    }
    logger.debug("Initial state: %s", initial_state)
    result = await workflow.compile().ainvoke(initial_state)
    logger.debug("Final state: %s", result)
    for msg in result["messages"]:
        print(f"{msg.__class__.__name__}: {msg.content}")
        if hasattr(msg, 'tool_calls'):
            print(f"  Eszközhívások: {msg.tool_calls}")

# Futtatáshoz:
# asyncio.run(main())
