from typing import List

from langgraph.graph import StateGraph, END

from infrastructure.openai_gateway import OpenAIGateway
from infrastructure.tools.tool_executor import ToolExecutor
from core.rag_engine import RAGEngine
from workflows.state import WorkflowState
from workflows.nodes.router_node import RouterNode
from workflows.nodes.retrieve_node import RetrieveNode
from workflows.nodes.generate_node import GenerateNode
from workflows.nodes.tool_node import ToolNode


def should_use_tools(state: WorkflowState) -> str:
    """Conditional edge: check if we need to execute tools."""
    if state.pending_tool_calls:
        return "execute_tools"
    return "end"


class KnowledgeWorkflow:
    """
    LangGraph workflow for multi-domain knowledge retrieval with tool support.

    Flow:
        Route -> Retrieve -> Generate -> [Tool Loop] -> END
                                |            ^
                                v            |
                            Execute Tools ---+

    Single Responsibility: Orchestrating the query-to-response workflow.
    """

    def __init__(
        self,
        openai_gateway: OpenAIGateway,
        rag_engine: RAGEngine,
        tool_executor: ToolExecutor
    ):
        self.openai_gateway = openai_gateway
        self.rag_engine = rag_engine
        self.tool_executor = tool_executor
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with tool support."""
        # Initialize nodes with dependencies
        router_node = RouterNode(self.openai_gateway)
        retrieve_node = RetrieveNode(self.rag_engine)
        generate_node = GenerateNode(self.openai_gateway, self.tool_executor)
        tool_node = ToolNode(self.tool_executor)

        # Create the graph
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("route", router_node)
        workflow.add_node("retrieve", retrieve_node)
        workflow.add_node("generate", generate_node)
        workflow.add_node("execute_tools", tool_node)

        # Define edges
        workflow.set_entry_point("route")
        workflow.add_edge("route", "retrieve")
        workflow.add_edge("retrieve", "generate")

        # Conditional edge after generate: tool loop or end
        workflow.add_conditional_edges(
            "generate",
            should_use_tools,
            {
                "execute_tools": "execute_tools",
                "end": END
            }
        )

        # After tool execution, go back to generate
        workflow.add_edge("execute_tools", "generate")

        return workflow.compile()

    async def run(self, query: str, conversation_history: List[dict] = None) -> WorkflowState:
        """
        Execute the workflow for a query.

        Args:
            query: User's question
            conversation_history: Optional list of previous messages in OpenAI format

        Returns:
            Final WorkflowState with response and citations
        """
        initial_state = WorkflowState(
            query=query,
            conversation_history=conversation_history or []
        )
        final_state = await self.graph.ainvoke(initial_state)
        return final_state


def create_workflow(
    openai_gateway: OpenAIGateway,
    rag_engine: RAGEngine,
    tool_executor: ToolExecutor = None
) -> KnowledgeWorkflow:
    """Factory function to create the workflow."""
    if tool_executor is None:
        tool_executor = ToolExecutor()
    return KnowledgeWorkflow(openai_gateway, rag_engine, tool_executor)
