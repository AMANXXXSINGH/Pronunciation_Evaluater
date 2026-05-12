from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WordAlignment:
    expected_index: int
    expected: str | None
    recognized: str | None
    op: Literal["match", "substitute", "delete", "insert"]


def levenshtein_distance(a: str, b: str) -> int:
    """
    Standard Levenshtein distance for strings.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # DP with O(min(len(a), len(b))) memory.
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


def levenshtein_similarity(a: str, b: str) -> float:
    """
    Similarity in [0, 1] derived from edit distance.
    """
    denom = max(1, max(len(a), len(b)))
    dist = levenshtein_distance(a, b)
    return max(0.0, 1.0 - (dist / denom))


def wer_with_alignment(expected_words: list[str], recognized_words: list[str]) -> tuple[float, list[WordAlignment]]:
    """
    Returns (WER, per-expected-word alignment).

    Note: this uses unit costs: match=0, substitute=1, delete=1, insert=1.
    """
    ref = expected_words
    hyp = recognized_words
    n = len(ref)
    m = len(hyp)

    if n == 0:
        # If there's no reference, define WER as 0 when hypothesis is empty,
        # otherwise penalize all insertions as 1.0.
        return (0.0 if m == 0 else 1.0), []

    # DP matrix sized (n+1) x (m+1) for backtracking.
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # delete
                dp[i][j - 1] + 1,      # insert
                dp[i - 1][j - 1] + cost,  # substitute/match
            )

    # Backtrack to produce a per-reference alignment.
    i, j = n, m
    insertions = 0
    alignments_rev: list[WordAlignment] = []

    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hyp[j - 1] and dp[i][j] == dp[i - 1][j - 1]:
            alignments_rev.append(
                WordAlignment(
                    expected_index=i - 1,
                    expected=ref[i - 1],
                    recognized=hyp[j - 1],
                    op="match",
                )
            )
            i -= 1
            j -= 1
            continue

        # Substitute
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            alignments_rev.append(
                WordAlignment(
                    expected_index=i - 1,
                    expected=ref[i - 1],
                    recognized=hyp[j - 1],
                    op="substitute",
                )
            )
            i -= 1
            j -= 1
            continue

        # Delete (expected word missing)
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            alignments_rev.append(
                WordAlignment(
                    expected_index=i - 1,
                    expected=ref[i - 1],
                    recognized=None,
                    op="delete",
                )
            )
            i -= 1
            continue

        # Otherwise it's an insertion on the hypothesis side.
        if j > 0:
            alignments_rev.append(
                WordAlignment(
                    expected_index=i, # Ties it to the position before the next expected word
                    expected=None,
                    recognized=hyp[j - 1],
                    op="insert",
                )
            )
            insertions += 1
            j -= 1
            continue

        # Fallback (shouldn't happen with the above cases).
        break

    alignments = list(reversed(alignments_rev))

    # Derive S and D from the alignment list; I from backtracking.
    substitutions = sum(1 for a in alignments if a.op == "substitute")
    deletions = sum(1 for a in alignments if a.op == "delete")
    wer = (substitutions + deletions + insertions) / n
    return wer, alignments

