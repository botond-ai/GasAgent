"""
LangGraph workflow nodes for support ticket processing.
Refactored with proper typing and error tracking.
"""
from typing import Any, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import SupportTicketState, AnswerDraft, Citation
from app.services.rag_service import RAGService
from app.prompts import (
    INTENT_DETECTION_PROMPT,
    TRIAGE_CLASSIFICATION_PROMPT,
    DRAFT_ANSWER_PROMPT,
    POLICY_CHECK_PROMPT,
)
from app.prompts.templates import get_tone_for_sentiment

logger = get_logger(__name__)


# Type alias for workflow state (matches graph.py SupportWorkflowState)
WorkflowState = dict[str, Any]


def add_error(state: WorkflowState, node: str, message: str, recoverable: bool = True) -> dict:
    """
    Add an error to the state's error list.

    Args:
        state: Current workflow state
        node: Name of the node where error occurred
        message: Error message
        recoverable: Whether the workflow can continue

    Returns:
        State update dict with error information
    """
    errors = list(state.get("errors", []))
    errors.append({
        "node": node,
        "message": message,
        "recoverable": recoverable
    })
    return {
        "errors": errors,
        "has_critical_error": not recoverable or state.get("has_critical_error", False)
    }


# Pydantic models for structured outputs
class IntentDetection(BaseModel):
    problem_type: str = Field(description="One of: billing, technical, account, shipping, product, other")
    sentiment: str = Field(description="One of: frustrated, neutral, satisfied")


class TriageClassification(BaseModel):
    category: str = Field(description="Ticket category")
    subcategory: str = Field(description="Ticket subcategory")
    priority: str = Field(description="P1, P2, or P3")
    sla_hours: int = Field(description="SLA in hours: 2, 24, or 72")
    suggested_team: str = Field(description="Team to handle this ticket")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0)


# ELTÁVOLÍTVA: AnswerDraft osztály (most a schemas.py-ból jön)
# A Citation is onnan jön


class PolicyCheck(BaseModel):
    refund_promise: bool = Field(description="Does response promise unauthorized refund?")
    sla_mentioned: bool = Field(description="Does response commit to specific timeframe?")
    escalation_needed: bool = Field(description="Does issue need supervisor review?")
    compliance: str = Field(description="passed, failed, or warning")
    notes: str = Field(description="Additional compliance notes")


class WorkflowNodes:
    """Collection of LangGraph workflow nodes."""

    def __init__(self, rag_service: RAGService):
        """
        Initialize workflow nodes.

        Args:
            rag_service: RAG service instance
        """
        self.rag = rag_service
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            openai_api_key=settings.openai_api_key
        )
        logger.info("Initialized WorkflowNodes")

    async def detect_intent(self, state: WorkflowState) -> dict:
        """
        Node: Detect customer intent and sentiment.

        Args:
            state: Current workflow state

        Returns:
            Updated state with problem_type, sentiment, and any errors
        """
        logger.info(f"Detecting intent for ticket: {state['ticket_id']}")

        llm_with_structure = self.llm.with_structured_output(IntentDetection)

        prompt = ChatPromptTemplate.from_messages([
            ("system", INTENT_DETECTION_PROMPT["system"]),
            ("user", INTENT_DETECTION_PROMPT["user"])
        ])

        chain = prompt | llm_with_structure

        try:
            result = await chain.ainvoke({"message": state["raw_message"]})

            return {
                "problem_type": result.problem_type,
                "sentiment": result.sentiment
            }
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            error_update = add_error(state, "detect_intent", str(e), recoverable=True)
            return {
                "problem_type": "other",
                "sentiment": "neutral",
                **error_update
            }

    async def triage_classify(self, state: WorkflowState) -> dict:
        """
        Node: Classify ticket for triage routing.

        Args:
            state: Current workflow state

        Returns:
            Updated state with triage classification
        """
        logger.info(f"Classifying triage for ticket: {state['ticket_id']}")

        llm_with_structure = self.llm.with_structured_output(TriageClassification)

        prompt = ChatPromptTemplate.from_messages([
            ("system", TRIAGE_CLASSIFICATION_PROMPT["system"]),
            ("user", TRIAGE_CLASSIFICATION_PROMPT["user"])
        ])

        chain = prompt | llm_with_structure

        try:
            result = await chain.ainvoke({
                "message": state["raw_message"],
                "sentiment": state.get("sentiment", "neutral"),
                "problem_type": state.get("problem_type", "unknown")
            })

            return {
                "category": result.category,
                "subcategory": result.subcategory,
                "priority": result.priority,
                "sla_hours": result.sla_hours,
                "suggested_team": result.suggested_team,
                "triage_confidence": result.confidence
            }
        except Exception as e:
            logger.error(f"Error classifying triage: {e}")
            error_update = add_error(state, "triage_classify", str(e), recoverable=True)
            return {
                "category": "General",
                "subcategory": "Other",
                "priority": "P2",
                "sla_hours": 24,
                "suggested_team": "general_support",
                "triage_confidence": 0.5,
                **error_update
            }

    async def fleet_lookup(self, state: WorkflowState) -> dict:
        """Node: Lookup device from FleetDM using hostname or email."""
        import re
        logger.info(f"FleetDM lookup for ticket: {state['ticket_id']}")
        from app.services.fleet import create_fleet_client

        fleet = create_fleet_client()
        device_info = None
        device_context = ""

        if not fleet.enabled:
            logger.info("FleetDM not configured")
            return {"device_info": None, "device_context": ""}

        raw_message = state.get("raw_message", "")
        hostname = self._extract_hostname_regex(raw_message)

        if hostname:
            logger.info(f"Extracted hostname: {hostname}")
            device_info = await fleet.search_host(hostname)

        if not device_info:
            email = state.get("customer_email")
            if email and "@" in email:
                device_info = await fleet.search_host(email)

        if device_info:
            # Get full details if we only have summary
            if device_info.id:
                details = await fleet.get_host_details(device_info.id)
                if details:
                    device_info = details
            device_context = fleet.format_device_context(device_info)
            
            # Add intelligent alerts for device issues
            alerts = self._analyze_device_issues(device_info)
            if alerts:
                device_context += "\n\n**DEVICE ALERTS:**\n" + "\n".join([f"⚠️  {alert}" for alert in alerts])
            
            logger.info(f"Found device: {device_info.hostname}")
        else:
            logger.info("No device found")

        return {"device_info": device_info, "device_context": device_context}

    def _extract_hostname_regex(self, message: str):
        """Extract hostname from message using regex patterns."""
        import re
        
        logger.info(f"Extracting hostname from message: {message[:100]}...")
        
        # Pattern 1: Look for "hostname:" or "Hostname:" followed by hostname (handles quoted versions too)
        match = re.search(r'[Hh]ostname\s*:\s*["\']?([A-Z0-9][A-Za-z0-9\-_]{1,})["\']?', message)
        if match:
            hostname = match.group(1).upper()
            logger.info(f"Found hostname via keyword pattern: {hostname}")
            return hostname
        
        # Pattern 2: Try specific corporate hostname patterns first
        patterns = [r'PD-NB\d+', r'[A-Z]{2,3}-\d{5,}', r'DESKTOP-[A-Z0-9]+', r'[A-Z]+-NB\d+']
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                hostname = match.group(0).upper()
                logger.info(f"Found hostname via pattern {pattern}: {hostname}")
                return hostname
        
        # Pattern 3: Look after "gép:", "laptop:", "computer:", "pc:" keywords
        match = re.search(r'(?:gép|laptop|computer|pc|machine)\s*:\s*["\']?([A-Z0-9][A-Za-z0-9\-_]{1,})["\']?', message, re.IGNORECASE)
        if match:
            hostname = match.group(1).upper()
            logger.info(f"Found hostname via device keyword: {hostname}")
            return hostname
        
        logger.info("No hostname found in message")
        return None

    def _analyze_device_issues(self, device_info) -> list:
        """Analyze device info and identify potential issues with alerts."""
        alerts = []
        
        try:
            # Check disk space
            if hasattr(device_info, 'disk_space_available') and device_info.disk_space_available:
                # Typically in GB, warn if less than 10GB or less than 5%
                disk_available = device_info.disk_space_available
                if isinstance(disk_available, str):
                    # Parse "7.0 GB (1%)" format
                    import re
                    match = re.search(r'(\d+\.?\d*)\s*GB', disk_available)
                    if match:
                        disk_gb = float(match.group(1))
                        if disk_gb < 10:
                            alerts.append(f"Low disk space: Only {disk_gb}GB available. Recommend cleanup or expansion.")
            
            # Check policy failures
            if hasattr(device_info, 'policy_issues') and device_info.policy_issues:
                issues = device_info.policy_issues
                if isinstance(issues, dict):
                    failing = issues.get('failing', 0)
                    total = issues.get('total', 0)
                    if failing > 0:
                        alerts.append(f"Security policies failing: {failing}/{total} policies. This requires immediate attention from IT.")
                elif isinstance(issues, str) and 'failing' in issues.lower():
                    alerts.append(f"Security policies failing: {issues}")
            
            # Check if offline
            if hasattr(device_info, 'status') and device_info.status and device_info.status.lower() != 'online':
                alerts.append(f"Device status: {device_info.status}. May have connectivity issues.")
            
            # Check memory (if less than 4GB, could be performance issue)
            if hasattr(device_info, 'memory') and device_info.memory:
                memory_str = str(device_info.memory).lower()
                if 'gb' in memory_str:
                    import re
                    match = re.search(r'(\d+\.?\d*)', memory_str)
                    if match:
                        memory_gb = float(match.group(1))
                        if memory_gb < 4:
                            alerts.append(f"Low memory: {memory_gb}GB RAM. May cause performance issues. Consider upgrade.")
            
        except Exception as e:
            logger.warning(f"Error analyzing device issues: {e}")
        
        return alerts

    async def expand_queries(self, state: WorkflowState) -> dict:
        """
        Node: Generate search query variations.

        Args:
            state: Current workflow state

        Returns:
            Updated state with search_queries
        """
        logger.info(f"Expanding queries for ticket: {state['ticket_id']}")

        try:
            queries = await self.rag.expand_queries(state["raw_message"])
            return {"search_queries": queries}
        except Exception as e:
            logger.error(f"Error expanding queries: {e}")
            error_update = add_error(state, "expand_queries", str(e), recoverable=True)
            return {"search_queries": [state["raw_message"]], **error_update}

    async def search_rag(self, state: WorkflowState) -> dict:
        """
        Node: Perform hybrid vector + keyword search.

        Args:
            state: Current workflow state

        Returns:
            Updated state with retrieved_docs
        """
        logger.info(f"Searching documents for ticket: {state['ticket_id']}")

        queries = state.get("search_queries", [state["raw_message"]])
        category_filter = state.get("category")

        try:
            documents = await self.rag.search_documents(queries, category_filter)
            return {"retrieved_docs": documents}
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            error_update = add_error(state, "search_rag", str(e), recoverable=True)
            return {"retrieved_docs": [], **error_update}

    async def rerank_docs(self, state: WorkflowState) -> dict:
        """
        Node: Rerank and filter retrieved documents.

        Args:
            state: Current workflow state

        Returns:
            Updated state with reranked_docs
        """
        logger.info(f"Reranking documents for ticket: {state['ticket_id']}")

        documents = state.get("retrieved_docs", [])

        try:
            reranked = await self.rag.rerank_documents(state["raw_message"], documents)
            return {"reranked_docs": reranked}
        except Exception as e:
            logger.error(f"Error reranking documents: {e}")
            error_update = add_error(state, "rerank_docs", str(e), recoverable=True)
            return {"reranked_docs": documents, **error_update}

    async def draft_answer(self, state: WorkflowState) -> dict:
        """
        Node: Generate answer draft with citations.

        Args:
            state: Current workflow state

        Returns:
            Updated state with answer_draft and citations
        """
        logger.info(f"Drafting answer for ticket: {state['ticket_id']}")

        llm_with_structure = self.llm.with_structured_output(AnswerDraft)

        # Format context from reranked docs with source info for citations
        context_docs = state.get("reranked_docs", [])
        context_parts = []
        for i, doc in enumerate(context_docs):
            # Extract source info from metadata
            metadata = doc.get("metadata", {})
            source_title = metadata.get("title", doc.get("doc_id", f"Document {i+1}"))
            category = doc.get("category", metadata.get("category", ""))
            source_label = f"{source_title}" + (f" ({category})" if category else "")

            context_parts.append(f"[Source {i+1}: {source_label}]\n{doc['text']}")

        context = "\n\n".join(context_parts)

        # Get device context if available
        device_context = state.get("device_context", "")
        
        # If no device context from state, try to get from fleet_lookup (for non-chat workflows)
        if not device_context:
            logger.info("No device context in state, attempting Fleet lookup")
            # The fleet_lookup node should have run if it was a technical issue
            # If not, device_context will remain empty
        
        logger.info(f"Device context available: {bool(device_context)}")

        # Determine tone based on sentiment
        sentiment = state.get("sentiment", "neutral")
        tone = get_tone_for_sentiment(sentiment)

        prompt = ChatPromptTemplate.from_messages([
            ("system", DRAFT_ANSWER_PROMPT["system"]),
            ("user", DRAFT_ANSWER_PROMPT["user"])
        ])

        chain = prompt | llm_with_structure

        try:
            result = await chain.ainvoke({
                "customer_name": state["customer_name"],
                "problem_type": state.get("problem_type", "support request"),
                "sentiment": sentiment,
                "tone": tone,
                "device_info": device_context if device_context else "No device information available.",
                "context": context or "No specific documentation found.",
                "message": state["raw_message"]
            })

            citations_list = [citation.model_dump() for citation in result.citations] if result.citations else []
            logger.info(f"draft_answer generated {len(citations_list)} citations")
            if citations_list:
                logger.info(f"Citations: {citations_list}")

            return {
                "answer_draft": {
                    "greeting": result.greeting,
                    "body": result.body,
                    "closing": result.closing,
                    "tone": result.tone
                },
                "citations": citations_list
            }
        except Exception as e:
            logger.error(f"Error drafting answer: {e}")
            error_update = add_error(state, "draft_answer", str(e), recoverable=True)
            return {
                "answer_draft": {
                    "greeting": f"Hello {state['customer_name']},",
                    "body": "Thank you for contacting us. We're looking into your request.",
                    "closing": "Best regards,\nSupport Team",
                    "tone": "formal"
                },
                "citations": [],
                **error_update
            }

    async def check_policy(self, state: WorkflowState) -> dict:
        """
        Node: Validate response against company policies.

        Args:
            state: Current workflow state

        Returns:
            Updated state with policy_check
        """
        logger.info(f"Checking policy compliance for ticket: {state['ticket_id']}")

        llm_with_structure = self.llm.with_structured_output(PolicyCheck)

        answer_draft = state.get("answer_draft", {})
        body = answer_draft.get("body", "")

        prompt = ChatPromptTemplate.from_messages([
            ("system", POLICY_CHECK_PROMPT["system"]),
            ("user", POLICY_CHECK_PROMPT["user"])
        ])

        chain = prompt | llm_with_structure

        try:
            result = await chain.ainvoke({"body": body})
            return {"policy_check": result.model_dump()}
        except Exception as e:
            logger.error(f"Error checking policy: {e}")
            error_update = add_error(state, "check_policy", str(e), recoverable=True)
            return {
                "policy_check": {
                    "refund_promise": False,
                    "sla_mentioned": False,
                    "escalation_needed": True,  # Flag for manual review when policy check fails
                    "compliance": "warning",
                    "notes": f"Policy check failed: {str(e)}"
                },
                **error_update
            }

    async def validate_output(self, state: WorkflowState) -> dict:
        """
        Node: Validate and structure final output.

        Args:
            state: Current workflow state

        Returns:
            Updated state with validated output
        """
        logger.info(f"Validating output for ticket: {state['ticket_id']}")

        from datetime import datetime

        # Check if there were any errors during processing
        errors = state.get("errors", [])
        has_errors = len(errors) > 0

        # Debug: log citations from state
        citations_from_state = state.get("citations", [])
        logger.info(f"validate_output: found {len(citations_from_state)} citations in state")
        if citations_from_state:
            logger.info(f"validate_output citations: {citations_from_state}")

        output = {
            "ticket_id": state["ticket_id"],
            "timestamp": datetime.utcnow().isoformat(),
            "triage": {
                "category": state.get("category", "General"),
                "subcategory": state.get("subcategory", "Other"),
                "priority": state.get("priority", "P2"),
                "sla_hours": state.get("sla_hours", 24),
                "suggested_team": state.get("suggested_team", "general_support"),
                "sentiment": state.get("sentiment", "neutral"),
                "confidence": state.get("triage_confidence", 0.0)
            },
            "answer_draft": state.get("answer_draft", {}),
            "citations": citations_from_state,
            "policy_check": state.get("policy_check", {
                "refund_promise": False,
                "sla_mentioned": False,
                "escalation_needed": False,
                "compliance": "passed"
            }),
            # Include error information in output for transparency
            "processing_errors": errors if has_errors else None,
            "had_processing_issues": has_errors
        }

        return {"output": output}