"""Per-turn state of multi-agent delegation (V1), kept apart from the Gateway.

A parent conversation turn opens a `DelegationTurn`: its deadline on the
Gateway's clock, and the delegations it started and refused (at most
`MAX_DELEGATIONS_PER_TURN`). A delegated sub-run marks itself with a
`SubRun`, so the Gateway can leave the parent's person-facing parts out of it
(the session list, memory, forms, live progress) and never offer it the
delegation tool (depth 1).

Both live in context variables. `asyncio` tasks and `asyncio.to_thread` copy
them, and the objects are shared by reference, so parallel sub-runs of one
turn count against the same turn.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

#: Depth 1, at most three sub-agents per parent turn (owner Gate 0, ADR-MA5).
MAX_DELEGATIONS_PER_TURN = 3
#: Read-only sub-agents of one model reply run concurrently, at most this many.
MAX_PARALLEL_DELEGATIONS = 3
#: The Host tool's name; never offered inside a sub-run.
DELEGATE_TOOL = "agent__delegate"


@dataclass
class DelegationTurn:
    """One parent turn: its time budget and its delegations (counts only)."""

    deadline: float
    clock: Callable[[], float]
    started: int = 0
    refused: int = 0
    running: int = 0

    def remaining(self) -> float:
        return self.deadline - self.clock()

    def counts(self) -> dict[str, int]:
        return {"delegations": self.started, "delegations_refused": self.refused}


@dataclass
class SubRun:
    """One delegated sub-run: which profile, and what its model calls used."""

    profile: str
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_reports: int = 0

    def note_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self.model_calls += 1
        if input_tokens or output_tokens:
            self.token_reports += 1
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens


_TURN: ContextVar[DelegationTurn | None] = ContextVar("aep_delegation_turn", default=None)
_SUB_RUN: ContextVar[SubRun | None] = ContextVar("aep_delegation_sub_run", default=None)


def current_turn() -> DelegationTurn | None:
    return _TURN.get()


def sub_run() -> SubRun | None:
    """The sub-run being executed, if any (None in a parent turn)."""
    return _SUB_RUN.get()


def in_sub_run() -> bool:
    return _SUB_RUN.get() is not None


@contextmanager
def parent_turn(deadline: float, clock: Callable[[], float]) -> Iterator[DelegationTurn | None]:
    """The turn's delegation state; a run nested under a turn (a sub-run, a
    Host-check retry pass) keeps the outer one. Yields the turn it opened, or
    None when it only joined one."""
    if _TURN.get() is not None or _SUB_RUN.get() is not None:
        yield None
        return
    turn = DelegationTurn(deadline=deadline, clock=clock)
    token = _TURN.set(turn)
    try:
        yield turn
    finally:
        _TURN.reset(token)


@contextmanager
def running_sub_run(profile: str) -> Iterator[SubRun]:
    """Mark the code inside as one delegated sub-run."""
    marker = SubRun(profile=profile)
    token = _SUB_RUN.set(marker)
    try:
        yield marker
    finally:
        _SUB_RUN.reset(token)


def note_tokens(input_tokens: int, output_tokens: int) -> None:
    """One model call of the running sub-run (the Gateway calls it per call)."""
    marker = _SUB_RUN.get()
    if marker is not None:
        marker.note_tokens(input_tokens, output_tokens)
