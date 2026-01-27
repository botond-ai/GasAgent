"""
LangGraph workflow definition for support ticket processing.
"""
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate

from app.core.logging import get_logger
from app.workflows.nodes import WorkflowNodes
from app.prompts import FALLBACK_ANSWER_PROMPT
from app.prompts.templates import get_tone_for_sentiment
from app.models.schemas import AnswerDraft

logger = get_logger(__name__)


class WorkflowError(TypedDict):
    """Error information for workflow tracking."""
    node: str
    message: str
    recoverable: bool


class SupportWorkflowState(TypedDict, total=False):
    """Type definition for workflow state."""
    # Input (required)
    ticket_id: str
    raw_message: str
    customer_name: str
    customer_email: str

    # Intent Detection
    problem_type: str
    sentiment: str

    # Triage Classification
    category: str
    subcategory: str
    priority: str
    sla_hours: int
    suggested_team: str
    triage_confidence: float

    # FleetDM Device Context
    device_info: dict | None
    device_context: str

    # RAG Pipeline
    search_queries: list[str]
    retrieved_docs: list[dict]
    reranked_docs: list[dict]

    # Answer Generation
    answer_draft: dict
    citations: list[dict]
    policy_check: dict

    # Final Output
    output: dict

    # Error Tracking (for explicit error paths)
    errors: list[WorkflowError]
    has_critical_error: bool


class SupportWorkflow:
    """LangGraph workflow for support ticket processing."""

    def __init__(self, nodes: WorkflowNodes):
        """
        Initialize workflow graph.

        Args:
            nodes: Workflow nodes instance
        """
        self.nodes = nodes
        self.graph = self._build_graph()
        logger.info("Initialized SupportWorkflow")

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow with explicit error handling paths.

        Returns:
            Compiled StateGraph
        """
        # Create graph
        workflow = StateGraph(SupportWorkflowState)

        # Add processing nodes
        workflow.add_node("detect_intent", self.nodes.detect_intent)
        workflow.add_node("triage_classify", self.nodes.triage_classify)
        workflow.add_node("fleet_lookup", self.nodes.fleet_lookup)
        workflow.add_node("expand_queries", self.nodes.expand_queries)
        workflow.add_node("search_rag", self.nodes.search_rag)
        workflow.add_node("rerank_docs", self.nodes.rerank_docs)
        workflow.add_node("draft_answer", self.nodes.draft_answer)
        workflow.add_node("check_policy", self.nodes.check_policy)
        workflow.add_node("validate_output", self.nodes.validate_output)

        # Add error handling node
        workflow.add_node("handle_error", self._handle_error)
        workflow.add_node("fallback_answer", self._fallback_answer)

        # Routing predicates
        def should_lookup_device(state: SupportWorkflowState) -> str:
            """Decide if we need FleetDM lookup based on ticket type."""
            # Check for critical errors first
            if state.get("has_critical_error"):
                return "handle_error"

            problem_type = state.get("problem_type", "").lower()
            category = state.get("category", "").lower()

            # Keywords that trigger device lookup
            technical_keywords = ["technical", "hardware", "device", "computer", "laptop", "desktop", "machine", "system"]

            for keyword in technical_keywords:
                if keyword in problem_type or keyword in category:
                    logger.info(f"FleetDM lookup triggered for technical issue")
                    return "fleet_lookup"

            logger.info("Skipping FleetDM lookup for non-technical ticket")
            return "expand_queries"

        def check_rag_results(state: SupportWorkflowState) -> str:
            """Check if RAG returned usable results."""
            docs = state.get("reranked_docs", [])
            if not docs:
                logger.warning("No documents found, using fallback answer")
                return "fallback_answer"
            return "draft_answer"

        def check_policy_result(state: SupportWorkflowState) -> str:
            """Route based on policy check results."""
            policy = state.get("policy_check", {})
            if policy.get("compliance") == "failed":
                logger.warning("Policy check failed, needs review")
                # Still continue but flag for review
            if policy.get("escalation_needed"):
                logger.info("Escalation needed flag set")
            return "validate_output"

        # Entry point
        workflow.set_entry_point("detect_intent")

        # Main flow with conditional routing
        workflow.add_edge("detect_intent", "triage_classify")

        workflow.add_conditional_edges(
            "triage_classify",
            should_lookup_device,
            {
                "fleet_lookup": "fleet_lookup",
                "expand_queries": "expand_queries",
                "handle_error": "handle_error"
            }
        )

        workflow.add_edge("fleet_lookup", "expand_queries")
        workflow.add_edge("expand_queries", "search_rag")
        workflow.add_edge("search_rag", "rerank_docs")

        # Conditional: check if we have RAG results
        workflow.add_conditional_edges(
            "rerank_docs",
            check_rag_results,
            {
                "draft_answer": "draft_answer",
                "fallback_answer": "fallback_answer"
            }
        )

        workflow.add_edge("draft_answer", "check_policy")
        workflow.add_edge("fallback_answer", "check_policy")

        # Policy check routing
        workflow.add_conditional_edges(
            "check_policy",
            check_policy_result,
            {
                "validate_output": "validate_output"
            }
        )

        workflow.add_edge("validate_output", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    async def _handle_error(self, state: SupportWorkflowState) -> dict:
        """
        Error handler node - creates error response.

        Args:
            state: Current workflow state with error info

        Returns:
            State update with error output
        """
        errors = state.get("errors", [])
        error_messages = [e.get("message", "Unknown error") for e in errors]

        logger.error(f"Workflow error for ticket {state.get('ticket_id')}: {error_messages}")

        return {
            "output": {
                "ticket_id": state.get("ticket_id"),
                "error": True,
                "error_messages": error_messages,
                "triage": {
                    "category": state.get("category", "General"),
                    "subcategory": state.get("subcategory", "Error"),
                    "priority": "P1",
                    "sla_hours": 2,
                    "suggested_team": "escalation_team",
                    "sentiment": state.get("sentiment", "neutral"),
                    "confidence": 0.0
                },
                "answer_draft": {
                    "greeting": f"Hello {state.get('customer_name', 'Customer')},",
                    "body": "We encountered an issue processing your request. A support specialist will review your ticket shortly.",
                    "closing": "We apologize for any inconvenience.\nSupport Team",
                    "tone": "empathetic_professional"
                },
                "citations": [],
                "policy_check": {
                    "refund_promise": False,
                    "sla_mentioned": False,
                    "escalation_needed": True,
                    "compliance": "warning"
                }
            }
        }

    async def _fallback_answer(self, state: SupportWorkflowState) -> dict:
        """
        Fallback answer node - used when RAG returns no results.
        Now uses LLM with device context if available.

        Args:
            state: Current workflow state

        Returns:
            State update with fallback answer draft
        """
        logger.info(f"Generating fallback answer for ticket {state.get('ticket_id')}")

        sentiment = state.get("sentiment", "neutral")
        customer_name = state.get("customer_name", "Customer")
        device_context = state.get("device_context", "")
        tone = get_tone_for_sentiment(sentiment)

        # If we have device context, use LLM to generate intelligent response
        if device_context:
            logger.info("Device context available - using LLM for intelligent fallback")
            try:
                llm_with_structure = self.nodes.llm.with_structured_output(AnswerDraft)

                prompt = ChatPromptTemplate.from_messages([
                    ("system", FALLBACK_ANSWER_PROMPT["system"]),
                    ("user", FALLBACK_ANSWER_PROMPT["user"])
                ])

                chain = prompt | llm_with_structure

                result = await chain.ainvoke({
                    "customer_name": customer_name,
                    "problem_type": state.get("problem_type", "support request"),
                    "sentiment": sentiment,
                    "tone": tone,
                    "device_info": device_context,
                    "message": state["raw_message"]
                })

                return {
                    "answer_draft": {
                        "greeting": result.greeting,
                        "body": result.body,
                        "closing": result.closing,
                        "tone": result.tone
                    },
                    "citations": [citation.model_dump() for citation in result.citations] if result.citations else []
                }
            except Exception as e:
                logger.error(f"Error in LLM fallback: {e}")
                # Fall through to static response

        # Static fallback when no device context or LLM fails
        logger.info("No device context - using static fallback response")
        return {
            "answer_draft": {
                "greeting": f"Hello {customer_name}," if tone == "formal" else f"Hi {customer_name}!",
                "body": "Thank you for reaching out to us. I've reviewed your request and while I don't have specific documentation to reference, I want to ensure you get the help you need. Our team will look into this matter and follow up with you shortly with more detailed information.",
                "closing": "Best regards,\nSupport Team" if tone == "formal" else "Thanks for your patience!\nSupport Team",
                "tone": tone
            },
            "citations": []
        }

    async def process_ticket(self, state: dict) -> dict:
        """
        Process a support ticket through the workflow.

        Args:
            state: Initial state with ticket data

        Returns:
            Final state with complete processing results
        """
        logger.info(f"Processing ticket: {state.get('ticket_id')}")

        try:
            # Run workflow
            final_state = await self.graph.ainvoke(state)

            logger.info(f"Successfully processed ticket: {state.get('ticket_id')}")
            return final_state

        except Exception as e:
            logger.error(f"Error processing ticket {state.get('ticket_id')}: {e}", exc_info=True)
            raise
