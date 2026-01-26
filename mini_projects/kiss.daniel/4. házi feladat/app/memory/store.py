"""
Memory store for deduplication and context retrieval.
Implements retrieval-before-tools pattern.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)


class Match(BaseModel):
    """A match result from memory search."""
    run_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    notes_hash: str
    summary: Optional[str] = None
    event_details: Optional[dict] = None
    created_event_id: Optional[str] = None
    timestamp: datetime


class RunRecord(BaseModel):
    """A record of a single agent run."""
    run_id: str
    notes_hash: str
    notes_text_preview: str = Field(max_length=200)
    summary: Optional[str] = None
    event_details: Optional[dict] = None
    created_event_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    embedding: Optional[list[float]] = None


class MemoryStore(ABC):
    """
    Abstract base class for memory storage.
    Supports deduplication and similarity search.
    """
    
    @abstractmethod
    def upsert_run(
        self,
        run_id: str,
        notes_hash: str,
        notes_text: str,
        summary: Optional[str] = None,
        event_details: Optional[dict] = None,
        created_event_id: Optional[str] = None,
        embedding: Optional[list[float]] = None,
    ) -> None:
        """
        Store or update a run record.
        
        Args:
            run_id: Unique run identifier
            notes_hash: Hash of the notes text
            notes_text: Original notes (will be truncated for preview)
            summary: Generated summary
            event_details: Extracted event details dict
            created_event_id: ID of created calendar event
            embedding: Optional embedding vector
        """
        pass
    
    @abstractmethod
    def find_similar_notes(self, notes_text: str, embedding: Optional[list[float]] = None) -> list[Match]:
        """
        Find runs with similar notes.
        
        Args:
            notes_text: Notes to search for
            embedding: Optional embedding vector for similarity
            
        Returns:
            List of matches sorted by similarity (highest first)
        """
        pass
    
    @abstractmethod
    def find_similar_event_candidate(self, event_details: dict) -> list[Match]:
        """
        Find runs with similar event candidates.
        
        Args:
            event_details: Event details dict to compare
            
        Returns:
            List of matches sorted by similarity
        """
        pass
    
    @abstractmethod
    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Get a specific run by ID."""
        pass


class InMemoryStore(MemoryStore):
    """In-memory implementation of MemoryStore."""
    
    def __init__(self):
        self._records: dict[str, RunRecord] = {}
        self._hash_index: dict[str, list[str]] = {}  # notes_hash -> [run_ids]
    
    def upsert_run(
        self,
        run_id: str,
        notes_hash: str,
        notes_text: str,
        summary: Optional[str] = None,
        event_details: Optional[dict] = None,
        created_event_id: Optional[str] = None,
        embedding: Optional[list[float]] = None,
    ) -> None:
        """Store or update a run record in memory."""
        record = RunRecord(
            run_id=run_id,
            notes_hash=notes_hash,
            notes_text_preview=notes_text[:200],
            summary=summary,
            event_details=event_details,
            created_event_id=created_event_id,
            embedding=embedding,
        )
        self._records[run_id] = record
        
        # Update hash index
        if notes_hash not in self._hash_index:
            self._hash_index[notes_hash] = []
        if run_id not in self._hash_index[notes_hash]:
            self._hash_index[notes_hash].append(run_id)
        
        logger.debug(f"Stored run {run_id} with hash {notes_hash[:8]}...")
    
    def find_similar_notes(self, notes_text: str, embedding: Optional[list[float]] = None) -> list[Match]:
        """Find runs with similar notes using hash and optional embedding."""
        matches = []
        
        # Compute hash
        normalized = " ".join(notes_text.lower().split())
        notes_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        
        # Exact hash match
        if notes_hash in self._hash_index:
            for run_id in self._hash_index[notes_hash]:
                record = self._records.get(run_id)
                if record:
                    matches.append(Match(
                        run_id=run_id,
                        similarity=1.0,
                        notes_hash=record.notes_hash,
                        summary=record.summary,
                        event_details=record.event_details,
                        created_event_id=record.created_event_id,
                        timestamp=record.timestamp,
                    ))
        
        # Embedding-based similarity if available
        if embedding and not matches:
            matches.extend(self._find_by_embedding(embedding))
        
        return sorted(matches, key=lambda m: m.similarity, reverse=True)
    
    def _find_by_embedding(self, query_embedding: list[float], threshold: float = 0.85) -> list[Match]:
        """Find similar records by embedding cosine similarity."""
        matches = []
        
        for record in self._records.values():
            if record.embedding:
                similarity = self._cosine_similarity(query_embedding, record.embedding)
                if similarity >= threshold:
                    matches.append(Match(
                        run_id=record.run_id,
                        similarity=similarity,
                        notes_hash=record.notes_hash,
                        summary=record.summary,
                        event_details=record.event_details,
                        created_event_id=record.created_event_id,
                        timestamp=record.timestamp,
                    ))
        
        return matches
    
    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def find_similar_event_candidate(self, event_details: dict) -> list[Match]:
        """Find runs with similar event candidates."""
        matches = []
        
        title = event_details.get("title", "")
        start = event_details.get("start_datetime", "")
        
        for record in self._records.values():
            if not record.event_details:
                continue
            
            # Check title similarity
            record_title = record.event_details.get("title", "")
            title_sim = self._title_similarity(title, record_title)
            
            # Check start time match
            record_start = record.event_details.get("start_datetime", "")
            time_match = str(start) == str(record_start) if start and record_start else False
            
            # Combined similarity
            if title_sim > 0.5 or (title_sim > 0.3 and time_match):
                similarity = title_sim * 0.7 + (0.3 if time_match else 0.0)
                matches.append(Match(
                    run_id=record.run_id,
                    similarity=min(similarity, 1.0),
                    notes_hash=record.notes_hash,
                    summary=record.summary,
                    event_details=record.event_details,
                    created_event_id=record.created_event_id,
                    timestamp=record.timestamp,
                ))
        
        return sorted(matches, key=lambda m: m.similarity, reverse=True)
    
    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """Simple word-overlap title similarity."""
        if not a or not b:
            return 0.0
        
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        
        if not words_a or not words_b:
            return 0.0
        
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        
        return intersection / union if union > 0 else 0.0
    
    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Get a specific run by ID."""
        return self._records.get(run_id)


class FileBasedStore(InMemoryStore):
    """
    File-based implementation that persists to JSON.
    Extends InMemoryStore with file persistence.
    """
    
    def __init__(self, file_path: Optional[str] = None):
        super().__init__()
        settings = get_settings()
        self.file_path = Path(file_path or settings.memory_store_path)
        self._load()
    
    def _load(self) -> None:
        """Load records from file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r") as f:
                    data = json.load(f)
                
                for record_data in data.get("records", []):
                    record = RunRecord.model_validate(record_data)
                    self._records[record.run_id] = record
                    
                    if record.notes_hash not in self._hash_index:
                        self._hash_index[record.notes_hash] = []
                    if record.run_id not in self._hash_index[record.notes_hash]:
                        self._hash_index[record.notes_hash].append(record.run_id)
                
                logger.info(f"Loaded {len(self._records)} records from {self.file_path}")
            except Exception as e:
                logger.warning(f"Failed to load memory store: {e}")
    
    def _save(self) -> None:
        """Save records to file."""
        try:
            data = {
                "records": [r.model_dump(mode="json") for r in self._records.values()]
            }
            with open(self.file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            logger.debug(f"Saved {len(self._records)} records to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save memory store: {e}")
    
    def upsert_run(self, *args, **kwargs) -> None:
        """Store and persist a run record."""
        super().upsert_run(*args, **kwargs)
        self._save()


def get_memory_store() -> MemoryStore:
    """Get the configured memory store instance."""
    settings = get_settings()
    return FileBasedStore(settings.memory_store_path)
