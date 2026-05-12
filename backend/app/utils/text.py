from __future__ import annotations

import re


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def normalize_text(text: str) -> str:
    """
    Normalize for token alignment:
    - lower-case
    - keep word characters and spaces
    - collapse whitespace
    """
    text = text.strip().lower()
    # Replace non-word characters with spaces, then collapse.
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_words(text: str) -> list[str]:
    """
    Tokenize into "words" for WER and per-word feedback.
    """
    return _WORD_RE.findall(normalize_text(text))

