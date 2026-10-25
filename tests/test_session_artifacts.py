"""A session remembers what it produced (owner, Telegram, 2026-10-25).

The SDE weekly report ran at 15:15 and made `effort-chart.png`; at 16:57 in
the same chat 「那你可以把統計圖片貼在這個 session 嗎」 got "I have no image file,
give me a path". Now the run's result and its outputs are kept per session
and actor (short id, kind, file name), listed in every turn's system prompt
so they outlive the history window, the run's pictures are sent at its end,
and `session__attach_file {artifact_id}` attaches one again. Over the fake
Bot API of `test_telegram_ingress` and Agent Web's in-process object; no
socket, no real bot, no Outlook. Synthetic data.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from test_run_prefill import TODAY
from test_telegram_fewer_questions import _install
from test_telegram_ingress import OWNER, FakeReply, FakeTransport, ingress, poll, update
from test_telegram_workflow_flow import _tap

from common import run_prefill
from common.assets import AssetIdentity
from common.execution import (
    CapabilityResult,
    RequestContext,
    TraceIdentifiers,
    WorkflowRun,
)
from host_runtime.agent import LocalAgentOutcome
from host_runtime.session_artifacts import (
    ATTACH_TOOL,
    SessionArtifacts,
)
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent, ModelToolCall
from workflow.engine import WorkflowRunSnapshot

PNG = b"\x89PNG\r\n\x1a\n" + b"chart"
TRACE = TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1")
SDE = AssetIdentity(namespace="engineering", name="sde-weekly-report", version="1.0.0")


def _snapshot(workspace: Path, run_id: str = "run-43w", *, outside: Path | None = None) -> Any:
    """What the SDE weekly report's mail step returns: the chart beside the
    draft, the draft's Outlook id and subject, and the plain-text preview."""
    chart = workspace / "weekly-mail" / "2026_43W" / "effort-chart.png"
    chart.parent.mkdir(parents=True, exist_ok=True)
    chart.write_bytes(PNG)
    data: dict[str, Any] = {
        "week": "2026_43W",
        "subject": "[SDE] Weekly report 2026_43W",
        "entry_id": "000ABC",
        "matched": 63,
        "counted": 4,
        "chart_path": str(chart),
        "preview": "SDE weekly report 2026_43W: 4 items worked on\nmore lines",
    }
    if outside is not None:
        data["png_path"] = str(outside)
    return WorkflowRunSnapshot(
        run=WorkflowRun(
            run_id=run_id, workflow=SDE, trace=TRACE, status="succeeded", completed_steps=3
        ),
        step_results=(
            CapabilityResult(trace=TRACE, status="succeeded", data={"week": "2026_43W"}),
            CapabilityResult(trace=TRACE, status="succeeded", data=data),
        ),
    )


def _context(session: str | None, actor: str = "engineer") -> RequestContext:
    return RequestContext(
        trace=TRACE,
        actor=actor,
        namespace="engineering",
        message="把統計圖貼給我",
        channel="telegram",
        session_id=session,
    )


def _attach(store: SessionArtifacts, context: RequestContext, artifact_id: object) -> Any:
    tool = store.tools()[0]

    async def call() -> Any:
        return await tool.handler(context, {"artifact_id": artifact_id})  # type: ignore[dict-item]

    return asyncio.run(call())


class ChartModel:
    """Asked for the chart, attaches the id the system prompt lists for
    `effort-chart.png`; otherwise answers plainly. Keeps every request."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if request.messages[-1].role == "tool":
            return ModelResponse(
                trace=request.trace, model_alias=request.model_alias, text="統計圖在下面。"
            )
        user = [m.text for m in request.messages if m.role == "user"][-1]
        system = request.messages[0].text
        listed = re.search(r"(f\d+) image: effort-chart\.png", system)
        offered = {tool.name for tool in request.tools}
        if "統計圖" in user and listed and ATTACH_TOOL in offered:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                tool_calls=(
                    ModelToolCall(
                        call_id=f"c{len(self.requests)}",
                        name=ATTACH_TOOL,
                        arguments={"artifact_id": listed.group(1)},
                    ),
                ),
            )
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text="好的")

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


class UploadTransport(FakeTransport):
    """Also takes `sendPhoto` and `sendDocument` (multipart), recording each."""

    def __init__(self, batches: list[list[dict[str, Any]]]) -> None:
        super().__init__(batches)
        self.uploads: list[tuple[str, bytes]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        method = url.rsplit("/", 1)[-1]
        if method in ("sendPhoto", "sendDocument"):
            self.uploads.append((method, body))
            return FakeReply(200, {"ok": True, "result": {"message_id": 99}})
        return super().send(url, body, headers, timeout_s)


# -- the ledger and the attach tool ---------------------------------------------


def test_a_run_is_kept_with_its_outputs_by_short_id(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    store = SessionArtifacts(workspace)
    elsewhere = tmp_path / "elsewhere.png"
    elsewhere.write_bytes(PNG)
    run = store.record_run("chat-1", "engineer", _snapshot(workspace, outside=elsewhere))
    assert run is not None and run.status == "succeeded"
    assert run.summary == "SDE weekly report 2026_43W: 4 items worked on"
    ledger = store.ledger("chat-1", "engineer")
    kinds = [(item.artifact_id, item.kind, item.filename) for item in ledger.artifacts]
    # The file outside the workspace is not kept; the mail draft is, without a path.
    assert kinds == [
        ("f1", "image", "effort-chart.png"),
        ("f2", "mail draft", "[SDE] Weekly report 2026_43W"),
    ]
    # Recording the same run again changes nothing.
    store.record_run("chat-1", "engineer", _snapshot(workspace))
    assert len(store.ledger("chat-1", "engineer").runs) == 1
    guidance = store.guidance(_context("chat-1"))
    assert "Workflow sde-weekly-report run run-43w: succeeded" in guidance
    assert "f1 image: effort-chart.png" in guidance and ATTACH_TOOL in guidance
    assert str(workspace) not in guidance  # ids and names, never paths
    assert store.guidance(_context("chat-2")) == ""


def test_the_attach_tool_refuses_anything_not_made_here_for_this_person(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    store = SessionArtifacts(workspace)
    store.record_run("chat-1", "engineer", _snapshot(workspace))
    ok = _attach(store, _context("chat-1"), "f1")
    assert ok.status == "succeeded" and ok.data["filename"] == "effort-chart.png"
    assert "path" not in json.dumps(ok.data)
    refusals = {
        "another session": (_context("chat-2"), "f1"),
        "another actor": (_context("chat-1", actor="someone-else"), "f1"),
        "a path": (_context("chat-1"), str(workspace / "weekly-mail" / "2026_43W")),
        "a traversal": (_context("chat-1"), "../state.sqlite"),
        "not a string": (_context("chat-1"), 1),
        "no session": (_context(None), "f1"),
        "a mail draft": (_context("chat-1"), "f2"),
        "unknown id": (_context("chat-1"), "f9"),
    }
    codes = {
        name: _attach(store, context, value).failure.code
        for name, (context, value) in refusals.items()
    }
    assert codes == {
        "another session": "artifact_unknown",
        "another actor": "artifact_unknown",
        "a path": "artifact_id_invalid",
        "a traversal": "artifact_id_invalid",
        "not a string": "artifact_id_invalid",
        "no session": "attach_no_session",
        "a mail draft": "artifact_not_a_file",
        "unknown id": "artifact_unknown",
    }
    # A file that left the workspace since is refused too.
    (workspace / "weekly-mail" / "2026_43W" / "effort-chart.png").unlink()
    assert _attach(store, _context("chat-1"), "f1").failure.code == "artifact_missing"


# -- Telegram -------------------------------------------------------------------


def _telegram(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, ...]:
    monkeypatch.setattr(run_prefill, "_today", lambda: TODAY)
    transport = UploadTransport([[update(1, OWNER, "幫我執行 43W SDE weekly report")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent)
    workspace = tmp_path / "workspace"
    store = SessionArtifacts(workspace)
    item.session_artifacts = store
    agent.gateway.session_context = store.guidance
    agent.gateway.host_tools = store.tools
    model = ChartModel()
    agent.gateway.router.model = model

    async def fake_run(state: Any, step: Any, acting: str, *_: Any) -> LocalAgentOutcome:
        return LocalAgentOutcome(
            trace=TRACE, ingress="telegram", actor=acting, workflow=_snapshot(workspace)
        )

    monkeypatch.setattr(item, "_execute_flow", fake_run)
    return item, transport, store, model


def _run_the_report(item: Any, transport: UploadTransport) -> Any:
    card = poll(item).deliveries[0]
    assert (card.reply or "").startswith("執行 sde-weekly-report？")
    transport.batches.append([_tap(2, OWNER, "run:yes", transport)])
    return poll(item).deliveries[0]


def test_telegram_sends_the_runs_chart_and_attaches_it_again_on_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item, transport, _store, model = _telegram(tmp_path, monkeypatch)
    ran = _run_the_report(item, transport)
    assert ran.disposition == "routed"
    # The chart goes out at the end of the run, as a photo with its name.
    assert len(ran.attached) == 1 and ran.attached[0].endswith("effort-chart.png")
    assert [method for method, _ in transport.uploads] == ["sendPhoto"]
    assert b'filename="effort-chart.png"' in transport.uploads[0][1]
    assert b"\xe4\xbe\x9d\xe4\xba\x8b\xe6\xa5\xad\xe7\xbe\xa4" not in transport.uploads[0][1]
    # The chat's history keeps the result and its outputs by short id.
    history = item._histories[(OWNER, OWNER)]
    entry = history[-1].text
    assert "【執行結果】sde-weekly-report · run run-43w · succeeded" in entry
    assert "- f1 image: effort-chart.png" in entry and "- f2 mail draft:" in entry
    assert str(tmp_path) not in entry
    # Later: 「把統計圖貼給我」 attaches it, and the photo is sent again.
    transport.batches.append([update(3, OWNER, "把統計圖貼給我")])
    asked = poll(item).deliveries[0]
    assert asked.reply == "統計圖在下面。" and len(asked.attached) == 1
    assert [method for method, _ in transport.uploads] == ["sendPhoto", "sendPhoto"]
    called = [m for m in model.requests[-1].messages if m.role == "tool"]
    assert called and "path" not in called[0].text


def test_the_run_entry_survives_more_than_the_chat_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from channels.telegram import MAX_CHAT_HISTORY

    item, transport, _store, model = _telegram(tmp_path, monkeypatch)
    _run_the_report(item, transport)
    for number in range(MAX_CHAT_HISTORY + 2):
        transport.batches.append([update(10 + number, OWNER, f"閒聊 {number}")])
        poll(item)
    history = item._histories[(OWNER, OWNER)]
    assert not any("【執行結果】" in message.text for message in history)  # out of the window
    # Yet the model still sees what the session produced, and attaches it.
    assert "f1 image: effort-chart.png" in model.requests[-1].messages[0].text
    transport.batches.append([update(99, OWNER, "那你可以把統計圖片貼在這個 session 嗎")])
    asked = poll(item).deliveries[0]
    assert len(asked.attached) == 1 and asked.attached[0].endswith("effort-chart.png")
    assert transport.uploads[-1][0] == "sendPhoto"


def test_new_starts_with_nothing_produced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    item, transport, store, _model = _telegram(tmp_path, monkeypatch)
    _run_the_report(item, transport)
    assert store.ledger(f"telegram-chat-{OWNER}", "engineer").artifacts
    transport.batches.append([update(3, OWNER, "/new")])
    poll(item)
    assert not store.ledger(f"telegram-chat-{OWNER}", "engineer").artifacts


# -- Agent Web --------------------------------------------------------------------


class AttachingGateway:
    """An OpenAI-compatible model: asked for the chart with the attach tool
    on offer, calls it with the id the system prompt lists; else "ok"."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> Any:
        from test_host_models import GatewayReply

        payload = json.loads(body)
        self.calls.append(payload)
        messages = payload.get("messages", [])
        offered = {tool["function"]["name"] for tool in payload.get("tools", [])}
        system = messages[0].get("content") or "" if messages else ""
        listed = re.search(r"(f\d+) image: effort-chart\.png", str(system))
        last = messages[-1] if messages else {}
        if last.get("role") == "tool":
            reply: dict[str, Any] = {"role": "assistant", "content": "統計圖在下面。"}
        elif ATTACH_TOOL in offered and listed and "統計圖" in str(last.get("content")):
            reply = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": ATTACH_TOOL,
                            "arguments": json.dumps({"artifact_id": listed.group(1)}),
                        },
                    }
                ],
            }
        else:
            reply = {"role": "assistant", "content": "ok"}
        return GatewayReply(200, {"choices": [{"index": 0, "message": reply}]})


def test_agent_web_shows_the_runs_chart_and_attaches_it_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_chat_workflow_forms import _plain
    from test_conversation_turn_groups import _chat_config

    from host_runtime.contracts import WorkflowLaunchRequest
    from host_runtime.conversations import ConversationTurnRequest
    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb

    config, layout = _chat_config(tmp_path)
    transport = AttachingGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        manifest = _plain("sde-weekly-report")
        runtime.agent.gateway.engine.workflows.register(manifest)
        (runtime.layout.workflows / "sde-weekly-report.json").write_text(
            manifest.model_dump_json(), encoding="utf-8"
        )
        web = AgentWeb(runtime)
        workspace = runtime.layout.workspace_root

        async def fake_execute(request: Any) -> LocalAgentOutcome:
            return LocalAgentOutcome(
                trace=TRACE,
                ingress="local",
                actor=request.actor,
                workflow=_snapshot(workspace),
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
        assert "【執行結果】sde-weekly-report · run run-43w" in message["text"]
        assert [file["filename"] for file in message["attachments"]] == ["effort-chart.png"]
        chart = message["attachments"][0]["path"]
        assert web.conversation_file(session, chart) == (PNG, "image/png")
        # A chat of more than the window later, the chart is attached again.
        for number in range(14):
            web.conversation_turn(
                ConversationTurnRequest(session_id=session, message=f"聊 {number}")
            )
        turned = web.conversation_turn(
            ConversationTurnRequest(session_id=session, message="把統計圖貼給我")
        )
        stored = turned["conversation"]["messages"][-1]
        assert [file["filename"] for file in stored["attachments"]] == ["effort-chart.png"]
        assert web.conversation_file(session, stored["attachments"][0]["path"]) is not None
        # Another conversation cannot attach it.
        other = web.create_conversation()["conversation"]["session_id"]
        refused = _attach(
            runtime.session_artifacts,  # type: ignore[arg-type]
            RequestContext(
                trace=TRACE,
                actor=runtime.actor,
                namespace="engineering",
                message="x",
                channel="agent_web",
                session_id=other,
            ),
            "f1",
        )
        assert refused.failure.code == "artifact_unknown"
