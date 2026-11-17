"""Agent Web: "run X" in the chat answers with the Workflow's inline run form
(owner 2026-10-15); see docs/phases/CHAT_WORKFLOW_FORMS.md."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from test_chat_workflow_forms import RELEASE_SETTINGS, _plain

from capabilities.release_package.manifest import release_workflow
from common.assets import WorkflowManifest

# -- Agent Web ----------------------------------------------------------------


@pytest.fixture
def web(tmp_path: Path) -> Any:
    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb

    config, layout = _chat_config(tmp_path)
    transport = _ChatGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        for manifest in (release_workflow(), _plain("nightly-check"), _form_workflow()):
            runtime.agent.gateway.engine.workflows.register(manifest)
            (runtime.layout.workflows / f"{manifest.metadata.identity.name}.json").write_text(
                manifest.model_dump_json(), encoding="utf-8"
            )
        yield AgentWeb(runtime), runtime, transport


def _form_workflow() -> WorkflowManifest:
    return _plain(
        "forms-chat",
        [
            {
                "name": "company",
                "label": "Company",
                "kind": "text",
                "group": "identity",
                "required": True,
            },
            {
                "name": "chipset",
                "label": "Chipset",
                "kind": "select",
                "allow_other": True,
                "choices": [{"value": "kt326"}, {"value": "kt400"}],
            },
            {
                "name": "mode",
                "label": "Mode",
                "kind": "select",
                "required": True,
                "choices": [{"value": "quick"}, {"value": "deep"}],
            },
            {"name": "dryRun", "label": "Dry run", "kind": "boolean", "default": True},
        ],
    )


def _turn(web: Any, session: str, message: str) -> dict[str, Any]:
    from host_runtime.conversations import ConversationTurnRequest

    return dict(web.conversation_turn(ConversationTurnRequest(session_id=session, message=message)))


def test_web_answers_run_x_with_the_form_and_never_asks_the_model(web: Any) -> None:
    agent_web, _runtime, transport = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    replied = _turn(agent_web, session, "我要執行rs-wmt-package-release")
    form = replied["answer"]["workflow_form"]
    assert form["workflow"]["name"] == "rs-wmt-package-release"
    # No settings on this computer yet: named, and not asked in the chat.
    assert {"release_repo_url", "work_root", "inbox_path", "allowed_root"} <= {
        item["name"] for item in form["missing_settings"]
    }
    stored = replied["conversation"]["messages"][-1]
    assert stored["workflow_form"]["workflow"]["name"] == "rs-wmt-package-release"
    assert "settings page" in stored["text"]
    assert transport.calls == []  # the model was never asked


def test_web_prefill_settings_and_a_workflow_without_parameters(web: Any) -> None:
    from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore

    agent_web, runtime, _ = web
    WorkflowSettingsStore(runtime.layout.workspace_root / SETTINGS_FILE).save(
        release_workflow().metadata.identity, RELEASE_SETTINGS
    )
    session = agent_web.create_conversation()["conversation"]["session_id"]
    form = _turn(
        agent_web, session, "執行 rs-wmt-package-release companyName=Foxconn chipsetId=kt326"
    )["answer"]["workflow_form"]
    assert form["missing_settings"] == []
    assert form["prefill"] == {"companyName": "Foxconn", "chipsetId": "kt326"}
    plain = _turn(agent_web, session, "run nightly-check")["answer"]["workflow_form"]
    assert plain["workflow"]["name"] == "nightly-check" and plain["prefill"] == {}
    slash = _turn(agent_web, session, "/run forms-chat")["answer"]["workflow_form"]
    assert slash["workflow"]["name"] == "forms-chat"
    unknown = _turn(agent_web, session, "/run not-installed")["answer"]
    assert "workflow_form" not in unknown and "No single installed" in unknown["answer"]


def test_web_reads_plain_values_from_the_request_as_telegram_does(web: Any) -> None:
    """Owner 2026-10-25: a value named in the request is filled in, the same
    shared reading as Telegram's flow (common/run_prefill.py)."""
    agent_web, _runtime, transport = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    form = _turn(agent_web, session, "幫我執行 forms-chat deep")["answer"]["workflow_form"]
    assert form["prefill"] == {"mode": "deep"}
    assert "already gave are filled in" in form["message"]
    unclear = _turn(agent_web, session, "run forms-chat quick deep")["answer"]["workflow_form"]
    assert unclear["prefill"] == {}  # two choices named: nothing is guessed
    assert transport.calls == []


def test_a_run_from_the_chat_form_is_added_to_the_conversation(web: Any) -> None:
    from host_runtime.contracts import WorkflowLaunchRequest

    agent_web, runtime, _ = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    _turn(agent_web, session, "run forms-chat")
    launched = agent_web.launch_workflow(
        WorkflowLaunchRequest(
            workflow=_form_workflow().metadata.identity,
            arguments={"company": "Foxconn", "mode": "quick"},
            idempotency_key="chat-form-1",
            session_id=session,
        )
    )
    assert launched["message"]["role"] == "assistant"
    messages = runtime.state.conversation(session, runtime.actor).messages
    assert messages[-2].text.startswith('▶ Run forms-chat from the form: company="Foxconn"')
    assert messages[-1].text == launched["answer"]


# -- the inline form in a real browser ----------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_inline_chat_form_renders_and_runs_in_a_real_browser(tmp_path: Path) -> None:
    """ "Run X" in the chat draws the Workflow's own form under the answer
    (prefilled, measured), Run records the run in the conversation, and a
    Workflow with a missing setting points to its settings instead."""
    import threading
    import time

    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb, AgentWebServer
    from integrations.browser import Browser

    config, layout = _chat_config(tmp_path)
    needs = _plain(
        "needs-settings",
        [
            {
                "name": "inbox_path",
                "label": "Input inbox",
                "kind": "folder",
                "scope": "static",
                "required": True,
            },
            {"name": "company", "label": "Company", "kind": "text"},
        ],
    )
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        for manifest in (_form_workflow(), needs):
            runtime.agent.gateway.engine.workflows.register(manifest)
            (runtime.layout.workflows / f"{manifest.metadata.identity.name}.json").write_text(
                manifest.model_dump_json(), encoding="utf-8"
            )
        served = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def wait(expression: str, seconds: float = 30) -> object:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                value = browser._evaluate(expression)
                if value:
                    return value
                time.sleep(0.2)
            raise AssertionError(expression)

        def measure(selector: str) -> list[int]:
            size: list[int] = json.loads(
                str(
                    browser._evaluate(
                        "JSON.stringify((() => { const r = document.querySelector("
                        + json.dumps(selector)
                        + ").getBoundingClientRect();"
                        " return [Math.round(r.width), Math.round(r.height)]; })())"
                    )
                )
            )
            return size

        def ask(message: str) -> None:
            browser._evaluate(
                "(() => { const f = document.getElementById('message'); f.value = "
                + json.dumps(message)
                + "; document.getElementById('ask').requestSubmit(); })()"
            )

        try:
            browser.navigate(served.address)
            wait('!document.getElementById("send").disabled')
            ask("我要執行 forms-chat company=Foxconn")
            wait('!!document.querySelector(".chat-run-form[open] input[id$=\\"-company\\"]")')
            width, height = measure(".chat-run-form[open]")
            assert width >= 280 and height >= 250, (width, height)
            run_width, run_height = measure(".chat-run-form[open] .chat-run-actions button")
            assert run_width >= 44 and run_height >= 44, (run_width, run_height)
            print(f"chat run form {width}x{height}, Run {run_width}x{run_height}")
            shots = os.environ.get("AEP_UI_SHOTS")
            if shots:
                browser.screenshot(Path(shots) / "chat-run-form.png")
            assert (
                browser._evaluate(
                    'document.querySelector(".chat-run-form[open] input[id$=\\"-company\\"]").value'
                )
                == "Foxconn"
            )
            assert browser._evaluate(
                'document.querySelector(".chat-run-form[open] input[list]") !== null'
            )
            # The given value is named; optional fields nobody gave are folded away.
            assert (
                browser._evaluate(
                    'document.querySelector(".chat-run-form[open] .chat-run-given").innerText'
                )
                == "已從你的訊息帶入：Company = Foxconn"
            )
            assert (
                browser._evaluate(
                    'document.querySelector(".chat-run-form[open] .optional-fields > summary")'
                    ".innerText"
                )
                == "其他選項（使用預設值）"
            )
            assert browser._evaluate(
                '!document.querySelector(".chat-run-form[open] .optional-fields").open'
                ' && !!document.querySelector(".chat-run-form[open] .optional-fields'
                ' input[id$=\\"-chipset\\"]")'
                ' && !document.querySelector(".chat-run-form[open] .optional-fields'
                ' [id$=\\"-mode\\"]")'
            )
            assert not browser._evaluate(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )
            browser._evaluate(
                "(() => { const s = document.querySelector("
                '".chat-run-form[open] select[id$=\\"-mode\\"]"); s.value = "deep"; '
                's.dispatchEvent(new Event("change")); })()'
            )
            browser._evaluate(
                'document.querySelector(".chat-run-form[open] .chat-run-actions button").click()'
            )
            wait(
                'document.getElementById("log").innerText.includes("Run forms-chat from the form")',
                60,
            )
            # Only the newest answer's form is open; the run's own answer has none.
            assert browser._evaluate('document.querySelectorAll(".chat-run-form").length') == 1

            ask("run needs-settings")
            wait('!!document.querySelector(".chat-run-form[open] .chat-run-missing")')
            assert "Input inbox" in str(
                browser._evaluate(
                    'document.querySelector(".chat-run-form[open] .chat-run-missing").innerText'
                )
            )
            assert (
                browser._evaluate(
                    'document.querySelector(".chat-run-form[open] .chat-run-actions button")'
                    ".disabled"
                )
                is True
            )
            browser._evaluate(
                'document.querySelector(".chat-run-form[open] .chat-run-missing button").click()'
            )
            wait('document.getElementById("panel-installed").hasAttribute("data-open")')
            wait(
                'document.getElementById("capability-detail-content").innerText'
                '.includes("needs-settings")'
            )
        finally:
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
@pytest.mark.parametrize("succeeds", [True, False])
@pytest.mark.parametrize("reload_document", [True, False])
def test_running_form_survives_navigation_and_reload_in_browser(
    tmp_path: Path, succeeds: bool, reload_document: bool
) -> None:
    import asyncio
    import threading
    import time

    from test_conversation_turn_groups import _chat_config, _ChatGateway
    from test_workflow_harness import SPEC, In, Out, engine_with

    from capabilities.runtime import CapabilityGrant, CapabilityRefused
    from common.assets import ExecutionDependencies
    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb, AgentWebServer
    from integrations.browser import Browser

    config, layout = _chat_config(tmp_path)
    entered, release = threading.Event(), threading.Event()
    calls: list[Any] = []
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        _, template = engine_with([])
        data = template.model_dump(mode="json")
        data["metadata"]["identity"]["name"] = "forms-chat"
        data["parameters"] = _form_workflow().model_dump(mode="json")["parameters"]
        data["steps"][0]["inputs"] = {}
        manifest = WorkflowManifest.model_validate(data)

        async def slow(context: Any, inputs: Any) -> Any:
            calls.append(context)
            entered.set()
            assert await asyncio.to_thread(release.wait, 30)
            if not succeeds:
                raise CapabilityRefused("stub_failed")
            return Out(files=[])

        bridge = runtime.agent.gateway.bridge
        bridge.installed.register(
            SPEC, slow, In, Out, ExecutionDependencies(central_required=False)
        )
        bridge.policy.add(
            CapabilityGrant(
                actor=runtime.actor,
                asset=SPEC.identity,
                permissions=("lab.make",),
                policy_refs=("p",),
            )
        )
        runtime.agent.gateway.engine.workflows.register(manifest)
        (layout.workflows / "slow.json").write_text(manifest.model_dump_json(), encoding="utf-8")
        agent_web = AgentWeb(runtime)
        session = agent_web.create_conversation()["conversation"]["session_id"]
        _turn(agent_web, session, "run forms-chat company=Fictional mode=quick")
        served = AgentWebServer(agent_web)
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=45)
        browser.start()

        def wait(expression: str) -> None:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if browser._evaluate(expression):
                    return
                time.sleep(0.1)
            raise AssertionError(expression)

        try:
            browser.navigate(served.address)
            wait('!!document.querySelector(".chat-run-actions button")')
            browser._evaluate("""(() => {
              const box = document.querySelector('.chat-run-form input[id$=-company]');
              box.value = 'Changed on form';
              document.querySelector('.chat-run-form select[id$=-mode]').value = 'deep';
            })()""")
            if not reload_document:
                browser._evaluate("""(() => {
                  const original = window.fetch;
                  window.fetch = async (...args) => {
                    const response = await original(...args);
                    if (args[0] === '/api/workflows/run') throw new Error('lost response');
                    return response;
                  };
                })()""")
            browser._evaluate('document.querySelector(".chat-run-actions button").click()')
            assert entered.wait(10)
            browser._evaluate('selectPrimaryTab("tasks")')
            wait('document.getElementById("panel-tasks").hasAttribute("data-open")')
            browser._evaluate(
                'selectPrimaryTab("ask"); loadConversations(' + json.dumps(session) + ")"
            )
            wait('document.getElementById("log").innerText.includes("Workflow 執行中")')
            assert (
                browser._evaluate('document.querySelectorAll(".chat-run-actions button").length')
                == 0
            )
            # A full document reload also drops the original fetch/DOM, never the host work.
            if reload_document:
                browser.navigate(served.address)
                wait('document.getElementById("log").innerText.includes("Workflow 執行中")')
            assert len(calls) == 1
            release.set()
            label = "已完成" if succeeds else "執行失敗"
            wait(
                'document.querySelector(".chat-run-form summary").textContent.includes('
                + json.dumps(label)
                + ")"
            )
            browser._evaluate('document.querySelector(".chat-run-form").open = true')
            if succeeds:
                wait('document.querySelector(".chat-run-result").textContent.includes("已完成")')
                assert (
                    browser._evaluate(
                        'document.querySelectorAll(".chat-run-actions button").length'
                    )
                    == 0
                )
            else:
                wait('!!document.querySelector(".chat-run-actions button")')
                assert (
                    browser._evaluate(
                        'document.querySelector(".chat-run-actions button").textContent'
                    )
                    == "重試 Workflow"
                )
                assert (
                    browser._evaluate(
                        'document.querySelector(".chat-run-form input[id$=-company]").value'
                    )
                    == "Changed on form"
                )
                assert (
                    browser._evaluate(
                        'document.querySelector(".chat-run-form select[id$=-mode]").value'
                    )
                    == "deep"
                )

            assert len(calls) == 1
        finally:
            release.set()
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_running_form_poll_keeps_another_forms_draft_and_focus(web: Any, tmp_path: Path) -> None:
    import threading
    import time

    from host_runtime.web import AgentWebServer
    from integrations.browser import Browser

    agent_web, runtime, _ = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    first = _turn(agent_web, session, "run forms-chat")["conversation"]["messages"][-1]
    runtime.state.set_workflow_form_run(
        session,
        runtime.actor,
        first["message_id"],
        {"status": "running", "key": "blocked-attempt", "owner": agent_web._workflow_form_owner},
    )
    _turn(agent_web, session, "run forms-chat")
    served = AgentWebServer(agent_web)
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    browser = Browser(tmp_path / "poll-browser", timeout_s=30)
    browser.start()

    def wait(expression: str) -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if browser._evaluate(expression):
                return
            time.sleep(0.1)
        raise AssertionError(expression)

    try:
        browser.navigate(served.address)
        wait('document.querySelectorAll(".chat-run-form input[id$=\\"-company\\"]").length === 1')
        browser._evaluate("""(() => {
          const input = document.querySelector('.chat-run-form input[id$=-company]');
          input.value = 'Unsubmitted draft'; input.focus(); input.setSelectionRange(4, 8);
          document.querySelector('.chat-run-form select[id$=-mode]').value = 'deep';
          window.formPolls = 0;
          const original = window.fetch;
          window.fetch = async (...args) => {
            const response = await original(...args);
            if (String(args[0]).startsWith('/api/conversations?')) window.formPolls += 1;
            return response;
          };
        })()""")
        wait("window.formPolls >= 2")
        assert (
            browser._evaluate(
                'document.querySelector(".chat-run-form input[id$=\\"-company\\"]").value'
            )
            == "Unsubmitted draft"
        )
        assert (
            browser._evaluate(
                'document.querySelector(".chat-run-form select[id$=\\"-mode\\"]").value'
            )
            == "deep"
        )
        assert browser._evaluate(
            'document.activeElement.matches(".chat-run-form input[id$=-company]")'
            " && document.activeElement.selectionStart === 4"
            " && document.activeElement.selectionEnd === 8"
        )
    finally:
        browser.close()
        browser.discard_profile()
        served.shutdown()
        served.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_failed_form_reuses_uploaded_files_without_resetting_file_input(
    web: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    import threading
    import time

    from host_runtime.web import AgentWebServer
    from integrations.browser import Browser

    agent_web, runtime, _ = web
    manifest = _plain(
        "upload-retry",
        [
            {
                "name": "packages",
                "label": "Packages",
                "kind": "upload",
                "accept": [".json"],
                "multiple": True,
                "required": True,
            }
        ],
    )
    runtime.agent.gateway.engine.workflows.register(manifest)
    (runtime.layout.workflows / "upload-retry.json").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    first = agent_web.upload_workflow_file(
        manifest.metadata.identity, "packages", "", "one.json", b"{}"
    )
    second = agent_web.upload_workflow_file(
        manifest.metadata.identity, "packages", first["upload_set"], "two.json", b"{}"
    )
    assert first["ok"] and second["ok"]
    paths = [first["path"], second["path"]]
    session = agent_web.create_conversation()["conversation"]["session_id"]
    offer = _turn(agent_web, session, "run upload-retry")["conversation"]["messages"][-1]
    runtime.state.set_workflow_form_run(
        session,
        runtime.actor,
        offer["message_id"],
        {
            "status": "failed",
            "key": "old-upload-attempt",
            "owner": agent_web._workflow_form_owner,
            "arguments": {"packages": paths},
            "answer": "stub failed",
        },
    )
    received: list[Any] = []

    def execute(request: Any) -> dict[str, Any]:
        received.append(request)
        return {"ok": False, "answer": "stub failed"}

    monkeypatch.setattr(agent_web, "_execute_workflow_launch", execute)
    served = AgentWebServer(agent_web)
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    browser = Browser(tmp_path / "uploads-browser", timeout_s=30)
    browser.start()

    def wait(expression: str) -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if browser._evaluate(expression):
                return
            time.sleep(0.1)
        raise AssertionError(expression)

    try:
        browser.navigate(served.address)
        wait('!!document.querySelector(".chat-run-form input[type=file]")')
        restored = browser._evaluate(
            'document.querySelector(".chat-run-form input[type=file]").dataset.paths'
        )
        assert json.loads(str(restored)) == paths
        assert (
            browser._evaluate('document.querySelector(".chat-run-form input[type=file]").value')
            == ""
        )
        assert "one.json" in str(
            browser._evaluate('document.querySelector(".chat-run-form").innerText')
        )
        assert "two.json" in str(
            browser._evaluate('document.querySelector(".chat-run-form").innerText')
        )
        browser._evaluate('document.querySelector(".chat-run-actions button").click()')
        wait(
            'document.querySelector(".chat-run-form").innerText.includes("stub failed")'
            ' && !!document.querySelector(".chat-run-actions button")'
            ' && !document.querySelector(".chat-run-actions button").disabled'
        )
        assert len(received) == 1
        assert received[0].arguments == {"packages": paths}
        assert received[0].retry_of == "old-upload-attempt"
    finally:
        browser.close()
        browser.discard_profile()
        served.shutdown()
        served.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
@pytest.mark.parametrize("reject_mode", ["network", "parameters", "network_state"])
def test_unclaimed_form_can_be_started_after_a_rejected_request(
    web: Any, tmp_path: Path, monkeypatch: Any, reject_mode: str
) -> None:
    import threading
    import time

    from common.workflow_parameters import WorkflowParameterError
    from host_runtime.web import AgentWebServer
    from integrations.browser import Browser

    agent_web, _, _ = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    _turn(agent_web, session, "run forms-chat company=Fictional mode=quick")
    received: list[Any] = []

    def execute(request: Any) -> dict[str, Any]:
        received.append(request)
        return {"ok": False, "answer": "stub failed"}

    monkeypatch.setattr(agent_web, "_execute_workflow_launch", execute)
    original = agent_web.launch_workflow
    rejected = False

    def launch(request: Any) -> dict[str, Any]:
        nonlocal rejected
        if reject_mode == "parameters" and not rejected:
            rejected = True
            raise WorkflowParameterError("synthetic parameter rejection")
        return dict(original(request))

    monkeypatch.setattr(agent_web, "launch_workflow", launch)
    served = AgentWebServer(agent_web)
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    browser = Browser(tmp_path / "rejected-browser", timeout_s=30)
    browser.start()

    def wait(expression: str) -> None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if browser._evaluate(expression):
                return
            time.sleep(0.1)
        raise AssertionError(expression)

    try:
        browser.navigate(served.address)
        wait('!!document.querySelector(".chat-run-actions button")')
        if reject_mode.startswith("network"):
            browser._evaluate("""(() => {
              const original = window.fetch;
              let rejected = false;
              window.statusReads = 0;
              window.fetch = async (...args) => {
                if (args[0] === '/api/workflows/run' && !rejected) {
                  rejected = true; throw new Error('synthetic offline');
                }
                if (rejected && String(args[0]).startsWith('/api/conversations?')) {
                  window.statusReads += 1;
                  if (window.failStatusRead && window.statusReads === 1) {
                    throw new Error('synthetic status offline');
                  }
                }
                return original(...args);
              };
            })()""")
            browser._evaluate(
                "window.failStatusRead = " + json.dumps(reject_mode == "network_state")
            )
        browser._evaluate('document.querySelector(".chat-run-actions button").click()')
        if reject_mode == "network_state":
            wait('document.querySelector(".chat-run-result").textContent.includes("連線中斷")')
            browser._evaluate("loadConversations(" + json.dumps(session) + ")")
            wait(
                'document.querySelector(".chat-run-result").textContent.includes("已確認主機尚無")'
            )
            assert browser._evaluate("window.statusReads >= 2")
        else:
            wait('document.querySelector(".chat-run-result").textContent.includes("synthetic")')
        assert browser._evaluate('!document.querySelector(".chat-run-actions button").disabled')
        assert received == []
        assert (
            browser._evaluate('document.querySelector(".chat-run-form input[id$=-company]").value')
            == "Fictional"
        )
        browser._evaluate('document.querySelector(".chat-run-actions button").click()')
        wait('document.querySelector(".chat-run-form summary").textContent.includes("執行失敗")')
        assert len(received) == 1
        assert received[0].arguments["company"] == "Fictional"
    finally:
        browser.close()
        browser.discard_profile()
        served.shutdown()
        served.server_close()
        thread.join(timeout=5)
