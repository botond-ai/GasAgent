"""Tests for the AI metrics monitoring module.

Tests cover:
- APICallMetric creation and validation
- MetricCollector interface and implementations
- Cost calculations via OpenAIPricingCalculator
- Metrics aggregation and percentile calculations
- Import/export functionality
- MetricsMiddleware recording
"""
import json
import os
import tempfile
from datetime import datetime

import pytest

from app.metrics import (
    APICallMetric,
    InMemoryMetricsCollector,
    MetricsMiddleware,
    OpenAIPricingCalculator,
    MetricCollector,
    MetricsSummary,
)


class TestAPICallMetric:
    """Tests for APICallMetric dataclass."""
    
    def test_metric_creation(self):
        """Test creating a valid metric."""
        now = datetime.now()
        metric = APICallMetric(
            timestamp=now,
            model="gpt-4o-mini",
            tokens_in=100,
            tokens_out=50,
            latency_ms=250.5,
            cost_usd=0.0005,
            operation_type="llm_completion",
        )
        
        assert metric.timestamp == now
        assert metric.model == "gpt-4o-mini"
        assert metric.tokens_in == 100
        assert metric.tokens_out == 50
        assert metric.latency_ms == 250.5
        assert metric.cost_usd == 0.0005
        assert metric.operation_type == "llm_completion"
        assert metric.success is True
        assert metric.error_message is None
    
    def test_metric_with_error(self):
        """Test creating a failed metric."""
        metric = APICallMetric(
            timestamp=datetime.now(),
            model="text-embedding-3-small",
            tokens_in=50,
            tokens_out=0,
            latency_ms=100.0,
            cost_usd=0.0,
            operation_type="embedding",
            success=False,
            error_message="API rate limit exceeded",
        )
        
        assert metric.success is False
        assert metric.error_message == "API rate limit exceeded"


class TestOpenAIPricingCalculator:
    """Tests for cost calculation."""
    
    def test_embedding_cost_small_model(self):
        """Test cost calculation for embedding with small model."""
        # text-embedding-3-small: $0.02 per 1M tokens (both input and output)
        cost = OpenAIPricingCalculator.calculate_cost(
            tokens_in=1_000_000,
            tokens_out=0,
            model="text-embedding-3-small",
            operation_type="embedding",
        )
        assert cost == pytest.approx(0.02, abs=0.0001)
    
    def test_embedding_cost_large_model(self):
        """Test cost calculation for embedding with large model."""
        # text-embedding-3-large: $0.13 per 1M tokens
        cost = OpenAIPricingCalculator.calculate_cost(
            tokens_in=1_000_000,
            tokens_out=0,
            model="text-embedding-3-large",
            operation_type="embedding",
        )
        assert cost == pytest.approx(0.13, abs=0.0001)
    
    def test_llm_cost_gpt4o_mini(self):
        """Test cost calculation for GPT-4o-mini."""
        # gpt-4o-mini: $0.15 in, $0.60 out per 1M tokens
        cost = OpenAIPricingCalculator.calculate_cost(
            tokens_in=1_000_000,
            tokens_out=1_000_000,
            model="gpt-4o-mini",
            operation_type="llm_completion",
        )
        expected = 0.15 + 0.60  # $0.75
        assert cost == pytest.approx(expected, abs=0.0001)
    
    def test_llm_cost_unknown_model(self):
        """Test cost calculation for unknown model defaults to $0."""
        cost = OpenAIPricingCalculator.calculate_cost(
            tokens_in=1_000_000,
            tokens_out=1_000_000,
            model="unknown-model",
            operation_type="llm_completion",
        )
        assert cost == 0.0
    
    def test_partial_tokens(self):
        """Test cost calculation with partial token counts."""
        # 500K input tokens at $0.15 per 1M = $0.075
        cost = OpenAIPricingCalculator.calculate_cost(
            tokens_in=500_000,
            tokens_out=250_000,
            model="gpt-4o-mini",
            operation_type="llm_completion",
        )
        expected = (500_000 / 1_000_000) * 0.15 + (250_000 / 1_000_000) * 0.60
        assert cost == pytest.approx(expected, abs=0.0001)
    
    def test_supported_models(self):
        """Test getting list of supported models."""
        models = OpenAIPricingCalculator.get_supported_models()
        
        assert "embedding" in models
        assert "llm" in models
        assert "text-embedding-3-small" in models["embedding"]
        assert "gpt-4o-mini" in models["llm"]


class TestInMemoryMetricsCollector:
    """Tests for InMemoryMetricsCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create a fresh collector for each test."""
        return InMemoryMetricsCollector()
    
    def test_record_single_metric(self, collector):
        """Test recording a single metric."""
        metric = APICallMetric(
            timestamp=datetime.now(),
            model="gpt-4o-mini",
            tokens_in=100,
            tokens_out=50,
            latency_ms=250.0,
            cost_usd=0.0005,
            operation_type="llm_completion",
        )
        
        collector.record_call(metric)
        summary = collector.get_summary()
        
        assert summary.total_inferences == 1
        assert summary.total_tokens_in == 100
        assert summary.total_tokens_out == 50
        assert summary.total_cost_usd == pytest.approx(0.0005, abs=0.00001)
    
    def test_record_multiple_metrics(self, collector):
        """Test recording and aggregating multiple metrics."""
        for i in range(5):
            metric = APICallMetric(
                timestamp=datetime.now(),
                model="text-embedding-3-small",
                tokens_in=100 * (i + 1),
                tokens_out=0,
                latency_ms=50.0 + i * 10,
                cost_usd=0.0002 * (i + 1),
                operation_type="embedding",
            )
            collector.record_call(metric)
        
        summary = collector.get_summary()
        
        assert summary.total_inferences == 5
        assert summary.total_tokens_in == 100 + 200 + 300 + 400 + 500  # 1500
        assert summary.total_cost_usd == pytest.approx(0.003, abs=0.00001)
        # latencies are: 50, 60, 70, 80, 90 -> mean = 70.0
        assert summary.latency_mean_ms == pytest.approx(70.0, abs=1.0)
    
    def test_percentile_calculation(self, collector):
        """Test latency percentile calculation."""
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        
        for latency in latencies:
            metric = APICallMetric(
                timestamp=datetime.now(),
                model="gpt-4o-mini",
                tokens_in=100,
                tokens_out=50,
                latency_ms=float(latency),
                cost_usd=0.001,
                operation_type="llm_completion",
            )
            collector.record_call(metric)
        
        summary = collector.get_summary()
        
        # p95 should be near 95 (or 90-100 range)
        assert summary.latency_p95_ms >= 80
        # p50 should be near 55 (median)
        assert 50 <= summary.latency_p50_ms <= 60
        # mean should be 55
        assert summary.latency_mean_ms == pytest.approx(55.0, abs=1.0)
    
    def test_aggregation_by_operation(self, collector):
        """Test aggregation by operation type."""
        # Add embedding operations
        for i in range(3):
            metric = APICallMetric(
                timestamp=datetime.now(),
                model="text-embedding-3-small",
                tokens_in=100,
                tokens_out=0,
                latency_ms=50.0,
                cost_usd=0.0002,
                operation_type="embedding",
            )
            collector.record_call(metric)
        
        # Add LLM operations
        for i in range(2):
            metric = APICallMetric(
                timestamp=datetime.now(),
                model="gpt-4o-mini",
                tokens_in=200,
                tokens_out=100,
                latency_ms=100.0,
                cost_usd=0.001,
                operation_type="llm_completion",
            )
            collector.record_call(metric)
        
        summary = collector.get_summary()
        
        assert "embedding" in summary.by_operation
        assert "llm_completion" in summary.by_operation
        assert summary.by_operation["embedding"]["count"] == 3
        assert summary.by_operation["llm_completion"]["count"] == 2
    
    def test_aggregation_by_model(self, collector):
        """Test aggregation by model."""
        # Add small embedding model calls
        for i in range(2):
            metric = APICallMetric(
                timestamp=datetime.now(),
                model="text-embedding-3-small",
                tokens_in=100,
                tokens_out=0,
                latency_ms=50.0,
                cost_usd=0.0002,
                operation_type="embedding",
            )
            collector.record_call(metric)
        
        # Add gpt-4o-mini calls
        for i in range(3):
            metric = APICallMetric(
                timestamp=datetime.now(),
                model="gpt-4o-mini",
                tokens_in=200,
                tokens_out=100,
                latency_ms=100.0,
                cost_usd=0.001,
                operation_type="llm_completion",
            )
            collector.record_call(metric)
        
        summary = collector.get_summary()
        
        assert "text-embedding-3-small" in summary.by_model
        assert "gpt-4o-mini" in summary.by_model
        assert summary.by_model["text-embedding-3-small"]["count"] == 2
        assert summary.by_model["gpt-4o-mini"]["count"] == 3
    
    def test_empty_summary(self, collector):
        """Test summary for empty collector."""
        summary = collector.get_summary()
        
        assert summary.total_inferences == 0
        assert summary.total_tokens_in == 0
        assert summary.total_tokens_out == 0
        assert summary.total_cost_usd == 0.0
        assert summary.latency_p95_ms == 0.0
    
    def test_reset(self, collector):
        """Test resetting the collector."""
        # Add some metrics
        metric = APICallMetric(
            timestamp=datetime.now(),
            model="gpt-4o-mini",
            tokens_in=100,
            tokens_out=50,
            latency_ms=250.0,
            cost_usd=0.001,
            operation_type="llm_completion",
        )
        collector.record_call(metric)
        
        # Verify metrics were recorded
        summary = collector.get_summary()
        assert summary.total_inferences == 1
        
        # Reset
        collector.reset()
        
        # Verify empty
        summary = collector.get_summary()
        assert summary.total_inferences == 0
        assert summary.total_cost_usd == 0.0
    
    def test_export_and_load(self, collector):
        """Test exporting and loading metrics."""
        # Add some metrics
        for i in range(3):
            metric = APICallMetric(
                timestamp=datetime.now(),
                model="gpt-4o-mini",
                tokens_in=100 * (i + 1),
                tokens_out=50 * (i + 1),
                latency_ms=250.0 + i * 50,
                cost_usd=0.001 * (i + 1),
                operation_type="llm_completion",
            )
            collector.record_call(metric)
        
        original_summary = collector.get_summary()
        
        # Export to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        
        try:
            collector.export(filepath)
            
            # Verify file exists and is valid JSON
            assert os.path.exists(filepath)
            with open(filepath, "r") as f:
                data = json.load(f)
            assert "calls" in data
            assert len(data["calls"]) == 3
            
            # Create new collector and load
            new_collector = InMemoryMetricsCollector()
            new_collector.load(filepath)
            loaded_summary = new_collector.get_summary()
            
            # Verify loaded data matches original
            assert loaded_summary.total_inferences == original_summary.total_inferences
            assert loaded_summary.total_tokens_in == original_summary.total_tokens_in
            assert loaded_summary.total_cost_usd == pytest.approx(
                original_summary.total_cost_usd, abs=0.00001
            )
        finally:
            # Cleanup
            if os.path.exists(filepath):
                os.remove(filepath)


class TestMetricsMiddleware:
    """Tests for MetricsMiddleware."""
    
    @pytest.fixture
    def collector_and_middleware(self):
        """Create collector and middleware."""
        collector = InMemoryMetricsCollector()
        middleware = MetricsMiddleware(collector)
        return collector, middleware
    
    def test_record_embedding_call(self, collector_and_middleware):
        """Test recording an embedding call."""
        collector, middleware = collector_and_middleware
        
        middleware.record_embedding_call(
            model="text-embedding-3-small",
            tokens_in=1000,
            latency_ms=50.0,
        )
        
        summary = collector.get_summary()
        assert summary.total_inferences == 1
        assert summary.total_tokens_in == 1000
        assert summary.total_tokens_out == 0
    
    def test_record_llm_call(self, collector_and_middleware):
        """Test recording an LLM call."""
        collector, middleware = collector_and_middleware
        
        middleware.record_llm_call(
            model="gpt-4o-mini",
            tokens_in=500,
            tokens_out=250,
            latency_ms=100.0,
        )
        
        summary = collector.get_summary()
        assert summary.total_inferences == 1
        assert summary.total_tokens_in == 500
        assert summary.total_tokens_out == 250
    
    def test_record_failed_call(self, collector_and_middleware):
        """Test recording a failed call."""
        collector, middleware = collector_and_middleware
        
        middleware.record_embedding_call(
            model="text-embedding-3-small",
            tokens_in=500,
            latency_ms=75.0,
            success=False,
            error_message="API timeout",
        )
        
        summary = collector.get_summary()
        assert summary.total_inferences == 1
        # Cost is calculated based on tokens even for failed calls
        # 500 tokens * $0.02 per 1M = $0.00001
        assert summary.total_cost_usd == pytest.approx(0.00001, abs=0.000001)
    
    def test_record_vector_db_load(self, collector_and_middleware):
        """Test recording a vector DB load operation."""
        collector, middleware = collector_and_middleware
        
        middleware.record_vector_db_load(
            documents_loaded=5,
            latency_ms=45.3,
        )
        
        summary = collector.get_summary()
        assert summary.total_inferences == 1
        # Vector DB operations have no cost
        assert summary.total_cost_usd == 0.0
        # Document count stored in tokens_in
        assert summary.total_tokens_in == 5
    
    def test_record_multiple_vector_db_loads(self, collector_and_middleware):
        """Test recording multiple vector DB operations."""
        collector, middleware = collector_and_middleware
        
        # Record multiple vector DB loads
        for i in range(3):
            middleware.record_vector_db_load(
                documents_loaded=10 + i,
                latency_ms=50.0 + i * 10,
            )
        
        summary = collector.get_summary()
        assert summary.total_inferences == 3
        # Total documents loaded: 10 + 11 + 12 = 33
        assert summary.total_tokens_in == 33
        # No cost for vector DB
        assert summary.total_cost_usd == 0.0
        assert "vector_db_load" in summary.by_operation
    
    def test_record_agent_execution(self):
        """Test recording agent execution latency."""
        collector = InMemoryMetricsCollector()
        middleware = MetricsMiddleware(collector)
        
        # Record agent execution
        middleware.record_agent_execution(
            latency_ms=1000.0,
            success=True,
        )
        
        summary = collector.get_summary()
        # Agent execution should be recorded as a metric
        assert "agent_execution" in summary.by_operation
        # Agent latency should be tracked separately
        assert summary.agent_execution_latency_mean_ms == 1000.0
        assert summary.agent_execution_latency_p95_ms == 1000.0
    
    def test_record_agent_execution_multiple(self):
        """Test recording multiple agent executions and calculating percentiles."""
        collector = InMemoryMetricsCollector()
        middleware = MetricsMiddleware(collector)
        
        # Record multiple agent executions with varying latencies
        latencies = [500.0, 750.0, 900.0, 1000.0, 1100.0, 1200.0, 1500.0]
        for latency in latencies:
            middleware.record_agent_execution(latency_ms=latency, success=True)
        
        summary = collector.get_summary()
        # Verify mean calculation (average of latencies)
        assert abs(summary.agent_execution_latency_mean_ms - 992.86) < 1.0
        # p95 should be close to 1500
        assert summary.agent_execution_latency_p95_ms > 1400
        # Verify operation type is recorded
        assert "agent_execution" in summary.by_operation
        assert summary.by_operation["agent_execution"]["count"] == 7
    
    def test_record_agent_execution_with_failure(self):
        """Test recording failed agent execution."""
        collector = InMemoryMetricsCollector()
        middleware = MetricsMiddleware(collector)
        
        middleware.record_agent_execution(
            latency_ms=500.0,
            success=False,
            error_message="Agent execution timeout",
        )
        
        summary = collector.get_summary()
        assert summary.agent_execution_latency_mean_ms == 500.0
        assert summary.error_rate == 100.0  # 1 error out of 1 call
        assert summary.total_errors == 1


class TestErrorRateMetrics:
    """Tests for error rate tracking functionality."""
    
    def test_error_rate_no_errors(self):
        """Test error rate calculation with no errors."""
        collector = InMemoryMetricsCollector()
        middleware = MetricsMiddleware(collector)
        
        # Record 5 successful calls
        for i in range(5):
            middleware.record_embedding_call(
                model="text-embedding-3-small",
                tokens_in=100,
                latency_ms=50.0,
                success=True,
            )
        
        summary = collector.get_summary()
        assert summary.error_rate == 0.0
        assert summary.total_errors == 0
        assert summary.total_inferences == 5
    
    def test_error_rate_all_errors(self):
        """Test error rate calculation with all errors."""
        collector = InMemoryMetricsCollector()
        middleware = MetricsMiddleware(collector)
        
        # Record 5 failed calls
        for i in range(5):
            middleware.record_embedding_call(
                model="text-embedding-3-small",
                tokens_in=100,
                latency_ms=50.0,
                success=False,
                error_message="API error",
            )
        
        summary = collector.get_summary()
        assert summary.error_rate == 100.0
        assert summary.total_errors == 5
        assert summary.total_inferences == 5
    
    def test_error_rate_mixed(self):
        """Test error rate calculation with mixed success/failure."""
        collector = InMemoryMetricsCollector()
        middleware = MetricsMiddleware(collector)
        
        # Record 7 successful calls
        for i in range(7):
            middleware.record_embedding_call(
                model="text-embedding-3-small",
                tokens_in=100,
                latency_ms=50.0,
                success=True,
            )
        
        # Record 3 failed calls
        for i in range(3):
            middleware.record_embedding_call(
                model="text-embedding-3-small",
                tokens_in=100,
                latency_ms=50.0,
                success=False,
                error_message="Timeout",
            )
        
        summary = collector.get_summary()
        # 3 errors out of 10 calls = 30%
        assert abs(summary.error_rate - 30.0) < 0.1
        assert summary.total_errors == 3
        assert summary.total_inferences == 10
    
    def test_error_rate_llm_and_embedding(self):
        """Test error rate across different operation types."""
        collector = InMemoryMetricsCollector()
        middleware = MetricsMiddleware(collector)
        
        # Record embeddings: 3 success, 1 failure
        for i in range(3):
            middleware.record_embedding_call(
                model="text-embedding-3-small",
                tokens_in=100,
                latency_ms=50.0,
                success=True,
            )
        middleware.record_embedding_call(
            model="text-embedding-3-small",
            tokens_in=100,
            latency_ms=50.0,
            success=False,
            error_message="Error",
        )
        
        # Record LLM calls: 4 success, 1 failure
        for i in range(4):
            middleware.record_llm_call(
                model="gpt-4o-mini",
                tokens_in=100,
                tokens_out=50,
                latency_ms=150.0,
                success=True,
            )
        middleware.record_llm_call(
            model="gpt-4o-mini",
            tokens_in=100,
            tokens_out=50,
            latency_ms=150.0,
            success=False,
            error_message="Rate limit",
        )
        
        summary = collector.get_summary()
        # 2 errors out of 9 calls = 22.22%
        assert abs(summary.error_rate - 22.22) < 0.1
        assert summary.total_errors == 2
        assert summary.total_inferences == 9


class TestMetricsSummary:
    """Tests for MetricsSummary dataclass."""
    
    def test_summary_creation(self):
        """Test creating a summary."""
        summary = MetricsSummary(
            total_inferences=100,
            total_tokens_in=10000,
            total_tokens_out=5000,
            total_cost_usd=0.50,
            latency_p95_ms=250.0,
            latency_p50_ms=150.0,
            latency_mean_ms=160.0,
            error_rate=5.0,
            total_errors=5,
            agent_execution_latency_p95_ms=2000.0,
            agent_execution_latency_mean_ms=1500.0,
        )
        
        assert summary.total_inferences == 100
        assert summary.total_tokens_in == 10000
        assert summary.total_tokens_out == 5000
        assert summary.total_cost_usd == 0.50
        assert summary.latency_p95_ms == 250.0
        assert summary.error_rate == 5.0
        assert summary.total_errors == 5
        assert summary.agent_execution_latency_p95_ms == 2000.0
        assert summary.agent_execution_latency_mean_ms == 1500.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
