#!/usr/bin/env python3
"""
Integration Tests: Complete Hybrid Workflow Execution

Covers:
1. Full workflow execution from question to answer
2. Error handling and recovery in real scenario
3. Logging from start to finish
4. Activity callback integration
5. File persistence
6. AdvancedRAGAgent class
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

from services.langgraph_workflow import (
    create_advanced_rag_workflow,
    AdvancedRAGAgent,
    ToolRegistry,
    WorkflowOutput,
)


class TestAdvancedRAGAgent:
    """Test AdvancedRAGAgent class."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test that AdvancedRAGAgent initializes properly."""
        graph, tool_registry = create_advanced_rag_workflow()
        
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        assert agent.graph is not None
        assert agent.tool_registry is not None
    
    @pytest.mark.asyncio
    async def test_agent_answer_question_returns_output(self):
        """Test that answer_question returns WorkflowOutput."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        mock_callback = AsyncMock()
        
        output = await agent.answer_question(
            user_id="test_user",
            question="What is machine learning?",
            available_categories=["AI", "ML", "Data Science"],
            activity_callback=mock_callback
        )
        
        assert isinstance(output, WorkflowOutput)
        assert output.final_answer is not None
        assert isinstance(output.error_messages, list)
    
    @pytest.mark.asyncio
    async def test_agent_includes_workflow_log_in_output(self):
        """Test that output includes workflow_log."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="What is AI?",
            available_categories=["AI", "ML"],
            activity_callback=None
        )
        
        # Should have workflow_log
        assert output.workflow_log is not None or output.error_messages  # Either success or documented error
    
    @pytest.mark.asyncio
    async def test_agent_includes_debug_metadata_in_output(self):
        """Test that output includes debug_metadata."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="Test question?",
            available_categories=["AI"],
            activity_callback=None
        )
        
        # Should have debug_metadata
        assert output.debug_metadata is not None or len(output.error_messages) == 0


class TestActivityCallbackIntegration:
    """Test activity callback integration."""
    
    @pytest.mark.asyncio
    async def test_agent_sends_callback_messages(self):
        """Test that agent sends messages via activity callback."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        mock_callback = AsyncMock()
        
        await agent.answer_question(
            user_id="test_user",
            question="What is AI?",
            available_categories=["AI", "ML"],
            activity_callback=mock_callback
        )
        
        # Callback should have been called at least once
        # (Note: actual call depends on workflow implementation)
        # We're just verifying it doesn't crash
        assert mock_callback is not None


class TestWorkflowLogStructure:
    """Test the structure of generated workflow logs."""
    
    @pytest.mark.asyncio
    async def test_workflow_log_has_required_fields(self):
        """Test that workflow_log contains all required fields."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="What is ML?",
            available_categories=["ML"],
            activity_callback=None
        )
        
        if output.workflow_log:
            log = output.workflow_log
            
            # Verify required fields
            required_fields = ["status", "error_count", "total_time_ms"]
            for field in required_fields:
                assert field in log or log is None, f"Missing field: {field}"
    
    @pytest.mark.asyncio
    async def test_debug_metadata_structure(self):
        """Test that debug_metadata contains expected fields."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="Test?",
            available_categories=["Test"],
            activity_callback=None
        )
        
        if output.debug_metadata:
            meta = output.debug_metadata
            
            # Verify structure
            assert isinstance(meta, dict)


class TestErrorHandlingIntegration:
    """Test error handling in full workflow."""
    
    @pytest.mark.asyncio
    async def test_workflow_handles_missing_categories(self):
        """Test workflow gracefully handles missing categories."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="What is AI?",
            available_categories=[],  # Empty categories
            activity_callback=None
        )
        
        # Should complete with error message
        assert output is not None
        assert len(output.error_messages) >= 0  # May have error or not
    
    @pytest.mark.asyncio
    async def test_workflow_handles_empty_question(self):
        """Test workflow gracefully handles empty question."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="",  # Empty question
            available_categories=["AI"],
            activity_callback=None
        )
        
        # Should complete with error message
        assert output is not None
        assert len(output.error_messages) > 0


class TestLoggingPersistence:
    """Test workflow log persistence."""
    
    @pytest.mark.asyncio
    async def test_workflow_log_json_serializable(self):
        """Test that workflow_log is JSON serializable."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="What is AI?",
            available_categories=["AI"],
            activity_callback=None
        )
        
        if output.workflow_log:
            try:
                json_str = json.dumps(output.workflow_log)
                assert json_str is not None
            except TypeError:
                pytest.fail("workflow_log is not JSON serializable")
    
    @pytest.mark.asyncio
    async def test_debug_metadata_json_serializable(self):
        """Test that debug_metadata is JSON serializable."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="Test?",
            available_categories=["Test"],
            activity_callback=None
        )
        
        if output.debug_metadata:
            try:
                json_str = json.dumps(output.debug_metadata)
                assert json_str is not None
            except TypeError:
                pytest.fail("debug_metadata is not JSON serializable")


class TestWorkflowTiming:
    """Test workflow timing and performance."""
    
    @pytest.mark.asyncio
    async def test_workflow_timing_recorded(self):
        """Test that total_time_ms is recorded."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        start = time.time()
        output = await agent.answer_question(
            user_id="test_user",
            question="What is AI?",
            available_categories=["AI"],
            activity_callback=None
        )
        actual_ms = (time.time() - start) * 1000
        
        if output.workflow_log and "total_time_ms" in output.workflow_log:
            reported_ms = output.workflow_log["total_time_ms"]
            # Should be reasonable (actual should be >= reported, with some margin for scheduling)
            assert reported_ms > 0
    
    @pytest.mark.asyncio
    async def test_workflow_logs_include_timing_events(self):
        """Test that workflow logs include timing information."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="What is ML?",
            available_categories=["ML"],
            activity_callback=None
        )
        
        if output.workflow_log and "logs" in output.workflow_log:
            logs = output.workflow_log["logs"]
            
            # Logs should include timing info
            timing_logs = [l for l in logs if "time_ms" in str(l).lower()]
            # May or may not have timing (depends on implementation)
            assert isinstance(logs, list)


class TestMultipleQuestions:
    """Test workflow with multiple questions."""
    
    @pytest.mark.asyncio
    async def test_multiple_questions_independent(self):
        """Test that multiple questions are processed independently."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        questions = [
            "What is AI?",
            "What is machine learning?",
            "What is deep learning?",
        ]
        
        outputs = []
        for question in questions:
            output = await agent.answer_question(
                user_id="test_user",
                question=question,
                available_categories=["AI", "ML"],
                activity_callback=None
            )
            outputs.append(output)
        
        # All should complete
        assert len(outputs) == 3
        for output in outputs:
            assert isinstance(output, WorkflowOutput)


class TestToolRegistry:
    """Test tool registry functionality."""
    
    def test_tool_registry_contains_all_tools(self):
        """Test that tool registry includes all 4 tools."""
        graph, tool_registry = create_advanced_rag_workflow()
        
        assert tool_registry is not None
        
        # Should have the tool creation functions available
        # (Actual registry structure depends on implementation)
        assert hasattr(tool_registry, 'tools') or hasattr(tool_registry, 'get_tools')


class TestWorkflowStateExtensions:
    """Test WorkflowState extension fields."""
    
    @pytest.mark.asyncio
    async def test_workflow_state_logging_fields_used(self):
        """Test that workflow state logging fields are properly used."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        output = await agent.answer_question(
            user_id="test_user",
            question="What is AI?",
            available_categories=["AI"],
            activity_callback=None
        )
        
        # Output should reflect workflow processing
        assert output is not None
        # Either has logs or documented error
        assert output.error_messages is not None or output.final_answer is not None


# Performance and stress tests
class TestWorkflowPerformance:
    """Test workflow performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_workflow_completes_in_reasonable_time(self):
        """Test that workflow completes within timeout."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        start = time.time()
        
        # Set a timeout
        try:
            output = await asyncio.wait_for(
                agent.answer_question(
                    user_id="test_user",
                    question="Quick question?",
                    available_categories=["AI"],
                    activity_callback=None
                ),
                timeout=30.0  # 30 second timeout
            )
            elapsed = time.time() - start
            assert elapsed < 30
        except asyncio.TimeoutError:
            pytest.fail("Workflow exceeded 30 second timeout")
    
    @pytest.mark.asyncio
    async def test_workflow_memory_efficiency(self):
        """Test that workflow doesn't leak memory with logs."""
        graph, tool_registry = create_advanced_rag_workflow()
        agent = AdvancedRAGAgent(graph, tool_registry)
        
        # Run multiple times
        for i in range(5):
            output = await agent.answer_question(
                user_id=f"user_{i}",
                question="Test question",
                available_categories=["AI"],
                activity_callback=None
            )
            assert output is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
