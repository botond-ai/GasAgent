"""
Rolling summary for conversation history compression.
Summarizes every N messages to maintain context while reducing tokens.
"""

from typing import List, Optional

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.models import Message
from app.core.prompts import ROLLING_SUMMARY_PROMPT


class RollingSummary:
    """
    Rolling summary implementation.
    Compresses conversation history by summarizing older messages.
    """

    def __init__(
        self,
        summary_interval: Optional[int] = None,
        max_history: Optional[int] = None,
    ):
        """
        Initialize rolling summary.

        Args:
            summary_interval: Number of messages before triggering summary
            max_history: Maximum messages to keep in full (not summarized)
        """
        settings = get_settings()
        self.summary_interval = summary_interval or settings.memory_rolling_summary_interval
        self.max_history = max_history or settings.memory_max_history

        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
        )

    def should_summarize(self, message_count: int) -> bool:
        """
        Check if summarization should be triggered.

        Args:
            message_count: Current number of messages

        Returns:
            True if summarization should occur
        """
        return message_count >= self.summary_interval

    def summarize(
        self,
        messages: List[Message],
        previous_summary: Optional[str] = None,
    ) -> str:
        """
        Create a rolling summary of messages.

        Args:
            messages: Messages to summarize
            previous_summary: Previous summary to build upon

        Returns:
            New summary text
        """
        if not messages:
            return previous_summary or ""

        # Format messages for summarization
        formatted_messages = self._format_messages(messages)

        prompt = ROLLING_SUMMARY_PROMPT.format(
            previous_summary=previous_summary or "No previous summary.",
            new_messages=formatted_messages,
        )

        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            print(f"Summarization failed: {e}")
            return previous_summary or ""

    def get_context_for_prompt(
        self,
        messages: List[Message],
        current_summary: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> tuple[str, List[Message]]:
        """
        Get optimized context for LLM prompt.
        Combines summary with recent messages.

        Args:
            messages: All messages in session
            current_summary: Current rolling summary
            max_tokens: Maximum tokens for context

        Returns:
            Tuple of (summary, recent_messages)
        """
        # Keep last N messages in full
        recent_messages = messages[-self.max_history:]

        # If we have a summary, return it with recent messages
        if current_summary:
            return current_summary, recent_messages

        # Otherwise, just return recent messages
        return "", recent_messages

    def _format_messages(self, messages: List[Message]) -> str:
        """Format messages for the summarization prompt."""
        parts = []
        for msg in messages:
            role = msg.role.capitalize()
            content = msg.content
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"{role}: {content}")
        return "\n\n".join(parts)

    def update_summary_if_needed(
        self,
        messages: List[Message],
        current_summary: Optional[str] = None,
    ) -> tuple[Optional[str], List[Message]]:
        """
        Check if summary update is needed and perform it.

        Args:
            messages: All messages
            current_summary: Current summary

        Returns:
            Tuple of (new_summary or None, messages_to_keep)
        """
        if not self.should_summarize(len(messages)):
            return None, messages

        # Messages to summarize (older ones)
        to_summarize = messages[:-self.max_history]
        to_keep = messages[-self.max_history:]

        if not to_summarize:
            return None, messages

        # Create new summary
        new_summary = self.summarize(
            messages=to_summarize,
            previous_summary=current_summary,
        )

        return new_summary, to_keep


# Singleton instance
_rolling_summary = None


def get_rolling_summary() -> RollingSummary:
    """Get or create the rolling summary singleton."""
    global _rolling_summary
    if _rolling_summary is None:
        _rolling_summary = RollingSummary()
    return _rolling_summary
