"""
Tests for prompt templates module.
Ensures prompts are properly structured and versioned.
"""
import pytest
from app.prompts import (
    INTENT_DETECTION_PROMPT,
    TRIAGE_CLASSIFICATION_PROMPT,
    DRAFT_ANSWER_PROMPT,
    POLICY_CHECK_PROMPT,
    PROMPT_VERSION,
)
from app.prompts.templates import get_tone_for_sentiment, TONE_MAP


class TestPromptVersion:
    """Tests for prompt versioning."""

    def test_prompt_version_exists(self):
        """Test that prompt version is defined."""
        assert PROMPT_VERSION is not None
        assert isinstance(PROMPT_VERSION, str)

    def test_prompt_version_format(self):
        """Test prompt version follows semver format."""
        parts = PROMPT_VERSION.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)


class TestPromptStructure:
    """Tests for prompt template structure."""

    def test_intent_detection_prompt_structure(self):
        """Test intent detection prompt has required keys."""
        assert "system" in INTENT_DETECTION_PROMPT
        assert "user" in INTENT_DETECTION_PROMPT
        assert isinstance(INTENT_DETECTION_PROMPT["system"], str)
        assert isinstance(INTENT_DETECTION_PROMPT["user"], str)

    def test_triage_classification_prompt_structure(self):
        """Test triage classification prompt has required keys."""
        assert "system" in TRIAGE_CLASSIFICATION_PROMPT
        assert "user" in TRIAGE_CLASSIFICATION_PROMPT

    def test_draft_answer_prompt_structure(self):
        """Test draft answer prompt has required keys."""
        assert "system" in DRAFT_ANSWER_PROMPT
        assert "user" in DRAFT_ANSWER_PROMPT

    def test_policy_check_prompt_structure(self):
        """Test policy check prompt has required keys."""
        assert "system" in POLICY_CHECK_PROMPT
        assert "user" in POLICY_CHECK_PROMPT


class TestPromptContent:
    """Tests for prompt template content."""

    def test_intent_detection_mentions_required_types(self):
        """Test intent detection prompt mentions all problem types."""
        system = INTENT_DETECTION_PROMPT["system"].lower()
        required_types = ["billing", "technical", "account", "shipping", "product", "other"]
        for ptype in required_types:
            assert ptype in system, f"Missing problem type: {ptype}"

    def test_intent_detection_mentions_sentiments(self):
        """Test intent detection prompt mentions all sentiments."""
        system = INTENT_DETECTION_PROMPT["system"].lower()
        sentiments = ["frustrated", "neutral", "satisfied"]
        for sentiment in sentiments:
            assert sentiment in system, f"Missing sentiment: {sentiment}"

    def test_triage_prompt_mentions_priorities(self):
        """Test triage prompt mentions priority levels."""
        system = TRIAGE_CLASSIFICATION_PROMPT["system"]
        assert "P1" in system
        assert "P2" in system
        assert "P3" in system

    def test_triage_prompt_mentions_teams(self):
        """Test triage prompt mentions team assignments."""
        system = TRIAGE_CLASSIFICATION_PROMPT["system"].lower()
        assert "team" in system

    def test_draft_answer_prompt_structure_requirements(self):
        """Test draft answer prompt specifies response structure."""
        system = DRAFT_ANSWER_PROMPT["system"].lower()
        assert "greeting" in system
        assert "body" in system
        assert "closing" in system

    def test_policy_check_prompt_checks(self):
        """Test policy check prompt mentions compliance checks."""
        system = POLICY_CHECK_PROMPT["system"].lower()
        assert "refund" in system
        assert "sla" in system
        assert "escalation" in system


class TestPromptPlaceholders:
    """Tests for prompt template placeholders."""

    def test_intent_detection_has_message_placeholder(self):
        """Test intent detection user prompt has message placeholder."""
        assert "{message}" in INTENT_DETECTION_PROMPT["user"]

    def test_triage_has_required_placeholders(self):
        """Test triage prompts have required placeholders."""
        system = TRIAGE_CLASSIFICATION_PROMPT["system"]
        assert "{sentiment}" in system
        assert "{problem_type}" in system
        assert "{message}" in TRIAGE_CLASSIFICATION_PROMPT["user"]

    def test_draft_answer_has_required_placeholders(self):
        """Test draft answer prompt has all required placeholders."""
        system = DRAFT_ANSWER_PROMPT["system"]
        required = ["{customer_name}", "{problem_type}", "{sentiment}", "{tone}", "{context}"]
        for placeholder in required:
            assert placeholder in system, f"Missing placeholder: {placeholder}"


class TestToneMapping:
    """Tests for tone mapping function."""

    def test_tone_map_has_all_sentiments(self):
        """Test tone map covers all expected sentiments."""
        assert "frustrated" in TONE_MAP
        assert "neutral" in TONE_MAP
        assert "satisfied" in TONE_MAP

    def test_get_tone_for_frustrated(self):
        """Test frustrated sentiment maps to empathetic tone."""
        assert get_tone_for_sentiment("frustrated") == "empathetic_professional"

    def test_get_tone_for_neutral(self):
        """Test neutral sentiment maps to formal tone."""
        assert get_tone_for_sentiment("neutral") == "formal"

    def test_get_tone_for_satisfied(self):
        """Test satisfied sentiment maps to casual tone."""
        assert get_tone_for_sentiment("satisfied") == "casual"

    def test_get_tone_fallback(self):
        """Test unknown sentiment falls back to empathetic."""
        assert get_tone_for_sentiment("unknown") == "empathetic_professional"
        assert get_tone_for_sentiment("") == "empathetic_professional"
