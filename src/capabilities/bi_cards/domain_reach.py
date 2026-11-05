"""Which working domains a vault unit reaches (`docs/phases/BI_PAGE_SIMPLE.md` §14).

Owner, 2026-11-05: 「為了不彼此干擾，每一個domain會有專人來處理」. So a push is held back only by
what it touches, and a test counts for a domain's content, not the whole vault's. Both ask
one question of a unit. The answer is a set of homes; `ALL` when the unit is shared, or when
it cannot be placed soundly, which then behaves as a whole-vault change always did.

A unit that does not change what anyone reads (`import:`) reaches nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from typing import Any

from capabilities.bi_cards import homes, vault_checks, vault_skills
from knowledge.repo.repository import canonical

ALL = frozenset({"*"})
NOTHING: frozenset[str] = frozenset()
_CARD_UNITS = ("card:", "field:", "evidence:", "state:")
#: A library entry spans domains, so a change there reaches them all.
_LIBRARY = f"{homes.LIBRARY}/"


def _home_set(home: Any) -> frozenset[str]:
    """One home, as a reach. A library entry, or what is not a home, is everyone's."""
    if not isinstance(home, str) or not home or home.startswith(_LIBRARY):
        return ALL
    return ALL if homes.home_problem(home) else frozenset({home})


class Reach:
    """Answers for the units of one or two states; a card's domains in either count, so moving
    a card between domains reaches both."""

    def __init__(self, *states: Mapping[str, Any]) -> None:
        self.states = states
        self.by_domain: dict[str, str] = {}
        for state in states:
            for item in vault_skills.home_list(state):
                if not item["home"].startswith(_LIBRARY):
                    self.by_domain[item["home"].casefold()] = item["home"]

    def _card(self, card_id: str) -> frozenset[str]:
        """The homes of a card's `domain` field. A card with none, or only domains no home
        stands for, cannot be placed."""
        found: set[str] = set()
        key = f"field:{card_id}:domain"
        for state in self.states:
            value = state.get(key)
            value = value.get("value") if isinstance(value, dict) else None
            for name in value if isinstance(value, list) else [value]:
                home = self.by_domain.get(str(name).casefold()) if name else None
                if home:
                    found.add(home)
        return frozenset(found) or ALL

    def _value(self, key: str) -> Any:
        for state in self.states:
            if isinstance(state.get(key), dict):
                return state[key]
        return None

    def unit(self, key: str) -> frozenset[str]:
        if key.startswith("import:"):
            return NOTHING
        if key.startswith(_CARD_UNITS):
            return self._card(key.partition(":")[2].partition(":")[0])
        value = self._value(key)
        if key.startswith("proposal:"):
            card = value.get("card") if value else None
            return self._card(str(card)) if card else ALL
        if key.startswith("relation:"):
            if not value or not value.get("from") or not value.get("to"):
                return ALL
            ends = self._card(str(value["from"])) | self._card(str(value["to"]))
            return ALL if "*" in ends else ends
        if key.startswith("source:"):
            return _home_set(homes.home_of(str(value.get("folder") or ""))) if value else ALL
        if key.startswith(vault_checks.QUESTION_PREFIX):
            return _home_set(value.get("home")) if value else ALL
        if key.startswith(vault_checks.EXTRACT_PREFIX):
            return _home_set(vault_checks.case_home(value)) if value else ALL
        if key.startswith("skill:") or key.startswith("tool:"):
            return _home_set(key.partition(":")[2].rpartition("/")[0])
        if key.startswith("profile:"):
            return _home_set(key.partition(":")[2])
        for prefix in ("meta:dashboard:", vault_skills.HOME_PREFIX):
            if key.startswith(prefix):
                return _home_set(key[len(prefix) :])
        return ALL


def touched(before: Mapping[str, Any], after: Mapping[str, Any]) -> frozenset[str]:
    """What going from `before` to `after` reaches."""
    reach = Reach(after, before)
    found: set[str] = set()
    for key in set(before) | set(after):
        if canonical(before.get(key)) != canonical(after.get(key)):
            found |= reach.unit(key)
            if "*" in found:
                return ALL
    return frozenset(found)


def digests(units: Mapping[str, Any], wanted: Iterable[str]) -> dict[str, str]:
    """A digest of what each home's tests stand on: its units and the shared ones. A
    colleague's change in another domain leaves it alone; a shared unit changes every one."""
    reach = Reach(units)
    hashed = sorted(
        (key, hashlib.sha256(canonical(value).encode("utf-8")).hexdigest(), reach.unit(key))
        for key, value in units.items()
    )
    found = {}
    for home in wanted:
        digest = hashlib.sha256()
        for key, value_hash, reached in hashed:
            if "*" in reached or home in reached:
                digest.update(f"{key}\0{value_hash}\n".encode())
        found[home] = digest.hexdigest()
    return found
