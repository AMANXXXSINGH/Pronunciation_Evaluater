from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import nltk
from nltk.corpus import cmudict


_TRAILING_DIGIT_RE = re.compile(r"\d$")


def _strip_stress(phoneme: str) -> str:
    # CMU dict uses stress markers like AH0/AH1; strip trailing digits for comparison.
    return _TRAILING_DIGIT_RE.sub("", phoneme)


def _levenshtein_distance_seq(a: list[str], b: list[str]) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    if len(a) < len(b):
        s1, s2 = a, b
    else:
        s1, s2 = b, a

    previous = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, start=1):
        current = [i]
        for j, c2 in enumerate(s2, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            sub_cost = previous[j - 1] + (0 if c1 == c2 else 1)
            current.append(min(insert_cost, delete_cost, sub_cost))
        previous = current
    return previous[-1]


def _similarity_from_distance(dist: int, len_a: int, len_b: int) -> float:
    denom = max(1, max(len_a, len_b))
    return max(0.0, 1.0 - (dist / denom))


@dataclass(frozen=True)
class PhonemeMatch:
    expected_phonemes: list[str] | None
    recognized_phonemes: list[str] | None
    similarity: float | None
    message: str


class PhonemeComparator:
    def __init__(self, *, download_if_missing: bool = True) -> None:
        self._download_if_missing = download_if_missing
        self._cmu = None

    def _ensure_loaded(self) -> None:
        if self._cmu is not None:
            return
        try:
            self._cmu = cmudict.dict()
        except LookupError:
            if not self._download_if_missing:
                raise
            nltk.download("cmudict", quiet=True)
            self._cmu = cmudict.dict()

    def phonemes_for_word(self, word: str) -> list[str] | None:
        self._ensure_loaded()
        if not word:
            return None
        key = word.strip().lower()
        # CMU dict key doesn't include punctuation; keep it simple.
        key = re.sub(r"[^a-z']+", "", key)
        if not key:
            return None
        entries = self._cmu.get(key)
        if not entries:
            return None
        # Each entry is a list of phonemes; pick the first pronunciation variant.
        phonemes = entries[0]
        return [_strip_stress(p) for p in phonemes]

    def compare_words(self, expected_word: str, recognized_word: str | None) -> PhonemeMatch:
        expected_ph = self.phonemes_for_word(expected_word)
        if recognized_word is None:
            return PhonemeMatch(
                expected_phonemes=expected_ph,
                recognized_phonemes=None,
                similarity=None,
                message="Missing from transcription.",
            )

        recognized_ph = self.phonemes_for_word(recognized_word)
        if expected_ph is None:
            return PhonemeMatch(
                expected_phonemes=None,
                recognized_phonemes=recognized_ph,
                similarity=None,
                message="No phoneme entry for expected word.",
            )
        if recognized_ph is None:
            return PhonemeMatch(
                expected_phonemes=expected_ph,
                recognized_phonemes=None,
                similarity=None,
                message="No phoneme entry for spoken word.",
            )

        dist = _levenshtein_distance_seq(expected_ph, recognized_ph)
        sim = _similarity_from_distance(dist, len(expected_ph), len(recognized_ph))
        return PhonemeMatch(
            expected_phonemes=expected_ph,
            recognized_phonemes=recognized_ph,
            similarity=sim,
            message="Phoneme similarity computed (CMU dict).",
        )

    def _format_sound(self, phonemes: list[str] | None) -> str:
        return " ".join(phonemes) if phonemes else ""

    def suggest_improvement(
        self, expected_word: str, recognized_word: str | None
    ) -> str:
        match = self.compare_words(expected_word, recognized_word)
        if recognized_word is None:
            return "Try clearly pronouncing the missing word and pause slightly between words."

        if match.similarity is None:
            if match.expected_phonemes is None:
                return "I could not find a pronunciation entry for the expected word. Try speaking more clearly."
            if match.recognized_phonemes is None:
                return "The spoken word was not recognized clearly. Try repeating it more slowly."

        if match.similarity is not None and match.similarity >= 0.85:
            return "Your pronunciation is close. Focus on stress and clarity for a more natural sound."

        expected_ph = match.expected_phonemes or []
        recognized_ph = match.recognized_phonemes or []

        if expected_ph and recognized_ph:
            if expected_ph[0] != recognized_ph[0]:
                return (
                    f"Try starting '{expected_word}' with the sound {expected_ph[0]} "
                    f"instead of {recognized_ph[0]}."
                )
            if expected_ph[-1] != recognized_ph[-1]:
                return (
                    f"Make sure '{expected_word}' ends with {expected_ph[-1]} "
                    "for clearer pronunciation."
                )
            if len(expected_ph) != len(recognized_ph):
                return (
                    f"Match the rhythm of '{expected_word}' more closely; "
                    "there should be a similar number of sounds."
                )

        return (
            "Try articulating each syllable more clearly and slow down slightly "
            "to improve pronunciation."
        )

