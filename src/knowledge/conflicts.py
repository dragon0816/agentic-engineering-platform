"""Settled decisions and open conflicts. Adapted from the pinned `conflicts.py`
(docs/PHASE_4_MIGRATION.md).

`decisions.md` is the append-only record of what a person judged right and
wrong. It is injected into every plan so a later source does not reinstate a
rejected claim — the piece a change log cannot provide, since a log records
that a line was deleted, not that it was deleted *because it was wrong*. Open
conflicts are the `⚠️` lines still sitting on pages, found by reading; one is
cleared only after its decision is on record, and clearing removes marker
lines and nothing else. Manual-edit detection lives in `knowledge.lint`,
which computes it into the report.
"""

from datetime import date
from typing import Self

from pydantic import model_validator

from common.base import Contract, Text
from knowledge.lint import CONFLICT, OpenConflict, find_conflicts, line_ending, read_pages
from knowledge.planning import NO_DECISIONS
from knowledge.vault import Vault, normalize

DECISIONS_FILE = "decisions.md"
DECISIONS_HEADER = """# Decisions — settled conflicts

> An **append-only record of decisions**, not a timeline (that is `log.md`).
> Every ingest and lint gives this file to the model so a rejected claim is
> not written back. One `## [YYYY-MM-DD] topic` per decision, saying what is
> kept, what is rejected and why. Keep it short: it enters every prompt.
"""


class Decision(Contract):
    """One settled conflict: what a person kept, rejected and why."""

    topic: Text
    keep: str = ""
    reject: str = ""
    reason: str = ""
    pages: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def says_something(self) -> Self:
        if not (self.keep.strip() or self.reject.strip() or self.reason.strip()):
            raise ValueError("a decision keeps, rejects or explains something")
        return self


def decision_block(decision: Decision, today: date) -> str:
    lines = [f"## [{today.isoformat()}] {decision.topic.strip()}"]
    if decision.keep.strip():
        lines.append(f"- keep: {decision.keep.strip()}")
    if decision.reject.strip():
        lines.append(f"- reject: {decision.reject.strip()}")
    if decision.reason.strip():
        lines.append(f"- reason: {decision.reason.strip()}")
    if decision.pages:
        lines.append("- pages: " + ", ".join(f"[[{page}]]" for page in decision.pages))
    return "\n".join(lines) + "\n"


def decisions_text(vault: Vault) -> str:
    """The block a plan prompt receives: the settled decisions, or the
    planner's marker saying there are none (a header alone is none)."""
    text = vault.read(DECISIONS_FILE).strip()
    if not text or text == DECISIONS_HEADER.strip():
        return NO_DECISIONS
    return text


def append_decision(vault: Vault, decision: Decision, *, today: date) -> str:
    """Append one decision; the header is written once, on the first."""
    checked = Decision.model_validate(decision)
    if not vault.exists(DECISIONS_FILE):
        vault.write(DECISIONS_FILE, DECISIONS_HEADER, stamp="decisions")
    vault.append(DECISIONS_FILE, "\n" + decision_block(checked, today))
    return DECISIONS_FILE


def open_conflicts(vault: Vault) -> tuple[OpenConflict, ...]:
    """Every `⚠️` line still on a wiki page, with enough context to act on."""
    texts, _ = read_pages(vault, vault.wiki_files())
    found: list[OpenConflict] = []
    for rel, text in texts.items():
        found.extend(find_conflicts(rel, text))
    return tuple(found)


def clear_conflicts(
    vault: Vault, page: str, lines: tuple[int, ...], *, stamp: str
) -> tuple[int, ...]:
    """Remove the marker lines of one page in one write — one backup of the
    original, whatever the number of markers — and return the line numbers
    actually removed. A line that is not a conflict marker (a heading or prose
    that merely mentions the symbol), or that has moved, is left alone: nothing
    but markers is ever removed."""
    rel = normalize(page)
    text = vault.read(rel)
    rows = text.split("\n")
    removable = sorted(
        {n for n in lines if 1 <= n <= len(rows) and CONFLICT.match(rows[n - 1]) is not None},
        reverse=True,
    )
    if not removable:
        return ()
    for number in removable:
        index = number - 1
        del rows[index]
        # Leave no double blank line behind.
        while 0 < index < len(rows) and not rows[index].strip() and not rows[index - 1].strip():
            del rows[index]
    ending = line_ending(vault, rel)
    vault.write(rel, ending.join(rows).rstrip("\r\n") + ending, stamp=stamp)
    return tuple(sorted(removable))


def clear_conflict(vault: Vault, page: str, line: int, *, stamp: str) -> bool:
    """Remove one marker line after it has been decided; False when it moved."""
    return bool(clear_conflicts(vault, page, (line,), stamp=stamp))


class Resolution(Contract):
    """What resolving did: the decision recorded, the conflicts cleared, and
    the ones that had moved and were left alone."""

    decision: Decision
    cleared: tuple[OpenConflict, ...] = ()
    missed: tuple[tuple[Text, int], ...] = ()


def resolve(
    vault: Vault,
    decision: Decision,
    *,
    clear: tuple[tuple[str, int], ...] = (),
    today: date,
    stamp: str,
) -> Resolution:
    """Record why, then remove the markers. The decision is written first so
    a marker is never cleared without its reason on record; the clear list is
    checked before anything is written so nothing can fail half-way."""
    wanted: dict[str, set[int]] = {}
    for page, line in clear:
        rel = normalize(page)
        if not rel or line < 1:
            raise ValueError("a conflict to clear is a page and a line number")
        wanted.setdefault(rel, set()).add(line)
    append_decision(vault, decision, today=today)
    before = {(item.page, item.line): item for item in open_conflicts(vault)}
    cleared: list[OpenConflict] = []
    missed: list[tuple[str, int]] = []
    for rel in sorted(wanted):
        known = {line for line in wanted[rel] if (rel, line) in before}
        removed = set(clear_conflicts(vault, rel, tuple(known), stamp=stamp)) if known else set()
        for line in sorted(wanted[rel]):
            if line in removed:
                cleared.append(before[(rel, line)])
            else:
                missed.append((rel, line))
    return Resolution(decision=decision, cleared=tuple(cleared), missed=tuple(missed))
