"""
Session store using SQLite for persistence.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import uuid

from app.config import get_settings
from app.models import Session, Message, SessionSummary


class SessionStore:
    """
    SQLite-based session store for conversation persistence.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize session store.

        Args:
            db_path: Path to SQLite database. Defaults to config setting.
        """
        settings = get_settings()
        if db_path is None:
            # Extract path from sqlite:/// URL
            db_url = settings.database_url
            if db_url.startswith("sqlite:///"):
                db_path = db_url[10:]
            else:
                db_path = "./data/sessions.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_identifier TEXT,
                    rolling_summary TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_filtered TEXT,
                    citations TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id)
            """)

            conn.commit()

    def create_session(
        self,
        session_id: Optional[str] = None,
        user_identifier: Optional[str] = None,
    ) -> Session:
        """
        Create a new session.

        Args:
            session_id: Optional session ID. Generated if not provided.
            user_identifier: Optional user identifier (hashed).

        Returns:
            Created Session object
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        now = datetime.utcnow()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (id, user_identifier, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, user_identifier, now, now)
            )
            conn.commit()

        return Session(
            id=session_id,
            user_identifier=user_identifier,
            messages=[],
            created_at=now,
            updated_at=now,
        )

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session object or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get session
            cursor.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,)
            )
            session_row = cursor.fetchone()

            if not session_row:
                return None

            # Get messages
            cursor.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
                (session_id,)
            )
            message_rows = cursor.fetchall()

            messages = []
            for row in message_rows:
                messages.append(Message(
                    id=row["id"],
                    role=row["role"],
                    content=row["content"],
                    content_filtered=row["content_filtered"],
                    citations=json.loads(row["citations"]) if row["citations"] else [],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    created_at=datetime.fromisoformat(row["created_at"]),
                ))

            return Session(
                id=session_row["id"],
                user_identifier=session_row["user_identifier"],
                messages=messages,
                rolling_summary=session_row["rolling_summary"],
                metadata=json.loads(session_row["metadata"]) if session_row["metadata"] else {},
                created_at=datetime.fromisoformat(session_row["created_at"]),
                updated_at=datetime.fromisoformat(session_row["updated_at"]),
            )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        content_filtered: Optional[str] = None,
        citations: Optional[List[dict]] = None,
        metadata: Optional[dict] = None,
    ) -> Message:
        """
        Add a message to a session.

        Args:
            session_id: Session ID
            role: Message role (user, assistant, system)
            content: Message content
            content_filtered: PII-filtered content
            citations: List of citations
            metadata: Additional metadata

        Returns:
            Created Message object
        """
        now = datetime.utcnow()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Insert message
            cursor.execute(
                """
                INSERT INTO messages
                (session_id, role, content, content_filtered, citations, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    content,
                    content_filtered,
                    json.dumps(citations) if citations else None,
                    json.dumps(metadata) if metadata else None,
                    now,
                )
            )
            message_id = cursor.lastrowid

            # Update session timestamp
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id)
            )

            conn.commit()

        return Message(
            id=message_id,
            role=role,
            content=content,
            content_filtered=content_filtered,
            citations=citations or [],
            metadata=metadata or {},
            created_at=now,
        )

    def update_summary(self, session_id: str, summary: str) -> None:
        """
        Update the rolling summary for a session.

        Args:
            session_id: Session ID
            summary: New summary text
        """
        now = datetime.utcnow()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET rolling_summary = ?, updated_at = ?
                WHERE id = ?
                """,
                (summary, now, session_id)
            )
            conn.commit()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[SessionSummary]:
        """
        List sessions with summary info.

        Args:
            limit: Maximum number of sessions
            offset: Offset for pagination

        Returns:
            List of SessionSummary objects
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT s.*, COUNT(m.id) as message_count,
                       (SELECT content FROM messages
                        WHERE session_id = s.id
                        ORDER BY created_at DESC LIMIT 1) as last_message
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )

            summaries = []
            for row in cursor.fetchall():
                last_preview = row["last_message"]
                if last_preview and len(last_preview) > 100:
                    last_preview = last_preview[:100] + "..."

                summaries.append(SessionSummary(
                    id=row["id"],
                    message_count=row["message_count"],
                    last_message_preview=last_preview,
                    rolling_summary=row["rolling_summary"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                ))

            return summaries


# Singleton instance
_session_store = None


def get_session_store() -> SessionStore:
    """Get or create the session store singleton."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
