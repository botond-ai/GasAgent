"""
Conversation history service for session-based chat memory.
Implements the Memory layer of the 4-layer AI Agent architecture.
"""
import json
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.services.redis_service import RedisService

logger = get_logger(__name__)


class ConversationMessage(BaseModel):
    """Single message in a conversation."""
    role: str = Field(description="Message role: user, assistant, or system")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[dict] = Field(default=None, description="Optional metadata (category, priority, etc.)")


class ConversationSession(BaseModel):
    """Conversation session with message history."""
    session_id: str
    user_id: Optional[str] = None
    ticket_id: Optional[str] = None
    messages: List[ConversationMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    context: Optional[dict] = Field(default=None, description="Session context (device info, preferences, etc.)")


class ConversationService:
    """
    Service for managing conversation history.
    Supports session-based stateful conversations.
    """

    def __init__(self, redis_service: Optional[RedisService] = None):
        """Initialize conversation service."""
        self.redis = redis_service or RedisService()
        self.session_ttl = timedelta(hours=24)  # Sessions expire after 24 hours
        self.max_messages = 50  # Maximum messages per session
        logger.info("Initialized ConversationService")

    def _get_session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"conversation:{session_id}"

    async def create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        context: Optional[dict] = None
    ) -> ConversationSession:
        """
        Create a new conversation session.

        Args:
            session_id: Unique session identifier
            user_id: Optional user identifier
            ticket_id: Optional ticket identifier
            context: Optional initial context

        Returns:
            New ConversationSession
        """
        session = ConversationSession(
            session_id=session_id,
            user_id=user_id,
            ticket_id=ticket_id,
            context=context or {}
        )

        await self._save_session(session)
        logger.info(f"Created conversation session: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Retrieve a conversation session.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession or None if not found
        """
        key = self._get_session_key(session_id)
        data = self.redis.client.get(key)

        if not data:
            logger.debug(f"Session not found: {session_id}")
            return None

        try:
            session_data = json.loads(data)
            return ConversationSession(**session_data)
        except Exception as e:
            logger.error(f"Error parsing session {session_id}: {e}")
            return None

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> Optional[ConversationSession]:
        """
        Add a message to a conversation session.

        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional message metadata

        Returns:
            Updated ConversationSession or None if session not found
        """
        session = await self.get_session(session_id)

        if not session:
            # Auto-create session if it doesn't exist
            session = await self.create_session(session_id)

        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata
        )

        session.messages.append(message)
        session.updated_at = datetime.utcnow()

        # Trim old messages if exceeding max
        if len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages:]

        await self._save_session(session)
        logger.debug(f"Added {role} message to session {session_id}")
        return session

    async def get_history(
        self,
        session_id: str,
        last_n: Optional[int] = None
    ) -> List[ConversationMessage]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            last_n: Optional limit to last N messages

        Returns:
            List of ConversationMessage
        """
        session = await self.get_session(session_id)

        if not session:
            return []

        messages = session.messages
        if last_n and last_n < len(messages):
            messages = messages[-last_n:]

        return messages

    async def get_history_as_text(
        self,
        session_id: str,
        last_n: Optional[int] = 10
    ) -> str:
        """
        Get conversation history formatted as text for LLM context.

        Args:
            session_id: Session identifier
            last_n: Limit to last N messages

        Returns:
            Formatted conversation history string
        """
        messages = await self.get_history(session_id, last_n)

        if not messages:
            return ""

        formatted = []
        for msg in messages:
            role = msg.role.capitalize()
            formatted.append(f"{role}: {msg.content}")

        return "\n\n".join(formatted)

    async def update_context(
        self,
        session_id: str,
        context: dict
    ) -> Optional[ConversationSession]:
        """
        Update session context (device info, preferences, etc.).

        Args:
            session_id: Session identifier
            context: Context dict to merge

        Returns:
            Updated ConversationSession or None
        """
        session = await self.get_session(session_id)

        if not session:
            return None

        if session.context:
            session.context.update(context)
        else:
            session.context = context

        session.updated_at = datetime.utcnow()
        await self._save_session(session)
        logger.debug(f"Updated context for session {session_id}")
        return session

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a conversation session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False otherwise
        """
        key = self._get_session_key(session_id)
        result = self.redis.client.delete(key)
        if result:
            logger.info(f"Deleted session: {session_id}")
        return bool(result)

    async def _save_session(self, session: ConversationSession) -> None:
        """Save session to Redis."""
        key = self._get_session_key(session.session_id)

        # Convert to JSON-serializable format
        session_data = session.model_dump(mode='json')

        self.redis.client.setex(
            key,
            self.session_ttl,
            json.dumps(session_data)
        )


# Singleton instance
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """Get or create the conversation service singleton."""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service
