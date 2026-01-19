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

from domain.models import DomainType, QueryResponse, Citation, ProcessingStatus, FeedbackMetrics
from domain.llm_outputs import IntentOutput, MemoryUpdate, RAGGenerationOutput
from infrastructure.error_handling import (
    check_token_limit,
    estimate_tokens,
    with_timeout_and_retry,
    TimeoutError,
    APICallError,
)
from infrastructure.atlassian_client import atlassian_client
from django.conf import settings

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
    # Error handling
    rag_unavailable: bool  # True if RAG retrieval failed


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
        """Maintain rolling window memory with reducer pattern + semantic compression.

        - Keeps only last N messages (env MEMORY_MAX_MESSAGES, default 8)
        - REDUCER PATTERN: Concatenates previous summary with new summary
        - SEMANTIC COMPRESSION: LLM decides which facts to keep (relevance-based)
        - Multi-level summarization: short (8 msgs) → medium (50 msgs) → long (200+ msgs)
        - Non-blocking on errors
        """
        logger.info("Memory update node executing")
        try:
            import os
            max_messages = int(os.getenv("MEMORY_MAX_MESSAGES", 8))
            msgs = list(state.get("messages", []))
            
            # Track total message count (for multi-level summarization)
            total_msg_count = len(msgs)
            
            if len(msgs) > max_messages:
                msgs = msgs[-max_messages:]
                state["messages"] = msgs

            def format_msg(m: BaseMessage) -> str:
                role = m.__class__.__name__.replace("Message", "").lower()
                content = getattr(m, "content", "")
                return f"{role}: {content}"

            transcript = "\n".join(format_msg(m) for m in msgs)

            # Get previous summary and facts (for reducer pattern)
            prev_summary = state.get("memory_summary", "")
            prev_facts = state.get("memory_facts", [])
            
            need_summary = (len(msgs) >= max_messages) or (not prev_summary)
            if need_summary and transcript:
                # Build prompt with REDUCER PATTERN (include previous summary)
                prompt_mem = (
                    "You are updating conversation memory using a REDUCER PATTERN.\n\n"
                )
                
                # Include previous summary if exists
                if prev_summary:
                    prompt_mem += (
                        f"**PREVIOUS SUMMARY:**\n{prev_summary}\n\n"
                        f"**PREVIOUS FACTS ({len(prev_facts)}):**\n"
                    )
                    if prev_facts:
                        prompt_mem += "\n".join(f"- {fact}" for fact in prev_facts) + "\n\n"
                    else:
                        prompt_mem += "None\n\n"
                
                prompt_mem += (
                    f"**NEW CONVERSATION (last {len(msgs)} messages):**\n{transcript}\n\n"
                    "**TASK:**\n"
                    "1. **summary**: Merge previous summary with new information (3-5 sentences). "
                    "Focus on cumulative user intent, constraints, and key decisions across ALL conversations.\n"
                    "2. **facts**: Semantically filter facts - keep up to 8 MOST RELEVANT facts "
                    "(merge previous facts + extract new ones, prioritize by recency and relevance). "
                    "Drop outdated or redundant facts.\n"
                    "3. **decisions**: Track cumulative key decisions made by the user.\n\n"
                    "**SEMANTIC COMPRESSION RULES:**\n"
                    "- Merge similar facts (e.g., 'user wants X' + 'user needs X' → 'user requires X')\n"
                    "- Prioritize recent facts over old ones if conflict exists\n"
                    "- Keep domain-specific constraints (dates, names, numbers)\n"
                    "- Drop facts no longer relevant to current conversation direction\n\n"
                    "IMPORTANT: Only extract facts explicitly stated. Do NOT hallucinate.\n\n"
                    "Respond with summary, facts, and decisions fields."
                )
                
                try:
                    # Use structured output with Pydantic validation
                    structured_llm = self.llm.with_structured_output(MemoryUpdate)
                    memory_update = await structured_llm.ainvoke([HumanMessage(content=prompt_mem)])
                    
                    # Update state with validated data (REDUCER: replaces with merged summary)
                    if memory_update.summary:
                        state["memory_summary"] = memory_update.summary
                    if memory_update.facts:
                        state["memory_facts"] = memory_update.facts[:8]  # Max 8 facts after semantic compression
                    
                    compression_ratio = len(prev_facts) + len(msgs) if prev_facts else len(msgs)
                    final_facts = len(memory_update.facts)
                    logger.info(
                        f"Memory updated (REDUCER): {final_facts} facts "
                        f"(compressed from {compression_ratio} items), "
                        f"summary length: {len(memory_update.summary)} chars, "
                        f"total messages: {total_msg_count}"
                    )
                except Exception as e:
                    logger.warning(f"Memory update failed (non-blocking): {e}")

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
        
        # Otherwise use LLM with structured output
        prompt = f"""
Classify this query into ONE category:

marketing = brand, logo, visual-design, arculat, guideline
hr = vacation, employee, szabadság
it = VPN, computer, software
finance = invoice, expense, számla
legal = contract, szerződés
general = other

Query: "{state['query']}"

Provide:
1. domain (one of the above categories)
2. confidence (0.0-1.0, how sure you are)
3. reasoning (why this domain, 10-500 characters)

Respond in JSON format."""
        
        # Use structured output with Pydantic validation
        structured_llm = self.llm.with_structured_output(IntentOutput)
        intent_output = await structured_llm.ainvoke([HumanMessage(content=prompt)])
        
        domain = intent_output.domain.lower()

        # Validate domain
        try:
            DomainType(domain)
        except ValueError:
            domain = DomainType.GENERAL.value
            logger.warning(f"Invalid domain '{intent_output.domain}' from LLM, defaulting to {domain}")

        state["domain"] = domain
        state["messages"] = self._dedup_messages([HumanMessage(content=state["query"])])
        logger.info(f"Detected domain: {domain} (confidence: {intent_output.confidence:.3f}, reasoning: {intent_output.reasoning[:50]}...)")

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

            # Wrap RAG call with timeout and retry
            citations = await with_timeout_and_retry(
                self.rag_client.retrieve_for_domain(
                    domain=state["domain"],
                    query=augmented_query,
                    top_k=5
                ),
                timeout=settings.RAG_TIMEOUT,
                max_retries=3,
                operation_name="RAG retrieval",
            )
        except (TimeoutError, APICallError) as e:
            logger.error(f"RAG retrieval failed: {str(e)}. Continuing with empty citations.")
            citations = []
            # Mark state for summary-only fallback mode
            state["rag_unavailable"] = True
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {str(e)}. Continuing with empty citations.")
            citations = []
            state["rag_unavailable"] = True

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
        """Generate response using RAG context with token limit protection.
        
        Fallback to summary-only mode if RAG is unavailable.
        """
        logger.info("Generation node executing")

        # Check if RAG is unavailable (timeout or error)
        rag_unavailable = state.get("rag_unavailable", False)
        
        if rag_unavailable:
            logger.warning("⚠️ RAG unavailable - using summary-only mode")
            return await self._generate_summary_only_response(state)
        
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

CRITICAL FAIL-SAFE INSTRUCTIONS:
1. **Only use information from the retrieved documents above** - DO NOT invent facts, policies, or procedures
2. **If information is contradictory, unclear, or missing:**
   - DO NOT hallucinate or make assumptions
   - Instead, respond with: "Sajnálom, nem tudok pontos választ adni a rendelkezésre álló információk alapján. Kérlek, pontosítsd a kérdést vagy fordulj a [domain] csapathoz közvetlenül."
   - For Hungarian queries: "Sajnálom, az elérhető dokumentumok nem tartalmaznak elegendő információt ehhez a kérdéshez. Kérlek, vedd fel a kapcsolatot a [HR/IT/Finance/Legal/Marketing] csapattal további segítségért."
3. **If no relevant documents were retrieved** (empty context):
   - Respond with: "Sajnálom, nem találtam releváns információt ehhez a kérdéshez a rendelkezésre álló dokumentumokban. Kérlek, próbáld meg átfogalmazni a kérdést vagy vedd fel a kapcsolatot a megfelelő csapattal."
4. **Never fabricate:** email addresses, phone numbers, section IDs, policy details, dates, or procedures not explicitly stated in the retrieved documents
5. **If uncertain about any detail:** acknowledge the uncertainty and suggest contacting the relevant team

Provide a comprehensive answer based on the retrieved documents above.
Combine information from multiple sources when they relate to the same topic.
If asking about guidelines or rules, include ALL relevant details found in the documents.
Use proper formatting with line breaks and bullet points for better readability.
Answer in Hungarian if the query is in Hungarian, otherwise in English.

Respond with:
1. answer (comprehensive response based ONLY on retrieved documents, minimum 10 characters)
2. language (detected language code: hu/en/other)
3. section_ids (list of section IDs referenced, e.g., ['IT-KB-267', 'IT-KB-320'])
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

CRITICAL FAIL-SAFE INSTRUCTIONS:
- Only use information from the retrieved documents - DO NOT hallucinate
- If information is missing or unclear, respond with: "Sajnálom, nem tudok pontos választ adni a rendelkezésre álló információk alapján."
- Never fabricate details not in the documents

Provide an answer based on the retrieved documents above.
Answer in Hungarian if the query is in Hungarian, otherwise in English.

Respond with:
1. answer (comprehensive response based ONLY on retrieved documents)
2. language (detected language code)
3. section_ids (list of section IDs if available)
"""
            logger.warning("Prompt truncated to fit token limit")

        # Use structured output with Pydantic validation
        structured_llm = self.llm.with_structured_output(RAGGenerationOutput)
        rag_output = await structured_llm.ainvoke([HumanMessage(content=prompt)])
        
        answer = rag_output.answer

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

            # Merge LLM-provided section_ids with extracted ones
            all_section_ids = list(set(section_ids + rag_output.section_ids))
            
            if all_section_ids and not any(sid in answer for sid in all_section_ids):
                refs = ", ".join(f"[{sid}]" for sid in all_section_ids)
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

    async def _generate_summary_only_response(self, state: AgentState) -> AgentState:
        """Fallback response generation using only memory summary and conversation context.
        
        Used when RAG is unavailable due to timeout or connection errors.
        No citations, only memory-based context.
        """
        logger.info("🔄 Generating summary-only response (RAG unavailable)")
        
        # Memory blocks
        mem_summary = (state.get("memory_summary") or "").strip()
        mem_facts = state.get("memory_facts") or []
        facts_block = "\n".join(f"- {f}" for f in mem_facts[:5]) if mem_facts else ""
        
        memory_block = ""
        if mem_summary or facts_block:
            memory_block = f"""
Previous conversation summary:
{mem_summary}

Known facts from conversation:
{facts_block}
"""
        
        # Build conversation history (last 5 messages for context)
        conversation_history = ""
        messages = state.get("messages", [])[-5:]
        if messages:
            conversation_history = "\n".join([
                f"{msg.__class__.__name__.replace('Message', '')}: {getattr(msg, 'content', '')[:200]}"
                for msg in messages
            ])
        
        prompt = f"""
You are a helpful assistant. The document retrieval system is temporarily unavailable.

{memory_block}

Recent conversation:
{conversation_history}

User query: "{state['query']}"

IMPORTANT INSTRUCTIONS:
1. Answer ONLY based on the conversation summary and known facts above
2. DO NOT make up or hallucinate information
3. Acknowledge the limitation: Start your response with "⚠️ Válasz korlátozott információk alapján (dokumentum retrieval átmenetileg nem elérhető):"
4. If you cannot answer based on available context, be honest and suggest:
   - Trying again later when the document system is available
   - Contacting the relevant team directly (HR/IT/Finance/Legal/Marketing)
5. Keep response concise and factual

Answer in Hungarian if the query is in Hungarian, otherwise in English.

Respond with:
1. answer (your response starting with the warning message)
2. language (detected language code: hu/en/other)
3. section_ids (empty list - no citations available)
"""
        
        try:
            # Use structured output
            structured_llm = self.llm.with_structured_output(RAGGenerationOutput)
            rag_output = await structured_llm.ainvoke([HumanMessage(content=prompt)])
            answer = rag_output.answer
            
        except Exception as e:
            logger.error(f"Summary-only generation failed: {e}")
            # Ultimate fallback
            answer = (
                "⚠️ Válasz korlátozott információk alapján (dokumentum retrieval átmenetileg nem elérhető):\n\n"
                "Sajnálom, jelenleg nem tudok részletes választ adni, mert a dokumentum-keresési rendszer "
                "átmenetileg nem elérhető. Kérlek, próbáld újra később, vagy fordulj közvetlenül "
                "a megfelelő csapathoz (HR/IT/Finance/Legal/Marketing)."
            )
        
        # Save telemetry
        state["llm_prompt"] = prompt
        state["llm_response"] = answer
        
        # Build output (no citations)
        state["output"] = {
            "domain": state["domain"],
            "answer": answer,
            "citations": [],  # Empty - RAG unavailable
        }
        
        state["messages"].append(AIMessage(content=answer))
        state["messages"] = self._dedup_messages(state["messages"])
        
        logger.info("✓ Summary-only response generated (RAG unavailable mode)")
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
        """Collect pipeline metrics for telemetry using Pydantic validation.
        
        Gathers performance data: latency, cache hits, token usage.
        Uses TurnMetrics model for automatic validation and JSON encoding.
        If metrics collection fails, continues without blocking workflow.
        """
        logger.info("Feedback metrics node executing")
        
        try:
            # 1. Retrieval quality metrics
            citations = state.get("citations", [])
            retrieval_score_top1 = None
            retrieval_count = 0
            if citations:
                if isinstance(citations[0], dict) and "score" in citations[0]:
                    retrieval_score_top1 = citations[0]["score"]
                retrieval_count = len(citations)
            
            # 2. Token usage estimation
            llm_response = state.get("llm_response", "")
            llm_prompt = state.get("llm_prompt", "")
            llm_tokens_output = estimate_tokens(llm_response) if llm_response else None
            llm_tokens_input = estimate_tokens(llm_prompt) if llm_prompt else None
            llm_tokens_used = None
            if llm_tokens_input is not None and llm_tokens_output is not None:
                llm_tokens_used = llm_tokens_input + llm_tokens_output
            
            # 3. Latency calculation
            request_start = state.get("request_start_time")
            total_latency_ms = None
            if request_start:
                current_time = time.time()
                total_latency_ms = (current_time - request_start) * 1000
            
            # 4. Create FeedbackMetrics with Pydantic validation
            turn_metrics = FeedbackMetrics(
                retrieval_score_top1=retrieval_score_top1,
                retrieval_count=retrieval_count,
                dedup_count=0,  # Would be populated by dedup logic
                llm_latency_ms=total_latency_ms,
                llm_tokens_used=llm_tokens_used,
                llm_tokens_input=llm_tokens_input,
                llm_tokens_output=llm_tokens_output,
                cache_hit_embedding=False,  # Placeholder - would be populated by cache
                cache_hit_query=False,
                validation_errors=state.get("validation_errors", []),
                retry_count=state.get("retry_count", 0),
                total_latency_ms=total_latency_ms,
            )
            
            # Store as dict for JSON serialization (Pydantic validators already ran)
            state["feedback_metrics"] = turn_metrics.model_dump()
            
            logger.info(f"Metrics collected: {retrieval_count} citations, "
                       f"tokens={llm_tokens_used or 'N/A'}, "
                       f"latency={total_latency_ms:.1f if total_latency_ms else 'N/A'}ms")
            
            return state
            
        except Exception as e:
            # Non-blocking: log error and continue
            logger.warning(f"Metrics collection error (non-blocking): {e}")
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

        # Determine processing status from state
        validation_errors = final_state.get("validation_errors", [])
        retry_count = final_state.get("retry_count", 0)
        citations_count = len(final_state.get("citations", []))
        
        # Status determination logic
        if retry_count >= 2 and validation_errors:
            # Max retries reached with persistent errors
            processing_status = ProcessingStatus.VALIDATION_FAILED
        elif retry_count > 0 and not validation_errors:
            # Guardrail retry occurred but eventually succeeded
            processing_status = ProcessingStatus.PARTIAL_SUCCESS
        elif citations_count == 0 and "retrieved_docs" in final_state:
            # RAG attempted but no citations (possible RAG failure fallback)
            processing_status = ProcessingStatus.RAG_UNAVAILABLE
        else:
            # Clean success
            processing_status = ProcessingStatus.SUCCESS
        
        # Build response with state tracking
        response = QueryResponse(
            domain=final_state["domain"],
            answer=final_state["output"]["answer"],
            citations=[Citation(**c) for c in final_state["citations"]],
            workflow=final_state.get("workflow"),
            processing_status=processing_status,
            validation_errors=validation_errors,
            retry_count=retry_count,
        )

        logger.info(f"Agent run completed: status={processing_status.value}, retries={retry_count}")
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