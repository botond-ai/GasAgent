"""Chat service orchestrating message flow."""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import difflib

from domain.models import Message, MessageRole, UserProfile
from domain.interfaces import (
    UserProfileRepository, SessionRepository, ActivityCallback
)
from services.langgraph_workflow import AdvancedRAGAgent
from services.development_logger import get_dev_logger


class ChatService:
    """Service for handling chat interactions."""

    def __init__(
        self,
        rag_agent: AdvancedRAGAgent,
        profile_repo: UserProfileRepository,
        session_repo: SessionRepository,
        upload_repo=None,  # Optional file upload repo to get global categories
        activity_callback: Optional[ActivityCallback] = None,
    ):
        self.rag_agent = rag_agent
        self.profile_repo = profile_repo
        self.session_repo = session_repo
        self.upload_repo = upload_repo
        self.activity_callback = activity_callback

    async def process_message(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Process user message:
        - Check for reset context command
        - Load/create profile
        - Append user message
        - Run RAG agent
        - Append assistant response
        - Return response
        """
        # Track API call timing
        api_start_time = time.time()
        
        # Check for reset context command (case-insensitive)
        # Handle both "reset context" and the confirmation variant
        message_lower = user_message.strip().lower()
        if message_lower == "reset context" or message_lower.startswith("reset context ("):
            return await self._handle_reset_context(user_id, session_id)

        # Log: Message received
        if self.activity_callback:
            await self.activity_callback.log_activity(
                f"💬 Kérdés feldolgozása: '{user_message[:50]}{'...' if len(user_message) > 50 else ''}'",
                activity_type="processing"
            )

        # Load or create profile
        profile = await self.profile_repo.get_profile(user_id)
        if not profile:
            profile = UserProfile(user_id=user_id)
            await self.profile_repo.save_profile(profile)

        # Get available categories - now from upload repo (global, not user-specific)
        available_categories = []
        if self.upload_repo:
            available_categories = await self.upload_repo.get_categories()
        
        # If no categories uploaded, respond
        if not available_categories:
            response = {
                "final_answer": "Még nincsenek feltöltött dokumentumok. Kérjük, először töltsön fel egy dokumentumot egy kategóriához.",
                "tools_used": [],
                "memory_snapshot": {
                    "available_categories": [],
                }
            }
            # Append messages
            await self.session_repo.append_message(
                session_id,
                Message(
                    role=MessageRole.USER,
                    content=user_message,
                    timestamp=datetime.now(),
                )
            )
            await self.session_repo.append_message(
                session_id,
                Message(
                    role=MessageRole.ASSISTANT,
                    content=response["final_answer"],
                    timestamp=datetime.now(),
                    metadata={"response_type": "no_documents"},
                )
            )

            # Log: No documents
            if self.activity_callback:
                await self.activity_callback.log_activity(
                    "⚠️ Nincs feltöltött dokumentum",
                    activity_type="warning"
                )

            return response

        # ============================================================================
        # FEATURE: Conversation History Cache - Check BEFORE appending the current message
        # ============================================================================
        # Load conversation history for context (BEFORE appending current message)
        previous_messages = await self.session_repo.get_messages(session_id)
        
        # DEBUG: Log session info and history count
        dev_logger = get_dev_logger()
        dev_logger.log_suggestion_1_history(
            event="session_info",
            description=f"Session {session_id} has {len(previous_messages)} messages",
            details={"session_id": session_id, "message_count": len(previous_messages)}
        )
        
        # DEBUG: Print loaded messages for verification
        import sys
        print(f"[CHAT] Loaded session {session_id}: {len(previous_messages)} messages", file=sys.stderr, flush=True)
        for i, msg in enumerate(previous_messages):
            print(f"[CHAT]   [{i}] {msg.role}: '{msg.content[:60]}...'", file=sys.stderr, flush=True)
        
        # Check if this exact question was asked before in the conversation
        cached_answer = await self._check_question_cache(user_message, previous_messages)

        # Append user message
        await self.session_repo.append_message(
            session_id,
            Message(
                role=MessageRole.USER,
                content=user_message,
                timestamp=datetime.now(),
                user_id=user_id,
            )
        )
        
        # DEBUG: Log the append
        dev_logger = get_dev_logger()
        dev_logger.log_suggestion_1_history(
            event="user_message_appended",
            description=f"User message appended to session",
            details={"message": user_message[:50]}
        )
        
        if cached_answer:
            # Cache hit! Return the cached answer without running RAG agent
            
            # 🔥 CRITICAL: Append ASSISTANT message to history for next cache check!
            await self.session_repo.append_message(
                session_id,
                Message(
                    role=MessageRole.ASSISTANT,
                    content=cached_answer,
                    timestamp=datetime.now(),
                    metadata={"source": "conversation_cache", "from_cache": True}
                )
            )
            
            # DEBUG: Log the cache hit append
            dev_logger.log_suggestion_1_history(
                event="cache_hit_assistant_appended",
                description=f"Assistant message from cache appended",
                details={"answer_length": len(cached_answer)}
            )
            
            # Log cache hit to development logger
            dev_logger = get_dev_logger()
            dev_logger.log_suggestion_1_history(
                event="cache_hit",
                description=f"Cache hit! Returning cached answer without RAG pipeline",
                details={"cached_answer_length": len(cached_answer)}
            )
            
            # Log activity callback for UI display
            if self.activity_callback:
                await self.activity_callback.log_activity(
                    f"⚡ Cache hit: Válasz az előzményekből (telepített dokumentumok keresése nélkül)",
                    activity_type="success",
                    metadata={
                        "event_type": "cache_hit",
                        "response_length": len(cached_answer),
                        "source": "conversation_cache"
                    }
                )

            
            return {
                "final_answer": cached_answer,
                "tools_used": [],
                "fallback_search": False,
                "memory_snapshot": {
                    "routed_category": None,
                    "available_categories": available_categories,
                    "from_cache": True,
                },
                "rag_debug": {
                    "retrieved": [],
                    "cache_hit": True,
                },
                "debug_steps": [],
                "api_info": {
                    "endpoint": "/api/chat",
                    "method": "POST",
                    "status_code": 200,
                    "response_time_ms": round((time.time() - api_start_time) * 1000, 2),
                    "source": "conversation_cache"
                }
            }

        # Log: Category routing (CSAK ha cache miss!)
        if self.activity_callback:
            await self.activity_callback.log_activity(
                f"🎯 Kategória felismerés: {len(available_categories)} kategória közül",
                activity_type="processing",
                metadata={"category_count": len(available_categories), "categories": available_categories}
            )
        
        # Cache miss - Run RAG agent with available global categories AND conversation history
        rag_response = await self.rag_agent.answer_question(
            user_id, user_message, available_categories,
            activity_callback=self.activity_callback,
            conversation_history=previous_messages if previous_messages else None
        )

        # Extract answer and metadata (WorkflowOutput object)
        final_answer = rag_response.final_answer
        routed_category = rag_response.routed_category
        # Get context_chunks from citation_sources or use empty list
        context_chunks = getattr(rag_response, 'context_chunks', [])
        if not context_chunks and hasattr(rag_response, 'citation_sources'):
            context_chunks = rag_response.citation_sources
        fallback_search = getattr(rag_response, 'fallback_triggered', False)

        # DEBUG: Log the final answer
        import sys
        print(f"[CHAT] final_answer type={type(final_answer)}, length={len(final_answer) if final_answer else 0}, value={final_answer[:100] if final_answer else 'NONE/EMPTY'}", file=sys.stderr)

        # Log: Response ready
        if self.activity_callback:
            await self.activity_callback.log_activity(
                f"✓ Válasz kész: {len(context_chunks)} chunk felhasználva",
                activity_type="success",
                metadata={
                    "chunk_count": len(context_chunks),
                    "category": routed_category,
                    "fallback_search": fallback_search
                }
            )

        # Append assistant response
        # Extract chunk IDs - try to get chunk_id or use index as fallback
        chunk_ids = []
        for c in context_chunks:
            if hasattr(c, 'chunk_id'):
                chunk_ids.append(c.chunk_id)
            elif hasattr(c, 'index'):
                chunk_ids.append(str(c.index))
            else:
                chunk_ids.append(str(len(chunk_ids)))
        
        await self.session_repo.append_message(
            session_id,
            Message(
                role=MessageRole.ASSISTANT,
                content=final_answer,
                timestamp=datetime.now(),
                metadata={
                    "category_routed": routed_category,
                    "chunk_ids": chunk_ids,
                    "fallback_search": fallback_search,
                }
            )
        )

        return {
            "final_answer": final_answer,
            "tools_used": [],
            "fallback_search": fallback_search,
            "memory_snapshot": {
                "routed_category": routed_category,
                "available_categories": available_categories,
            },
            "rag_debug": {
                "retrieved": [
                    {
                        "chunk_id": getattr(c, "chunk_id", getattr(c, "index", "")),
                        "distance": getattr(c, "distance", 0),
                        "snippet": getattr(c, "preview", "")[:100] if hasattr(c, "preview") else "",
                        "metadata": getattr(c, "metadata", {}),
                        "content": getattr(c, "content", ""),
                        "source_file": getattr(c, "metadata", {}).get("source_file", "Unknown") if hasattr(c, "metadata") else "Unknown",
                        "section_title": getattr(c, "metadata", {}).get("section_title", "") if hasattr(c, "metadata") else "",
                    }
                    for c in (context_chunks if context_chunks else [])
                ]
            },
            "debug_steps": getattr(rag_response, "workflow_logs", []),
            "api_info": {
                "endpoint": "/api/chat",
                "method": "POST",
                "status_code": 200,
                "response_time_ms": round((time.time() - api_start_time) * 1000, 2),
            }
        }

    async def _handle_reset_context(
        self, user_id: str, session_id: str
    ) -> Dict[str, Any]:
        """Clear session conversation history only."""
        await self.session_repo.clear_messages(session_id)

        # Get profile for categories
        profile = await self.profile_repo.get_profile(user_id)
        categories = profile.categories if profile else []

        return {
            "final_answer": "Kontextus törölve, tiszta lappal megyünk tovább.",
            "tools_used": [],
            "memory_snapshot": {
                "available_categories": categories,
            }
        }

    async def get_session_history(self, session_id: str) -> List[Message]:
        """Get conversation history for a session."""
        return await self.session_repo.get_messages(session_id)

    async def _check_question_cache(
        self,
        current_question: str,
        conversation_history: Optional[List[Message]] = None
    ) -> Optional[str]:
        """
        Check if this exact (or very similar) question was asked before in the conversation.
        
        Returns:
            Cached answer if found (exact or fuzzy match), None otherwise
        """
        if not conversation_history:
            return None
        
        # DEBUG: Log what we have in history
        dev_logger = get_dev_logger()
        user_msgs = [m.content[:40] for m in conversation_history if (m.role == MessageRole.USER if not isinstance(m.role, str) else m.role == 'user')]
        dev_logger.log_suggestion_1_history(
            event="cache_check_debug",
            description=f"Cache check started. History has {len(conversation_history)} messages, {len(user_msgs)} user messages",
            details={"user_questions": user_msgs[:5]}
        )
        
        # Normalize current question for comparison
        normalized_current = current_question.strip().lower()
        
        # DEBUG: Log detailed comparison
        import sys
        print(f"[CACHE] Checking: '{normalized_current}'", file=sys.stderr, flush=True)
        
        # Search through history for previous answers
        for i in range(len(conversation_history) - 1):
            msg = conversation_history[i]
            
            # Convert role to MessageRole if it's a string
            msg_role = msg.role
            if isinstance(msg_role, str):
                msg_role = MessageRole(msg_role)
            
            # Look for USER messages (questions)
            if msg_role == MessageRole.USER:
                normalized_prev = msg.content.strip().lower()
                
                # DEBUG: Log comparison
                import sys
                if normalized_current == normalized_prev:
                    print(f"[CACHE] ✅ EXACT MATCH FOUND at index {i}!", file=sys.stderr, flush=True)
                
                # Check 1: Exact match (case-insensitive, whitespace-trimmed)
                if normalized_current == normalized_prev:
                    # Found exact match! Get the next ASSISTANT message
                    if i + 1 < len(conversation_history):
                        next_msg = conversation_history[i + 1]
                        next_msg_role = next_msg.role
                        if isinstance(next_msg_role, str):
                            next_msg_role = MessageRole(next_msg_role)
                        if next_msg_role == MessageRole.ASSISTANT:
                            print(f"[CACHE] Returning cached answer of length {len(next_msg.content)}", file=sys.stderr, flush=True)
                            return next_msg.content
                
                # Check 2: Fuzzy match (similarity > 0.85 = very similar)
                similarity = difflib.SequenceMatcher(
                    None,
                    normalized_current,
                    normalized_prev
                ).ratio()
                
                if similarity > 0.85:
                    # Found very similar question! Get the next ASSISTANT message
                    if i + 1 < len(conversation_history):
                        next_msg = conversation_history[i + 1]
                        next_msg_role = next_msg.role
                        if isinstance(next_msg_role, str):
                            next_msg_role = MessageRole(next_msg_role)
                        if next_msg_role == MessageRole.ASSISTANT:
                            print(f"[CACHE] FUZZY MATCH ({similarity:.2f}) - returning cached answer", file=sys.stderr, flush=True)
                            return next_msg.content
        
        print(f"[CACHE] ❌ No cache hit found", file=sys.stderr, flush=True)
        # No cache hit found
        return None
