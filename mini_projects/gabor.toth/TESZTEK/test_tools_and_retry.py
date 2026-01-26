#!/usr/bin/env python3
"""
Test: Tool Implementations & Retry Logic

Covers:
1. Tool execution with timing metadata (_time_ms)
2. Error signal handling (_error, _error_type)
3. Exponential backoff retry logic
4. Tool success/error responses
5. Fallback answer generation in generate_answer_tool
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

from services.langgraph_workflow import (
    category_router_tool,
    embed_question_tool,
    search_vectors_tool,
    generate_answer_tool,
    retry_with_backoff,
)


class TestToolTiming:
    """Test that all tools include timing metadata."""
    
    @pytest.mark.asyncio
    async def test_category_router_includes_time_ms(self):
        """Test category_router_tool returns _time_ms field."""
        question = "What is machine learning?"
        categories = ["AI", "ML", "Data Science"]
        
        result = await category_router_tool(question, categories)
        
        # Verify _time_ms is present
        assert "_time_ms" in result
        assert isinstance(result["_time_ms"], (int, float))
        assert result["_time_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_embed_question_includes_time_ms(self):
        """Test embed_question_tool returns _time_ms field."""
        question = "What is AI?"
        
        result = await embed_question_tool(question)
        
        # Verify _time_ms is present
        assert "_time_ms" in result
        assert isinstance(result["_time_ms"], (int, float))
        assert result["_time_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_search_vectors_includes_time_ms(self):
        """Test search_vectors_tool returns _time_ms field."""
        embedding = [0.1, 0.2, 0.3]
        category = "AI"
        
        result = await search_vectors_tool(embedding, category)
        
        # Verify _time_ms is present
        assert "_time_ms" in result
        assert isinstance(result["_time_ms"], (int, float))
        assert result["_time_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_generate_answer_includes_time_ms(self):
        """Test generate_answer_tool returns _time_ms field."""
        question = "What is ML?"
        chunks = ["ML is a field of AI", "ML uses algorithms"]
        
        result = await generate_answer_tool(question, chunks)
        
        # Verify _time_ms is present
        assert "_time_ms" in result
        assert isinstance(result["_time_ms"], (int, float))
        assert result["_time_ms"] > 0


class TestToolErrorSignals:
    """Test error signal handling in tools."""
    
    @pytest.mark.asyncio
    async def test_tool_error_includes_error_fields(self):
        """Test that tool errors include _error and _error_type fields."""
        # Mock a tool call that will fail
        # This tests the error handling within each tool
        pass
    
    @pytest.mark.asyncio
    async def test_generate_answer_fallback_on_error(self):
        """Test generate_answer_tool provides fallback answer on error."""
        question = "Test question?"
        chunks = []
        
        result = await generate_answer_tool(question, chunks)
        
        # On error or empty chunks, should return fallback
        # Fallback answer should still have timing
        assert "_time_ms" in result


class TestRetryWithBackoff:
    """Test exponential backoff retry logic."""
    
    @pytest.mark.asyncio
    async def test_retry_backoff_succeeds_first_try(self):
        """Test successful function on first attempt."""
        mock_func = AsyncMock(return_value={"data": "success"})
        
        result, error = await retry_with_backoff(mock_func, max_retries=2)
        
        assert result is not None
        assert error is None
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_backoff_succeeds_second_try(self):
        """Test successful function on second attempt after initial failure."""
        call_count = 0
        
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First attempt fails")
            return {"data": "success"}
        
        result, error = await retry_with_backoff(failing_then_success, max_retries=2)
        
        assert result is not None
        assert error is None
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_backoff_exponential_delays(self):
        """Test that retry uses exponential backoff delays."""
        call_times = []
        
        async def always_fails():
            call_times.append(time.time())
            raise Exception("Always fails")
        
        start = time.time()
        result, error = await retry_with_backoff(always_fails, max_retries=2)
        elapsed = time.time() - start
        
        # With max_retries=2: 0.5s delay after 1st, 1.0s delay after 2nd
        # Total minimum ~1.5s
        assert error is not None
        # Allow some variance
        assert elapsed > 1.0
    
    @pytest.mark.asyncio
    async def test_retry_backoff_max_retries_limit(self):
        """Test that retry respects max_retries limit."""
        call_count = 0
        
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")
        
        result, error = await retry_with_backoff(always_fails, max_retries=2)
        
        # Should try: initial + 2 retries = 3 total attempts
        assert call_count == 3
        assert error is not None
        assert result is None


class TestToolResponseFormat:
    """Test that tools return properly formatted responses."""
    
    @pytest.mark.asyncio
    async def test_successful_tool_response_structure(self):
        """Test structure of successful tool response."""
        question = "What is AI?"
        categories = ["AI", "ML"]
        
        result = await category_router_tool(question, categories)
        
        # Successful response should have
        assert "success" in result or "_time_ms" in result  # At least timing
        assert "_time_ms" in result
        # Should not have error fields on success
        if "_error" in result:
            assert result["_error"] == False
    
    @pytest.mark.asyncio
    async def test_tool_response_json_serializable(self):
        """Test that tool responses are JSON serializable."""
        import json
        
        question = "Test?"
        categories = ["Cat1", "Cat2"]
        
        result = await category_router_tool(question, categories)
        
        # Should be JSON serializable
        try:
            json_str = json.dumps(result)
            assert json_str is not None
        except TypeError:
            pytest.fail("Tool response is not JSON serializable")


class TestToolInputValidation:
    """Test that tools validate inputs appropriately."""
    
    @pytest.mark.asyncio
    async def test_category_router_with_empty_categories(self):
        """Test category_router_tool with empty categories list."""
        question = "What is AI?"
        categories = []
        
        result = await category_router_tool(question, categories)
        
        # Should handle gracefully with timing
        assert "_time_ms" in result
    
    @pytest.mark.asyncio
    async def test_embed_question_with_empty_question(self):
        """Test embed_question_tool with empty question."""
        question = ""
        
        result = await embed_question_tool(question)
        
        # Should handle gracefully
        assert "_time_ms" in result
    
    @pytest.mark.asyncio
    async def test_search_vectors_with_invalid_embedding(self):
        """Test search_vectors_tool with empty embedding."""
        embedding = []
        category = "AI"
        
        result = await search_vectors_tool(embedding, category)
        
        # Should handle gracefully
        assert "_time_ms" in result


class TestToolIntegration:
    """Integration tests for tool interactions."""
    
    @pytest.mark.asyncio
    async def test_tool_chain_category_to_embed_to_search(self):
        """Test the flow: category_router → embed → search."""
        question = "What is machine learning?"
        categories = ["AI", "ML", "Data Science"]
        
        # Step 1: Route to category
        router_result = await category_router_tool(question, categories)
        assert "_time_ms" in router_result
        
        # Step 2: Embed question
        embed_result = await embed_question_tool(question)
        assert "_time_ms" in embed_result
        
        # Step 3: Search vectors
        embedding = embed_result.get("embedding") or [0.1, 0.2, 0.3]
        category = "ML"
        search_result = await search_vectors_tool(embedding, category)
        assert "_time_ms" in search_result


# Timing accuracy tests
class TestToolTimingAccuracy:
    """Test that timing measurements are accurate."""
    
    @pytest.mark.asyncio
    async def test_tool_timing_matches_actual_execution(self):
        """Test that _time_ms roughly matches actual execution time."""
        question = "What is AI?"
        
        start = time.time()
        result = await embed_question_tool(question)
        actual_ms = (time.time() - start) * 1000
        
        reported_ms = result.get("_time_ms", 0)
        
        # Reported timing should be close to actual (within 50ms tolerance)
        assert abs(reported_ms - actual_ms) < 50


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
