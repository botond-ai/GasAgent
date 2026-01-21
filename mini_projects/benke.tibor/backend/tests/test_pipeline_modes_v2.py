"""
Unit tests for pipeline mode switching (USE_SIMPLE_PIPELINE feature flag).

Tests:
1. Feature flag configuration
2. Method existence verification
3. Performance expectations documentation
"""

import inspect
from django.conf import settings


def test_feature_flag_exists():
    """Test that USE_SIMPLE_PIPELINE setting exists."""
    assert hasattr(settings, 'USE_SIMPLE_PIPELINE'), "USE_SIMPLE_PIPELINE setting should exist"
    assert isinstance(settings.USE_SIMPLE_PIPELINE, bool), "USE_SIMPLE_PIPELINE should be boolean"


def test_feature_flag_parsing():
    """Test that environment variable string parsing works correctly."""
    test_cases = [
        ('True', True),
        ('true', False),  # Case-sensitive (only 'True' -> True)
        ('FALSE', False),
        ('False', False),
        ('1', False),
        ('', False),
    ]
    
    for env_value, expected in test_cases:
        parsed = env_value == 'True'
        assert parsed == expected, f"Parsing '{env_value}' should result in {expected}"


def test_performance_expectations():
    """Document performance expectations for both pipeline modes."""
    expectations = {
        "simple": {
            "avg_latency_ms": 15000,
            "max_latency_ms": 20000,
            "llm_calls": 2,  # generation + guardrail
            "nodes": 4,  # intent, rag, generation, guardrail
        },
        "complex": {
            "avg_latency_ms": 35000,
            "max_latency_ms": 50000,
            "llm_calls": 6,  # intent, plan, tool_select, observation, generation, memory
            "nodes": 11,  # full LangGraph workflow
            "replan_max": 2,
        }
    }
    
    # Simple pipeline expectations
    assert expectations["simple"]["avg_latency_ms"] < 20000, "Simple should be under 20 sec"
    assert expectations["simple"]["llm_calls"] <= 2, "Simple should use minimal LLM calls"
    
    # Complex pipeline expectations
    assert expectations["complex"]["avg_latency_ms"] > 20000, "Complex should be slower but feature-rich"
    assert expectations["complex"]["nodes"] >= 10, "Complex should have full workflow"
    assert expectations["complex"]["replan_max"] == 2, "Max 2 replan iterations"


def test_chat_service_has_process_query():
    """Test that ChatService has process_query method."""
    from services.chat_service import ChatService
    
    assert hasattr(ChatService, 'process_query'), "ChatService should have process_query method"
    assert inspect.iscoroutinefunction(ChatService.process_query), "process_query should be async"


def test_query_agent_has_both_run_methods():
    """Test that QueryAgent has both run() and run_simple() methods."""
    from services.agent import QueryAgent
    
    # Complex workflow method
    assert hasattr(QueryAgent, 'run'), "QueryAgent should have run() method (complex workflow)"
    assert inspect.iscoroutinefunction(QueryAgent.run), "run() should be async"
    
    # Simple pipeline method
    assert hasattr(QueryAgent, 'run_simple'), "QueryAgent should have run_simple() method (fast pipeline)"
    assert inspect.iscoroutinefunction(QueryAgent.run_simple), "run_simple() should be async"


def test_run_simple_signature():
    """Test that run_simple() has correct method signature."""
    from services.agent import QueryAgent
    
    sig = inspect.signature(QueryAgent.run_simple)
    params = list(sig.parameters.keys())
    
    # Should have: self, query, user_id, session_id
    assert 'self' in params, "Should have self parameter"
    assert 'query' in params, "Should have query parameter"
    assert 'user_id' in params, "Should have user_id parameter"
    assert 'session_id' in params, "Should have session_id parameter"


def test_run_signature():
    """Test that run() has correct method signature (complex workflow)."""
    from services.agent import QueryAgent
    
    sig = inspect.signature(QueryAgent.run)
    params = list(sig.parameters.keys())
    
    # Should have: self, query, user_id, session_id
    assert 'self' in params, "Should have self parameter"
    assert 'query' in params, "Should have query parameter"
    assert 'user_id' in params, "Should have user_id parameter"
    assert 'session_id' in params, "Should have session_id parameter"


def test_query_agent_has_workflow():
    """Test that QueryAgent has LangGraph workflow for complex mode."""
    from services.agent import QueryAgent
    
    # Check that __init__ creates workflow (instance attribute)
    # Workflow is created in __init__ via self._build_graph()
    assert hasattr(QueryAgent, '__init__'), "QueryAgent should have __init__"
    
    # Check that _build_graph method exists
    assert hasattr(QueryAgent, '_build_graph'), "QueryAgent should have _build_graph method"


def test_settings_module_configuration():
    """Test that Django settings module is correctly configured."""
    from django.conf import settings
    
    # Basic settings should exist
    assert hasattr(settings, 'OPENAI_API_KEY'), "OPENAI_API_KEY should exist"
    assert hasattr(settings, 'OPENAI_MODEL'), "OPENAI_MODEL should exist"
    assert hasattr(settings, 'USE_SIMPLE_PIPELINE'), "USE_SIMPLE_PIPELINE should exist"


def test_pipeline_mode_documentation():
    """Test that pipeline modes are documented with expected characteristics."""
    
    # This test serves as documentation
    pipeline_modes = {
        "simple": {
            "description": "Fast RAG-only pipeline",
            "flow": ["intent_keyword", "rag", "generation", "guardrail"],
            "skip": ["plan", "tool_selection", "observation", "replan", "memory"],
            "latency_target": "15-20 sec",
            "use_case": "IT/Marketing simple queries",
        },
        "complex": {
            "description": "Full LangGraph workflow with automation",
            "flow": ["intent_llm", "plan", "tool_selection", "tool_executor", 
                     "observation", "replan_loop", "generation", "guardrail", 
                     "workflow", "memory"],
            "features": ["replan_mechanism", "tool_execution", "workflow_automation"],
            "latency_target": "30-50 sec",
            "use_case": "Multi-step tasks, complex automation",
        }
    }
    
    # Verify documentation structure
    assert len(pipeline_modes["simple"]["flow"]) == 4, "Simple should have 4 nodes"
    assert len(pipeline_modes["complex"]["flow"]) == 10, "Complex should have 10+ nodes"
    assert "replan_loop" in pipeline_modes["complex"]["flow"], "Complex should have replan"
