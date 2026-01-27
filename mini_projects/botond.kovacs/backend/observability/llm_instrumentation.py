import time
from typing import Any, List, Optional
from observability.metrics import (
    llm_inference_count,
    llm_inference_latency_seconds,
    llm_inference_token_input_total,
    llm_inference_token_output_total,
    llm_cost_total_usd,
    model_fallback_count,
    max_retries_exceeded_count,
    record_error,
    record_llm_usage
)
from observability.prompt_lineage import get_prompt_tracker

async def instrumented_llm_call(llm, messages, model: str, agent_execution_id: Optional[str] = None):
    """Wrapper, ami automatikusan rögzíti az LLM metrikákat és prompt lineage-t."""
    start_time = time.time()
    try:
        # Prompt lineage követés
        if agent_execution_id:
            tracker = get_prompt_tracker()
            tracker.track_prompt(
                messages=messages,
                model_name=model,
                agent_execution_id=agent_execution_id
            )
        # Tényleges LLM hívás
        response = await llm.ainvoke(messages)
        duration = time.time() - start_time
        prompt_tokens = response.usage_metadata.get('input_tokens', 0)
        completion_tokens = response.usage_metadata.get('output_tokens', 0)
        # Metrikák rögzítése
        record_llm_usage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_seconds=duration
        )
        return response
    except Exception as e:
        duration = time.time() - start_time
        record_error(error_type="llm_error", node="llm_call")
        llm_inference_latency_seconds.labels(model=model).observe(duration)
        raise

async def instrumented_llm_call_with_fallback(
    primary_llm,
    fallback_llm,
    messages,
    primary_model: str,
    fallback_model: str,
    max_retries: int = 3,
    agent_execution_id: Optional[str] = None
):
    """
    Instrumentált LLM hívás automatikus fallback-kel másodlagos modellre.
    Model fallback útvonalakat követ a model_fallback_count metrikán keresztül.
    """
    # Próbáld az elsődleges modellt először
    for attempt in range(max_retries):
        try:
            return await instrumented_llm_call(
                llm=primary_llm,
                messages=messages,
                model=primary_model,
                agent_execution_id=agent_execution_id
            )
        except Exception:
            if attempt == max_retries - 1:
                break
    # Fallback követése metrikával
    model_fallback_count.labels(
        from_model=primary_model,
        to_model=fallback_model
    ).inc()
    # Próbáld a fallback modellt
    for attempt in range(max_retries):
        try:
            return await instrumented_llm_call(
                llm=fallback_llm,
                messages=messages,
                model=fallback_model,
                agent_execution_id=agent_execution_id
            )
        except Exception:
            if attempt == max_retries - 1:
                max_retries_exceeded_count.inc()
                record_error(error_type="llm_error", node="llm_fallback")
                raise
