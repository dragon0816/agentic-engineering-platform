"""Contract-first coverage for the local-only company host preview."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from common.execution import TraceIdentifiers
from host_runtime.cli import main
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.runtime import enrollment_request, inspect_host


def config(**changes: Any) -> CompanyHostConfiguration:
    return CompanyHostConfiguration.model_validate(
        {
            "device": {
                "bridge_id": "bridge-company-001",
                "registered_by": "engineer-a",
                "device_kind": "company_workstation",
                "windows_account_mode": "dedicated_user",
                "resource_scope": "corporate_internal",
                "local_isolation": "single_user",
                "interactive_slots": 1,
                "status": "active",
            },
            "workspace_root": r"C:\AEP\workspace",
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"password": "synthetic"},
        {"access_token": "synthetic"},
        {"workspace_root": "relative\\workspace"},
        {
            "device": {
                "bridge_id": "bridge-shared",
                "registered_by": "engineer-a",
                "device_kind": "shared_test_workstation",
                "windows_account_mode": "shared_user",
                "resource_scope": "external_only",
                "local_isolation": "cooperative_workspace",
            }
        },
    ],
)
def test_company_host_config_is_closed_and_contains_no_secret(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        config(**changes)


def test_doctor_is_side_effect_free_and_reports_every_local_requirement(tmp_path: Path) -> None:
    before = tuple(tmp_path.iterdir())
    report = inspect_host(
        config(),
        system_name="Windows",
        python_version=(3, 12),
        workspace_exists=True,
        workspace_writable=True,
    )
    assert report.status == "ready"
    assert all(check.status == "passed" for check in report.checks)
    limitations = " ".join(report.limitations)
    # What the preview cannot do is stated, and what it now can do is not
    # claimed as a limitation: the weekly report runs here once configured.
    # Matching the phrasing rather than a number, because the number was
    # wrong until slice 3f and a negative assertion carrying it said nothing.
    assert "workflow 13" in limitations and "Enrollment" in limitations
    unable = [line for line in report.limitations if "cannot execute" in line]
    assert unable == [line for line in unable if "workflow 13" in line], unable
    assert any("weekly report" in line and "needs" in line for line in report.limitations)
    assert "no vendor DUT/instrument driver" in limitations
    assert "DUT or instrument capability is included" not in limitations
    assert tuple(tmp_path.iterdir()) == before


def test_doctor_fails_closed_for_wrong_platform_python_or_workspace() -> None:
    report = inspect_host(
        config(),
        system_name="Linux",
        python_version=(3, 11),
        workspace_exists=False,
        workspace_writable=False,
    )
    assert report.status == "not_ready"
    assert {item.name for item in report.checks if item.status == "failed"} == {
        "operating_system",
        "python",
        "workspace",
    }


def test_enrollment_request_is_empty_advertisement_and_grants_no_authority() -> None:
    request = enrollment_request(
        config(),
        TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
    )
    assert request.advertisement.bridge_id == request.device.bridge_id
    assert request.advertisement.owner_id == request.device.registered_by
    assert request.advertisement.capabilities == ()
    assert request.advertisement.installed_tasks == ()
    assert request.advertisement.local_resources == ()
    payload = request.model_dump_json().lower()
    assert all(word not in payload for word in ("password", "token", "permission", "secret"))


def test_cli_writes_inspectable_request_without_echoing_invalid_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "host.json"
    source.write_text(config().model_dump_json(), encoding="utf-8")
    output = tmp_path / "request.json"
    assert main(["enrollment-request", "--config", str(source), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["device"]["bridge_id"] == (
        "bridge-company-001"
    )
    source.write_text('{"password":"do-not-echo"}', encoding="utf-8")
    assert main(["enrollment-request", "--config", str(source)]) == 2
    captured = capsys.readouterr()
    assert "do-not-echo" not in captured.err
