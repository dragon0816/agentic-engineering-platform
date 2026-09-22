"""The resident local Agent on a Bridge computer: admits by membership on
every ingress alike, routes through the real Gateway, and keeps its
inventory and run state in durable local storage that outlives the process.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 2d.
"""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from evaluation_runner import GatewayRunner
from pydantic import ValidationError

from common.assets import AssetIdentity, AssetMetadata, Owner, PackageMetadata
from common.distribution import (
    InstallationPlan,
    LocalRunSummary,
    LocalStateError,
    PublishedAssetPackage,
    RemoteWorkflowJob,
)
from common.enrollment import BridgeBinding, BridgeDevice
from common.execution import ExecutionAuthorization, TraceIdentifiers
from common.local_agent import BridgeMembership, LocalAgentRequest
from host_runtime.agent import LocalAgent, LocalAgentOutcome
from host_runtime.state import SqliteLocalState

NOW = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
RELEASE = AssetIdentity(namespace="engineering", name="release-package", version="1.0.0")


def device(kind: str = "company_workstation", **changes: Any) -> BridgeDevice:
    profile = {
        "company_workstation": {
            "bridge_id": "bridge-company",
            "windows_account_mode": "dedicated_user",
            "resource_scope": "corporate_internal",
            "local_isolation": "single_user",
        },
        "shared_test_workstation": {
            "bridge_id": "bridge-shared",
            "windows_account_mode": "shared_user",
            "resource_scope": "external_only",
            "local_isolation": "cooperative_workspace",
        },
    }[kind]
    return BridgeDevice.model_validate(
        {"registered_by": "engineer", "device_kind": kind, **profile, **changes}
    )


def binding(actor: str, bridge_id: str = "bridge-company", **changes: Any) -> BridgeBinding:
    return BridgeBinding.model_validate(
        {"bridge_id": bridge_id, "actor": actor, "role": "operator", **changes}
    )


def company() -> BridgeMembership:
    return BridgeMembership(device=device(), bindings=(binding("engineer"),))


def shared() -> BridgeMembership:
    return BridgeMembership(
        device=device("shared_test_workstation"),
        bindings=(binding("engineer", "bridge-shared"), binding("tester", "bridge-shared")),
    )


def trace(suffix: str = "1") -> TraceIdentifiers:
    return TraceIdentifiers(
        trace_id=f"trace-{suffix}", request_id=f"request-{suffix}", span_id=f"span-{suffix}"
    )


def request(**changes: Any) -> LocalAgentRequest:
    return LocalAgentRequest.model_validate(
        {
            "ingress": "local",
            "actor": "engineer",
            "bridge_id": "bridge-company",
            "namespace": "engineering",
            "message": "shipment.run",
            "trace": trace(),
            **changes,
        }
    )


def job(**changes: Any) -> RemoteWorkflowJob:
    values = dict(changes)
    actor = values.pop("actor", "engineer")
    workflow = values.pop("workflow", RELEASE)
    request_trace = trace("job")
    return RemoteWorkflowJob.model_validate(
        {
            "job_id": "job-1",
            "ingress": "shared_platform",
            "actor": actor,
            "bridge_id": "bridge-company",
            "workflow": workflow,
            "arguments": {},
            "trace": request_trace,
            "authorization": ExecutionAuthorization(
                allowed=True,
                actor=actor,
                asset=workflow,
                trace=request_trace,
                policy_ref="policy/remote-workflow",
            ),
            **values,
        }
    )


def agent(membership: BridgeMembership, tmp_path: Path) -> tuple[LocalAgent, GatewayRunner]:
    """The Agent over the repository's real Gateway wiring: three skills, the
    two release workflows, a Bridge with a policy, and no control plane."""
    runner = GatewayRunner()
    tmp_path.mkdir(exist_ok=True)
    state = SqliteLocalState(tmp_path / "local-state.sqlite", bridge_id=membership.device.bridge_id)
    resident = LocalAgent(membership, runner.gateway(), state, clock=lambda: NOW)
    return resident, runner


def package(name: str, payload: bytes) -> PublishedAssetPackage:
    return PublishedAssetPackage(
        kind="workflow",
        metadata=AssetMetadata(
            identity=AssetIdentity(namespace="engineering", name=name, version="1.0.0"),
            owner=Owner(type="team", id="engineering"),
            visibility="organization",
            lifecycle="published",
            package=PackageMetadata(
                artifact_ref=f"registry://engineering/{name}/1.0.0",
                sha256=hashlib.sha256(payload).hexdigest(),
            ),
        ),
    )


def test_membership_is_this_device_only_and_a_company_device_has_one_owner() -> None:
    with pytest.raises(ValidationError, match="names the device"):
        BridgeMembership(device=device(), bindings=(binding("engineer", "bridge-other"),))
    with pytest.raises(ValidationError, match="bound to a device once"):
        BridgeMembership(device=device(), bindings=(binding("engineer"), binding("engineer")))
    with pytest.raises(ValidationError, match="one active member"):
        BridgeMembership(device=device(), bindings=(binding("engineer"), binding("tester")))
    with pytest.raises(ValidationError, match="registered owner"):
        BridgeMembership(device=device(), bindings=(binding("tester"),))
    # A revoked binding for somebody else beside the owner's active one is
    # history, not membership; a shared test device holds several members.
    kept = BridgeMembership(
        device=device(), bindings=(binding("engineer"), binding("tester", status="revoked"))
    )
    assert kept.binding_for("tester") is None
    assert shared().binding_for("tester") is not None
    assert shared().binding_for("stranger") is None


def test_a_request_is_closed_and_refuses_credential_material() -> None:
    with pytest.raises(ValidationError):
        request(message="run it with password: hunter2")
    with pytest.raises(ValidationError):
        LocalAgentRequest.model_validate({**request().model_dump(), "token": "x"})
    with pytest.raises(ValidationError):
        request(ingress="email")


def test_a_company_device_admits_only_its_owner_and_records_nothing_on_refusal(
    tmp_path: Path,
) -> None:
    resident, runner = agent(company(), tmp_path)
    refused = asyncio.run(resident.handle(request(actor="tester")))
    assert refused.refusal == "company_owner_required"
    assert refused.decision is None and refused.workflow is None and refused.run is None
    assert runner.bridge.events == ()
    assert resident.runs() == ()
    # The same rule on every ingress.
    for ingress in ("shared_platform", "telegram"):
        outcome = asyncio.run(resident.handle(request(actor="tester", ingress=ingress)))
        assert outcome.refusal == "company_owner_required"
    assert asyncio.run(resident.handle(request(bridge_id="bridge-other"))).refusal == (
        "device_mismatch"
    )
    assert runner.bridge.events == ()


def test_a_shared_test_device_admits_its_bound_actors_and_refuses_the_rest(
    tmp_path: Path,
) -> None:
    resident, runner = agent(shared(), tmp_path)
    for actor in ("engineer", "tester"):
        outcome = asyncio.run(
            resident.handle(request(actor=actor, bridge_id="bridge-shared", ingress="telegram"))
        )
        assert outcome.refusal is None
        assert outcome.decision is not None and outcome.decision.kind == "workflow"
    stranger = asyncio.run(resident.handle(request(actor="stranger", bridge_id="bridge-shared")))
    assert stranger.refusal == "actor_not_bound"
    disabled = BridgeMembership(
        device=device("shared_test_workstation", status="disabled"),
        bindings=(binding("engineer", "bridge-shared"),),
    )
    resident, runner = agent(disabled, tmp_path / "disabled")
    outcome = asyncio.run(resident.handle(request(bridge_id="bridge-shared")))
    assert outcome.refusal == "device_disabled"
    assert runner.bridge.events == ()


def test_an_admitted_message_reaches_a_real_workflow_through_the_gateway(
    tmp_path: Path,
) -> None:
    resident, runner = agent(company(), tmp_path)
    outcome = asyncio.run(resident.handle(request(ingress="local")))
    assert outcome.refusal is None
    assert outcome.decision is not None
    assert outcome.decision.kind == "workflow" and outcome.decision.target == RELEASE
    assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
    assert outcome.workflow.run.completed_steps == 2
    assert [event.status for event in runner.bridge.events] == ["succeeded", "succeeded"]
    # Recorded under the actor who asked.
    assert outcome.run is not None
    assert outcome.run.actor == "engineer" and outcome.run.workflow == RELEASE
    assert outcome.run.status == "succeeded" and outcome.run.updated_at == NOW
    assert resident.runs() == (outcome.run,)
    assert LocalAgentOutcome.model_validate_json(outcome.model_dump_json()) == outcome


def test_a_remote_job_executes_its_exact_workflow_without_routing(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    outcome = asyncio.run(resident.execute(job()))
    assert outcome.refusal is None and outcome.decision is None
    assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
    assert outcome.workflow.run.trace == trace("job")
    assert outcome.run is not None and outcome.run.actor == "engineer"
    assert len(runner.bridge.events) == 2
    # The membership rule applies to jobs as it does to messages.
    refused = asyncio.run(resident.execute(job(actor="tester", job_id="job-2")))
    assert refused.refusal == "company_owner_required"
    assert len(runner.bridge.events) == 2


def test_a_job_for_a_workflow_not_installed_here_is_refused_before_anything_runs(
    tmp_path: Path,
) -> None:
    resident, runner = agent(company(), tmp_path)
    missing = AssetIdentity(namespace="engineering", name="not-here", version="1.0.0")
    outcome = asyncio.run(resident.execute(job(workflow=missing)))
    assert outcome.refusal == "workflow_not_installed"
    assert runner.bridge.events == () and resident.runs() == ()


def test_a_run_keeps_its_owner_and_never_moves_backwards(tmp_path: Path) -> None:
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge-company")
    first = LocalRunSummary(
        run_id="run-1", actor="engineer", workflow=RELEASE, status="running", updated_at=NOW
    )
    state.record_run(first)
    later = first.model_copy(update={"status": "succeeded", "updated_at": NOW + timedelta(1)})
    state.record_run(later)
    assert state.runs() == (later,)
    with pytest.raises(LocalStateError, match="run_owner_fixed"):
        state.record_run(later.model_copy(update={"actor": "tester"}))
    with pytest.raises(LocalStateError, match="run_update_stale"):
        state.record_run(first)
    assert state.runs() == (later,)


def test_whole_plan_refusal_leaves_the_sqlite_inventory_untouched(tmp_path: Path) -> None:
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge-company")
    good = package("report", b"report")
    bad = package("release", b"release")
    plan = InstallationPlan(actor="engineer", bridge_id="bridge-company", packages=(good, bad))
    with pytest.raises(LocalStateError, match="artifact_hash_mismatch"):
        state.install(
            plan,
            {
                "registry://engineering/report/1.0.0": b"report",
                "registry://engineering/release/1.0.0": b"tampered",
            },
        )
    assert state.installed() == ()
    with pytest.raises(LocalStateError, match="installation_bridge_mismatch"):
        state.install(plan.model_copy(update={"bridge_id": "bridge-other"}), {})
    installed = state.install(
        plan,
        {
            "registry://engineering/report/1.0.0": b"report",
            "registry://engineering/release/1.0.0": b"release",
        },
    )
    assert [item.identity.name for item in installed] == ["report", "release"]
    with pytest.raises(LocalStateError, match="duplicate_install"):
        state.install(plan, {"registry://engineering/report/1.0.0": b"report"})
    assert len(state.installed()) == 2


def test_inventory_and_runs_survive_reopening_the_file_and_fill_the_snapshot(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.sqlite"
    with SqliteLocalState(path, bridge_id="bridge-company") as state:
        state.install(
            InstallationPlan(
                actor="engineer",
                bridge_id="bridge-company",
                packages=(package("report", b"report"),),
            ),
            {"registry://engineering/report/1.0.0": b"report"},
        )
        state.record_run(
            LocalRunSummary(
                run_id="run-1",
                actor="engineer",
                workflow=RELEASE,
                status="succeeded",
                updated_at=NOW,
            )
        )
    with SqliteLocalState(path, bridge_id="bridge-company") as reopened:
        assert [item.identity.name for item in reopened.installed()] == ["report"]
        assert reopened.installed()[0].installed_by == "engineer"
        assert [item.run_id for item in reopened.runs()] == ["run-1"]
        snapshot = reopened.snapshot(device(), observed_at=NOW + timedelta(minutes=1))
        with pytest.raises(ValidationError):
            reopened.snapshot(device(), observed_at=NOW - timedelta(minutes=1))
    assert snapshot.authority == "bridge"
    assert snapshot.device.bridge_id == "bridge-company"
    assert [item.identity.name for item in snapshot.installed] == ["report"]
    assert snapshot.runs[0].status == "succeeded"
    # The file knows whose it is.
    with pytest.raises(LocalStateError, match="unavailable"):
        SqliteLocalState(path, bridge_id="bridge-other")


def test_company_work_runs_with_no_control_plane_in_the_process(tmp_path: Path) -> None:
    """Local-first resilience: the release workflow's manifest declares no
    central service, and nothing in this process is a Registry, a control
    plane or a transport. The run succeeds anyway."""
    resident, _ = agent(company(), tmp_path)
    outcome = asyncio.run(resident.handle(request()))
    assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
    snapshot = resident.snapshot(observed_at=NOW)
    assert snapshot.runs[0].run_id == outcome.workflow.run.run_id
    assert snapshot.installed == ()
