"""Egységtesztek a VersionStore-hoz.

Tesztek:
- Verziókövetés mentése/betöltése
- Változásérzékelés
- Törlés
- Tartósság példányok között
"""
import pytest
from pathlib import Path
import tempfile

from rag.ingestion.version_store import VersionStore


def test_version_store_new_document():
    """Új dokumentum követése."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "versions.json"
        store = VersionStore(store_path)
        
        # Kezdetben üres
        assert store.get_version("doc1") is None
        assert store.has_changed("doc1", "hash123")
        
        # Dokumentum hozzáadása
        store.update("doc1", "hash123", "/path/to/doc1.pdf", 10)
        
        # Most már követve van
        assert store.get_version("doc1") == "hash123"
        assert not store.has_changed("doc1", "hash123")


def test_version_store_change_detection():
    """Észleli, ha a dokumentum hash-e megváltozik."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "versions.json"
        store = VersionStore(store_path)
        
        store.update("doc1", "hash_v1", "/path/to/doc1.pdf", 10)
        
        # Azonos hash => nincs változás
        assert not store.has_changed("doc1", "hash_v1")
        
        # Eltérő hash => változott
        assert store.has_changed("doc1", "hash_v2")


def test_version_store_persistence():
    """A verziótár példányok között is megmarad."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "versions.json"
        
        # Első példány
        store1 = VersionStore(store_path)
        store1.update("doc1", "hash123", "/path/doc1.pdf", 5)
        
        # Második példány (betöltés lemezről)
        store2 = VersionStore(store_path)
        assert store2.get_version("doc1") == "hash123"


def test_version_store_removal():
    """Dokumentum eltávolítása a követésből."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "versions.json"
        store = VersionStore(store_path)
        
        store.update("doc1", "hash123", "/path/doc1.pdf", 5)
        assert store.get_version("doc1") == "hash123"
        
        store.remove("doc1")
        assert store.get_version("doc1") is None


def test_version_store_list_all():
    """Összes követett doc_id listázása."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "versions.json"
        store = VersionStore(store_path)
        
        store.update("doc1", "hash1", "/path/doc1.pdf", 5)
        store.update("doc2", "hash2", "/path/doc2.pdf", 3)
        
        doc_ids = store.get_all_doc_ids()
        assert set(doc_ids) == {"doc1", "doc2"}


def test_version_store_clear():
    """Minden verzióadat törlése."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "versions.json"
        store = VersionStore(store_path)
        
        store.update("doc1", "hash1", "/path/doc1.pdf", 5)
        store.update("doc2", "hash2", "/path/doc2.pdf", 3)
        
        store.clear()
        assert len(store.get_all_doc_ids()) == 0
