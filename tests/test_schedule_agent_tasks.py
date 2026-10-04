"""Scheduled Agent Tasks: exact installed templates through run_task's path."""

import asyncio
import json
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_gateway_task_execution import AnswerModel, approved, executor
from test_host_wiring import host_json, ready
from test_local_agent import company

from common.assets import AssetIdentity
from common.execution import TraceIdentifiers
from common.scheduling import Recurrence, ScheduleDefinition, ScheduleExecutionGrant
from host_runtime.agent import LocalAgent
from host_runtime.agent_tasks import AGENT_TASK_DIRECTORY, AgentTaskTemplate, installed_agent_tasks
from host_runtime.cli import main
from host_runtime.schedule_policy import ScheduleGrantAuthorizer
from host_runtime.schedule_worker import ScheduleWorker
from host_runtime.schedules import SqliteScheduleStore

DUE = datetime(2026, 10, 5, 1, tzinfo=UTC)
IDENTITY = AssetIdentity(namespace="engineering", name="answer-task", version="1.0.0")
TRACE = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")


def template_payload(**changes: Any) -> dict[str, Any]:
    return {
        "kind": "agent_task",
        "identity": IDENTITY.model_dump(),
        "description": "Summarize the week's open questions",
        "objective": "Answer the question",
        "expected_outputs": [{"output_id": "answer", "artifact_ref": "answer"}],
        "checks": [{"check_id": "answer-present", "output_id": "answer", "kind": "nonempty"}],
        **changes,
    }


def definition(**changes: Any) -> ScheduleDefinition:
    return ScheduleDefinition.model_validate(
        {
            "schedule_id": "weekly-answer",
            "owner": "engineer",
            "target_kind": "agent_task",
            "target": IDENTITY,
            "recurrence": Recurrence(
                kind="weekly", timezone="Asia/Taipei", at=time(9), weekdays=(1,)
            ),
            **changes,
        }
    )


def test_template_is_an_exact_authority_free_task() -> None:
    template = AgentTaskTemplate.model_validate(template_payload())
    task = template.to_task(actor="engineer", task_id="x", trace=TRACE)
    assert task.namespace == "engineering" and task.actor == "engineer"
    assert task.objective == "Answer the question"
    for change in (
        {"objective": "use password=hunter22"},
        {"actor": "engineer"},
        {"resource_refs": ["ref"]},
        {"checks": [{"check_id": "c", "output_id": "missing", "kind": "nonempty"}]},
        {"kind": "workflow"},
    ):
        with pytest.raises(ValidationError):
            AgentTaskTemplate.model_validate(template_payload(**change))


def test_only_cleanly_read_unique_templates_are_installed(tmp_path: Path) -> None:
    directory = tmp_path / AGENT_TASK_DIRECTORY
    directory.mkdir(parents=True)
    (directory / "a.json").write_text(json.dumps(template_payload()), encoding="utf-8")
    other = template_payload(identity={**IDENTITY.model_dump(), "name": "other-task"})
    (directory / "b.json").write_text(json.dumps([other]), encoding="utf-8")
    (directory / "c.json").write_text("{not json", encoding="utf-8")
    assert set(installed_agent_tasks(tmp_path)) == {
        IDENTITY.key,
        ("engineering", "other-task", "1.0.0"),
    }
    (directory / "d.json").write_text(json.dumps(other), encoding="utf-8")
    assert set(installed_agent_tasks(tmp_path)) == {IDENTITY.key}
    assert installed_agent_tasks(tmp_path / "missing") == {}


def test_cli_schedules_an_installed_agent_task_without_runtime_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    host = host_json(tmp_path, config)
    directory = layout.workspace_root / AGENT_TASK_DIRECTORY
    directory.mkdir(parents=True)
    (directory / "answer.json").write_text(json.dumps(template_payload()), encoding="utf-8")
    with_inputs = tmp_path / "inputs.json"
    with_inputs.write_text(
        definition(runtime_inputs={"topic": "x"}).model_dump_json(), encoding="utf-8"
    )
    assert (
        main(["schedules", "--config", str(host), "create", "--definition", str(with_inputs)]) == 1
    )
    assert "declares no runtime inputs" in capsys.readouterr().err
    source = tmp_path / "task.json"
    source.write_text(definition().model_dump_json(), encoding="utf-8")
    assert main(["schedules", "--config", str(host), "create", "--definition", str(source)]) == 0
    assert "weekly-answer: active; agent_task engineering/answer-task@1.0.0" in (
        capsys.readouterr().out
    )
    assert (
        main(["schedules", "--config", str(host), "grant", "weekly-answer", "--max-effect", "read"])
        == 0
    )


def _worker(store: SqliteScheduleStore, resident: LocalAgent) -> ScheduleWorker:
    template = AgentTaskTemplate.model_validate(template_payload())
    templates = {IDENTITY.key: template.to_task(actor="engineer", task_id="t", trace=TRACE)}
    return ScheduleWorker(
        store,
        resident,
        authorizer=ScheduleGrantAuthorizer(store, resident, task_templates=templates),
        task_templates=templates,
    )


def test_scheduled_agent_task_needs_a_grant_then_runs_through_run_task(tmp_path: Path) -> None:
    model = AnswerModel()
    service, state = executor(tmp_path, model, approved())
    resident = LocalAgent(company(), service.backend.gateway, state, task_executor=service)
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        (refused,) = asyncio.run(_worker(store, resident).poll_once(now=DUE))
        assert (refused.status, refused.result_code) == ("needs_input", "schedule_grant_missing")
        assert model.calls == [] and state.task_runs("engineer") == ()
        store.grant(
            ScheduleExecutionGrant(
                schedule_id="weekly-answer",
                owner="engineer",
                target_kind="agent_task",
                target=IDENTITY,
                max_side_effect="read",
                policy_ref="owner-schedule-grant",
                approved_by="engineer",
                approved_at=DUE,
            )
        )
        week = DUE + timedelta(days=7)
        (done,) = asyncio.run(_worker(store, resident).poll_once(now=week))
        assert (done.status, done.result_code, done.side_effect) == (
            "succeeded",
            "task_validated",
            "read",
        )
        assert len(model.calls) == 1
        (run,) = state.task_runs("engineer")
        assert run.task_id.startswith("scheduled-")
    state.close()
