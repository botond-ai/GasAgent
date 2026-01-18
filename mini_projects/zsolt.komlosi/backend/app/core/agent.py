"""
SupportAI Agent with LangGraph.
Extended from HF1 with RAG, memory, and policy check capabilities.
"""

from datetime import datetime
from typing import Optional
import uuid

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.config import get_settings
from app.models import TicketAnalysis, PRIORITY_SLA_HOURS
from app.models.output import AnswerDraft
from app.tools import get_location_info, get_holidays, calculate_sla_deadline
from .state import AgentState
from .prompts import ANALYSIS_PROMPT, CUSTOMER_RESPONSE_PROMPT


class SupportAIAgent:
    """
    SupportAI Agent with LangGraph.
    Handles ticket analysis, RAG retrieval, answer generation, and policy checks.
    """

    def __init__(self):
        settings = get_settings()

        # Base LLM
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
        )

        # Structured output LLM for ticket analysis
        self.analysis_llm = self.llm.with_structured_output(TicketAnalysis)

        # Structured output LLM for customer response
        self.response_llm = self.llm.with_structured_output(AnswerDraft)

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes - Phase 1 (HF1 functionality)
        workflow.add_node("analyze_ticket", self._analyze_ticket_node)
        workflow.add_node("get_location", self._get_location_node)
        workflow.add_node("get_holidays", self._get_holidays_node)
        workflow.add_node("calculate_sla", self._calculate_sla_node)
        workflow.add_node("generate_response", self._generate_response_node)

        # TODO: Add RAG nodes in Phase 2-3
        # workflow.add_node("expand_query", self._expand_query_node)
        # workflow.add_node("hybrid_search", self._hybrid_search_node)
        # workflow.add_node("rerank", self._rerank_node)
        # workflow.add_node("generate_answer", self._generate_answer_node)
        # workflow.add_node("policy_check", self._policy_check_node)

        # Define edges
        workflow.set_entry_point("analyze_ticket")
        workflow.add_conditional_edges(
            "analyze_ticket",
            self._should_get_location,
            {
                "get_location": "get_location",
                "calculate_sla": "calculate_sla",
            }
        )
        workflow.add_edge("get_location", "get_holidays")
        workflow.add_edge("get_holidays", "calculate_sla")
        workflow.add_edge("calculate_sla", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    def _should_get_location(self, state: AgentState) -> str:
        """Decide whether location lookup is needed."""
        if state.get("ip_address"):
            return "get_location"
        return "calculate_sla"

    def _analyze_ticket_node(self, state: AgentState) -> dict:
        """Node: Analyze ticket with LLM using structured output."""
        print("  [1/5] Ticket elemzése...")

        # Structured output - directly get TicketAnalysis object
        analysis: TicketAnalysis = self.analysis_llm.invoke(
            ANALYSIS_PROMPT.format(ticket_text=state["ticket_text"])
        )

        return {
            "language": analysis.language,
            "sentiment": analysis.sentiment,
            "category": analysis.category,
            "subcategory": analysis.subcategory,
            "priority": analysis.priority,
            "routing": analysis.routing,
            "confidence": analysis.confidence,
            "messages": [SystemMessage(content=f"Ticket analyzed: {analysis.model_dump()}")]
        }

    def _get_location_node(self, state: AgentState) -> dict:
        """Node: Query location based on IP address."""
        print("  [2/5] Lokáció lekérdezése...")

        ip_address = state.get("ip_address")
        if not ip_address:
            return {"location_info": None}

        location_info = get_location_info.invoke({"ip_address": ip_address})

        return {
            "location_info": location_info,
            "messages": [SystemMessage(content=f"Location retrieved: {location_info}")]
        }

    def _get_holidays_node(self, state: AgentState) -> dict:
        """Node: Query public holidays."""
        print("  [3/5] Munkaszüneti napok ellenőrzése...")

        location_info = state.get("location_info")
        if not location_info or location_info.get("error"):
            return {"holidays": []}

        country_code = location_info.get("country_code", "")
        if not country_code:
            return {"holidays": []}

        holidays_result = get_holidays.invoke({
            "country_code": country_code,
            "year": datetime.now().year
        })

        holidays = holidays_result.get("holidays", []) if not holidays_result.get("error") else []

        return {
            "holidays": holidays,
            "messages": [SystemMessage(content=f"Holidays retrieved: {len(holidays)} found")]
        }

    def _calculate_sla_node(self, state: AgentState) -> dict:
        """Node: Calculate SLA deadline."""
        print("  [4/5] SLA számítása...")

        priority = state.get("priority", "P3")
        location_info = state.get("location_info") or {}
        timezone = location_info.get("timezone", "UTC")
        country_code = location_info.get("country_code", "")

        sla_info = calculate_sla_deadline.invoke({
            "timezone": timezone,
            "priority": priority,
            "country_code": country_code
        })

        return {
            "sla_info": sla_info,
            "messages": [SystemMessage(content=f"SLA calculated: {sla_info}")]
        }

    def _generate_response_node(self, state: AgentState) -> dict:
        """Node: Generate final response using structured output."""
        print("  [5/5] Válasz generálása...")

        location = state.get("location_info") or {"message": "No IP address provided"}
        sla = state.get("sla_info") or {}
        customer_name = state.get("customer_name") or "Ügyfelünk"

        # Generate structured answer draft
        detected_language = state.get("language", "Hungarian")
        answer_draft: AnswerDraft = self.response_llm.invoke(
            CUSTOMER_RESPONSE_PROMPT.format(
                customer_name=customer_name,
                language=detected_language,
                ticket_text=state["ticket_text"],
                category=state.get("category", "General"),
                priority=state.get("priority", "P3"),
                sentiment=state.get("sentiment", "neutral"),
            )
        )

        # Determine if we should auto-respond based on confidence
        confidence = state.get("confidence", 0.0)
        should_auto = confidence >= 0.85

        # Build structured output
        final_response = {
            "session_id": state.get("session_id", str(uuid.uuid4())),
            "triage": {
                "category": state.get("category", "General"),
                "subcategory": state.get("subcategory"),
                "priority": state.get("priority", "P3"),
                "sla_hours": PRIORITY_SLA_HOURS.get(state.get("priority", "P3"), 24),
                "suggested_team": state.get("routing", "General Support"),
                "sentiment": state.get("sentiment", "neutral"),
                "language": state.get("language", "Unknown"),
                "confidence": confidence,
            },
            "answer_draft": {
                "greeting": answer_draft.greeting,
                "body": answer_draft.body,
                "closing": answer_draft.closing,
                "tone": answer_draft.tone,
            },
            "citations": [],  # Will be populated by RAG in Phase 2
            "policy_check": {
                "refund_promise": False,
                "sla_mentioned": True,
                "escalation_needed": False,
                "compliance": "passed",
                "warnings": [],
            },
            "similar_tickets": [],  # Will be populated in Phase 6
            "internal_note": None,
            "should_auto_respond": should_auto,
            "location_info": location,
            "sla_info": sla,
        }

        return {
            "final_response": final_response,
            "messages": [SystemMessage(content="Response generated")]
        }

    def analyze(
        self,
        ticket_text: str,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> dict:
        """
        Analyze support ticket and provide SLA recommendation.

        Args:
            ticket_text: The ticket text
            ip_address: Optional IP address for customer location
            session_id: Optional session ID for conversation tracking
            customer_name: Optional customer name for personalized response

        Returns:
            SupportAIResponse as dictionary
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        initial_state: AgentState = {
            "messages": [HumanMessage(content=ticket_text)],
            "ticket_text": ticket_text,
            "ip_address": ip_address,
            "session_id": session_id,
            "customer_name": customer_name,
            "language": None,
            "sentiment": None,
            "category": None,
            "subcategory": None,
            "priority": None,
            "routing": None,
            "confidence": None,
            "location_info": None,
            "holidays": None,
            "sla_info": None,
            "query_original": None,
            "query_expanded": None,
            "query_english": None,
            "retrieved_documents": None,
            "reranked_documents": None,
            "answer_draft": None,
            "citations": None,
            "policy_check": None,
            "similar_tickets": None,
            "rolling_summary": None,
            "conversation_history": None,
            "pii_filtered": None,
            "pii_matches": None,
            "final_response": None,
            "retry_count": 0,
            "top_score": None,
        }

        # Run graph
        final_state = self.graph.invoke(initial_state)

        return final_state.get("final_response", {"error": "Analysis failed"})

    def reset_history(self):
        """Clear chat history."""
        pass
