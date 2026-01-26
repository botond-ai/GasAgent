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
    RadioTool, BookTool, TranslatorTool, PhotoUploadTool
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
        book_tool: BookTool = None,
        translator_tool: TranslatorTool = None,
        photo_upload_tool: PhotoUploadTool = None
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
        
        # Add book tool if provided
        if book_tool:
            self.tools["book"] = book_tool
        
        # Add photo upload tool if provided
        if photo_upload_tool:
            self.tools["photo_upload"] = photo_upload_tool
        
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
        
        logger.info("Agent run completed")
        
        return {
            "final_answer": final_answer,
            "tools_called": final_state["tools_called"],
            "messages": final_state["messages"],
            "memory": final_state["memory"]
        }
    
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
        
        # Clear pending files
        self._pending_files = None
        
        # Extract final answer
        final_answer = ""
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage):
                final_answer = msg.content
                break
        
        logger.info("Agent run with files completed")
        
        return {
            "final_answer": final_answer,
            "tools_called": final_state["tools_called"],
            "messages": final_state["messages"],
            "memory": final_state["memory"]
        }
