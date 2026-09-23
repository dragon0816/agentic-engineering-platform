"""A company host assembled from the files an operator put in its workspace,
and driven through the `aep-host` command line.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 2f. Every test builds
a real workspace on disk, wires the real Gateway, Bridge policy and workflow
engine, and reads a real file through the one capability the package ships.
No socket is opened and no external system is touched.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from capabilities.contracts import CapabilitySpec
from capabilities.files import READ_FILE_SPEC, ReadFileHandler, ReadFileInput, ReadFileOutput
from capabilities.runtime import InstalledCapabilities
from channels.telegram import TELEGRAM_CHANNEL
from common.assets import ExecutionDependencies
from common.authorization import DeviceAuthorization
from common.distribution import LocalStateError
from host_runtime.cli import main
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.host import (
    HostError,
    HostLayout,
    _decided_grants,
    build_runtime,
    host_report,
)
from host_runtime.state import SqliteLocalState
from models.credentials import StaticCredentials

TOKEN = "1234567890:AAE" + "x" * 32
BRIDGE = "bridge-company"


def device(**changes: Any) -> dict[str, Any]:
    return {
        "bridge_id": BRIDGE,
        "registered_by": "engineer",
        "device_kind": "company_workstation",
        "windows_account_mode": "dedicated_user",
        "resource_scope": "corporate_internal",
        "local_isolation": "single_user",
        **changes,
    }


def skill_manifest() -> dict[str, Any]:
    """One installed skill: `files.read <path>` triggers a workflow."""
    return {
        "metadata": {
            "identity": {"namespace": "engineering", "name": "file-skill", "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "private",
            "lifecycle": "published",
        },
        "alias": "files",
        "instructions": "Read a file inside this host's workspace through the governed capability.",
        "commands": [
            {
                "name": "read",
                "kind": "workflow",
                "target": {
                    "namespace": "engineering",
                    "name": "read-local-file",
                    "version": "1.0.0",
                },
            }
        ],
        "default_command": "read",
    }


def workflow_manifest() -> dict[str, Any]:
    """One installed workflow whose only step is the shipped read capability,
    taking its path from what the operator typed after the command."""
    return {
        "metadata": {
            "identity": {
                "namespace": "engineering",
                "name": "read-local-file",
                "version": "1.0.0",
            },
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "private",
            "lifecycle": "published",
        },
        "kind": "workflow",
        "description": "Read one workspace file through the governed filesystem capability",
        "execution": {"mode": "local"},
        "dependencies": {"central_required": False},
        "input_contract": "engineering.read-local-file.input.v1",
        "output_contract": "engineering.read-local-file.output.v1",
        "steps": [
            {
                "capability": {
                    "namespace": "filesystem",
                    "name": "read-file",
                    "version": "1.0.0",
                },
                "inputs": {"path": {"source": "run", "path": ["args"]}},
            }
        ],
    }


def membership_record(**changes: Any) -> dict[str, Any]:
    """A self-consistent membership record: the binding names the device it
    belongs to, and a company workstation's one member is its owner."""
    described = device(**changes.pop("device", {}))
    return {
        "device": described,
        "bindings": [
            {
                "bridge_id": described["bridge_id"],
                "actor": described["registered_by"],
                "role": "operator",
            }
        ],
        **changes,
    }


def grant_record() -> list[dict[str, Any]]:
    """The read capability's own policy record is `pending` and requires an
    approval, so a grant without `approval_ref` authorizes nothing."""
    return [
        {
            "actor": "engineer",
            "asset": {"namespace": "filesystem", "name": "read-file", "version": "1.0.0"},
            "permissions": ["filesystem.read"],
            "policy_refs": ["filesystem-read-policy"],
            "approval_ref": "workspace-read-approval",
        }
    ]


def workspace(
    tmp_path: Path,
    *,
    membership: dict[str, Any] | None = None,
    grants: list[dict[str, Any]] | None = None,
    assets: bool = True,
    telegram: dict[str, Any] | None = None,
    config_changes: Any = None,
) -> tuple[CompanyHostConfiguration, HostLayout]:
    """A company workspace exactly as an operator would leave it."""
    root = tmp_path / "workspace"
    layout = HostLayout.under(root)
    layout.skills.mkdir(parents=True, exist_ok=True)
    layout.workflows.mkdir(parents=True, exist_ok=True)
    if assets:
        (layout.skills / "files.json").write_text(json.dumps([skill_manifest()]), encoding="utf-8")
        (layout.workflows / "read.json").write_text(
            json.dumps(workflow_manifest()), encoding="utf-8"
        )
    if membership is not None:
        layout.membership.write_text(json.dumps(membership), encoding="utf-8")
    if grants is not None:
        layout.grants.write_text(json.dumps(grants), encoding="utf-8")
    if telegram is not None:
        layout.telegram.write_text(json.dumps(telegram), encoding="utf-8")
    (root / "notes.txt").write_text("first line\nsecond line\n", encoding="utf-8")
    config = CompanyHostConfiguration.model_validate(
        {
            "device": device(),
            "workspace_root": str(root),
            "namespace": "engineering",
            **(config_changes or {}),
        }
    )
    return config, layout


def ready(tmp_path: Path, **changes: Any) -> tuple[CompanyHostConfiguration, HostLayout]:
    return workspace(tmp_path, membership=membership_record(), grants=grant_record(), **changes)


def host_json(tmp_path: Path, config: CompanyHostConfiguration) -> Path:
    path = tmp_path / "host.json"
    path.write_text(config.model_dump_json(), encoding="utf-8")
    return path


def test_the_layout_is_one_workspace_and_a_relative_workspace_is_refused(tmp_path: Path) -> None:
    layout = HostLayout.under(tmp_path / "w")
    assert layout.membership.parent == layout.workspace_root
    assert layout.skills == layout.workspace_root / "assets" / "skills"
    assert layout.state == layout.workspace_root / "state.sqlite"
    with pytest.raises(ValidationError, match="absolute"):
        CompanyHostConfiguration.model_validate(
            {"device": device(), "workspace_root": "relative/workspace"}
        )
    # A Windows path stays valid wherever the file is inspected.
    assert (
        CompanyHostConfiguration.model_validate(
            {"device": device(), "workspace_root": r"C:\AEP\workspace"}
        ).namespace
        is None
    )


def test_a_host_with_its_files_reads_a_workspace_file_end_to_end(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        assert runtime.actor == "engineer"
        assert runtime.telegram is None
        code = main(
            [
                "ask",
                "--config",
                str(host_json(tmp_path, config)),
                f"files.read {layout.workspace_root / 'notes.txt'}",
            ]
        )
    assert code == 0
    # The run is in the Bridge's own durable state, under the actor who asked.
    with build_runtime(config) as runtime:
        runs = runtime.agent.runs()
        assert len(runs) == 1
        assert runs[0].actor == "engineer"
        assert runs[0].workflow.name == "read-local-file"
        assert runs[0].status == "succeeded"


def test_what_the_operator_sees_when_a_request_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    assert (
        main(["ask", "--config", str(path), f"files.read {layout.workspace_root / 'notes.txt'}"])
        == 0
    )
    printed = capsys.readouterr().out
    assert "route: workflow engineering/read-local-file@1.0.0" in printed
    assert "succeeded, 1 step(s) completed" in printed
    assert main(["status", "--config", str(path)]) == 0
    status = capsys.readouterr().out
    assert f"bridge {BRIDGE}" in status and "read-local-file: succeeded (engineer)" in status


def test_without_a_grant_the_policy_refuses_the_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Installing an asset is not permission to run it. The route resolves,
    the run is recorded, and the dispatch is refused."""
    config, layout = workspace(tmp_path, membership=membership_record())
    target = layout.workspace_root / "notes.txt"
    assert main(["ask", "--config", str(host_json(tmp_path, config)), f"files.read {target}"]) == 0
    assert "failure: permission_denied" in capsys.readouterr().out
    with build_runtime(config) as runtime:
        run = runtime.agent.runs()[0]
    assert run.status == "failed"
    # A grant that omits the approval this capability's policy requires is
    # no better than no grant at all.
    without_approval = grant_record()
    without_approval[0].pop("approval_ref")
    layout.grants.write_text(json.dumps(without_approval), encoding="utf-8")
    assert main(["ask", "--config", str(host_json(tmp_path, config)), f"files.read {target}"]) == 0
    assert "failure: permission_denied" in capsys.readouterr().out


def test_an_unbound_actor_is_refused_before_anything_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    target = layout.workspace_root / "notes.txt"
    code = main(
        [
            "ask",
            "--config",
            str(host_json(tmp_path, config)),
            "--actor",
            "someone-else",
            f"files.read {target}",
        ]
    )
    assert code == 1
    assert "refused: company_owner_required" in capsys.readouterr().out
    with build_runtime(config) as runtime:
        assert runtime.agent.runs() == ()


def test_a_missing_or_foreign_membership_record_stops_the_host(tmp_path: Path) -> None:
    config, layout = workspace(tmp_path, grants=grant_record())
    with pytest.raises(HostError) as missing:
        build_runtime(config)
    assert missing.value.code == "membership_missing"
    assert missing.value.path == layout.membership
    # A record that is valid in itself but describes another device would
    # admit the wrong people, so it is refused rather than reconciled.
    layout.membership.write_text(
        json.dumps(membership_record(device={"bridge_id": "bridge-other"})), encoding="utf-8"
    )
    with pytest.raises(HostError) as mismatch:
        build_runtime(config)
    assert mismatch.value.code == "membership_mismatch"
    layout.membership.write_text('{"device": {}}', encoding="utf-8")
    with pytest.raises(HostError) as invalid:
        build_runtime(config)
    assert invalid.value.code == "membership_invalid"


def test_an_unreadable_asset_is_named_without_its_contents(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    broken = layout.skills / "broken.json"
    broken.write_text('{"alias": "nope", "password": "hunter2"}', encoding="utf-8")
    with pytest.raises(HostError) as error:
        build_runtime(config)
    assert error.value.code == "asset_invalid" and error.value.path == broken
    assert main(["ask", "--config", str(host_json(tmp_path, config)), "files.read x"]) == 2
    printed = capsys.readouterr()
    assert "asset_invalid" in printed.err and "hunter2" not in printed.err
    # A grants file that is not a grant is refused the same way.
    broken.unlink()
    layout.grants.write_text('[{"actor": "engineer"}]', encoding="utf-8")
    with pytest.raises(HostError) as grants:
        build_runtime(config)
    assert grants.value.code == "grants_invalid"


def test_doctor_reports_what_the_host_has_been_given_without_writing_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = workspace(tmp_path)
    probe = {
        "system_name": "Windows",
        "python_version": (3, 12),
        "workspace_exists": True,
        "workspace_writable": True,
    }
    report = host_report(config, layout, **probe)  # type: ignore[arg-type]
    assert report.status == "ready" and report.runtime == "pending"
    named = {item.name: item for item in report.checks}
    assert named["membership"].status == "pending"
    assert named["state"].status == "pending"
    assert named["assets"].status == "passed" and "1 skill(s)" in named["assets"].detail
    assert not layout.state.exists()
    # Once the operator adds membership, the host is ready to run.
    layout.membership.write_text(json.dumps(membership_record()), encoding="utf-8")
    assert host_report(config, layout, **probe).runtime == "ready"  # type: ignore[arg-type]
    # A membership record for another device is a failure, not a pending
    # item. It keeps the Agent pending without claiming the installation
    # itself is broken, which is what `status` answers and what the
    # installer acts on.
    layout.membership.write_text(
        json.dumps(membership_record(device={"bridge_id": "bridge-other"})), encoding="utf-8"
    )
    broken = host_report(config, layout, **probe)  # type: ignore[arg-type]
    assert broken.status == "ready" and broken.runtime == "pending"
    assert {item.name for item in broken.checks if item.status == "failed"} == {"membership"}
    # Through the command line, on this machine, doctor says the same.
    assert main(["doctor", "--config", str(host_json(tmp_path, config)), "--json"]) in (0, 1)
    assert "membership" in capsys.readouterr().out


def test_a_state_file_that_cannot_be_read_is_reported_not_raised(tmp_path: Path) -> None:
    """A corrupt state file is SQLite's problem to report and this host's to
    translate: `doctor` says so and `ask` refuses, neither with a traceback."""
    config, layout = ready(tmp_path)
    layout.state.write_bytes(b"this is not a database")
    report = host_report(
        config,
        layout,
        system_name="Windows",
        python_version=(3, 12),
        workspace_exists=True,
        workspace_writable=True,
    )
    named = {item.name: item for item in report.checks}
    assert named["state"].status == "failed" and "cannot be read" in named["state"].detail
    assert report.status == "ready" and report.runtime == "pending"
    with pytest.raises(HostError) as error:
        build_runtime(config)
    assert error.value.code == "state_unavailable"
    assert main(["ask", "--config", str(host_json(tmp_path, config)), "files.read x"]) == 2


def test_reporting_on_a_state_file_changes_nothing_about_it(tmp_path: Path) -> None:
    """A diagnostic that writes is not a diagnostic. Opening the store to
    count its rows must not create a table or migrate a schema version."""
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        runtime.state.advance_cursor(TELEGRAM_CHANNEL, 3)
    # Put the file back to the schema the previous package wrote.
    with sqlite3.connect(layout.state) as conn:
        conn.execute("UPDATE local_meta SET value = '1' WHERE key = 'schema_version'")
        conn.execute("DROP TABLE channel_cursor")
        conn.commit()
    before = layout.state.read_bytes()
    probe = {
        "system_name": "Windows",
        "python_version": (3, 12),
        "workspace_exists": True,
        "workspace_writable": True,
    }
    report = host_report(config, layout, **probe)  # type: ignore[arg-type]
    assert {item.name: item.status for item in report.checks}["state"] == "passed"
    assert layout.state.read_bytes() == before
    with sqlite3.connect(layout.state) as conn:
        version = conn.execute(
            "SELECT value FROM local_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
    assert version == "1"
    # A read-only store refuses to write, and refuses another device's file.
    with SqliteLocalState(layout.state, bridge_id=BRIDGE, read_only=True) as store:
        assert store.runs() == ()
        with pytest.raises(LocalStateError, match="unavailable"):
            store.advance_cursor(TELEGRAM_CHANNEL, 9)
    with pytest.raises(LocalStateError, match="unavailable"):
        SqliteLocalState(layout.state, bridge_id="bridge-other", read_only=True)
    with pytest.raises(LocalStateError, match="unavailable"):
        SqliteLocalState(layout.workspace_root / "absent.sqlite", bridge_id=BRIDGE, read_only=True)
    # Opening it for writing is what migrates it, and only then.
    with build_runtime(config) as runtime:
        assert runtime.state.cursor(TELEGRAM_CHANNEL) is None


def authorization(*kinds: str, actor: str = "engineer") -> dict[str, Any]:
    """What the members of this device decided it may run, as the control
    plane would issue it. The shipped read capability's own policy requires
    an approval, so choosing it as a tool carries one."""
    chosen: list[dict[str, Any]] = []
    for kind in kinds:
        asset = {
            "skill": {"namespace": "engineering", "name": "file-skill", "version": "1.0.0"},
            "workflow": {"namespace": "engineering", "name": "read-local-file", "version": "1.0.0"},
            "capability": {"namespace": "filesystem", "name": "read-file", "version": "1.0.0"},
        }[kind]
        decision: dict[str, Any] = {
            "bridge_id": BRIDGE,
            "actor": actor,
            "kind": kind,
            "asset": asset,
            "decided_at": "2026-09-22T12:00:00+00:00",
        }
        if kind == "capability":
            decision["approval_ref"] = "workspace-read-approval"
            decision["approved_by"] = actor
        chosen.append(decision)
    return {
        "bridge_id": BRIDGE,
        "issued_at": "2026-09-22T12:30:00+00:00",
        "selections": chosen,
    }


def test_the_host_runs_what_its_members_chose_and_nothing_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = workspace(tmp_path, membership=membership_record())
    layout.authorization.write_text(
        json.dumps(authorization("skill", "workflow", "capability")), encoding="utf-8"
    )
    target = layout.workspace_root / "notes.txt"
    path = host_json(tmp_path, config)
    assert main(["ask", "--config", str(path), f"files.read {target}"]) == 0
    printed = capsys.readouterr().out
    assert "route: workflow engineering/read-local-file@1.0.0" in printed
    assert "succeeded, 1 step(s) completed" in printed
    # The grant came from the capability's own specification, not from the
    # decision, which named no permission at all.
    with build_runtime(config) as runtime:
        grant = runtime.agent.gateway.bridge.policy._grants[  # noqa: SLF001 - the policy is the subject
            ("engineer", ("filesystem", "read-file", "1.0.0"))
        ]
    assert grant.permissions == READ_FILE_SPEC.policy.required_permissions
    assert grant.policy_refs == READ_FILE_SPEC.policy.policy_refs
    assert grant.approval_ref == "workspace-read-approval"


def test_an_asset_nobody_chose_is_not_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The manifests are all sitting in the assets directory. What the device
    installs is what its members chose, so an unchosen Workflow is not there
    to run and an unchosen Skill is not there to route to."""
    config, layout = workspace(tmp_path, membership=membership_record())
    target = layout.workspace_root / "notes.txt"
    path = host_json(tmp_path, config)
    layout.authorization.write_text(
        json.dumps(authorization("skill", "capability")), encoding="utf-8"
    )
    assert main(["ask", "--config", str(path), f"files.read {target}"]) == 0
    assert "workflow_not_installed" in capsys.readouterr().out
    layout.authorization.write_text(json.dumps(authorization("capability")), encoding="utf-8")
    assert main(["ask", "--config", str(path), f"files.read {target}"]) == 0
    assert "needs_input (unknown_skill)" in capsys.readouterr().out
    with build_runtime(config) as runtime:
        assert runtime.agent.runs() == ()


def test_a_revoked_tool_stops_authorizing_the_same_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = workspace(tmp_path, membership=membership_record())
    target = layout.workspace_root / "notes.txt"
    path = host_json(tmp_path, config)
    layout.authorization.write_text(
        json.dumps(authorization("skill", "workflow", "capability")), encoding="utf-8"
    )
    assert main(["ask", "--config", str(path), f"files.read {target}"]) == 0
    assert "succeeded" in capsys.readouterr().out
    # The member changed their mind; the control plane reissues without it.
    layout.authorization.write_text(
        json.dumps(authorization("skill", "workflow")), encoding="utf-8"
    )
    assert main(["ask", "--config", str(path), f"files.read {target}"]) == 0
    assert "failure: permission_denied" in capsys.readouterr().out
    # Another member's decision authorizes nothing for this one.
    layout.authorization.write_text(
        json.dumps(authorization("skill", "workflow", "capability", actor="tester")),
        encoding="utf-8",
    )
    assert main(["ask", "--config", str(path), f"files.read {target}"]) == 0
    assert "failure: permission_denied" in capsys.readouterr().out


def test_doctor_reports_the_members_decisions_and_what_they_leave_installed(
    tmp_path: Path,
) -> None:
    config, layout = workspace(tmp_path, membership=membership_record())
    probe = {
        "system_name": "Windows",
        "python_version": (3, 12),
        "workspace_exists": True,
        "workspace_writable": True,
    }
    named = {item.name: item for item in host_report(config, layout, **probe).checks}  # type: ignore[arg-type]
    assert named["authorization"].status == "pending"
    assert "grants.json" in named["authorization"].detail
    assert named["assets"].detail == "1 skill(s) and 1 workflow(s) installed"
    # With decisions, the count is what this host would actually install.
    layout.authorization.write_text(json.dumps(authorization("skill")), encoding="utf-8")
    report = host_report(config, layout, **probe)  # type: ignore[arg-type]
    named = {item.name: item for item in report.checks}
    assert named["authorization"].status == "passed" and "1 decision(s)" in (
        named["authorization"].detail
    )
    assert named["assets"].detail == "1 skill(s) and 0 workflow(s) installed"
    assert report.runtime == "ready"
    # Two answers to one question is a failure the operator can see before
    # a command fails on it.
    layout.grants.write_text(json.dumps(grant_record()), encoding="utf-8")
    report = host_report(config, layout, **probe)  # type: ignore[arg-type]
    named = {item.name: item for item in report.checks}
    assert named["authorization"].status == "failed"
    assert "authorization_conflict" in named["authorization"].detail
    assert report.status == "ready" and report.runtime == "pending"


def test_a_tool_this_host_cannot_grant_is_named_rather_than_silently_ignored(
    tmp_path: Path,
) -> None:
    """A grant names the policy it was made under, so a capability that
    declares none cannot be granted. The host says so instead of building a
    policy that refuses every dispatch of it."""
    config, layout = workspace(tmp_path, membership=membership_record())
    layout.authorization.write_text(json.dumps(authorization("capability")), encoding="utf-8")
    decided = DeviceAuthorization.model_validate_json(layout.authorization.read_text())
    installed = InstalledCapabilities()
    installed.register(
        CapabilitySpec.model_validate(
            {
                **READ_FILE_SPEC.model_dump(),
                "policy": {
                    "approval_required": False,
                    "required_permissions": [],
                    "policy_refs": [],
                },
            }
        ),
        ReadFileHandler(layout.workspace_root),
        ReadFileInput,
        ReadFileOutput,
        ExecutionDependencies(central_required=False),
    )
    with pytest.raises(HostError) as error:
        _decided_grants(decided, installed)
    assert error.value.code == "authorization_ungrantable"
    # The capability this package actually ships does declare one.
    assert READ_FILE_SPEC.policy.policy_refs


def test_two_answers_to_one_question_are_refused(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    layout.authorization.write_text(json.dumps(authorization("capability")), encoding="utf-8")
    with pytest.raises(HostError) as conflict:
        build_runtime(config)
    assert conflict.value.code == "authorization_conflict"
    layout.grants.unlink()
    # A bundle that is valid in itself but was issued for another device.
    foreign = authorization("capability")
    foreign["bridge_id"] = "bridge-other"
    for decision in foreign["selections"]:
        decision["bridge_id"] = "bridge-other"
    layout.authorization.write_text(json.dumps(foreign), encoding="utf-8")
    with pytest.raises(HostError) as mismatch:
        build_runtime(config)
    assert mismatch.value.code == "authorization_mismatch"
    layout.authorization.write_text('{"bridge_id": "bridge-company"}', encoding="utf-8")
    with pytest.raises(HostError) as invalid:
        build_runtime(config)
    assert invalid.value.code == "authorization_invalid"


def test_a_telegram_ingress_is_built_only_when_its_secret_is_mapped(tmp_path: Path) -> None:
    ingress_config = {
        "credential": {"name": "telegram_bot"},
        "bridge_id": BRIDGE,
        "namespace": "engineering",
        "senders": [{"sender_id": 111, "actor": "engineer"}],
    }
    config, layout = ready(tmp_path, telegram=ingress_config)
    with pytest.raises(HostError) as unmapped:
        build_runtime(config)
    assert unmapped.value.code == "credential_unmapped"
    mapped = CompanyHostConfiguration.model_validate(
        {
            **config.model_dump(),
            "credentials": [
                {"secret": "telegram_bot", "environment_variable": "AEP_TELEGRAM_BOT_TOKEN"}
            ],
        }
    )
    with build_runtime(mapped) as runtime:
        assert runtime.telegram is not None
        assert runtime.telegram.config.senders[0].actor == "engineer"
        # The ingress reads its offset from this Bridge's own durable state.
        assert runtime.telegram.offset() is None
        runtime.state.advance_cursor(TELEGRAM_CHANNEL, 7)
        assert runtime.telegram.offset() == 7
    # An ingress naming another Bridge is refused.
    other, _ = ready(
        tmp_path / "other", telegram={**ingress_config, "bridge_id": "bridge-elsewhere"}
    )
    with pytest.raises(HostError) as wrong:
        build_runtime(other, resolver=StaticCredentials({"telegram_bot": TOKEN}))
    assert wrong.value.code == "telegram_invalid"


def test_the_telegram_command_needs_a_configured_ingress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, _ = ready(tmp_path)
    assert main(["telegram", "--config", str(host_json(tmp_path, config)), "--once"]) == 2
    assert "no Telegram ingress is configured" in capsys.readouterr().err


def test_a_host_without_a_namespace_will_not_guess_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path, config_changes={"namespace": None})
    path = host_json(tmp_path, config)
    target = layout.workspace_root / "notes.txt"
    assert main(["ask", "--config", str(path), f"files.read {target}"]) == 2
    assert "no namespace is configured" in capsys.readouterr().err
    assert (
        main(["ask", "--config", str(path), "--namespace", "engineering", f"files.read {target}"])
        == 0
    )


def test_a_configuration_that_cannot_be_used_says_which_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An operator edits this file by hand. Refusing without naming the field
    left them to guess which of a hundred lines to look at, which is what
    happened on 2026-09-23."""
    broken = tmp_path / "host.json"
    broken.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "device": device(),
                "workspace_root": str(tmp_path / "workspace"),
                "integrations": {
                    "github_project": {"project_number": 1, "credential": {"name": "board"}},
                    "weekly_report": {"workbook_path": "a-relative-path.xlsx"},
                },
                "credentials": [{"secret": "board", "environment_variable": "AEP_GITHUB_TOKEN"}],
            }
        ),
        encoding="utf-8",
    )
    assert main(["doctor", "--config", str(broken)]) == 2
    said = capsys.readouterr().err
    assert "integrations.github_project.owner" in said, "the missing field is named"
    assert "absolute path" in said, "and so is the rule the other one broke"
    assert "a-relative-path.xlsx" not in said, "but never what the file says"
    assert "No value from it is shown" in said


def test_a_configuration_that_is_not_json_says_where(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "host.json"
    broken.write_text('{"schema_version": "1",' + chr(10) + '  "device": }', encoding="utf-8")
    assert main(["doctor", "--config", str(broken)]) == 2
    said = capsys.readouterr().err
    assert "line 2" in said, "a position is not a value"


def test_a_configuration_that_is_not_there_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["doctor", "--config", str(tmp_path / "nowhere.json")]) == 2
    assert "cannot read" in capsys.readouterr().err
