"""Local installation is execution availability, never a fabricated review."""

import json
from pathlib import Path

from test_chat_authoring import call, workflow
from test_external_authoring import desk, skill
from test_host_wiring import ready

from host_runtime.external_authoring import guarded
from host_runtime.host import build_runtime


def test_writing_candidate_runs_directly_without_approval_or_data_egress(tmp_path: Path) -> None:
    authoring, recorder = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "fixture")
    result = authoring.run_workflow(str(submitted["candidate_id"]), {"month": "private-fixture"})
    assert result["ran"] and result["ok"]
    assert recorder.calls == ["private-fixture"]
    assert "private-fixture" not in json.dumps(result)
    assert authoring.chat.approvals("owner") == []


def test_local_workflow_installs_without_trial_or_fake_business_review(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "fixture")
    installed = authoring.install_workflow(str(submitted["candidate_id"]))
    assert installed["ok"] and installed["installed_as"]
    assert installed["verified"] is False
    assert "approval_id" not in installed
    files = list((tmp_path / "workflows").glob("*.json"))
    assert len(files) == 1
    metadata = json.loads(files[0].read_text(encoding="utf-8"))["metadata"]
    assert metadata["business_approval"]["status"] == "pending"
    assert metadata["business_approval"]["reviewer"] is None
    assert metadata["lifecycle"] == "draft"
    assert metadata["validation_refs"]  # candidate identity/digest, not a passed test
    assert authoring.chat.approvals("owner") == []
    assert not (tmp_path / "grants.json").exists()


def test_a_reference_string_is_not_evidence_of_an_actual_owner_review(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "fixture")
    item = authoring.chat.candidate(str(submitted["candidate_id"]), "owner")
    authoring.chat.install(item, "owner", "invented-review-reference")
    metadata = json.loads(
        next((tmp_path / "workflows").glob("*.json")).read_text(encoding="utf-8")
    )["metadata"]
    assert metadata["business_approval"]["status"] == "pending"
    assert metadata["business_approval"]["reviewer"] is None


def test_local_skill_install_is_direct_and_not_a_false_review(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    submitted = authoring.submit_skill(skill(), "fixture")
    installed = authoring.install_skill(str(submitted["candidate_id"]))
    assert installed["ok"] and installed["installed_as"]
    assert "approval_id" not in installed
    metadata = json.loads(next((tmp_path / "skills").glob("*.json")).read_text(encoding="utf-8"))[
        "metadata"
    ]
    assert metadata["business_approval"]["status"] == "pending"
    assert metadata["business_approval"]["reviewer"] is None
    assert authoring.chat.approvals("owner") == []


def test_dependency_disappearing_before_install_is_a_technical_failure(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "fixture")
    from common.assets import AssetIdentity

    authoring.chat.installed.unregister(
        AssetIdentity(namespace="lab", name="write-it", version="1.0.0")
    )
    result = guarded(lambda: authoring.install_workflow(str(submitted["candidate_id"])))
    assert result["ok"] is False
    assert not list((tmp_path / "workflows").glob("*.json"))
    assert authoring.chat.approvals("owner") == []


def test_gateway_skill_install_is_available_without_host_restart(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        chat = runtime.chat_authoring
        assert chat is not None
        raw = {
            "name": "fixture-procedure",
            "alias": "fixture_procedure",
            "instructions": "Read the fixture and cite it.",
            "commands": [],
        }
        drafted = call(chat, "authoring__draft_skill", {"title": "fixture", "skill": raw})
        assert drafted.status == "succeeded"
        assert isinstance(drafted.data, dict)
        installed = call(
            chat, "authoring__install_skill", {"candidate_id": drafted.data["candidate_id"]}
        )
        assert installed.status == "succeeded"
        found = runtime.agent.gateway.router.commands.skills.get(
            chat.namespace, "fixture_procedure"
        )
        assert found is not None and found.instructions == raw["instructions"]
        assert found.metadata.business_approval.status == "pending"


def test_authoring_rerun_in_same_turn_replays_success_without_new_trial(tmp_path: Path) -> None:
    from agent.turn_effects import turn_scope

    authoring, recorder = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "fixture")
    item = authoring.chat.candidate(str(submitted["candidate_id"]), "owner")
    with turn_scope() as (effects, _):
        first = authoring.chat.execute("owner", item, {"month": "once"}, "fixture")
        second = authoring.chat.execute("owner", item, {"month": "once"}, "fixture")
        assert first["status"] == "succeeded" and second["replayed"]
        assert recorder.calls == ["once"]
        assert effects.counts() == {"side_effects_recorded": 1, "side_effects_replayed": 1}


def test_generic_capability_then_workflow_does_not_repeat_the_same_write(tmp_path: Path) -> None:
    import asyncio

    from agent.turn_effects import turn_scope
    from host_runtime.tool_access import ToolAccess, tool_context

    authoring, recorder = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "fixture")
    item = authoring.chat.candidate(str(submitted["candidate_id"]), "owner")
    with turn_scope():
        direct = asyncio.run(
            ToolAccess(authoring.chat.bridge).invoke(
                tool_context("owner", "engineering"), "lab/write-it@1.0.0", {"value": "once"}
            )
        )
        assert direct.status == "succeeded"
        result = authoring.chat.execute("owner", item, {"month": "once"}, "fixture")
        assert result["status"] == "succeeded"
        assert recorder.calls == ["once"]


def test_legacy_studio_installs_without_preview_or_forged_business_review(tmp_path: Path) -> None:
    from test_authoring_conversation import Scripted
    from test_authoring_sessions import ACTOR, draft, studio
    from test_workflow_preview import Calls

    from common.assets import WorkflowManifest

    room = studio(
        tmp_path, Scripted({"reply": "draft", "questions": [], "workflow": draft()}), Calls()
    )
    session = room.start(ACTOR, title="fixture", sop_text="fixture SOP")
    installed, path = room.install(session.session_id, ACTOR)
    assert installed.status == "installed"
    manifest = WorkflowManifest.model_validate_json(path.read_text(encoding="utf-8"))
    assert manifest.metadata.lifecycle == "draft"
    assert manifest.metadata.business_approval.status == "pending"
    assert manifest.metadata.business_approval.reviewer is None
    assert not (tmp_path / "grants.json").exists()
