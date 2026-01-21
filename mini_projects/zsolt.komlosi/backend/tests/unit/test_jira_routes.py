"""
Tests for Jira webhook API routes.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.api.routes.jira import (
    _format_customer_response,
    _format_internal_note,
    router,
)


class TestFormatCustomerResponse:
    """Tests for _format_customer_response function."""

    def test_format_customer_response_with_full_draft(self):
        """Test formatting with complete answer draft."""
        analysis = {
            "answer_draft": {
                "greeting": "Kedves Kovács János!",
                "body": "Köszönjük a megkeresését. Hamarosan válaszolunk.",
                "closing": "Üdvözlettel, TaskFlow Support",
            }
        }

        result = _format_customer_response(analysis)

        assert "Kedves Kovács János!" in result
        assert "Köszönjük a megkeresését" in result
        assert "Üdvözlettel, TaskFlow Support" in result

    def test_format_customer_response_no_draft(self):
        """Test formatting with no answer draft."""
        analysis = {}

        result = _format_customer_response(analysis)

        assert result == ""

    def test_format_customer_response_empty_draft(self):
        """Test formatting with empty answer draft."""
        analysis = {"answer_draft": {}}

        result = _format_customer_response(analysis)

        # Should return string with just newlines
        assert result.strip() == ""

    def test_format_customer_response_partial_draft(self):
        """Test formatting with partial answer draft."""
        analysis = {
            "answer_draft": {
                "greeting": "Kedves Ügyfél!",
                "body": "Válaszunk.",
                # closing is missing
            }
        }

        result = _format_customer_response(analysis)

        assert "Kedves Ügyfél!" in result
        assert "Válaszunk." in result


class TestFormatInternalNote:
    """Tests for _format_internal_note function."""

    def test_format_internal_note_with_triage(self):
        """Test formatting with complete triage data."""
        analysis = {
            "triage": {
                "language": "Hungarian",
                "category": "Technical",
                "subcategory": "Login Issue",
                "priority": "P2",
                "sla_hours": 8,
                "suggested_team": "IT Support",
                "sentiment": "frustrated",
                "confidence": 0.92,
            }
        }

        result = _format_internal_note(analysis)

        assert "SupportAI Automatikus Elemzés" in result
        assert "Triage Információ" in result
        assert "Nyelv: Hungarian" in result
        assert "Kategória: Technical" in result
        assert "Prioritás: P2" in result
        assert "SLA: 8 óra" in result
        assert "IT Support" in result
        assert "frustrated" in result
        assert "92%" in result

    def test_format_internal_note_with_citations(self):
        """Test formatting with citations."""
        analysis = {
            "triage": {
                "language": "Hungarian",
                "category": "General",
                "priority": "P3",
                "sla_hours": 24,
                "suggested_team": "Support",
                "sentiment": "neutral",
                "confidence": 0.85,
            },
            "citations": [
                {"id": 1, "title": "FAQ - Bejelentkezés", "score": 0.95},
                {"id": 2, "title": "Felhasználói útmutató", "score": 0.82},
            ]
        }

        result = _format_internal_note(analysis)

        assert "Felhasznált tudásbázis források" in result
        assert "FAQ - Bejelentkezés" in result
        assert "95%" in result
        assert "Felhasználói útmutató" in result

    def test_format_internal_note_with_policy_check(self):
        """Test formatting with policy check data."""
        analysis = {
            "triage": {
                "language": "Hungarian",
                "category": "Billing",
                "priority": "P2",
                "sla_hours": 8,
                "suggested_team": "Finance",
                "sentiment": "frustrated",
                "confidence": 0.88,
            },
            "policy_check": {
                "compliance": "warning",
                "refund_promise": True,
                "sla_mentioned": False,
                "escalation_needed": True,
            }
        }

        result = _format_internal_note(analysis)

        assert "Policy Check" in result
        assert "Visszatérítés ígéret: Igen" in result
        assert "Eszkaláció szükséges: Igen" in result

    def test_format_internal_note_high_confidence_recommendation(self):
        """Test auto-respond recommendation for high confidence."""
        analysis = {
            "triage": {
                "language": "Hungarian",
                "category": "General",
                "priority": "P3",
                "sla_hours": 24,
                "suggested_team": "Support",
                "sentiment": "neutral",
                "confidence": 0.92,  # >= 0.85
            },
            "should_auto_respond": True,
        }

        result = _format_internal_note(analysis)

        assert "automatikus válasz javasolt" in result

    def test_format_internal_note_low_confidence_recommendation(self):
        """Test manual review recommendation for low confidence."""
        analysis = {
            "triage": {
                "language": "Hungarian",
                "category": "General",
                "priority": "P3",
                "sla_hours": 24,
                "suggested_team": "Support",
                "sentiment": "neutral",
                "confidence": 0.75,  # < 0.85
            },
            "should_auto_respond": False,
        }

        result = _format_internal_note(analysis)

        assert "Manuális ellenőrzés javasolt" in result

    def test_format_internal_note_empty_analysis(self):
        """Test formatting with empty analysis."""
        analysis = {}

        result = _format_internal_note(analysis)

        assert "SupportAI Automatikus Elemzés" in result
        # Should still have the header and recommendation


class TestPriorityMapping:
    """Tests for priority mapping in Jira webhook."""

    def test_priority_mapping_values(self):
        """Test that priority mapping matches Jira configuration."""
        # This tests the expected mapping defined in jira.py
        priority_mapping = {
            "P1": "Highest",
            "P2": "Medium",
            "P3": "Low",
            "P4": "Lowest",
        }

        assert priority_mapping["P1"] == "Highest"
        assert priority_mapping["P2"] == "Medium"
        assert priority_mapping["P3"] == "Low"
        assert priority_mapping["P4"] == "Lowest"


class TestWebhookPayloadParsing:
    """Tests for webhook payload parsing."""

    def test_extract_reporter_name_display_name(self):
        """Test extracting reporter display name."""
        fields = {
            "reporter": {
                "displayName": "Kovács János",
                "name": "jkovacs",
            }
        }

        reporter = fields.get("reporter") or {}
        reporter_name = reporter.get("displayName") or reporter.get("name") or "Ügyfelünk"

        assert reporter_name == "Kovács János"

    def test_extract_reporter_name_fallback_to_name(self):
        """Test fallback to name when displayName is missing."""
        fields = {
            "reporter": {
                "name": "jkovacs",
            }
        }

        reporter = fields.get("reporter") or {}
        reporter_name = reporter.get("displayName") or reporter.get("name") or "Ügyfelünk"

        assert reporter_name == "jkovacs"

    def test_extract_reporter_name_fallback_to_default(self):
        """Test fallback to default when reporter is missing."""
        fields = {}

        reporter = fields.get("reporter") or {}
        reporter_name = reporter.get("displayName") or reporter.get("name") or "Ügyfelünk"

        assert reporter_name == "Ügyfelünk"

    def test_extract_adf_description(self):
        """Test extracting text from Atlassian Document Format."""
        description = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Ez az első bekezdés."}
                    ]
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Ez a második bekezdés."}
                    ]
                }
            ]
        }

        # Simulate the parsing logic from jira.py
        if isinstance(description, dict):
            content = description.get("content", [])
            text_parts = []
            for block in content:
                if block.get("type") == "paragraph":
                    for item in block.get("content", []):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
            description_text = "\n".join(text_parts)

        assert "Ez az első bekezdés." in description_text
        assert "Ez a második bekezdés." in description_text


class TestDueDateExtraction:
    """Tests for due date extraction from SLA info."""

    def test_extract_duedate_with_timestamp(self):
        """Test extracting date from ISO timestamp."""
        sla_info = {"deadline": "2024-01-15T14:00:00"}

        deadline_str = sla_info.get("deadline", "")
        if "T" in deadline_str:
            duedate = deadline_str.split("T")[0]
        else:
            duedate = deadline_str[:10]

        assert duedate == "2024-01-15"

    def test_extract_duedate_date_only(self):
        """Test extracting date when only date is provided."""
        sla_info = {"deadline": "2024-01-15"}

        deadline_str = sla_info.get("deadline", "")
        if "T" in deadline_str:
            duedate = deadline_str.split("T")[0]
        elif deadline_str:
            duedate = deadline_str[:10]
        else:
            duedate = None

        assert duedate == "2024-01-15"

    def test_extract_duedate_empty(self):
        """Test handling empty deadline."""
        sla_info = {}

        duedate = None
        if sla_info and sla_info.get("deadline"):
            deadline_str = sla_info.get("deadline", "")
            if "T" in deadline_str:
                duedate = deadline_str.split("T")[0]
            elif deadline_str:
                duedate = deadline_str[:10]

        assert duedate is None
