"""Task result summaries (任務結果摘要; owner 2026-10-25).

「每次跑完任務是不是應該要compose，把重要的結果結論記下來」, kept 「存硬碟，保留 30 天」.
After a run (or a model turn that used several tools) the Host composes a
summary from the run's outputs, shows it as a 「結果摘要」 block, lists it in
later turns (after any number of messages and after a restart), keeps it 30
days per actor and saves it as a note only on 「存成筆記」. Over the fake Bot
API and Agent Web's in-process object; no socket, real bot or Outlook.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_session_artifacts import (
    TRACE,
    AttachingGateway,
    _context,
    _run_the_report,
    _snapshot,
    _telegram,
)
from test_telegram_ingress import OWNER, poll, update
from test_telegram_workflow_flow import _tap

from common.execution import CapabilityResult, WorkflowRun
from host_runtime.agent import LocalAgentOutcome
from host_runtime.session_artifacts import SessionArtifacts
from host_runtime.task_summaries import TaskSummaries
from workflow.engine import WorkflowRunSnapshot

START = datetime(2026, 10, 25, 7, 15, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


def test_a_summary_is_composed_from_the_runs_outputs(tmp_path: Path) -> None:
    store = SessionArtifacts(tmp_path / "workspace")
    done = store.finish_run(
        "chat-1", "engineer", _snapshot(tmp_path / "workspace"), {"week": "2026_43W"}
    )
    summary = done.summary
    assert summary is not None and summary.status == "succeeded"
    assert summary.task == "sde-weekly-report（week 2026_43W）"
    assert summary.key_results[0] == "SDE weekly report 2026_43W: 4 items worked on"
    assert "matched 63" in summary.key_results and "counted 4" in summary.key_results
    assert [(a.id, a.kind, a.name) for a in summary.artifacts] == [
        ("f1", "image", "effort-chart.png"),
        ("f2", "mail draft", "[SDE] Weekly report 2026_43W"),
    ]
    assert summary.follow_ups == ("郵件草稿已存在 Outlook，尚未寄出",)
    block = summary.block().splitlines()
    assert block[0] == "結果摘要" and 3 <= len(block) <= 5
    assert str(tmp_path) not in summary.block()
    # Listed for later turns, newest last.
    assert "results: SDE weekly report 2026_43W" in store.guidance(_context("chat-1"))


def test_summaries_are_per_actor(tmp_path: Path) -> None:
    store = SessionArtifacts(tmp_path / "workspace")
    summary = store.finish_run("chat-1", "engineer", _snapshot(tmp_path / "workspace")).summary
    assert summary is not None
    other = store.summaries
    assert other.get("someone-else", summary.summary_id) is None
    assert other.recent("someone-else") == [] and other.for_session("chat-1", "someone-else") == []
    assert "results:" not in store.guidance(_context("chat-1", actor="someone-else"))
    assert not other.delete("someone-else", summary.summary_id)
    assert other.get("engineer", summary.summary_id) is not None


def test_summaries_are_purged_after_the_retention(tmp_path: Path) -> None:
    clock = Clock()
    store = SessionArtifacts(tmp_path / "workspace")
    store.summaries = TaskSummaries(store.root, clock=clock)
    store.finish_run("chat-1", "engineer", _snapshot(tmp_path / "workspace"))
    assert len(store.summaries.recent("engineer")) == 1
    clock.now = START + timedelta(days=29)
    assert store.summaries.purge() == 0 and len(store.summaries.recent("engineer")) == 1
    clock.now = START + timedelta(days=31)
    # Past the retention it is no longer shown, even before the nightly purge.
    assert store.summaries.recent("engineer") == []
    assert store.summaries.purge() == 1
    # A longer retention is kept additively in its own settings file.
    assert store.summaries.save_settings(60).retention_days == 60
    assert store.summaries.settings().retention_days == 60
    with pytest.raises(ValueError):
        store.summaries.save_settings(0)


def test_the_condensing_call_is_bounded_and_skipped_without_a_model(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from host_runtime.host import model_condenser

    workspace = tmp_path / "workspace"
    plain = WorkflowRunSnapshot(
        run=WorkflowRun(
            run_id="run-plain",
            workflow=_snapshot(workspace).run.workflow,
            trace=TRACE,
            status="succeeded",
            completed_steps=1,
        ),
        step_results=(
            CapabilityResult(
                trace=TRACE,
                status="succeeded",
                data={"preview": "Total hours 37.5 over 4 items; longest item 12 h"},
            ),
        ),
    )
    asked: list[str] = []
    store = SessionArtifacts(workspace)
    store.condenser = lambda text: asked.append(text) or ["總工時 37.5 小時", "4 項"]  # type: ignore[func-returns-value]
    summary = store.finish_run("chat-1", "engineer", plain).summary
    assert summary is not None and "總工時 37.5 小時" in summary.key_results
    assert len(asked) == 1 and len(asked[0]) <= 3_000
    # With enough facts from the outputs, no model call.
    store.finish_run("chat-1", "engineer", _snapshot(workspace, "run-2"))
    assert len(asked) == 1
    # No model on the Host: the condenser calls nothing and adds nothing.
    gateway = SimpleNamespace(router=SimpleNamespace(model=None, model_alias="company"))
    assert model_condenser(gateway)("Total hours 37.5") == []


def test_telegram_shows_the_summary_and_saves_a_note_only_on_press(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item, transport, store, model = _telegram(tmp_path, monkeypatch)

    class Notes:
        def __init__(self) -> None:
            self.saved: list[tuple[str, str, str]] = []

        def task_summary_note(self, actor: str, summary_id: str, channel: str) -> dict[str, Any]:
            self.saved.append((actor, summary_id, channel))
            return {"ok": True, "message": "已存成筆記（n-1）。"}

    notes = Notes()
    item.cards = notes
    ran = _run_the_report(item, transport)
    assert "結果摘要\n- 任務：sde-weekly-report" in (ran.reply or "")
    assert "郵件草稿已存在 Outlook，尚未寄出" in (ran.reply or "")
    summary = store.summaries.recent("engineer")[0]
    assert ("存成筆記", f"sumnote:{summary.summary_id}") in [b for row in ran.buttons for b in row]
    assert notes.saved == []  # nothing is saved by itself
    transport.batches.append([_tap(3, OWNER, f"sumnote:{summary.summary_id}", transport)])
    pressed = poll(item).deliveries[0]
    assert pressed.reply == "已存成筆記（n-1）。"
    assert notes.saved == [("engineer", summary.summary_id, "telegram")]
    # A typed 「存成筆記」 saves the session's latest summary.
    transport.batches.append([update(4, OWNER, "存成筆記")])
    poll(item)
    assert notes.saved[-1] == ("engineer", summary.summary_id, "telegram")
    # Fourteen messages later the model still has the summary.
    for number in range(14):
        transport.batches.append([update(10 + number, OWNER, f"閒聊 {number}")])
        poll(item)
    assert "results: SDE weekly report 2026_43W" in model.requests[-1].messages[0].text


def test_agent_web_shows_the_summary_keeps_it_across_a_restart_and_saves_a_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_chat_workflow_forms import _plain
    from test_conversation_turn_groups import _chat_config

    from host_runtime.contracts import WorkflowLaunchRequest
    from host_runtime.conversations import ConversationTurnRequest
    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb

    config, layout = _chat_config(tmp_path)
    manifest = _plain("sde-weekly-report")
    transport = AttachingGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        runtime.agent.gateway.engine.workflows.register(manifest)
        (runtime.layout.workflows / "sde-weekly-report.json").write_text(
            manifest.model_dump_json(), encoding="utf-8"
        )
        web = AgentWeb(runtime)
        workspace = runtime.layout.workspace_root

        async def fake_execute(request: Any) -> LocalAgentOutcome:
            return LocalAgentOutcome(
                trace=TRACE, ingress="local", actor=request.actor, workflow=_snapshot(workspace)
            )

        monkeypatch.setattr(runtime.agent, "execute_workflow", fake_execute)
        session = web.create_conversation()["conversation"]["session_id"]
        launched = web.launch_workflow(
            WorkflowLaunchRequest(
                workflow=manifest.metadata.identity,
                arguments={},
                idempotency_key="sde-1",
                session_id=session,
            )
        )
        message = launched["message"]
        assert "結果摘要\n- 任務：sde-weekly-report" in message["text"]
        summary_id = message["task_summary_id"]
        listed = web.memory_page.get("/api/memory/task-summaries", {})
        assert [item["summary_id"] for item in listed["summaries"]] == [summary_id]
        assert listed["settings"]["retention_days"] == 30
        # No note until the press; the press saves one, a second press does not.
        assert web.personal_memory.listed("notes")["notes"] == []
        saved = web.memory_page.post("/api/memory/task-summaries/note", {"id": summary_id})
        assert saved["ok"] and not saved.get("already")
        notes = web.personal_memory.listed("notes")["notes"]
        assert len(notes) == 1 and "結果摘要" in notes[0]["text"]
        again = web.memory_page.post("/api/memory/task-summaries/note", {"id": summary_id})
        assert again["already"]
        assert web.memory_page.post("/api/memory/task-summaries/settings", {"retention_days": 45})[
            "settings"
        ] == {"retention_days": 45}
    # After a restart the session's summary is still in the model's prompt.
    transport = AttachingGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        web = AgentWeb(runtime)
        web.conversation_turn(ConversationTurnRequest(session_id=session, message="這週算了幾項？"))
        prompts = [call["messages"][0]["content"] for call in transport.calls if call.get("tools")]
        assert any("counted 4" in str(prompt) for prompt in prompts)
        deleted = web.memory_page.post("/api/memory/task-summaries/delete", {"id": summary_id})
        assert deleted["ok"]
        assert web.memory_page.get("/api/memory/task-summaries", {})["summaries"] == []
