from core.rag_engine import RAGEngine
from workflows.state import WorkflowState


class RetrieveNode:
    """
    Retrieves relevant context from the vector store.

    Single Responsibility: Context retrieval using RAGEngine.
    """

    def __init__(self, rag_engine: RAGEngine):
        self.rag_engine = rag_engine

    async def __call__(self, state: WorkflowState) -> WorkflowState:
        """Retrieve relevant documents for the query and domain."""
        if state.detected_domain is None:
            state.error = "No domain detected for retrieval"
            return state

        try:
            result = await self.rag_engine.retrieve_for_query(
                query=state.query,
                domain=state.detected_domain
            )

            state.context = result.context
            state.citations = result.citations

        except Exception as e:
            state.error = f"Retrieval error: {str(e)}"
            state.context = ""
            state.citations = []

        return state
