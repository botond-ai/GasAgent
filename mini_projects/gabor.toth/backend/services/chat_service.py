"""Chat service orchestrating message flow."""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from domain.models import Message, MessageRole, UserProfile
from domain.interfaces import (
    UserProfileRepository, SessionRepository, ActivityCallback
)
from services.langgraph_workflow import AdvancedRAGAgent


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

        # Log: Category routing
        if self.activity_callback:
            await self.activity_callback.log_activity(
                f"🎯 Kategória felismerés: {len(available_categories)} kategória közül",
                activity_type="processing",
                metadata={"category_count": len(available_categories), "categories": available_categories}
            )

        # Run RAG agent with available global categories
        rag_response = await self.rag_agent.answer_question(
            user_id, user_message, available_categories,
            activity_callback=self.activity_callback
        )

        # Extract answer and metadata (WorkflowOutput object)
        final_answer = rag_response.final_answer
        routed_category = rag_response.routed_category
        # Get context_chunks from citation_sources or use empty list
        context_chunks = getattr(rag_response, 'context_chunks', [])
        if not context_chunks and hasattr(rag_response, 'citation_sources'):
            context_chunks = rag_response.citation_sources
        fallback_search = getattr(rag_response, 'fallback_triggered', False)

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
