"""
Trace logging utility for hybrid memory execution flow.
"""
def log_trace(trace: list, step: str, info: dict = None):
    entry = {'step': step}
    if info:
        entry.update(info)
    trace.append(entry)
    return trace
