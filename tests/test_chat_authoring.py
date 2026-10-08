"""Conversational authoring G4: draft, preview, run and install from a conversation.

The model never approves: a Workflow whose steps only read runs directly,
anything else becomes an approval request only the owner's decision runs.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.chat_authoring import ChatAuthoring, ChatAuthoringError, digest
from workflow.dispatch import BridgeExecutor


class Echo(Contract):
    value: str = ""


class Out(Contract):
    echoed: str


def spec(name: str, side_effect: str) -> CapabilitySpec:
    policy: dict[str, Any] = {"risk": "low", "required_permissions": [f"lab.{name}"],
                              "policy_refs": ["lab-policy"]}
    if side_effect != "read":
        policy["approval_required"] = True
    return CapabilitySpec.model_validate({
        "identity": {"namespace": "lab", "name": name, "version": "1.0.0"},
        "name": f"lab.{name}", "description": name,
        "input_contract": f"lab.{name}.in.v1", "output_contract": f"lab.{name}.out.v1",
        "side_effect": side_effect, "policy": policy,
    })


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        value = Echo.model_validate(inputs).value
        self.calls.append(value)
        return Out(echoed=value)


def studio(tmp_path: Path) -> tuple[ChatAuthoring, Recorder]:
    recorder = Recorder()
    installed = InstalledCapabilities()
    for name, effect in (("read-it", "read"), ("write-it", "write")):
        installed.register(spec(name, effect), recorder, Echo, Out,
                           ExecutionDependencies(central_required=False))
    bridge = BridgeExecutor(installed, LocalPolicy(()))
    return ChatAuthoring(
        tmp_path / "chat", bridge=lambda: bridge, namespace="engineering",
        workflows_dir=tmp_path / "workflows", grants_file=tmp_path / "grants.json",
    ), recorder


def workflow(capability: str) -> dict[str, Any]:
    return {
        "name": "echo-month", "description": "Echo the month.",
        "parameters": [{"name": "month", "label": "Which month?", "kind": "text",
                        "scope": "runtime", "required": True}],
        "steps": [{"capability": f"lab/{capability}@1.0.0",
                   "inputs": {"value": {"source": "run", "path": ["month"]}}}],
    }


def context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"), actor="owner",
        namespace="engineering", channel="local", session_id="session-1", message="x",
    )


def call(chat: ChatAuthoring, name: str, args: dict[str, Any]) -> Any:
    tool = next(t for t in chat.tools() if t.tool.name == name)
    return asyncio.run(tool.handler(context(), args))


def draft(chat: ChatAuthoring, capability: str) -> Any:
    return call(chat, "authoring__draft_workflow",
                {"title": "Echo", "workflow": workflow(capability)})


def test_an_invalid_draft_returns_problems_and_keeps_nothing(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    outcome = call(chat, "authoring__draft_workflow",
                   {"title": "x", "workflow": workflow("missing-capability")})
    assert outcome.status == "failed" and outcome.failure.code == "workflow_invalid"
    assert chat.candidates("owner") == []


def test_a_read_only_workflow_runs_directly(tmp_path: Path) -> None:
    chat, recorder = studio(tmp_path)
    drafted = draft(chat, "read-it")
    assert drafted.status == "succeeded" and drafted.data["read_only"] is True
    ran = call(chat, "authoring__run_workflow",
               {"candidate_id": drafted.data["candidate_id"], "arguments": {"month": "2026-09"}})
    assert ran.status == "succeeded" and ran.data["status"] == "succeeded"
    assert recorder.calls == ["2026-09"]


def test_a_writing_workflow_waits_for_the_owner_and_runs_once_approved(tmp_path: Path) -> None:
    chat, recorder = studio(tmp_path)
    drafted = draft(chat, "write-it")
    candidate_id = drafted.data["candidate_id"]
    asked = call(chat, "authoring__run_workflow",
                 {"candidate_id": candidate_id, "arguments": {"month": "2026-08"}})
    assert asked.status == "awaiting_approval" and recorder.calls == []
    (pending,) = chat.approvals("owner", session_id="session-1")
    assert pending.approval_id == asked.data["approval_id"]
    decided = chat.decide(pending.approval_id, "owner", approve=True)
    assert decided.status == "approved" and recorder.calls == ["2026-08"]
    assert isinstance(decided.result, dict) and decided.result["status"] == "succeeded"
    with pytest.raises(ChatAuthoringError):
        chat.decide(pending.approval_id, "owner", approve=True)
    assert chat.approvals("owner") == []


def test_a_rejected_or_stale_request_never_runs_and_others_cannot_decide(tmp_path: Path) -> None:
    chat, recorder = studio(tmp_path)
    drafted = draft(chat, "write-it")
    candidate_id = drafted.data["candidate_id"]
    first = call(chat, "authoring__run_workflow", {"candidate_id": candidate_id, "arguments": {}})
    with pytest.raises(ChatAuthoringError):
        chat.decide(first.data["approval_id"], "someone-else", approve=True)
    assert chat.decide(first.data["approval_id"], "owner", approve=False).status == "rejected"
    second = call(chat, "authoring__run_workflow", {"candidate_id": candidate_id, "arguments": {}})
    changed = workflow("write-it") | {"description": "Changed after the request."}
    call(chat, "authoring__draft_workflow",
         {"title": "W", "workflow": changed, "candidate_id": candidate_id})
    stale = chat.decide(second.data["approval_id"], "owner", approve=True)
    assert stale.status == "failed" and recorder.calls == []


def test_install_needs_approval_and_a_rerun_keeps_the_same_digest(tmp_path: Path) -> None:
    chat, recorder = studio(tmp_path)
    drafted = draft(chat, "write-it")
    candidate_id = drafted.data["candidate_id"]
    asked = call(chat, "authoring__install_workflow", {"candidate_id": candidate_id})
    assert asked.status == "awaiting_approval"
    assert not (tmp_path / "workflows").exists()
    installed = chat.decide(asked.data["approval_id"], "owner", approve=True)
    assert installed.status == "approved"
    files = list((tmp_path / "workflows").glob("*.json"))
    assert len(files) == 1
    published = json.loads(files[0].read_text(encoding="utf-8"))
    assert published["metadata"]["lifecycle"] == "published"
    assert published["metadata"]["business_approval"]["reviewer"] == "owner"
    grants = json.loads((tmp_path / "grants.json").read_text(encoding="utf-8"))
    assert [g["asset"]["name"] for g in grants] == ["write-it"]
    listed = call(chat, "authoring__list_workflows", {})
    assert listed.data[0]["status"] == "installed"
    item = chat.candidate(candidate_id, "owner")
    assert listed.data[0]["digest"] == digest(item.draft) == installed.result["digest"]
    again = call(chat, "authoring__install_workflow", {"candidate_id": candidate_id})
    assert again.status == "failed" and again.failure.code == "candidate_already_installed"
    # Installing was the approval (owner 2026-10-08): reruns of the installed
    # version run at once.
    for month in ("2026-09", "2026-10"):
        run = call(chat, "authoring__run_workflow",
                   {"candidate_id": candidate_id, "arguments": {"month": month}})
        assert run.status == "succeeded"
    assert recorder.calls == ["2026-09", "2026-10"]


def test_the_agent_can_read_back_its_own_draft(tmp_path: Path) -> None:
    """Lab fix-007 W01: the Agent could not see the steps of the draft it had to fix."""
    chat, _ = studio(tmp_path)
    drafted = draft(chat, "write-it")
    shown = call(chat, "authoring__get_workflow", {"candidate_id": drafted.data["candidate_id"]})
    assert shown.status == "succeeded"
    assert shown.data["steps"][0]["capability"]["name"] == "write-it"
    assert [p["name"] for p in shown.data["parameters"]] == ["month"]
    missing = call(chat, "authoring__get_workflow", {"candidate_id": "wf-nope"})
    assert missing.status == "failed" and missing.failure.code == "candidate_unknown"


def install(chat: ChatAuthoring, candidate_id: str) -> Any:
    asked = call(chat, "authoring__install_workflow", {"candidate_id": candidate_id})
    return chat.decide(asked.data["approval_id"], "owner", approve=True)


def test_a_new_draft_of_an_installed_name_continues_its_versions(tmp_path: Path) -> None:
    """Lab fix-008 W01: a new candidate restarted at 1.0.0 and collided on install."""
    chat, _ = studio(tmp_path)
    first = draft(chat, "write-it")
    assert first.data["workflow"] == "engineering/echo-month@1.0.0"
    assert install(chat, first.data["candidate_id"]).status == "approved"
    revised = call(chat, "authoring__draft_workflow",
                   {"title": "Echo", "workflow": workflow("write-it"),
                    "candidate_id": first.data["candidate_id"]})
    assert revised.data["workflow"] == "engineering/echo-month@1.0.1"
    later = draft(chat, "write-it")  # another conversation, same name
    assert later.data["workflow"] == "engineering/echo-month@1.0.1"
    assert install(chat, later.data["candidate_id"]).status == "approved"
    again = draft(chat, "write-it")
    assert again.data["workflow"] == "engineering/echo-month@1.0.2"


def test_a_name_someone_else_installed_is_refused_with_its_owner(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    first = draft(chat, "write-it")
    install(chat, first.data["candidate_id"])
    (path,) = (tmp_path / "workflows").glob("*.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["metadata"]["owner"] = {"type": "user", "id": "colleague"}
    path.write_text(json.dumps(manifest), encoding="utf-8")
    refused = draft(chat, "write-it")
    assert refused.status == "failed"
    assert "colleague" in json.dumps(refused.model_dump(mode="json"), ensure_ascii=False)


def test_an_installed_workflow_runs_without_asking_again_and_is_usable_at_once(
    tmp_path: Path,
) -> None:
    """Owner 2026-10-08: after Install, a run asked for approval again, and the
    Capabilities page said workflow_not_installed until a restart."""
    chat, recorder = studio(tmp_path)
    used: list[tuple[str, int]] = []
    chat.on_installed = lambda manifest, grants: used.append(
        (manifest.metadata.identity.name, len(grants)))
    candidate_id = draft(chat, "write-it").data["candidate_id"]
    decided = chat.install_now("owner", candidate_id)
    assert decided.status == "approved" and used == [("echo-month", 1)]
    assert "runs now" in decided.result["note"]  # type: ignore[index]
    ran = call(chat, "authoring__run_workflow",
               {"candidate_id": candidate_id, "arguments": {"month": "2026-10"}})
    assert ran.status == "succeeded" and recorder.calls == ["2026-10"]
    # A changed draft is no longer the installed version: it asks again.
    revised = workflow("write-it")
    revised["description"] = "Echo the month, revised."
    call(chat, "authoring__draft_workflow",
         {"title": "Echo", "workflow": revised, "candidate_id": candidate_id})
    again = call(chat, "authoring__run_workflow",
                 {"candidate_id": candidate_id, "arguments": {"month": "2026-11"}})
    assert again.status == "awaiting_approval" and recorder.calls == ["2026-10"]


def test_the_host_registers_an_install_and_its_grants_while_running() -> None:
    from capabilities.runtime import CapabilityGrant, LocalPolicy
    from common.assets import AssetIdentity

    policy = LocalPolicy(())
    grant = CapabilityGrant(actor="owner", asset=AssetIdentity(
        namespace="lab", name="write-it", version="1.0.0"),
        permissions=("lab.write-it",), policy_refs=("lab-policy",), approval_ref="x")
    policy.add(grant)
    policy.add(grant.model_copy(update={"approval_ref": "y"}))  # the first one stays
    assert policy._grants[("owner", grant.asset.key)].approval_ref == "x"
