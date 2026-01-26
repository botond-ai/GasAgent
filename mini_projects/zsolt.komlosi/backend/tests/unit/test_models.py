"""
Unit tests for Pydantic models.
"""

import pytest
from pydantic import ValidationError

from app.models import (
    TicketAnalysis,
    Triage,
    AnswerDraft,
    Citation,
    PolicyCheck,
    SupportAIResponse,
    PIIMatch,
    Message,
)


class TestTicketAnalysis:
    """Tests for TicketAnalysis model."""

    def test_valid_ticket_analysis(self):
        """Test valid ticket analysis creation."""
        analysis = TicketAnalysis(
            language="Hungarian",
            sentiment="frustrated",
            category="Technical",
            priority="P2",
            routing="IT Support",
        )

        assert analysis.language == "Hungarian"
        assert analysis.sentiment == "frustrated"
        assert analysis.priority == "P2"

    def test_invalid_sentiment(self):
        """Test that invalid sentiment raises error."""
        with pytest.raises(ValidationError):
            TicketAnalysis(
                language="Hungarian",
                sentiment="angry",  # Invalid
                category="Technical",
                priority="P2",
                routing="IT Support",
            )

    def test_invalid_category(self):
        """Test that invalid category raises error."""
        with pytest.raises(ValidationError):
            TicketAnalysis(
                language="Hungarian",
                sentiment="neutral",
                category="Invalid",  # Invalid
                priority="P2",
                routing="IT Support",
            )

    def test_invalid_priority(self):
        """Test that invalid priority raises error."""
        with pytest.raises(ValidationError):
            TicketAnalysis(
                language="Hungarian",
                sentiment="neutral",
                category="Technical",
                priority="P5",  # Invalid
                routing="IT Support",
            )

    def test_optional_fields(self):
        """Test that optional fields work correctly."""
        analysis = TicketAnalysis(
            language="English",
            sentiment="satisfied",
            category="General",
            priority="P4",
            routing="General Support",
            subcategory="Feedback",
            confidence=0.95,
        )

        assert analysis.subcategory == "Feedback"
        assert analysis.confidence == 0.95


class TestTriage:
    """Tests for Triage model."""

    def test_valid_triage(self):
        """Test valid triage creation."""
        triage = Triage(
            category="Billing",
            priority="P1",
            sla_hours=4,
            suggested_team="Finance Team",
            sentiment="frustrated",
            language="Hungarian",
            confidence=0.92,
        )

        assert triage.sla_hours == 4
        assert triage.confidence == 0.92

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            Triage(
                category="Billing",
                priority="P1",
                sla_hours=4,
                suggested_team="Finance Team",
                sentiment="frustrated",
                language="Hungarian",
                confidence=1.5,  # Invalid - over 1
            )


class TestAnswerDraft:
    """Tests for AnswerDraft model."""

    def test_valid_answer_draft(self):
        """Test valid answer draft creation."""
        draft = AnswerDraft(
            greeting="Tisztelt Ügyfelünk,",
            body="Köszönjük megkeresését. [#1] A probléma megoldásához...",
            closing="Üdvözlettel,\nSupport Team",
        )

        assert "[#1]" in draft.body
        assert draft.tone == "empathetic_professional"

    def test_tone_options(self):
        """Test different tone options."""
        for tone in ["empathetic_professional", "formal", "friendly", "apologetic", "neutral"]:
            draft = AnswerDraft(
                greeting="Hello",
                body="Content",
                closing="Bye",
                tone=tone,
            )
            assert draft.tone == tone


class TestCitation:
    """Tests for Citation model."""

    def test_valid_citation(self):
        """Test valid citation creation."""
        citation = Citation(
            id=1,
            doc_id="KB-001",
            title="Login Issues",
            excerpt="To reset your password...",
            score=0.89,
        )

        assert citation.id == 1
        assert citation.score == 0.89

    def test_score_bounds(self):
        """Test score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            Citation(
                id=1,
                doc_id="KB-001",
                title="Test",
                excerpt="Test",
                score=1.5,  # Invalid
            )


class TestPolicyCheck:
    """Tests for PolicyCheck model."""

    def test_default_values(self):
        """Test default values are applied."""
        check = PolicyCheck()

        assert check.refund_promise is False
        assert check.sla_mentioned is False
        assert check.escalation_needed is False
        assert check.compliance == "passed"
        assert check.warnings == []

    def test_with_warnings(self):
        """Test policy check with warnings."""
        check = PolicyCheck(
            refund_promise=True,
            compliance="warning",
            warnings=["Refund promised without manager approval"],
        )

        assert check.refund_promise is True
        assert len(check.warnings) == 1


class TestPIIMatch:
    """Tests for PIIMatch model."""

    def test_valid_pii_match(self):
        """Test valid PII match creation."""
        match = PIIMatch(
            type="email",
            original="test@example.com",
            masked="[EMAIL]",
            start=10,
            end=26,
        )

        assert match.type == "email"
        assert match.masked == "[EMAIL]"


class TestMessage:
    """Tests for Message model."""

    def test_valid_message(self):
        """Test valid message creation."""
        msg = Message(
            role="user",
            content="Hello, I need help",
        )

        assert msg.role == "user"
        assert msg.content == "Hello, I need help"
        assert msg.citations == []

    def test_message_with_citations(self):
        """Test message with citations."""
        msg = Message(
            role="assistant",
            content="Here's your answer [#1]",
            citations=[{"id": 1, "doc_id": "KB-001"}],
        )

        assert len(msg.citations) == 1
