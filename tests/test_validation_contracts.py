from typing import Any

import pytest
from pydantic import ValidationError

from common.assets import AssetIdentity
from validation.contracts import (
    OwnerDecision,
    ValidationExecution,
    ValidationRequest,
    ValidationTarget,
)


def asset(name: str) -> AssetIdentity:
    return AssetIdentity(namespace="engineering", name=name, version="1.0.0")


def request(**changes: Any) -> ValidationRequest:
    values: dict[str, Any] = {
        "request_id": "validate-workflow-11",
        "target": ValidationTarget(
            capability=asset("weekly-report"),
            package_commit="a" * 40,
            build="0.1.0",
            test_profile="aep-capability-suite",
        ),
        "execution": ValidationExecution(
            bridge="company-pc-01",
            actor="employee.id",
            required_grants=(asset("weekly-report"),),
            model_routing="company-gateway-default",
            knowledge_assets=(asset("product-knowledge"),),
        ),
        "acceptance_criteria": ("workflow-11-completed", "knowledge-query-grounded"),
        "max_codex_repair_attempts": 3,
        "max_hermes_retests": 3,
    }
    values.update(changes)
    return ValidationRequest(**values)


def test_validation_request_is_serializable_and_pins_the_tested_revision() -> None:
    value = request()

    assert value.target.package_commit == "a" * 40
    assert value.model_dump(mode="json")["execution"]["actor"] == "employee.id"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"acceptance_criteria": ()}, "at least one acceptance criterion"),
        ({"acceptance_criteria": ("same", "same")}, "acceptance criteria must be unique"),
        ({"max_hermes_retests": 4}, "less than or equal to 3"),
    ],
)
def test_validation_request_rejects_ambiguous_or_unbounded_work(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        request(**changes)


def test_owner_decision_requires_a_declared_kind_and_explicit_choice() -> None:
    decision = OwnerDecision(
        decision_id="decision-108",
        request_id="validate-workflow-11",
        kind="authorize_test_actor",
        choice="approved",
        evidence="Issue-108 reviewed",
    )

    assert decision.choice == "approved"

    with pytest.raises(ValidationError):
        OwnerDecision.model_validate(
            {
                "decision_id": "decision-108",
                "request_id": "validate-workflow-11",
                "kind": "authorize_test_actor",
                "choice": "approved",
            }
        )
