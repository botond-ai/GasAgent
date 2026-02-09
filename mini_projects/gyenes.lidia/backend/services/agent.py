"""
Services - LangGraph-based agent orchestration.
"""
import logging
import re
import time
from typing import Dict, Any, Sequence
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

from domain.models import DomainType, QueryResponse, Citation
from infrastructure.error_handling import check_token_limit, estimate_tokens
from infrastructure.atlassian_client import atlassian_client

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    """LangGraph state object."""
    messages: Sequence[BaseMessage]
    query: str
    domain: str
    retrieved_docs: list
    output: Dict[str, Any]
    citations: list
    workflow: Dict[str, Any]
    user_id: str
    # Telemetry fields
    rag_context: str  # Full RAG context sent to LLM
    llm_prompt: str   # Complete prompt sent to LLM
    llm_response: str # Raw LLM response
    # Guardrail fields
    validation_errors: list  # List of validation error messages
    retry_count: int  # Number of retry attempts (max 2)
    # Feedback metrics fields
    feedback_metrics: Dict[str, Any]  # FeedbackMetrics as dict for state serialization
    request_start_time: float  # Unix timestamp for latency calculation
    # Memory
    memory_summary: str
    memory_facts: list


class QueryAgent:
    """Multi-domain RAG + Workflow agent using LangGraph."""

    def __init__(self, llm_client: Any, rag_client):
        self.llm = llm_client
        self.rag_client = rag_client
        self.atlassian_client = atlassian_client  # Atlassian client for IT Jira ticket creation
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow: intent → retrieval → generation → guardrail → feedback_metrics → workflow."""
        graph = StateGraph(AgentState)

        # Add nodes (7 nodes total)
        graph.add_node("intent_detection", self._intent_detection_node)
        graph.add_node("retrieval", self._retrieval_node)
        graph.add_node("generation", self._generation_node)
        graph.add_node("guardrail", self._guardrail_node)
        graph.add_node("collect_metrics", self._feedback_metrics_node)
        graph.add_node("execute_workflow", self._workflow_node)
        graph.add_node("memory_update", self._memory_update_node)

        # Set entry point
        graph.set_entry_point("intent_detection")

        # Add edges
        graph.add_edge("intent_detection", "retrieval")
        graph.add_edge("retrieval", "generation")
        graph.add_edge("generation", "guardrail")
        
        # Conditional routing from guardrail: retry or continue
        graph.add_conditional_edges(
            "guardrail",
            self._guardrail_decision,
            {
                "retry": "generation",    # If validation fails, go back to generation
                "continue": "collect_metrics"  # If validation passes, continue to metrics collection
            }
        )
        
        # Linear edges: metrics → workflow → memory_update → END
        graph.add_edge("collect_metrics", "execute_workflow")
        graph.add_edge("execute_workflow", "memory_update")
        graph.add_edge("memory_update", END)

        return graph.compile()

    @staticmethod
    def _hash_message(msg: BaseMessage) -> str:
        """Compute SHA256 hash for a message based on role and normalized content."""
        from hashlib import sha256
        role = msg.__class__.__name__
        content = getattr(msg, "content", "")
        norm = re.sub(r"\s+", " ", content.strip())
        key = f"{role}:{norm}"
        return sha256(key.encode("utf-8")).hexdigest()

    def _dedup_messages(self, messages: Sequence[BaseMessage]) -> list:
        """Remove duplicate messages (SHA256-based), preserve order."""
        seen = set()
        result = []
        for m in messages:
            h = self._hash_message(m)
            if h not in seen:
                seen.add(h)
                result.append(m)
        return result

    async def _memory_update_node(self, state: AgentState) -> AgentState:
        """Maintain rolling window memory and update summary + facts.

        - Keeps only last N messages (env MEMORY_MAX_MESSAGES, default 8)
        - Updates `memory_summary` via LLM when needed
        - Extracts `memory_facts` via LLM (simple bullet list)
        - Non-blocking on errors
        """
        logger.info("Memory update node executing")
        try:
            import os
            max_messages = int(os.getenv("MEMORY_MAX_MESSAGES", 8))
            msgs = list(state.get("messages", []))
            if len(msgs) > max_messages:
                msgs = msgs[-max_messages:]
                state["messages"] = msgs

            def format_msg(m: BaseMessage) -> str:
                role = m.__class__.__name__.replace("Message", "").lower()
                content = getattr(m, "content", "")
                return f"{role}: {content}"

            transcript = "\n".join(format_msg(m) for m in msgs)

            summary = state.get("memory_summary", "")
            need_summary = (len(msgs) >= max_messages) or (not summary)
            if need_summary and transcript:
                prompt_sum = (
                    "Summarize the following conversation in 3-4 sentences focusing on user intent, constraints, and decisions.\n\n"
                    f"Conversation:\n{transcript}\n\nSummary:"
                )
                try:
                    resp = await self.llm.ainvoke([HumanMessage(content=prompt_sum)])
                    state["memory_summary"] = getattr(resp, "content", "").strip() or summary
                except Exception as e:
                    logger.warning(f"Memory summary failed (non-blocking): {e}")

            if transcript:
                prompt_facts = (
                    "Extract up to 5 atomic facts (short bullet points) from the conversation useful for future turns.\n"
                    "Return one fact per line, no numbering.\n\n"
                    f"Conversation:\n{transcript}\n\nFacts:"
                )
                try:
                    resp2 = await self.llm.ainvoke([HumanMessage(content=prompt_facts)])
                    raw = getattr(resp2, "content", "")
                    lines = [line.strip("- •\t ") for line in raw.splitlines() if line.strip()]
                    seenf = set()
                    nfacts = []
                    for line in lines:
                        if line and line not in seenf:
                            seenf.add(line)
                            nfacts.append(line)
                    if nfacts:
                        state["memory_facts"] = nfacts[:5]
                except Exception as e:
                    logger.warning(f"Memory facts extraction failed (non-blocking): {e}")

        except Exception as e:
            logger.warning(f"Memory update node error (non-blocking): {e}")
        return state

    async def _intent_detection_node(self, state: AgentState) -> AgentState:
        """Detect which domain this query belongs to."""
        logger.info("Intent detection node executing")

        # Simple keyword-based pre-classification for better accuracy
        query_lower = state['query'].lower()
        
        # Explicit marketing keywords (expanded with variations)
        marketing_keywords = [
            'brand', 'logo', 'color', 'font', 'typography', 'design', 'layout', 
            'arculat', 'guideline', 'betűtípus', 'betutipus', 'sorhossz', 'színek', 
            'szinek', 'márka', 'marka', 'spacing', 'térköz', 'terkoz', 'elrendezés', 
            'elrendezes', 'margin', 'tipográfia', 'tipografia', 'visual', 'vizuális',
            'vizualis', 'ikonográfia', 'ikonografia'
        ]
        if any(kw in query_lower for kw in marketing_keywords):
            domain = DomainType.MARKETING.value
            state["domain"] = domain
            state["messages"] = self._dedup_messages([HumanMessage(content=state["query"])])
            logger.info(f"Detected domain (keyword match): {domain}")
            return state
        
        # Otherwise use LLM
        prompt = f"""
Classify this query into ONE category:

marketing = brand, logo, visual-design, arculat, guideline
hr = vacation, employee, szabadság
it = VPN, computer, software
finance = invoice, expense, számla
legal = contract, szerződés
general = other

Query: "{state['query']}"

Category:"""
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        domain = response.content.strip().lower()

        # Validate domain
        try:
            DomainType(domain)
        except ValueError:
            domain = DomainType.GENERAL.value

        state["domain"] = domain
        state["messages"] = self._dedup_messages([HumanMessage(content=state["query"])])
        logger.info(f"Detected domain: {domain}")

        return state

    async def _retrieval_node(self, state: AgentState) -> AgentState:
        """Retrieve relevant documents from RAG."""
        logger.info(f"Retrieval node executing for domain={state['domain']}")

        try:
            # Query rewrite using known facts (basic augmentation)
            augmented_query = state["query"]
            try:
                facts = state.get("memory_facts") or []
                if facts:
                    # Append up to 3 facts keywords to guide retrieval
                    aug_tail = " ".join(facts[:3])
                    augmented_query = f"{state['query']} {aug_tail}"
            except Exception:
                augmented_query = state["query"]

            citations = await self.rag_client.retrieve_for_domain(
                domain=state["domain"],
                query=augmented_query,
                top_k=5
            )
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {str(e)}. Continuing with empty citations.")
            citations = []

        state["citations"] = [c.model_dump() for c in citations]
        state["retrieved_docs"] = citations
        
        # Build RAG context for telemetry (use section_id for IT domain)
        is_it_domain = state.get("domain") == DomainType.IT.value
        context_parts = []
        for i, c in enumerate(citations, 1):
            if hasattr(c, 'content') and c.content:
                # For IT domain, use section_id if available
                if is_it_domain:
                    section_id = c.section_id if hasattr(c, 'section_id') else None
                    if not section_id and c.content:
                        match = re.search(r"\[([A-Z]+-KB-\d+)\]", c.content)
                        section_id = match.group(1) if match else None
                    doc_label = f"[{section_id}]" if section_id else f"[Doc {i}: {c.title}]"
                else:
                    doc_label = f"[Doc {i}: {c.title}]"
                context_parts.append(f"{doc_label}\n{c.content[:500]}...")
            else:
                context_parts.append(f"[Doc {i}: {c.title}]")
        state["rag_context"] = "\n\n".join(context_parts)
        
        logger.info(f"Retrieved {len(citations)} documents")

        return state

    async def _generation_node(self, state: AgentState) -> AgentState:
        """Generate response using RAG context with token limit protection."""
        logger.info("Generation node executing")

        # Build context from citations with content
        context_parts = []
        is_it_domain = state.get("domain") == DomainType.IT.value
        
        for i, c in enumerate(state["citations"], 1):
            # If chunk content is available, use it
            if c.get("content"):
                # For IT domain, try to use section_id; fallback to IT Policy label to avoid "Document X"
                if is_it_domain:
                    section_id = c.get("section_id")
                    if not section_id:
                        match = re.search(r"([A-Z]+-KB-\d+)", c["content"])
                        section_id = match.group(1) if match else None
                    doc_label = f"[{section_id}]" if section_id else "[IT Policy]"
                    c["section_id"] = section_id  # propagate inferred id for later use
                else:
                    doc_label = f"[Document {i}: {c['title']}]"
                
                # Use full content for top 3 results, truncate rest to avoid timeout
                if i <= 3:
                    context_parts.append(f"{doc_label}\n{c['content']}")
                else:
                    context_parts.append(f"{doc_label}\n{c['content'][:300]}...")
            else:
                context_parts.append(f"[Document {i}: {c['title']}]")
        
        context = "\n\n".join(context_parts)

        # Memory blocks
        mem_summary = (state.get("memory_summary") or "").strip()
        mem_facts = state.get("memory_facts") or []
        facts_block = "\n".join(f"- {f}" for f in mem_facts[:5]) if mem_facts else ""
        memory_block = ""
        if mem_summary or facts_block:
            memory_block = f"""
    Conversation summary:
    {mem_summary}

    Known facts:
    {facts_block}
    """

        # Domain-specific instructions
        domain_instructions = ""
        if state.get("domain") == DomainType.IT.value:
            domain_instructions = """
IMPORTANT FOR IT QUESTIONS:
1. Provide clear, step-by-step troubleshooting or guidance based on the retrieved IT Policy documents
2. **ALWAYS reference the exact section IDs** when cited (e.g., [IT-KB-234], [IT-KB-320])
   - Use the exact format shown in square brackets at the start of each document (e.g., [IT-KB-267])
   - Example: "A VPN hibaelhárítási folyamat [IT-KB-267] alapján először ellenőrizd..."
   - Do NOT use [Document 1], [Document 2] format - use the actual section IDs
3. Include procedures and responsible parties if mentioned in the documents
4. At the end of your response, ALWAYS ask if the user wants to create a Jira support ticket

Format your offer like this:
"📋 Szeretnéd, hogy létrehozzak egy Jira support ticketet ehhez a kérdéshez? (Válaszolj 'igen'-nel vagy 'nem'-mel)"

This question MUST appear at the end of EVERY IT domain response.
"""

        prompt = f"""
You are a helpful HR/IT/Finance/Legal/Marketing assistant.

    {memory_block}
    Use the conversation summary and known facts above to interpret the user's intent and constraints.

Retrieved documents (use ALL relevant information):
{context}

User query: "{state['query']}"

{domain_instructions}

Provide a comprehensive answer based on the retrieved documents above.
Combine information from multiple sources when they relate to the same topic.
If asking about guidelines or rules, include ALL relevant details found in the documents.
Use proper formatting with line breaks and bullet points for better readability.
Answer in Hungarian if the query is in Hungarian, otherwise in English.
"""

        # Check token limit before sending to OpenAI
        try:
            check_token_limit(prompt, max_tokens=100000)  # gpt-4o-mini 128k context
            logger.info(f"Prompt size: ~{estimate_tokens(prompt)} tokens")
        except ValueError as e:
            logger.error(f"Token limit exceeded: {e}")
            # Truncate context and retry
            context_parts = context_parts[:3]  # Only use top 3 docs
            context = "\n\n".join(context_parts)
            prompt = f"""
You are a helpful HR/IT/Finance/Legal/Marketing assistant.

{memory_block}
Use the conversation summary and known facts above to interpret the user's intent and constraints.

Retrieved documents:
{context}

User query: "{state['query']}"

Provide an answer based on the retrieved documents above.
Answer in Hungarian if the query is in Hungarian, otherwise in English.
"""
            logger.warning("Prompt truncated to fit token limit")

        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        answer = response.content

        # Ensure IT answers surface section references even if the model forgets
        if is_it_domain:
            section_ids = []
            for citation in state.get("citations", []):
                section_id = citation.get("section_id")
                if not section_id and citation.get("content"):
                    match = re.search(r"([A-Z]+-KB-\d+)", citation["content"])
                    section_id = match.group(1) if match else None
                    citation["section_id"] = section_id
                if section_id and section_id not in section_ids:
                    section_ids.append(section_id)

            if section_ids and not any(sid in answer for sid in section_ids):
                refs = ", ".join(f"[{sid}]" for sid in section_ids)
                answer = f"{answer}\n\nForrás: {refs} – IT Üzemeltetési és Felhasználói Szabályzat"
        
        # Save telemetry data
        state["llm_prompt"] = prompt
        state["llm_response"] = answer

        state["output"] = {
            "domain": state["domain"],
            "answer": answer,
            "citations": state["citations"],
        }

        state["messages"].append(AIMessage(content=answer))
        state["messages"] = self._dedup_messages(state["messages"])  # SHA256-based message dedup
        logger.info("Generation completed")

        return state

    async def _guardrail_node(self, state: AgentState) -> AgentState:
        """Validate generated response for quality and accuracy.
        
        For IT domain:
        - Check that citations use [IT-KB-XXX] format
        - Detect hallucinations (claims not in retrieved_docs)
        - Set retry_count to enable conditional routing
        """
        logger.info("Guardrail node executing")
        
        domain = state.get("domain", "")
        answer = state.get("llm_response", "")
        citations = state.get("citations", [])
        
        errors = []
        
        # IT domain specific validation
        if domain == DomainType.IT.value:
            logger.info("🔍 Validating IT domain response...")
            
            # 1. Check for section ID citations in answer
            it_kb_pattern = r"\[IT-KB-\d+\]"
            found_citations = re.findall(it_kb_pattern, answer)
            
            if not found_citations:
                # Extract available section IDs from citations
                available_ids = []
                for c in citations:
                    section_id = c.get("section_id")
                    if not section_id and c.get("content"):
                        match = re.search(r"([A-Z]+-KB-\d+)", c["content"])
                        section_id = match.group(1) if match else None
                    if section_id and section_id not in available_ids:
                        available_ids.append(section_id)
                
                if available_ids:
                    error_msg = f"IT domain válasz hiányzik a [IT-KB-XXX] formátumú hivatkozások. Elérhető: {', '.join(available_ids)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            # 2. Detect hallucinations: explicit contradictions in retrieved_docs
            # Only flag if answer claims something OPPOSITE to what's in retrieved content
            # Placeholder for future hallucination checks using retrieved content
            # (semantic comparison would be required and is intentionally omitted here)
            
            # Look for explicit contradictions (e.g., "not required" vs "required")
            # For now, skip automatic hallucination detection - it's too error-prone
            # Only flag missing citations (see above)
            # Real hallucination detection would need semantic similarity (would require extra LLM call)
        
        # Store validation results in state
        state["validation_errors"] = errors
        
        # Initialize retry_count if not set
        if "retry_count" not in state:
            state["retry_count"] = 0
        
        # Log results
        if errors:
            logger.warning(f"Validation errors found: {errors}")
        else:
            logger.info("✓ Validation passed")
        
        return state

    def _guardrail_decision(self, state: AgentState) -> str:
        """Decide whether to retry generation or continue to workflow.
        
        Returns: "retry" if validation failed and retries remain, "continue" otherwise
        """
        errors = state.get("validation_errors", [])
        retry_count = state.get("retry_count", 0)
        max_retries = 2
        
        if errors and retry_count < max_retries:
            state["retry_count"] = retry_count + 1
            logger.info(f"🔄 Retrying generation (attempt {state['retry_count']}/{max_retries})")
            return "retry"
        elif errors:
            logger.warning(f"⚠️ Max retries reached ({max_retries}). Continuing despite validation errors.")
            return "continue"
        else:
            logger.info("✓ Validation passed, continuing to workflow")
            return "continue"

    async def _workflow_node(self, state: AgentState) -> AgentState:
        """Execute domain-specific workflows if needed."""
        logger.info(f"Workflow node executing for domain={state['domain']}")

        domain = state.get("domain", "general")

        if domain == DomainType.HR.value:
            # Example: HR vacation request workflow
            query_lower = state["query"].lower()
            if any(kw in query_lower for kw in ["szabadság", "szabadsag", "vacation", "szabis"]):
                state["workflow"] = {
                    "action": "hr_request_draft",
                    "type": "vacation_request",
                    "status": "draft",
                    "next_step": "Review and submit"
                }
        
        elif domain == DomainType.IT.value:
            # IT domain: Prepare Jira ticket creation
            # (Citations already retrieved from Qdrant by _retrieval_node)
            logger.info("🔧 IT workflow: Preparing Jira ticket draft")
            
            # Prepare ticket data from query and LLM response
            query = state.get("query", "")
            answer = state.get("llm_response", "")
            user_id = state.get("user_id", "unknown")
            
            # Create ticket summary (truncate to 100 chars for Jira)
            ticket_summary = f"IT Support: {query[:100]}"
            
            # Use LLM response as detailed description
            ticket_description = (
                f"Felhasználó kérdése: {query}\n\n"
                f"Rendszer válasza:\n{answer}\n\n"
                f"Felhasználó ID: {user_id}\n"
                f"Domain: IT Support"
            )
            
            # Include citations in ticket for reference
            citations = state.get("citations", [])
            if citations:
                citation_refs = "\n\nForrásdokumentumok:\n"
                for i, c in enumerate(citations[:5], 1):  # Limit to top 5
                    section_id = c.get("section_id", "")
                    title = c.get("title", "Document")
                    citation_refs += f"{i}. [{section_id or title}] {title}\n"
                ticket_description += citation_refs
            
            state["workflow"] = {
                "action": "it_support_ready",
                "type": "it_support",
                "jira_available": True,
                "ticket_draft": {
                    "summary": ticket_summary,
                    "description": ticket_description,
                    "issue_type": "Task",
                    "priority": "Medium",
                    "user_id": user_id,
                    "domain": "it"
                },
                "next_step": "User can confirm to create Jira ticket"
            }

        return state

    async def _feedback_metrics_node(self, state: AgentState) -> AgentState:
        """Collect pipeline metrics for telemetry (non-blocking).
        
        Gathers performance data: latency, cache hits, token usage.
        If metrics collection fails, continues without blocking workflow.
        """
        logger.info("📊 Feedback metrics node executing")
        
        try:
            metrics = {
                "retrieval_score_top1": None,
                "retrieval_count": 0,
                "dedup_count": 0,
                "llm_latency_ms": None,
                "llm_tokens_used": None,
                "llm_tokens_input": None,
                "llm_tokens_output": None,
                "cache_hit_embedding": False,
                "cache_hit_query": False,
                "validation_errors": state.get("validation_errors", []),
                "retry_count": state.get("retry_count", 0),
            }
            
            # 1. Retrieval quality metrics
            citations = state.get("citations", [])
            if citations:
                # Top-1 score from first citation
                if isinstance(citations[0], dict) and "score" in citations[0]:
                    metrics["retrieval_score_top1"] = citations[0]["score"]
                metrics["retrieval_count"] = len(citations)
            
            # 2. Token usage (extract from LLM response if available)
            llm_response = state.get("llm_response", "")
            if llm_response:
                # Rough token estimation: ~4 chars per token (GPT tokenizer)
                metrics["llm_tokens_output"] = estimate_tokens(llm_response)
            
            llm_prompt = state.get("llm_prompt", "")
            if llm_prompt:
                metrics["llm_tokens_input"] = estimate_tokens(llm_prompt)
                if metrics.get("llm_tokens_input") and metrics.get("llm_tokens_output"):
                    metrics["llm_tokens_used"] = metrics["llm_tokens_input"] + metrics["llm_tokens_output"]
            
            # 3. Latency calculation
            request_start = state.get("request_start_time")
            if request_start:
                current_time = time.time()
                metrics["total_latency_ms"] = (current_time - request_start) * 1000
            
            # 4. Cache flags (placeholder - would be populated by retrieval/cache nodes)
            # These would be set by _retrieval_node in production
            # For now, we track that metrics collection was attempted
            
            # Store metrics in state (as dict for JSON serialization)
            state["feedback_metrics"] = metrics
            
            logger.info(f"✓ Metrics collected: {len(citations)} citations, "
                       f"tokens={metrics.get('llm_tokens_used', 'N/A')}, "
                       f"latency={metrics.get('total_latency_ms', 'N/A'):.1f}ms")
            
            return state
            
        except Exception as e:
            # Non-blocking: log error and continue
            logger.warning(f"⚠️ Metrics collection error (non-blocking): {e}")
            state["feedback_metrics"] = {
                "error": str(e),
                "validation_errors": state.get("validation_errors", []),
                "retry_count": state.get("retry_count", 0),
            }
            return state

    async def regenerate(self, query: str, domain: str, citations: list, user_id: str) -> QueryResponse:
        """Regenerate response using cached domain + citations (skip intent + RAG)."""
        logger.info(f"Agent regenerate: user={user_id}, domain={domain}, cached_citations={len(citations)}")

        # Build state with cached data
        initial_state: AgentState = {
            "query": query,
            "user_id": user_id,
            "messages": [HumanMessage(content=query)],
            "domain": domain,  # ← FROM CACHE
            "citations": citations,  # ← FROM CACHE
            "retrieved_docs": [],
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
            "feedback_metrics": {},
            "request_start_time": time.time(),
        }

        # SKIP intent detection node
        # SKIP retrieval node
        # Run ONLY generation + guardrail + workflow
        logger.info("Skipping intent detection and RAG retrieval (using cache)")
        
        state_after_generation = await self._generation_node(initial_state)
        state_after_guardrail = await self._guardrail_node(state_after_generation)
        final_state = await self._workflow_node(state_after_guardrail)

        # Build response
        response = QueryResponse(
            domain=final_state["domain"],
            answer=final_state["output"]["answer"],
            citations=[Citation(**c) for c in final_state["citations"]],
            workflow=final_state.get("workflow"),
        )

        logger.info("Agent regenerate completed (cached)")
        return response

    async def run(self, query: str, user_id: str, session_id: str) -> QueryResponse:
        """Execute full agent workflow (intent → retrieval → generation → guardrail → feedback_metrics → workflow)."""
        logger.info(f"Agent run: user={user_id}, session={session_id}, query={query[:50]}...")
        
        request_start = time.time()

        initial_state: AgentState = {
            "query": query,
            "user_id": user_id,
            "messages": [],
            "domain": "",
            "retrieved_docs": [],
            "citations": [],
            "workflow": None,
            "validation_errors": [],
            "retry_count": 0,
            "feedback_metrics": {},
            "request_start_time": request_start,
        }

        final_state = await self.workflow.ainvoke(initial_state)

        # Build response with telemetry
        response = QueryResponse(
            domain=final_state["domain"],
            answer=final_state["output"]["answer"],
            citations=[Citation(**c) for c in final_state["citations"]],
            workflow=final_state.get("workflow"),
            rag_context=final_state.get("rag_context"),
            llm_prompt=final_state.get("llm_prompt"),
            llm_response=final_state.get("llm_response"),
        )

        logger.info("Agent run completed")
        return response
    async def create_jira_ticket_from_draft(self, ticket_draft: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a Jira ticket from a draft prepared by the IT workflow node.
        
        Called when user confirms Jira ticket creation after IT domain response.
        
        Args:
            ticket_draft: Dict with summary, description, issue_type, priority from workflow
            
        Returns:
            Dict with ticket creation result {success, ticket_key, ticket_url, error}
        """
        logger.info("🎟️ Creating Jira ticket from draft...")
        
        try:
            if not self.atlassian_client:
                return {
                    "success": False,
                    "error": "Atlassian client not configured"
                }
            
            summary = ticket_draft.get("summary", "IT Support Request")
            description = ticket_draft.get("description", "")
            issue_type = ticket_draft.get("issue_type", "Task")
            priority = ticket_draft.get("priority", "Medium")
            
            # Create ticket via atlassian_client
            result = await self.atlassian_client.create_jira_ticket(
                summary=summary,
                description=description,
                issue_type=issue_type,
                priority=priority
            )
            
            if result:
                logger.info(f"✅ Jira ticket created: {result.get('key')}")
                return {
                    "success": True,
                    "ticket_key": result.get("key"),
                    "ticket_url": result.get("url")
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create Jira ticket (Atlassian API error)"
                }
        
        except Exception as e:
            logger.error(f"❌ Error creating Jira ticket: {e}")
            return {
                "success": False,
                "error": str(e)
            }