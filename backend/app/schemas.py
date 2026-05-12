from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluateResponseWord(BaseModel):
    index: int = Field(..., ge=0)
    expected: str | None
    recognized: str | None
    ok: bool
    # Human-friendly explanation for UI tooltips.
    feedback: str | None = None
    # Phoneme-level similarity (0..1) when both sides have phonemes.
    phoneme_similarity: float | None = None
    # Suggested improvement wording for this word.
    suggestion: str | None = None


class EvaluateResponse(BaseModel):
    expected_text: str
    transcribed_text: str
    has_expected: bool = True
    wer: float = Field(..., ge=0)
    accuracy_score: float = Field(..., ge=0, le=100)
    levenshtein_similarity: float = Field(..., ge=0, le=1)

    # Token-level results aligned to the expected words.
    words: list[EvaluateResponseWord]
    suggestions: list[str] = []
    grammar_issues: list[str] = []
    corrected_text: str | None = None

    # Subset of `words` where ok == False.
    mispronounced_words: list[EvaluateResponseWord]

    created_at: datetime
    attempt_id: int
    audio_url: str | None = None
    duration: float | None = None
    wpm: float | None = None
    feedback: str | None = None
    ai_feedback: str | None = None


class HistoryAttempt(BaseModel):
    attempt_id: int
    audio_url: str | None = None
    duration: float | None = None
    wpm: float | None = None
    feedback: str | None = None
    created_at: datetime
    expected_text: str
    transcribed_text: str
    wer: float
    accuracy_score: float
    levenshtein_similarity: float

    # Raw analysis payloads stored for later display.
    words: list[dict[str, Any]] = []


class HistoryResponse(BaseModel):
    items: list[HistoryAttempt]

