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
