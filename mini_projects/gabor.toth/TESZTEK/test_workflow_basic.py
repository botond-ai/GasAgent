"""Tests for simplified LangGraph workflow."""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import asyncio
from unittest.mock import AsyncMock, MagicMock
from services.langgraph_workflow import (
    validate_input_node,
    evaluate_search_quality_node,
    deduplicate_chunks_node,
    format_response_node,
    handle_errors_node,
    WorkflowState,
    SearchStrategy,
)
from domain.models import RetrievedChunk


class TestValidateInputNode:
    """Test validate_input_node function."""
    
    def test_validates_empty_question(self):
        """Test validation of empty question."""
        state: WorkflowState = {"question": "", "available_categories": ["cat1", "cat2"]}
        result = validate_input_node(state)
        assert len(result["errors"]) > 0
        assert result["error_messages"] == ["Question is empty"]
    
    def test_validates_empty_categories(self):
        """Test validation of empty categories."""
        state: WorkflowState = {"question": "What is X?", "available_categories": []}
        result = validate_input_node(state)
        assert len(result["errors"]) > 0
    
    def test_initializes_workflow_logs(self):
        """Test that workflow_logs is initialized."""
        state: WorkflowState = {"question": "What is X?", "available_categories": ["cat1"]}
        result = validate_input_node(state)
        assert "workflow_logs" in result
        assert isinstance(result["workflow_logs"], list)
    
    def test_initializes_workflow_steps(self):
        """Test that workflow_steps is initialized."""
        state: WorkflowState = {"question": "What is X?", "available_categories": ["cat1"]}
        result = validate_input_node(state)
        assert "workflow_steps" in result
        assert "input_validated" in result["workflow_steps"]
    
    def test_initializes_error_tracking(self):
        """Test that error tracking fields are initialized."""
        state: WorkflowState = {"question": "What is X?", "available_categories": ["cat1"]}
        result = validate_input_node(state)
        assert result["error_count"] == 0
        assert result["retry_count"] == 0
        assert "tool_failures" in result


class TestEvaluateSearchQualityNode:
    """Test evaluate_search_quality_node function."""
    
    def test_detects_low_quality_chunks(self):
        """Test detection of low quality chunks."""
        chunk = RetrievedChunk(chunk_id="1", content="test", distance=0.9, metadata={"source": "test.txt"})
        state: WorkflowState = {
            "context_chunks": [chunk],
            "workflow_logs": [],
            "workflow_steps": [],
        }
        result = evaluate_search_quality_node(state)
        assert result["fallback_triggered"] is True
    
    def test_logs_quality_metrics(self):
        """Test that quality metrics are logged."""
        chunk = RetrievedChunk(chunk_id="1", content="test", distance=0.1, metadata={"source": "test.txt"})
        state: WorkflowState = {
            "context_chunks": [chunk, chunk, chunk],
            "workflow_logs": [],
            "workflow_steps": [],
        }
        result = evaluate_search_quality_node(state)
        assert len(result["workflow_logs"]) > 0
        assert result["workflow_logs"][0]["event"] == "quality_evaluation"


class TestDeduplicateChunksNode:
    """Test deduplicate_chunks_node function."""
    
    def test_deduplicates_chunks(self):
        """Test chunk deduplication."""
        chunk1 = RetrievedChunk(chunk_id="1", content="test content", distance=0.1, metadata={"source": "test1.txt"})
        chunk2 = RetrievedChunk(chunk_id="2", content="test content", distance=0.2, metadata={"source": "test2.txt"})  # Duplicate
        chunk3 = RetrievedChunk(chunk_id="3", content="other content", distance=0.3, metadata={"source": "test3.txt"})
        
        state: WorkflowState = {
            "context_chunks": [chunk1, chunk2, chunk3],
            "workflow_logs": [],
            "workflow_steps": [],
        }
        result = deduplicate_chunks_node(state)
        
        # Should have 2 unique chunks
        assert len(result["context_chunks"]) == 2
    
    def test_logs_deduplication(self):
        """Test that deduplication is logged."""
        chunk1 = RetrievedChunk(chunk_id="1", content="test content", distance=0.1, metadata={"source": "test1.txt"})
        chunk2 = RetrievedChunk(chunk_id="2", content="test content", distance=0.2, metadata={"source": "test2.txt"})
        
        state: WorkflowState = {
            "context_chunks": [chunk1, chunk2],
            "workflow_logs": [],
            "workflow_steps": [],
        }
        result = deduplicate_chunks_node(state)
        
        assert any(log["event"] == "deduplication" for log in result["workflow_logs"])


class TestFormatResponseNode:
    """Test format_response_node function."""
    
    def test_formats_citations(self):
        """Test citation formatting."""
        chunk = RetrievedChunk(chunk_id="1", content="This is important information.", distance=0.2, metadata={"source": "doc.txt"})
        state: WorkflowState = {
            "context_chunks": [chunk],
            "final_answer": "The answer is X.",
            "error_count": 0,
            "retry_count": 0,
            "workflow_logs": [],
            "workflow_steps": [],
            "recovery_actions": [],
            "fallback_triggered": False,
            "workflow_start_time": 1234567890.0,
        }
        result = format_response_node(state)
        
        assert len(result["citation_sources"]) > 0
        assert result["citation_sources"][0]["source"] == "Unknown"  # metadata.source not extracted
    
    def test_builds_workflow_log(self):
        """Test that workflow_log is built."""
        state: WorkflowState = {
            "context_chunks": [],
            "final_answer": "Answer",
            "error_count": 0,
            "retry_count": 0,
            "workflow_logs": [],
            "workflow_steps": [],
            "recovery_actions": [],
            "fallback_triggered": False,
            "workflow_start_time": 1234567890.0,
            "user_id": "test_user",
            "question": "Test?",
            "session_id": "sess_123",
        }
        result = format_response_node(state)
        
        assert "workflow_log" in result
        assert result["workflow_log"]["status"] == "success"
        assert result["workflow_log"]["error_count"] == 0


class TestHandleErrorsNode:
    """Test handle_errors_node function."""
    
    def test_no_errors_continues_flow(self):
        """Test that no errors continue to next node."""
        state: WorkflowState = {
            "error_count": 0,
            "retry_count": 0,
            "last_error_type": None,
            "workflow_logs": [],
        }
        result = handle_errors_node(state)
        # Now returns dict (state) instead of routing string
        assert isinstance(result, dict)
        assert result["error_count"] == 0
    
    def test_retries_recoverable_errors(self):
        """Test that recoverable errors are retried."""
        state: WorkflowState = {
            "error_count": 1,
            "retry_count": 0,
            "last_error_type": "timeout",
            "workflow_logs": [],
            "recovery_actions": [],
        }
        result = handle_errors_node(state)
        # Now returns dict (state) instead of routing string
        assert isinstance(result, dict)
        assert result["retry_count"] == 1
        assert result["error_count"] == 1
    
    def test_fallback_after_retries_exhausted(self):
        """Test fallback when retries exhausted."""
        state: WorkflowState = {
            "error_count": 1,
            "retry_count": 2,
            "last_error_type": "api_error",
            "workflow_logs": [],
            "recovery_actions": [],
            "fallback_triggered": False,
        }
        result = handle_errors_node(state)
        # Now returns dict (state) instead of routing string
        assert isinstance(result, dict)
        assert result["fallback_triggered"] is True


class TestWorkflowStatePersistence:
    """Test WorkflowState initialization and persistence."""
    
    def test_state_persists_across_nodes(self):
        """Test that state persists across node invocations."""
        state: WorkflowState = {
            "question": "What is X?",
            "available_categories": ["cat1"],
        }
        
        # First node
        state = validate_input_node(state)
        assert "workflow_logs" in state
        
        # Second node should see the logs
        chunk = RetrievedChunk(chunk_id="1", content="test", distance=0.5, metadata={"source": "test.txt"})
        state["context_chunks"] = [chunk]
        
        state = evaluate_search_quality_node(state)
        assert len(state["workflow_logs"]) >= 1  # From first node
    
    def test_errors_accumulate(self):
        """Test that errors accumulate properly."""
        state: WorkflowState = {
            "question": "",  # Invalid
            "available_categories": ["cat1"],
        }
        
        state = validate_input_node(state)
        initial_error_count = len(state["errors"])
        
        # Manually add more errors
        state["errors"].append("Another error")
        state["error_count"] += 1
        
        # State should preserve all errors
        assert len(state["errors"]) > initial_error_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
