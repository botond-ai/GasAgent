"""
Unit tests for memory store.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from app.memory.store import (
    MemoryStore,
    InMemoryStore,
    FileBasedStore,
    Match,
    RunRecord,
)


class TestInMemoryStore:
    """Tests for InMemoryStore."""
    
    @pytest.fixture
    def store(self):
        """Create an in-memory store."""
        return InMemoryStore()
    
    def test_upsert_and_get_run(self, store):
        """Test storing and retrieving a run."""
        store.upsert_run(
            run_id="test-123",
            notes_hash="abc123",
            notes_text="Test meeting notes",
            summary="Test summary",
            event_details={"title": "Test Event"},
            created_event_id="event-456",
        )
        
        record = store.get_run("test-123")
        
        assert record is not None
        assert record.run_id == "test-123"
        assert record.notes_hash == "abc123"
        assert record.summary == "Test summary"
        assert record.created_event_id == "event-456"
    
    def test_get_nonexistent_run(self, store):
        """Test getting a run that doesn't exist."""
        record = store.get_run("nonexistent")
        assert record is None
    
    def test_find_similar_notes_exact_hash(self, store):
        """Test finding notes by exact hash match."""
        store.upsert_run(
            run_id="run-1",
            notes_hash="abc123",
            notes_text="Test meeting notes",
            summary="Summary 1",
        )
        
        # Search with same text (will produce same hash)
        matches = store.find_similar_notes("Test meeting notes")
        
        assert len(matches) == 1
        assert matches[0].run_id == "run-1"
        assert matches[0].similarity == 1.0
    
    def test_find_similar_notes_no_match(self, store):
        """Test finding notes with no match."""
        store.upsert_run(
            run_id="run-1",
            notes_hash="abc123",
            notes_text="Original notes",
        )
        
        matches = store.find_similar_notes("Completely different text")
        
        assert len(matches) == 0
    
    def test_find_similar_event_candidate(self, store):
        """Test finding similar event candidates."""
        store.upsert_run(
            run_id="run-1",
            notes_hash="abc123",
            notes_text="Notes",
            event_details={
                "title": "Sprint Planning Meeting",
                "start_datetime": "2026-01-20T10:00:00",
            },
        )
        
        # Search with similar title
        matches = store.find_similar_event_candidate({
            "title": "Sprint Planning",
            "start_datetime": "2026-01-20T10:00:00",
        })
        
        assert len(matches) > 0
        assert matches[0].similarity > 0.5
    
    def test_cosine_similarity(self, store):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        vec3 = [0.0, 1.0, 0.0]
        
        # Same vectors
        assert store._cosine_similarity(vec1, vec2) == 1.0
        # Orthogonal vectors
        assert store._cosine_similarity(vec1, vec3) == 0.0
    
    def test_title_similarity(self, store):
        """Test title similarity calculation."""
        # Exact match
        assert store._title_similarity("Test Meeting", "Test Meeting") == 1.0
        # Partial match
        sim = store._title_similarity("Sprint Planning Meeting", "Sprint Planning")
        assert 0.5 < sim < 1.0
        # No match
        assert store._title_similarity("Meeting A", "Conference B") < 0.5


class TestFileBasedStore:
    """Tests for FileBasedStore."""
    
    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for the store."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            yield Path(f.name)
    
    @pytest.fixture
    def store(self, temp_file):
        """Create a file-based store."""
        return FileBasedStore(str(temp_file))
    
    def test_persistence(self, temp_file):
        """Test that data persists to file."""
        # Create store and add data
        store1 = FileBasedStore(str(temp_file))
        store1.upsert_run(
            run_id="persist-test",
            notes_hash="xyz789",
            notes_text="Persistent notes",
            summary="Persistent summary",
        )
        
        # Create new store instance (should load from file)
        store2 = FileBasedStore(str(temp_file))
        record = store2.get_run("persist-test")
        
        assert record is not None
        assert record.summary == "Persistent summary"
    
    def test_file_format(self, store, temp_file):
        """Test that file is valid JSON."""
        store.upsert_run(
            run_id="format-test",
            notes_hash="abc",
            notes_text="Test",
        )
        
        # Read and parse file
        with open(temp_file) as f:
            data = json.load(f)
        
        assert "records" in data
        assert len(data["records"]) == 1
        assert data["records"][0]["run_id"] == "format-test"
    
    def test_load_empty_file(self, temp_file):
        """Test loading from non-existent file."""
        temp_file.unlink()  # Delete the file
        
        # Should create empty store without error
        store = FileBasedStore(str(temp_file))
        
        assert store.get_run("anything") is None


class TestMatch:
    """Tests for Match model."""
    
    def test_match_creation(self):
        """Test creating a match result."""
        match = Match(
            run_id="test-run",
            similarity=0.95,
            notes_hash="abc123",
            summary="Test summary",
            timestamp=datetime.now(),
        )
        
        assert match.run_id == "test-run"
        assert match.similarity == 0.95
    
    def test_similarity_bounds(self):
        """Test that similarity is bounded 0-1."""
        with pytest.raises(Exception):
            Match(
                run_id="test",
                similarity=1.5,
                notes_hash="abc",
                timestamp=datetime.now(),
            )
