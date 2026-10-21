"""Tool inputs the model got wrong in the 2026-10-21 live trial (#233).

`cards__list` was refused twice with `invalid_input` before it succeeded:
its schema offered `limit` as a bare integer while the contract allows
1–200, and the refusal said only `limit: less_than_equal`. The schemas now
carry the contract's own bounds and default, and a refusal names the bound
(never the value sent).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from agent.tool_recovery import classify
from capabilities.business_cards.contracts import (
    FindRequest,
    HarvestRequest,
    HistoryRequest,
    ListRequest,
    ProposalsRequest,
)
from common.base import Contract
from common.execution import Failure
from host_runtime.business_cards_tools import TOOLS
from workflow.dispatch import _where_invalid

BOUNDED: dict[tuple[str, str], type[Contract]] = {
    ("cards__find", "limit"): FindRequest,
    ("cards__list", "limit"): ListRequest,
    ("cards__history", "limit"): HistoryRequest,
    ("cards__proposals", "limit"): ProposalsRequest,
    ("cards__harvest_signatures", "limit"): HarvestRequest,
    ("cards__harvest_signatures", "days"): HarvestRequest,
}


def _schema(tool: str) -> dict[str, Any]:
    return next(schema for name, _, _, schema in TOOLS if name == tool)


def test_every_integer_argument_carries_the_contracts_bounds() -> None:
    for (tool, field), model in BOUNDED.items():
        offered = _schema(tool)["properties"][field]
        assert offered["type"] == "integer"
        rules = {
            key: getattr(rule, key)
            for rule in model.model_fields[field].metadata
            for key in ("ge", "le")
            if getattr(rule, key, None) is not None
        }
        assert (offered["minimum"], offered["maximum"]) == (rules["ge"], rules["le"]), tool
        assert offered["description"].startswith("leave out for"), tool
    # No integer argument of a cards tool is left unbounded.
    for name, _, _, schema in TOOLS:
        for field, offered in schema["properties"].items():
            if offered.get("type") == "integer":
                assert "maximum" in offered, (name, field)
    assert _schema("cards__list")["properties"]["limit"]["maximum"] == 200
    assert "never null" in next(d for n, _, d, _ in TOOLS if n == "cards__list")


def _refusal(body: dict[str, Any]) -> str:
    with pytest.raises(ValidationError) as refused:
        ListRequest.model_validate_json(json.dumps(body), strict=True)
    return _where_invalid(refused.value)


def test_a_refusal_names_the_bound_and_never_the_value() -> None:
    too_many = _refusal({"company": "Secret Client Co", "limit": 500})
    assert too_many == "Invalid input at limit: less_than_equal (le=200)"
    assert "500" not in too_many and "Secret" not in too_many
    assert _refusal({"limit": 0}) == "Invalid input at limit: greater_than_equal (ge=1)"
    status = _refusal({"status": "everyone"})
    assert status.startswith("Invalid input at status: literal_error (expected=")
    assert "'any'" in status and "everyone" not in status
    # Errors without a bound stay as they were.
    assert _refusal({"company": None}) == "Invalid input at company: string_type"
    hint = classify(Failure(code="invalid_input", message=too_many))
    assert hint is not None and hint.recoverable
    assert "(limit: less_than_equal (le=200))" in hint.hint
    assert "bounds shown" in hint.hint and "instead of sending null" in hint.hint
