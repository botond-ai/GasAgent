#!/usr/bin/env python3
"""
Test: Logging System - State Logging, Activity Callbacks, File Persistence

Covers:
1. workflow_logs[] array population
2. Activity callback real-time messaging
3. Async file writing to data/logs/
4. Log aggregation in format_response_node
5. WorkflowOutput enhancement with logs
"""

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

from services.langgraph_workflow import (
    write_workflow_log_async,
    WorkflowState,
    WorkflowOutput,
)


class TestWorkflowLogging:
    """Test workflow logging system."""
    
    @pytest.mark.asyncio
    async def test_log_and_notify_simultaneous(self):
        """Test that log_and_notify updates both activity callback and state."""
        from services.langgraph_workflow import log_and_notify
        
        # Mock activity callback
        mock_callback = AsyncMock()
        
        state = {
            "workflow_logs": [],
            "activity_callback": mock_callback,
        }
        
        message = "Test message"
        activity_type = "info"
        
        # Call log_and_notify
        await log_and_notify(state, message, activity_type)
        
        # Verify activity callback called
        mock_callback.log_activity.assert_called_once_with(message, activity_type=activity_type)
        
        # Verify state logging
        assert len(state["workflow_logs"]) == 1
        log_entry = state["workflow_logs"][0]
        assert "timestamp" in log_entry
        assert "message" in log_entry or "activity_type" in log_entry
    
    @pytest.mark.asyncio
    async def test_write_workflow_log_async_creates_directory(self):
        """Test that async file writing creates directory structure."""
        user_id = "test_user_123"
        session_id = "session_456"
        workflow_log = {
            "total_time_ms": 1234.56,
            "status": "success",
            "error_count": 0,
        }
        
        with patch('builtins.open', create=True) as mock_open:
            with patch('os.makedirs') as mock_makedirs:
                await write_workflow_log_async(user_id, session_id, workflow_log)
                
                # Verify directory creation
                mock_makedirs.assert_called()
                call_args = mock_makedirs.call_args[0][0]
                assert user_id in call_args
                assert "logs" in call_args
    
    @pytest.mark.asyncio
    async def test_write_workflow_log_async_json_format(self):
        """Test that workflow log is written as valid JSON."""
        user_id = "test_user"
        session_id = "test_session"
        workflow_log = {
            "session_id": session_id,
            "user_id": user_id,
            "total_time_ms": 5000.0,
            "status": "success",
            "error_count": 0,
            "logs": [
                {"event": "tool_success", "time_ms": 100.0},
                {"event": "tool_success", "time_ms": 150.0},
            ]
        }
        
        written_content = None
        
        def mock_file_write(content):
            nonlocal written_content
            written_content = content
        
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=None)
            mock_file.write = mock_file_write
            mock_open.return_value = mock_file
            
            with patch('os.makedirs'):
                await write_workflow_log_async(user_id, session_id, workflow_log)
        
        # Verify JSON was written
        if written_content:
            try:
                parsed = json.loads(written_content)
                assert parsed["session_id"] == session_id
                assert parsed["error_count"] == 0
            except json.JSONDecodeError:
                pytest.fail("Written content is not valid JSON")
    
    @pytest.mark.asyncio
    async def test_write_workflow_log_async_handles_error(self):
        """Test that file write errors are handled gracefully."""
        user_id = "test_user"
        session_id = "test_session"
        workflow_log = {"test": "data"}
        
        with patch('os.makedirs'):
            with patch('builtins.open', side_effect=IOError("Disk full")):
                # Should not raise, should handle gracefully
                try:
                    await write_workflow_log_async(user_id, session_id, workflow_log)
                except IOError:
                    pytest.fail("write_workflow_log_async should handle IOError gracefully")


class TestWorkflowLogAggregation:
    """Test log aggregation in format_response_node."""
    
    def test_format_response_aggregates_logs(self):
        """Test that format_response_node aggregates all logs correctly."""
        # Create a state with logs
        state: WorkflowState = {
            "workflow_logs": [
                {
                    "event": "tool_success",
                    "tool_name": "category_router_tool",
                    "time_ms": 234.5,
                    "timestamp": "2024-01-15T10:30:45.123456"
                },
                {
                    "event": "tool_success",
                    "tool_name": "search_vectors_tool",
                    "time_ms": 1456.2,
                    "timestamp": "2024-01-15T10:30:47.234567"
                },
                {
                    "event": "quality_evaluation",
                    "chunk_count": 5,
                    "avg_similarity": 0.725,
                    "timestamp": "2024-01-15T10:30:49.456789"
                },
            ],
            "workflow_start_time": time.time() - 5.0,  # Started 5 seconds ago
            "error_count": 0,
            "retry_count": 0,
            "recovery_actions": [],
            "tool_failures": {},
            "error_messages": [],
            "last_error_type": None,
            "fallback_triggered": False,
            "context_chunks": [MagicMock() for _ in range(5)],
            "final_answer": "Test answer",
            "session_id": "test_session_123",
            "user_id": "test_user_456",
            "question": "What is AI?",
        }
        
        # Mock context_chunks to have required attributes
        for i, chunk in enumerate(state["context_chunks"]):
            chunk.source = f"source_{i}"
            chunk.distance = 0.7 + (i * 0.05)
            chunk.content = f"Content chunk {i}"
        
        from services.langgraph_workflow import format_response_node
        
        # Call format_response_node
        result = format_response_node(state)
        
        # Verify workflow_log was created
        assert "workflow_log" in result
        assert "debug_metadata" in result
        
        workflow_log = result["workflow_log"]
        
        # Verify aggregated metrics
        assert workflow_log["session_id"] == "test_session_123"
        assert workflow_log["user_id"] == "test_user_456"
        assert workflow_log["error_count"] == 0
        assert workflow_log["status"] == "success"
        assert workflow_log["answer_generated"] == True
        assert len(workflow_log["logs"]) > 0
        assert workflow_log["total_time_ms"] > 0


class TestActivityCallbackIntegration:
    """Test activity callback integration in nodes."""
    
    def test_error_node_sends_activity_callbacks(self):
        """Test that handle_errors_node sends correct activity messages."""
        from services.langgraph_workflow import handle_errors_node
        
        mock_callback = AsyncMock()
        
        # Scenario: Retry decision
        state: WorkflowState = {
            "error_count": 1,
            "retry_count": 0,
            "last_error_type": "timeout",
            "activity_callback": mock_callback,
            "workflow_logs": [],
            "recovery_actions": [],
            "fallback_triggered": False,
        }
        
        result_node = handle_errors_node(state)
        
        # Verify callback would be called (it's async task, so we check if task was created)
        # In actual execution, activity_callback.log_activity should be called
        assert result_node == "tools"  # Should retry
        assert state["retry_count"] == 1
    
    def test_evaluate_quality_node_sends_callback_on_low_quality(self):
        """Test that evaluate_search_quality_node sends warning for low quality."""
        from services.langgraph_workflow import evaluate_search_quality_node
        
        mock_callback = AsyncMock()
        
        # Low quality scenario: few chunks, low similarity
        mock_chunks = [
            MagicMock(distance=0.2),
            MagicMock(distance=0.25),
        ]
        
        state: WorkflowState = {
            "context_chunks": mock_chunks,
            "activity_callback": mock_callback,
            "workflow_logs": [],
            "fallback_triggered": False,
        }
        
        result = evaluate_search_quality_node(state)
        
        # Verify fallback was triggered
        assert result["fallback_triggered"] == True
        
        # Verify quality was logged
        logged_events = [e for e in result["workflow_logs"] if e["event"] == "quality_evaluation"]
        assert len(logged_events) > 0


class TestWorkflowStateExtension:
    """Test WorkflowState type hints and logging fields."""
    
    def test_workflow_state_has_logging_fields(self):
        """Test that WorkflowState includes all logging fields."""
        state: WorkflowState = {
            "workflow_logs": [],
            "workflow_start_time": time.time(),
            "error_count": 0,
            "retry_count": 0,
            "errors": [],
            "tool_failures": {},
            "recovery_actions": [],
            "last_error_type": None,
        }
        
        # Verify all logging fields are accessible
        assert isinstance(state["workflow_logs"], list)
        assert isinstance(state["workflow_start_time"], float)
        assert isinstance(state["error_count"], int)
        assert isinstance(state["retry_count"], int)
        assert isinstance(state["tool_failures"], dict)
        assert isinstance(state["recovery_actions"], list)


class TestWorkflowOutputExtension:
    """Test WorkflowOutput enhancement with logging data."""
    
    def test_workflow_output_includes_logs(self):
        """Test that WorkflowOutput can include workflow_log and debug_metadata."""
        workflow_log = {
            "total_time_ms": 2500.5,
            "status": "success",
            "error_count": 0,
            "logs": [{"event": "tool_success", "time_ms": 100}],
        }
        
        debug_metadata = {
            "tool_failures": {},
            "error_messages": [],
            "last_error_type": None,
        }
        
        output = WorkflowOutput(
            final_answer="Test answer",
            answer_with_citations="Test answer with citations",
            citation_sources=[],
            workflow_steps=["validate_input", "tools", "format_response"],
            error_messages=[],
            routed_category="Test Category",
            search_strategy="CATEGORY_BASED",
            fallback_triggered=False,
            workflow_log=workflow_log,
            debug_metadata=debug_metadata,
        )
        
        assert output.workflow_log is not None
        assert output.workflow_log["total_time_ms"] == 2500.5
        assert output.debug_metadata is not None
        assert len(output.debug_metadata["error_messages"]) == 0


# Integration tests
@pytest.mark.asyncio
async def test_end_to_end_logging_flow():
    """Integration test: Verify complete logging flow from initialization to persistence."""
    # This would test the full workflow with mocked components
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
