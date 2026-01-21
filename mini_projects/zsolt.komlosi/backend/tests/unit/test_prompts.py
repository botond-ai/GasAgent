"""
Tests for LLM prompts.
"""

import pytest

from app.core.prompts import (
    ANALYSIS_PROMPT,
    QUERY_EXPANSION_PROMPT,
    ANSWER_GENERATION_PROMPT,
    POLICY_CHECK_PROMPT,
    CUSTOMER_RESPONSE_PROMPT,
    ROLLING_SUMMARY_PROMPT,
    RERANKING_PROMPT,
)


class TestAnalysisPrompt:
    """Tests for ticket analysis prompt."""

    def test_prompt_has_ticket_placeholder(self):
        """Test that prompt includes ticket_text placeholder."""
        assert "{ticket_text}" in ANALYSIS_PROMPT

    def test_prompt_includes_categories(self):
        """Test that prompt includes expected categories."""
        categories = ["Billing", "Technical", "Account", "Feature Request", "General"]
        for category in categories:
            assert category in ANALYSIS_PROMPT

    def test_prompt_includes_priorities(self):
        """Test that prompt includes priority levels."""
        priorities = ["P1", "P2", "P3", "P4"]
        for priority in priorities:
            assert priority in ANALYSIS_PROMPT

    def test_prompt_includes_sentiment_guidance(self):
        """Test that prompt includes sentiment analysis guidance."""
        assert "Sentiment" in ANALYSIS_PROMPT or "sentiment" in ANALYSIS_PROMPT


class TestQueryExpansionPrompt:
    """Tests for query expansion prompt."""

    def test_prompt_has_query_placeholder(self):
        """Test that prompt includes query placeholder."""
        assert "{query}" in QUERY_EXPANSION_PROMPT

    def test_prompt_has_context_placeholder(self):
        """Test that prompt includes context placeholder."""
        assert "{context}" in QUERY_EXPANSION_PROMPT

    def test_prompt_asks_for_multiple_queries(self):
        """Test that prompt asks for multiple search queries."""
        assert "3" in QUERY_EXPANSION_PROMPT


class TestAnswerGenerationPrompt:
    """Tests for answer generation prompt."""

    def test_prompt_has_required_placeholders(self):
        """Test that prompt includes all required placeholders."""
        required = ["{ticket_text}", "{category}", "{priority}", "{sentiment}", "{documents}", "{tone}"]
        for placeholder in required:
            assert placeholder in ANSWER_GENERATION_PROMPT

    def test_prompt_mentions_citations(self):
        """Test that prompt mentions citation format."""
        assert "[#" in ANSWER_GENERATION_PROMPT

    def test_prompt_warns_about_refunds(self):
        """Test that prompt includes refund warning."""
        assert "refund" in ANSWER_GENERATION_PROMPT.lower()


class TestPolicyCheckPrompt:
    """Tests for policy check prompt."""

    def test_prompt_has_response_placeholder(self):
        """Test that prompt includes response placeholder."""
        assert "{response}" in POLICY_CHECK_PROMPT

    def test_prompt_checks_refund_promise(self):
        """Test that prompt checks for refund promises."""
        assert "refund" in POLICY_CHECK_PROMPT.lower()

    def test_prompt_checks_sla_mention(self):
        """Test that prompt checks for SLA mentions."""
        assert "sla" in POLICY_CHECK_PROMPT.lower()

    def test_prompt_checks_escalation(self):
        """Test that prompt checks for escalation needs."""
        assert "escalat" in POLICY_CHECK_PROMPT.lower()


class TestCustomerResponsePrompt:
    """Tests for customer response prompt."""

    def test_prompt_has_customer_name_placeholder(self):
        """Test that prompt includes customer name placeholder."""
        assert "{customer_name}" in CUSTOMER_RESPONSE_PROMPT

    def test_prompt_has_language_placeholder(self):
        """Test that prompt includes language placeholder."""
        assert "{language}" in CUSTOMER_RESPONSE_PROMPT

    def test_prompt_has_ticket_placeholder(self):
        """Test that prompt includes ticket text placeholder."""
        assert "{ticket_text}" in CUSTOMER_RESPONSE_PROMPT

    def test_prompt_instructs_same_language_response(self):
        """Test that prompt instructs to respond in same language."""
        assert "SAME LANGUAGE" in CUSTOMER_RESPONSE_PROMPT

    def test_prompt_includes_greeting_examples(self):
        """Test that prompt includes greeting examples."""
        assert "Kedves" in CUSTOMER_RESPONSE_PROMPT
        assert "Dear" in CUSTOMER_RESPONSE_PROMPT

    def test_prompt_forbids_question_repetition(self):
        """Test that prompt forbids repeating customer's question."""
        assert "DO NOT repeat" in CUSTOMER_RESPONSE_PROMPT

    def test_prompt_forbids_internal_info(self):
        """Test that prompt forbids internal analysis info."""
        assert "internal" in CUSTOMER_RESPONSE_PROMPT.lower()

    def test_prompt_can_be_formatted(self):
        """Test that prompt can be formatted with all placeholders."""
        formatted = CUSTOMER_RESPONSE_PROMPT.format(
            customer_name="Test User",
            language="Hungarian",
            ticket_text="Test ticket",
            category="Technical",
            priority="P2",
            sentiment="frustrated",
        )

        assert "Test User" in formatted
        assert "Hungarian" in formatted
        assert "Test ticket" in formatted


class TestRollingSummaryPrompt:
    """Tests for rolling summary prompt."""

    def test_prompt_has_previous_summary_placeholder(self):
        """Test that prompt includes previous summary placeholder."""
        assert "{previous_summary}" in ROLLING_SUMMARY_PROMPT

    def test_prompt_has_new_messages_placeholder(self):
        """Test that prompt includes new messages placeholder."""
        assert "{new_messages}" in ROLLING_SUMMARY_PROMPT

    def test_prompt_specifies_max_length(self):
        """Test that prompt specifies maximum length."""
        assert "200" in ROLLING_SUMMARY_PROMPT


class TestRerankingPrompt:
    """Tests for reranking prompt."""

    def test_prompt_has_query_placeholder(self):
        """Test that prompt includes query placeholder."""
        assert "{query}" in RERANKING_PROMPT

    def test_prompt_has_documents_placeholder(self):
        """Test that prompt includes documents placeholder."""
        assert "{documents}" in RERANKING_PROMPT

    def test_prompt_specifies_score_range(self):
        """Test that prompt specifies scoring range."""
        assert "0.0" in RERANKING_PROMPT
        assert "1.0" in RERANKING_PROMPT

    def test_prompt_requests_json_output(self):
        """Test that prompt requests JSON output."""
        assert "JSON" in RERANKING_PROMPT


class TestPromptConsistency:
    """Tests for overall prompt consistency."""

    def test_all_prompts_are_non_empty(self):
        """Test that all prompts have content."""
        prompts = [
            ANALYSIS_PROMPT,
            QUERY_EXPANSION_PROMPT,
            ANSWER_GENERATION_PROMPT,
            POLICY_CHECK_PROMPT,
            CUSTOMER_RESPONSE_PROMPT,
            ROLLING_SUMMARY_PROMPT,
            RERANKING_PROMPT,
        ]

        for prompt in prompts:
            assert len(prompt) > 50  # Minimum reasonable length

    def test_prompts_use_consistent_placeholder_style(self):
        """Test that all prompts use {placeholder} style."""
        prompts = [
            ANALYSIS_PROMPT,
            QUERY_EXPANSION_PROMPT,
            ANSWER_GENERATION_PROMPT,
            POLICY_CHECK_PROMPT,
            CUSTOMER_RESPONSE_PROMPT,
            ROLLING_SUMMARY_PROMPT,
            RERANKING_PROMPT,
        ]

        for prompt in prompts:
            # Check that placeholders use curly braces
            if "{" in prompt:
                assert "}" in prompt
