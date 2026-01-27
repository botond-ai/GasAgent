from dataclasses import dataclass, field
from typing import List


@dataclass
class ConversationSession:
    """Manages conversation history across multiple queries."""
    history: List[dict] = field(default_factory=list)  # OpenAI message format
    max_turns: int = 10  # Limit to avoid token overflow

    def add_turn(self, query: str, response: str) -> None:
        """Add a user/assistant exchange to history."""
        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": response})
        # Enforce limit (keep most recent turns)
        max_messages = self.max_turns * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]

    def get_history(self) -> List[dict]:
        """Return history in OpenAI message format."""
        return self.history.copy()

    def clear(self) -> None:
        """Clear conversation history."""
        self.history = []
