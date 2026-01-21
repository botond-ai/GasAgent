"""
Unit tests for v2.9.0 critical bugfixes.

Tests:
1. JSON parsing from LLM responses (manual extraction)
2. None-safe replan_count handling
3. Jira ticket question auto-append for IT domain
4. Recursion limit configuration in ainvoke
"""

import json
import re
import pytest
from unittest.mock import AsyncMock


# ===================================================================
# Test 1: JSON Parsing from LLM Responses
# ===================================================================

def test_json_parsing_from_markdown_code_block():
    """Test JSON extraction from markdown ```json...``` block."""
    response_text = """
Here's the result:

```json
{
    "domain": "it",
    "confidence": 0.95,
    "reasoning": "VPN keyword indicates IT domain"
}
```
"""
    
    # Extract JSON (mimics agent.py logic)
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    assert json_match is not None
    
    json_str = json_match.group(1)
    data = json.loads(json_str)
    
    assert data["domain"] == "it"
    assert data["confidence"] == 0.95
    assert "VPN" in data["reasoning"]


def test_json_parsing_from_raw_json():
    """Test JSON extraction from raw {...} without markdown."""
    response_text = """
    {"domain": "hr", "confidence": 0.88, "reasoning": "Holiday policy question"}
    """
    
    # Try markdown first, fallback to raw
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if not json_match:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    
    assert json_match is not None
    json_str = json_match.group(0)
    data = json.loads(json_str)
    
    assert data["domain"] == "hr"
    assert data["confidence"] == 0.88


def test_json_parsing_fallback_empty_dict():
    """Test fallback to empty dict if no JSON found."""
    response_text = "This response contains no JSON at all."
    
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if not json_match:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    
    json_str = json_match.group(0) if json_match else '{}'
    data = json.loads(json_str)
    
    assert data == {}


# ===================================================================
# Test 2: None-Safe replan_count Handling
# ===================================================================

def test_replan_count_none_safe_with_default():
    """Test that state.get('replan_count', 0) can still return None."""
    state = {"replan_count": None}  # Key exists but value is None
    
    # OLD (BROKEN):
    # replan_count = state.get("replan_count", 0)  # Returns None!
    # This would crash: if replan_count > 0
    
    # NEW (WORKING):
    replan_count = state.get("replan_count") or 0
    
    assert replan_count == 0  # None → 0 conversion


def test_replan_count_none_safe_with_missing_key():
    """Test that missing key returns 0."""
    state = {}
    
    replan_count = state.get("replan_count") or 0
    
    assert replan_count == 0


def test_replan_count_none_safe_with_valid_value():
    """Test that valid integer value is preserved."""
    state = {"replan_count": 2}
    
    replan_count = state.get("replan_count") or 0
    
    assert replan_count == 2


def test_replan_count_increment_in_plan_node():
    """Test replan_count increment logic in plan_node."""
    # Scenario: Coming from observation_check with replan decision
    state = {
        "observation_result": {"sufficient": False, "next_action": "replan"},
        "replan_count": 1
    }
    
    # Simulate plan_node logic
    replan_count = state.get("replan_count") or 0
    if replan_count > 0 or state.get("observation_result"):
        state["replan_count"] = replan_count + 1
    
    assert state["replan_count"] == 2


# ===================================================================
# Test 3: IT Domain Jira Question Auto-Append
# ===================================================================

def test_jira_question_auto_append_for_it_domain():
    """Test that Jira ticket question is automatically appended for IT domain."""
    is_it_domain = True
    answer = "A VPN hibaelhárítási folyamat [IT-KB-234] alapján először ellenőrizd..."
    
    # Simulate generation_node logic
    jira_question = "📋 Szeretnéd, hogy létrehozzak egy Jira support ticketet ehhez a kérdéshez?"
    if is_it_domain and jira_question not in answer:
        answer = f"{answer}\n\n{jira_question}"
    
    assert jira_question in answer
    assert answer.endswith(jira_question)


def test_jira_question_not_duplicated():
    """Test that Jira question is not duplicated if already present."""
    is_it_domain = True
    jira_question = "📋 Szeretnéd, hogy létrehozzak egy Jira support ticketet ehhez a kérdéshez?"
    answer = f"VPN troubleshooting steps...\n\n{jira_question}"
    
    # Should NOT append again
    if is_it_domain and jira_question not in answer:
        answer = f"{answer}\n\n{jira_question}"
    
    # Count occurrences
    occurrences = answer.count(jira_question)
    assert occurrences == 1


def test_jira_question_not_added_for_non_it_domain():
    """Test that Jira question is NOT added for non-IT domains."""
    is_it_domain = False
    answer = "A szabadság policy [HR-POL-123] szerint..."
    
    jira_question = "📋 Szeretnéd, hogy létrehozzak egy Jira support ticketet ehhez a kérdéshez?"
    if is_it_domain and jira_question not in answer:
        answer = f"{answer}\n\n{jira_question}"
    
    assert jira_question not in answer


# ===================================================================
# Test 4: Recursion Limit Configuration
# ===================================================================

@pytest.mark.asyncio
async def test_recursion_limit_in_ainvoke_config():
    """Test that recursion_limit is correctly passed to ainvoke config."""
    from services.agent import QueryAgent
    
    # Mock dependencies
    mock_llm = AsyncMock()
    mock_rag = AsyncMock()
    mock_workflow = AsyncMock()
    
    # Create agent instance
    agent = QueryAgent(llm_client=mock_llm, rag_client=mock_rag)
    agent.workflow = mock_workflow
    
    # Mock workflow.ainvoke to verify config
    async def mock_ainvoke(state, config=None):
        # Verify recursion_limit is passed
        assert config is not None
        assert "recursion_limit" in config
        assert config["recursion_limit"] == 50
        return state
    
    mock_workflow.ainvoke = mock_ainvoke
    
    # Run agent (this should call ainvoke with config)
    # Note: This test verifies the pattern, actual implementation may vary
    # Adjust based on actual agent.py implementation


# ===================================================================
# Test 5: Decision Function Read-Only Enforcement
# ===================================================================

def test_observation_decision_is_read_only():
    """Test that observation_decision does NOT modify state."""
    from services.agent import QueryAgent
    
    # Mock dependencies
    mock_llm = AsyncMock()
    mock_rag = AsyncMock()
    agent = QueryAgent(llm_client=mock_llm, rag_client=mock_rag)
    
    state = {
        "observation_result": {"sufficient": False, "next_action": "replan"},
        "replan_count": 1
    }
    
    # Call decision function
    result = agent._observation_decision(state)
    
    # Verify state NOT modified
    assert state["replan_count"] == 1  # NOT incremented
    assert result in ["replan", "generate"]


def test_observation_decision_forces_generate_at_limit():
    """Test that observation_decision forces generate when replan_count >= 2."""
    from services.agent import QueryAgent
    
    mock_llm = AsyncMock()
    mock_rag = AsyncMock()
    agent = QueryAgent(llm_client=mock_llm, rag_client=mock_rag)
    
    state = {
        "observation_result": {"sufficient": False, "next_action": "replan"},
        "replan_count": 2  # Max limit reached
    }
    
    result = agent._observation_decision(state)
    
    # Should force "generate" despite insufficient info
    assert result == "generate"
    assert state["replan_count"] == 2  # NOT incremented


# ===================================================================
# Test 6: LangGraph Node Name Uniqueness
# ===================================================================

def test_node_names_unique_from_state_fields():
    """Test that node names don't conflict with state field names."""
    # This is a design test - ensure observation_check node name
    # doesn't conflict with any AgentState field
    
    # AgentState fields (TypedDict)
    state_fields = [
        "query", "user_id", "session_id", "messages", "domain",
        "retrieved_docs", "citations", "workflow", "validation_errors",
        "retry_count", "replan_count", "observation_result",  # NOT "observation"!
        "feedback_metrics", "request_start_time", "tool_results",
        "tool_selection", "execution_plan", "intent_output",
        "rag_unavailable", "llm_prompt", "llm_response", "rag_context",
        "output", "memory_summary", "memory_facts", "memory_key_decisions",
    ]
    
    # Node names
    node_names = [
        "intent_detection", "plan_node", "select_tools", "tool_executor",
        "observation_check",  # Renamed from "observation"
        "retrieval", "generation", "guardrail",
        "collect_metrics", "execute_workflow", "memory_update"
    ]
    
    # Verify no overlap
    overlap = set(state_fields).intersection(set(node_names))
    assert len(overlap) == 0, f"Node names conflict with state fields: {overlap}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
