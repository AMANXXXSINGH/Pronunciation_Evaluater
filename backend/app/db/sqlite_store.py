from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AttemptRow:
    attempt_id: int
    created_at: datetime
    expected_text: str
    transcribed_text: str
    wer: float
    accuracy_score: float
    levenshtein_similarity: float
    words: list[dict[str, Any]]
    audio_url: str | None = None
    duration: float | None = None
    wpm: float | None = None
    feedback: str | None = None
    ai_feedback: str | None = None


class SQLiteStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        # `detect_types` helps with datetime parsing when needed.
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    expected_text TEXT NOT NULL,
                    transcribed_text TEXT NOT NULL,
                    wer REAL NOT NULL,
                    accuracy_score REAL NOT NULL,
                    levenshtein_similarity REAL NOT NULL,
                    words_json TEXT NOT NULL
                );
                """
            )
            columns = [
                ("audio_url", "TEXT"),
                ("duration", "REAL"),
                ("wpm", "REAL"),
                ("feedback", "TEXT"),
                ("ai_feedback", "TEXT")
            ]
            for col_name, col_type in columns:
                try:
                    conn.execute(f"ALTER TABLE attempts ADD COLUMN {col_name} {col_type};")
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    def create_attempt(
        self,
        *,
        expected_text: str,
        transcribed_text: str,
        wer: float,
        accuracy_score: float,
        levenshtein_similarity: float,
        words: list[dict[str, Any]],
        audio_url: str | None = None,
        duration: float | None = None,
        wpm: float | None = None,
        feedback: str | None = None,
        ai_feedback: str | None = None,
    ) -> tuple[int, datetime]:
        created_at_dt = datetime.now(timezone.utc)
        created_at = created_at_dt.isoformat()
        payload = json.dumps(words, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO attempts (
                    created_at,
                    expected_text,
                    transcribed_text,
                    wer,
                    accuracy_score,
                    levenshtein_similarity,
                    words_json,
                    audio_url,
                    duration,
                    wpm,
                    feedback,
                    ai_feedback
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    expected_text,
                    transcribed_text,
                    wer,
                    accuracy_score,
                    levenshtein_similarity,
                    payload,
                    audio_url,
                    duration,
                    wpm,
                    feedback,
                    ai_feedback,
                ),
            )
            conn.commit()
            return int(cur.lastrowid), created_at_dt

    def list_attempts(self, limit: int = 20) -> list[AttemptRow]:
        limit = max(1, min(int(limit), 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    attempt_id,
                    created_at,
                    expected_text,
                    transcribed_text,
                    wer,
                    accuracy_score,
                    levenshtein_similarity,
                    words_json,
                    audio_url,
                    duration,
                    wpm,
                    feedback,
                    ai_feedback
                FROM attempts
                ORDER BY attempt_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        items: list[AttemptRow] = []
        for r in rows:
            created_at = datetime.fromisoformat(r["created_at"])
            words_json = r["words_json"]
            words = json.loads(words_json) if words_json else []
            
            # Safe parsing for newly added columns
            audio_url = r["audio_url"] if "audio_url" in r.keys() else None
            duration = float(r["duration"]) if "duration" in r.keys() and r["duration"] is not None else None
            wpm = float(r["wpm"]) if "wpm" in r.keys() and r["wpm"] is not None else None
            feedback = r["feedback"] if "feedback" in r.keys() else None
            ai_feedback = r["ai_feedback"] if "ai_feedback" in r.keys() else None

            items.append(
                AttemptRow(
                    attempt_id=int(r["attempt_id"]),
                    created_at=created_at,
                    expected_text=r["expected_text"],
                    transcribed_text=r["transcribed_text"],
                    wer=float(r["wer"]),
                    accuracy_score=float(r["accuracy_score"]),
                    levenshtein_similarity=float(r["levenshtein_similarity"]),
                    words=words,
                    audio_url=audio_url,
                    duration=duration,
                    wpm=wpm,
                    feedback=feedback,
                    ai_feedback=ai_feedback,
                )
            )
        return items

    def delete_attempt(self, attempt_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM attempts WHERE attempt_id = ?",
                (attempt_id,)
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_all_attempts(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM attempts")
            conn.commit()
