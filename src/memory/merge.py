"""Merge rules as data, evaluated (docs/phases/ACCUMULATED_MEMORY.md §3.8.3).

`decide` says what one offered value does to a field's current value;
`resolve` folds a list of observations into current values and the conflicts
left to the person; `auto_merge` says whether a contribution joins an
existing entity by itself (§10.7). Nothing here touches storage.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from common.memory import Decision, MergeRules, TrustClass


def same_text(a: str, b: str) -> bool:
    """Equal apart from spacing and case."""
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def _rank(order: Sequence[TrustClass], trust: TrustClass | None) -> int:
    """Higher is more trusted; an unknown kind ranks lowest."""
    if trust is None or trust not in order:
        return 0
    return len(order) - order.index(trust)


def decide(
    rules: MergeRules,
    field_name: str,
    *,
    current: str,
    current_kind: str | None,
    current_date: str,
    offered: str,
    offered_kind: str,
    offered_date: str,
    uncertain: bool = False,
    same: Callable[[str, str], bool] = same_text,
    novel: bool = False,
) -> Decision:
    """What the rules do with `offered` for a field whose current value is
    `current`, set from a source of `current_kind` dated `current_date` (no
    kind: no provenance). In order:

    1. nothing offered, or the same value: kept;
    2. an external id system's value: kept, it is for matching only;
    3. the person's own statement: taken;
    4. the current value is the person's own (also an emptied one): never
       replaced by old evidence; the offered value is a proposal
       (`propose_if_newer` / `take_if_newer`: only new evidence counts, a
       dated source dated after the statement's day, an `undated` source
       only when `novel`, its identity never seen before; `take_if_newer`
       takes new evidence unless uncertain);
    5. nothing current: taken;
    6. `precedence`: a lower trust class never replaces a higher one (a
       proposal, or kept); a higher one wins whatever its date;
    7. an uncertain reading never replaces a value;
    8. older evidence never replaces newer;
    9. otherwise taken.
    """
    if not offered.strip():
        return Decision(action="keep", reason="empty")
    if same(current, offered):
        return Decision(action="keep", reason="same")
    if field_name in rules.external_ids:
        return Decision(action="keep", reason="match_only")
    offered_trust = rules.trust_of(offered_kind)
    if offered_trust == "user_stated":
        return Decision(action="take")
    rule = rules.rule_for(field_name)
    current_trust = None if current_kind is None else rules.trust_of(current_kind)
    if current_trust == "user_stated":
        # Owner 2026-10-20: only new evidence counts against the person's
        # value. An undated source (a card) by its identity, never by a date;
        # a dated one by day, after the statement's day. New evidence is a
        # proposal (`propose_if_newer`) or, sure, the new value
        # (`take_if_newer`).
        if rule.user_conflict in ("propose_if_newer", "take_if_newer"):
            if offered_kind in rules.undated:
                if not novel:
                    return Decision(action="keep", reason="seen_evidence")
            elif offered_date[:10] <= current_date[:10]:
                return Decision(action="keep", reason="older_evidence")
            if rule.user_conflict == "take_if_newer" and not uncertain:
                return Decision(action="take", reason="new_evidence")
        return Decision(action="propose", reason="user_set")
    if not current:
        return Decision(action="take")
    higher = False
    if rule.policy == "precedence" and current_kind is not None:
        mine, theirs = (
            _rank(rule.precedence, offered_trust),
            _rank(rule.precedence, current_trust),
        )
        if mine < theirs:
            action = "propose" if rule.lower_conflict == "propose" else "keep"
            return Decision(action=action, reason="lower_trust")
        higher = mine > theirs
    if uncertain:
        return Decision(action="keep", reason="uncertain")
    if not higher and current_kind is not None and offered_date < current_date:
        return Decision(action="keep", reason="older_evidence")
    return Decision(action="take")


class ObservationLike(Protocol):
    """What `resolve` reads of an observation (`memory.service.Observation`)."""

    @property
    def observation_id(self) -> int: ...
    @property
    def source_kind(self) -> str: ...
    @property
    def source_date(self) -> str: ...
    @property
    def fields(self) -> Mapping[str, str]: ...
    @property
    def uncertain(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class Resolved:
    """A field's current value and the evidence it came from."""

    value: str
    source_kind: str
    source_date: str
    observation_id: int


@dataclass(frozen=True)
class Conflict:
    """An offered value the rules did not take and leave to the person."""

    field: str
    current: str
    proposed: str
    source_kind: str
    observation_id: int
    reason: str


@dataclass
class Resolution:
    values: dict[str, Resolved] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)


def resolve(rules: MergeRules, observations: Iterable[ObservationLike]) -> Resolution:
    """Current values from observations, oldest evidence first (then in the
    order they were recorded), each offered value decided by the rules; the
    proposals are the conflicts, one per distinct proposed value."""
    result = Resolution()
    ordered = sorted(observations, key=lambda item: (item.source_date, item.observation_id))
    for item in ordered:
        for name, value in item.fields.items():
            if not isinstance(value, str) or not value.strip():
                continue
            now = result.values.get(name)
            verdict = decide(
                rules,
                name,
                current="" if now is None else now.value,
                current_kind=None if now is None else now.source_kind,
                current_date="" if now is None else now.source_date,
                offered=value,
                offered_kind=item.source_kind,
                offered_date=item.source_date,
                uncertain=name in item.uncertain,
            )
            if verdict.action == "take":
                result.values[name] = Resolved(
                    value=value,
                    source_kind=item.source_kind,
                    source_date=item.source_date,
                    observation_id=item.observation_id,
                )
                # A value the person takes settles the field's conflicts.
                if rules.trust_of(item.source_kind) == "user_stated":
                    result.conflicts = [c for c in result.conflicts if c.field != name]
            elif verdict.action == "propose" and not any(
                c.field == name and same_text(c.proposed, value) for c in result.conflicts
            ):
                result.conflicts.append(
                    Conflict(
                        field=name,
                        current="" if now is None else now.value,
                        proposed=value,
                        source_kind=item.source_kind,
                        observation_id=item.observation_id,
                        reason=verdict.reason,
                    )
                )
    return result


@dataclass(frozen=True)
class AutoMerge:
    """Whether a contribution joins an entity by itself (`entity_id`, `by`),
    must be asked about (`ask`, with the `candidates`), or is someone new."""

    entity_id: str | None = None
    by: str = ""
    ask: bool = False
    candidates: tuple[str, ...] = ()


def auto_merge(
    rules: MergeRules,
    identities: Mapping[str, str],
    *,
    by_identity: Callable[[str, str], str | None],
    by_external_id: Callable[[str, str], str | None],
    possible: Callable[[], Sequence[str]] = lambda: (),
) -> AutoMerge:
    """§10.7: join an existing entity only on an identical identity value
    (`rules.auto_merge.identities`, e.g. email) or an external id already in
    the mapping table; when the manager sees a possible match by other means
    (a name at the same company), ask; otherwise the entity is new."""
    policy = rules.auto_merge
    for system, value in identities.items():
        if not value.strip():
            continue
        if system in policy.identities:
            hit = by_identity(system, value)
            if hit:
                return AutoMerge(entity_id=hit, by=system)
        if policy.mapped_external_ids and system in rules.external_ids:
            hit = by_external_id(system, value)
            if hit:
                return AutoMerge(entity_id=hit, by=f"external_id:{system}")
    maybe = tuple(dict.fromkeys(possible()))
    if maybe:
        return AutoMerge(ask=True, candidates=maybe)
    return AutoMerge()
