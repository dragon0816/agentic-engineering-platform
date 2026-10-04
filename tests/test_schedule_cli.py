"""Local schedule controls persist intent but never dispatch a due occurrence."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_host_wiring import host_json, ready

from common.scheduling import ScheduleDefinition
from host_runtime.cli import main
from host_runtime.schedules import SqliteScheduleStore


def _definition(
    path: Path,
    *,
    owner: str = "engineer",
    name: str = "read-local-file",
    kind: str = "workflow",
) -> Path:
    source = path / "schedule.json"
    source.write_text(
        json.dumps(
            {
                "schedule_id": "daily-read",
                "owner": owner,
                "target_kind": kind,
                "target": {"namespace": "engineering", "name": name, "version": "1.0.0"},
                "recurrence": {"kind": "daily", "timezone": "Asia/Taipei", "at": "09:00"},
                "runtime_inputs": {"args": "notes.txt"},
            }
        ),
        encoding="utf-8",
    )
    return source


def test_create_list_pause_resume_history_are_durable_and_inert(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    host = host_json(tmp_path, config)
    source = _definition(tmp_path)

    def command(*args: str) -> int:
        return main(["schedules", "--config", str(host), *args])

    assert command("create", "--definition", str(source)) == 0
    assert "daily-read: active" in capsys.readouterr().out
    assert command("list") == 0
    assert "engineering/read-local-file@1.0.0" in capsys.readouterr().out
    assert command("pause", "daily-read") == 0
    assert "daily-read: paused" in capsys.readouterr().out
    assert command("list") == 0
    assert command("resume", "daily-read") == 0
    assert "daily-read: active" in capsys.readouterr().out
    assert command("history", "daily-read") == 0
    assert capsys.readouterr().out == ""
    with SqliteScheduleStore(
        layout.workspace_root / "schedules.sqlite", bridge_id="bridge-company"
    ) as store:
        record = store.get("daily-read", owner="engineer")
        assert record.status == "active"
        assert record.next_due_at > datetime.now(UTC) - timedelta(minutes=1)
        assert record.definition.target.name == "read-local-file"
        assert store.history("daily-read", owner="engineer") == ()
        assert store.pending_claims() == ()


def test_create_denies_different_owner_missing_workflow_and_untrusted_task(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    host = host_json(tmp_path, config)

    for change in ({"owner": "other"}, {"name": "missing"}, {"kind": "agent_task"}):
        source = _definition(tmp_path, **change)
        assert (
            main(["schedules", "--config", str(host), "create", "--definition", str(source)])
            == 1
        )
    assert not (layout.workspace_root / "schedules.sqlite").exists()


def test_unbound_host_cannot_manage_schedules(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    host = host_json(tmp_path, config)
    source = _definition(tmp_path)
    layout.membership.write_text(
        json.dumps({"device": config.device.model_dump(mode="json"), "bindings": []}),
        encoding="utf-8",
    )
    assert main(["schedules", "--config", str(host), "create", "--definition", str(source)]) == 1
    assert main(["schedules", "--config", str(host), "list"]) == 1
    assert not (layout.workspace_root / "schedules.sqlite").exists()


def test_history_and_state_changes_are_restricted_to_bound_member(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    host = host_json(tmp_path, config)
    source = _definition(tmp_path, owner="other")
    definition = ScheduleDefinition.model_validate_json(source.read_text(encoding="utf-8"))
    path = layout.workspace_root / "schedules.sqlite"
    with SqliteScheduleStore(path, bridge_id="bridge-company") as store:
        store.create(definition, now=datetime.now(UTC))
    for action in ("pause", "resume", "history"):
        assert main(["schedules", "--config", str(host), action, "daily-read"]) == 1
        assert "owner_mismatch" in capsys.readouterr().err
    with SqliteScheduleStore(path, bridge_id="bridge-company") as store:
        assert store.get("daily-read", owner="other").status == "active"


def test_history_shows_durable_outcome_without_dispatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    host = host_json(tmp_path, config)
    source = _definition(tmp_path)
    assert main(["schedules", "--config", str(host), "create", "--definition", str(source)]) == 0
    capsys.readouterr()
    path = layout.workspace_root / "schedules.sqlite"
    with SqliteScheduleStore(path, bridge_id="bridge-company") as store:
        due = store.get("daily-read", owner="engineer").next_due_at
        (claim,) = store.claim_due(now=due, owner="engineer")
        store.record_outcome(
            claim.idempotency_key,
            owner="engineer",
            status="needs_input",
            result_code="schedule_approval_required",
        )
    assert main(["schedules", "--config", str(host), "history", "daily-read"]) == 0
    output = capsys.readouterr().out
    assert "needs_input (schedule_approval_required)" in output
    assert claim.idempotency_key in output


def _due_an_hour_ago(layout_root: Path, schedule_id: str) -> None:
    """Save a read schedule whose occurrence fell due an hour ago."""
    now = datetime.now(UTC)
    at = (now - timedelta(hours=1)).time().replace(second=0, microsecond=0)
    definition = ScheduleDefinition.model_validate(
        {
            "schedule_id": schedule_id,
            "owner": "engineer",
            "target_kind": "workflow",
            "target": {"namespace": "engineering", "name": "read-local-file", "version": "1.0.0"},
            "recurrence": {"kind": "daily", "timezone": "UTC", "at": at.isoformat("minutes")},
            "runtime_inputs": {"args": "notes.txt"},
        }
    )
    with SqliteScheduleStore(
        layout_root / "schedules.sqlite", bridge_id="bridge-company"
    ) as store:
        store.create(definition, now=now - timedelta(hours=2))


def test_tick_runs_only_a_granted_schedule_and_never_twice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    host = host_json(tmp_path, config)

    def command(*args: str) -> int:
        return main(["schedules", "--config", str(host), *args])

    _due_an_hour_ago(layout.workspace_root, "ungranted")
    _due_an_hour_ago(layout.workspace_root, "granted")
    assert command("grant", "granted", "--max-effect", "read", "--days", "30") == 0
    assert "granted: granted up to read by engineer until" in capsys.readouterr().out
    assert command("tick") == 0
    output = capsys.readouterr().out
    assert "granted" in output and "succeeded (workflow_succeeded) [read]" in output
    assert "ungranted" in output and "needs_input (schedule_grant_missing)" in output
    assert command("tick") == 0
    assert capsys.readouterr().out.strip() == "nothing was due"
    assert command("revoke", "granted") == 0
    assert "granted: grant revoked" in capsys.readouterr().out
    assert command("revoke", "granted") == 1
    assert "no_grant" in capsys.readouterr().err


def test_pending_and_resolve_settle_an_uncertain_claim_without_running_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    host = host_json(tmp_path, config)

    def command(*args: str) -> int:
        return main(["schedules", "--config", str(host), *args])

    _due_an_hour_ago(layout.workspace_root, "stuck")
    with SqliteScheduleStore(
        layout.workspace_root / "schedules.sqlite", bridge_id="bridge-company"
    ) as store:
        # A claim whose process died after dispatch: nobody knows what happened.
        (claim,) = store.claim_due(now=datetime.now(UTC), owner="engineer")
    assert command("pending") == 0
    assert f"stuck: blocked by unresolved claim {claim.idempotency_key}" in (
        capsys.readouterr().out
    )
    assert command("tick") == 0
    assert capsys.readouterr().out.strip() == "nothing was due"
    assert command("approve", claim.idempotency_key) == 1
    assert "not_awaiting_approval" in capsys.readouterr().err
    assert (
        command(
            "resolve", claim.idempotency_key, "--outcome", "failed", "--note", "checked log"
        )
        == 0
    )
    assert "failed (operator_resolved_failed)" in capsys.readouterr().out
    assert command("pending") == 0
    assert capsys.readouterr().out == ""
    with SqliteScheduleStore(
        layout.workspace_root / "schedules.sqlite", bridge_id="bridge-company"
    ) as store:
        (decision,) = store.decisions("stuck", owner="engineer")
        assert decision.note == "checked log" and decision.decided_by == "engineer"
