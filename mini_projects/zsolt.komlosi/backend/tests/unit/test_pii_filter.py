"""
Unit tests for PII filter.
"""

import pytest
from app.memory.pii_filter import PIIFilter, get_pii_filter


class TestPIIFilter:
    """Tests for PII detection and masking."""

    def test_detect_email(self):
        """Test email detection."""
        pii_filter = PIIFilter()
        text = "Contact me at test@example.com please."
        matches = pii_filter.detect(text)

        assert len(matches) == 1
        assert matches[0].type == "email"
        assert matches[0].original == "test@example.com"

    def test_detect_hungarian_phone(self):
        """Test Hungarian phone number detection."""
        pii_filter = PIIFilter()
        text = "Hívj a +36 30 123 4567 számon."
        matches = pii_filter.detect(text)

        assert len(matches) >= 1
        phone_matches = [m for m in matches if "PHONE" in m.masked]
        assert len(phone_matches) >= 1

    def test_detect_credit_card(self):
        """Test credit card detection."""
        pii_filter = PIIFilter()
        text = "A kártyaszámom: 4111-2222-3333-4444"
        matches = pii_filter.detect(text)

        card_matches = [m for m in matches if m.masked == "[CREDIT_CARD]"]
        assert len(card_matches) == 1

    def test_filter_masks_all_pii(self, sample_pii_text):
        """Test that filter masks all PII in text."""
        pii_filter = PIIFilter()
        result = pii_filter.filter(sample_pii_text)

        assert result.has_pii is True
        assert len(result.matches) >= 3  # email, phone, credit card

        # Check that original values are not in filtered text
        assert "kovacs.janos@example.com" not in result.filtered_text
        assert "[EMAIL]" in result.filtered_text

    def test_filter_preserves_non_pii_text(self):
        """Test that non-PII text is preserved."""
        pii_filter = PIIFilter()
        text = "Ez egy normális szöveg PII nélkül."
        result = pii_filter.filter(text)

        assert result.has_pii is False
        assert result.filtered_text == text
        assert len(result.matches) == 0

    def test_mask_for_logging(self):
        """Test quick masking for logging."""
        pii_filter = PIIFilter()
        text = "Email: test@test.com"
        masked = pii_filter.mask_for_logging(text)

        assert "test@test.com" not in masked
        assert "[EMAIL]" in masked

    def test_singleton_pattern(self):
        """Test that get_pii_filter returns same instance."""
        filter1 = get_pii_filter()
        filter2 = get_pii_filter()
        assert filter1 is filter2

    def test_enabled_types_filter(self):
        """Test filtering with only specific PII types enabled."""
        pii_filter = PIIFilter(enabled_types=["email"])
        text = "Email: test@test.com, Phone: +36 30 123 4567"
        matches = pii_filter.detect(text)

        # Should only detect email, not phone
        assert len(matches) == 1
        assert matches[0].type == "email"

    def test_ip_address_detection(self):
        """Test IP address detection."""
        pii_filter = PIIFilter()
        text = "User IP: 192.168.1.1"
        matches = pii_filter.detect(text)

        ip_matches = [m for m in matches if m.masked == "[IP_ADDRESS]"]
        assert len(ip_matches) == 1
