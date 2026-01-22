from infrastructure.openai_gateway import OpenAIGateway
from infrastructure.vector_store import Domain
from workflows.state import WorkflowState


class RouterNode:
    """
    Classifies user query to determine the appropriate domain.

    Single Responsibility: Domain classification using LLM.
    """

    def __init__(self, openai_gateway: OpenAIGateway):
        self.openai_gateway = openai_gateway

    async def __call__(self, state: WorkflowState) -> WorkflowState:
        """Classify the query and update state with detected domain."""
        try:
            domain_str = await self.openai_gateway.classify_intent(state.query)
            domain_str = domain_str.strip().lower()

            # Map string to Domain enum
            try:
                state.detected_domain = Domain(domain_str)
                state.routing_confidence = 1.0
            except ValueError:
                # Fallback to general if classification returns unknown domain
                state.detected_domain = Domain.GENERAL
                state.routing_confidence = 0.5

        except Exception as e:
            state.error = f"Router error: {str(e)}"
            state.detected_domain = Domain.GENERAL
            state.routing_confidence = 0.0

        return state
