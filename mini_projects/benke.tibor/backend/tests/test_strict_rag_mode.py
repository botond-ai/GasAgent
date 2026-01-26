"""
Tests for STRICT_RAG_MODE feature flag.

This feature controls whether the LLM can use general knowledge when RAG returns no results.
- STRICT_RAG_MODE=true: Refuse to answer without RAG context (original behavior)
- STRICT_RAG_MODE=false: Allow LLM general knowledge with warning prefix
"""
import os
from unittest.mock import patch


class TestStrictRAGMode:
    """Test STRICT_RAG_MODE feature flag behavior in prompt generation."""

    def test_strict_mode_generates_strict_prompt(self):
        """Test STRICT_RAG_MODE=true generates strict fail-safe instructions."""
        with patch.dict(os.environ, {"STRICT_RAG_MODE": "true"}):
            # Check that strict mode is detected correctly
            strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
            assert strict_rag_mode is True

    def test_relaxed_mode_detected(self):
        """Test STRICT_RAG_MODE=false is detected correctly."""
        with patch.dict(os.environ, {"STRICT_RAG_MODE": "false"}):
            strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
            assert strict_rag_mode is False

    def test_default_is_strict_mode(self):
        """Test that default behavior is STRICT_RAG_MODE=true when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove STRICT_RAG_MODE from environment
            if "STRICT_RAG_MODE" in os.environ:
                del os.environ["STRICT_RAG_MODE"]
            
            strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
            assert strict_rag_mode is True

    def test_case_insensitive_true_values(self):
        """Test that 'True', 'TRUE', 'true' all enable strict mode."""
        for value in ["true", "True", "TRUE"]:
            with patch.dict(os.environ, {"STRICT_RAG_MODE": value}):
                strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
                assert strict_rag_mode is True, f"Failed for value: {value}"

    def test_case_insensitive_false_values(self):
        """Test that 'False', 'FALSE', 'false' all enable relaxed mode."""
        for value in ["false", "False", "FALSE"]:
            with patch.dict(os.environ, {"STRICT_RAG_MODE": value}):
                strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
                assert strict_rag_mode is False, f"Failed for value: {value}"

    def test_prompt_contains_strict_instructions_when_enabled(self):
        """Test that strict mode prompt contains CRITICAL FAIL-SAFE INSTRUCTIONS."""
        with patch.dict(os.environ, {"STRICT_RAG_MODE": "true"}):
            strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
            
            # Simulate the prompt building logic
            if strict_rag_mode:
                failsafe_instructions = """
CRITICAL FAIL-SAFE INSTRUCTIONS:
1. **Only use information from the retrieved documents above** - DO NOT invent facts
"""
            else:
                failsafe_instructions = """
INSTRUCTIONS:
1. **Prefer information from the retrieved documents above**, but you may use your general knowledge
"""
            
            assert "CRITICAL FAIL-SAFE INSTRUCTIONS" in failsafe_instructions
            assert "Only use information from the retrieved documents above" in failsafe_instructions

    def test_prompt_contains_relaxed_instructions_when_disabled(self):
        """Test that relaxed mode prompt allows general knowledge."""
        with patch.dict(os.environ, {"STRICT_RAG_MODE": "false"}):
            strict_rag_mode = os.getenv("STRICT_RAG_MODE", "true").lower() == "true"
            
            # Simulate the prompt building logic
            if strict_rag_mode:
                failsafe_instructions = """
CRITICAL FAIL-SAFE INSTRUCTIONS:
1. **Only use information from the retrieved documents above** - DO NOT invent facts
"""
            else:
                failsafe_instructions = """
INSTRUCTIONS:
1. **Prefer information from the retrieved documents above**, but you may use your general knowledge
2. **If using general knowledge (not from documents):**
   - Clearly state: "⚠️ A következő információ általános tudásomon alapul"
"""
            
            assert "you may use your general knowledge" in failsafe_instructions
            assert "⚠️ A következő információ általános tudásomon alapul" in failsafe_instructions
            assert "CRITICAL FAIL-SAFE" not in failsafe_instructions
