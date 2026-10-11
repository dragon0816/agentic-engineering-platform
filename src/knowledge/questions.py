"""Question sets by drop folder, graded by string match (collaboration C3).

`docs/phases/KNOWLEDGE_COLLAB.md` section 5. The format is the owner's own
`checks/questions/` file: one question per `.md`, its first `# ` heading is the
question, and `必須提到:` (must mention) / `不可以說:` (must not say) list plain
terms. The program grades; no model judges a model.

Sets follow the drop folders: `market/`, `productions/`, and combinations such
as `market_productions/`. Questions directly in the root form the general set
(key ""). A folder name matches a category ignoring case and a plural `s`, and
the order of its parts does not matter.
"""

from __future__ import annotations

import re
from pathlib import Path

from common.base import Contract

MUST = ("必須提到", "must mention")
MUST_NOT = ("不可以說", "must not say")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


class Question(Contract):
    set: str  # the folder under checks/questions, "" for the general set
    path: str  # relative to the questions root
    text: str
    must: tuple[str, ...] = ()
    must_not: tuple[str, ...] = ()


class Grade(Contract):
    passed: bool
    missing: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()


def category(name: str) -> str:
    key = name.strip().casefold()
    return key[:-1] if key.endswith("s") and len(key) > 1 else key


def set_categories(set_name: str) -> frozenset[str]:
    return frozenset(category(part) for part in set_name.split("_") if part.strip())


def parse(text: str, *, set_name: str, path: str) -> Question | None:
    body = COMMENT.sub("", text.replace("\r\n", "\n"))
    if body.startswith("---\n"):
        body = body[4:].partition("\n---\n")[2]
    question = next((line[2:].strip() for line in body.split("\n") if line.startswith("# ")), "")
    if not question:
        return None
    lists: dict[str, list[str]] = {"must": [], "must_not": []}
    current: list[str] | None = None
    for line in body.split("\n"):
        head = line.strip().rstrip(":：").strip().casefold()
        if head in MUST:
            current = lists["must"]
        elif head in MUST_NOT:
            current = lists["must_not"]
        elif current is not None and line.strip().startswith("- "):
            term = line.strip()[2:].strip()
            if term:
                current.append(term)
        elif line.strip() and not line.startswith((" ", "\t")):
            current = None
    return Question(set=set_name, path=path, text=question, must=tuple(lists["must"]),
                    must_not=tuple(lists["must_not"]))


def load(root: Path) -> tuple[Question, ...]:
    """Every question under `root`, in path order; unreadable files are skipped."""
    found = []
    if root.is_dir():
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(root)
            set_name = rel.parts[0] if len(rel.parts) > 1 else ""
            try:
                question = parse(path.read_text(encoding="utf-8"), set_name=set_name,
                                 path=rel.as_posix())
            except (OSError, UnicodeDecodeError):
                continue
            if question is not None:
                found.append(question)
    return tuple(found)


def sets(questions: tuple[Question, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for question in questions:
        counts[question.set] = counts.get(question.set, 0) + 1
    return dict(sorted(counts.items()))


def default_sets(available: list[str] | dict[str, int], scope: tuple[str, ...]) -> tuple[str, ...]:
    """The sets whose categories all lie in the sandbox's pulled scope. Every
    folder of a pulled path counts: `Productions/VNA` selects `productions/`,
    `vna/` and `productions_vna/`, not the other product lines' sets."""
    pulled = frozenset(category(part) for folder in scope for part in folder.split("/")
                       if part.strip())
    return tuple(name for name in available
                 if name and set_categories(name) and set_categories(name) <= pulled)


def grade(question: Question, answer: str) -> Grade:
    seen = answer.casefold()
    missing = tuple(term for term in question.must if term.casefold() not in seen)
    forbidden = tuple(term for term in question.must_not if term.casefold() in seen)
    return Grade(passed=not missing and not forbidden, missing=missing, forbidden=forbidden)
