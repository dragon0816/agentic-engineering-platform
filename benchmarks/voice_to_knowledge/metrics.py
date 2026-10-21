"""Versioned scoring policy; never alter stored transcripts or references."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Any

POLICY = "voice-score-v0.1"
TERMS = ("CMP180", "Wi-Fi 8", "UWB", "Qualcomm", "LitePoint")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(c for c in text if not unicodedata.category(c).startswith("P"))


def distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    row = list(range(len(hypothesis) + 1))
    for i, left in enumerate(reference, 1):
        next_row = [i]
        for j, right in enumerate(hypothesis, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (left != right)))
        row = next_row
    return row[-1]


def rate(reference: list[str], hypothesis: list[str]) -> dict[str, Any]:
    edits = distance(reference, hypothesis)
    return {
        "edits": edits,
        "reference_units": len(reference),
        "rate": edits / len(reference) if reference else None,
    }


def mixed(text: str) -> list[str]:
    # Han codepoints + runs of non-Han letters/numbers + individual punctuation.
    return re.findall(
        r"[\u3400-\u9fff\U00020000-\U0002fa1f]|"
        r"[^\W\u3400-\u9fff\U00020000-\U0002fa1f]+|[^\w\s]",
        text,
    )


def term_counts(text: str) -> Counter[str]:
    text = normalize(text)
    return Counter(
        {
            term: len(
                re.findall(r"(?<![a-z0-9])" + re.escape(normalize(term)) + r"(?![a-z0-9])", text)
            )
            for term in TERMS
        }
    )


def score(reference: str, hypothesis: str) -> dict[str, Any]:
    output: dict[str, Any] = {"policy": POLICY}
    for label, ref, hyp in [
        ("raw", reference, hypothesis),
        ("normalized", normalize(reference), normalize(hypothesis)),
    ]:
        output[label] = {
            "cer": rate(list("".join(ref.split())), list("".join(hyp.split()))),
            "wer": rate(ref.split(), hyp.split()),
            "mer": rate(mixed(ref), mixed(hyp)),
        }
    expected, actual = term_counts(reference), term_counts(hypothesis)
    tp = sum((expected & actual).values())
    fp, fn = sum((actual - expected).values()), sum((expected - actual).values())
    output["terms"] = {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "reference": dict(expected),
        "hypothesis": dict(actual),
    }
    output["silence_hallucination"] = (
        bool(normalize(hypothesis).strip()) if not reference.strip() else None
    )
    output["diagnostics"] = {
        f"{side}_{kind}": re.findall(pattern, normalize(text))
        for side, text in [("reference", reference), ("hypothesis", hypothesis)]
        for kind, pattern in [
            ("numbers", r"\d+"),
            ("negations", r"不|沒|未|無|\b(?:no|not|never)\b"),
        ]
    }
    return output


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Micro-average within strata; failed inference never disappears from counts."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = "/".join(str(row[k]) for k in ("language", "kind", "split", "thermal"))
        groups.setdefault(key, []).append(row)
    output: dict[str, Any] = {}
    for key, values in groups.items():
        success = [r for r in values if r["status"] == "ok"]
        summary: dict[str, Any] = {
            "attempts": len(values),
            "success": len(success),
            "failed": len(values) - len(success),
            "unique_samples": len({r["id"] for r in values}),
        }
        for variant in ("raw", "normalized"):
            summary[variant] = {}
            for metric in ("cer", "wer", "mer"):
                edits = sum(r["metrics"][variant][metric]["edits"] for r in success)
                count = sum(r["metrics"][variant][metric]["reference_units"] for r in success)
                summary[variant][metric] = {
                    "edits": edits,
                    "reference_units": count,
                    "rate": edits / count if count else None,
                }
        tp, fp, fn = (sum(r["metrics"]["terms"][k] for r in success) for k in ("tp", "fp", "fn"))
        summary["terms"] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        }
        silence = [
            r["metrics"]["silence_hallucination"]
            for r in success
            if r["metrics"]["silence_hallucination"] is not None
        ]
        summary["silence"] = {
            "evaluated": len(silence),
            "hallucinated": sum(silence),
            "rate": sum(silence) / len(silence) if silence else None,
        }
        summary["latency_seconds"] = [r["latency_seconds"] for r in success]
        summary["rtf"] = [r["rtf"] for r in success]
        output[key] = summary
    return output
