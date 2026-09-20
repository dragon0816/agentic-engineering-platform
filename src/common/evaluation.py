"""Portable cases for deterministic, agent and scenario evaluation."""

from typing import Literal

from common.base import Contract, Symbol
from common.execution import RequestContext, RouteDecision, SideEffect


class EvaluationCase(Contract):
    case_id: Symbol
    category: Literal["deterministic", "agent", "scenario"]
    request: RequestContext
    expected_route: RouteDecision
    forbidden_side_effects: tuple[SideEffect, ...]
    assertions: tuple[Symbol, ...]
