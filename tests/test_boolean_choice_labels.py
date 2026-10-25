"""A yes/no input says what each choice does (owner, Telegram, 2026-10-25).

「Dry run: show the plan only … Default: False」 with buttons Yes / No: 「這個yes,
和No讓人很confused, 是要dry run 還是不要呀」, and a card line 「Dry run：否」 was
no clearer. A boolean's two choices now come from the declaration
(`true_label` / `false_label`), else the label and 「不要：<label>」, on the
Telegram buttons, the confirmation card, typed answers and edits, the Agent
tool schema and the Agent Web run form (two labelled radio options).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_chat_workflow_forms import _plain
from test_workflow_parameter_declaration import _manifest

from capabilities.loan_reply.manifest import reply_workflow, scan_workflow
from capabilities.ncc_plan.manifest import plan_workflow
from capabilities.release_package.manifest import prepare_workflow, release_workflow
from capabilities.weekly_report.manifest import weekly_report_workflow
from channels import telegram_flow as flow
from common.assets import WorkflowManifest, WorkflowParameter
from common.workflow_forms import (
    agent_tool_schema,
    boolean_from_label,
    boolean_labels,
    form_field,
)
from common.workflow_run_form import prefill_from_text

DRY = "只看計畫（不寫入、不寄信）"
REAL = "正式執行（寫入週報、起草郵件）"


def _switch(**extra: Any) -> WorkflowParameter:
    return WorkflowParameter.model_validate(
        {"name": "dry_run", "label": "只試跑？", "kind": "boolean", **extra}
    )


def _text(step: flow.FlowStep) -> str:
    assert step.prompt is not None
    return step.prompt.text


def _weekly_flow() -> flow.FlowState:
    state = flow.start(weekly_report_workflow(), "write", prefill={"week": "2026_43W"})
    assert isinstance(state, flow.FlowState)
    return state


# -- the declaration ----------------------------------------------------------------


def test_labels_come_from_the_declaration_or_are_derived_from_the_label() -> None:
    declared = _switch(true_label="只看計畫", false_label="正式執行")
    assert boolean_labels(declared) == ("只看計畫", "正式執行")
    # Derived: the label without its question mark, and 「不要：<label>」.
    assert boolean_labels(_switch()) == ("只試跑", "不要：只試跑")
    assert boolean_labels(_switch(true_label="只看計畫")) == ("只看計畫", "不要：只試跑")
    # Every generated form reads the two choices from the same field data.
    assert form_field(declared)["true_label"] == "只看計畫"
    assert form_field(_switch())["false_label"] == "不要：只試跑"
    assert "true_label" not in form_field(WorkflowParameter(name="week", label="Week", kind="text"))


def test_the_new_fields_are_optional_checked_and_keep_older_manifest_bytes() -> None:
    plain = _switch()
    assert "true_label" not in plain.model_dump(mode="json")
    assert "false_label" not in plain.model_dump(mode="json")
    labelled = _switch(true_label="只看計畫", false_label="正式執行")
    assert labelled.model_dump(mode="json")["true_label"] == "只看計畫"
    with pytest.raises(ValidationError, match="only boolean parameters"):
        WorkflowParameter.model_validate(
            {"name": "week", "label": "Week", "kind": "text", "true_label": "x"}
        )
    with pytest.raises(ValidationError, match="must differ"):
        _switch(true_label="Go", false_label="go ")
    with pytest.raises(ValidationError):
        _switch(true_label="  ")


@pytest.mark.parametrize(
    "manifest",
    [
        weekly_report_workflow(),
        scan_workflow(),
        reply_workflow(),
        plan_workflow(),
        release_workflow(),
        prepare_workflow(),
    ],
    ids=lambda manifest: manifest.metadata.identity.name,
)
def test_every_bundled_boolean_says_what_each_choice_does(manifest: WorkflowManifest) -> None:
    switches = [item for item in manifest.parameters if item.kind == "boolean"]
    assert switches
    for item in switches:
        assert item.true_label and item.false_label, item.name
    # The manifest survives its own round trip with the new fields.
    again = WorkflowManifest.model_validate(manifest.model_dump(mode="json"))
    assert again == manifest


def test_the_weekly_report_dry_run_is_the_run_mode() -> None:
    dry_run = next(item for item in weekly_report_workflow().parameters if item.name == "dry_run")
    assert dry_run.label == "執行方式"
    assert boolean_labels(dry_run) == (DRY, REAL)


def test_a_choice_is_read_from_its_words() -> None:
    dry_run = next(item for item in weekly_report_workflow().parameters if item.name == "dry_run")
    assert boolean_from_label(dry_run, DRY) is True
    assert boolean_from_label(dry_run, "只看計畫") is True  # the head before 「（」
    assert boolean_from_label(dry_run, "正式執行吧") is False
    assert boolean_from_label(dry_run, "正式") is False  # the start of one choice only
    assert boolean_from_label(dry_run, "隨便") is None
    assert boolean_from_label(dry_run, "只") is None  # too short to tell
    assert boolean_from_label(_switch(), "不要：只試跑") is False


def test_the_agent_tool_schema_names_both_choices() -> None:
    schema = agent_tool_schema(weekly_report_workflow())
    description = schema["properties"]["dry_run"]["description"]
    assert f"true: {DRY}" in description and f"false: {REAL}" in description


def test_a_run_request_may_name_the_choice() -> None:
    given = prefill_from_text(weekly_report_workflow(), "run sde-weekly-report dry_run=只看計畫")
    assert given["dry_run"] is True
    given = prefill_from_text(weekly_report_workflow(), "run sde-weekly-report dry_run=正式執行")
    assert given["dry_run"] is False


# -- Telegram -----------------------------------------------------------------------


def test_the_card_shows_each_switch_by_what_it_does() -> None:
    text = _text(flow.begin(_weekly_flow()))
    assert f"- 執行方式：{REAL}（預設）" in text
    assert (
        "- Save the weekly mail draft：Save the mail as an Outlook draft (never sent)（預設）"
        in (text)
    )
    assert "：是" not in text and "：否" not in text
    assert "「改成只看計畫」" in text  # the example is the other choice, in its words


def test_the_switch_buttons_say_what_each_choice_does() -> None:
    state = _weekly_flow()
    flow.begin(state)
    flow.answer(state, "修改")
    position = [item.name for item in state.fields].index("dry_run")
    asked = flow.answer(state, f"edit:{position}")
    assert asked.prompt is not None
    assert asked.prompt.buttons == [[(DRY, "yes")], [(REAL, "no")]]
    assert "Yes" not in json.dumps(asked.prompt.buttons, ensure_ascii=False)
    assert f"Default: {REAL}" in asked.prompt.text
    card = flow.answer(state, "yes")  # the button's data is unchanged
    assert f"- 執行方式：{DRY}\n" in _text(card)


@pytest.mark.parametrize(
    ("said", "dry"),
    [
        ("只看計畫", True),
        (DRY, True),
        ("改成只看計畫", True),
        ("執行方式 改成只看計畫", True),
        ("dry run 改成是", True),
        ("Dry run 是", True),
    ],
)
def test_a_typed_edit_may_use_the_choice_words(said: str, dry: bool) -> None:
    state = _weekly_flow()
    flow.begin(state)
    changed = _text(flow.answer(state, said))
    assert f"已改：執行方式 = {DRY}" in changed
    assert state.answers["dry_run"] is dry
    back = _text(flow.answer(state, "改成正式執行"))
    assert f"- 執行方式：{REAL}\n" in back and state.answers["dry_run"] is False


def test_a_typed_answer_to_the_question_may_use_the_choice_words() -> None:
    fields = [
        {
            "name": "dry_run",
            "label": "執行方式",
            "kind": "boolean",
            "required": True,
            "true_label": DRY,
            "false_label": REAL,
        }
    ]
    for said, expected in (("只看計畫", True), ("正式執行", False), ("是", True), ("no", False)):
        state = flow.start(_manifest(fields), "write")
        assert isinstance(state, flow.FlowState)
        flow.begin(state)
        flow.answer(state, said)
        assert state.answers == {"dry_run": expected}, said
    state = flow.start(_manifest(fields), "write")
    assert isinstance(state, flow.FlowState)
    flow.begin(state)
    assert f"choose 「{DRY}」 or 「{REAL}」" in _text(flow.answer(state, "maybe"))


def test_a_switch_without_declared_choices_is_never_a_bare_yes_or_no() -> None:
    fields = [{"name": "go", "label": "Send the report?", "kind": "boolean", "default": False}]
    state = flow.start(_manifest(fields), "write")
    assert isinstance(state, flow.FlowState)
    text = _text(flow.begin(state))
    assert "- Send the report?：不要：Send the report（預設）" in text
    assert "已改：Send the report\n" in _text(flow.answer(state, "send the report"))
    assert state.answers == {"go": True}


# -- Agent Web: two labelled radio options --------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_web_run_form_shows_a_switch_as_two_labelled_choices(tmp_path: Path) -> None:
    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb, AgentWebServer
    from integrations.browser import Browser

    config, layout = _chat_config(tmp_path)
    workflow = _plain(
        "switch-chat",
        [
            {
                "name": "dry_run",
                "label": "執行方式",
                "kind": "boolean",
                "default": False,
                "true_label": DRY,
                "false_label": REAL,
                "help": "Plan the week and show it.",
            },
            {"name": "notify", "label": "通知我？", "kind": "boolean", "default": True},
        ],
    )
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        runtime.agent.gateway.engine.workflows.register(workflow)
        (runtime.layout.workflows / "switch-chat.json").write_text(
            workflow.model_dump_json(), encoding="utf-8"
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

        def evaluate(expression: str) -> Any:
            return json.loads(str(browser._evaluate(f"JSON.stringify({expression})")))

        form = ".chat-run-form[open] "
        try:
            browser.navigate(served.address)
            wait('!document.getElementById("send").disabled')
            browser._evaluate(
                "(() => { const f = document.getElementById('message'); f.value = "
                + json.dumps("執行 switch-chat dry_run=只看計畫")
                + "; document.getElementById('ask').requestSubmit(); })()"
            )
            wait(f"!!document.querySelector({json.dumps(form + '[id$=-dry_run-choices]')})")
            # The value given in words is named in words, not 是/否.
            given = evaluate(f'document.querySelector("{form}.chat-run-given").innerText')
            assert given == f"已從你的訊息帶入：執行方式 = {DRY}"
            choices = evaluate(
                f'[...document.querySelectorAll("{form}[id$=-dry_run-choices] label")]'
                ".map(l => [l.innerText.trim(), l.querySelector('input').type,"
                " l.querySelector('input').checked])"
            )
            assert choices == [[DRY, "radio", True], [REAL, "radio", False]]
            group = evaluate(
                f'(() => {{ const g = document.querySelector("{form}[id$=-dry_run-choices]");'
                " return [g.getAttribute('role'),"
                " document.getElementById(g.getAttribute('aria-labelledby')).innerText]; })()"
            )
            assert group == ["radiogroup", "執行方式"]
            # No visible checkbox whose meaning depends on reading the help.
            assert evaluate(
                f'[...document.querySelectorAll("{form}input[type=checkbox]")]'
                ".every(box => box.hidden && box.offsetParent === null)"
            )
            # A switch without declared choices (folded: optional, nobody gave it):
            # its label and 「不要：<label>」.
            derived = evaluate(
                f'[...document.querySelectorAll("{form}[id$=-notify-choices] label")]'
                ".map(l => [l.textContent.trim(), l.querySelector('input').checked])"
            )
            assert derived == [["通知我", True], ["不要：通知我", False]]
            # Choosing the other option is what the run receives.
            browser._evaluate(f'document.querySelector("{form}input[id$=-dry_run-false]").click()')
            assert evaluate(f'document.querySelector("{form}input[id$=-dry_run]").checked') is (
                False
            )
            browser._evaluate(f'document.querySelector("{form}.chat-run-actions button").click()')
            wait(
                'document.getElementById("log").innerText'
                '.includes("Run switch-chat from the form: dry_run=false")',
                60,
            )
        finally:
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)
