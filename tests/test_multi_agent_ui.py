"""Multi-agent V1, the person-facing side: the sub-agent lines of a running
turn, the 「委派紀錄」 under the answer (Agent Web and Telegram) and the Settings
switch. Fakes only: no model, no Gateway sub-run, no real bot, no restart."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture
from test_host_wiring import host_json, ready
from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update

from agent import turn_progress
from agent.gateway import ConversationToolExecution, GatewayConversationResult, HostToolOutcome
from agent.turn_progress import SubAgentProgress, TurnProgress, compact_lines, delegation_lines
from common.execution import Failure, TraceIdentifiers
from host_runtime import multi_agent_switch
from host_runtime.agent import LocalConversationOutcome
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.conversation_backends import LocalConversationBackends
from host_runtime.delegation_record import DELEGATE_TOOL, records_from, text_lines
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer

TRACE = TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1")
ANSWER = "兩份文件的比較如下。"
SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "multi-agent-ui"
SECRET_ARGUMENT = "argument-marker-5d1"


def delegation(
    profile: str = "engineering/researcher@1.0.0",
    status: str = "succeeded",
    *,
    summary: str = "Vendor Q 的 MLO 支援 3 條鏈路。\n- 來源 [doc-a]",
    artifacts: list[dict[str, Any]] | None = None,
    failure: str | None = None,
    question: str | None = None,
    tokens: tuple[int | None, int | None, int] = (1200, 300, 2),
) -> dict[str, Any]:
    """A `DelegationResult` as the tool's host data carries it (the contract)."""
    data: dict[str, Any] = {
        "status": status,
        "profile": profile,
        "summary": summary,
        "findings": ["來源 [doc-a]"],
        "question": question,
        "artifacts": artifacts or [],
        "approvals": [],
        "tool_calls": [{"name": "knowledge__vault", "status": "succeeded", "replayed": False}],
        "tokens": {"input": tokens[0], "output": tokens[1], "model_calls": tokens[2]},
        "read_only": True,
        "validated": status == "succeeded",
        "host_note": None,
        "elapsed_s": 4.2,
        "failure": None if failure is None else {"code": failure, "message": "m"},
    }
    return data


def delegate_call(index: int, data: dict[str, Any]) -> ConversationToolExecution:
    failed = data["status"] in ("failed", "needs_input")
    return ConversationToolExecution(
        call_id=f"d{index}",
        name=DELEGATE_TOOL,
        arguments={"profile": data["profile"], "objective": SECRET_ARGUMENT},
        host=HostToolOutcome(
            status="failed" if failed else "succeeded",
            data={"delegation": data},
            failure=(
                Failure(code=data["failure"]["code"] if data["failure"] else "x", message="m")
                if failed
                else None
            ),
        ),
    )


def answered(*calls: ConversationToolExecution) -> GatewayConversationResult:
    return GatewayConversationResult(
        trace=TRACE, status="answered", text=ANSWER, model_turns=2, tools=calls
    )


# -- the progress hook (turn_progress) ---------------------------------------------


def test_each_sub_agent_is_a_line_under_the_turn_with_its_own_count_and_time() -> None:
    now = [0.0]
    parent = TurnProgress(turn_id="t", clock=lambda: now[0])
    parent.set_limits(150, 1800)
    changes: list[int] = []
    parent.listener = lambda: changes.append(1)
    first = parent.delegation_started(
        "engineering/researcher@1.0.0", "比較 Vendor Q 與 Vendor M 的 MLO\n支援", read_only=True
    )
    second = parent.delegation_started("engineering/coder@2.0.0", "寫 parser", read_only=False)
    assert isinstance(first, SubAgentProgress) and changes
    # A sub-run reports into its own line: limits, tools, across its passes.
    first.set_limits(20, 300)
    first.tool_started("knowledge__vault")
    first.tool_finished("knowledge__vault", "succeeded")
    first.begin_pass()
    first.tool_started("knowledge__vault")
    now[0] = 12.0
    shown = parent.snapshot()
    assert shown["tool_count"] == 0  # the parent's own count is untouched
    assert shown["delegations_running"] == 2
    lines = shown["delegations"]
    assert [line["profile"] for line in lines] == ["engineering/researcher", "engineering/coder"]
    assert lines[0] == {
        "index": 1,
        "profile": "engineering/researcher",
        "objective": "比較 Vendor Q 與 Vendor M 的 MLO 支援",
        "status": "running",
        "label": "執行中",
        "read_only": True,
        "tool_count": 2,
        "tool_cap": 20,
        "elapsed_s": 12,
    }
    assert lines[1]["read_only"] is False and lines[1]["tool_cap"] is None
    first.finish("succeeded")
    now[0] = 30.0
    second.finish("needs_input")
    after = parent.snapshot()
    assert "delegations_running" not in after
    assert [(line["status"], line["label"]) for line in after["delegations"]] == [
        ("done", "完成"),
        ("needs_input", "需要資訊"),
    ]
    assert after["delegations"][0]["elapsed_s"] == 12  # stopped at its end


def test_the_objective_is_short_and_never_carries_a_credential() -> None:
    parent = TurnProgress(turn_id="t")
    long = parent.delegation_started("a/b@1", "x" * 200)
    secret = parent.delegation_started("a/c@1", "use Authorization: Bearer abcdefghijklmnop123")
    lines = parent.snapshot()["delegations"]
    assert len(lines[0]["objective"]) == turn_progress.MAX_OBJECTIVE_CHARS
    assert lines[0]["objective"].endswith("…")
    assert "abcdefghijklmnop123" not in lines[1]["objective"]
    assert long.status == secret.status == "running"


def test_a_sub_agent_cannot_open_a_line_of_its_own() -> None:
    child = TurnProgress(turn_id="t").delegation_started("a/b@1", "x")
    with pytest.raises(RuntimeError):
        child.delegation_started("a/c@1", "y")
    child.delegation_changed(1)  # depth 1: ignored
    assert child.delegations_running == 0


def test_the_core_counter_and_the_lines_are_not_counted_twice() -> None:
    parent = TurnProgress(turn_id="t")
    parent.delegation_changed(1)
    assert parent.snapshot()["delegations_running"] == 1
    assert "delegations" not in parent.snapshot()
    parent.delegation_started("a/b@1", "x")
    assert parent.snapshot()["delegations_running"] == 1
    parent.delegation_started("a/c@1", "y")
    assert parent.snapshot()["delegations_running"] == 2


def test_a_turn_without_delegation_shows_exactly_what_it_did_before() -> None:
    parent = TurnProgress(turn_id="t")
    parent.tool_started("files__read")
    shown = parent.snapshot()
    assert "delegations" not in shown and "delegations_running" not in shown
    assert delegation_lines(shown) == []
    assert compact_lines(shown) == ["0:00"]


def test_the_chat_status_lists_each_sub_agent() -> None:
    now = [0.0]
    parent = TurnProgress(turn_id="t", clock=lambda: now[0])
    first = parent.delegation_started("engineering/researcher@1.0.0", "比較兩份文件")
    first.set_limits(20, 300)
    first.tool_started("knowledge__vault")
    parent.delegation_started("engineering/coder@1.0.0", "寫 parser").finish("failed")
    now[0] = 65.0
    assert compact_lines(parent.snapshot()) == [
        "子代理（1 個執行中）：",
        "⏳ engineering/researcher：執行中 · 工具 1/20 · 1:05",
        "   比較兩份文件",
        "✗ engineering/coder：失敗 · 工具 0 · 0:00",
        "   寫 parser",
        "1:05",
    ]


# -- the record (委派紀錄) ---------------------------------------------------------


def test_the_record_keeps_ran_sub_agents_with_status_summary_artifacts_and_tokens() -> None:
    tools = (
        delegate_call(
            1,
            delegation(
                artifacts=[
                    {"kind": "file", "id": "f3", "name": "compare.md", "status": None},
                    {"kind": "run", "id": "run-1", "name": "release", "status": "succeeded"},
                ]
            ),
        ),
        # Refused: no sub-agent ran, so it is not in the record.
        delegate_call(
            2,
            delegation(
                "engineering/nobody",
                "failed",
                failure="delegation_target_not_allowed",
                tokens=(None, None, 0),
            ),
        ),
        delegate_call(
            3,
            delegation(
                "engineering/coder@1.0.0",
                "needs_input",
                question="要用哪一個 log 版本？",
                tokens=(None, None, 1),
            ),
        ),
        ConversationToolExecution(
            call_id="x", name="files__read", arguments={}, host=HostToolOutcome(status="succeeded")
        ),
    )
    records = records_from(
        tools, lambda artifact_id: "C:/w/out/compare.md" if artifact_id == "f3" else None
    )
    assert [record["profile"] for record in records] == [
        "engineering/researcher@1.0.0",
        "engineering/coder@1.0.0",
    ]
    first = records[0]
    assert first["status"] == "succeeded" and first["validated"] is True
    assert first["summary"] == "Vendor Q 的 MLO 支援 3 條鏈路。 - 來源 [doc-a]"
    assert first["tokens"] == {"input": 1200, "output": 300, "model_calls": 2}
    assert first["artifacts"][0] == {
        "kind": "file",
        "id": "f3",
        "name": "compare.md",
        "path": "C:/w/out/compare.md",
    }
    assert first["artifacts"][1]["status"] == "succeeded" and "path" not in first["artifacts"][1]
    assert records[1]["question"] == "要用哪一個 log 版本？"
    # Never the objective (the tool's arguments).
    assert SECRET_ARGUMENT not in json.dumps(records, ensure_ascii=False)
    assert text_lines(records) == [
        "委派紀錄",
        "• engineering/researcher@1.0.0 — 完成 · 4.2 s · tokens 1,200/300（2 次呼叫）",
        "  Vendor Q 的 MLO 支援 3 條鏈路。 - 來源 [doc-a]",
        "  產出：f3 compare.md、run-1 release（succeeded）",
        "• engineering/coder@1.0.0 — 需要資訊 · 4.2 s · 1 次模型呼叫",
        "  需要：要用哪一個 log 版本？",
    ]


def test_a_long_summary_is_cut_and_a_malformed_record_is_skipped() -> None:
    long = delegate_call(1, delegation(summary="長" * 1000))
    broken = ConversationToolExecution(
        call_id="b",
        name=DELEGATE_TOOL,
        arguments={},
        host=HostToolOutcome(status="succeeded", data={"delegation": {"status": "weird"}}),
    )
    records = records_from((long, broken))
    assert len(records) == 1 and len(records[0]["summary"]) == 280
    assert records[0]["summary"].endswith("…")
    assert records_from(()) == [] and text_lines([]) == []


# -- Agent Web: the answer keeps its record, the files open in the viewer -----------


def _session(url: str, token: str) -> str:
    created = fetch(url + "/api/conversations", token=token, body={}).json()
    session_id: str = created["conversation"]["session_id"]
    return session_id


def _progress(url: str, token: str, session_id: str) -> Any:
    return fetch(url + "/api/conversations/progress?session_id=" + session_id, token=token).json()


def _wait_for(read: Callable[[], Any], seconds: float = 20) -> Any:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = read()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("timed out")


def _delegating_turn(
    web: AgentWeb, release: threading.Event, *, elapsed: int = 0
) -> Callable[..., Any]:
    """A turn that starts sub-agents the way the core reports them (two
    read-only ones in parallel, one already done), then answers with their
    results; the third one's file is in the session ledger."""

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        progress = turn_progress.current()
        assert progress is not None, "the turn runs with its progress set"
        progress.started -= elapsed
        progress.set_limits(150, 1800)
        done = progress.delegation_started(
            "engineering/coder@1.0.0", "依 T15 規格寫 log parser 並跑測試", read_only=False
        )
        done.set_limits(20, 300)
        for _step in range(3):
            done.tool_started("coding__run")
            done.tool_finished("coding__run", "succeeded")
        done.finish("succeeded")
        left = progress.delegation_started(
            "engineering/researcher@1.0.0", "整理 Vendor Q 文件的 MLO 規格與限制"
        )
        right = progress.delegation_started(
            "engineering/researcher@1.0.0", "整理 Vendor M 文件的 MLO 規格與限制"
        )
        for child in (left, right):
            child.set_limits(20, 300)
            child.tool_started("knowledge__vault")
        await asyncio.to_thread(release.wait, 60)
        left.finish("succeeded")
        right.finish("needs_input")
        workspace = web.runtime.layout.workspace_root
        out = workspace / "outputs" / "compare.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("# Vendor Q vs Vendor M\n\n| | Q | M |\n|---|---|---|\n", encoding="utf-8")
        store = web.runtime.session_artifacts
        assert store is not None
        [file_id] = store.record_files(request.session_id, request.actor, [{"path": str(out)}])
        result = answered(
            delegate_call(
                1,
                delegation(
                    "engineering/coder@1.0.0",
                    summary="parser 完成，6 筆、3 個 warning。",
                    artifacts=[{"kind": "file", "id": file_id, "name": "compare.md"}],
                ),
            ),
            delegate_call(2, delegation()),
            delegate_call(
                3,
                delegation(
                    summary="",
                    status="needs_input",
                    question="Vendor M 文件缺少第 4 章，要用哪一版？",
                ),
            ),
        )
        return LocalConversationOutcome(
            trace=TRACE, ingress="local", actor=request.actor, conversation=result
        )

    return converse


def test_the_progress_route_shows_sub_agents_and_the_answer_keeps_the_record(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    monkeypatch.setattr(served.web.runtime.agent, "converse", _delegating_turn(served.web, release))
    url, token = base(served), served.token
    session_id = _session(url, token)
    finished: list[Any] = []
    turn = threading.Thread(
        target=lambda: finished.append(
            fetch(
                url + "/api/conversations/turn",
                token=token,
                body={"session_id": session_id, "message": "比較這兩份文件"},
            ).json()
        )
    )
    turn.start()
    try:
        shown = _wait_for(
            lambda: (
                len((_progress(url, token, session_id)["progress"] or {}).get("delegations") or [])
                == 3
                and _progress(url, token, session_id)["progress"]
            )
        )
        assert shown["delegations_running"] == 2
        assert [line["status"] for line in shown["delegations"]] == ["done", "running", "running"]
        assert shown["delegations"][0]["tool_count"] == 3
        assert SECRET_ARGUMENT not in json.dumps(shown, ensure_ascii=False)
    finally:
        release.set()
        turn.join(timeout=30)
    reply = finished[0]["answer"]
    assert reply["answer"].startswith(ANSWER)
    stored = fetch(url + "/api/conversations?session_id=" + session_id, token=token).json()
    answer = stored["selected"]["messages"][-1]
    records = answer["delegations"]
    assert [record["status"] for record in records] == ["succeeded", "succeeded", "needs_input"]
    file_artifact = records[0]["artifacts"][0]
    assert file_artifact["id"].startswith("f") and file_artifact["path"].endswith("compare.md")
    # The file is listed on the answer, so the viewer route serves it.
    assert file_artifact["path"] in {item["path"] for item in answer["attachments"]}
    served_file = fetch(
        url
        + "/api/conversations/file?session_id="
        + session_id
        + "&path="
        + __import__("urllib.parse").parse.quote(file_artifact["path"]),
        token=token,
    )
    assert served_file.status == 200 and b"Vendor Q vs Vendor M" in served_file.body


def test_an_answer_without_delegation_has_no_record(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        return LocalConversationOutcome(
            trace=TRACE, ingress="local", actor=request.actor, conversation=answered()
        )

    monkeypatch.setattr(served.web.runtime.agent, "converse", converse)
    url, token = base(served), served.token
    session_id = _session(url, token)
    fetch(
        url + "/api/conversations/turn",
        token=token,
        body={"session_id": session_id, "message": "hi"},
    )
    stored = fetch(url + "/api/conversations?session_id=" + session_id, token=token).json()
    assert stored["selected"]["messages"][-1]["delegations"] == []


# -- Settings: the switch round-trips through host.json ---------------------------


def test_the_settings_switch_writes_host_json_and_says_a_restart_is_needed(
    tmp_path: Path,
) -> None:
    config, _layout = ready(tmp_path)
    config_path = host_json(tmp_path, config)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime, config_path=config_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url, token = base(server), server.token
            before = fetch(url + "/api/settings/multi-agent", token=token).json()
            assert before == {
                "ok": True,
                "supported": True,
                "writable": True,
                "enabled": False,
                "running": False,
                "restart_needed": False,
            }
            assert fetch(url + "/api/settings/multi-agent").status == 401
            on = fetch(url + "/api/settings/multi-agent", token=token, body={"enabled": True})
            assert on.status == 200
            assert on.json()["enabled"] is True and on.json()["running"] is False
            assert on.json()["restart_needed"] is True
            written = CompanyHostConfiguration.model_validate_json(
                config_path.read_text(encoding="utf-8")
            )
            assert written.multi_agent.enabled is True
            # The running Agent is unchanged until the restart.
            assert runtime.config.multi_agent.enabled is False
            read = fetch(url + "/api/settings/multi-agent", token=token).json()
            assert read["enabled"] is True and read["restart_needed"] is True
            bad = fetch(url + "/api/settings/multi-agent", token=token, body={"enabled": "yes"})
            assert bad.status == 409 and bad.json()["code"] == "multi_agent_settings_invalid"
            off = fetch(url + "/api/settings/multi-agent", token=token, body={"enabled": False})
            assert off.json()["enabled"] is False and off.json()["restart_needed"] is False
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    written = CompanyHostConfiguration.model_validate_json(config_path.read_text(encoding="utf-8"))
    assert written.multi_agent.enabled is False
    # Everything else in the file is kept.
    assert written.model_dump(exclude={"multi_agent"}) == config.model_dump(exclude={"multi_agent"})


def test_the_switch_is_read_only_without_a_config_file_and_off_on_an_older_host(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, token = base(served), served.token
    shown = fetch(url + "/api/settings/multi-agent", token=token).json()
    assert shown["writable"] is False and shown["enabled"] is False
    refused = fetch(url + "/api/settings/multi-agent", token=token, body={"enabled": True})
    assert refused.status == 409 and refused.json()["code"] == "settings_read_only"
    # A Host whose contract predates the flag: nothing is written.
    monkeypatch.setattr(multi_agent_switch, "supported", lambda: False)
    older = fetch(url + "/api/settings/multi-agent", token=token).json()
    assert older["supported"] is False and older["writable"] is False
    assert (
        fetch(url + "/api/settings/multi-agent", token=token, body={"enabled": True}).json()["code"]
        == "multi_agent_unsupported"
    )


# -- Telegram: the status lists the sub-agents, the reply ends with the record -------


def test_telegram_lists_sub_agents_in_its_status_and_the_record_in_the_reply(
    tmp_path: Path,
) -> None:
    transport = FakeTransport([[update(1, OWNER, "比較這兩份文件")]])
    item, agent, _ = ingress(tmp_path, transport)
    item.status_edit_interval_s = 0.0

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        progress = turn_progress.current()
        assert progress is not None
        child = progress.delegation_started("engineering/researcher@1.0.0", "整理 Vendor Q 文件")
        child.tool_started("knowledge__vault")
        await asyncio.sleep(0.2)  # the status message shows the running line
        child.finish("succeeded")
        await asyncio.sleep(0.2)
        result = answered(
            delegate_call(1, delegation(artifacts=[{"kind": "file", "id": "f7", "name": "q.md"}]))
        )
        return LocalConversationOutcome(
            trace=TRACE, ingress="telegram", actor=request.actor, conversation=result
        )

    agent.converse = converse  # type: ignore[method-assign]
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered"
    statuses = transport.statuses()
    assert any(
        "子代理（1 個執行中）：" in text and "⏳ engineering/researcher：執行中 · 工具 1" in text
        for text in statuses
    ), statuses
    assert any("✓ engineering/researcher：完成" in text for text in statuses), statuses
    # One status message, edited in place.
    assert sum(1 for url, _ in transport.calls if url.endswith("/sendMessage")) >= 1
    [reply] = transport.sent()
    assert reply.startswith(ANSWER)
    assert "委派紀錄\n• engineering/researcher@1.0.0 — 完成 · 4.2 s" in reply
    assert "產出：f7 q.md" in reply
    assert SECRET_ARGUMENT not in reply and all(SECRET_ARGUMENT not in s for s in statuses)


def test_telegram_sends_a_long_record_through_the_file_fallback(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "比較")]])
    item, agent, _ = ingress(tmp_path, transport)

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        long = "結論" * 2000
        result = GatewayConversationResult(
            trace=TRACE,
            status="answered",
            text=long,
            model_turns=2,
            tools=(delegate_call(1, delegation()),),
        )
        return LocalConversationOutcome(
            trace=TRACE, ingress="telegram", actor=request.actor, conversation=result
        )

    agent.converse = converse  # type: ignore[method-assign]
    poll(item)
    documents = [url for url, _ in transport.calls if url.endswith("/sendDocument")]
    sent = transport.sent()
    # The existing long-reply handling applies to the reply with its record.
    assert documents or len(sent) > 1, transport.calls


# -- the views in a real browser -------------------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_sub_agents_and_the_record_in_a_real_browser(tmp_path: Path) -> None:
    from integrations.browser import Browser

    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        backends = LocalConversationBackends(layout.workspace_root, which=lambda _name: None)
        config_path = host_json(tmp_path, config)
        web = AgentWeb(runtime, conversation_backends=backends, config_path=config_path)
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        release = threading.Event()
        runtime.agent.converse = _delegating_turn(web, release, elapsed=75)  # type: ignore[method-assign]
        browser = Browser(tmp_path / "browser", timeout_s=60, viewport=(1440, 900))
        browser.start()
        shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
        shots.mkdir(parents=True, exist_ok=True)

        def wait(expression: str, seconds: float = 30) -> object:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                value = browser._evaluate(expression)
                if value:
                    return value
                time.sleep(0.2)
            raise AssertionError(expression)

        def no_side_scroll() -> None:
            assert not browser._evaluate(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )

        def dark(on: bool) -> None:
            browser.page().call(
                "Emulation.setEmulatedMedia",
                features=[{"name": "prefers-color-scheme", "value": "dark" if on else "light"}],
            )

        def narrow(on: bool) -> None:
            width, height = (390, 844) if on else (1440, 900)
            browser.page().call(
                "Emulation.setDeviceMetricsOverride",
                width=width,
                height=height,
                deviceScaleFactor=1,
                mobile=on,
            )
            assert browser._evaluate("innerWidth") == width

        agents = ".turn-progress .tp-agents"
        try:
            browser.navigate(server.address)
            assert browser._evaluate("innerWidth") == 1440
            wait('!document.getElementById("send").disabled')
            browser._evaluate(
                'document.getElementById("message").value = "比較這兩份文件";'
                'document.getElementById("send").click()'
            )
            wait(f'document.querySelectorAll("{agents} li").length === 3')
            shown = str(browser._evaluate("document.querySelector('.turn-progress').innerText"))
            for words in (
                "子代理執行中（2 個）…",
                "engineering/coder",
                "完成",
                "依 T15 規格寫 log parser 並跑測試",
                "工具 3/20 · 0:00",
                "engineering/researcher",
                "整理 Vendor Q 文件的 MLO 規格與限制",
                "整理 Vendor M 文件的 MLO 規格與限制",
                "… 執行中",
                "只讀",
            ):
                assert words in shown, (words, shown)
            # The two parallel read-only sub-agents sit side by side.
            tops = browser._evaluate(
                f'Array.from(document.querySelectorAll("{agents} li"))'
                ".map(node => Math.round(node.getBoundingClientRect().top))"
            )
            assert isinstance(tops, list) and tops[1] == tops[2], tops
            no_side_scroll()
            browser.screenshot(shots / "progress-light.png")
            dark(True)
            no_side_scroll()
            browser.screenshot(shots / "progress-dark.png")
            narrow(True)
            time.sleep(1.5)  # a poll redraws at the narrow width
            browser._evaluate(
                "document.querySelector('.turn-progress').scrollIntoView({block: 'center'})"
            )
            no_side_scroll()
            right = browser._evaluate(
                f'Math.max(...Array.from(document.querySelectorAll("{agents} li"))'
                ".map(node => node.getBoundingClientRect().right))"
            )
            assert isinstance(right, int | float) and right <= 390, right
            stacked = browser._evaluate(
                f'Array.from(document.querySelectorAll("{agents} li"))'
                ".map(node => Math.round(node.getBoundingClientRect().top))"
            )
            assert isinstance(stacked, list) and len(set(stacked)) == 3, stacked
            browser.screenshot(shots / "progress-narrow-dark.png")
            # The turn ends: the answer carries the closed 委派紀錄.
            release.set()
            record = ".delegation-record"
            wait(f"!!document.querySelector({json.dumps(record)})")
            assert browser._evaluate(f"document.querySelector({json.dumps(record)}).open") is False
            summary = str(
                browser._evaluate(f'document.querySelector("{record} > summary").innerText')
            )
            assert summary == "委派紀錄（3 個子代理）"
            height = browser._evaluate(
                f'document.querySelector("{record} > summary").getBoundingClientRect().height'
            )
            assert isinstance(height, int | float) and height >= 44, height
            browser._evaluate(f'document.querySelector("{record} > summary").click()')
            wait(f"document.querySelector({json.dumps(record)}).open")
            text = str(browser._evaluate(f"document.querySelector({json.dumps(record)}).innerText"))
            for words in (
                "engineering/coder@1.0.0",
                "parser 完成，6 筆、3 個 warning。",
                "tokens 1,200 / 300（2 次呼叫）",
                "需要：Vendor M 文件缺少第 4 章，要用哪一版？",
                "需要資訊",
                "compare.md",
            ):
                assert words in text, (words, text)
            browser._evaluate(
                f"document.querySelector({json.dumps(record)}).scrollIntoView({{block: 'center'}})"
            )
            no_side_scroll()
            browser.screenshot(shots / "record-narrow-dark.png")
            # The file chip opens the existing viewer.
            browser._evaluate(f'document.querySelector("{record} .file-chip").click()')
            wait('!document.getElementById("file-viewer").hidden')
            browser.screenshot(shots / "record-file-viewer-narrow-dark.png")
            browser._evaluate('document.getElementById("viewer-close").click()')
            narrow(False)
            dark(False)
            browser._evaluate(
                f"document.querySelector({json.dumps(record)}).scrollIntoView({{block: 'center'}})"
            )
            browser.screenshot(shots / "record-light.png")
            # Settings: the switch, off by default; turning it on is saved to
            # host.json and the card says a restart is still needed.
            browser._evaluate("document.getElementById('nav-settings').click()")
            result = "document.getElementById('multi-agent-result').textContent"
            wait(f"{result} === '已關閉（預設）。'")
            switch = "document.getElementById('multi-agent-enabled')"
            assert browser._evaluate(f"{switch}.checked") is False
            assert browser._evaluate(f"{switch}.disabled") is False
            dark(True)
            narrow(True)
            time.sleep(0.5)
            browser._evaluate(f"{switch}.click()")
            wait(f"{result}.includes('重新啟動 Agent Web 後生效')")
            assert browser._evaluate(f"{switch}.checked") is True
            assert json.loads(config_path.read_text(encoding="utf-8"))["multi_agent"] == {
                "enabled": True
            }
            browser._evaluate(
                "document.getElementById('multi-agent-heading').scrollIntoView({block: 'start'})"
            )
            no_side_scroll()
            browser.screenshot(shots / "settings-narrow-dark.png")
        finally:
            release.set()
            browser.close()
            browser.discard_profile()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


# -- end to end with the core's DelegationService ------------------------------------


def test_a_real_delegation_reports_its_own_line_and_tool_count() -> None:
    """The core sets the sub-agent's line as the sub-run's progress: its tool
    call counts on that line, the parent's own count stays untouched."""
    from test_delegation import agent_profile as profile
    from test_delegation import converse, delegate, reply, wired

    seen: list[dict[str, Any]] = []
    parent = TurnProgress(turn_id="t", session_id="conversation-1", owner="engineer")

    def hook(key: str, index: int) -> None:
        if key == "check the release" and index == 1:
            seen.append(parent.snapshot())  # after the sub-agent's tool call

    scripts = {
        "parent": [reply(delegate("check the release")), reply(text="子代理的結果如上。")],
        "check the release": [reply(("release__check", {})), reply(text="摘要\n- release ok")],
    }
    built, _, _, _ = wired(scripts, (profile(),), hook=hook)
    token = turn_progress.TURN_PROGRESS.set(parent)
    try:
        result = converse(built)
    finally:
        turn_progress.TURN_PROGRESS.reset(token)
    assert result.status == "answered"
    [during] = seen
    [line] = during["delegations"]
    assert line["profile"] == "engineering/researcher" and line["status"] == "running"
    assert line["objective"] == "check the release" and line["tool_count"] == 1
    assert during["delegations_running"] == 1
    after = parent.snapshot()
    assert [item["status"] for item in after["delegations"]] == ["done"]
    assert "delegations_running" not in after
    assert [tool["name"] for tool in after["tools"]] == [DELEGATE_TOOL]
