from typing import TypedDict, Annotated, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
import json

from domain.models import Analysis, TriageDecision, AnswerDraft, TicketOutput, TicketCreate
from domain.interfaces import ILLMClient, IVectorDBClient, ITicketClient

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    analysis: Dict[str, Any]
    triage: Dict[str, Any]
    context: List[str]
    draft: Dict[str, Any]
    ticket_result: Dict[str, Any]
    final_output: Dict[str, Any]
    context: List[str]
    draft: Dict[str, Any]
    ticket_result: Dict[str, Any]
    final_output: Dict[str, Any]

class TriageAgent:
    def __init__(self, llm_client: ILLMClient, vector_db: IVectorDBClient, ticket_client: ITicketClient = None):
        self.llm = llm_client
        self.vector_db = vector_db
        self.ticket_client = ticket_client
        
        # Define tools
        self.tools = []
        if self.ticket_client:
            self.tools = [self._get_create_ticket_tool()]
            # Bind tools to the LLM client
            # self.llm.bind_tools(self.tools) # Assuming client handles binding internally or we do it here
            
        self.graph = self._build_graph()

    def _get_create_ticket_tool(self):
        @tool
        async def create_ticket_tool(title: str, description: str, priority: str, category: str, tags: List[str]) -> str:
            """Creates a support ticket in the external system."""
            ticket = TicketCreate(
                title=title,
                description=description,
                priority=priority,
                category=category,
                tags=tags
            )
            try:
                result = await self.ticket_client.create_ticket(ticket)
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e)})
        return create_ticket_tool

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("analyze_intent", self._analyze_intent)
        workflow.add_node("triage_ticket", self._triage_ticket)
        # ToolNode handles tool execution
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("draft_response", self._draft_response)
        workflow.add_node("create_output", self._create_output)

        workflow.set_entry_point("analyze_intent")
        
        workflow.add_edge("analyze_intent", "triage_ticket")
        
        # Conditional edge: If tools are called in triage_ticket, go to 'tools', else 'retrieve_context'
        workflow.add_conditional_edges(
            "triage_ticket",
            tools_condition,
            {
                "tools": "tools",
                "__end__": "retrieve_context"  # If no tool called, go to retrieve_context (acting as 'next' node)
            } 
            # Note: tools_condition typically maps to END if no tool called, but we want to continue workflow.
            # However, tools_condition logic is: if message has tool_calls -> "tools", else -> END.
            # We need to customize this or ensure the graph flow works.
            # Custom conditional edge might be safer if tools_condition is strict on END.
        )
        
        workflow.add_edge("tools", "retrieve_context")
        workflow.add_edge("retrieve_context", "draft_response")
        workflow.add_edge("draft_response", "create_output")
        workflow.add_edge("create_output", END)

        return workflow.compile()

    async def _analyze_intent(self, state: AgentState):
        messages = state["messages"]
        last_message = messages[-1].content
        prompt = f"""Analyze the following support ticket message and extract the summary, intent, and complexity.
        Message: {last_message}
        """
        analysis = await self.llm.generate_structured(prompt, Analysis)
        return {"analysis": analysis.model_dump()}

    async def _triage_ticket(self, state: AgentState):
        analysis = state["analysis"]
        
        # 1. First get the classification decision
        prompt = f"""Based on the analysis below, triage the ticket into one of the following tiers:
        - Tier 1 Support: Basic troubleshooting, Passwords, Routine requests.
        - Tier 2 Support: Advanced technical support, Data issues, Integration logic.
        - Tier 3 Support: Critical/Complex engineering, Root cause analysis, Config changes.
        - Vendor Product Support: Core product bugs.

        Analysis: {json.dumps(analysis)}
        
        Provide the decision, responsible party, reasoning, and if escalation is needed.
        
        IMPORTANT: 
        - 'escalation_needed' MUST be True if the decision is Tier 2 Support, Tier 3 Support, or Vendor Product Support.
        - 'escalation_needed' should be False ONLY for Tier 1 Support.
        """
        decision = await self.llm.generate_structured(prompt, TriageDecision)
        
        # 2. If escalation is needed, force a tool call
        messages = []
        if decision.escalation_needed and self.tools:
            # We explicitly construct a tool call request for the LLM or invoke it.
            # Since we are essentially "forcing" the logic here based on the structured output,
            # we can skip the LLM "deciding" to call the tool and just return a ToolCall message manually,
            # OR we can ask the LLM to call the tool.
            
            # Approach: Ask LLM to call the tool with specific parameters based on analysis.
            # This uses the bind_tools capability.
            
            tool_prompt = f"""You are a helpful assistant.
            A ticket needs to be created based on this analysis:
            {json.dumps(analysis)}
            And this triage decision:
            {json.dumps(decision.model_dump())}
            
            Call the create_ticket_tool with the appropriate parameters.
            """
            
            # We need to access the bound LLM which we haven't exposed directly in the interface cleanly
            # except via bind_tools.
            
            # Using the client's underlying LLM directly if possible or extending interface?
            # The interface has generate and generate_structured.
            # We added bind_tools to the specific client.
            # Let's bind tools now for this specific call if not globally bound.
            
            self.llm.bind_tools(self.tools)
            response = await self.llm.llm.ainvoke(tool_prompt) # Directly accessing .llm is a bit leaky but pragmatic here
            messages = [response]

        return {"triage": decision.model_dump(), "messages": messages}

    async def _retrieve_context(self, state: AgentState):
        # Handle tool output if it exists in messages
        ticket_result = None
        messages = state.get("messages", [])
        if messages and isinstance(messages[-1], AIMessage):
             # If the last message was a tool call (or response to it), previous extraction logic needed?
             # LangGraph StateGraph with ToolNode appends ToolMessage.
             pass
        
        # We can extract ticket result from the state messages history if needed, 
        # or relying on the tool returning a string that we can parse? 
        # For now, let's keep the context retrieval logic.
        
        analysis = state["analysis"]
        query = f"{analysis['intent']} {analysis['summary']}"
        results = await self.vector_db.search(query)
        context = [f"Source: {r['source']}\nContent: {r['text']}" for r in results]
        return {"context": context}

    async def _draft_response(self, state: AgentState):
        context = state.get("context", [])
        analysis = state["analysis"]
        triage = state["triage"]
        
        # Retrieve original user message
        # In a long conversation, this index might be wrong, but for this linear flow it's 0 or similar.
        # State "messages" now includes tool calls.
        user_message = ""
        for m in state["messages"]:
            if isinstance(m, HumanMessage):
                user_message = m.content
                break
        
        # Try to find ticket result in messages if available
        ticket_info = "No ticket created"
        for m in reversed(state["messages"]):
             if hasattr(m, "tool_call_id"): # ToolMessage
                 ticket_info = m.content
                 break

        context_str = "\n\n".join(context)
        
        prompt = f"""You are a helpful Medical Support Assistant.
        Draft a polite and professional response to the user based on the context and triage decision.
        
        User Message: {user_message}
        
        Context:
        {context_str}
        
        Triage Info:
        {json.dumps(triage)}

        Ticket Info (from tool):
        {ticket_info}
        
        Analysis:
        {json.dumps(analysis)}
        
        If a ticket was created, provide the Ticket ID to the user.
        If the issue is escalated (Tier 2/3/Product), inform the user that it has been forwarded to the responsible team.
        Provide citations if available in the context.
        """
        draft = await self.llm.generate_structured(prompt, AnswerDraft)
        return {"draft": draft.model_dump()}

    async def _create_output(self, state: AgentState):
        # Extract ticket result for final output
        ticket_created = None
        for m in reversed(state["messages"]):
             if hasattr(m, "tool_call_id"):
                 try:
                    ticket_created = json.loads(m.content)
                 except:
                    ticket_created = m.content
                 break

        return {
            "final_output": {
                "analysis": state["analysis"],
                "triage_decision": state["triage"],
                "answer_draft": state["draft"],
                "ticket_created": ticket_created
            }
        }

    async def run(self, message: str):
        result = await self.graph.ainvoke({
            "messages": [HumanMessage(content=message)],
            "analysis": {},
            "triage": {},
            "context": [],
            "draft": {},
            "ticket_result": None,
            "final_output": {}
        })
        return result["final_output"]
