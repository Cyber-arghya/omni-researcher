"""Persistent SQLite session store for non-volatile mission tracking and history lifecycle."""

import json
import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.state.schemas import ResearchState

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("./storage/sessions.db")


class SessionStore:
    """Manages SQLite storage for research sessions and report metadata."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging for high-concurrency read/write
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create sessions table if it doesn't already exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    target_depth INTEGER NOT NULL,
                    current_depth INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    user_constraints TEXT DEFAULT '',
                    total_tokens_used INTEGER DEFAULT 0,
                    estimated_cost_usd REAL DEFAULT 0.0,
                    error_message TEXT DEFAULT '',
                    report_payload_json TEXT DEFAULT '{}',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()

    def upsert_session(
        self, state: ResearchState, report_payload: dict[str, Any] | None = None
    ) -> None:
        """Persist or update a research session state."""
        report_json = json.dumps(report_payload or {})
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, topic, target_depth, current_depth, status,
                    user_constraints, total_tokens_used, estimated_cost_usd,
                    error_message, report_payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    topic = excluded.topic,
                    target_depth = excluded.target_depth,
                    current_depth = excluded.current_depth,
                    status = excluded.status,
                    user_constraints = excluded.user_constraints,
                    total_tokens_used = excluded.total_tokens_used,
                    estimated_cost_usd = excluded.estimated_cost_usd,
                    error_message = excluded.error_message,
                    report_payload_json = CASE
                        WHEN excluded.report_payload_json != '{}' THEN excluded.report_payload_json
                        ELSE sessions.report_payload_json
                    END,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    state.session_id,
                    state.topic,
                    state.target_depth,
                    state.current_depth,
                    state.status,
                    state.user_constraints,
                    state.total_tokens_used,
                    state.estimated_cost_usd,
                    state.error_message or "",
                    report_json,
                ),
            )
            conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve a session by its unique ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None

            data = dict(row)
            try:
                data["report_payload"] = json.loads(data.get("report_payload_json", "{}"))
            except Exception:
                data["report_payload"] = {}
            return data

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List past research sessions ordered by last update."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT session_id, topic, target_depth, current_depth, status,
                       total_tokens_used, estimated_cost_usd, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        """Delete an individual research session."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all(self) -> int:
        """Clear all session records."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions")
            conn.commit()
            return cursor.rowcount
