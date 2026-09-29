import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from common.assets import AssetIdentity
from validation.contracts import (
    CompanyAgentValidationProfile,
    OwnerDecision,
    ValidationExecution,
    ValidationRequest,
    ValidationTarget,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "deploy/windows-preview/validation/company-agent-integration-v1/profile.json"


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


def test_company_agent_profile_is_fixed_local_and_least_privilege() -> None:
    profile = CompanyAgentValidationProfile.model_validate_json(PROFILE.read_text(encoding="utf-8"))

    assert profile.model.endpoint.base_url is None
    assert profile.model.binding is not None
    assert profile.model.binding.host == "127.0.0.1"
    assert profile.model.binding.strategy == "first_available"
    assert (profile.model.binding.port_start, profile.model.binding.port_end) == (18765, 18864)
    assert profile.model.binding.base_path == "/v1"
    assert profile.model.endpoint.credential is None
    assert profile.model.endpoint.capabilities.local is True
    grants = {grant.asset.key: grant for grant in profile.grants}
    assert set(grants) == {
        ("workflow-author", "draft", "1.0.0"),
        ("knowledge-query", "ask", "1.0.0"),
        ("company-agent", "personal-proof-fixture-read", "1.0.0"),
    }
    assert grants[("workflow-author", "draft", "1.0.0")].permissions == ("workflow-author.draft",)
    assert grants[("knowledge-query", "ask", "1.0.0")].permissions == ("knowledge-query.ask",)
    assert grants[("company-agent", "personal-proof-fixture-read", "1.0.0")].permissions == (
        "filesystem.read",
    )
    dumped = json.dumps(profile.model_dump(mode="json"))
    assert "filesystem/read-file" not in dumped
    assert "api_key" not in dumped.casefold()
    assert profile.model.endpoint.credential is None


@pytest.mark.parametrize(
    "path", ("../outside.pdf", "C:/outside.pdf", "folder\\\\file.pdf", "/outside.pdf")
)
def test_company_agent_profile_rejects_paths_outside_its_bundle(path: str) -> None:
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    payload["sop"]["pdf_path"] = path

    with pytest.raises(ValidationError, match="relative POSIX paths"):
        CompanyAgentValidationProfile.model_validate(payload)


def test_company_agent_profile_rejects_remote_or_credentialed_fixture_models() -> None:
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    payload["model"]["binding"] = None
    payload["model"]["endpoint"]["base_url"] = "https://gateway.example.invalid/v1"
    with pytest.raises(ValidationError, match="HTTP loopback"):
        CompanyAgentValidationProfile.model_validate(payload)

    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    payload["model"]["endpoint"]["credential"] = {"name": "fixture_token"}
    with pytest.raises(ValidationError, match="carries no credential"):
        CompanyAgentValidationProfile.model_validate(payload)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"host": "localhost"}, "literal_error"),
        ({"port_start": 80}, "greater than or equal to 1024"),
        ({"port_start": 18864, "port_end": 18765}, "must not precede"),
        ({"port_start": 18765, "port_end": 18893}, "at most 128 ports"),
    ],
)
def test_company_agent_profile_rejects_unsafe_loopback_binding(
    changes: dict[str, object], message: str
) -> None:
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    payload["model"]["binding"].update(changes)

    with pytest.raises(ValidationError, match=message):
        CompanyAgentValidationProfile.model_validate(payload)


def test_dynamic_loopback_binding_cannot_hide_a_fixed_url() -> None:
    payload = json.loads(PROFILE.read_text(encoding="utf-8"))
    payload["model"]["endpoint"]["base_url"] = "http://127.0.0.1:8765/v1"

    with pytest.raises(ValidationError, match="requires an unset endpoint base URL"):
        CompanyAgentValidationProfile.model_validate(payload)
