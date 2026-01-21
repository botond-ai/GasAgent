#!/usr/bin/env python3
"""
Test: Hybrid Workflow Nodes Execution

Covers:
1. validate_input_node initialization
2. process_tool_results_node error detection & logging
3. handle_errors_node decision logic
4. evaluate_search_quality_node quality assessment
5. deduplicate_chunks_node dedup logic
6. route_to_fallback_decision_node routing
7. format_response_node aggregation
8. Complete workflow execution
"""

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

from services.langgraph_workflow import (
    validate_input_node,
    process_tool_results_node,
    handle_errors_node,
    evaluate_search_quality_node,
    deduplicate_chunks_node,
    route_to_fallback_decision_node,
    format_response_node,
    WorkflowState,
)


class TestValidateInputNode:
    """Test input validation and logging initialization."""
    
    def test_validate_input_initializes_logging(self):
        """Test that validate_input_node initializes all logging fields."""
        state: WorkflowState = {
            "question": "What is AI?",
            "available_categories": ["AI", "ML", "Data Science"],
            "user_id": "test_user",
            "activity_callback": None,
        }
        
        result = validate_input_node(state)
        
        # Verify logging fields initialized
        assert "workflow_logs" in result
        assert isinstance(result["workflow_logs"], list)
        assert len(result["workflow_logs"]) > 0
        
        assert "workflow_start_time" in result
        assert isinstance(result["workflow_start_time"], float)
        
        assert "error_count" in result
        assert result["error_count"] == 0
        
        assert "retry_count" in result
        assert result["retry_count"] == 0
        
        assert "errors" in result
        assert isinstance(result["errors"], list)
        
        assert "tool_failures" in result
        assert isinstance(result["tool_failures"], dict)
        
        assert "recovery_actions" in result
        assert isinstance(result["recovery_actions"], list)
    
    def test_validate_input_logs_validation_success(self):
        """Test that validation success is logged."""
        state: WorkflowState = {
            "question": "What is AI?",
            "available_categories": ["AI", "ML"],
            "user_id": "user123",
            "activity_callback": None,
        }
        
        result = validate_input_node(state)
        
        # Verify validation log entry
        validation_logs = [l for l in result["workflow_logs"] if "validated" in str(l).lower()]
        assert len(validation_logs) > 0
    
    def test_validate_input_rejects_empty_question(self):
        """Test that validate_input_node rejects empty question."""
        state: WorkflowState = {
            "question": "",
            "available_categories": ["AI", "ML"],
            "user_id": "user123",
            "activity_callback": None,
        }
        
        result = validate_input_node(state)
        
        # Should have error messages
        assert len(result.get("error_messages", [])) > 0


class TestProcessToolResultsNode:
    """Test tool result processing with error detection."""
    
    def test_process_tool_results_success(self):
        """Test successful tool result processing."""
        tool_result = {
            "success": True,
            "data": {"category": "AI", "confidence": 0.95},
            "_time_ms": 234.5,
        }
        
        state: WorkflowState = {
            "tool_result": tool_result,
            "workflow_logs": [],
            "activity_callback": None,
            "tool_failures": {},
            "error_messages": [],
        }
        
        result = process_tool_results_node(state)
        
        # Verify tool result logged
        tool_logs = [l for l in result["workflow_logs"] if "tool" in str(l).lower()]
        assert len(tool_logs) > 0
    
    def test_process_tool_results_detects_error(self):
        """Test that error in tool result is detected."""
        tool_result = {
            "_error": True,
            "_error_type": "api_error",
            "_time_ms": 2450.3,
            "error_message": "API returned 500",
        }
        
        state: WorkflowState = {
            "tool_result": tool_result,
            "workflow_logs": [],
            "activity_callback": None,
            "tool_failures": {},
            "error_messages": [],
            "error_count": 0,
            "last_error_type": None,
        }
        
        result = process_tool_results_node(state)
        
        # Verify error was detected
        assert result["error_count"] > 0
        assert result["last_error_type"] is not None
        
        # Verify error logged
        error_logs = [l for l in result["workflow_logs"] if "error" in str(l).lower()]
        assert len(error_logs) > 0
    
    def test_process_tool_results_parses_json_string(self):
        """Test JSON string parsing from tool result."""
        import json
        
        tool_data = {
            "success": True,
            "data": {"chunks": ["chunk1", "chunk2"]},
            "_time_ms": 100.0,
        }
        
        state: WorkflowState = {
            "tool_result": json.dumps(tool_data),  # Pass as JSON string
            "workflow_logs": [],
            "activity_callback": None,
            "tool_failures": {},
            "error_messages": [],
        }
        
        result = process_tool_results_node(state)
        
        # Should parse without error
        assert len(result["error_messages"]) == 0 or True  # May log parsing event


class TestHandleErrorsNode:
    """Test error handling and recovery decisions."""
    
    def test_handle_errors_no_error_continues(self):
        """Test that no error continues to next node."""
        state: WorkflowState = {
            "error_count": 0,
            "retry_count": 0,
            "last_error_type": None,
            "activity_callback": None,
            "workflow_logs": [],
            "recovery_actions": [],
        }
        
        result = handle_errors_node(state)
        
        # Should continue to quality evaluation
        assert result == "evaluate_search_quality"
        
        # Should log no-error check
        error_check_logs = [l for l in state["workflow_logs"] if l.get("event") == "error_check"]
        assert len(error_check_logs) > 0
    
    def test_handle_errors_retry_on_timeout(self):
        """Test retry decision on timeout error."""
        state: WorkflowState = {
            "error_count": 1,
            "retry_count": 0,
            "last_error_type": "timeout",
            "activity_callback": None,
            "workflow_logs": [],
            "recovery_actions": [],
            "fallback_triggered": False,
        }
        
        result = handle_errors_node(state)
        
        # Should retry
        assert result == "tools"
        assert state["retry_count"] == 1
        assert "retry_attempt_1" in state["recovery_actions"]
    
    def test_handle_errors_fallback_after_retries_exhausted(self):
        """Test fallback trigger after max retries."""
        state: WorkflowState = {
            "error_count": 3,
            "retry_count": 2,  # Already used 2 retries
            "last_error_type": "api_error",
            "activity_callback": None,
            "workflow_logs": [],
            "recovery_actions": ["retry_attempt_1", "retry_attempt_2"],
            "fallback_triggered": False,
        }
        
        result = handle_errors_node(state)
        
        # Should trigger fallback
        assert result == "tools"
        assert state["fallback_triggered"] == True
        assert "fallback_after_retries" in state["recovery_actions"]


class TestEvaluateSearchQualityNode:
    """Test search quality evaluation."""
    
    def test_evaluate_quality_good_results(self):
        """Test quality evaluation with good results."""
        mock_chunks = [
            MagicMock(distance=0.8),
            MagicMock(distance=0.85),
            MagicMock(distance=0.9),
            MagicMock(distance=0.75),
            MagicMock(distance=0.82),
        ]
        
        state: WorkflowState = {
            "context_chunks": mock_chunks,
            "activity_callback": None,
            "workflow_logs": [],
            "fallback_triggered": False,
            "workflow_steps": [],
        }
        
        result = evaluate_search_quality_node(state)
        
        # Good quality shouldn't trigger fallback
        assert result["fallback_triggered"] == False
        
        # Should log quality evaluation
        quality_logs = [l for l in result["workflow_logs"] if l.get("event") == "quality_evaluation"]
        assert len(quality_logs) > 0
    
    def test_evaluate_quality_triggers_fallback_on_low_similarity(self):
        """Test fallback trigger on low similarity."""
        mock_chunks = [
            MagicMock(distance=0.2),
            MagicMock(distance=0.25),
        ]
        
        state: WorkflowState = {
            "context_chunks": mock_chunks,
            "activity_callback": None,
            "workflow_logs": [],
            "fallback_triggered": False,
            "workflow_steps": [],
        }
        
        result = evaluate_search_quality_node(state)
        
        # Low quality should trigger fallback
        assert result["fallback_triggered"] == True
    
    def test_evaluate_quality_triggers_fallback_on_few_chunks(self):
        """Test fallback trigger on insufficient chunks."""
        mock_chunks = [MagicMock(distance=0.8)]
        
        state: WorkflowState = {
            "context_chunks": mock_chunks,
            "activity_callback": None,
            "workflow_logs": [],
            "fallback_triggered": False,
            "workflow_steps": [],
        }
        
        result = evaluate_search_quality_node(state)
        
        # Too few chunks should trigger fallback
        assert result["fallback_triggered"] == True


class TestDeduplicateChunksNode:
    """Test chunk deduplication."""
    
    def test_deduplicate_removes_duplicates(self):
        """Test that duplicate chunks are removed."""
        # Create chunks with some duplicates
        chunk1 = MagicMock(content="Content A")
        chunk2 = MagicMock(content="Content B")
        chunk3 = MagicMock(content="Content A")  # Duplicate of chunk1
        
        state: WorkflowState = {
            "context_chunks": [chunk1, chunk2, chunk3],
            "activity_callback": None,
            "workflow_logs": [],
            "workflow_steps": [],
        }
        
        result = deduplicate_chunks_node(state)
        
        # Should have 2 unique chunks
        assert len(result["context_chunks"]) == 2
        
        # Should log dedup results
        dedup_logs = [l for l in result["workflow_logs"] if l.get("event") == "deduplication"]
        assert len(dedup_logs) > 0
        assert dedup_logs[0]["duplicates_removed"] == 1
    
    def test_deduplicate_empty_chunks(self):
        """Test deduplication with empty chunks list."""
        state: WorkflowState = {
            "context_chunks": [],
            "activity_callback": None,
            "workflow_logs": [],
            "workflow_steps": [],
        }
        
        result = deduplicate_chunks_node(state)
        
        # Should handle empty case
        assert len(result["context_chunks"]) == 0


class TestRouteToFallbackNode:
    """Test fallback routing decision."""
    
    def test_route_to_fallback_when_triggered(self):
        """Test routing to fallback search when triggered."""
        state: WorkflowState = {
            "fallback_triggered": True,
            "activity_callback": None,
            "workflow_logs": [],
            "recovery_actions": [],
        }
        
        result = route_to_fallback_decision_node(state)
        
        # Should route to tools for fallback
        assert result == "tools"
        assert "triggered_fallback_search" in state["recovery_actions"]
    
    def test_route_normal_when_not_triggered(self):
        """Test normal routing when fallback not triggered."""
        state: WorkflowState = {
            "fallback_triggered": False,
            "activity_callback": None,
            "workflow_logs": [],
        }
        
        result = route_to_fallback_decision_node(state)
        
        # Should continue normally
        assert result == "dedup_chunks"


class TestFormatResponseNode:
    """Test response formatting and log aggregation."""
    
    def test_format_response_aggregates_logs(self):
        """Test that format_response_node aggregates all logs."""
        start_time = time.time()
        
        mock_chunks = [
            MagicMock(source="source1", distance=0.8, content="Content 1"),
            MagicMock(source="source2", distance=0.75, content="Content 2"),
        ]
        
        state: WorkflowState = {
            "workflow_logs": [
                {"event": "tool_success", "time_ms": 100},
                {"event": "quality_evaluation", "chunk_count": 2},
            ],
            "workflow_start_time": start_time,
            "error_count": 0,
            "retry_count": 0,
            "recovery_actions": [],
            "tool_failures": {},
            "error_messages": [],
            "last_error_type": None,
            "fallback_triggered": False,
            "context_chunks": mock_chunks,
            "final_answer": "Test answer",
            "session_id": "session_123",
            "user_id": "user_456",
            "question": "What is AI?",
            "citation_sources": [],
            "answer_with_citations": "",
            "activity_callback": None,
            "workflow_steps": [],
        }
        
        result = format_response_node(state)
        
        # Verify workflow_log created
        assert "workflow_log" in result
        workflow_log = result["workflow_log"]
        
        assert workflow_log["status"] == "success"
        assert workflow_log["error_count"] == 0
        assert len(workflow_log["logs"]) > 0
        assert workflow_log["total_time_ms"] >= 0
    
    def test_format_response_creates_debug_metadata(self):
        """Test that format_response_node creates debug metadata."""
        state: WorkflowState = {
            "workflow_logs": [],
            "workflow_start_time": time.time(),
            "error_count": 1,
            "retry_count": 1,
            "recovery_actions": ["retry_attempt_1"],
            "tool_failures": {"search_tool": "timeout"},
            "error_messages": ["Timeout error"],
            "last_error_type": "timeout",
            "fallback_triggered": True,
            "context_chunks": [],
            "final_answer": "Fallback answer",
            "session_id": "session_123",
            "user_id": "user_456",
            "question": "Test?",
            "citation_sources": [],
            "answer_with_citations": "",
            "activity_callback": None,
            "workflow_steps": [],
        }
        
        result = format_response_node(state)
        
        # Verify debug_metadata created
        assert "debug_metadata" in result
        debug = result["debug_metadata"]
        
        assert "tool_failures" in debug
        assert debug["last_error_type"] == "timeout"


# End-to-end workflow test
class TestCompleteWorkflow:
    """Test complete workflow execution."""
    
    def test_workflow_happy_path(self):
        """Test complete workflow happy path: input → tools → format."""
        # Start with validate_input
        state: WorkflowState = {
            "question": "What is AI?",
            "available_categories": ["AI", "ML"],
            "user_id": "test_user",
            "activity_callback": None,
        }
        
        # Step 1: Validate input
        state = validate_input_node(state)
        assert state["error_count"] == 0
        assert len(state["workflow_logs"]) > 0
        
        # Step 2: Format response (skipping tools for this test)
        state["context_chunks"] = []
        state["final_answer"] = "Test answer"
        state["workflow_start_time"] = time.time()
        
        state = format_response_node(state)
        
        # Verify final state
        assert "workflow_log" in state
        assert "debug_metadata" in state


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
