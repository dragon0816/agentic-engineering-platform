"""Where a failed benchmark question went wrong (proposal §6.1 D).

Must and must_not terms still decide pass or fail (`knowledge.questions.grade`); this
only says what to look at next, one term at a time, from what the turn's tools returned
and what the cards and sources hold:

    retrieval   a card holds the term, and no fetched card links to it
    relation    a card holds the term, and a fetched card links to it
    extraction  a source says the term and no card does; or a card's value holds a
                forbidden term that its evidence does not say
    evidence    a forbidden term came from evidence kept only as context
    generation  the tools returned a wanted term and the answer left it out; the answer
                says a forbidden term no tool returned, or one its evidence refutes
    unknown     anything else: no trace, a failed turn, or a term found nowhere

Pure, so the same inputs always give the same class. It never guesses: finding a term
is what it knows, and a wrong class would send a person to fix the wrong thing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

RETRIEVAL = "retrieval"
RELATION = "relation"
EXTRACTION = "extraction"
EVIDENCE = "evidence"
GENERATION = "generation"
UNKNOWN = "unknown"
CLASSES = (RETRIEVAL, RELATION, EXTRACTION, EVIDENCE, GENERATION, UNKNOWN)


@dataclass(frozen=True)
class Card:
    """What one card holds: its name and values as text, its links, its evidence."""

    text: str
    values: Mapping[str, str]
    linked: frozenset[str]
    evidence: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class World:
    """The version the question was asked on."""

    cards: Mapping[str, Card]
    sources: str


def walk_strings(value: Any) -> Iterable[str]:
    """Every string in a tool's data, keys left out."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from walk_strings(item)


def _in(term: str, text: Any) -> bool:
    return term.casefold() in str(text or "").casefold()


def _missing(term: str, shown: Sequence[str], world: World) -> tuple[str, str]:
    if any(_in(term, text) for text in shown):
        return GENERATION, "工具回傳過這個詞，回答沒有寫出來"
    fetched = {text for text in shown if text in world.cards}
    holders = {cid for cid, card in world.cards.items() if _in(term, card.text)}
    if holders & fetched:
        return UNKNOWN, "取回的卡片有這個詞，但工具沒有回傳這部分"
    if holders:
        if any(world.cards[cid].linked & fetched for cid in holders):
            return RELATION, "有卡片寫了這個詞，取回的卡片連得到它，但沒有順著關係取回"
        return RETRIEVAL, "有卡片寫了這個詞，但沒有被取回"
    if _in(term, world.sources):
        return EXTRACTION, "來源寫了這個詞，但沒有任何卡片記下來"
    return UNKNOWN, "卡片和來源裡都找不到這個詞"


def _forbidden(term: str, shown: Sequence[str], world: World) -> tuple[str, str]:
    if not any(_in(term, text) for text in shown):
        return GENERATION, "工具沒有回傳過這個詞，回答卻寫了"
    fetched = [world.cards[text] for text in shown if text in world.cards]
    rows = [row for card in fetched for row in card.evidence if _in(term, row.get("excerpt"))]
    stances = {row.get("stance") for row in rows}
    if "refutes" in stances:
        return GENERATION, "取回的證據反駁這個說法，回答仍這樣寫"
    if "context_only" in stances:
        return EVIDENCE, "這個詞只出現在背景證據，卻被當成支持"
    if rows:
        return UNKNOWN, "證據確實這樣寫，工具分不出這筆證據該不該採信"
    for card in fetched:
        for field, value in card.values.items():
            proof = [r for r in card.evidence if r.get("field") == field and r.get("excerpt")]
            if _in(term, value) and proof:
                return EXTRACTION, f"卡片的 {field} 寫了這個詞，它的證據沒有這樣寫"
    return UNKNOWN, "工具回傳過這個詞，但分不出是哪一步造成的"


def classify(
    *,
    missing: Sequence[str],
    forbidden: Sequence[str],
    answered: bool,
    shown: Sequence[str] | None,
    world: World | None,
) -> list[dict[str, str]]:
    """One entry per term that failed. `shown` is every string the turn's tools
    returned, card ids included; None when no trace was kept."""
    terms = [("missing", term) for term in missing] + [("forbidden", term) for term in forbidden]
    found = []
    for kind, term in terms:
        if not answered:
            verdict = (UNKNOWN, "這一輪沒有答完")
        elif shown is None or world is None:
            verdict = (UNKNOWN, "沒有這一輪的工具紀錄")
        elif kind == "missing":
            verdict = _missing(term, shown, world)
        else:
            verdict = _forbidden(term, shown, world)
        found.append({"term": term, "kind": kind, "class": verdict[0], "why": verdict[1]})
    return found


def counts(errors: Iterable[Mapping[str, str]]) -> dict[str, int]:
    """How many failed terms fell in each class, the classes found only."""
    tally = dict.fromkeys(CLASSES, 0)
    for item in errors:
        tally[item["class"]] += 1
    return {name: number for name, number in tally.items() if number}
