"""Memory space declarations and merge rules (docs/phases/ACCUMULATED_MEMORY.md §3).

Shared contract formats, never data: a Skill or Workflow manifest declares
the memory spaces it manages, contributes to or reads (`memory_spaces`), and
the manager of a space ships its merge rules as data (`MergeRules`). The
Memory Service in the Host (`memory.service`) enforces both. Field
provenance follows Knowledge Strategy ADR-K11 (`origin`, `set_by`, `set_at`,
`reason`), so personal memory and team knowledge share one contract, never
one store (owner decision 2026-10-20, §10.5).

Spaces are named by domain, not by Skill (§3.8): `contacts/org` holds people,
companies and reporting lines, whichever Skill or source fills it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from common.base import Contract, Symbol, Text

#: `<domain>/<name>`, lower case, e.g. `contacts/org`, `projects/chipset-readiness`.
SpaceName = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:/[a-z][a-z0-9]*(?:-[a-z0-9]+)*){1,2}$",
        max_length=80,
    ),
]
MemoryKind = Literal["entities", "sync_state", "preferences", "facts", "notes"]
Sensitivity = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
#: manager: defines schema and merge rules, reads and writes; contributor:
#: adds observations and reads; reader: reads only.
MemoryRole = Literal["manager", "contributor", "reader"]
#: How long a space keeps what it holds: `until_deleted`, or an ISO 8601
#: period of days, months or years (`P30D`, `P12M`, `P2Y`).
Retention = Annotated[str, StringConstraints(pattern=r"^(?:until_deleted|P[1-9][0-9]{0,3}[DMY])$")]
#: A versioned reference to data the manager ships (`contacts.org.person.v1`).
DataRef = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]*\.v[0-9]+$", max_length=120)]

_ROLE_RANK: dict[str, int] = {"reader": 1, "contributor": 2, "manager": 3}


class MemorySpaceDeclaration(Contract):
    """One space an asset touches. A manager says what the space is (kinds,
    sensitivity, retention, schema and merge rules); a contributor or a
    reader only names it (and, optionally, the kinds it touches)."""

    space: SpaceName
    role: MemoryRole
    kinds: tuple[MemoryKind, ...] = Field(default=(), max_length=5)
    sensitivity: Sensitivity | None = None
    retention: Retention | None = None
    schema_ref: DataRef | None = None
    merge_rules: DataRef | None = None

    @model_validator(mode="after")
    def complete_for_the_manager(self) -> Self:
        if len(set(self.kinds)) != len(self.kinds):
            raise ValueError("memory kinds must be unique")
        defining = (self.sensitivity, self.retention, self.schema_ref, self.merge_rules)
        if self.role == "manager":
            if not self.kinds or any(item is None for item in defining):
                raise ValueError(
                    "a space manager declares kinds, sensitivity, retention, schema_ref "
                    "and merge_rules"
                )
        elif any(item is not None for item in defining):
            raise ValueError(
                "only the space manager declares sensitivity, retention, schema_ref and merge_rules"
            )
        return self

    def allows(self, needed: MemoryRole) -> bool:
        """Whether this role includes `needed` (manager > contributor > reader)."""
        return _ROLE_RANK[self.role] >= _ROLE_RANK[needed]


def check_declarations(
    declarations: Sequence[MemorySpaceDeclaration],
) -> tuple[MemorySpaceDeclaration, ...]:
    """The rule a manifest's `memory_spaces` obeys: one declaration per space."""
    names = [item.space for item in declarations]
    if len(names) != len(set(names)):
        raise ValueError("memory spaces must be declared once each")
    return tuple(declarations)


def manager_conflicts(
    installed: Iterable[tuple[tuple[str, str], Sequence[MemorySpaceDeclaration]]],
    candidate: tuple[str, str],
    declarations: Sequence[MemorySpaceDeclaration],
) -> tuple[str, ...]:
    """Spaces `candidate` (namespace, name) declares to manage that another
    installed asset already manages: a space has one manager. Other versions
    of the same asset are not a conflict."""
    managed: dict[str, tuple[str, str]] = {}
    for asset, items in installed:
        for item in items:
            if item.role == "manager":
                managed.setdefault(item.space, asset)
    return tuple(
        item.space
        for item in declarations
        if item.role == "manager" and managed.get(item.space, candidate) != candidate
    )


# -- merge rules (data, shipped by the space manager) ---------------------

#: How much a source is trusted (§3.8.5): what the person said, a document
#: (a card, a signature block), a system record filled in by people (C4C),
#: a model's inference.
TrustClass = Literal["user_stated", "document", "system_record", "inferred"]
#: ADR-K11 `origin` of a current value; `tool` is a deterministic tool reading
#: a source (a card, a signature).
Origin = Literal["human", "tool", "import", "agent", "migration"]
DEFAULT_PRECEDENCE: tuple[TrustClass, ...] = (
    "user_stated",
    "document",
    "system_record",
    "inferred",
)


class FieldMergeRule(Contract):
    """How a field's current value follows its observations.

    - `newest_evidence`: the newest evidence wins; older evidence never
      replaces newer.
    - `precedence`: a source of a higher trust class wins whatever its date;
      one of a lower class never replaces it (`lower_conflict` says whether
      it becomes a proposal); within one class, the newest evidence wins.

    Whatever the policy, a value the person stated wins: differing evidence
    becomes a proposal (`user_conflict: propose`), or only when it is newer
    than the person's statement (`propose_if_newer`)."""

    policy: Literal["newest_evidence", "precedence"] = "newest_evidence"
    precedence: tuple[TrustClass, ...] = DEFAULT_PRECEDENCE
    lower_conflict: Literal["propose", "keep"] = "propose"
    user_conflict: Literal["propose", "propose_if_newer"] = "propose"

    @model_validator(mode="after")
    def complete_precedence(self) -> Self:
        if sorted(self.precedence) != sorted(DEFAULT_PRECEDENCE):
            raise ValueError("precedence lists every trust class once")
        return self


class RelationRule(Contract):
    """A relationship between entities (a reporting line): drawn solid only
    with evidence of one of `solid_evidence`; any other evidence is an
    inference, drawn dashed."""

    relation: Symbol
    solid_evidence: tuple[Symbol, ...] = Field(min_length=1)


class AutoMergeRule(Contract):
    """When a contribution from another source joins an existing entity by
    itself (§10.7): an identical value of one of `identities` (`email`), or
    an external id already in the space's mapping table. Anything else is
    asked about, never merged silently."""

    identities: tuple[Symbol, ...] = ()
    mapped_external_ids: bool = True


class MergeRules(Contract):
    """A space's merge rules, as data (§3.8.3)."""

    rules_id: DataRef
    #: Every source kind the space accepts, with its trust class; an
    #: observation of any other kind is refused.
    trust: dict[Symbol, TrustClass] = Field(min_length=1)
    default: FieldMergeRule = FieldMergeRule()
    fields: dict[Symbol, FieldMergeRule] = Field(default_factory=dict)
    #: External id systems (a C4C account id, a card image hash): kept for
    #: matching only, never a field value and never a name.
    external_ids: tuple[Symbol, ...] = ()
    relations: tuple[RelationRule, ...] = ()
    auto_merge: AutoMergeRule = AutoMergeRule()

    @model_validator(mode="after")
    def user_is_known(self) -> Self:
        if "user" not in self.trust or self.trust["user"] != "user_stated":
            raise ValueError("the source kind `user` is user_stated in every space")
        return self

    def rule_for(self, field: str) -> FieldMergeRule:
        return self.fields.get(field, self.default)

    def trust_of(self, source_kind: str) -> TrustClass | None:
        return self.trust.get(source_kind)

    def relation(self, name: str) -> RelationRule | None:
        return next((item for item in self.relations if item.relation == name), None)


class Decision(Contract):
    """What a merge rule does with one offered value."""

    action: Literal["take", "keep", "propose"]
    reason: Literal[
        "",
        "empty",
        "same",
        "user_set",
        "lower_trust",
        "uncertain",
        "older_evidence",
        "match_only",
    ] = ""


class FieldProvenance(Contract):
    """Where a current value came from (ADR-K11): the source kind and date of
    the evidence, the observation, the `origin`, who set it (`set_by`, filled
    by the Host as `<actor> via <channel>`), when and why."""

    field: Symbol
    source_kind: Symbol
    source_date: str
    observation_id: int | None = None
    origin: Origin | Literal[""] = ""
    set_by: str = ""
    set_at: str = ""
    reason: str = ""


class SpaceSummary(Contract):
    """A registered space as the registry row holds it."""

    space: SpaceName
    manager: Text
    table_prefix: Text
    declaration: MemorySpaceDeclaration
    rules: MergeRules


# -- sync state (accumulated memory M2, §3.3 and §4) ----------------------

#: How many message ids a sync state keeps for de-duplication at its
#: boundary (the overlap window re-reads a little of the previous pass).
MAX_SYNC_IDS = 500
SyncAction = Literal["advance", "reset", "restore"]


class SyncState(Contract):
    """How far one source has been processed for one key in a space, e.g.
    `{space: contacts/org, source: mail:Inbox, key: wnc.com.tw}`: everything
    up to `last_message_date` was processed by `extractor_version`;
    `last_message_ids` are the ids processed near that boundary, so an
    overlapping re-read skips them. `updated_by` is filled by the Host
    (`<actor> via <channel>`)."""

    space: SpaceName
    source: Text
    key: Text
    last_message_date: str
    last_message_ids: tuple[str, ...] = ()
    extractor_version: str = ""
    updated_at: str
    updated_by: str


class SyncHistoryEntry(Contract):
    """One change of a sync state, kept so a reset is audited and can be
    restored: the state before (`old`, None when there was none) and after
    (`new`, None after a reset)."""

    history_id: int
    space: SpaceName
    source: Text
    key: Text
    action: SyncAction
    at: str
    actor: str
    reason: str = ""
    old: SyncState | None = None
    new: SyncState | None = None


def origin_for(trust: TrustClass | None, source_kind: str) -> Origin:
    """ADR-K11 `origin` of a value from a source of this trust class."""
    if trust == "user_stated":
        return "human"
    if trust == "inferred":
        return "agent"
    if source_kind == "import":
        return "import"
    return "tool"


def declarations_of(manifest: object) -> tuple[MemorySpaceDeclaration, ...]:
    """A Skill's or Workflow's `memory_spaces`, or none."""
    found = getattr(manifest, "memory_spaces", ())
    return tuple(found) if isinstance(found, tuple) else ()


def roles(declarations: Iterable[MemorySpaceDeclaration]) -> Mapping[str, MemoryRole]:
    return {item.space: item.role for item in declarations}
