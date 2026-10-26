"""P0-2 (multi-agent Phase 0.5): a side effect happens at most once per turn,
including the Host check's retry pass and runs nested under the turn. Fakes only."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from test_gateway import Handler, gateway, request
from test_routing import FakeModel

import telemetry.recorder as telemetry_recorder
from agent.gateway import Gateway, HostTool, HostToolOutcome
from agent.skills import SkillManifest
from agent.turn_effects import REPLAY_NOTE, current, turn_scope
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant, LocalPolicy
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import Failure, RequestContext, TraceIdentifiers
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelTool, ModelToolCall

WRITE = {"namespace": "engineering", "name": "publish-note", "version": "1.0.0"}


class NoteInput(Contract):
    note: str = ""


class NoteOutput(Contract):
    saved: bool = True


class WriteHandler(Handler):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.calls += 1
        return NoteOutput()


def write_spec() -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": WRITE,
            "name": "engineering.publish_note",
            "description": "Inert write fixture",
            "input_contract": "engineering.publish-note.input.v1",
            "output_contract": "engineering.publish-note.output.v1",
            "side_effect": "write",
            "policy": {
                "required_permissions": ["engineering.publish"],
                "policy_refs": ["notes-policy"],
            },
        }
    )


def _reply(*calls: tuple[str, dict[str, Any]], text: str = "") -> ModelResponse:
    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"),
        model_alias="routing",
        text=text,
        tool_calls=tuple(
            ModelToolCall(call_id=f"c{index}", name=name, arguments=arguments)
            for index, (name, arguments) in enumerate(calls)
        ),
    )


class Scripted(FakeModel):
    def __init__(self, replies: list[ModelResponse]) -> None:
        super().__init__()
        self.replies = replies

    def generate(self, item: ModelRequest) -> ModelResponse:
        self.calls.append(item)
        reply = self.replies[len(self.calls) - 1]
        return reply.model_copy(update={"trace": item.trace, "model_alias": item.model_alias})


def _built(
    replies: list[ModelResponse],
    *,
    owner_mode: bool = False,
    host_tools: tuple[HostTool, ...] = (),
) -> tuple[Gateway, Scripted, Handler, Handler]:
    """The release fixture (a read capability and a Workflow) plus a write
    capability `notes__publish`. Returns the gateway, the model, the write's
    handler and the read's handler."""
    model = Scripted(replies)
    read = Handler()
    built = gateway(read, model)
    write = WriteHandler()
    built.bridge.installed.register(
        write_spec(), write, NoteInput, NoteOutput, ExecutionDependencies(central_required=False)
    )
    grant = CapabilityGrant.model_validate(
        {
            "actor": "engineer",
            "asset": WRITE,
            "permissions": ["engineering.publish"],
            "policy_refs": ["notes-policy"],
            "approval_ref": "notes-approval",
        }
    )
    policy = built.bridge.policy
    assert isinstance(policy, LocalPolicy)
    policy.add(grant)
    policy.owner_mode = owner_mode
    built.router.commands.skills.register(
        SkillManifest.model_validate(
            {
                "metadata": {
                    "identity": {
                        "namespace": "engineering",
                        "name": "notes-skill",
                        "version": "1.0.0",
                    },
                    "owner": {"type": "team", "id": "engineering"},
                    "visibility": "private",
                    "lifecycle": "draft",
                },
                "alias": "notes",
                "instructions": "Publish a note.",
                "commands": [{"name": "publish", "kind": "capability", "target": WRITE}],
                "default_command": "publish",
            }
        )
    )
    built.host_tools = lambda: list(host_tools)
    return built, model, write, read


def _converse(built: Gateway, message: str = "do the work") -> Any:
    history = (ModelMessage(role="user", text=message),)
    return asyncio.run(built.converse(request(message), history))


def _observations(model: Scripted) -> list[dict[str, Any]]:
    """Every tool message the model was sent in its last request."""
    return [
        json.loads(message.text) for message in model.calls[-1].messages if message.role == "tool"
    ]


def _host_write(
    outcomes: list[HostToolOutcome], name: str = "files__save"
) -> tuple[HostTool, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    async def handler(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        seen.append(arguments)
        return outcomes[min(len(seen), len(outcomes)) - 1]

    tool = HostTool(
        ModelTool(name=name, description=name, input_contract="x.v1"),
        handler,
        side_effect="write",
    )
    return tool, seen


# -- the Host check's retry ----------------------------------------------------------


def test_a_host_check_retry_that_reissues_the_same_write_does_not_execute_it_twice(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "out" / "report.xlsx"
    (tmp_path / "out").mkdir()
    built, model, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "weekly"})),
            # Names a file that does not exist: `named_outputs_exist` fails.
            _reply(text=f"已寫入 {missing}。"),
            _reply(("notes__publish", {"note": "weekly"})),
            _reply(text="已發布筆記。"),
        ]
    )
    built._workspace_roots = (str(tmp_path),)
    result = _converse(built)
    assert len(model.calls) == 4  # the first pass, then the retry pass
    assert model.calls[2].messages[-1].text.startswith("[Host check failed]")
    assert write.calls == 1
    assert result.status == "answered" and result.text == "已發布筆記。"
    assert [item.replayed for item in result.tools] == [True]
    replayed = result.tools[0]
    assert replayed.capability is not None and replayed.capability.status == "succeeded"
    assert replayed.call_id == "c0"
    observation = _observations(model)[-1]
    assert observation["replayed"] is True and observation["host_note"] == REPLAY_NOTE


def test_a_host_tool_that_declares_a_write_is_guarded_and_one_that_declares_nothing_is_not(
    tmp_path: Path,
) -> None:
    saved, saves = _host_write([HostToolOutcome(status="succeeded", data={"ok": True})])
    plain, plains = _host_write(
        [HostToolOutcome(status="succeeded", data={"ok": True})], name="plain__make"
    )
    plain = HostTool(plain.tool, plain.handler)  # no side effect declared
    missing = tmp_path / "out" / "a.csv"
    (tmp_path / "out").mkdir()
    built, model, _, _ = _built(
        [
            _reply(("files__save", {"path": "a"}), ("plain__make", {})),
            _reply(text=f"已寫入 {missing}。"),
            _reply(("files__save", {"path": "a"}), ("plain__make", {})),
            _reply(text="完成。"),
        ],
        host_tools=(saved, plain),
    )
    built._workspace_roots = (str(tmp_path),)
    result = _converse(built)
    assert len(saves) == 1 and len(plains) == 2
    assert [item.replayed for item in result.tools] == [True, False]


# -- what is not recorded ------------------------------------------------------------


def test_different_arguments_execute() -> None:
    built, _, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "a"})),
            _reply(("notes__publish", {"note": "b"})),
            _reply(text="兩則都發布了。"),
        ]
    )
    result = _converse(built)
    assert write.calls == 2
    assert [item.replayed for item in result.tools] == [False, False]


def test_the_same_write_twice_in_one_pass_runs_once() -> None:
    built, _, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "a"}), ("notes__publish", {"note": "a"})),
            _reply(text="已發布。"),
        ]
    )
    result = _converse(built)
    assert write.calls == 1
    assert [item.replayed for item in result.tools] == [False, True]


def test_reads_are_unaffected() -> None:
    built, _, _, read = _built(
        [
            _reply(("release__check", {}), ("release__check", {})),
            _reply(text="檢查兩次都通過。"),
        ]
    )
    result = _converse(built)
    assert read.calls == 2
    assert [item.replayed for item in result.tools] == [False, False]


def test_a_failed_write_is_not_cached() -> None:
    tool, seen = _host_write(
        [
            HostToolOutcome(status="failed", failure=Failure(code="locked", message="busy")),
            HostToolOutcome(status="succeeded", data={"ok": True}),
        ]
    )
    built, _, _, _ = _built(
        [
            _reply(("files__save", {"path": "a"})),
            _reply(("files__save", {"path": "a"})),
            _reply(("files__save", {"path": "a"})),
            _reply(text="存好了。"),
        ],
        host_tools=(tool,),
    )
    result = _converse(built)
    # The failure ran again when asked; the success after it is recorded once.
    assert len(seen) == 2
    assert [item.replayed for item in result.tools] == [False, False, True]
    assert result.tools[0].failure is None and result.tools[0].host is not None
    assert result.tools[0].host.status == "failed"


def test_a_call_awaiting_approval_is_not_recorded_as_succeeded() -> None:
    built, _, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "a"})),
            _reply(("notes__publish", {"note": "a"})),
            _reply(text="等你核准。"),
        ],
        owner_mode=True,
    )
    asked: list[dict[str, Any]] = []

    def approval(context: RequestContext, target: Any, arguments: dict[str, Any]) -> Any:
        asked.append(arguments)
        return {"approval": "pending"}

    built.capability_approval = approval
    result = _converse(built)
    assert write.calls == 0
    assert len(asked) == 2  # asked again: nothing was done, nothing to replay
    assert [item.host.status for item in result.tools if item.host] == [
        "awaiting_approval",
        "awaiting_approval",
    ]
    assert not any(item.replayed for item in result.tools)


def test_a_refused_write_is_not_recorded() -> None:
    built, _, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "a"})),
            _reply(("notes__publish", {"note": "a"})),
            _reply(text="沒有權限。"),
        ]
    )
    policy = built.bridge.policy
    assert isinstance(policy, LocalPolicy)
    policy._grants.clear()
    result = _converse(built)
    assert write.calls == 0
    assert not any(item.replayed for item in result.tools)
    assert all(
        item.capability is not None and item.capability.status != "succeeded"
        for item in result.tools
    )


# -- Workflow runs -------------------------------------------------------------------


def test_a_workflow_tool_runs_once_per_turn_for_the_same_arguments() -> None:
    built, _, _, read = _built(
        [
            _reply(("release__package", {})),
            _reply(("release__package", {})),
            _reply(text="驗證流程已執行。"),
        ]
    )
    result = _converse(built)
    assert read.calls == 1  # the Workflow's one step ran once
    assert [item.replayed for item in result.tools] == [False, True]
    first, second = (item.workflow for item in result.tools)
    assert first is not None and second is not None
    assert first.run.run_id == second.run.run_id


def test_execute_workflow_inside_a_turn_runs_once_and_outside_a_turn_as_before() -> None:
    built, _, _, read = _built([])
    target = built.engine.workflows.manifests()[0].metadata.identity

    async def inside() -> tuple[Any, Any]:
        with turn_scope() as (effects, owns):
            assert owns and current() is effects
            first = await built.execute_workflow(request("run it"), target, {})
            second = await built.execute_workflow(request("run it"), target, {})
            assert effects.counts() == {"side_effects_recorded": 1, "side_effects_replayed": 1}
            return first, second

    first, second = asyncio.run(inside())
    assert read.calls == 1 and first.run.run_id == second.run.run_id
    assert current() is None
    asyncio.run(built.execute_workflow(request("run it"), target, {}))
    asyncio.run(built.execute_workflow(request("run it"), target, {}))
    assert read.calls == 3  # a form, a schedule or a remote job: the engine decides


def test_a_run_nested_under_the_turn_shares_its_record() -> None:
    """Ready for V1 delegation: a sub-run under the same parent turn does not
    redo a write its parent already did."""
    built: Gateway

    async def delegate(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        inner = await built.converse(
            request("sub-task"), (ModelMessage(role="user", text="sub-task"),)
        )
        return HostToolOutcome(
            status="succeeded",
            data={"replayed": [item.replayed for item in inner.tools]},
        )

    sub = HostTool(ModelTool(name="agent__delegate", description="d", input_contract="x"), delegate)
    built, _, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "a"})),
            _reply(("agent__delegate", {})),
            # The sub-run's own model loop.
            _reply(("notes__publish", {"note": "a"})),
            _reply(text="子任務完成。"),
            _reply(text="都完成了。"),
        ],
        host_tools=(sub,),
    )
    result = _converse(built)
    assert write.calls == 1
    delegated = result.tools[1].host
    assert delegated is not None and delegated.data == {"replayed": [True]}


# -- telemetry -----------------------------------------------------------------------


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, Any]]]:
    seen: dict[str, list[dict[str, Any]]] = {"emit": [], "set_run": []}
    emit, set_run = telemetry_recorder.emit, telemetry_recorder.set_run

    def emitted(event_type: str, **kwargs: Any) -> None:
        if event_type == "tool.replayed":
            seen["emit"].append(kwargs.get("attributes") or {})
        emit(event_type, **kwargs)

    def ran(**attributes: Any) -> None:
        seen["set_run"].append(dict(attributes))
        set_run(**attributes)

    monkeypatch.setattr(telemetry_recorder, "emit", emitted)
    monkeypatch.setattr(telemetry_recorder, "set_run", ran)
    return seen


def test_telemetry_gets_counts_only(events: dict[str, list[dict[str, Any]]]) -> None:
    marker = "argument-marker-p02"
    built, _, write, _ = _built(
        [
            _reply(("notes__publish", {"note": marker}), ("notes__publish", {"note": marker})),
            _reply(("notes__publish", {"note": "other"})),
            _reply(text="完成。"),
        ]
    )
    _converse(built)
    assert write.calls == 2
    assert events["emit"] == [{"tool_id": "notes__publish", "loop_index": 1, "replayed": 1}]
    final = events["set_run"][-1]
    assert final["side_effects_recorded"] == 2 and final["side_effects_replayed"] == 1
    assert marker not in json.dumps(events, default=str)
