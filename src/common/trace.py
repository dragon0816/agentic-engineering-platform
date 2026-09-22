"""One record of a request's journey, safe to store.

`ObservedRun` is evidence a grader reads while grading. A trace is what a
person or a later evaluation reads back afterwards, so it has three duties the
evidence does not: it joins to the request that produced it, it keeps the
order things happened in, and it is safe to write down. The last is the hard
one. A failure message is the usual route by which a credential leaves a
process, and this record is built so that it cannot carry one: everything
stored passes through `redact`, and the contract refuses to exist around
anything redaction missed.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from common.assets import SECRET_PATTERN, AssetIdentity
from common.base import Contract, Symbol
from common.evaluation import ObservedRun, Origin, labelled
from common.execution import Failure, RouteDecision, RunStatus, TraceIdentifiers

MARKER = "[redacted]"
Kind = Literal["route", "dispatch", "outcome"]


class DispatchRecord(Protocol):
    """What the Bridge writes down for every dispatch. A protocol rather than
    the Bridge's own event type, so `common` does not import `workflow`."""

    @property
    def trace(self) -> TraceIdentifiers: ...
    @property
    def asset(self) -> AssetIdentity: ...
    @property
    def status(self) -> str: ...
    @property
    def code(self) -> str | None: ...


def carries_credential(value: object, label: str = "") -> bool:
    """The scan `no_credential_in_evidence` runs, applied to anything. A
    redaction marker is the absence of a credential, so it is removed before
    the pattern is applied: `password: <anything>` would otherwise match its
    own replacement, and nothing could ever be stored under that key."""
    return any(SECRET_PATTERN.search(line.replace(MARKER, "")) for line in labelled(value, label))


def redact(value: object, label: str = "") -> tuple[object, int]:
    """A copy with every recognizable credential replaced by the marker, and
    how many were replaced.

    A match inside a string is cut out of it, so the rest of a failure message
    survives. When the string still scans as a credential beside its field
    name, the whole value goes: either the field is named `password` and the
    value alone is the secret, or the string holds JSON whose quotes hid the
    match from the substitution, and in both cases there is nothing worth
    keeping."""
    if isinstance(value, str):
        cleaned, count = SECRET_PATTERN.subn(MARKER, value)
        if carries_credential(cleaned, label):
            return MARKER, count + 1
        return cleaned, count
    if isinstance(value, Mapping):
        total = 0
        redacted: dict[str, object] = {}
        for key, item in value.items():
            redacted[str(key)], count = redact(item, str(key))
            total += count
        return redacted, total
    if isinstance(value, (list, tuple)):
        total = 0
        items: list[object] = []
        for item in value:
            inner, count = redact(item, label)
            items.append(inner)
            total += count
        return items, total
    return value, 0


class TraceEvent(Contract):
    """One thing that happened, in order. Built from what the platform already
    records, the routing outcome and the Bridge's events, and carrying no
    payload: identities, statuses and codes are what a reader needs to see
    where a run went, and none of them can hold a credential."""

    sequence: int = Field(ge=0, strict=True)
    kind: Kind
    asset: AssetIdentity | None = None
    status: Symbol
    code: Symbol | None = None


class ExecutionTrace(Contract):
    """The record of one request: its route, every dispatch in Bridge order,
    the approvals behind them, the workflow's progress, what the model cost,
    how long it took, how it ended, and how many secrets were removed on the
    way in. `trace` is the request's own identifiers, so the record joins to
    the journal entries and Bridge events that share them."""

    trace: TraceIdentifiers
    events: tuple[TraceEvent, ...] = Field(min_length=2)
    decision: RouteDecision | None = None
    origin: Origin | None = None
    dispatched: tuple[AssetIdentity, ...] = ()
    ran: tuple[AssetIdentity, ...] = ()
    # Dispatched identities whose grant carried an approval reference. The
    # Roadmap asks for approvals in the record, and a reader asking "who
    # allowed that" needs the ones that were allowed as well as the ones that
    # were not.
    approved: tuple[AssetIdentity, ...] = ()
    unapproved: tuple[AssetIdentity, ...] = ()
    status: RunStatus | None = None
    completed_steps: int = Field(default=0, ge=0, strict=True)
    declared_steps: int = Field(default=0, ge=0, strict=True)
    model_calls: int = Field(default=0, ge=0, strict=True)
    duration_ms: int | None = Field(default=None, ge=0, strict=True)
    input_tokens: int = Field(default=0, ge=0, strict=True)
    output_tokens: int = Field(default=0, ge=0, strict=True)
    failure: Failure | None = None
    redactions: int = Field(default=0, ge=0, strict=True)

    @model_validator(mode="after")
    def ordered_and_clean(self) -> Self:
        if [event.sequence for event in self.events] != list(range(len(self.events))):
            raise ValueError("trace events are numbered from zero without gaps")
        if self.events[0].kind != "route" or self.events[-1].kind != "outcome":
            raise ValueError("a trace opens with the route and closes with the outcome")
        # Validated here and not only in `build`, so a trace assembled from
        # stored parts is held to the same rule as one the platform produced.
        if carries_credential(self.model_dump(mode="json")):
            raise ValueError("a trace must not carry credential material")
        return self

    @classmethod
    def build(
        cls,
        trace: TraceIdentifiers,
        observed: ObservedRun,
        dispatches: Iterable[DispatchRecord],
        *,
        approved: Iterable[AssetIdentity] = (),
    ) -> Self:
        """The record of one run, from the evidence it produced and the
        Bridge events it caused. An event carrying another request's
        identifiers is refused rather than filed here: a trace that quietly
        absorbed a neighbour's dispatch would be worse than none."""
        records = tuple(dispatches)
        for record in records:
            if record.trace != trace:
                raise ValueError("an event from another request cannot join this trace")
        decision = observed.decision
        events: list[TraceEvent] = [
            TraceEvent(
                sequence=0,
                kind="route",
                asset=decision.target if decision is not None else None,
                status=decision.kind if decision is not None else "unrouted",
                code=observed.origin,
            )
        ]
        events.extend(
            TraceEvent(
                sequence=index,
                kind="dispatch",
                asset=item.asset,
                status=item.status,
                code=item.code,
            )
            for index, item in enumerate(records, start=1)
        )
        status, code = _outcome(observed, records)
        events.append(TraceEvent(sequence=len(events), kind="outcome", status=status, code=code))
        raw = {
            "trace": trace.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in events],
            "decision": decision.model_dump(mode="json") if decision is not None else None,
            "origin": observed.origin,
            "dispatched": [item.model_dump(mode="json") for item in observed.dispatched],
            "ran": [item.model_dump(mode="json") for item in observed.ran],
            "approved": [item.model_dump(mode="json") for item in approved],
            "unapproved": [item.model_dump(mode="json") for item in observed.unapproved],
            "status": observed.status,
            "completed_steps": observed.completed_steps,
            "declared_steps": observed.declared_steps,
            "model_calls": observed.model_calls,
            "duration_ms": observed.duration_ms,
            "input_tokens": observed.input_tokens,
            "output_tokens": observed.output_tokens,
            "failure": (
                observed.failure.model_dump(mode="json") if observed.failure is not None else None
            ),
        }
        cleaned, redactions = redact(raw)
        if not isinstance(cleaned, dict):  # pragma: no cover - a mapping redacts to a mapping
            raise TypeError("redaction changed the shape of the record")
        return cls.model_validate({**cleaned, "redactions": redactions})


def _outcome(observed: ObservedRun, records: Sequence[DispatchRecord]) -> tuple[str, str | None]:
    """How the run ended, read from the strongest evidence present: the
    workflow's status when one ran, else the last dispatch's, else the
    routing failure. `nothing_ran` is the honest name for a route that
    resolved and was never dispatched."""
    code = observed.failure.code if observed.failure is not None else None
    if observed.status is not None:
        return observed.status, code
    if records:
        last = records[-1]
        return last.status, code if code is not None else last.code
    if observed.failure is not None:
        return "unresolved", code
    return "nothing_ran", None
