"""Trial proof belongs to the executed revision and the requesting session."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from test_chat_authoring import context, studio, workflow

from agent.gateway import HostToolOutcome
from common.execution import Failure, RequestContext, WorkflowRun
from host_runtime.authoring_task import Requirement
from host_runtime.chat_authoring import ChatAuthoring, ChatCandidate, digest
from workflow.engine import WorkflowRunSnapshot


def _requirement(ident: str = "echo") -> Requirement:
    return Requirement.model_validate(
        {
            "requirement_id": ident,
            "description": "Echo the supplied month",
            "check_ids": ["echoed"],
            "assertions": [
                {
                    "path": ["steps", 0, "capability", "name"],
                    "operator": "equals",
                    "expected": "read-it",
                }
            ],
        }
    )


def _planned(chat: ChatAuthoring, session: str = "session-1") -> ChatCandidate:
    chat.tasks.plan("owner", session, "Echo the month", [_requirement()])
    raw = workflow("read-it")
    raw["checks"] = [{"check_id": "echoed", "step_index": 0, "kind": "data_nonempty"}]
    item, problems = chat.draft("owner", session, "Echo", raw)
    assert item is not None and not problems
    return item


def _snapshot(candidate: ChatCandidate, *, failed: bool = False) -> WorkflowRunSnapshot:
    return WorkflowRunSnapshot(
        run=WorkflowRun(
            run_id="trial-old-revision",
            workflow=candidate.draft.metadata.identity,
            trace=context().trace,
            status="failed" if failed else "succeeded",
            failure=Failure(code="fixture_failed", message="Fixture failed") if failed else None,
        )
    )


def _call(
    chat: ChatAuthoring, name: str, args: dict[str, Any], ctx: RequestContext
) -> HostToolOutcome:
    tool = next(t for t in chat.tools() if t.tool.name == name)

    async def invoke() -> HostToolOutcome:
        return await tool.handler(ctx, args)

    return asyncio.run(invoke())


def test_finishing_old_trial_preserves_new_draft_and_cannot_verify_it(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    original = _planned(chat)
    running = chat.begin_trial("owner", original, {"month": "2026-11"})
    raw = running.draft.model_dump(mode="json")
    raw["description"] = "Revised while the old trial was running"
    revised, problems = chat.draft("owner", "session-1", "Revised", raw, original.candidate_id)
    assert revised is not None and not problems
    assert digest(revised.draft) != digest(running.draft)

    chat.record_trial("owner", running, _snapshot(running))

    current = chat.candidate(original.candidate_id, "owner")
    assert current.revision == revised.revision
    assert current.draft == revised.draft
    assert current.authoring_task is not None
    assert current.authoring_task.verified_digest != digest(revised.draft)
    active = chat.tasks.load("owner", "session-1")
    assert active is not None and active.verified_digest != digest(revised.draft)


def test_proof_of_another_executed_body_cannot_verify_current_candidate(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    original = _planned(chat)
    raw = original.draft.model_dump(mode="json")
    raw["description"] = "Different procedure version"
    revised, problems = chat.draft("owner", "session-1", "Revised", raw, original.candidate_id)
    assert revised is not None and not problems
    running = chat.begin_trial("owner", revised, {"month": "2026-11"})

    chat.record_trial("owner", running, _snapshot(original), executed_manifest=original.draft)

    active = chat.tasks.load("owner", "session-1")
    assert active is not None and active.verified_digest is None
    assert active.last_run_id is None


def test_changed_plan_invalidates_inflight_trial_without_overwriting_progress(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    running = chat.begin_trial("owner", _planned(chat), {"month": "2026-11"})
    active = chat.tasks.plan(
        "owner", "session-1", "Echo the month", [_requirement(), _requirement("additional")]
    )
    active = active.model_copy(
        update={"repair_attempts": 2, "last_repaired_run_id": "another-repair"}
    )
    chat.tasks.save("owner", "session-1", active)

    chat.record_trial("owner", running, _snapshot(running, failed=True))

    saved = chat.tasks.load("owner", "session-1")
    assert saved is not None
    assert saved.requirements == active.requirements
    assert saved == active
    assert saved.active_trial_token is None
    assert saved.last_run_id is None
    assert saved.repair_attempts == 2
    assert saved.last_repaired_run_id == "another-repair"
    current = chat.candidate(running.candidate_id, "owner")
    assert current == running


def test_begin_trial_returns_the_exact_persisted_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat, _ = studio(tmp_path)
    original = _planned(chat)
    monkeypatch.setattr("host_runtime.chat_authoring._now", lambda: "2030-01-01T00:00:00Z")
    running = chat.begin_trial("owner", original, {"month": "2026-11"})
    assert running.updated_at != original.updated_at
    assert chat.candidate(running.candidate_id, "owner") == running


def test_trial_completion_preserves_same_plan_concurrent_repair_progress(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    running = chat.begin_trial("owner", _planned(chat), {"month": "2026-11"})
    active = chat.tasks.load("owner", "session-1")
    assert active is not None
    active = active.model_copy(
        update={"repair_attempts": 2, "last_repaired_run_id": "another-repair"}
    )
    chat.tasks.save("owner", "session-1", active)

    chat.record_trial("owner", running, _snapshot(running, failed=True))

    saved = chat.tasks.load("owner", "session-1")
    assert saved is not None
    assert saved.requirements == active.requirements
    assert saved.repair_attempts == 3
    assert saved.last_repaired_run_id == "another-repair"
    assert chat.candidate(running.candidate_id, "owner").authoring_task == saved


def test_unfinished_continuation_does_not_repeat_a_successful_partial_trial(tmp_path: Path) -> None:
    chat, recorder = studio(tmp_path)
    chat.tasks.plan(
        "owner", "session-1", "Two requirements", [_requirement(), _requirement("more")]
    )
    item, problems = chat.draft("owner", "session-1", "Prototype", workflow("read-it"))
    assert item is not None and not problems
    result = chat.execute("owner", item, {"month": "2026-11"}, "approved-partial")
    assert result["status"] == "succeeded" and result["verified"] is False
    ctx = context().model_copy(
        update={
            "message": (
                "[Host authoring continuation: incomplete trial] "
                f"Candidate {item.candidate_id}; preserve successful results"
            )
        }
    )
    outcome = _call(
        chat,
        "authoring__run_workflow",
        {"candidate_id": item.candidate_id, "arguments": {"month": "2026-11"}},
        ctx,
    )
    assert outcome.status == "failed"
    assert outcome.failure is not None
    assert outcome.failure.code == "authoring_revision_required"
    assert recorder.calls == ["2026-11"]


@pytest.mark.parametrize("operation", ["run_workflow", "draft_workflow", "get_workflow"])
def test_repair_tools_refuse_another_session_candidate(tmp_path: Path, operation: str) -> None:
    chat, recorder = studio(tmp_path)
    own = _planned(chat)
    foreign = _planned(chat, "session-2")
    before = chat.candidate(foreign.candidate_id, "owner")
    ctx = context().model_copy(
        update={
            "message": (
                "[Host authoring continuation: repair the failed trial] "
                f"Candidate {own.candidate_id}; failure fixture_failed"
            )
        }
    )
    args: dict[str, Any] = {"candidate_id": foreign.candidate_id}
    if operation == "run_workflow":
        args["arguments"] = {"month": "2026-11"}
    elif operation == "draft_workflow":
        args.update(
            title="Overwrite another session", workflow=foreign.draft.model_dump(mode="json")
        )

    outcome = _call(chat, f"authoring__{operation}", args, ctx)

    assert outcome.status == "failed"
    assert outcome.failure is not None
    assert recorder.calls == []
    assert chat.candidate(foreign.candidate_id, "owner") == before


def test_sop_revision_requires_plan_before_creating_revision(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    original, problems = chat.draft("owner", "source-session", "Echo", workflow("read-it"))
    assert original is not None and not problems
    installed = chat.install(original, "owner", "owner-approved")
    chat.tasks.observe("owner", "session-1", "Please revise this workflow using the SOP")
    before = chat.candidates("owner")

    outcome = _call(
        chat,
        "authoring__revise_workflow",
        {"workflow": installed["installed_as"]},
        context(),
    )

    assert outcome.status == "failed"
    assert outcome.failure is not None and outcome.failure.code == "authoring_plan_required"
    assert chat.candidates("owner") == before


def test_failed_output_check_is_a_failed_host_tool_outcome(tmp_path: Path) -> None:
    chat, recorder = studio(tmp_path)
    raw = workflow("read-it")
    raw["checks"] = [{"check_id": "report", "step_index": 0, "kind": "files_nonempty"}]
    item, problems = chat.draft("owner", "session-1", "Must produce a file", raw)
    assert item is not None and not problems

    outcome = _call(
        chat,
        "authoring__run_workflow",
        {"candidate_id": item.candidate_id, "arguments": {"month": "2026-11"}},
        context(),
    )

    assert recorder.calls == ["2026-11"]
    assert outcome.status == "failed"
    assert outcome.failure is not None
    assert isinstance(outcome.data, dict)
    assert outcome.data["status"] == "failed"
