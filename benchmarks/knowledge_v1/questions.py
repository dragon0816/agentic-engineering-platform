"""The question bank: parse the owner's file and pick the stratified sample.

`questions/source.md` is the owner's file, copied unchanged; `SOURCE_SHA256`
pins it, so a run never asks a rewritten question. The sample is fixed by
the questions' IDs, not drawn at random, so every run asks the same ones.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "questions" / "source.md"
SOURCE_SHA256 = "f5275373dad71f1b76a7560611d80f931228410487f34212117138619aa7668e"
TYPES = ("basic", "application", "solution_mapping", "cross_domain", "competitive", "strategic")
_HEAD = re.compile(r"^\*\*(Q\d{4})\*\*\s*(.*)$")
_TAG = re.compile(r"`\[([a-z_]+):([^\]]*)\]`")


def load() -> list[dict[str, Any]]:
    """Every question with its tags, in file order."""
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise SystemExit("questions/source.md changed: the question bank is pinned by its sha256")
    lines = raw.decode("utf-8").splitlines()
    out: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        head = _HEAD.match(lines[index])
        if head is None:
            index += 1
            continue
        tags_text = head.group(2)
        index += 1
        # Tags may continue on the next lines; a line ending in "\" closes them.
        while not tags_text.rstrip().endswith("\\") and index < len(lines) and lines[index].strip():
            tags_text += " " + lines[index]
            index += 1
        body: list[str] = []
        while index < len(lines) and lines[index].strip() and not _HEAD.match(lines[index]):
            body.append(lines[index].strip())
            index += 1
        tags = dict(_TAG.findall(tags_text))
        out.append({"id": head.group(1), "text": " ".join(body), **tags})
    return out


def sample(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """110 questions: five per market x product cell, the left-out type rotating so
    each type is asked about equally often, plus every tenth foundation question.
    Within a cell and type the first question in file order is taken."""
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    foundation = []
    for question in questions:
        if "market" in question:
            cells.setdefault((question["market"], question["product"]), []).append(question)
        else:
            foundation.append(question)
    chosen = []
    for number, key in enumerate(sorted(cells)):
        skipped = TYPES[number % len(TYPES)]
        for kind in TYPES:
            if kind == skipped:
                continue
            first = next((q for q in cells[key] if q.get("type") == kind), None)
            if first is not None:
                chosen.append(first)
    chosen += foundation[::10]
    return sorted(chosen, key=lambda q: q["id"])


def main() -> int:
    questions = load()
    picked = sample(questions)
    (HERE / "questions" / "questions.json").write_text(
        json.dumps(
            {"source_sha256": SOURCE_SHA256, "questions": questions}, ensure_ascii=False, indent=1
        )
        + "\n",
        encoding="utf-8",
    )
    (HERE / "questions" / "sample.json").write_text(
        json.dumps([q["id"] for q in picked], indent=1) + "\n", encoding="utf-8"
    )
    print(f"{len(questions)} questions, sample of {len(picked)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
