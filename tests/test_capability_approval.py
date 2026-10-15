"""A side effect the model chose itself waits for the person's button (owner mode step 2).

Owner 2026-10-11: in owner mode a model-chosen write returns
`approval_required`; the Gateway turns that into an approval request, and the
person's Approve runs the exact call as the person.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from test_chat_authoring import Echo, Out, Recorder, context, spec
from test_gateway import FakeModel, Handler, Probe, Report, capability_spec, gateway, request

from agent.gateway import HostToolOutcome
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import AssetIdentity, ExecutionDependencies
from host_runtime.chat_authoring import ChatAuthoring, approval_text
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelToolCall
from workflow.dispatch import BridgeExecutor

WRITE = AssetIdentity(namespace="lab", name="write-it", version="1.0.0")


def owner_studio(tmp_path: Path) -> tuple[ChatAuthoring, Recorder]:
    recorder = Recorder()
    installed = InstalledCapabilities()
    installed.register(
        spec("write-it", "write"),
        recorder,
        Echo,
        Out,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="owner",
        asset=WRITE,
        permissions=("lab.write-it",),
        policy_refs=("lab-policy",),
        approval_ref="device-owner",
    )
    bridge = BridgeExecutor(installed, LocalPolicy((grant,), owner_mode=True))
    return ChatAuthoring(
        tmp_path / "chat",
        bridge=lambda: bridge,
        namespace="engineering",
        workflows_dir=tmp_path / "workflows",
        grants_file=tmp_path / "grants.json",
    ), recorder


def test_approving_runs_the_exact_call_as_the_person(tmp_path: Path) -> None:
    chat, recorder = owner_studio(tmp_path)
    pending = chat.capability_approval_tool_data(context(), WRITE, {"value": "x"})
    assert recorder.calls == []  # nothing ran on the request
    listed = chat.approvals("owner")
    assert [a.kind for a in listed] == ["capability"] and "lab/write-it@1.0.0" in listed[0].summary
    decided = chat.decide(str(pending["approval_id"]), "owner", True)
    assert decided.status == "approved" and recorder.calls == ["x"]
    assert approval_text(decided).startswith("【已核准並執行】lab/write-it@1.0.0")


def test_rejecting_runs_nothing(tmp_path: Path) -> None:
    chat, recorder = owner_studio(tmp_path)
    pending = chat.capability_approval_tool_data(context(), WRITE, {"value": "x"})
    assert chat.decide(str(pending["approval_id"]), "owner", False).status == "rejected"
    assert recorder.calls == []


def test_a_changed_request_is_not_run(tmp_path: Path) -> None:
    chat, recorder = owner_studio(tmp_path)
    pending = chat.capability_approval_tool_data(context(), WRITE, {"value": "x"})
    stored = next((tmp_path / "chat" / "approvals").glob("*.json"))
    record = json.loads(stored.read_text(encoding="utf-8"))
    record["arguments"] = {"value": "something else"}
    stored.write_text(json.dumps(record), encoding="utf-8")
    decided = chat.decide(str(pending["approval_id"]), "owner", True)
    assert decided.status == "failed" and recorder.calls == []


def write_spec() -> CapabilitySpec:
    payload = capability_spec().model_dump(mode="json")
    payload["side_effect"] = "write"
    payload["policy"]["approval_required"] = True
    return CapabilitySpec.model_validate(payload)


def test_the_gateway_turns_a_model_chosen_write_into_an_approval_request() -> None:
    class WriteModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            if len(self.calls) == 1:
                return ModelResponse(
                    trace=item.trace,
                    model_alias=item.model_alias,
                    tool_calls=(
                        ModelToolCall(call_id="call-w", name="release__check", arguments={}),
                    ),
                )
            assert "awaiting_approval" in item.messages[-1].text
            return ModelResponse(
                trace=item.trace, model_alias=item.model_alias, text="It waits for your approval."
            )

    handler = Handler()
    built = gateway(handler, WriteModel())
    installed = InstalledCapabilities()
    installed.register(
        write_spec(), handler, Probe, Report, ExecutionDependencies(central_required=False)
    )
    grant = CapabilityGrant(
        actor="engineer",
        asset=write_spec().identity,
        permissions=("engineering.validate",),
        policy_refs=("release-policy",),
        approval_ref="device-owner",
    )
    built.bridge = BridgeExecutor(installed, LocalPolicy((grant,), owner_mode=True))
    requested: list[Any] = []

    def approval(context: Any, target: AssetIdentity, arguments: Any) -> dict[str, Any]:
        requested.append((context.actor, target, arguments))
        return {"approval_id": "ap-1", "summary": "Run it", "next": "wait"}

    built.capability_approval = approval
    result = asyncio.run(
        built.converse(
            request("check the release"), (ModelMessage(role="user", text="check the release"),)
        )
    )
    assert handler.calls == 0
    assert result.tools[0].host == HostToolOutcome(
        status="awaiting_approval",
        data={"approval_id": "ap-1", "summary": "Run it", "next": "wait"},
    )
    assert requested == [("engineer", write_spec().identity, {})]
