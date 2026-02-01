from datetime import datetime
from typing import List
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from ..models.schemas import MessageRecord
from ..models.state import AgentState
from .llm_client import LLMClient
from .mcp_tools import create_mcp_tools, execute_mcp_tool

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """LangGraph-based orchestrator for the chat agent (web search removed)."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        rag_service=None,
    ) -> None:
        self.llm = llm_client or LLMClient()
        # RAG service is injected to keep OCP/DIP and for easy testing
        self.rag = rag_service
        self.mcp_tools = create_mcp_tools()
        
        graph = StateGraph(AgentState)
        # KB-first routing with MCP tool support
        graph.add_node("route_query", self.route_query)
        graph.add_node("build_prompt", self.build_prompt)
        graph.add_node("call_llm", self.call_llm)
        graph.add_node("execute_tools", self.execute_tools)
        graph.add_node("call_llm_final", self.call_llm_final)
        
        graph.set_entry_point("route_query")
        graph.add_edge("route_query", "build_prompt")
        graph.add_edge("build_prompt", "call_llm")
        
        # Conditional: if LLM wants to call tools, execute them
        graph.add_conditional_edges(
            "call_llm",
            self.should_execute_tools,
            {
                "execute_tools": "execute_tools",
                "end": END
            }
        )
        graph.add_edge("execute_tools", "call_llm_final")
        graph.add_edge("call_llm_final", END)
        
        self.workflow = graph.compile()

    def maybe_search(self, state: AgentState) -> AgentState:
        """Deprecated: web search was removed."""
        state["rag_context"] = state.get("rag_context") or []
        return state

    async def run(self, initial_state: AgentState) -> AgentState:
        return await self.workflow.ainvoke(initial_state)

    def route_query(self, state: AgentState) -> AgentState:
        """KB-first routing: use the injected RAG service to get context.

        If RAG returns 'no_hit', we leave rag_context empty and annotate the
        state for potential fallback. This ensures the downstream prompt will
        be KB-first: it receives context when available and otherwise nothing.
        """
        state["rag_context"] = []
        if not self.rag:
            # no RAG service injected -> noop
            return state
        q = state.get("query", "")
        # RBAC: if the user has a scope in preferences, pass it as a filter
        prefs = state.get("request_metadata", {}) or {}
        access_scope = prefs.get("access_scope") or (state.get("user_preferences", {}).get("access_scope") if state.get("user_preferences") else None)
        filters = {**(prefs), **({"access_scope": access_scope} if access_scope else {})}
        # ChromaDB requires None for no filters, not empty dict
        if not filters:
            filters = None
        telemetry = self.rag.route_and_retrieve(q, filters=filters)
        state["rag_telemetry"] = telemetry
        if telemetry.get("decision") == "hit":
            # include topk hits as context for the prompt generation
            state["rag_context"] = telemetry.get("topk", [])
        else:
            state["rag_context"] = []
            state["rag_telemetry"]["fallback_reason"] = "no_hit_or_low_confidence"
        return state

    def build_prompt(self, state: AgentState) -> AgentState:
        rag_context = state.get("rag_context") or []
        history = state.get("history") or []
        history_text = self._history_to_text(history)
        system_prompt = (
            "You are KnowledgeRouter, a helpful internal assistant with access to powerful tools. "
            "You can search the web using brave_search, remember information using memory tools, "
            "and read documents using filesystem tools. "
            "Use these tools proactively when needed to provide accurate, up-to-date information. "
            "If the user asks about current events, news, or recent information, use brave_search. "
            "If KB context is provided, use it, but you can also search for additional information if needed."
        )
        user_prompt = (
            f"User question at {datetime.utcnow().isoformat()}:\n"
            f"{state.get('query','')}\n\n"
            f"Conversation history:\n{history_text if history_text else 'None'}\n\n"
            f"Search / RAG context:\n{rag_context if rag_context else 'None'}\n\n"
            "Compose a concise, actionable answer. If context is present, ground the answer in it."
        )
        state["system_prompt"] = system_prompt
        state["final_prompt"] = user_prompt
        state["history_messages"] = self._history_to_messages(history)
        return state

    async def call_llm(self, state: AgentState) -> AgentState:
        """Call LLM with MCP tool support."""
        logger.info(f"Calling LLM with {len(self.mcp_tools)} tools available")
        response = await self.llm.generate(
            system_prompt=state.get("system_prompt", "You are KnowledgeRouter."),
            user_prompt=state.get("final_prompt", ""),
            history=state.get("history_messages") or [],
            tools=self.mcp_tools,
            tool_choice="auto"
        )
        state["llm_response"] = response
        logger.info(f"LLM response type: {response.get('type')}")
        
        if response.get("type") == "tool_calls":
            tool_calls = response.get("tool_calls", [])
            logger.info(f"LLM wants to call {len(tool_calls)} tools: {[tc['name'] for tc in tool_calls]}")
            state["tool_calls"] = tool_calls
            state["response_text"] = ""
        else:
            logger.info("LLM returned text response without tool calls")
            state["response_text"] = response.get("content", "")
            state["tool_calls"] = []
        
        return state

    def should_execute_tools(self, state: AgentState) -> str:
        """Determine if we should execute tools or end."""
        if state.get("tool_calls"):
            logger.info("Routing to execute_tools")
            return "execute_tools"
        logger.info("Routing to end (no tools)")
        return "end"

    async def execute_tools(self, state: AgentState) -> AgentState:
        """Execute the tools requested by the LLM."""
        tool_calls = state.get("tool_calls", [])
        tool_results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            arguments = tool_call.get("arguments", {})
            
            logger.info(f"Executing tool: {tool_name} with args: {arguments}")
            result = await execute_mcp_tool(tool_name, arguments)
            logger.info(f"Tool result: {str(result)[:200]}...")
            tool_results.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": result
            })
        
        state["tool_results"] = tool_results
        return state

    async def call_llm_final(self, state: AgentState) -> AgentState:
        """Call LLM with tool results to generate final response."""
        tool_results = state.get("tool_results", [])
        
        logger.info(f"Synthesizing response from {len(tool_results)} tool results")
        
        # Format tool results as text
        tool_results_text = "\n\n".join([
            f"Tool: {r['tool']}\nArguments: {json.dumps(r['arguments'])}\nResult: {r['result']}"
            for r in tool_results
        ])
        
        final_prompt = (
            f"Original query: {state.get('query', '')}\n\n"
            f"Tool execution results:\n{tool_results_text}\n\n"
            "Based on the tool results above, provide a comprehensive answer to the user's question. "
            "Synthesize the information from the tools and present it clearly."
        )
        
        response = await self.llm.generate(
            system_prompt=state.get("system_prompt", "You are KnowledgeRouter."),
            user_prompt=final_prompt,
            history=state.get("history_messages") or [],
            tools=None,
        )
        
        state["response_text"] = response.get("content", "")
        logger.info(f"Final response length: {len(state['response_text'])} chars")
        return state

    def _history_to_messages(self, history: List[MessageRecord]):
        messages = []
        for item in history:
            if item.role == "assistant":
                messages.append(AIMessage(content=item.content))
            else:
                messages.append(HumanMessage(content=item.content))
        return messages

    def _history_to_text(self, history: List[MessageRecord]) -> str:
        lines = []
        for msg in history:
            lines.append(f"{msg.role}: {msg.content}")
        return "\n".join(lines)
