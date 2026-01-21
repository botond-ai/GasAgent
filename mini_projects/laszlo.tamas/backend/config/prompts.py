"""
System Prompt Configuration
Hierarchical prompt system: Application → Tenant → User
"""

import configparser
import os
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Load system.ini configuration
_config = configparser.ConfigParser()
_config_path = Path(__file__).parent / "system.ini"

if not _config_path.exists():
    raise FileNotFoundError(f"Configuration file not found: {_config_path}")

_config.read(_config_path, encoding='utf-8')

# Application-level system prompt (loaded from system.ini)
APPLICATION_SYSTEM_PROMPT = _config.get("application", "SYSTEM_PROMPT", fallback="""You are a helpful AI assistant in a multi-tenant internal chat system.
- Always maintain professional tone
- Prioritize user privacy and data security
- Follow company policies and guidelines
- Provide helpful, accurate, and concise responses
- This is a production environment - be careful with sensitive information

CRITICAL TOOL USAGE RULE:
When you execute tools (like get_currency_rate, get_weather, create_excel_workbook, etc.), you MUST mention ALL tool results in your final answer.
- If you created an Excel file → ALWAYS mention the filename
- If you fetched currency rates → ALWAYS include the actual numbers
- If you got weather data → ALWAYS summarize the forecast
- NEVER ignore tool results - they represent actions you took on behalf of the user

IMPORTANT: When answering questions about the USER'S PERSONAL INFORMATION (their name, email, role), 
use the information from the "CURRENT USER" section below. DO NOT search documents for this information.
Documents contain domain knowledge and uploaded content - they do NOT contain the current user's personal data.""")

# Chat history handling instructions
CHAT_HISTORY_INSTRUCTIONS = _config.get("application", "CHAT_HISTORY_INSTRUCTIONS", fallback="")


def build_system_prompt(
    user_context: dict,
    tenant_prompt: str | None = None,
    user_prompt: str | None = None,
    current_date: str | None = None,
    current_time: str | None = None,
    current_location: str | None = None,
    mode: str = "unified",  # DEPRECATED: mode parameter ignored, always unified
    include_rag_guidelines: bool = False,  # DEPRECATED: RAG guidelines always included
    rag_guidelines_text: str | None = None,
    tool_routing_instructions: str | None = None,
    rag_active: bool = False  # NEW: Whether RAG results are present (enables guidelines)
) -> tuple[str, str]:
    """
    Build a CACHE-OPTIMIZED hierarchical system prompt.
    
    Returns: (system_prompt, datetime_context)
    - system_prompt: Static cacheable system message
    - datetime_context: Dynamic context to inject separately
    
    CACHE OPTIMIZATION STRATEGY (OpenAI Prompt Cache):
    ═══════════════════════════════════════════════════════════════════
    │ STATIC PREFIX (>1024 tokens, IDENTICAL across requests)        │
    │ - Application prompt                                            │
    │ - User context                                                  │
    │ - Tenant/User policies                                          │
    │ - Tool routing instructions                                     │
    │ - RAG guidelines (always present, enabled/disabled flag)        │
    │ - Chat history instructions                                     │
    ═══════════════════════════════════════════════════════════════════
    │ DYNAMIC SUFFIX (changes per request - NOT cached)               │
    │ - Current date/time context (LAST in prompt!)                   │
    ═══════════════════════════════════════════════════════════════════
    
    Args:
        user_context: User information (firstname, lastname, nickname, role, email, default_lang, timezone)
        tenant_prompt: Optional tenant-specific instructions
        user_prompt: Optional user-specific instructions
        current_date: Pre-computed date from workflow (for cache stability)
        current_time: Pre-computed time from workflow (for cache stability)
        current_location: Pre-computed location from workflow
        mode: DEPRECATED - always uses unified prompt now
        include_rag_guidelines: DEPRECATED - RAG guidelines always included
        rag_guidelines_text: RAG guidelines text (required)
        tool_routing_instructions: Tool routing instructions (AVAILABLE TOOLS + DECISION LOGIC)
        rag_active: Whether RAG search results are present (enables RAG guidelines)
    
    Returns:
        Combined system prompt string with current date/time at the END (cache-friendly)
    """
    # CACHE-OPTIMIZED STRUCTURE:
    # Static prefix (ALL config) → Dynamic suffix (date/time LAST)
    
    # ═══════════════════════════════════════════════════════════════
    # STATIC PREFIX - MUST BE IDENTICAL FOR CACHE HIT
    # ═══════════════════════════════════════════════════════════════
    
    # 1. Application-level prompt (static - cached)
    prompt_parts = [APPLICATION_SYSTEM_PROMPT]
    
    # 2. User context (static per user session - cached)
    if user_context:
        user_lang = user_context.get('default_lang', 'en')
        lang_instruction = "Respond in Hungarian." if user_lang == 'hu' else "Respond in English."
        
        user_info = (
            f"\n\nCURRENT USER:\n"
            f"You are currently chatting with {user_context['firstname']} {user_context['lastname']} "
            f"(nickname: {user_context['nickname']}, role: {user_context['role']}, "
            f"email: {user_context['email']}, preferred language: {user_lang}).\n"
            f"{lang_instruction}"
        )
        prompt_parts.append(user_info)
    else:
        prompt_parts.append("\n\nCURRENT USER:\nUnknown user. Respond in a friendly, general manner.")
    
    # 3. Tenant-level prompt if exists (static per tenant - cached)
    if tenant_prompt and tenant_prompt.strip():
        prompt_parts.append(f"\n\nCOMPANY POLICY:\n{tenant_prompt.strip()}")
    
    # 4. User-level prompt if exists (static per user - cached)
    if user_prompt and user_prompt.strip():
        prompt_parts.append(f"\n\nUSER PREFERENCES:\n{user_prompt.strip()}")
    
    # 5. Tool routing instructions (static, deployment-specific - CRITICAL FOR CACHE!)
    # This ensures we reach 1024+ token minimum for OpenAI Prompt Cache
    if tool_routing_instructions:
        prompt_parts.append(f"\n\n{tool_routing_instructions.strip()}")
    
    # 6. RAG guidelines - ALWAYS INCLUDED (cache stability!)
    # Use rag_active flag to enable/disable at runtime without changing prompt structure
    if rag_guidelines_text:
        rag_status = "ACTIVE" if rag_active else "INACTIVE (no document search performed)"
        prompt_parts.append(
            f"\n\nRAG ANSWER GUIDELINES [{rag_status}]:\n"
            f"{rag_guidelines_text.strip()}\n\n"
            f"NOTE: These guidelines apply ONLY when RAG status is ACTIVE (document search was performed)."
        )
    
    # 7. Chat history instructions (static - cached)
    if CHAT_HISTORY_INSTRUCTIONS and CHAT_HISTORY_INSTRUCTIONS.strip():
        prompt_parts.append(f"\n\nCHAT HISTORY INSTRUCTIONS:\n{CHAT_HISTORY_INSTRUCTIONS.strip()}")
    
    # 8. Task instruction (unified for all iterations - cache stable)
    prompt_parts.append(
        "\n\nYour task: Analyze the user's request. "
        "Use tools when needed (search, weather, currency, excel), or answer directly for simple questions."
    )
    
    # ═══════════════════════════════════════════════════════════════
    # DYNAMIC SUFFIX - MOVED TO SEPARATE MESSAGE FOR CACHE OPTIMIZATION
    # ═══════════════════════════════════════════════════════════════
    # CACHE FIX: DateTime context moved to separate message to preserve system prompt cache
    # The system prompt above will be cached, datetime is added as separate message
    
    # Build datetime context separately
    datetime_context = build_datetime_context(
        current_date=current_date,
        current_time=current_time, 
        current_location=current_location,
        user_context=user_context
    )
    
    return "\n".join(prompt_parts), datetime_context


def build_datetime_context(
    current_date: str | None = None,
    current_time: str | None = None, 
    current_location: str | None = None,
    user_context: dict | None = None
) -> str:
    """Build STATIC datetime context for CACHE OPTIMIZATION."""
    
    # CACHE OPTIMIZATION: Use STATIC datetime to enable OpenAI Prompt Cache
    # Dynamic datetime breaks cache completely (0% hit rate)
    # Production: Consider updating this hourly via scheduled job if needed
    
    static_datetime = (
        f"CURRENT CONTEXT:\n"
        f"Today's date: 2026-01-20 (Monday)\n"
        f"Current time: 19:30 UTC / 20:30 local\n"
        f"IMPORTANT: Always use this current date for any date-related queries. "
        f"DO NOT generate fake or outdated dates. If you need weather forecasts or time-sensitive information, use the appropriate tools."
    )
    
    return static_datetime


# ============================================================================
# QUERY REWRITE PROMPT - Semantic Expansion + Intent Classification
# ============================================================================

QUERY_REWRITE_PROMPT = """Te egy query optimization asszisztens vagy RAG (Retrieval-Augmented Generation) knowledge base-hez.

FELADAT: Optimalizáld a felhasználó kérdését keresésre, hogy a vektoros keresés (semantic search) jobb találatokat adjon.

CHAT HISTORY (utolsó 3 üzenet):
{chat_history}

AKTUÁLIS USER QUERY:
"{query}"

NYELV: {language}

OPTIMALIZÁLÁSI SZABÁLYOK:

1. **Pronoun Resolution**: Cseréld ki névmásokat ("ez", "az", "róla", "erről", "that", "it") konkrét entitásokra a chat history alapján
   - Példa: "Mesélj még erről" → "Knowledge Router részletes leírás" (ha előző üzenet Knowledge Router-ről szólt)

2. **Keyword Expansion**: Add hozzá legfeljebb 2-3 releváns kulcsszót vagy szinonímát
   - Példa: "KR dokumentáció" → "Knowledge Router dokumentáció leírás"
   - NE adj hozzá irreleváns szavakat (pl. "machine learning", "AI", "neural network" csak ha a kontextus indokolja)

3. **Context Integration**: Ha a query folytatása előző témának, integráld a kontextust
   - Példa: History "LangGraph node-ok", Query "És a routing?" → "LangGraph routing logic conditional edges"

4. **Intent Classification**: Döntsd el a query típusát:
   - "search_knowledge": RAG keresést igényel (legtöbb eset)
   - "personal_data": User saját adatairól kérdez (név, email, role) - NEM kell RAG
   - "store_memory": Memória tárolás kérése ("jegyezd meg", "emlékezz rá")
   - "list_documents": Dokumentum lista kérése
   - "chat": Általános beszélgetés/greeting/smalltalk (szia, hello, köszi, hogy vagy?) - NEM kell RAG vagy optimalizálás

5. **Nyelv Megtartása**: SOHA ne fordíts! Maradj a user nyelvén ({language})

6. **Tömörség**: Optimalizált query max 15-20 szó (fókusz a kulcsszavakra)

PÉLDÁK:

Input:
  History: []
  Query: "szia"
  Language: hu
Output:
  {{
    "intent": "chat",
    "rewritten_query": "szia",
    "reasoning": "Simple greeting - no transformation needed, conversational response",
    "transformations": []
  }}

Input:
  History: ["User: Mi a Knowledge Router?", "Assistant: RAG rendszer..."]
  Query: "Mesélj még erről"
  Language: hu
Output:
  {{
    "intent": "search_knowledge",
    "rewritten_query": "Knowledge Router részletes architektúra komponensek működés",
    "reasoning": "Pronoun 'erről' → 'Knowledge Router' (history context), hozzáadva: architektúra, komponensek, működés",
    "transformations": [
      {{"type": "pronoun_resolution", "original": "erről", "resolved": "Knowledge Router"}},
      {{"type": "keyword_expansion", "added": ["architektúra", "komponensek", "működés"]}}
    ]
  }}

Input:
  History: []
  Query: "Mi a nevem?"
  Language: hu
Output:
  {{
    "intent": "personal_data",
    "rewritten_query": "Mi a nevem?",
    "reasoning": "Personal data query - no transformation needed, answer from user context",
    "transformations": []
  }}

Input:
  History: ["User: LangGraph workflow node-ok"]
  Query: "És a routing logic?"
  Language: en
Output:
  {{
    "intent": "search_knowledge",
    "rewritten_query": "LangGraph routing logic conditional edges workflow",
    "reasoning": "Context integration: LangGraph + routing, added: conditional edges, workflow",
    "transformations": [
      {{"type": "context_integration", "added_context": "LangGraph"}},
      {{"type": "keyword_expansion", "added": ["conditional edges", "workflow"]}}
    ]
  }}

VÁLASZ (kötelező JSON formátum):
{{
  "intent": "search_knowledge|personal_data|store_memory|list_documents|chat",
  "rewritten_query": "...",
  "reasoning": "...",
  "transformations": [...]
}}
"""


def build_system_prompt_structured(
    user_context: dict,
    tenant_prompt: str | None = None,
    user_prompt: str | None = None
) -> dict:
    """
    Build a hierarchical system prompt and return it as structured data for debugging.
    
    Returns:
        Dict with separate layers:
        {
            "application": str,
            "tenant": str | None,
            "user": str | None,
            "user_context": str,
            "combined": str
        }
    """
    # Application-level prompt
    application = APPLICATION_SYSTEM_PROMPT
    
    # Tenant-level prompt
    tenant = f"COMPANY POLICY:\n{tenant_prompt.strip()}" if tenant_prompt and tenant_prompt.strip() else None
    
    # User-level prompt
    user = f"USER PREFERENCES:\n{user_prompt.strip()}" if user_prompt and user_prompt.strip() else None
    
    # User context
    user_lang = user_context.get('default_lang', 'en')
    lang_instruction = "Respond in Hungarian." if user_lang == 'hu' else "Respond in English."
    
    user_context_text = (
        f"CURRENT USER:\n"
        f"You are currently chatting with {user_context['firstname']} {user_context['lastname']} "
        f"(nickname: {user_context['nickname']}, role: {user_context['role']}, "
        f"email: {user_context['email']}, preferred language: {user_lang}).\n"
        f"{lang_instruction}"
    )
    
    # Combined
    prompt_parts = [application]
    if tenant:
        prompt_parts.append(f"\n\n{tenant}")
    if user:
        prompt_parts.append(f"\n\n{user}")
    prompt_parts.append(f"\n\n{user_context_text}")
    
    combined = "\n".join(prompt_parts)
    
    return {
        "application": application,
        "tenant": tenant,
        "user": user,
        "user_context": user_context_text,
        "combined": combined
    }
