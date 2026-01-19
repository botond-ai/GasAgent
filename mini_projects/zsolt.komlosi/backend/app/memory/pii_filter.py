"""
PII (Personally Identifiable Information) filter.
Detects and masks sensitive information before logging/storage.
"""

import re
from typing import List, Tuple

from app.models import PIIMatch, PIIFilterResult


class PIIFilter:
    """
    PII detection and masking filter.
    Supports: email, phone, credit card, Hungarian tax ID, etc.
    """

    # Regex patterns for PII detection
    PATTERNS = {
        "email": (
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "[EMAIL]"
        ),
        "phone": (
            r"(?:\+36|06)[\s.-]?(?:\d{1,2})[\s.-]?(?:\d{3})[\s.-]?(?:\d{3,4})",
            "[PHONE]"
        ),
        "phone_intl": (
            r"\+\d{1,3}[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{1,9}",
            "[PHONE]"
        ),
        "credit_card": (
            r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "[CREDIT_CARD]"
        ),
        "hungarian_tax_id": (
            r"\b\d{8}-\d-\d{2}\b",
            "[TAX_ID]"
        ),
        "hungarian_personal_id": (
            r"\b\d{6}[A-Z]{2}\b",
            "[PERSONAL_ID]"
        ),
        "iban": (
            r"\b[A-Z]{2}\d{2}[\s]?(?:\d{4}[\s]?){4,7}\d{0,4}\b",
            "[IBAN]"
        ),
        "ip_address": (
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            "[IP_ADDRESS]"
        ),
    }

    def __init__(self, enabled_types: List[str] = None):
        """
        Initialize PII filter.

        Args:
            enabled_types: List of PII types to detect. If None, all are enabled.
        """
        if enabled_types:
            self.patterns = {k: v for k, v in self.PATTERNS.items() if k in enabled_types}
        else:
            self.patterns = self.PATTERNS.copy()

    def detect(self, text: str) -> List[PIIMatch]:
        """
        Detect PII in text.

        Args:
            text: Text to scan

        Returns:
            List of PIIMatch objects
        """
        matches = []

        for pii_type, (pattern, mask) in self.patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(PIIMatch(
                    type=pii_type if pii_type in ["email", "phone", "credit_card", "name", "address"] else "other",
                    original=match.group(),
                    masked=mask,
                    start=match.start(),
                    end=match.end(),
                ))

        # Sort by position
        matches.sort(key=lambda x: x.start)

        return matches

    def filter(self, text: str) -> PIIFilterResult:
        """
        Detect and mask PII in text.

        Args:
            text: Text to filter

        Returns:
            PIIFilterResult with filtered text and matches
        """
        matches = self.detect(text)

        if not matches:
            return PIIFilterResult(
                original_text=text,
                filtered_text=text,
                matches=[],
                has_pii=False,
            )

        # Apply masks from end to start to preserve positions
        filtered_text = text
        for match in reversed(matches):
            filtered_text = (
                filtered_text[:match.start] +
                match.masked +
                filtered_text[match.end:]
            )

        return PIIFilterResult(
            original_text=text,
            filtered_text=filtered_text,
            matches=matches,
            has_pii=True,
        )

    def mask_for_logging(self, text: str) -> str:
        """
        Quick mask for logging purposes.

        Args:
            text: Text to mask

        Returns:
            Masked text
        """
        return self.filter(text).filtered_text


# Singleton instance
_pii_filter = None


def get_pii_filter() -> PIIFilter:
    """Get or create the PII filter singleton."""
    global _pii_filter
    if _pii_filter is None:
        _pii_filter = PIIFilter()
    return _pii_filter
