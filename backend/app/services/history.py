from __future__ import annotations

from ..db.sqlite_store import SQLiteStore
from ..schemas import HistoryAttempt, HistoryResponse


class HistoryService:
    def __init__(self, *, store: SQLiteStore) -> None:
        self.store = store

    def list(self, *, limit: int = 20) -> HistoryResponse:
        attempts = self.store.list_attempts(limit=limit)
        items: list[HistoryAttempt] = []
        for a in attempts:
            items.append(
                HistoryAttempt(
                    attempt_id=a.attempt_id,
                    created_at=a.created_at,
                    expected_text=a.expected_text,
                    transcribed_text=a.transcribed_text,
                    wer=a.wer,
                    accuracy_score=a.accuracy_score,
                    levenshtein_similarity=a.levenshtein_similarity,
                    words=a.words,
                    audio_url=a.audio_url,
                    duration=a.duration,
                    wpm=a.wpm,
                )
            )
        return HistoryResponse(items=items)

    def delete(self, *, attempt_id: int) -> bool:
        return self.store.delete_attempt(attempt_id)

    def clear(self) -> None:
        self.store.delete_all_attempts()

