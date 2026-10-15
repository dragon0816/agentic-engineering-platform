"""Workflow authoring sessions (owner design B; SOP_TO_WORKFLOW W5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_authoring_conversation import Scripted
from test_workflow_preview import LOCAL, Calls, Plans, Value, spec

from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import WorkflowManifest
from host_runtime.authoring import AuthoringError, AuthoringStudio
from host_runtime.workflow_settings import WorkflowSettingsStore
from workflow.dispatch import BridgeExecutor

ACTOR = "engineer"


def blocks(calls: Calls) -> InstalledCapabilities:
    installed = InstalledCapabilities()
    for name, effect in (("read", "read"), ("write", "write")):
        installed.register(spec(name, effect), Plans(name, calls), Value, Value, LOCAL)
    return installed


def draft(version: str = "1.0.0") -> dict[str, Any]:
    return {
        "metadata": {
            "identity": {"namespace": "engineering", "name": "daily-sop", "version": version},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "private",
        },
        "kind": "workflow",
        "description": "daily SOP",
        "execution": {"mode": "local"},
        "dependencies": {"central_required": False, "local_capabilities": ["t.read", "t.write"]},
        "input_contract": "t.in",
        "output_contract": "t.out",
        "parameters": [
            {
                "name": "folder",
                "label": "Output folder",
                "kind": "text",
                "scope": "static",
                "required": True,
            }
        ],
        "steps": [
            {
                "capability": {"namespace": "t", "name": "read", "version": "1.0.0"},
                "inputs": {"value": {"source": "run", "path": ["customer"]}},
            },
            {
                "capability": {"namespace": "t", "name": "write", "version": "1.0.0"},
                "inputs": {"value": {"source": "step", "step_index": 0, "path": ["value"]}},
            },
        ],
    }


def studio(tmp_path: Path, model: Scripted, calls: Calls) -> AuthoringStudio:
    return AuthoringStudio(
        tmp_path / "authoring",
        installed=blocks(calls),
        model=lambda: model,
        model_alias="gateway",
        local_only=False,
        namespace="engineering",
        workflows_dir=tmp_path / "assets" / "workflows",
        grants_file=tmp_path / "grants.json",
        settings_store=WorkflowSettingsStore(tmp_path / "workflow-settings.json"),
    )


def bridge(installed: InstalledCapabilities) -> BridgeExecutor:
    return BridgeExecutor(installed, LocalPolicy(()))


def test_discussion_preview_and_install_end_to_end(tmp_path: Path) -> None:
    calls = Calls()
    model = Scripted(
        {"reply": "請問客戶代碼？", "questions": ["要查哪個客戶？"], "workflow": None},
        {"reply": "草稿好了", "questions": [], "workflow": draft()},
    )
    room = studio(tmp_path, model, calls)
    session = room.start(ACTOR, title="出貨追蹤", sop_text="每天查一個客戶的出貨並記錄。")
    assert session.status == "needs_input" and session.draft is None
    assert session.turns[-1].role == "agent" and "要查哪個客戶" in session.turns[-1].text

    session = room.discuss(session.session_id, ACTOR, "客戶代碼每次執行時輸入")
    assert session.status == "ready" and session.draft is not None
    with pytest.raises(AuthoringError) as early:
        room.install(session.session_id, ACTOR)
    assert early.value.code == "authoring_preview_required"

    shown = room.preview(
        session.session_id,
        ACTOR,
        {"customer": "C001"},
        {"folder": "C:/out"},
        bridge(room.installed),
    )
    assert shown.status == "previewed" and calls.ran == ["read"]
    assert [step.state for step in shown.preview.steps] == ["ran", "planned"]  # type: ignore[union-attr]

    done, path = room.install(session.session_id, ACTOR)
    assert done.status == "installed" and done.installed_as == "engineering/daily-sop@1.0.0"
    published = WorkflowManifest.model_validate_json(path.read_text(encoding="utf-8"))
    assert published.metadata.lifecycle == "published"
    assert published.metadata.business_approval.reviewer == ACTOR
    grants = json.loads((tmp_path / "grants.json").read_text(encoding="utf-8"))
    assert {grant["asset"]["name"] for grant in grants} == {"read", "write"}
    assert all(grant["approval_ref"].startswith("authoring-session:") for grant in grants)
    settings = json.loads((tmp_path / "workflow-settings.json").read_text(encoding="utf-8"))
    assert settings["workflows"]["engineering/daily-sop"] == {"folder": "C:/out"}
    with pytest.raises(AuthoringError) as twice:
        room.discuss(session.session_id, ACTOR, "again")
    assert twice.value.code == "authoring_session_installed"


def test_a_draft_changed_after_its_preview_needs_a_new_preview(tmp_path: Path) -> None:
    calls = Calls()
    model = Scripted(
        {"reply": "草稿", "questions": [], "workflow": draft()},
        {"reply": "改了版本", "questions": [], "workflow": draft("1.0.1")},
    )
    room = studio(tmp_path, model, calls)
    session = room.start(ACTOR, title="t", sop_text="sop")
    room.preview(
        session.session_id, ACTOR, {"customer": "C1"}, {"folder": "x"}, bridge(room.installed)
    )
    changed = room.discuss(session.session_id, ACTOR, "版本改成 1.0.1")
    assert changed.preview is None and changed.status == "ready"
    with pytest.raises(AuthoringError) as refused:
        room.install(session.session_id, ACTOR)
    assert refused.value.code == "authoring_preview_required"


def test_sessions_belong_to_their_actor_and_a_pdf_must_be_a_pdf(tmp_path: Path) -> None:
    room = studio(
        tmp_path, Scripted({"reply": "ok", "questions": ["?"], "workflow": None}), Calls()
    )
    session = room.start(ACTOR, title="t", sop_text="sop")
    with pytest.raises(AuthoringError) as other:
        room.load(session.session_id, "someone-else")
    assert other.value.code == "authoring_session_unknown"
    assert [item.session_id for item in room.sessions(ACTOR)] == [session.session_id]
    with pytest.raises(AuthoringError) as not_pdf:
        room.start(ACTOR, title="t", pdf=b"hello")
    assert not_pdf.value.code == "authoring_sop_not_a_pdf"
