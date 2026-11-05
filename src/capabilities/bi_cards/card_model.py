"""The storage shape of the BI card model: its units, ids and allowed values.

Design: `docs/phases/BI_CARD_MODEL.md` §3; contract: `docs/CONTRACTS.md` "BI card
model". Pure, with no store or vault, so every part of the model builds these
values the same way on every PC: an id here is a hash of what it names, never
random, and never depends on the PC or the order of writes.

    state:<card id>:<field>       {"state", "reason", "raw", "ref", "by", "at"}
    relation:<relation id>        {"from", "type", "to", "origin", "status", "scope",
                                   "note", "by", "at"}
    relation_evidence:<link id>   {"relation", "basis_card", "reference_id", "stance",
                                   "assessment", "by", "at"}
    profile:<application>         {"revision", "author", "path", "sha256", "schema"}
    tool:<application>/<name>     {"revision", "author", "path", "sha256"}

A link in a `field:` unit's value is stored as `{"card": <id>, "name": <name at
write>}`, or stays text when no single card answers it. A `card:` unit may hold
`former_keys`, and an `evidence:` row `reference_id`, `stance`, `reference_at`
and `reference_time_basis`. Units written before this model stay valid and are
never rewritten.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

#: A local `bi.sqlite` older than this is rebuilt once from the units. Kept in
#: `PRAGMA user_version`, not `meta`: every `meta` row is a unit.
MODEL_VERSION = 10

STATE_PREFIX = "state:"
RELATION_PREFIX = "relation:"
RELATION_EVIDENCE_PREFIX = "relation_evidence:"
PROFILE_PREFIX = "profile:"
TOOL_PREFIX = "tool:"
UNIT_PREFIXES = (
    STATE_PREFIX,
    RELATION_PREFIX,
    RELATION_EVIDENCE_PREFIX,
    PROFILE_PREFIX,
    TOOL_PREFIX,
)

#: Proposal §3.2. No row reads as `unknown`, so a state is only stored with a reason.
UNKNOWN = "unknown"
NOT_APPLICABLE = "not_applicable"
PENDING_CONFIRMATION = "pending_confirmation"
CONFIRMED_NONE = "confirmed_none"
FIELD_STATES = (UNKNOWN, NOT_APPLICABLE, PENDING_CONFIRMATION, CONFIRMED_NONE)
#: Where a `field_states` row came from. Only `unit` rows read back as units:
#: the others are computed at rebuild, from a profile or a pending proposal.
STATE_ORIGINS = ("unit", "profile", "proposal")

SUPPORTS = "supports"
STANCES = (SUPPORTS, "refutes", "context_only")
SUBMISSION_FALLBACK = "submission_fallback"
#: A person's review of a reference, in words (proposal §6.1 B): no numeric weight.
DIRECTNESS = ("direct", "indirect", "insufficient", UNKNOWN)
SAME_SOURCE = ("independent", "same_source", UNKNOWN)
VERDICTS = ("accepted", "pending", "rejected")

#: `unreviewed` is only for a relation derived from a link field; it never blocks use.
UNREVIEWED = "unreviewed"
RELATION_STATUSES = (UNREVIEWED, "pending", "inferred", "confirmed", "disputed", "rejected")
SCHEMA_FIELD = "schema_field"
RELATION_ORIGINS = (SCHEMA_FIELD, "ai_inferred", "registered")

NAME_FORMER = "former"
NAME_ALIAS = "alias"


def _hash(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()[:12]


def relation_id(from_card: str, relation_type: str, to_card: str) -> str:
    """The same relation has the same id on every PC, derived or not."""
    return _hash(from_card, relation_type, to_card)


def reference_id(source_id: str, locator: Any) -> str:
    """A place in a source. It leaves out the excerpt, which a withdrawal blanks."""
    return _hash(source_id, json.dumps(locator, ensure_ascii=False, sort_keys=True))


def evidence_link_id(relation: str, basis_card: str, reference: str) -> str:
    return _hash(relation, basis_card, reference)


def default_relation_type(field: str) -> str:
    """`supplier` → `has_supplier`, unless the link field names its `relation_type`."""
    return f"has_{field}"


def link_item(card_id: str, name: str) -> dict[str, str]:
    return {"card": card_id, "name": name}


def is_link_item(value: Any) -> bool:
    """Exactly these keys: other units hold a `card` too (`proposal:`)."""
    return isinstance(value, dict) and set(value) == {"card", "name"}


def render_link(value: Any, names: Mapping[str, str]) -> Any:
    """A stored link value as `fields` shows it: a card's current name, the name
    at write when the card is gone, and text as it was written."""
    if isinstance(value, list):
        return [render_link(item, names) for item in value]
    if is_link_item(value):
        return names.get(value["card"], value.get("name") or value["card"])
    return value


def render_links_within(value: Any, names: Mapping[str, str]) -> Any:
    """A unit, or anything holding one, for a person: every link inside as a name."""
    if is_link_item(value):
        return render_link(value, names)
    if isinstance(value, list):
        return [render_links_within(item, names) for item in value]
    if isinstance(value, dict):
        return {k: render_links_within(v, names) for k, v in value.items()}
    return value


def card_names_of(units: Mapping[str, Any]) -> dict[str, str]:
    """Each card's current name, from `card:` units."""
    return {
        key[5:]: str(value["name"])
        for key, value in units.items()
        if key.startswith("card:") and isinstance(value, dict)
    }


def _text(value: Mapping[str, Any], *keys: str) -> bool:
    return all(isinstance(value.get(k), str) and value[k] for k in keys)


def unit_problem(key: str, value: Any) -> str | None:
    """Why `value` cannot be this model's unit `key`; None when it can."""
    if not isinstance(value, dict):
        return "value must be an object"
    if key.startswith(STATE_PREFIX):
        if key.count(":") != 2:
            return "state key is state:<card>:<field>"
        return None if value.get("state") in FIELD_STATES else "state unknown"
    if key.startswith(RELATION_EVIDENCE_PREFIX):
        if not _text(value, "relation", "basis_card", "reference_id"):
            return "relation evidence needs relation, basis_card and reference_id"
        return None if value.get("stance") in STANCES else "stance unknown"
    if key.startswith(RELATION_PREFIX):
        if not _text(value, "from", "type", "to"):
            return "relation needs from, type and to"
        if value.get("origin") not in RELATION_ORIGINS:
            return "relation origin unknown"
        return None if value.get("status") in RELATION_STATUSES else "relation status unknown"
    if key.startswith((PROFILE_PREFIX, TOOL_PREFIX)):
        if not _text(value, "author", "path", "sha256"):
            return "needs author, path and sha256"
        revision = value.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            return "revision must be a positive number"
        return None
    return "not a card model unit"
