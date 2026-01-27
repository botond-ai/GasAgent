import os
import time
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# Registry létrehozása
registry = CollectorRegistry()

def get_environment() -> str:
    return os.environ.get("ENVIRONMENT", "dev")

def get_version() -> str:
    return os.environ.get("APP_VERSION", "1.0.0")

# --- LLM METRIKÁK ---
llm_inference_count = Counter(
    name='llm_inference_count',
    documentation='Összes LLM inferencia hívás',
    labelnames=['model'],
    registry=registry
)

llm_inference_latency_seconds = Histogram(
    name='llm_inference_latency_seconds',
    documentation='LLM inferencia hívások késleltetése másodpercben',
    labelnames=['model'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry
)

llm_inference_token_input_total = Counter(
    name='llm_inference_token_input_total',
    documentation='Összes bemeneti token LLM által feldolgozva',
    labelnames=['model'],
    registry=registry
)

llm_inference_token_output_total = Counter(
    name='llm_inference_token_output_total',
    documentation='Összes kimeneti token LLM által generálva',
    labelnames=['model'],
    registry=registry
)

llm_cost_total_usd = Counter(
    name='llm_cost_total_usd',
    documentation='Teljes költség USD-ben LLM inferenciára',
    labelnames=['model'],
    registry=registry
)

# --- AGENT METRIKÁK ---

agent_execution_count = Counter(
    name='agent_execution_count',
    documentation='Agent végrehajtások teljes száma',
    registry=registry
)

agent_execution_latency_seconds = Histogram(
    name='agent_execution_latency_seconds',
    documentation='Agent végrehajtás késleltetése másodpercben',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
    registry=registry
)

node_execution_latency_seconds = Histogram(
    name='node_execution_latency_seconds',
    documentation='Egyedi node végrehajtás késleltetése másodpercben',
    labelnames=['node'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

tool_invocation_count = Counter(
    name='tool_invocation_count',
    documentation='Eszköz hívások teljes száma',
    labelnames=['tool'],
    registry=registry
)

agent_tool_duration_seconds = Histogram(
    name='agent_tool_duration_seconds',
    documentation='Eszköz hívások időtartama másodpercben',
    labelnames=['tool'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
    registry=registry
)

# --- HIBA ÉS FALLBACK METRIKÁK ---
agent_errors_total = Counter(
    name='agent_errors_total',
    documentation='Agent végrehajtás hibák teljes száma',
    labelnames=['error_type', 'node', 'environment'],
    registry=registry
)

model_fallback_count = Counter(
    name='model_fallback_count',
    documentation='Model fallback előfordulások teljes száma',
    labelnames=['from_model', 'to_model'],
    registry=registry
)

max_retries_exceeded_count = Counter(
    name='max_retries_exceeded_count',
    documentation='Maximális újrapróbálkozások túllépésének száma',
    registry=registry
)

# --- RAG METRIKÁK ---
agent_rag_retrievals_total = Counter(
    name='agent_rag_retrievals_total',
    documentation='RAG lekérések teljes száma',
    labelnames=['status', 'environment'],
    registry=registry
)

agent_rag_chunks_retrieved = Histogram(
    name='agent_rag_chunks_retrieved',
    documentation='Lekért chunk-ok száma RAG lekérdezésenként',
    labelnames=['environment'],
    buckets=[0, 1, 2, 5, 10, 20, 50],
    registry=registry
)

agent_rag_duration_seconds = Histogram(
    name='agent_rag_duration_seconds',
    documentation='RAG lekérési késleltetés másodpercben',
    labelnames=['environment'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
    registry=registry
)

rag_chunk_retrieval_count = Counter(
    name='rag_chunk_retrieval_count',
    documentation='RAG chunk lekérések teljes száma',
    registry=registry
)

rag_retrieved_chunk_relevance_score_avg = Gauge(
    name='rag_retrieved_chunk_relevance_score_avg',
    documentation='Lekért chunk-ok átlagos relevancia pontszáma',
    registry=registry
)

vector_db_query_latency_seconds = Histogram(
    name='vector_db_query_latency_seconds',
    documentation='Vektor adatbázis lekérdezések késleltetése másodpercben',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
    registry=registry
)

embedding_generation_count = Counter(
    name='embedding_generation_count',
    documentation='Embedding generálások teljes száma',
    registry=registry
)

# --- KONTEXTUS RESET METRIKA ---
context_reset_count = Counter(
    name='context_reset_count',
    documentation='Kontextus visszaállítások teljes száma',
    labelnames=['user_id'],
    registry=registry
)

# --- COST ESTIMATION ---
def _estimate_llm_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    PRICING = {
        "gpt-4-turbo-preview": (0.01, 0.03),
        "gpt-4": (0.03, 0.06),
        "gpt-4.1": (0.03, 0.06),
        "gpt-3.5-turbo": (0.0015, 0.002),
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
    }
    input_price, output_price = PRICING.get(model, PRICING["gpt-4"])
    cost = (prompt_tokens / 1000.0 * input_price) + (completion_tokens / 1000.0 * output_price)
    return cost

# --- CONTEXT MANAGERS ---
@contextmanager
def record_node_duration(node_name: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        node_execution_latency_seconds.labels(node=node_name).observe(duration)

@contextmanager
def record_tool_call(tool_name: str):
    start_time = time.time()
    try:
        yield
        tool_invocation_count.labels(tool=tool_name).inc()
    except Exception:
        tool_invocation_count.labels(tool=tool_name).inc()
        raise
    finally:
        duration = time.time() - start_time
        agent_tool_duration_seconds.labels(tool=tool_name).observe(duration)

@contextmanager
def record_rag_retrieval(num_chunks: int = 0, relevance_scores: Optional[List[float]] = None):
    start_time = time.time()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        agent_rag_retrievals_total.labels(status=status, environment=get_environment()).inc()
        rag_chunk_retrieval_count.inc()
        agent_rag_chunks_retrieved.labels(environment=get_environment()).observe(num_chunks)
        agent_rag_duration_seconds.labels(environment=get_environment()).observe(duration)
        vector_db_query_latency_seconds.observe(duration)
        if relevance_scores:
            avg_score = sum(relevance_scores) / len(relevance_scores)
            rag_retrieved_chunk_relevance_score_avg.set(avg_score)

def record_error(error_type: str, node: str = "unknown"):
    agent_errors_total.labels(
        error_type=error_type,
        node=node,
        environment=get_environment()
    ).inc()

def record_llm_usage(model: str, prompt_tokens: int, completion_tokens: int, duration_seconds: float):
    llm_inference_count.labels(model=model).inc()
    llm_inference_token_input_total.labels(model=model).inc(prompt_tokens)
    llm_inference_token_output_total.labels(model=model).inc(completion_tokens)
    llm_inference_latency_seconds.labels(model=model).observe(duration_seconds)
    cost_usd = _estimate_llm_cost(model, prompt_tokens, completion_tokens)
    llm_cost_total_usd.labels(model=model).inc(cost_usd)

def init_metrics(environment: str = "dev", version: str = "1.0.0"):
    os.environ["ENVIRONMENT"] = environment
    os.environ["APP_VERSION"] = version
