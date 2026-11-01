"""Character error rate for transcripts, ported from the voice-to-knowledge
prototype's `metrics.py` (draft PR #240): NFKC, case folding, and without
punctuation or whitespace, so 「ＣＭＸ５００。」 and "cmx500" compare equal."""

from __future__ import annotations

import unicodedata


def normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(
        character
        for character in folded
        if not character.isspace() and not unicodedata.category(character).startswith("P")
    )


def _distance(reference: str, hypothesis: str) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, start=1):
        current = [i]
        for j, heard in enumerate(hypothesis, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (expected != heard))
            )
        previous = current
    return previous[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Edits per reference character after normalising; 0.0 for two empties."""
    expected, heard = normalise(reference), normalise(hypothesis)
    if not expected:
        return 0.0 if not heard else 1.0
    return _distance(expected, heard) / len(expected)
