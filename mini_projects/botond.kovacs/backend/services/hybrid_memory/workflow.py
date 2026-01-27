"""
HybridChatWorkflowService: Orchestrates the hybrid memory chat workflow.
Handles all hybrid memory logic, state updates, and response formatting.
"""
from typing import Dict, Any
from services.hybrid_memory.core import HybridMemory
from services.hybrid_memory.pii import filter_pii_in_layer
from services.hybrid_memory.rag import should_trigger_rag, rag_retrieve
from services.hybrid_memory.trace import log_trace

class HybridChatWorkflowService:
    def __init__(self, vector_store, pii_mode: str = 'placeholder'):
        self.vector_store = vector_store
        self.pii_mode = pii_mode

    def run(self, user_message: str, prev_state: Dict[str, Any] = None) -> Dict[str, Any]:
        memory = HybridMemory()
        if prev_state:
            memory.restore(prev_state)
        trace = memory.state['trace']

        # 1. Log metrics
        log_trace(trace, 'metrics_logger', {'user_message': user_message})

        # 2. Summarizer (dummy, replace with real summary)
        summary = {'content': f'Summary up to now. Last: {user_message}'}
        memory.update_summary(summary)
        log_trace(trace, 'summarizer', {'summary': summary})

        # 3. Facts extractor (dummy, replace with LLM extraction)
        facts = {}
        memory.update_facts(facts)
        log_trace(trace, 'facts_extractor', {'facts': facts})

        # 4. Conditional RAG
        retrieved_context = None
        if should_trigger_rag(user_message):
            rag_results = rag_retrieve(user_message, self.vector_store)
            if rag_results:
                memory.update_retrieved_context(rag_results)
                retrieved_context = rag_results
                log_trace(trace, 'rag_recall', {'retrieved': True, 'count': len(rag_results)})
            else:
                memory.update_retrieved_context([])
                log_trace(trace, 'rag_recall', {'retrieved': False})
        else:
            memory.update_retrieved_context([])
            log_trace(trace, 'rag_skipped')

        # 5. PII filter (all layers)
        for key in ['messages', 'summary', 'facts', 'retrieved_context']:
            memory.state[key] = filter_pii_in_layer(memory.state[key], self.pii_mode)
        log_trace(trace, 'pii_filter', {'mode': self.pii_mode})

        # 6. Answer (dummy, replace with LLM call)
        answer = f"[Hybrid] Answer to: {user_message}"
        log_trace(trace, 'answer', {'answer': answer})

        # 7. END
        log_trace(trace, 'END')

        # Return answer and memory snapshot info
        return {
            'final_answer': answer,
            'memory_snapshot': memory.get_snapshot_info(),
            'checkpoint': memory.snapshot(),
            'trace': trace,
        }
