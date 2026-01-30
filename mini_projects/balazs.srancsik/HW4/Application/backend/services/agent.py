"""
Service layer - LangGraph agent implementation.
Following SOLID: 
- Single Responsibility - Agent handles orchestration, delegates tool execution.
- Dependency Inversion - Agent depends on tool abstractions.
- Open/Closed - Easy to add new tools without modifying agent core logic.
"""
from typing import List, Dict, Any, Optional, Annotated, Sequence
from typing_extensions import TypedDict
import json
import logging
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from domain.models import Message, Memory, WorkflowState, ToolCall
from services.tools import (
    WeatherTool, GeocodeTool, IPGeolocationTool, 
    FXRatesTool, CryptoPriceTool, FileCreationTool, HistorySearchTool,
    RadioTool, DocumentsTool, TranslatorTool, PhotoUploadTool, JSONCreatorTool,
    GuardrailsTool
)

logger = logging.getLogger(__name__)

# Maximum iterations to prevent infinite loops in multi-step workflows
MAX_ITERATIONS = 10


class AgentState(TypedDict, total=False):
    """State object for LangGraph agent."""
    messages: Sequence[BaseMessage]
    memory: Memory
    tools_called: List[ToolCall]
    current_user_id: str
    next_action: str
    tool_decision: Dict[str, Any]
    iteration_count: int  # Track iterations to prevent infinite loops
    is_support_feedback: bool  # Flag for support feedback workflow
    translated_user_message: str  # English translation of user message for RAG query


class AIAgent:
    """
    LangGraph-based AI Agent implementing the workflow:
    Prompt → Decision → Tool → Observation → Memory → Response
    
    Graph structure: Agent → Tool → Agent → User
    """
    
    def __init__(
        self,
        openai_api_key: str,
        weather_tool: WeatherTool,
        geocode_tool: GeocodeTool,
        ip_tool: IPGeolocationTool,
        fx_tool: FXRatesTool,
        crypto_tool: CryptoPriceTool,
        file_tool: FileCreationTool,
        history_tool: HistorySearchTool,
        radio_tool: RadioTool,
        documents_tool: DocumentsTool = None,
        translator_tool: TranslatorTool = None,
        photo_upload_tool: PhotoUploadTool = None,
        sentiment_tool = None,
        json_creator_tool: JSONCreatorTool = None,
        guardrails_tool: GuardrailsTool = None,
        sqlite_save_tool = None,
        email_send_tool = None
    ):
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.7,
            openai_api_key=openai_api_key
        )
        
        # Initialize pending files attribute
        self._pending_files = None
        
        # Store tools
        self.tools = {
            "weather": weather_tool,
            "geocode": geocode_tool,
            "ip_geolocation": ip_tool,
            "fx_rates": fx_tool,
            "crypto_price": crypto_tool,
            "create_file": file_tool,
            "search_history": history_tool,
            "radio": radio_tool
        }
        
        # Add translator tool if provided
        if translator_tool:
            self.tools["translator"] = translator_tool
        
        # Add documents tool if provided
        if documents_tool:
            self.tools["documents"] = documents_tool
        
        # Add photo upload tool if provided
        if photo_upload_tool:
            self.tools["photo_upload"] = photo_upload_tool
        
        # Add sentiment tool if provided
        if sentiment_tool:
            self.tools["sentiment"] = sentiment_tool
        
        # Add JSON creator tool if provided
        if json_creator_tool:
            self.tools["json_creator"] = json_creator_tool
        
        # Add guardrails tool if provided (PII masking for legal compliance)
        if guardrails_tool:
            self.tools["guardrails"] = guardrails_tool
        
        # Add SQLite save tool if provided
        if sqlite_save_tool:
            self.tools["sqlite_save"] = sqlite_save_tool
        
        # Add email send tool if provided
        if email_send_tool:
            self.tools["send_ticket_via_email"] = email_send_tool
        
        # Build LangGraph workflow
        self.workflow = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow graph.
        
        Nodes:
        - agent_decide: LLM reasoning and decision-making (can loop multiple times)
        - tool_*: Individual tool execution nodes
        - agent_finalize: Final response generation
        
        Flow: agent_decide → tool → agent_decide (loop) → ... → agent_finalize
        """
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("agent_decide", self._agent_decide_node)
        workflow.add_node("agent_finalize", self._agent_finalize_node)
        
        # Add tool nodes
        for tool_name in self.tools.keys():
            workflow.add_node(f"tool_{tool_name}", self._create_tool_node(tool_name))
        
        # Set entry point
        workflow.set_entry_point("agent_decide")
        
        # Add conditional edges from agent_decide
        workflow.add_conditional_edges(
            "agent_decide",
            self._route_decision,
            {
                "final_answer": "agent_finalize",
                **{f"tool_{name}": f"tool_{name}" for name in self.tools.keys()}
            }
        )
        
        # Add edges from tools back to agent_decide (for multi-step reasoning)
        for tool_name in self.tools.keys():
            workflow.add_edge(f"tool_{tool_name}", "agent_decide")
        
        # Add edge from finalize to end
        workflow.add_edge("agent_finalize", END)
        
        # Compile the workflow
        return workflow.compile()
    
    def _is_support_feedback_message(self, message: str) -> bool:
        """
        Detect if the message is a support feedback/issue report.
        Returns True if the message appears to be reporting an issue or seeking support.
        
        Strategy:
        1. First check for explicit non-support queries (greetings, general questions)
        2. Check for support/feature keywords
        3. For short messages (1-3 words), assume they are topic-based support queries
        """
        if not message:
            return False
        
        message_lower = message.lower().strip()
        word_count = len(message_lower.split())
        
        # Explicit non-support patterns (greetings, general questions)
        non_support_patterns = [
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
            'how are you', 'what can you do', 'who are you', 'what is your name',
            'thank you', 'thanks', 'bye', 'goodbye', 'szia', 'helló', 'köszönöm',
            'what time', 'what date', 'what day'
        ]
        
        if any(pattern in message_lower for pattern in non_support_patterns):
            return False
        
        # Comprehensive keywords extracted from Issue_types_and_details Excel files
        support_keywords = [
            # === ACCOUNT ISSUES ===
            'locked', 'account', 'password', 'reset', 'mfa', 'multi-factor', '2fa',
            'sso', 'provisioning', 'role', 'permission', 'permissions', 'rbac',
            'orphaned', 'admin', 'ownership', 'dispute', 'email', 'change',
            'deactivation', 'reactivation', 'profile', 'data', 'domain', 'claim',
            'verification', 'tenant', 'merge', 'split', 'export', 'gdpr', 'dsar',
            'forgotten', 'suspicious', 'login', 'alert', 'api', 'token', 'rotation',
            'seat', 'limit', 'impersonation', 'alias', 'regional', 'residency',
            'suspension', 'appeal', 'license', 'assignment', 'trial', 'paid',
            'invite', 'timezone', 'locale', 'mismatch', 'collision', 'collaborator',
            'import', 'compliance', 'attestation', 'audit', 'log', 'retrieval',
            'scim', 'saml', 'oauth', 'idp', 'identity',
            
            # === BILLING ISSUES ===
            'charged', 'incorrect', 'amount', 'duplicate', 'charges', 'failed',
            'payment', 'card', 'declined', 'invoice', 'received', 'tax', 'vat',
            'refund', 'processed', 'plan', 'updated', 'billing', 'proration',
            'credit', 'applied', 'usage', 'billed', 'currency', 'chargeback',
            'inquiry', 'cycle', 'misaligned', 'po', 'missing', 'address', 'company',
            'annual', 'monthly', 'transition', 'portal', 'access', 'late', 'fee',
            'free', 'gift', 'code', 'coupon', 'consolidated', 'contracted', 'price',
            'honored', 'auto-renewal', 'renewal', 'unexpected', 'removal', 'blocked',
            'receipt', 'confusion', 'country', 'exemption', 'ignored', 'partial',
            'bank', 'transfer', 'reconciled', 'link', 'expired', 'recurring',
            'formatting', 'subscription', 'discount', 'promotional', 'credits',
            
            # === FEATURE REQUESTS ===
            'integration', 'enhancement', 'custom', 'roles', 'offline', 'mode',
            'advanced', 'reporting', 'enhancements', 'white-labeling', 'whitelabel',
            'localization', 'expansion', 'accessibility', 'upgrades', 'bulk',
            'actions', 'webhooks', 'filters', 'sla', 'policy', 'controls',
            'mobile', 'widgets', 'search', 'scheduler', 'workspace', 'templates',
            'sandbox', 'env', 'environment', 'higher', 'limits', 'fields',
            'theme', 'themes', 'modes', 'notifications', 'rules', 'in-app',
            'guidance', 'homepage', 'homepages', 'workflow', 'automation',
            'marketplace', 'listing', 'microsoft', 'teams', 'dashboards',
            'wcag', 'multi-select', 'siem', 'selectors', 'allowlists', 'session',
            'facets', 'saved', 'searches', 'formats', 'files', 'automated',
            'reports', 'prebuilt', 'configs', 'availability', 'region', 'selection',
            'quotas', 'schema', 'extensions', 'high-contrast', 'granular', 'matrix',
            'tours', 'tips', 'personalized', 'triggers', 'hipaa', 'app', 'store',
            
            # === TECHNICAL ISSUES ===
            'outage', 'service', 'degraded', 'performance', 'latency', 'timeout',
            'loss', 'corruption', 'authentication', 'failure', 'breaking',
            'web', 'bug', 'crash', 'upload', 'notification', 'delivery',
            'connector', 'fails', 'report', 'generation', 'configuration', 'drift',
            'caching', 'inconsistency', 'webhook', 'failures', 'rate', 'false',
            'positives', 'localization', 'issues', 'defects', 'browser',
            'compatibility', 'sync', 'delay', 'sandbox', 'prod', 'licensing',
            'enforcement', 'storage', 'misfire', 'websocket', 'disconnects',
            'dns', 'ssl', 'certificate', 'background', 'jobs', 'stuck', 'tool',
            'sdk', 'feature', 'flag', 'bleed', 'logging', 'monitoring', 'blind',
            'spots', 'indexing', 'queue', 'backlog', 'hotfix', 'patch',
            
            # === COMMON TERMS ===
            'issue', 'problem', 'error', 'broken', 'not working', 'help',
            'support', 'complaint', 'feedback', 'trouble', 'difficulty',
            'can\'t', 'cannot', 'unable', 'wrong', 'request', 'suggestion',
            'improve', 'add', 'analytics', 'alert', 'customization',
            'backup', 'restore', 'migration', 'calendar', 'scheduling',
            'reminder', 'reminders', 'task', 'tasks', 'enterprise', 'ops',
            'devops', 'frontend', 'backend', 'platform', 'security',
            
            # === HUNGARIAN KEYWORDS ===
            'hiba', 'probléma', 'problémám', 'problémája', 'problémat',
            'segítség', 'panasz', 'visszajelzés', 'nem működik', 'sikertelen',
            'számla', 'számlával', 'számlát', 'számlán', 'számlázás',
            'fizetés', 'terhelés', 'visszatérítés', 'bejelentkezés', 'jelszó',
            'hibás', 'rossz', 'helytelen', 'hiányzik', 'hiány',
            'fejlesztés', 'kérés', 'javaslat', 'funkció', 'exportálás',
            'sablon', 'sablonok', 'munkaterület', 'fiók', 'jogosultság',
            'integráció', 'jelentés', 'automatizálás', 'biztonság'
        ]
        
        # Check for keyword match
        if any(keyword in message_lower for keyword in support_keywords):
            return True
        
        # For short messages (1-4 words) that aren't greetings, treat as support topic query
        # This handles cases like "Workplace templates", "SSO integration", "Mobile app"
        if word_count <= 4:
            logger.info(f"Short message ({word_count} words) treated as support topic query: '{message}'")
            return True
        
        return False
    
    def _get_forced_tool_sequence(self, tools_called: list, user_message: str, state: dict = None) -> dict:
        """
        Get the next forced tool call for support feedback workflow.
        
        Sequence:
        1. sentiment (analyze user's emotional tone)
        2. weather (get current weather for user's location)
        3. documents (identify issue type from user's feedback - using English translation)
        4. fx_rates USD->EUR (convert price)
        5. fx_rates USD->HUF (convert price)
        6. json_creator (create ticket with all collected data) - called AFTER final response
        
        Note: user_message should already be translated to English before calling this method.
        
        Returns None if sequence is complete.
        """
        called_tools = [tc.tool_name for tc in tools_called]
        called_with_args = [(tc.tool_name, tc.arguments) for tc in tools_called]
        
        # Step 1: Sentiment analysis
        if 'sentiment' not in called_tools:
            return {
                "action": "call_tool",
                "tool_name": "sentiment",
                "arguments": {"text": user_message},
                "reasoning": "Analyze user's emotional tone and sentiment"
            }
        
        # Step 2: Weather
        if 'weather' not in called_tools:
            return {
                "action": "call_tool",
                "tool_name": "weather",
                "arguments": {"city": "Budapest"},
                "reasoning": "Get current weather for greeting"
            }
        
        # Step 3: Documents - query to identify issue type (user_message is already in English)
        if 'documents' not in called_tools:
            return {
                "action": "call_tool",
                "tool_name": "documents",
                "arguments": {"action": "query", "question": user_message, "top_k": 5},
                "reasoning": "Identify issue type from user feedback using document search"
            }
        
        # Step 4: FX rates USD->EUR
        usd_eur_called = any(
            name == 'fx_rates' and args.get('base') == 'USD' and args.get('target') == 'EUR'
            for name, args in called_with_args
        )
        if not usd_eur_called:
            return {
                "action": "call_tool",
                "tool_name": "fx_rates",
                "arguments": {"base": "USD", "target": "EUR"},
                "reasoning": "Convert USD price to EUR"
            }
        
        # Step 5: FX rates USD->HUF
        usd_huf_called = any(
            name == 'fx_rates' and args.get('base') == 'USD' and args.get('target') == 'HUF'
            for name, args in called_with_args
        )
        if not usd_huf_called:
            return {
                "action": "call_tool",
                "tool_name": "fx_rates",
                "arguments": {"base": "USD", "target": "HUF"},
                "reasoning": "Convert USD price to HUF"
            }
        
        # All tools called, ready for final answer
        return None
    
    async def _agent_decide_node(self, state: AgentState) -> AgentState:
        """
        Agent decision node: Analyzes user request and decides next action.
        """
        logger.info("Agent decision node executing")
        
        # Build context for LLM
        system_prompt = self._build_system_prompt(state["memory"])
        
        # Get last user message
        last_user_msg = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_user_msg = msg.content
                break
        
        # Check if this is a support feedback message and force tool sequence
        is_first_message = len(state["memory"].chat_history) == 0
        is_support_feedback = self._is_support_feedback_message(last_user_msg)
        
        logger.info(f"Support feedback check: message='{last_user_msg[:50] if last_user_msg else 'None'}...', is_support_feedback={is_support_feedback}")
        
        if is_support_feedback:
            logger.info("Detected support feedback message - using forced tool sequence")
            
            # Detect language and translate to English if needed (BEFORE forced sequence)
            if "translated_user_message" not in state or state.get("translated_user_message") is None:
                detected_lang = self._detect_question_language(last_user_msg)
                logger.info(f"Detected language: {detected_lang} for message: '{last_user_msg[:50]}...'")
                
                if detected_lang != 'en':
                    # Need to translate to English for RAG
                    logger.info(f"Translating from {detected_lang} to English for RAG query")
                    # Use the translator tool asynchronously
                    translator_tool = self.tools.get('translator')
                    if translator_tool:
                        translation_result = await translator_tool.execute(text=last_user_msg, target_language='en')
                        
                        # Record the translator tool call
                        from domain.models import ToolCall
                        tool_call = ToolCall(
                            tool_name='translator',
                            arguments={'text': last_user_msg, 'target_language': 'en'},
                            result=translation_result.get('data') if translation_result.get('success') else None,
                            error=translation_result.get('error') if not translation_result.get('success') else None,
                            system_message=translation_result.get('system_message'),
                            detailed_message=translation_result.get('message')
                        )
                        state["tools_called"].append(tool_call)
                        
                        if translation_result.get('success'):
                            translated_text = translation_result.get('data', {}).get('translated_text', last_user_msg)
                            state["translated_user_message"] = translated_text
                            logger.info(f"Translated to English: {translated_text[:100]}...")
                        else:
                            logger.warning(f"Translation failed, using original: {translation_result.get('error')}")
                            state["translated_user_message"] = last_user_msg
                    else:
                        logger.warning("Translator tool not available, using original message")
                        state["translated_user_message"] = last_user_msg
                else:
                    # Already English
                    logger.info(f"Message is already in English, using original: '{last_user_msg[:50]}...'")
                    state["translated_user_message"] = last_user_msg
            
            # Get the message to use for documents query
            query_message = state.get("translated_user_message") or last_user_msg
            logger.info(f"Query message for forced sequence: '{query_message[:50] if query_message else 'None'}...'")
            
            forced_decision = self._get_forced_tool_sequence(state["tools_called"], query_message)
            
            if forced_decision:
                logger.info(f"Forced tool decision: {forced_decision}")
                state["next_action"] = forced_decision.get("action", "final_answer")
                state["tool_decision"] = forced_decision
                state["iteration_count"] = state.get("iteration_count", 0) + 1
                # Mark this as a support feedback workflow
                state["is_support_feedback"] = True
                return state
            else:
                # All forced tools called, proceed to final answer
                state["next_action"] = "final_answer"
                state["is_support_feedback"] = True
                return state
        
        # Build conversation context for decision
        recent_history = state["memory"].chat_history[-5:] if state["memory"].chat_history else []
        history_context = "\n".join([f"{msg.role}: {msg.content[:100]}" for msg in recent_history]) if recent_history else "No previous conversation"
        
        # Build list of already called tools with their arguments to prevent duplicates
        tools_called_info = [
            f"{tc.tool_name}({tc.arguments})"
            for tc in state["tools_called"]
        ]
        
        # Check if files are attached
        files_attached = hasattr(self, '_pending_files') and self._pending_files and len(self._pending_files.get('file_names', [])) > 0
        file_info = ""
        if files_attached:
            file_names = self._pending_files.get('file_names', [])
            file_info = f"\n\n**IMPORTANT: {len(file_names)} FILE(S) ATTACHED: {', '.join(file_names)}**\nYou MUST use the photo_upload tool to handle these files."
        
        # Create decision prompt - MUST return ONLY JSON, nothing else
        decision_prompt = f"""
You must analyze the user's request and respond with ONLY a valid JSON object, nothing else.

Recent conversation context:
{history_context}
{file_info}

Available tools:
- weather: Get weather forecast (params: city OR lat/lon) - ONLY provides current + 2 day future forecast, NO historical data
- geocode: Convert address to coordinates or reverse (params: address OR lat/lon)
- ip_geolocation: Get location from IP address (params: ip_address)
- fx_rates: Get currency exchange rates (params: base, target, optional date)
- crypto_price: Get cryptocurrency prices (params: symbol, fiat)
- create_file: Save text to a file (params: user_id, filename, content)
- search_history: Search past conversations (params: query)
- radio: Search and explore radio stations worldwide. Actions: 'search' (filter by country_code, country, name, language, tag), 'top' (by: votes/clicks/recent_clicks/recently_changed), 'countries', 'languages', 'tags'. Params: action, country_code, name, language, tag, by, limit
- translator: Detect language and translate text. Actions: 'detect' (detect language of text), 'translate' (translate text to target language). Params: action, text, target_language (e.g., 'en', 'hu', 'de', 'fr', 'es', 'it', 'pt', 'ru'), source_language (optional)
- book: Ask questions about the book "Pál utcai fiúk" (The Paul Street Boys). Actions: 'query' (ask a question about the book), 'info' (get book information). Params: action, question, top_k (number of sources to retrieve)
- photo_upload: Upload photos to pCloud Photo_Memories folder. USE THIS WHEN FILES ARE ATTACHED. Actions: 'upload' (upload files), 'list' (list folder structure). Params: action, date (when photos were taken), event_name (what event), location (where). The tool will ask for missing info if needed.

User's original request: {last_user_msg}

Tools already called with their arguments: {tools_called_info}

CRITICAL RULES:
1. NEVER call the same tool with the same arguments twice
2. If a tool was called and couldn't provide the data (e.g., historical weather), do NOT retry - move to final_answer
3. If the user asks for something a tool cannot do (like past weather data), explain the limitation in final_answer
4. If the user requested multiple DIFFERENT tasks, execute them ONE AT A TIME
5. Only use "final_answer" when ALL requested tasks are complete OR a task is impossible

Respond with ONLY this JSON structure (no other text, no markdown):
{{
  "action": "call_tool",
  "tool_name": "TOOL_NAME_HERE",
  "arguments": {{...}},
  "reasoning": "brief explanation"
}}

Examples:
- Weather: {{"action": "call_tool", "tool_name": "weather", "arguments": {{"city": "Budapest"}}, "reasoning": "get weather forecast"}}
- Create file: {{"action": "call_tool", "tool_name": "create_file", "arguments": {{"filename": "summary.txt", "content": "..."}}, "reasoning": "save summary"}}
- Final answer: {{"action": "final_answer", "reasoning": "all tasks completed"}}

IMPORTANT: The "action" field must ALWAYS be either "call_tool" or "final_answer" - NEVER use a tool name as the action!
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=decision_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        # Parse decision
        try:
            # Try to extract JSON from the response
            content = response.content.strip()
            
            # If response contains markdown code blocks, extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            decision = json.loads(content)
            logger.info(f"Agent decision: {decision}")
            
            state["next_action"] = decision.get("action", "final_answer")
            
            # Store decision for tool execution
            if decision.get("action") == "call_tool":
                state["tool_decision"] = decision
                # Increment iteration count when calling a tool
                state["iteration_count"] = state.get("iteration_count", 0) + 1
            
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            logger.error(f"Failed to parse agent decision: {e}, defaulting to final_answer")
            logger.error(f"Response content: {response.content[:200]}")
            state["next_action"] = "final_answer"
        
        return state
    
    def _route_decision(self, state: AgentState) -> str:
        """Route to next node based on agent decision."""
        # Check iteration limit to prevent infinite loops
        if state.get("iteration_count", 0) >= MAX_ITERATIONS:
            logger.warning(f"Max iterations ({MAX_ITERATIONS}) reached, forcing finalize")
            return "final_answer"
        
        action = state.get("next_action", "final_answer")
        
        if action == "call_tool" and "tool_decision" in state:
            tool_name = state["tool_decision"].get("tool_name")
            if tool_name in self.tools:
                return f"tool_{tool_name}"
        
        return "final_answer"
    
    def _create_tool_node(self, tool_name: str):
        """Create a tool execution node."""
        async def tool_node(state: AgentState) -> AgentState:
            logger.info(f"Executing tool: {tool_name}")
            
            tool = self.tools[tool_name]
            decision = state.get("tool_decision", {})
            arguments = decision.get("arguments", {})
            
            # Add user_id for file creation tool
            if tool_name == "create_file":
                arguments["user_id"] = state["current_user_id"]
            
            # Add file data for photo_upload tool
            if tool_name == "photo_upload" and hasattr(self, '_pending_files') and self._pending_files:
                arguments["file_paths"] = self._pending_files.get("file_paths", [])
                arguments["file_names"] = self._pending_files.get("file_names", [])
                arguments["file_data"] = self._pending_files.get("file_data", [])
                
                # Get ticket number from json_creator tool result if available
                ticket_number = None
                for tc in state["tools_called"]:
                    if tc.tool_name == "json_creator" and tc.result:
                        ticket_number = tc.result.get("ticket_number")
                        break
                
                if ticket_number:
                    arguments["ticket_number"] = ticket_number
                    logger.info(f"Adding ticket_number {ticket_number} to photo_upload arguments")
            
            # Execute tool
            try:
                result = await tool.execute(**arguments)
                
                # Record tool call
                tool_call = ToolCall(
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result.get("data") if result.get("success") else None,
                    error=result.get("error") if not result.get("success") else None,
                    system_message=result.get("system_message"),
                    detailed_message=result.get("message")  # Store full message for frontend display
                )
                state["tools_called"].append(tool_call)
                
                # Add system message - include full message content if available
                # This ensures the LLM sees the actual tool output (e.g., station names)
                if result.get("message"):
                    system_msg = result.get("message")
                else:
                    system_msg = result.get("system_message", f"Tool {tool_name} executed")
                state["messages"].append(SystemMessage(content=system_msg))
                
                # Log the message content for debugging
                if tool_name == "photo_upload":
                    logger.info(f"Photo upload message added (first 500 chars): {system_msg[:500]}")
                
                logger.info(f"Tool {tool_name} completed: {result.get('success', False)}")
                
            except Exception as e:
                logger.error(f"Tool {tool_name} error: {e}")
                error_msg = f"Error executing {tool_name}: {str(e)}"
                state["messages"].append(SystemMessage(content=error_msg))
                state["tools_called"].append(ToolCall(
                    tool_name=tool_name,
                    arguments=arguments,
                    error=str(e)
                ))
            
            return state
        
        return tool_node
    
    def _detect_question_language(self, text: str) -> str:
        """
        Detect the language of a question using lingua-language-detector.
        Returns ISO 639-1 language code (e.g., 'en', 'hu', 'de', 'fr').
        """
        if not text or len(text.strip()) < 3:
            return "en"
        
        try:
            from lingua import Language, LanguageDetectorBuilder
            
            # Build detector with minimum relative distance for better accuracy
            detector = LanguageDetectorBuilder.from_languages(
                Language.ENGLISH,
                Language.HUNGARIAN,
                Language.GERMAN,
                Language.FRENCH,
                Language.SPANISH,
                Language.ITALIAN,
                Language.PORTUGUESE,
                Language.RUSSIAN
            ).with_minimum_relative_distance(0.15).build()
            
            # Detect language
            detected = detector.detect_language_of(text)
            
            if detected is None:
                logger.warning(f"Could not detect language for: '{text[:50]}...', defaulting to English")
                return "en"
            
            # Map lingua Language enum to ISO 639-1 codes
            lang_map = {
                Language.ENGLISH: "en",
                Language.HUNGARIAN: "hu",
                Language.GERMAN: "de",
                Language.FRENCH: "fr",
                Language.SPANISH: "es",
                Language.ITALIAN: "it",
                Language.PORTUGUESE: "pt",
                Language.RUSSIAN: "ru"
            }
            
            lang_code = lang_map.get(detected, "en")
            logger.info(f"Detected question language by lingua: {detected.name} ({lang_code})")
            return lang_code
            
        except Exception as e:
            logger.error(f"Language detection error: {e}, defaulting to English")
            return "en"
    
    async def _translate_response_if_needed(self, response_text: str, target_lang: str) -> str:
        """
        Translate response to target language if needed.
        """
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            lang_names = {
                'en': 'English',
                'hu': 'Hungarian', 
                'de': 'German',
                'fr': 'French',
                'es': 'Spanish'
            }
            
            target_lang_name = lang_names.get(target_lang, 'English')
            
            messages = [
                SystemMessage(content=f"You are a professional translator. Translate the following text to {target_lang_name}. Preserve all formatting, markdown, and structure. Only output the translation, nothing else."),
                HumanMessage(content=response_text)
            ]
            
            translation = await self.llm.ainvoke(messages)
            logger.info(f"Translated final response to {target_lang_name}")
            return translation.content.strip()
            
        except Exception as e:
            logger.error(f"Translation error in finalize: {e}")
            return response_text
    
    async def _agent_finalize_node(self, state: AgentState) -> AgentState:
        """
        Agent finalize node: Generate final natural language response.
        """
        logger.info("Agent finalize node executing")
        
        # Get the CURRENT user's message (last HumanMessage)
        user_message = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        # Detect the language of the CURRENT question
        detected_lang = self._detect_question_language(user_message)
        logger.info(f"Detected current question language: {detected_lang} for question: '{user_message[:50]}...'")
        
        # Check if this is a support feedback workflow
        is_support_feedback = state.get("is_support_feedback", False)
        
        # Build system prompt WITHOUT language preference override
        system_prompt = """You are a helpful AI assistant with access to various tools.
        
Provide clear, accurate, and helpful responses based on the conversation context and tool results."""
        
        # Get conversation context - include full tool results
        conversation_parts = []
        for msg in state["messages"][-10:]:  # Last 10 messages
            if isinstance(msg, SystemMessage) and ("📸 **Photo Upload Complete!**" in msg.content or "Files in" in msg.content or "Photo_Memories" in msg.content):
                # Include full content for photo_upload tool results
                logger.info(f"Including full photo upload result in conversation history (length: {len(msg.content)})")
                conversation_parts.append(f"TOOL_RESULT: {msg.content}")
            else:
                # Truncate other messages
                conversation_parts.append(f"{msg.__class__.__name__}: {msg.content[:200]}")
        conversation_history = "\n".join(conversation_parts)
        
        # Log conversation history for debugging
        logger.info(f"Conversation history length: {len(conversation_history)} chars")
        
        # Language instruction mapping - Note: Book tool handles its own language enforcement
        lang_instructions = {
            'en': "Respond in ENGLISH to match the user's question language.",
            'hu': "Válaszolj MAGYARUL, hogy megfeleljen a felhasználó kérdésének.",
            'de': "Antworten Sie auf DEUTSCH, um der Sprache der Frage des Benutzers zu entsprechen.",
            'fr': "Répondez en FRANÇAIS pour correspondre à la langue de la question de l'utilisateur.",
            'es': "Responde en ESPAÑOL para que coincida con el idioma de la pregunta del usuario.",
            'it': "Rispondi in ITALIANO per corrispondere alla lingua della domanda dell'utente.",
            'pt': "Responda em PORTUGUÊS para corresponder ao idioma da pergunta do usuário.",
            'ru': "Отвечайте на РУССКОМ языке, чтобы соответствовать языку вопроса пользователя."
        }
        
        lang_instruction = lang_instructions.get(detected_lang, lang_instructions['en'])
        
        # Special handling for support feedback workflow
        if is_support_feedback:
            # Get current time in CET/CEST (automatically handles daylight saving)
            from datetime import datetime
            import pytz
            cet_timezone = pytz.timezone('Europe/Berlin')  # Handles both CET and CEST
            current_time = datetime.now(cet_timezone).strftime("%Y-%m-%d %H:%M:%S")
            
            # Extract tool results for support feedback response
            weather_info = ""
            document_info = ""
            eur_rate = ""
            huf_rate = ""
            issue_price_usd = None
            acknowledgement_time = ""
            resolution_time = ""
            document_source = ""
            document_category = ""
            
            for tc in state["tools_called"]:
                if tc.tool_name == "weather":
                    # tc.result contains the data directly (from result.get("data"))
                    # tc.detailed_message contains the formatted message
                    if tc.detailed_message:
                        weather_info = tc.detailed_message
                    elif tc.system_message:
                        weather_info = tc.system_message
                    else:
                        weather_info = "Weather information unavailable"
                        
                elif tc.tool_name == "documents":
                    # tc.result contains the RAG result data (answer, sources, etc.)
                    # tc.detailed_message contains the formatted message
                    if tc.result:
                        # tc.result is the data dict with answer, sources, etc.
                        answer = tc.result.get("answer", "")
                        document_info = answer if answer else (tc.detailed_message or "No document information found")
                        # Extract sources for issue details - sources contain content_preview with the raw data
                        sources = tc.result.get("sources", [])
                        if sources:
                            first_source = sources[0]
                            # Extract document source and category
                            document_source = first_source.get("source", "")
                            document_category = first_source.get("category", "")
                            # The content_preview contains the raw document text
                            content = first_source.get("content_preview", "")
                            # Parse the content to extract specific fields
                            for line in content.split('\n'):
                                if 'Cost to Customer' in line or 'cost' in line.lower():
                                    issue_price_usd = line.split(':')[-1].strip() if ':' in line else None
                                if 'Acknowledge Time' in line:
                                    acknowledgement_time = line.split(':')[-1].strip() if ':' in line else None
                                if 'Resolution Time' in line:
                                    resolution_time = line.split(':')[-1].strip() if ':' in line else None
                    elif tc.detailed_message:
                        document_info = tc.detailed_message
                    else:
                        document_info = tc.system_message or "Could not identify issue type"
                        
                elif tc.tool_name == "fx_rates":
                    # tc.result contains the rate data directly
                    if tc.result:
                        rate = tc.result.get("rate")
                        target = tc.arguments.get("target", "")
                        if target == "EUR":
                            eur_rate = str(rate) if rate else ""
                        elif target == "HUF":
                            huf_rate = str(rate) if rate else ""
            
            final_prompt = f"""
Generate a SUPPORT FEEDBACK RESPONSE to the user. This is a special workflow that MUST follow this exact structure:

**CURRENT TIME:** {current_time}

**USER'S FEEDBACK/ISSUE:** "{user_message}"

**TOOL RESULTS COLLECTED:**
1. Weather: {weather_info}
2. Document Search Result: {document_info}
   - Document Type: {document_category or 'Unknown category'}
   - Source File: [{document_source or 'Unknown'}](javascript:openDocument('{document_source or ''}'))
3. Extracted Issue Details:
   - Acknowledgement Time: {acknowledgement_time or 'See document info above'}
   - Resolution Time: {resolution_time or 'See document info above'}
   - Cost to Customer (USD): {issue_price_usd or 'See document info above'}
4. Currency Exchange Rates:
   - USD to EUR rate: {eur_rate}
   - USD to HUF rate: {huf_rate}

**RESPONSE STRUCTURE (MUST FOLLOW):**
1. Start with a WARM, FRIENDLY, slightly FLIRTY greeting that incorporates the weather in a natural, conversational way
   - Use the weather info to create engaging smalltalk (e.g., "What a beautiful sunny day!", "Hope you're staying cozy in this weather!", "Perfect weather for solving your issue!")
   - Make it feel personal and warm, not robotic
   - Mention the current time naturally in this greeting: {current_time}
   - DON'T just list weather facts - weave them into friendly conversation
2. Smoothly transition to acknowledging their issue/feedback
3. Explain what type of issue it is based on the document search
   - Mention that this issue is from the "{document_category or 'support'}" category
   - Reference the source document: [{document_source or 'document'}](javascript:openDocument('{document_source or ''}'))
4. Provide specific details from the document about:
   - Acknowledgement time: {acknowledgement_time or 'from document'}
   - Resolution time: {resolution_time or 'from document'}
   - Price/Cost in USD: {issue_price_usd or 'from document'}
   - If there is a numeric cost, convert to EUR using rate {eur_rate}
   - If there is a numeric cost, convert to HUF using rate {huf_rate}
5. End with warm reassurance that their issue will be handled

CRITICAL INSTRUCTIONS:
{lang_instruction}
- Be WARM, FRIENDLY, and slightly FLIRTY in your opening with weather-based smalltalk
- The weather should feel like natural conversation, not a weather report
- Include ALL the specific details from the tools
- The document search result contains the answer with all details - USE IT
- If a price is mentioned, calculate and show: USD amount, EUR equivalent, HUF equivalent
- Format currency conversions clearly
"""
        else:
            final_prompt = f"""
Generate a natural language response to the user based on the conversation history and any tool results.

Conversation:
{conversation_history}

Current user question: "{user_message}"

CRITICAL INSTRUCTIONS:
{lang_instruction}
- If you see a TOOL_RESULT in the conversation (especially for photo_upload), you MUST include the detailed information from that result in your response
- For photo uploads: Show the folder name, list of uploaded files with sizes, and all Photo_Memories folders
- Use proper icons: 📂 folder icon before folder names, 📷 camera icon before file names
- DO NOT use hyphens (-) before folders or files - use the icons instead
- For "Folder Used for Upload:" use 📂 icon, for "File Uploaded:" use 📷 icon
- When files are attached to the question, list them on a NEW LINE, not in the same line as the question text
- DO NOT generate a generic "upload successful" message - use the specific details from the TOOL_RESULT
- DO NOT apologize for being unable to view images - the tool already handled the upload
- Be conversational but include all the detailed information from the tool results
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=final_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        response_text = response.content
        
        # CRITICAL: Verify response language matches question language
        response_lang = self._detect_question_language(response_text)
        logger.info(f"Response language detected: {response_lang}, Expected: {detected_lang}")
        
        if response_lang != detected_lang:
            logger.warning(f"Language mismatch in final response! Translating from {response_lang} to {detected_lang}")
            response_text = await self._translate_response_if_needed(response_text, detected_lang)
        
        # Add assistant message
        state["messages"].append(AIMessage(content=response_text))
        
        logger.info("Agent finalized response")
        
        return state
    
    def _build_system_prompt(self, memory: Memory) -> str:
        """Build system prompt with memory context."""
        preferences = memory.preferences
        workflow = memory.workflow_state
        
        # Build user info section
        user_info = []
        if preferences.get('name'):
            user_info.append(f"- Name: {preferences['name']}")
        user_info.append(f"- Language: {preferences.get('language', 'hu')}")
        user_info.append(f"- Default city: {preferences.get('default_city', 'Budapest')}")
        
        # Add any other preferences
        for key, value in preferences.items():
            if key not in ['name', 'language', 'default_city']:
                user_info.append(f"- {key.replace('_', ' ').title()}: {value}")
        
        prompt = f"""You are a helpful AI assistant with access to various tools.

User preferences:
{chr(10).join(user_info)}

"""
        
        # Add recent conversation history for context
        if memory.chat_history:
            recent_history = memory.chat_history[-10:]  # Last 10 messages
            history_text = "\n".join([
                f"{msg.role}: {msg.content[:150]}"  # Truncate long messages
                for msg in recent_history
            ])
            prompt += f"\nRecent conversation history:\n{history_text}\n\n"
        
        if workflow.flow:
            prompt += f"\nCurrent workflow: {workflow.flow} (step {workflow.step}/{workflow.total_steps})\n"
        
        # Add personalization instruction
        if preferences.get('name'):
            prompt += f"\nAddress the user by their name ({preferences['name']}) when appropriate.\n"
        
        return prompt
    
    async def run(
        self,
        user_message: str,
        memory: Memory,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Run the agent workflow.
        
        Args:
            user_message: User's input message
            memory: Memory context (preferences, history, workflow state)
            user_id: Current user ID
        
        Returns:
            Dict containing final_answer, tools_called, and updated memory
        """
        logger.info(f"Agent run started for user {user_id}")
        
        # Initialize state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_message)],
            "memory": memory,
            "tools_called": [],
            "current_user_id": user_id,
            "next_action": "",
            "iteration_count": 0
        }
        
        # Run workflow with increased recursion limit for multi-step workflows
        final_state = await self.workflow.ainvoke(
            initial_state,
            {"recursion_limit": 50}
        )
        
        # Extract final answer
        final_answer = ""
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage):
                final_answer = msg.content
                break
        
        # If this was a support feedback workflow, create JSON ticket
        if final_state.get("is_support_feedback") and "json_creator" in self.tools:
            await self._create_json_ticket(final_state, user_message, final_answer, user_id)
        
        logger.info("Agent run completed")
        
        return {
            "final_answer": final_answer,
            "tools_called": final_state["tools_called"],
            "messages": final_state["messages"],
            "memory": final_state["memory"]
        }
    
    async def _create_json_ticket(self, state: AgentState, user_message: str, final_answer: str, user_id: str):
        """Create a JSON ticket with all collected conversation data."""
        try:
            import pytz
            cet_timezone = pytz.timezone('Europe/Berlin')
            contact_time = datetime.now(cet_timezone).strftime("%Y-%m-%d %H:%M:%S")
            
            # Extract data from tools_called
            sentiment = "neutral"
            sentiment_confidence = 0.0
            issue_type = ""
            potential_issue = ""
            owning_team = ""
            xlsx_file_name = ""
            priority = ""
            acknowledgement_time = ""
            resolve_time = ""
            cost_usd = ""
            eur_rate = ""
            huf_rate = ""
            notes_and_dependencies = ""
            original_language = state.get("memory", {}).preferences.get("language", "Unknown") if hasattr(state.get("memory", {}), "preferences") else "Unknown"
            
            # Try to get language from translator tool call
            for tc in state["tools_called"]:
                if tc.tool_name == "translator" and tc.result:
                    if tc.arguments.get("target_language") == "en":
                        # This was the translation to English, source was original language
                        original_language = tc.result.get("source_language", original_language)
            
            for tc in state["tools_called"]:
                if tc.tool_name == "sentiment" and tc.result:
                    sentiment = tc.result.get("sentiment", "neutral")
                    sentiment_confidence = tc.result.get("confidence", 0.0)
                
                elif tc.tool_name == "documents" and tc.result:
                    sources = tc.result.get("sources", [])
                    if sources:
                        first_source = sources[0]
                        xlsx_file_name = first_source.get("source", "")
                        issue_type = first_source.get("category", "")
                        potential_issue = first_source.get("potential_issue", "")
                        notes_and_dependencies = first_source.get("notes_and_dependencies", "")
                        content = first_source.get("content_preview", "")
                        
                        # Parse content for specific fields
                        for line in content.split('\n'):
                            line_lower = line.lower()
                            if 'owning team' in line_lower or 'team' in line_lower:
                                owning_team = line.split(':')[-1].strip() if ':' in line else ""
                            if 'priority' in line_lower:
                                priority = line.split(':')[-1].strip() if ':' in line else ""
                            if 'acknowledge' in line_lower:
                                acknowledgement_time = line.split(':')[-1].strip() if ':' in line else ""
                            if 'resolution' in line_lower or 'resolve' in line_lower:
                                resolve_time = line.split(':')[-1].strip() if ':' in line else ""
                            if 'cost' in line_lower:
                                cost_usd = line.split(':')[-1].strip() if ':' in line else ""
                
                elif tc.tool_name == "fx_rates" and tc.result:
                    rate = tc.result.get("rate", "")
                    target = tc.arguments.get("target", "")
                    if target == "EUR":
                        eur_rate = str(rate)
                    elif target == "HUF":
                        huf_rate = str(rate)
            
            # Get user name from user_id
            user_name = user_id
            
            # Build full conversation
            full_conversation = f"User: {user_message}\n\nAssistant: {final_answer}"
            
            # Get file names if files were attached
            file_names = []
            if hasattr(self, '_pending_files') and self._pending_files:
                file_names = self._pending_files.get("file_names", [])
            
            # STEP: Call Guardrails tool to mask PII before creating JSON ticket
            masked_user_message = user_message
            masked_full_conversation = full_conversation
            
            if "guardrails" in self.tools:
                logger.info("Calling Guardrails tool to mask PII in conversation data")
                guardrails_tool = self.tools["guardrails"]
                
                # Mask the user message
                user_msg_result = await guardrails_tool.execute(
                    text=user_message,
                    action="mask",
                    include_audit=True
                )
                
                if user_msg_result.get("success"):
                    masked_user_message = user_msg_result.get("data", {}).get("masked_text", user_message)
                    
                    # Add guardrails tool call for user message
                    from domain.models import ToolCall
                    guardrails_tool_call = ToolCall(
                        tool_name="guardrails",
                        arguments={"text": "user_message", "action": "mask"},
                        result=user_msg_result.get("data"),
                        system_message=user_msg_result.get("system_message"),
                        detailed_message=user_msg_result.get("message")
                    )
                    state["tools_called"].append(guardrails_tool_call)
                    logger.info(f"Guardrails masked {user_msg_result.get('data', {}).get('pii_count', 0)} PII items in user message")
                
                # Mask the full conversation
                conv_result = await guardrails_tool.execute(
                    text=full_conversation,
                    action="mask",
                    include_audit=True
                )
                
                if conv_result.get("success"):
                    masked_full_conversation = conv_result.get("data", {}).get("masked_text", full_conversation)
                    logger.info(f"Guardrails masked {conv_result.get('data', {}).get('pii_count', 0)} PII items in full conversation")
            else:
                logger.warning("Guardrails tool not available - PII will not be masked!")
            
            # Call JSON creator tool with masked data
            json_tool = self.tools["json_creator"]
            result = await json_tool.execute(
                user_name=user_name,
                contact_time=contact_time,
                original_language=original_language,
                original_message=masked_user_message,  # Use masked version
                issue_type=issue_type,
                potential_issue=potential_issue,
                owning_team=owning_team,
                xlsx_file_name=xlsx_file_name,
                priority=priority,
                acknowledgement_time=acknowledgement_time,
                resolve_time=resolve_time,
                cost_usd=cost_usd,
                eur_per_usd=eur_rate,
                huf_per_usd=huf_rate,
                notes_and_dependencies=notes_and_dependencies.strip(),
                sentiment=sentiment,
                sentiment_confidence=sentiment_confidence,
                full_conversation=masked_full_conversation,  # Use masked version
                file_names=file_names
            )
            
            if result.get("success"):
                # Add JSON creator to tools_called
                from domain.models import ToolCall
                json_tool_call = ToolCall(
                    tool_name="json_creator",
                    arguments={},
                    result=result.get("data"),
                    system_message=result.get("system_message")
                )
                state["tools_called"].append(json_tool_call)
                ticket_number = result.get('data', {}).get('ticket_number', 'Unknown')
                logger.info(f"JSON ticket created: {ticket_number}")
                
                # If files were attached, call photo_upload tool
                if file_names and len(file_names) > 0 and "photo_upload" in self.tools:
                    logger.info(f"Calling photo_upload tool for ticket {ticket_number} with {len(file_names)} files")
                    photo_tool = self.tools["photo_upload"]
                    
                    # Prepare file paths and data
                    file_paths = self._pending_files.get("file_paths", []) if hasattr(self, '_pending_files') and self._pending_files else []
                    file_data = self._pending_files.get("file_data", []) if hasattr(self, '_pending_files') and self._pending_files else []
                    
                    logger.info(f"Photo upload debug - file_paths: {len(file_paths)}, file_data: {len(file_data)}, file_names: {len(file_names)}")
                    
                    # Ensure we have either file_paths or file_data
                    if not file_paths and not file_data:
                        logger.error("No file_paths or file_data available for photo upload")
                        photo_tool_call = ToolCall(
                            tool_name="photo_upload",
                            arguments={"ticket_number": ticket_number, "file_names": file_names},
                            result=None,
                            system_message="Photo upload skipped - no file data available",
                            error="No file paths or data available"
                        )
                        state["tools_called"].append(photo_tool_call)
                    else:
                        try:
                            photo_result = await photo_tool.execute(
                                action="upload",
                                ticket_number=ticket_number,
                                file_paths=file_paths if file_paths else None,
                                file_names=file_names,
                                file_data=file_data if file_data else None
                            )
                            
                            # Add photo_upload to tools_called
                            photo_tool_call = ToolCall(
                                tool_name="photo_upload",
                                arguments={"ticket_number": ticket_number, "file_names": file_names},
                                result=photo_result.get("data") if photo_result.get("success") else None,
                                system_message=photo_result.get("system_message"),
                                error=photo_result.get("error") if not photo_result.get("success") else None
                            )
                            state["tools_called"].append(photo_tool_call)
                            
                            if photo_result.get("success"):
                                logger.info(f"Photos uploaded successfully to ticket folder {ticket_number}")
                            else:
                                logger.error(f"Failed to upload photos: {photo_result.get('error')}")
                        except Exception as photo_error:
                            logger.error(f"Error uploading photos: {photo_error}", exc_info=True)
                            # Add failed photo_upload to tools_called
                            photo_tool_call = ToolCall(
                                tool_name="photo_upload",
                                arguments={"ticket_number": ticket_number, "file_names": file_names},
                                result=None,
                                system_message="Photo upload failed",
                                error=str(photo_error)
                            )
                            state["tools_called"].append(photo_tool_call)
                
                # Call sqlite_save tool to save ticket to database
                if "sqlite_save" in self.tools:
                    logger.info(f"Calling sqlite_save tool for ticket {ticket_number}")
                    sqlite_tool = self.tools["sqlite_save"]
                    
                    try:
                        # Extract the actual ticket_data from the result
                        ticket_data_for_db = result.get("data", {}).get("ticket_data")
                        sqlite_result = await sqlite_tool.execute(ticket_data=ticket_data_for_db)
                        
                        # Add sqlite_save to tools_called
                        sqlite_tool_call = ToolCall(
                            tool_name="sqlite_save",
                            arguments={"ticket_number": ticket_number},
                            result=sqlite_result.get("data") if sqlite_result.get("success") else None,
                            system_message=sqlite_result.get("system_message"),
                            error=sqlite_result.get("error") if not sqlite_result.get("success") else None
                        )
                        state["tools_called"].append(sqlite_tool_call)
                        
                        if sqlite_result.get("success"):
                            logger.info(f"Ticket {ticket_number} saved to database successfully")
                        else:
                            logger.error(f"Failed to save ticket to database: {sqlite_result.get('error')}")
                    except Exception as sqlite_error:
                        logger.error(f"Error saving to database: {sqlite_error}", exc_info=True)
                        # Add failed sqlite_save to tools_called
                        sqlite_tool_call = ToolCall(
                            tool_name="sqlite_save",
                            arguments={"ticket_number": ticket_number},
                            result=None,
                            system_message="Database save failed",
                            error=str(sqlite_error)
                        )
                        state["tools_called"].append(sqlite_tool_call)
                
                # Call send_ticket_via_email tool to send notification email
                if "send_ticket_via_email" in self.tools:
                    logger.info(f"Calling send_ticket_via_email tool for ticket {ticket_number}")
                    email_tool = self.tools["send_ticket_via_email"]
                    
                    try:
                        # Extract the actual ticket_data from the result
                        ticket_data_for_email = result.get("data", {}).get("ticket_data")
                        email_result = await email_tool.execute(ticket_data=ticket_data_for_email)
                        
                        # Add send_ticket_via_email to tools_called
                        email_tool_call = ToolCall(
                            tool_name="send_ticket_via_email",
                            arguments={"ticket_number": ticket_number},
                            result=email_result.get("data") if email_result.get("success") else None,
                            system_message=email_result.get("system_message"),
                            error=email_result.get("error") if not email_result.get("success") else None
                        )
                        state["tools_called"].append(email_tool_call)
                        
                        if email_result.get("success"):
                            logger.info(f"Email sent successfully for ticket {ticket_number}")
                        else:
                            logger.error(f"Failed to send email: {email_result.get('error')}")
                    except Exception as email_error:
                        logger.error(f"Error sending email: {email_error}", exc_info=True)
                        # Add failed send_ticket_via_email to tools_called
                        email_tool_call = ToolCall(
                            tool_name="send_ticket_via_email",
                            arguments={"ticket_number": ticket_number},
                            result=None,
                            system_message="Email send failed",
                            error=str(email_error)
                        )
                        state["tools_called"].append(email_tool_call)
            else:
                logger.error(f"Failed to create JSON ticket: {result.get('error')}")
        
        except Exception as e:
            logger.error(f"Error creating JSON ticket: {e}", exc_info=True)
    
    async def run_with_files(
        self,
        user_message: str,
        memory: Memory,
        user_id: str,
        file_paths: List[str] = None,
        file_names: List[str] = None
    ) -> Dict[str, Any]:
        """
        Run the agent workflow with attached files.
        
        This method stores file information in the agent state so the photo_upload
        tool can access them during execution.
        
        Args:
            user_message: User's input message
            memory: Memory context (preferences, history, workflow state)
            user_id: Current user ID
            file_paths: List of temporary file paths
            file_names: List of original file names
        
        Returns:
            Dict containing final_answer, tools_called, and updated memory
        """
        logger.info(f"Agent run with files started for user {user_id}, {len(file_names) if file_names else 0} files")
        
        # Store file data in the agent instance temporarily for tool access
        self._pending_files = {
            "file_paths": file_paths or [],
            "file_names": file_names or []
        }
        
        # Initialize state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_message)],
            "memory": memory,
            "tools_called": [],
            "current_user_id": user_id,
            "next_action": "",
            "iteration_count": 0
        }
        
        # Run workflow with increased recursion limit for multi-step workflows
        final_state = await self.workflow.ainvoke(
            initial_state,
            {"recursion_limit": 50}
        )
        
        # Extract final answer
        final_answer = ""
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage):
                final_answer = msg.content
                break
        
        # If this was a support feedback workflow, create JSON ticket and upload files
        if final_state.get("is_support_feedback") and "json_creator" in self.tools:
            await self._create_json_ticket(final_state, user_message, final_answer, user_id)
        
        # Clear pending files after ticket creation and photo upload
        self._pending_files = None
        
        logger.info("Agent run with files completed")
        
        return {
            "final_answer": final_answer,
            "tools_called": final_state["tools_called"],
            "messages": final_state["messages"],
            "memory": final_state["memory"]
        }
