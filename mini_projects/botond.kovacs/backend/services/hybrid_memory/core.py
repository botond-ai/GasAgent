"""
HybridMemory class: coordinates all memory layers and exposes state channels.
Supports checkpointing, restore, and deterministic state updates.
"""
from typing import List, Dict, Any, Optional
import copy
import time
from .reducers import (
    messages_reducer, summary_reducer, facts_reducer, trace_reducer, retrieved_context_reducer
)

class HybridMemory:
    def __init__(self, max_turns: int = 3, trace_max_len: int = 100):
        self.state = {
            'messages': [],
            'summary': None,
            'facts': {},
            'retrieved_context': [],
            'trace': [],
        }
        self.max_turns = max_turns
        self.trace_max_len = trace_max_len

    def update_messages(self, new_messages: List[Dict[str, Any]]):
        self.state['messages'] = messages_reducer(self.state['messages'] + new_messages, self.max_turns)

    def update_summary(self, new_summary: Dict[str, Any]):
        self.state['summary'] = summary_reducer(self.state['summary'], new_summary)

    def update_facts(self, new_facts: Dict[str, Dict[str, Any]]):
        self.state['facts'] = facts_reducer(self.state['facts'], new_facts)

    def update_trace(self, new_entry: Dict[str, Any]):
        self.state['trace'] = trace_reducer(self.state['trace'], new_entry, self.trace_max_len)

    def update_retrieved_context(self, new_context: Optional[List[Dict[str, Any]]]):
        self.state['retrieved_context'] = retrieved_context_reducer(self.state['retrieved_context'], new_context)

    def snapshot(self) -> Dict[str, Any]:
        """Return a deep copy of the current state for checkpointing."""
        return copy.deepcopy(self.state)

    def restore(self, snapshot: Dict[str, Any]):
        """Restore state from a checkpoint."""
        self.state = copy.deepcopy(snapshot)

    def get_snapshot_info(self) -> Dict[str, Any]:
        """Return summary info for API response."""
        return {
            'summary_version': (self.state['summary'] or {}).get('version', 0),
            'facts_count': len(self.state['facts']),
            'recent_message_count': len(self.state['messages']),
            'retrieved_context': bool(self.state['retrieved_context']),
            'trace_length': len(self.state['trace']),
        }
