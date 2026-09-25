"""Company-host wiring for later E2E-01 physical evidence collection."""

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

import pytest
from test_host_wiring import device, host_json, membership_record, workspace

from capabilities.dut_engineering.handlers import DUT_PHYSICAL_VALIDATE_SPEC
from common.assets import AssetIdentity
from common.execution import TraceIdentifiers
from common.local_agent import LocalCapabilityRequest
from dut.adapters import DutAdapter, PhysicalDriverConfiguration, SubprocessDutAdapter
from dut.contracts import (
    DutCommand,
    DutObservation,
    DutPhysicalValidationRequest,
    DutTarget,
    DutValidationEvidence,
    DutValidationRequest,
    ExpectedState,
    Measurement,
    MeasurementLimit,
)
from dut.runtime import review_dut_change
from host_runtime.cli import main
from host_runtime.contracts import CompanyHostConfiguration, HostLayout
from host_runtime.host import build_runtime, host_report

SKILL = AssetIdentity(namespace="rf", name="acme-dut-control", version="1.0.0")
TRACE = TraceIdentifiers(
    trace_id="dut-host-trace",
    request_id="dut-host-request",
    span_id="dut-host-span",
)


class RecordingAdapter(DutAdapter):
    mode: Literal["recording"] = "recording"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, request: DutValidationRequest, command: DutCommand) -> DutObservation:
        self.calls += 1
        return DutObservation(
            command=command.name,
            state={"ready": True},
            measurements=(Measurement(name="tx_power", value=15.0, unit="dBm"),),
        )


class PhysicalTrapAdapter(DutAdapter):
    mode: Literal["physical"] = "physical"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, request: DutValidationRequest, command: DutCommand) -> DutObservation:
        self.calls += 1
        raise AssertionError("a disabled physical adapter must not be invoked")


def dut_skill() -> dict[str, Any]:
    return {
        "metadata": {
            "identity": SKILL.model_dump(mode="json"),
            "owner": {"type": "team", "id": "rf"},
            "visibility": "team",
            "lifecycle": "published",
        },
        "alias": "acme_dut",
        "instructions": "Follow the reviewed ACME driver and measurement procedure.",
        "commands": [
            {
                "name": "validate_physical",
                "kind": "capability",
                "target": DUT_PHYSICAL_VALIDATE_SPEC.identity.model_dump(mode="json"),
            }
        ],
    }


def dut_grant() -> list[dict[str, Any]]:
    return [
        {
            "actor": "engineer",
            "asset": DUT_PHYSICAL_VALIDATE_SPEC.identity.model_dump(mode="json"),
            "permissions": list(DUT_PHYSICAL_VALIDATE_SPEC.policy.required_permissions),
            "policy_refs": list(DUT_PHYSICAL_VALIDATE_SPEC.policy.policy_refs),
            "approval_ref": "owner-approved-real-dut-run",
        }
    ]


def dut_binding(driver: Path, *, enabled: bool = True) -> dict[str, Any]:
    return {
        "skill": SKILL.model_dump(mode="json"),
        "target": {
            "resource_id": "dut-acme-001",
            "device_id": "acme-001",
            "vendor": "acme",
            "model": "radio-x1",
            "firmware": "FW-2.3",
        },
        "driver": {"executable": str(driver.resolve())},
        "physical_enabled": enabled,
    }


def request(*, bridge_id: str = "bridge-company") -> DutPhysicalValidationRequest:
    return DutPhysicalValidationRequest(
        validation=DutValidationRequest(
            bridge_id=bridge_id,
            workspace_revision="a" * 64,
            skill=SKILL,
            target=DutTarget(
                resource_id="dut-acme-001",
                device_id="acme-001",
                vendor="acme",
                model="radio-x1",
                firmware="FW-2.3",
            ),
            commands=(DutCommand(name="set_tx_power", arguments={"requested_dbm": 10.0}),),
            limits=(MeasurementLimit(name="tx_power", unit="dBm", minimum=14.5, maximum=15.5),),
            expected_state=(ExpectedState(field="ready", expected=True),),
        )
    )


def configured(
    tmp_path: Path, *, enabled: bool = True
) -> tuple[CompanyHostConfiguration, HostLayout, Path]:
    driver = tmp_path / "driver.exe"
    driver.write_bytes(b"fixture only")
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=dut_grant(),
        config_changes={"namespace": "rf", "dut": dut_binding(driver, enabled=enabled)},
    )
    (layout.skills / "dut.json").write_text(json.dumps([dut_skill()]), encoding="utf-8")
    return config, layout, driver


def test_recording_adapter_uses_the_real_host_admission_and_policy_path(tmp_path: Path) -> None:
    config, _, _ = configured(tmp_path)
    adapter = RecordingAdapter()
    with build_runtime(config, dut_adapter=adapter) as runtime:
        outcome = asyncio.run(
            runtime.agent.execute_capability(
                LocalCapabilityRequest(
                    ingress="local",
                    actor="engineer",
                    bridge_id=config.device.bridge_id,
                    target=DUT_PHYSICAL_VALIDATE_SPEC.identity,
                    arguments=request().model_dump(mode="json"),
                    trace=TRACE,
                )
            )
        )
    assert outcome.capability is not None and outcome.capability.status == "succeeded"
    evidence = DutValidationEvidence.model_validate(outcome.capability.data)
    assert evidence.status == "passed"
    assert evidence.mode == "recording" and evidence.evidence_level == "simulated"
    assert adapter.calls == 1
    with pytest.raises(ValueError, match="production-like physical evidence"):
        review_dut_change(
            implementation_digest="b" * 64,
            evidence=evidence,
            reviewer="rf-owner",
            approval_ref="review-1",
            approved=True,
        )


def test_cli_retains_recording_evidence_without_claiming_the_physical_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config, _, _ = configured(tmp_path)
    adapter = RecordingAdapter()
    monkeypatch.setattr("host_runtime.host.SubprocessDutAdapter", lambda _: adapter)
    asked = tmp_path / "dut-request.json"
    evidence = tmp_path / "dut-evidence.json"
    asked.write_text(request().model_dump_json(indent=2), encoding="utf-8")
    code = main(
        [
            "dut-validate",
            "--config",
            str(host_json(tmp_path, config)),
            "--request",
            str(asked),
            "--output",
            str(evidence),
        ]
    )
    assert code == 1
    assert "production-like gate is still pending" in capsys.readouterr().out
    saved = json.loads(evidence.read_text(encoding="utf-8"))
    assert saved["capability"]["data"]["evidence_level"] == "simulated"
    assert adapter.calls == 1


def test_subprocess_driver_is_fixed_no_shell_and_uses_typed_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "driver.exe"
    executable.write_bytes(b"fixture only")
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = DutObservation(
            command="set_tx_power",
            state={"ready": True},
            measurements=(Measurement(name="tx_power", value=15.0, unit="dBm"),),
        ).model_dump_json()

    def run(command: list[str], **options: object) -> Completed:
        captured.update({"command": command, **options})
        return Completed()

    monkeypatch.setattr("dut.adapters.subprocess.run", run)
    adapter = SubprocessDutAdapter(
        PhysicalDriverConfiguration(executable=str(executable.resolve()), arguments=("--json",))
    )
    observation = adapter.execute(request().validation, request().validation.commands[0])
    assert observation.measurements[0].value == 15.0
    assert captured["command"] == [str(executable.resolve()), "--json"]
    assert captured["shell"] is False
    payload = json.loads(str(captured["input"]))
    assert payload["target"]["firmware"] == "FW-2.3"
    assert "password" not in str(captured)


def test_host_config_and_doctor_keep_physical_execution_explicit(tmp_path: Path) -> None:
    config, layout, driver = configured(tmp_path, enabled=False)
    report = host_report(
        config,
        layout,
        system_name="Windows",
        python_version=(3, 12),
        workspace_exists=True,
        workspace_writable=True,
    )
    named = {item.name: item for item in report.checks}
    assert named["dut"].status == "pending"
    assert "explicitly disabled" in named["dut"].detail

    trap = PhysicalTrapAdapter()
    with build_runtime(config, dut_adapter=trap) as runtime:
        outcome = asyncio.run(
            runtime.agent.execute_capability(
                LocalCapabilityRequest(
                    ingress="local",
                    actor="engineer",
                    bridge_id=config.device.bridge_id,
                    target=DUT_PHYSICAL_VALIDATE_SPEC.identity,
                    arguments=request().model_dump(mode="json"),
                    trace=TRACE,
                )
            )
        )
    assert outcome.capability is not None and outcome.capability.failure is not None
    assert outcome.capability.failure.code == "physical_execution_disabled"
    assert trap.calls == 0

    with pytest.raises(ValueError, match="credential"):
        CompanyHostConfiguration.model_validate(
            {
                "device": device(),
                "workspace_root": str(tmp_path.resolve()),
                "dut": {
                    **dut_binding(driver),
                    "driver": {
                        "executable": str(driver.resolve()),
                        "arguments": ["--password", "secret-value"],
                    },
                },
            }
        )
