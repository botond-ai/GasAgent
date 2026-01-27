from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

@dataclass
class StateSnapshot:
    snapshot_id: str
    agent_execution_id: str
    timestamp: str
    snapshot_type: str  # before_execution, after_node, after_completion
    node_name: Optional[str]
    state_summary: Dict[str, Any]
    metadata: Dict[str, Any]

class StateTracker:
    def __init__(self):
        self._snapshots = []

    def _create_snapshot(
        self,
        agent_execution_id: str,
        snapshot_type: str,
        state: Dict[str, Any],
        node_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StateSnapshot:
        snapshot = StateSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:12]}",
            agent_execution_id=agent_execution_id,
            timestamp=datetime.utcnow().isoformat(),
            snapshot_type=snapshot_type,
            node_name=node_name,
            state_summary={k: v for k, v in state.items() if k != "messages"},
            metadata=metadata or {}
        )
        self._snapshots.append(snapshot)
        return snapshot

    def snapshot_before_execution(self, agent_execution_id: str, initial_state: Dict[str, Any]) -> StateSnapshot:
        return self._create_snapshot(agent_execution_id, "before_execution", initial_state)

    def snapshot_after_node(self, agent_execution_id: str, node_name: str, state: Dict[str, Any]) -> StateSnapshot:
        return self._create_snapshot(agent_execution_id, "after_node", state, node_name=node_name)

    def snapshot_after_completion(self, agent_execution_id: str, final_state: Dict[str, Any]) -> StateSnapshot:
        return self._create_snapshot(agent_execution_id, "after_completion", final_state)

# --- Singleton tracker getter ---
_state_tracker = None

def get_state_tracker():
    global _state_tracker
    if _state_tracker is None:
        _state_tracker = StateTracker()
    return _state_tracker
