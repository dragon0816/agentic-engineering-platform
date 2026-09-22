"""One record of a request's journey, safe to store.

`ObservedRun` is evidence a grader reads while grading. A trace is what a
person or a later evaluation reads back afterwards, so it has three duties the
evidence does not: it joins to the request that produced it, it keeps the
order things happened in, and it is safe to write down. The last is the hard
one. A failure message is the usual route by which a credential leaves a
process, and this record is built so that it cannot carry one: the two fields
that can hold free text pass through `redact`, and the contract refuses to
exist around anything redaction missed, wherever the record came from.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from common.assets import REDACTED, SECRET_FIELD, SECRET_PATTERN, AssetIdentity
from common.base import Contract, Symbol
from common.evaluation import ObservedRun, Origin, labelled
from common.execution import Failure, RouteDecision, RunStatus, TraceIdentifiers

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
    """The scan `no_credential_in_evidence` runs, applied to anything. The
    pattern itself refuses to match `REDACTED`, so a record that has been
    redacted reads clean without any special case here."""
    return any(SECRET_PATTERN.search(line) for line in labelled(value, label))


def redact(value: object, label: str = "") -> tuple[object, int]:
    """A copy with every recognizable credential replaced by `REDACTED`, and
    how many were replaced. Three rules, in this order.

    A field named for a secret (`password`, `api_key`, ...) holds one whatever
    the shape of its value, so the whole value goes, a nested mapping
    included. A match inside a string is cut out of it, so the rest of a
    failure message survives; `SECRET_PATTERN` spans the whole secret, quoted
    value or private key block included. And a string that still scans as a
    credential beside its field name is replaced whole, because JSON inside a
    message hides the match from a substitution behind its quotes. Applying
    `redact` to its own output changes nothing and counts nothing."""
    if value is None or value == "" or value == REDACTED:
        return value, 0
    if label and SECRET_FIELD.match(label):
        return REDACTED, 1
    if isinstance(value, str):
        cleaned, count = SECRET_PATTERN.subn(REDACTED, value)
        if carries_credential(cleaned, label):
            return REDACTED, count + 1
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
    def ordered_consistent_and_clean(self) -> Self:
        """Held here and not only in `build`, so a trace assembled from stored
        parts is held to the same rules as one the platform produced: the
        events are in order and bracketed by the route and the outcome, the
        identity lists describe the dispatches the events record, and no
        field carries credential material."""
        if [event.sequence for event in self.events] != list(range(len(self.events))):
            raise ValueError("trace events are numbered from zero without gaps")
        if self.events[0].kind != "route" or self.events[-1].kind != "outcome":
            raise ValueError("a trace opens with the route and closes with the outcome")
        recorded = [event.asset for event in self.events if event.kind == "dispatch"]
        if recorded != list(self.dispatched):
            raise ValueError(
                "the dispatch events and `dispatched` name the same identities in order"
            )
        dispatched = set(self.dispatched)
        for name, items in (
            ("ran", self.ran),
            ("approved", self.approved),
            ("unapproved", self.unapproved),
        ):
            if not dispatched.issuperset(items):
                raise ValueError(f"`{name}` names an identity that was never dispatched")
        if dispatched and set(self.approved) & set(self.unapproved):
            raise ValueError("an identity was dispatched under an approval or without one")
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
        # Only the route's reason and the failure's message are free text.
        # Every other field is an identity, a Symbol or a number, and none of
        # those can hold a match, so they are stored as they are; the
        # validator's scan of the whole record stands behind that claim.
        route, redactions = redact(decision.model_dump(mode="json") if decision else None)
        failure, more = redact(
            observed.failure.model_dump(mode="json") if observed.failure else None
        )
        return cls(
            trace=trace,
            events=tuple(events),
            decision=RouteDecision.model_validate(route) if route is not None else None,
            origin=observed.origin,
            dispatched=observed.dispatched,
            ran=observed.ran,
            approved=tuple(approved),
            unapproved=observed.unapproved,
            status=observed.status,
            completed_steps=observed.completed_steps,
            declared_steps=observed.declared_steps,
            model_calls=observed.model_calls,
            duration_ms=observed.duration_ms,
            input_tokens=observed.input_tokens,
            output_tokens=observed.output_tokens,
            failure=Failure.model_validate(failure) if failure is not None else None,
            redactions=redactions + more,
        )


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
