"""
Services - LangGraph-based agent orchestration.
"""
import asyncio
import logging
import os
import re
import time
from typing import Dict, Any, Sequence
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

from domain.models import DomainType, QueryResponse, Citation, ProcessingStatus, FeedbackMetrics
from domain.llm_outputs import ToolResult
from infrastructure.error_handling import (
    check_token_limit,
    estimate_tokens,
    with_timeout_and_retry,
    TimeoutError,
    APICallError,
)
from infrastructure.prometheus_metrics import MetricsCollector
from infrastructure.atlassian_client import atlassian_client
from infrastructure.tool_registry import ToolRegistry
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
    llm_input_tokens: int  # LLM input tokens
    llm_output_tokens: int  # LLM output tokens
    llm_total_cost: float  # LLM cost in USD
    # Guardrail fields
    validation_errors: list  # List of validation error messages
    retry_count: int  # Number of retry attempts (max 2)
    # Feedback metrics fields
    feedback_metrics: Dict[str, Any]  # FeedbackMetrics as dict for state serialization
    request_start_time: float  # Unix timestamp for latency calculation
    # Memory
    memory_summary: str
    memory_facts: list
    # Planning
    execution_plan: Dict[str, Any]  # ExecutionPlan as dict for state serialization
    tool_selection: Dict[str, Any]  # ToolSelection as dict for state serialization
    observation_result: Dict[str, Any]  # ObservationOutput as dict for state serialization
    replan_count: int  # Number of replan iterations (max 2)
    # Error handling
    rag_unavailable: bool  # True if RAG retrieval failed


class QueryAgent:
    """Multi-domain RAG + Workflow agent using LangGraph."""

    def __init__(self, llm_client: Any, rag_client, tool_registry: ToolRegistry | None = None):
        self.llm = llm_client
        self.rag_client = rag_client
        self.atlassian_client = atlassian_client  # Atlassian client for IT Jira ticket creation
        self.tool_registry = tool_registry or ToolRegistry.default()
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow: intent → plan → tool_selection → retrieval → generation → guardrail → metrics → workflow → memory."""
        graph = StateGraph(AgentState)

        # Add nodes (11 nodes total)
        graph.add_node("intent_detection", self._intent_detection_node)
        graph.add_node("plan_node", self._plan_node)
        graph.add_node("select_tools", self._tool_selection_node)
        graph.add_node("tool_executor", self._tool_executor_node)
        graph.add_node("observation_check", self._observation_node)
        graph.add_node("retrieval", self._retrieval_node)
        graph.add_node("generation", self._generation_node)
        graph.add_node("guardrail", self._guardrail_node)
        graph.add_node("collect_metrics", self._feedback_metrics_node)
        graph.add_node("execute_workflow", self._workflow_node)
        graph.add_node("memory_update", self._memory_update_node)

        # Set entry point
        graph.set_entry_point("intent_detection")

        # Add edges
        graph.add_edge("intent_detection", "plan_node")
        graph.add_edge("plan_node", "select_tools")
        
        # Conditional routing from select_tools based on route
        graph.add_conditional_edges(
            "select_tools",
            self._tool_selection_decision,
            {
                "rag_only": "retrieval",       # RAG search only
                "tools_only": "tool_executor", # Execute tools
                "rag_and_tools": "tool_executor"  # Execute tools first, then retrieval
            }
        )
        
        # After tool_executor: if rag_and_tools → go to retrieval, else observation_check
        graph.add_conditional_edges(
            "tool_executor",
            lambda state: "retrieval" if state.get("tool_selection", {}).get("route") == "rag_and_tools" else "observation_check",
            {
                "retrieval": "retrieval",  # rag_and_tools case: do RAG after tools
                "observation_check": "observation_check"  # tools_only case: skip to observation
            }
        )
        
        # Retrieval always goes to observation
        graph.add_edge("retrieval", "observation_check")
        
        # Conditional routing from observation: replan or generate
        graph.add_conditional_edges(
            "observation_check",
            self._observation_decision,
            {
                "replan": "plan_node",     # Loop back to planning if insufficient info
                "generate": "generation"   # Proceed to generation if sufficient
            }
        )
        
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

    def _tool_selection_decision(self, state: AgentState) -> str:
        """Determine routing based on selected tools."""
        tool_selection = state.get("tool_selection", {})
        route = tool_selection.get("route", "rag_only")
        
        logger.info(f"Tool selection decision: route={route}")
        return route
    
    def _observation_decision(self, state: AgentState) -> str:
        """Determine routing based on observation: replan or generate.
        
        Max 2 replans allowed. After that, force generation.
        NOTE: Decision functions CANNOT modify state - read-only!
        """
        observation = state.get("observation_result", {})
        replan_count = state.get("replan_count", 0)
        next_action = observation.get("next_action", "generate")
        
        # Enforce max replan limit
        if next_action == "replan" and replan_count < 2:
            # Don't modify state here - will be incremented in plan_node
            logger.info(f"Observation decision: REPLAN (attempt {replan_count + 1}/2)")
            return "replan"
        
        if next_action == "replan" and replan_count >= 2:
            logger.warning("Max replan limit (2) reached. Forcing GENERATE despite insufficient info.")
        
        logger.info(f"Observation decision: GENERATE (replan_count={replan_count})")
        return "generate"

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
                    # Use JSON text output instead of structured_output (buggy in LangChain)
                    prompt_mem_json = prompt_mem + "\n\nRespond with JSON: {\"summary\": \"...\", \"facts\": [...], \"key_decisions\": [...]}"
                    response = await self.llm.ainvoke([HumanMessage(content=prompt_mem_json)])
                    response_text = response.content if hasattr(response, 'content') else str(response)
                    
                    # Parse JSON manually
                    import json
                    # Extract JSON from response (handle markdown code blocks)
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        # Try to find raw JSON
                        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                        json_str = json_match.group(0) if json_match else '{}'
                    
                    memory_data = json.loads(json_str)
                    
                    # Update state with validated data (REDUCER: replaces with merged summary)
                    if memory_data.get("summary"):
                        state["memory_summary"] = memory_data["summary"]
                    if memory_data.get("facts"):
                        state["memory_facts"] = memory_data["facts"][:8]  # Max 8 facts after semantic compression
                    
                    compression_ratio = len(prev_facts) + len(msgs) if prev_facts else len(msgs)
                    final_facts = len(memory_data.get("facts", []))
                    logger.info(
                        f"Memory updated (REDUCER): {final_facts} facts "
                        f"(compressed from {compression_ratio} items), "
                        f"summary length: {len(memory_data.get('summary', ''))} chars, "
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

Respond with JSON: {{"domain": "...", "confidence": 0.0, "reasoning": "..."}}"""
        
        # Use JSON text output instead of structured_output (buggy in LangChain)
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON manually
        import json
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else '{}'
        
        intent_data = json.loads(json_str)
        domain = intent_data.get("domain", "general").lower()

        # Validate domain
        try:
            DomainType(domain)
        except ValueError:
            domain = DomainType.GENERAL.value
            logger.warning(f"Invalid domain '{intent_data.get('domain', 'unknown')}' from LLM, defaulting to {domain}")

        state["domain"] = domain
        state["messages"] = self._dedup_messages([HumanMessage(content=state["query"])])
        
        # Initialize replan counter
        state["replan_count"] = 0
        
        confidence = intent_data.get("confidence", 0.5)
        reasoning = intent_data.get("reasoning", "No reasoning provided")
        logger.info(f"Detected domain: {domain} (confidence: {confidence:.3f}, reasoning: {reasoning[:50]}...)")

        return state

    async def _plan_node(self, state: AgentState) -> AgentState:
        """Generate execution plan using LLM step-by-step reasoning.
        
        This node creates a structured plan with:
        - Step-by-step reasoning (why this plan?)
        - Tool selections (which tools to use, in what order)
        - Dependencies and parallelization (can steps run in parallel?)
        - Cost and time estimates (resource usage prediction)
        
        Non-blocking: If planning fails, execution continues without plan.
        """
        logger.info("Plan node executing")
        
        # Increment replan counter if this is a replan (not initial plan)
        replan_count = state.get("replan_count") or 0  # Handle None value
        if replan_count > 0 or state.get("observation_result"):  # If we've been through observation, it's a replan
            state["replan_count"] = replan_count + 1
            logger.info(f"Replanning (attempt {state['replan_count']}/2)")
        
        try:
            query = state.get("query", "")
            domain = state.get("domain", "general")
            memory_summary = state.get("memory_summary", "")
            
            # Build context for planning
            memory_context = ""
            if memory_summary:
                memory_context = f"\n\nMemory context: {memory_summary}"
            
            # Build prompt with CoT guidance for planning
            prompt = f"""You are an AI assistant planning how to answer a user query.

Query: {query}
Domain: {domain}{memory_context}

Available tools:
1. rag_search - Search knowledge base for information
2. jira_create - Create or retrieve IT tickets
3. email_send - Send emails
4. calculator - Perform calculations

Think step-by-step:
1. What information do I need to answer this query?
2. Which tools should I use and in what order?
3. Are there dependencies or parallelization opportunities?
4. What's the estimated cost (0-1, where 0 is free and 1 is expensive)?
5. What's the estimated execution time in milliseconds?

Create an execution plan with:
- Reasoning: Why this plan? (10-1000 characters)
- Steps: List of steps to execute (1-5 steps max)
  - For each step: step_id (1-10), tool_name, description, arguments dict, dependencies (other step IDs), required flag
- Cost estimate: 0-1 scale
- Time estimate: milliseconds (100-120000ms)

Respond with JSON: {{\"reasoning\": \"...\", \"steps\": [{{\"step_id\": 1, \"tool_name\": \"...\", \"description\": \"...\", \"arguments\": {{}}, \"depends_on\": [], \"required\": true}}], \"estimated_cost\": 0.0, \"estimated_time_ms\": 1000}}"""
            
            # Use JSON text output instead of structured_output (buggy in LangChain)
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON manually
            import json
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                json_str = json_match.group(0) if json_match else '{}'
            
            plan_data = json.loads(json_str)
            
            # Convert to state dict
            state["execution_plan"] = plan_data
            
            steps_count = len(plan_data.get("steps", []))
            est_time = plan_data.get("estimated_time_ms", 0)
            est_cost = plan_data.get("estimated_cost", 0.0)
            reasoning_preview = plan_data.get("reasoning", "")[:50]
            logger.info(
                f"Plan generated: {steps_count} steps, "
                f"estimated {est_time}ms, cost {est_cost:.2f}, "
                f"reasoning: {reasoning_preview}..."
            )
            
        except Exception as e:
            # Non-blocking error handling: log and continue
            logger.warning(f"Plan generation failed (non-blocking): {str(e)}")
            # Don't set execution_plan, allow workflow to continue without explicit plan
            state["execution_plan"] = None
        
        return state

    async def _tool_selection_node(self, state: AgentState) -> AgentState:
        """Select which tools to use based on query and available tools.
        
        LLM decides:
        - Which tools are needed (RAG, Jira, Email, Calculator)
        - Tool arguments
        - Confidence scores
        - Routing decision (rag_only, tools_only, rag_and_tools)
        
        Non-blocking: If tool selection fails, defaults to rag_only route.
        """
        logger.info("Tool selection node executing")
        
        try:
            query = state.get("query", "")
            domain = state.get("domain", "general")
            execution_plan = state.get("execution_plan")
            memory_summary = state.get("memory_summary", "")

            # Build available tools description from registry
            descriptions = self.tool_registry.get_descriptions()
            available_tools = "Available tools:\n" + "\n".join(
                f"- {desc}" for desc in descriptions
            )
            
            # Build context
            plan_context = ""
            if execution_plan:
                plan_context = f"\n\nExecution plan suggests: {execution_plan.get('reasoning', '')}"
            
            memory_context = ""
            if memory_summary:
                memory_context = f"\n\nMemory context: {memory_summary}"
            
            # Build prompt for tool selection
            prompt = f"""You are selecting tools to answer a user query.

Query: {query}
Domain: {domain}{plan_context}{memory_context}

{available_tools}

Think step-by-step:
1. What information or actions do I need to answer this query?
2. Which tools can provide that information or perform those actions?
3. What arguments should I pass to each tool?
4. How confident am I that each tool is the right choice?
5. Should I use RAG only, tools only, or both?

Selection criteria:
- Use rag_search for knowledge base queries (policies, procedures, guidelines)
- Use jira_create for IT support requests (VPN, software, hardware issues)
- Use email_send for notification or communication needs
- Use calculator for mathematical calculations
- Combine tools when needed (e.g., RAG for context + Jira for ticket creation)

Return structured ToolSelection with:
- reasoning: Why these tools? (20-500 characters)
- selected_tools: List of 1-3 tools with arguments and confidence
- fallback_plan: What to do if tools unavailable (10-300 characters)
- route: rag_only / tools_only / rag_and_tools

Respond with JSON: {{\"reasoning\": \"...\", \"selected_tools\": [{{\"tool_name\": \"rag_search\", \"arguments\": {{}}, \"confidence\": 0.8, \"reasoning\": \"...\"}}], \"fallback_plan\": \"...\", \"route\": \"rag_only\"}}
"""
            
            # Use JSON text output instead of structured_output (buggy in LangChain)
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON manually
            import json
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                json_str = json_match.group(0) if json_match else '{}'
            
            tool_selection_data = json.loads(json_str)
            
            # Convert to state dict
            state["tool_selection"] = tool_selection_data
            
            tool_count = len(tool_selection_data.get("selected_tools", []))
            route = tool_selection_data.get("route", "rag_only")
            reasoning_preview = tool_selection_data.get("reasoning", "")[:50]
            logger.info(
                f"Tool selection: {tool_count} tools, "
                f"route: {route}, "
                f"reasoning: {reasoning_preview}..."
            )
            
        except Exception as e:
            # Non-blocking error handling: default to RAG-only route
            logger.warning(f"Tool selection failed (non-blocking): {str(e)}, defaulting to rag_only")
            state["tool_selection"] = {
                "reasoning": "Tool selection failed, using default RAG-only route",
                "selected_tools": [{
                    "tool_name": "rag_search",
                    "arguments": {"query": state.get("query", ""), "domain": state.get("domain", "general")},
                    "confidence": 0.8,
                    "reasoning": "Default fallback to RAG search"
                }],
                "fallback_plan": "Continue with RAG-only search",
                "route": "rag_only"
            }
        
        return state

    async def _tool_executor_node(self, state: AgentState) -> AgentState:
        """Execute selected tools using the registry with timeout/retry and collect results.

        Implements:
        - Sequential tool execution (parallel execution optional future enhancement)
        - Timeout protection per tool (10s limit)
        - Non-blocking: errors are captured as ToolResult entries
        - Latency tracking for each tool
        - Results stored as validated ToolResult models
        """
        logger.info("Tool executor node executing")

        try:
            selection = state.get("tool_selection", {}) or {}
            tools = selection.get("selected_tools", [])
            route = selection.get("route", "rag_only")

            logger.info(f"Executing {len(tools)} tools (route={route})")

            results = []
            for tool in tools:
                # Extract tool name and arguments
                name = tool.get("tool_name") if isinstance(tool, dict) else getattr(tool, "tool_name", None)
                args = tool.get("arguments", {}) if isinstance(tool, dict) else getattr(tool, "arguments", {})

                if not name:
                    # Missing tool name - record error
                    results.append(ToolResult(
                        tool_name="unknown",
                        status="error",
                        error="Missing tool_name in selection",
                        latency_ms=0.0,
                        retry_count=0
                    ))
                    logger.warning("Tool execution skipped: missing tool_name")
                    continue

                # Execute tool with timeout protection
                start_time = time.time()
                
                try:
                    # Execute tool with asyncio timeout wrapper (10s)
                    # The registry execute is synchronous but we wrap it for timeout
                    exec_result = await asyncio.wait_for(
                        asyncio.to_thread(self.tool_registry.execute, name, **args),
                        timeout=10.0
                    )
                    
                    latency_ms = (time.time() - start_time) * 1000
                    
                    # Registry returns {"tool": name, "status": "success/error", "result": ..., "error": ...}
                    # Map to ToolResult
                    if exec_result.get("status") == "success":
                        results.append(ToolResult(
                            tool_name=name,
                            status="success",
                            result=exec_result.get("result"),
                            latency_ms=latency_ms,
                            retry_count=0
                        ))
                        logger.info(f"Tool '{name}' executed successfully ({latency_ms:.1f}ms)")
                    else:
                        results.append(ToolResult(
                            tool_name=name,
                            status="error",
                            error=exec_result.get("error", "Unknown error"),
                            latency_ms=latency_ms,
                            retry_count=0
                        ))
                        logger.error(f"Tool '{name}' failed: {exec_result.get('error')} ({latency_ms:.1f}ms)")
                    
                except asyncio.TimeoutError:
                    latency_ms = (time.time() - start_time) * 1000
                    results.append(ToolResult(
                        tool_name=name,
                        status="timeout",
                        error="Tool execution exceeded 10s timeout",
                        latency_ms=latency_ms,
                        retry_count=0
                    ))
                    logger.error(f"Tool '{name}' timed out ({latency_ms:.1f}ms)")
                    
                except Exception as e:
                    latency_ms = (time.time() - start_time) * 1000
                    results.append(ToolResult(
                        tool_name=name,
                        status="error",
                        error=str(e),
                        latency_ms=latency_ms,
                        retry_count=0
                    ))
                    logger.error(f"Tool '{name}' failed: {str(e)} ({latency_ms:.1f}ms)")

            # Store validated ToolResult models in state
            wf = dict(state.get("workflow", {}) or {})
            wf["tool_results"] = [r.model_dump() for r in results]
            state["workflow"] = wf
            
            success_count = sum(1 for r in results if r.status == "success")
            logger.info(f"Tool execution complete: {success_count}/{len(results)} successful")

        except Exception as e:  # pragma: no cover - defensive outer catch
            logger.warning(f"Tool executor failed (non-blocking): {str(e)}")

        return state

    async def _observation_node(self, state: AgentState) -> AgentState:
        """Evaluate whether we have enough information before generation.

        LLM-based evaluation:
        - Analyzes tool results and retrieval outputs
        - Identifies information gaps
        - Decides: generate answer OR replan (if insufficient)
        - Max 2 replans allowed (replan_count tracking)
        
        OPTIMIZATION: Auto-generate for IT/Marketing domains with RAG results (skip LLM evaluation)
        """
        logger.info("Observation node executing")

        try:
            tool_results = (state.get("workflow", {}) or {}).get("tool_results", [])
            retrieved = state.get("retrieved_docs", [])
            query = state.get("query", "")
            execution_plan = state.get("execution_plan", {})
            domain = state.get("domain", "")
            
            # ⚡ OPTIMIZATION: Auto-generate for IT/Marketing with RAG results (skip LLM call)
            if domain in ["it", "marketing"] and len(retrieved) >= 3:
                logger.info(f"⚡ FAST PATH: Auto-generating for {domain} domain (skip observation LLM call)")
                state["observation_result"] = {
                    "sufficient": True,
                    "next_action": "generate",
                    "gaps": [],
                    "reasoning": f"Auto-generate: {len(retrieved)} documents retrieved for {domain} domain",
                    "tool_results_count": len(tool_results),
                    "retrieval_count": len(retrieved),
                }
                return state
            
            # Build context for LLM evaluation
            tool_results_summary = []
            for i, result in enumerate(tool_results, 1):
                status = result.get("status", "unknown")
                tool_name = result.get("tool_name", "unknown")
                if status == "success":
                    result_data = result.get("result", {})
                    tool_results_summary.append(f"{i}. {tool_name}: SUCCESS - {result_data}")
                elif status == "error":
                    error = result.get("error", "unknown error")
                    tool_results_summary.append(f"{i}. {tool_name}: ERROR - {error}")
                else:
                    tool_results_summary.append(f"{i}. {tool_name}: {status.upper()}")
            
            retrieval_summary = f"{len(retrieved)} documents retrieved" if retrieved else "No documents retrieved"
            
            # LLM evaluation prompt
            prompt = f"""Evaluate if we have enough information to answer the user's query.

**Original Query:** {query}

**Execution Plan:** {execution_plan.get('reasoning', 'N/A')}

**Tool Results:**
{chr(10).join(tool_results_summary) if tool_results_summary else 'No tools executed'}

**Retrieval Results:**
{retrieval_summary}

**Your Task:**
1. Do we have enough information to generate a complete answer?
2. Are there any critical gaps or missing information?
3. Should we proceed to generate the answer, or replan and gather more info?

**Guidelines:**
- If tool results are sufficient → sufficient=true, next_action=generate
- If critical info is missing → sufficient=false, next_action=replan, list gaps
- If tools failed but retrieval succeeded → may still be sufficient
- If everything failed → insufficient, suggest replan

Return:
- sufficient: bool (do we have enough info?)
- next_action: "generate" or "replan"
- gaps: list of missing information (if any)
- reasoning: explanation for your decision (10-500 chars)

Respond with JSON: {{\"sufficient\": true, \"next_action\": \"generate\", \"gaps\": [], \"reasoning\": \"...\"}}
"""
            
            # Use JSON text output instead of structured_output (buggy in LangChain)
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON manually
            import json
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                json_str = json_match.group(0) if json_match else '{}'
            
            observation_data = json.loads(json_str)
            
            # Add counts
            observation_data["tool_results_count"] = len(tool_results)
            observation_data["retrieval_count"] = len(retrieved) if retrieved else 0
            
            state["observation_result"] = observation_data
            
            sufficient = observation_data.get("sufficient", True)
            next_action = observation_data.get("next_action", "generate")
            gaps_count = len(observation_data.get("gaps", []))
            logger.info(
                f"Observation: sufficient={sufficient}, "
                f"next_action={next_action}, "
                f"gaps={gaps_count}"
            )

        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Observation node failed (non-blocking): {str(e)}")
            # Fallback: assume sufficient and proceed
            state["observation_result"] = {
                "sufficient": True,
                "next_action": "generate",
                "gaps": [],
                "reasoning": f"Observation failed ({str(e)}), proceeding to generation",
                "tool_results_count": len(tool_results) if tool_results else 0,
                "retrieval_count": len(retrieved) if retrieved else 0,
            }

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

        # Check if strict RAG mode is enabled (feature flag)
        strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
        logger.info(f"🔧 STRICT_RAG_MODE: env={os.getenv('STRICT_RAG_MODE', 'NOT_SET')}, strict_rag_mode={strict_rag_mode}")
        
        # Build fail-safe instructions based on feature flag
        if strict_rag_mode:
            # STRICT MODE: Require RAG context, refuse to answer without it
            failsafe_instructions = """
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
"""
        else:
            # RELAXED MODE: Allow LLM to use general knowledge if RAG context is empty
            failsafe_instructions = """
INSTRUCTIONS:
1. **Prefer information from the retrieved documents above**, but you may use your general knowledge if documents are insufficient
2. **If using general knowledge (not from documents):**
   - Clearly state: "⚠️ A következő információ általános tudásomon alapul, nem pedig a szervezeti dokumentumokon:"
   - Be conservative and factual - only provide widely accepted information
   - Suggest verifying with the relevant team for organization-specific details
3. **If information is contradictory or unclear in documents:**
   - Note the discrepancy and suggest contacting the relevant team for clarification
4. **Never fabricate organization-specific details:** email addresses, phone numbers, section IDs, policy details, dates, or internal procedures
5. **If uncertain about any detail:** acknowledge the uncertainty and suggest contacting the relevant team
"""

        prompt = f"""
You are a helpful HR/IT/Finance/Legal/Marketing assistant.

    {memory_block}
    Use the conversation summary and known facts above to interpret the user's intent and constraints.

Retrieved documents (use ALL relevant information):
{context}

User query: "{state['query']}"

{domain_instructions}

{failsafe_instructions}

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

        # Use JSON text output instead of structured_output (buggy in LangChain)
        prompt = prompt + "\n\nRespond with JSON: {{\"answer\": \"...\", \"language\": \"hu\", \"section_ids\": [...]}}"
        
        # ⏱️ METRIC: LLM generation latency
        import time
        llm_start = time.time()
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            llm_latency_sec = time.time() - llm_start
            llm_latency_ms = llm_latency_sec * 1000
            logger.info(f"🤖 LLM generation latency: {llm_latency_ms:.0f}ms (domain={state.get('domain')})")
            
            # Extract token usage from response
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, 'response_metadata'):
                # OpenAI uses 'token_usage' key in response_metadata
                usage = response.response_metadata.get('token_usage', {}) or response.response_metadata.get('usage', {})
                input_tokens = usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0) or usage.get('output_tokens', 0)
                logger.info(f"💰 Token usage: input={input_tokens}, output={output_tokens}")
            else:
                logger.warning("⚠️ No response_metadata found in LLM response")
            
            # Record LLM metrics with token usage
            model_name = getattr(self.llm, 'model_name', 'gpt-4o-mini')
            MetricsCollector.record_llm_call(
                model=model_name,
                status='success',
                purpose='generation',
                latency_seconds=llm_latency_sec,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            # Calculate cost for telemetry
            from infrastructure.prometheus_metrics import LLM_COST_CONFIG
            cost_config = LLM_COST_CONFIG.get(model_name, {'input': 0.0, 'output': 0.0})
            input_cost = (input_tokens / 1_000_000) * cost_config['input']
            output_cost = (output_tokens / 1_000_000) * cost_config['output']
            total_cost = input_cost + output_cost
            logger.info(f"💵 Request cost: ${total_cost:.6f} (model={model_name})")
            
            # Store token and cost info in state
            state["llm_input_tokens"] = input_tokens
            state["llm_output_tokens"] = output_tokens
            state["llm_total_cost"] = total_cost
        except Exception as e:
            llm_latency_sec = time.time() - llm_start
            logger.error(f"❌ LLM generation failed: {e}")
            
            # Record failed LLM call
            model_name = getattr(self.llm, 'model_name', 'gpt-4o-mini')
            MetricsCollector.record_llm_call(
                model=model_name,
                status='error',
                purpose='generation'
            )
            MetricsCollector.record_error(error_type='llm_generation', component='agent')
            raise
        
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON manually
        import json
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else '{}'
        
        rag_data = json.loads(json_str)
        answer = rag_data.get("answer", "Sajnálom, nem tudok választ adni.")

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
            all_section_ids = list(set(section_ids + rag_data.get("section_ids", [])))
            
            if all_section_ids and not any(sid in answer for sid in all_section_ids):
                refs = ", ".join(f"[{sid}]" for sid in all_section_ids)
                answer = f"{answer}\n\nForrás: {refs} – IT Üzemeltetési és Felhasználói Szabályzat"
            
            # ALWAYS append Jira ticket question for IT domain (if not already present)
            jira_question = "📋 Szeretnéd, hogy létrehozzak egy Jira support ticketet ehhez a kérdéshez?"
            if jira_question not in answer:
                answer = f"{answer}\n\n{jira_question}"
        
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
            # Use JSON text output instead of structured_output (buggy in LangChain)
            prompt = prompt + "\n\nRespond with JSON: {{\"answer\": \"...\", \"language\": \"hu\", \"section_ids\": []}}"
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON manually
            import json
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                json_str = json_match.group(0) if json_match else '{}'
            
            rag_data = json.loads(json_str)
            answer = rag_data.get("answer", "Sajnálom, nem tudok választ adni.")
            
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
        NOTE: Decision functions CANNOT modify state - read-only!
        """
        errors = state.get("validation_errors", [])
        retry_count = state.get("retry_count", 0)
        max_retries = 2
        
        if errors and retry_count < max_retries:
            # Don't modify state here - will be done in guardrail node before re-routing
            logger.info(f"🔄 Retrying generation (attempt {retry_count + 1}/{max_retries})")
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
            
            # Format latency properly
            latency_str = f"{total_latency_ms:.1f}ms" if total_latency_ms else "N/A"
            logger.info(f"Metrics collected: {retrieval_count} citations, "
                       f"tokens={llm_tokens_used or 'N/A'}, "
                       f"latency={latency_str}")
            
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
            llm_input_tokens=final_state.get("llm_input_tokens", 0),
            llm_output_tokens=final_state.get("llm_output_tokens", 0),
            llm_total_cost=final_state.get("llm_total_cost", 0.0),
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

        # Invoke with higher recursion limit to allow replans + full workflow
        # Default is 25, but with replans we can hit ~24 steps
        final_state = await self.workflow.ainvoke(
            initial_state,
            config={"recursion_limit": 50}
        )

        # Build response with telemetry
        response = QueryResponse(
            domain=final_state["domain"],
            answer=final_state["output"]["answer"],
            citations=[Citation(**c) for c in final_state["citations"]],
            workflow=final_state.get("workflow"),
            rag_context=final_state.get("rag_context"),
            llm_prompt=final_state.get("llm_prompt"),
            llm_response=final_state.get("llm_response"),
            llm_input_tokens=final_state.get("llm_input_tokens", 0),
            llm_output_tokens=final_state.get("llm_output_tokens", 0),
            llm_total_cost=final_state.get("llm_total_cost", 0.0),
        )

        logger.info("Agent run completed")
        return response
    
    async def run_simple(self, query: str, user_id: str, session_id: str) -> QueryResponse:
        """Simple fast RAG-only pipeline (no LangGraph workflow).
        
        Flow: Intent Detection → RAG Retrieval → Generation → Guardrail
        
        Use this for fast responses on IT/Marketing queries where the complex
        workflow (plan → observe → replan) adds unnecessary latency.
        
        Performance: ~15-20 sec vs 60-90 sec for complex workflow
        """
        import time
        start_time = time.time()
        
        # Track active requests
        MetricsCollector.increment_active_requests()
        
        try:
            logger.info(f"⚡ SIMPLE PIPELINE: user={user_id}, query={query[:50]}...")
            
            # Step 1: Intent Detection (keyword-based, fast)
            domain = await self._detect_intent_simple(query)
            logger.info(f"Domain detected: {domain}")
            
            # Step 2: RAG Retrieval
            citations = await self.rag_client.retrieve_for_domain(
                query=query,
                top_k=10,
                domain=domain
            )
            logger.info(f"Retrieved {len(citations)} documents")
            
            # Step 3: Generation
            state = {
                "query": query,
                "domain": domain,
                "citations": [c.model_dump() for c in citations],
                "retrieved_docs": citations,
                "messages": [],
                "validation_errors": [],
                "retry_count": 0,
            }
            state = await self._generation_node(state)
            
            # Step 4: Guardrail (IT domain only)
            if domain == "it":
                state = await self._guardrail_node(state)
                
                # Retry if validation failed
                if state.get("validation_errors") and state.get("retry_count", 0) < 2:
                    logger.warning(f"Guardrail retry {state['retry_count']}/2")
                    state = await self._generation_node(state)
                    state = await self._guardrail_node(state)
            
            # Build response
            total_latency = (time.time() - start_time) * 1000
            logger.info(f"⚡ SIMPLE PIPELINE completed in {total_latency:.0f}ms")
            
            # Record request metrics
            MetricsCollector.record_request(
                domain=domain.value if hasattr(domain, 'value') else str(domain),
                status='success',
                pipeline_mode='simple_pipeline',
                latency_seconds=total_latency / 1000
            )
            
            from domain.models import ProcessingStatus
            processing_status = ProcessingStatus.SUCCESS
            if state.get("validation_errors"):
                processing_status = ProcessingStatus.VALIDATION_FAILED
            
            response = QueryResponse(
                domain=state["domain"],
                answer=state["output"]["answer"],
                citations=[Citation(**c) for c in state["citations"]],
                workflow={"mode": "simple_pipeline", "latency_ms": total_latency},
                processing_status=processing_status,
                validation_errors=state.get("validation_errors", []),
                retry_count=state.get("retry_count", 0),
                rag_context=state.get("rag_context"),
                llm_prompt=state.get("llm_prompt"),
                llm_response=state.get("llm_response"),
                llm_input_tokens=state.get("llm_input_tokens", 0),
                llm_output_tokens=state.get("llm_output_tokens", 0),
                llm_total_cost=state.get("llm_total_cost", 0.0),
            )
            
            return response
        
        finally:
            # Always decrement active requests (even on error)
            MetricsCollector.decrement_active_requests()
    
    async def _detect_intent_simple(self, query: str) -> str:
        """Fast keyword-based intent detection (no LLM call)."""
        query_lower = query.lower()
        
        # Marketing keywords
        marketing_keywords = [
            "brand", "logo", "visual", "design", "arculat", "guideline",
            "marketing", "kampány", "hirdetés", "tartalommarketing"
        ]
        if any(kw in query_lower for kw in marketing_keywords):
            return "marketing"
        
        # IT keywords
        it_keywords = [
            "vpn", "jelszó", "password", "wifi", "hálózat", "network",
            "laptop", "számítógép", "computer", "szoftver", "software",
            "helpdesk", "support", "ticket",
            # Security & Antivirus
            "vírus", "virus", "antivirus", "vírusirtó", "vírusírt", "malware",
            "eset", "ransomware", "trojan", "tűzfal", "firewall", "biztonsági",
            "security", "támadás", "attack", "védelmi", "protection"
        ]
        if any(kw in query_lower for kw in it_keywords):
            return "it"
        
        # HR keywords
        hr_keywords = [
            "szabadság", "leave", "vacation", "béremelés", "salary",
            "teljesítményértékelés", "performance", "felmondás", "resignation"
        ]
        if any(kw in query_lower for kw in hr_keywords):
            return "hr"
        
        # Default: general
        return "general"
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