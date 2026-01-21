
"""
LangGraph StateGraph ToolNode architektúra – OpenAI LLM integrációval, GasExportClient és RegulationRAGClient eszközökkel.
"""
from typing import TypedDict, Sequence, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
import asyncio

# ToolNode-kompatibilis függvények importja
from backend.infrastructure.tool_clients import gas_exported_quantity, regulation_query

# 1. Állapot típus
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next_action: Literal["call_tool", "final_answer"]

# 2. ToolNode létrehozása
tools = [gas_exported_quantity, regulation_query]
tool_node = ToolNode(tools)

# 3. LLM node (OpenAI GPT-4)
llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.3)
llm_with_tools = llm.bind_tools(tools)

async def agent_node(state: AgentState) -> AgentState:
    """
    LLM node: eldönti, hogy kell-e eszközt hívni, vagy végső választ ad.
    """
    response = await llm_with_tools.ainvoke(state["messages"])
    if hasattr(response, 'tool_calls') and response.tool_calls:
        next_action = "call_tool"
    else:
        next_action = "final_answer"
    return {
        "messages": state["messages"] + [response],
        "next_action": next_action
    }

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
        "next_action": "call_tool"
    }
    result = await workflow.compile().ainvoke(initial_state)
    for msg in result["messages"]:
        print(f"{msg.__class__.__name__}: {msg.content}")
        if hasattr(msg, 'tool_calls'):
            print(f"  Eszközhívások: {msg.tool_calls}")

# Futtatáshoz:
# asyncio.run(main())
