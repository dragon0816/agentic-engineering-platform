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
            return json.loads(
                str(
                    browser._evaluate(
                        "JSON.stringify((() => { const r = document.querySelector("
                        + json.dumps(selector)
                        + ").getBoundingClientRect();"
                        " return [Math.round(r.width), Math.round(r.height)]; })())"
                    )
                )
            )

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
