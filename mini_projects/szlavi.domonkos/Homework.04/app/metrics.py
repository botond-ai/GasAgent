"""AI Metrics Monitoring Module.

Follows SOLID principles:
- Single Responsibility: Each class tracks specific metrics
- Open/Closed: Easy to add new metric collectors without modifying existing code
- Liskov Substitution: All collectors implement MetricCollector interface
- Interface Segregation: Minimal, focused interfaces
- Dependency Inversion: Depends on abstractions, not concrete implementations
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import json
import os
from statistics import mean, median, quantiles

logger = logging.getLogger(__name__)


@dataclass
class APICallMetric:
    """Represents a single API call metric."""
    
    timestamp: datetime
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    operation_type: str  # "embedding" or "llm_completion"
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class MetricsSummary:
    """Summary of collected metrics."""
    
    total_inferences: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    latency_p95_ms: float
    latency_p50_ms: float
    latency_mean_ms: float
    error_rate: float
    total_errors: int
    agent_execution_latency_p95_ms: float
    agent_execution_latency_mean_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    by_operation: Dict[str, Dict] = field(default_factory=dict)
    by_model: Dict[str, Dict] = field(default_factory=dict)


class MetricCollector(ABC):
    """Abstract base class for metric collection strategies."""
    
    @abstractmethod
    def record_call(self, metric: APICallMetric) -> None:
        """Record a single API call metric."""
    
    @abstractmethod
    def get_summary(self) -> MetricsSummary:
        """Return aggregated metrics summary."""
    
    @abstractmethod
    def reset(self) -> None:
        """Clear all collected metrics."""
    
    @abstractmethod
    def export(self, filepath: str) -> None:
        """Export metrics to a file."""
    
    @abstractmethod
    def load(self, filepath: str) -> None:
        """Load metrics from a file."""


class InMemoryMetricsCollector(MetricCollector):
    """In-memory metrics collector for runtime monitoring."""
    
    def __init__(self) -> None:
        """Initialize the metrics collector."""
        self._metrics: List[APICallMetric] = []
        self._agent_latencies: List[float] = []
        self._start_time = datetime.now()
    
    def record_call(self, metric: APICallMetric) -> None:
        """Record a single API call metric.
        
        Args:
            metric: APICallMetric instance to record.
        """
        if metric.timestamp is None:
            metric.timestamp = datetime.now()
        self._metrics.append(metric)
        logger.debug(
            f"Recorded metric: {metric.operation_type} | "
            f"Tokens: {metric.tokens_in}in/{metric.tokens_out}out | "
            f"Latency: {metric.latency_ms:.2f}ms | "
            f"Cost: ${metric.cost_usd:.6f}"
        )
    
    def get_summary(self) -> MetricsSummary:
        """Calculate and return aggregated metrics summary.
        
        Returns:
            MetricsSummary with all aggregated metrics.
        """
        if not self._metrics:
            return MetricsSummary(
                total_inferences=0,
                total_tokens_in=0,
                total_tokens_out=0,
                total_cost_usd=0.0,
                latency_p95_ms=0.0,
                latency_p50_ms=0.0,
                latency_mean_ms=0.0,
                error_rate=0.0,
                total_errors=0,
                agent_execution_latency_p95_ms=0.0,
                agent_execution_latency_mean_ms=0.0,
            )
        
        # Basic aggregations
        total_inferences = len(self._metrics)
        total_tokens_in = sum(m.tokens_in for m in self._metrics)
        total_tokens_out = sum(m.tokens_out for m in self._metrics)
        total_cost_usd = sum(m.cost_usd for m in self._metrics)
        
        # Latency percentiles
        latencies = [m.latency_ms for m in self._metrics]
        latency_p95_ms = self._calculate_percentile(latencies, 0.95)
        latency_p50_ms = median(latencies) if latencies else 0.0
        latency_mean_ms = mean(latencies) if latencies else 0.0
        
        # Calculate error rate
        failed_calls = sum(1 for m in self._metrics if not m.success)
        error_rate = (failed_calls / len(self._metrics) * 100) if self._metrics else 0.0
        
        # Calculate agent execution latency statistics
        agent_exec_p95_ms = (
            self._calculate_percentile(self._agent_latencies, 0.95)
            if self._agent_latencies
            else 0.0
        )
        agent_exec_mean_ms = (
            mean(self._agent_latencies)
            if self._agent_latencies
            else 0.0
        )
        
        # Breakdown by operation type
        by_operation = self._aggregate_by_field("operation_type")
        
        # Breakdown by model
        by_model = self._aggregate_by_field("model")
        
        return MetricsSummary(
            total_inferences=total_inferences,
            total_tokens_in=total_tokens_in,
            total_tokens_out=total_tokens_out,
            total_cost_usd=total_cost_usd,
            latency_p95_ms=latency_p95_ms,
            latency_p50_ms=latency_p50_ms,
            latency_mean_ms=latency_mean_ms,
            error_rate=error_rate,
            total_errors=failed_calls,
            agent_execution_latency_p95_ms=agent_exec_p95_ms,
            agent_execution_latency_mean_ms=agent_exec_mean_ms,
            by_operation=by_operation,
            by_model=by_model,
        )
    
    def reset(self) -> None:
        """Clear all collected metrics."""
        self._metrics.clear()
        self._agent_latencies.clear()
        self._start_time = datetime.now()
        logger.info("Metrics collector reset.")
    
    def export(self, filepath: str) -> None:
        """Export metrics to JSON file.
        
        Args:
            filepath: Path to save metrics JSON file.
        """
        try:
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
            
            # Prepare data for JSON serialization
            metrics_data = {
                "timestamp": datetime.now().isoformat(),
                "total_calls": len(self._metrics),
                "calls": [
                    {
                        "timestamp": m.timestamp.isoformat(),
                        "model": m.model,
                        "tokens_in": m.tokens_in,
                        "tokens_out": m.tokens_out,
                        "latency_ms": m.latency_ms,
                        "cost_usd": m.cost_usd,
                        "operation_type": m.operation_type,
                        "success": m.success,
                        "error_message": m.error_message,
                    }
                    for m in self._metrics
                ],
                "summary": self._summary_to_dict(self.get_summary()),
            }
            
            with open(filepath, "w") as f:
                json.dump(metrics_data, f, indent=2)
            
            logger.info(f"Metrics exported to {filepath}")
        except Exception as exc:
            logger.error(f"Failed to export metrics to {filepath}: {exc}")
    
    def load(self, filepath: str) -> None:
        """Load metrics from JSON file.
        
        Args:
            filepath: Path to metrics JSON file.
        """
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            self._metrics.clear()
            for call_data in data.get("calls", []):
                metric = APICallMetric(
                    timestamp=datetime.fromisoformat(call_data["timestamp"]),
                    model=call_data["model"],
                    tokens_in=call_data["tokens_in"],
                    tokens_out=call_data["tokens_out"],
                    latency_ms=call_data["latency_ms"],
                    cost_usd=call_data["cost_usd"],
                    operation_type=call_data["operation_type"],
                    success=call_data.get("success", True),
                    error_message=call_data.get("error_message"),
                )
                self._metrics.append(metric)
            
            logger.info(f"Loaded {len(self._metrics)} metrics from {filepath}")
        except Exception as exc:
            logger.error(f"Failed to load metrics from {filepath}: {exc}")
    
    def _aggregate_by_field(self, field_name: str) -> Dict[str, Dict]:
        """Aggregate metrics by a specific field.
        
        Args:
            field_name: Name of the field to aggregate by.
        
        Returns:
            Dictionary with aggregated values for each field value.
        """
        aggregates = {}
        
        for metric in self._metrics:
            field_value = getattr(metric, field_name)
            
            if field_value not in aggregates:
                aggregates[field_value] = {
                    "count": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_usd": 0.0,
                    "latencies": [],
                }
            
            agg = aggregates[field_value]
            agg["count"] += 1
            agg["tokens_in"] += metric.tokens_in
            agg["tokens_out"] += metric.tokens_out
            agg["cost_usd"] += metric.cost_usd
            agg["latencies"].append(metric.latency_ms)
        
        # Calculate percentiles for each group
        for field_value, agg in aggregates.items():
            latencies = agg.pop("latencies")
            if latencies:
                agg["latency_p95_ms"] = self._calculate_percentile(latencies, 0.95)
                agg["latency_p50_ms"] = median(latencies)
                agg["latency_mean_ms"] = mean(latencies)
            else:
                agg["latency_p95_ms"] = 0.0
                agg["latency_p50_ms"] = 0.0
                agg["latency_mean_ms"] = 0.0
        
        return aggregates
    
    @staticmethod
    def _calculate_percentile(values: List[float], percentile: float) -> float:
        """Calculate percentile of values.
        
        Args:
            values: List of numeric values.
            percentile: Percentile to calculate (0.0-1.0).
        
        Returns:
            Percentile value.
        """
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        
        if len(sorted_values) == 1:
            return sorted_values[0]
        
        # Use quantiles from statistics module
        try:
            result = quantiles(sorted_values, n=100)
            idx = int(percentile * 100) - 1
            return result[max(0, min(idx, len(result) - 1))]
        except Exception:
            # Fallback for small datasets
            idx = int(percentile * (len(sorted_values) - 1))
            return sorted_values[idx]
    
    @staticmethod
    def _summary_to_dict(summary: MetricsSummary) -> Dict:
        """Convert MetricsSummary to dictionary.
        
        Args:
            summary: MetricsSummary instance.
        
        Returns:
            Dictionary representation.
        """
        return {
            "total_inferences": summary.total_inferences,
            "total_tokens_in": summary.total_tokens_in,
            "total_tokens_out": summary.total_tokens_out,
            "total_cost_usd": round(summary.total_cost_usd, 6),
            "latency_p95_ms": round(summary.latency_p95_ms, 2),
            "latency_p50_ms": round(summary.latency_p50_ms, 2),
            "latency_mean_ms": round(summary.latency_mean_ms, 2),
            "by_operation": summary.by_operation,
            "by_model": summary.by_model,
        }


class OpenAIPricingCalculator:
    """Calculate costs for OpenAI API calls.
    
    Uses current OpenAI pricing as of January 2026.
    Update prices here when OpenAI changes their pricing.
    """
    
    # Embedding model prices (per 1M tokens)
    EMBEDDING_PRICES = {
        "text-embedding-3-small": {"input": 0.02, "output": 0.02},
        "text-embedding-3-large": {"input": 0.13, "output": 0.13},
    }
    
    # LLM model prices (per 1M tokens)
    LLM_PRICES = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.5, "output": 10.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    }
    
    @classmethod
    def calculate_cost(
        cls,
        tokens_in: int,
        tokens_out: int,
        model: str,
        operation_type: str = "embedding",
    ) -> float:
        """Calculate cost for an API call.
        
        Args:
            tokens_in: Number of input tokens.
            tokens_out: Number of output tokens.
            model: Model name.
            operation_type: Either "embedding" or "llm_completion".
        
        Returns:
            Cost in USD.
        """
        prices = (
            cls.EMBEDDING_PRICES
            if operation_type == "embedding"
            else cls.LLM_PRICES
        )
        
        # Get price per 1M tokens, default to 0 if model unknown
        price_info = prices.get(model, {"input": 0.0, "output": 0.0})
        
        # Calculate cost: (tokens / 1_000_000) * price_per_million
        input_cost = (tokens_in / 1_000_000) * price_info["input"]
        output_cost = (tokens_out / 1_000_000) * price_info["output"]
        
        return input_cost + output_cost
    
    @classmethod
    def get_supported_models(cls) -> Dict[str, str]:
        """Get all supported models grouped by type.
        
        Returns:
            Dictionary with model names grouped by operation type.
        """
        return {
            "embedding": list(cls.EMBEDDING_PRICES.keys()),
            "llm": list(cls.LLM_PRICES.keys()),
        }


class MetricsMiddleware:
    """Middleware for wrapping OpenAI API calls with metrics collection.
    
    This decorator-like class can wrap API calls to automatically track metrics.
    """
    
    def __init__(self, collector: MetricCollector) -> None:
        """Initialize the middleware.
        
        Args:
            collector: MetricCollector instance to record metrics.
        """
        self.collector = collector
    
    def record_embedding_call(
        self,
        model: str,
        tokens_in: int,
        latency_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Record an embedding API call.
        
        Args:
            model: Model name.
            tokens_in: Number of input tokens.
            latency_ms: Request latency in milliseconds.
            success: Whether the call succeeded.
            error_message: Error message if call failed.
        """
        # Embeddings don't have output tokens in the same way
        tokens_out = 0
        cost = OpenAIPricingCalculator.calculate_cost(
            tokens_in, tokens_out, model, "embedding"
        )
        
        metric = APICallMetric(
            timestamp=datetime.now(),
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            operation_type="embedding",
            success=success,
            error_message=error_message,
        )
        
        self.collector.record_call(metric)
    
    def record_llm_call(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Record an LLM completion API call.
        
        Args:
            model: Model name.
            tokens_in: Number of input tokens.
            tokens_out: Number of output tokens.
            latency_ms: Request latency in milliseconds.
            success: Whether the call succeeded.
            error_message: Error message if call failed.
        """
        cost = OpenAIPricingCalculator.calculate_cost(
            tokens_in, tokens_out, model, "llm_completion"
        )
        
        metric = APICallMetric(
            timestamp=datetime.now(),
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            operation_type="llm_completion",
            success=success,
            error_message=error_message,
        )
        
        self.collector.record_call(metric)
    
    def record_vector_db_load(
        self,
        documents_loaded: int,
        latency_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Record a vector database load/retrieval operation.
        
        Args:
            documents_loaded: Number of documents retrieved from vector DB.
            latency_ms: Operation latency in milliseconds.
            success: Whether the operation succeeded.
            error_message: Error message if operation failed.
        """
        # Vector DB operations don't have tokens or cost
        # Store the document count in tokens_in field for tracking
        metric = APICallMetric(
            timestamp=datetime.now(),
            model="vector_db",
            tokens_in=documents_loaded,  # Store document count here
            tokens_out=0,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Vector DB queries are not billed by tokens
            operation_type="vector_db_load",
            success=success,
            error_message=error_message,
        )
        
        self.collector.record_call(metric)
    
    def record_agent_execution(
        self,
        latency_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Record an agent execution latency metric.
        
        Args:
            latency_ms: Total execution time in milliseconds.
            success: Whether the execution succeeded.
            error_message: Error message if execution failed.
        """
        # Store agent latency for separate tracking
        if isinstance(self.collector, InMemoryMetricsCollector):
            self.collector._agent_latencies.append(latency_ms)
        
        # Also record as a metric for audit trail
        metric = APICallMetric(
            timestamp=datetime.now(),
            model="agent",
            tokens_in=0,
            tokens_out=0,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Agent execution itself is free
            operation_type="agent_execution",
            success=success,
            error_message=error_message,
        )
        
        self.collector.record_call(metric)


def create_metrics_collector() -> MetricCollector:
    """Factory function to create a metrics collector.
    
    Returns:
        InMemoryMetricsCollector instance.
    """
    return InMemoryMetricsCollector()
