"""
Planner/Orchestrator Node.

Analyzes the query and plans which nodes and tools to execute in the AI Agent flow.
Acts as a meta-controller that determines the execution path dynamically.
Uses JSON for structured communication between nodes.
"""

import logging
import time
import json
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Global LLM instance (set by graph during initialization)
_llm = None


def set_llm(llm):
    """Set the LLM for this node."""
    global _llm
    _llm = llm


def plan_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze the query and create an execution plan for the agent flow.

    This orchestrator node determines:
    - Which nodes should be executed (embed, retrieve, generate, jira, etc.)
    - The execution sequence/path through the graph
    - Required tools and their parameters
    - Conditional routing decisions

    Args:
        state: Current RAG state

    Returns:
        Updated state with execution plan in structured JSON format
    """
    logger.info("===== Planner/Orchestrator node executing =====")
    start_time = time.time()

    query = state.get("query", "")
    conversation_history = state.get("conversation_history", [])
    pending_jira = state.get("pending_jira_suggestion", {})

    # Initialize execution plan with defaults
    execution_plan = {
        "query_type": "informational",
        "intent": "search",
        "nodes_to_execute": ["embed", "retrieve", "build_context", "generate", "evaluate_jira", "format"],
        "skip_nodes": [],
        "tools_needed": ["embedding", "vector_search", "llm"],
        "parameters": {
            "k": 3,
            "max_tokens": 500,
            "skip_llm": False,
            "skip_retrieval": False
        },
        "routing_decisions": {
            "needs_rag": True,
            "needs_jira_evaluation": True,
            "is_jira_confirmation": False,
            "is_followup": False
        },
        "reasoning": "Default execution plan",
        "confidence": 0.5
    }

    # Build orchestration prompt with JSON response requirement
    orchestration_prompt = f"""You are an AI agent orchestrator. Analyze this query and create an execution plan.

User Query: "{query}"

Conversation History: {len(conversation_history)} messages
Has Pending Jira Suggestion: {"Yes" if pending_jira else "No"}

Available Nodes in the Graph:
1. embed - Generate query embeddings (requires: embedding tool)
2. retrieve - Search vector database (requires: vector_search tool)
3. build_context - Extract relevant text from search results
4. generate - Generate answer with LLM (requires: llm tool)
5. evaluate_jira - Evaluate if Jira ticket needed (requires: llm tool)
6. create_jira - Create Jira ticket (requires: jira_api tool)
7. format - Format final response

Available Tools:
- embedding: OpenAI text embeddings
- vector_search: ChromaDB similarity search
- llm: OpenAI GPT for generation
- jira_api: Jira REST API
- teams_api: Microsoft Teams webhooks

Create an execution plan as JSON:

{{
  "query_type": "informational|issue_report|feature_request|how_to|confirmation|followup",
  "intent": "search|create_ticket|confirm_action|answer_directly",
  "nodes_to_execute": ["list", "of", "nodes", "to", "run"],
  "skip_nodes": ["list", "of", "nodes", "to", "skip"],
  "tools_needed": ["list", "of", "required", "tools"],
  "parameters": {{
    "k": 3,
    "max_tokens": 500,
    "skip_llm": false,
    "skip_retrieval": false
  }},
  "routing_decisions": {{
    "needs_rag": true,
    "needs_jira_evaluation": true,
    "is_jira_confirmation": false,
    "is_followup": false
  }},
  "reasoning": "Explain your planning decisions",
  "confidence": 0.85
}}

Planning Guidelines:
- If query is "yes"/"no" to pending Jira: skip RAG, set is_jira_confirmation=true
- Always use RAG node for department evaluation. You need department context to create Jira.
- If asking about previous conversation: may skip retrieval if context sufficient
- If reporting bug/issue: include jira evaluation
- If simple factual question with no issues: skip jira evaluation
- If query is vague or unclear: use full RAG pipeline
- Optimize by skipping unnecessary nodes when possible

Respond ONLY with valid JSON, no additional text."""

    try:
        # Use LLM to create execution plan
        if not _llm:
            logger.warning("LLM not configured for planner, using default execution plan")
            raise ValueError("LLM not configured")

        logger.info(f"Orchestrating execution plan for query: '{query[:100]}...'")

        planning_response = _llm.generate(
            orchestration_prompt,
            context=[],
            max_tokens=600,
            conversation_history=conversation_history[-4:] if conversation_history else []  # Last 2 turns
        )

        logger.info(f"Raw orchestrator response: {planning_response[:800]}...")

        # Parse JSON response
        try:
            # Extract JSON from response
            json_start = planning_response.find('{')
            json_end = planning_response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in orchestrator response")

            json_str = planning_response[json_start:json_end]
            parsed_plan = json.loads(json_str)

            logger.info(f"Parsed orchestration plan: {json.dumps(parsed_plan, indent=2)}")

            # Validate and merge with defaults
            if "query_type" in parsed_plan:
                execution_plan["query_type"] = parsed_plan["query_type"]

            if "intent" in parsed_plan:
                execution_plan["intent"] = parsed_plan["intent"]

            if "nodes_to_execute" in parsed_plan and isinstance(parsed_plan["nodes_to_execute"], list):
                execution_plan["nodes_to_execute"] = parsed_plan["nodes_to_execute"]

            if "skip_nodes" in parsed_plan and isinstance(parsed_plan["skip_nodes"], list):
                execution_plan["skip_nodes"] = parsed_plan["skip_nodes"]

            if "tools_needed" in parsed_plan and isinstance(parsed_plan["tools_needed"], list):
                execution_plan["tools_needed"] = parsed_plan["tools_needed"]

            if "parameters" in parsed_plan and isinstance(parsed_plan["parameters"], dict):
                execution_plan["parameters"].update(parsed_plan["parameters"])

            if "routing_decisions" in parsed_plan and isinstance(parsed_plan["routing_decisions"], dict):
                execution_plan["routing_decisions"].update(parsed_plan["routing_decisions"])

            if "reasoning" in parsed_plan:
                execution_plan["reasoning"] = parsed_plan["reasoning"]

            if "confidence" in parsed_plan:
                execution_plan["confidence"] = max(0.0, min(1.0, float(parsed_plan["confidence"])))

            # Validate critical fields
            valid_node_names = ["embed", "retrieve", "build_context", "generate", "evaluate_jira", "create_jira", "format"]
            execution_plan["nodes_to_execute"] = [n for n in execution_plan["nodes_to_execute"] if n in valid_node_names]
            execution_plan["skip_nodes"] = [n for n in execution_plan["skip_nodes"] if n in valid_node_names]

            # Ensure booleans are proper type
            for key in ["skip_llm", "skip_retrieval"]:
                if key in execution_plan["parameters"]:
                    val = execution_plan["parameters"][key]
                    if not isinstance(val, bool):
                        execution_plan["parameters"][key] = str(val).lower() in ["true", "yes", "1"]

            for key in execution_plan["routing_decisions"]:
                val = execution_plan["routing_decisions"][key]
                if not isinstance(val, bool):
                    execution_plan["routing_decisions"][key] = str(val).lower() in ["true", "yes", "1"]

            # Validate ranges
            execution_plan["parameters"]["k"] = max(1, min(10, int(execution_plan["parameters"].get("k", 3))))
            execution_plan["parameters"]["max_tokens"] = max(100, min(2000, int(execution_plan["parameters"].get("max_tokens", 500))))

            logger.info("✓ Successfully validated and merged execution plan")

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.error(f"Raw response: {planning_response}")
            state["errors"].append(f"Orchestrator JSON parsing failed: {e}")
            # Continue with default execution_plan

        except Exception as e:
            logger.error(f"Error processing orchestrator response: {e}", exc_info=True)
            state["errors"].append(f"Orchestrator processing failed: {e}")
            # Continue with default execution_plan

    except Exception as e:
        logger.error(f"Orchestration error: {e}", exc_info=True)
        state["errors"].append(f"Orchestration failed: {e}")
        # execution_plan already has defaults

    # Store execution plan in state
    state["execution_plan"] = execution_plan

    # Also store key decisions at top level for easy access
    state["plan_query_type"] = execution_plan["query_type"]
    state["plan_intent"] = execution_plan["intent"]
    state["plan_reasoning"] = execution_plan["reasoning"]
    state["plan_confidence"] = execution_plan["confidence"]

    # Apply parameter decisions to state
    state["k"] = execution_plan["parameters"]["k"]
    state["max_tokens"] = execution_plan["parameters"]["max_tokens"]
    state["skip_llm"] = execution_plan["parameters"]["skip_llm"]

    # Apply routing decisions to state
    state["plan_needs_rag"] = execution_plan["routing_decisions"]["needs_rag"]
    state["plan_is_jira_confirmation"] = execution_plan["routing_decisions"]["is_jira_confirmation"]
    state["plan_is_followup"] = execution_plan["routing_decisions"]["is_followup"]

    # Track timing
    latency = (time.time() - start_time) * 1000
    state["step_timings"]["planning_ms"] = latency

    logger.info(f"===== Planner/Orchestrator completed in {latency:.2f}ms =====")
    logger.info(f"Execution Plan:")
    logger.info(f"  Query Type: {execution_plan['query_type']}")
    logger.info(f"  Intent: {execution_plan['intent']}")
    logger.info(f"  Nodes to Execute: {execution_plan['nodes_to_execute']}")
    logger.info(f"  Skip Nodes: {execution_plan['skip_nodes']}")
    logger.info(f"  Tools Needed: {execution_plan['tools_needed']}")
    logger.info(f"  Routing: needs_rag={execution_plan['routing_decisions']['needs_rag']}, "
               f"is_jira_confirmation={execution_plan['routing_decisions']['is_jira_confirmation']}")
    logger.info(f"  Confidence: {execution_plan['confidence']:.2f}")
    logger.info(f"  Reasoning: {execution_plan['reasoning']}")

    return state
