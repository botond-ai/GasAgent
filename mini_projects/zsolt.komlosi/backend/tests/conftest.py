"""
Pytest configuration and fixtures.
"""

import os
import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"
os.environ["DATABASE_URL"] = "sqlite:///./test_sessions.db"
os.environ["JIRA_WEBHOOK_SECRET"] = ""  # Disable webhook auth for tests


@pytest.fixture
def sample_ticket_text():
    """Sample Hungarian support ticket."""
    return "Nem tudok bejelentkezni a fiókba. A jelszó visszaállítás sem működik!"


@pytest.fixture
def sample_document_content():
    """Sample document for testing."""
    return """
    # Bejelentkezési problémák megoldása

    Ha nem tudsz bejelentkezni, kövesd az alábbi lépéseket:

    1. Ellenőrizd az e-mail címet
    2. Próbáld meg a jelszó visszaállítást
    3. Töröld a böngésző sütiket
    4. Próbálj másik böngészőt

    Ha továbbra sem működik, vedd fel velünk a kapcsolatot.
    """


@pytest.fixture
def sample_messages():
    """Sample conversation messages."""
    return [
        {"role": "user", "content": "Nem működik a bejelentkezés"},
        {"role": "assistant", "content": "Sajnálom a problémát. Próbálta már a jelszó visszaállítást?"},
        {"role": "user", "content": "Igen, de az sem működik"},
    ]


@pytest.fixture
def sample_pii_text():
    """Sample text with PII for testing."""
    return """
    Szia, a nevem Kovács János, az e-mail címem kovacs.janos@example.com,
    a telefonszámom +36 30 123 4567.
    A bankkártya számom 4111-2222-3333-4444.
    """
