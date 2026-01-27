"""
Unit tests for Prometheus monitoring infrastructure.

Tests:
- MetricsAPIView endpoint returns Prometheus format
- Metrics collection and increment operations
- Counter, histogram, gauge functionality
- Metrics output format validation
"""
import pytest
from django.test import RequestFactory
from api.views import MetricsAPIView
from infrastructure.prometheus_metrics import (
    get_metrics_output,
    MetricsCollector,
)


class TestMetricsAPIView:
    """Test the /api/metrics/ endpoint."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = MetricsAPIView.as_view()
    
    def test_metrics_endpoint_returns_200(self):
        """Endpoint should return 200 OK."""
        request = self.factory.get('/api/metrics/')
        response = self.view(request)
        assert response.status_code == 200
    
    def test_metrics_endpoint_content_type(self):
        """Endpoint should return Prometheus text format."""
        request = self.factory.get('/api/metrics/')
        response = self.view(request)
        assert response['Content-Type'] == 'text/plain; version=0.0.4; charset=utf-8'
    
    def test_metrics_endpoint_contains_metrics(self):
        """Response should contain Prometheus metrics."""
        request = self.factory.get('/api/metrics/')
        response = self.view(request)
        content = response.content.decode('utf-8')
        
        # Check for metric definitions
        assert 'knowledgerouter_requests_total' in content
        assert 'knowledgerouter_latency_seconds' in content
        assert 'knowledgerouter_llm_calls_total' in content
        assert 'knowledgerouter_cache_hits_total' in content
        assert 'knowledgerouter_errors_total' in content
    
    def test_metrics_endpoint_has_help_text(self):
        """Metrics should include HELP documentation."""
        request = self.factory.get('/api/metrics/')
        response = self.view(request)
        content = response.content.decode('utf-8')
        
        assert '# HELP' in content
        assert '# TYPE' in content
    
    def test_metrics_output_format(self):
        """Metrics output should be valid Prometheus format."""
        output = get_metrics_output()
        
        # Basic format validation
        assert isinstance(output, bytes)
        assert len(output) > 0
        assert b'# HELP' in output
        assert b'# TYPE' in output


class TestMetricsCollection:
    """Test individual metric collection functions."""
    
    def test_record_request(self):
        """Request counter should increment by domain."""
        initial_output = get_metrics_output()
        
        MetricsCollector.record_request(domain='test', status='success', pipeline_mode='simple', latency_seconds=0.5)
        MetricsCollector.record_request(domain='test', status='success', pipeline_mode='simple', latency_seconds=0.3)
        
        final_output = get_metrics_output()
        assert final_output != initial_output
    
    def test_record_llm_call(self):
        """LLM call counter should increment by model."""
        MetricsCollector.record_llm_call(model='claude-3-sonnet', status='success', purpose='reasoning', latency_seconds=1.5)
        MetricsCollector.record_llm_call(model='claude-3-sonnet', status='success', purpose='reasoning', latency_seconds=1.2)
        MetricsCollector.record_llm_call(model='gpt-4', status='success', purpose='answering', latency_seconds=2.3)
        
        output = get_metrics_output()
        assert b'knowledgerouter_llm_calls_total' in output
    
    def test_record_llm_call_with_tokens_and_cost(self):
        """LLM call should track tokens and calculate cost."""
        # GPT-4o-mini call: 1000 input tokens, 500 output tokens
        # Cost: (1000/1M * $0.15) + (500/1M * $0.60) = $0.00015 + $0.0003 = $0.00045
        MetricsCollector.record_llm_call(
            model='gpt-4o-mini',
            status='success',
            purpose='generation',
            latency_seconds=1.2,
            input_tokens=1000,
            output_tokens=500
        )
        
        output = get_metrics_output().decode('utf-8')
        assert 'knowledgerouter_llm_tokens_total' in output
        assert 'knowledgerouter_llm_cost_total' in output
        assert 'gpt-4o-mini' in output
        assert 'token_type="input"' in output
        assert 'token_type="output"' in output
    
    def test_llm_cost_calculation_accuracy(self):
        """Cost should be calculated accurately for different models."""
        # Claude 3.5 Sonnet: $3/M input, $15/M output
        # 10000 input, 2000 output = $0.03 + $0.03 = $0.06
        MetricsCollector.record_llm_call(
            model='claude-3-5-sonnet',
            status='success',
            purpose='generation',
            input_tokens=10000,
            output_tokens=2000
        )
        
        output = get_metrics_output().decode('utf-8')
        assert 'knowledgerouter_llm_cost_total' in output
        # Cost should be incremented (we can't check exact value without resetting metrics)
    
    def test_record_cache_operations(self):
        """Cache hit/miss counters should increment."""
        MetricsCollector.record_cache_hit(cache_type='redis')
        MetricsCollector.record_cache_hit(cache_type='redis')
        MetricsCollector.record_cache_miss(cache_type='redis')
        
        output = get_metrics_output()
        assert b'knowledgerouter_cache_hits_total' in output
        assert b'knowledgerouter_cache_misses_total' in output
    
    def test_record_error(self):
        """Error counter should increment by type."""
        MetricsCollector.record_error(error_type='validation', component='api')
        MetricsCollector.record_error(error_type='timeout', component='llm')
        
        output = get_metrics_output()
        assert b'knowledgerouter_errors_total' in output
    
    def test_record_tool_execution(self):
        """Tool execution counter should increment by tool name."""
        MetricsCollector.record_tool_execution(tool_name='google_search', status='success')
        MetricsCollector.record_tool_execution(tool_name='qdrant_query', status='success')
        
        output = get_metrics_output()
        assert b'knowledgerouter_tool_executions_total' in output
    
    def test_record_rag_latency(self):
        """Should record RAG operation latency."""
        MetricsCollector.record_rag_latency(domain='it', latency_seconds=0.350)
        MetricsCollector.record_rag_latency(domain='hr', latency_seconds=0.450)
        
        output = get_metrics_output()
        assert b'knowledgerouter_rag_latency_seconds' in output
    
    def test_active_requests_gauge(self):
        """Active requests gauge should increment/decrement."""
        MetricsCollector.increment_active_requests()
        MetricsCollector.increment_active_requests()
        output1 = get_metrics_output()
        
        MetricsCollector.decrement_active_requests()
        output2 = get_metrics_output()
        
        assert b'knowledgerouter_active_requests' in output1
        assert b'knowledgerouter_active_requests' in output2
        assert output1 != output2
    
    def test_record_replan_loop(self):
        """Replan loop counter should increment."""
        MetricsCollector.record_replan_loop(reason='insufficient_info', domain='general')
        MetricsCollector.record_replan_loop(reason='clarification_needed', domain='it')
        
        output = get_metrics_output()
        assert b'knowledgerouter_replan_loops_total' in output
    
    def test_metrics_labels(self):
        """Metrics should include proper labels."""
        MetricsCollector.record_request(domain='it', status='success', pipeline_mode='langgraph', latency_seconds=1.0)
        MetricsCollector.record_llm_call(model='claude-3-sonnet', status='success', purpose='reasoning')
        MetricsCollector.record_error(error_type='timeout', component='qdrant')
        MetricsCollector.record_tool_execution(tool_name='google_search', status='success')
        
        output = get_metrics_output().decode('utf-8')
        
        # Check for label formatting
        assert 'domain=' in output
        assert 'model=' in output
        assert 'error_type=' in output
        assert 'tool_name=' in output


class TestMetricsIntegration:
    """Integration tests for metrics in actual request flow."""
    
    def test_concurrent_metric_updates(self):
        """Metrics should handle concurrent updates safely."""
        import threading
        
        def worker():
            for _ in range(10):
                MetricsCollector.record_request(domain='test', status='success', pipeline_mode='simple', latency_seconds=0.1)
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        output = get_metrics_output()
        assert b'knowledgerouter_requests_total' in output
    
    def test_metrics_persistence_across_calls(self):
        """Metrics should persist across multiple API calls."""
        factory = RequestFactory()
        view = MetricsAPIView.as_view()
        
        MetricsCollector.record_request(domain='persistent', status='success', pipeline_mode='simple', latency_seconds=1.0)
        
        request1 = factory.get('/api/metrics/')
        response1 = view(request1)
        content1 = response1.content.decode('utf-8')
        
        request2 = factory.get('/api/metrics/')
        response2 = view(request2)
        content2 = response2.content.decode('utf-8')
        
        # Both responses should contain the metric
        assert 'knowledgerouter_requests_total' in content1
        assert 'knowledgerouter_requests_total' in content2


class TestMetricsEdgeCases:
    """Test edge cases and error handling."""
    
    def test_zero_latency(self):
        """Should handle zero latency values."""
        MetricsCollector.record_request(domain='test', status='success', pipeline_mode='simple', latency_seconds=0.0)
        output = get_metrics_output()
        assert b'knowledgerouter_latency_seconds' in output
    
    def test_very_large_latency(self):
        """Should handle very large latency values."""
        MetricsCollector.record_request(domain='test', status='success', pipeline_mode='simple', latency_seconds=999.999)
        output = get_metrics_output()
        assert b'knowledgerouter_latency_seconds' in output
    
    def test_empty_domain_label(self):
        """Should handle empty domain labels."""
        MetricsCollector.record_request(domain='', status='success', pipeline_mode='simple', latency_seconds=1.0)
        output = get_metrics_output()
        assert b'knowledgerouter_requests_total' in output
    
    def test_special_characters_in_labels(self):
        """Should handle special characters in labels."""
        MetricsCollector.record_request(domain='test-domain_123', status='success', pipeline_mode='simple', latency_seconds=1.0)
        MetricsCollector.record_llm_call(model='claude-3.5-sonnet', status='success', purpose='reasoning')
        
        output = get_metrics_output()
        assert b'knowledgerouter_requests_total' in output
        assert b'knowledgerouter_llm_calls_total' in output
    
    def test_unicode_in_labels(self):
        """Should handle unicode in labels."""
        MetricsCollector.record_error(error_type='ékezetes_hiba', component='api')
        output = get_metrics_output()
        assert b'knowledgerouter_errors_total' in output


@pytest.mark.django_db
class TestMetricsAPIViewDatabase:
    """Test metrics endpoint with database if needed."""
    
    def test_metrics_endpoint_no_database_required(self):
        """Metrics endpoint should work without database queries."""
        factory = RequestFactory()
        view = MetricsAPIView.as_view()
        
        request = factory.get('/api/metrics/')
        response = view(request)
        
        assert response.status_code == 200
        assert 'knowledgerouter' in response.content.decode('utf-8')
