"""
Reducers for hybrid memory channels: messages, summary, facts, trace, retrieved_context.
All reducers are deterministic and idempotent.
"""
from typing import List, Dict, Any, Optional
import time

# --- Messages Reducer ---
def messages_reducer(messages: List[Dict[str, Any]], max_turns: int = 6) -> List[Dict[str, Any]]:
    """
    Deduplicate, sort by timestamp, trim to last N turns (user+assistant = 1 turn).
    """
    seen = set()
    deduped = []
    for msg in sorted(messages, key=lambda x: x.get('timestamp', 0)):
        key = (msg.get('role'), msg.get('content'), msg.get('timestamp'))
        if key not in seen:
            seen.add(key)
            deduped.append(msg)
    # Only keep last N turns (2 messages per turn)
    return deduped[-max_turns*2:]

# --- Summary Reducer ---
def summary_reducer(summary: Optional[Dict[str, Any]], new_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace summary, increment version.
    """
    version = (summary or {}).get('version', 0) + 1
    return {'content': new_summary['content'], 'version': version, 'timestamp': int(time.time())}

# --- Facts Reducer ---
def facts_reducer(facts: Dict[str, Dict[str, Any]], new_facts: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Last-write-wins by timestamp for each fact key.
    """
    result = dict(facts)
    for k, v in new_facts.items():
        if k not in result or v['timestamp'] > result[k]['timestamp']:
            result[k] = v
    return result

# --- Trace Reducer ---
def trace_reducer(trace: List[Dict[str, Any]], new_entry: Dict[str, Any], max_len: int = 100) -> List[Dict[str, Any]]:
    """
    Append-only, capped size.
    """
    trace = (trace or []) + [new_entry]
    return trace[-max_len:]

# --- Retrieved Context Reducer ---
def retrieved_context_reducer(context: Optional[List[Dict[str, Any]]], new_context: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Replace with new context if provided, else keep existing.
    """
    if new_context is not None:
        return new_context
    return context or []
