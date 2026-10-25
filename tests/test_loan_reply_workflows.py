"""rs_workflow_system 06 / 06b (loan replies) as two AEP Workflows.

Through the real host: Workflow engine, Bridge policy with grants, the
generated forms and the queue in the host workspace. Outlook, the loan portal
and C4C are `tests/loan_fakes.FakeLoanHost`; nothing reads a real mailbox,
opens a real portal, saves a real draft or sends anything. The source jobs'
own tests run against the same code as tests/test_loan_*_source.py.
"""

from __future__ import annotations

import asyncio
import json
import time
import types
from pathlib import Path
from typing import Any

import pytest
from loan_fakes import FORM_URL, FakeLoanHost, notice
from test_host_wiring import membership_record, workspace

from capabilities.loan_reply import process, queue
from capabilities.loan_reply.handlers import queue_root, trusted_link
from capabilities.loan_reply.manifest import (
    DRAFT_SPEC,
    ENQUEUE_SPEC,
    LOOK_UP_SPEC,
    OFFER_SPEC,
    REPLY_WORKFLOW,
    SCAN_SPEC,
    SCAN_WORKFLOW,
    SEND_SPEC,
    loan_skill,
    reply_workflow,
    scan_workflow,
)
from channels import telegram_flow as flow
from common.execution import TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from common.workflow_forms import agent_tool_schema, form_fields, settings_fields
from host_runtime.host import build_runtime
from host_runtime.loan_reply_cards import LoanReplyCards
from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore

SPECS = (SCAN_SPEC, ENQUEUE_SPEC, LOOK_UP_SPEC, DRAFT_SPEC, OFFER_SPEC)
SCAN_SETTINGS: dict[str, Any] = {"process_from": "2026-01-01 00:00"}
REPLY_SETTINGS: dict[str, Any] = {"alert_recipient": ["ops@example.com"], "settle_ms": 0}


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """The job waits for real pages between steps; the fakes answer at once."""
    clock = types.SimpleNamespace(sleep=lambda *_a: None, monotonic=time.monotonic)
    monkeypatch.setattr(process, "time", clock)


def _grants() -> list[dict[str, Any]]:
    return [
        {
            "actor": "engineer",
            "asset": spec.identity.model_dump(),
            "permissions": list(spec.policy.required_permissions),
            "policy_refs": ["loan-reply-policy"],
            "approval_ref": "loan-approval",
        }
        for spec in SPECS
    ]


class Host:
    def __init__(
        self,
        tmp_path: Path,
        fake: FakeLoanHost,
        *,
        scan_settings: dict[str, Any] | None = None,
        reply_settings: dict[str, Any] | None = None,
    ) -> None:
        self.fake = fake
        self.config, layout = workspace(
            tmp_path / "host", membership=membership_record(), grants=_grants()
        )
        (layout.workflows / "loan-scan.json").write_text(
            scan_workflow().model_dump_json(), encoding="utf-8"
        )
        (layout.workflows / "loan-reply.json").write_text(
            reply_workflow().model_dump_json(), encoding="utf-8"
        )
        store = WorkflowSettingsStore(layout.workspace_root / SETTINGS_FILE)
        store.save(SCAN_WORKFLOW, scan_settings if scan_settings is not None else SCAN_SETTINGS)
        store.save(REPLY_WORKFLOW, reply_settings if reply_settings is not None else REPLY_SETTINGS)
        self.layout = layout
        self.root = queue_root(layout.workspace_root)
        self.runtime = build_runtime(self.config, loan_bridge=lambda: fake)

    def run(self, workflow: Any, arguments: dict[str, Any], key: str) -> Any:
        request = LocalWorkflowRequest(
            actor="engineer",
            bridge_id=self.config.device.bridge_id,
            workflow=workflow,
            arguments=arguments,
            idempotency_key=key,
            trace=TraceIdentifiers(trace_id=f"loan-{key}", request_id="loan", span_id="t"),
        )
        return asyncio.run(self.runtime.agent.execute_workflow(request))

    def last(self, outcome: Any) -> dict[str, Any]:
        result = outcome.workflow
        assert result is not None and result.run.status == "succeeded", result.run.failure
        data = result.step_results[-1].data
        assert isinstance(data, dict)
        return data

    def counts(self) -> dict[str, int]:
        return queue.counts(self.root)

    def close(self) -> None:
        self.runtime.close()


# -- manifests ---------------------------------------------------------------


def test_the_manifests_declare_parameters_effects_and_approvals() -> None:
    scan, reply = scan_workflow(), reply_workflow()
    assert scan.run_alias == 6 and reply.run_alias is None
    assert [step.capability.name for step in scan.steps] == ["scan-mail", "enqueue"]  # type: ignore[union-attr]
    assert [step.capability.name for step in reply.steps] == [  # type: ignore[union-attr]
        "look-up",
        "draft-replies",
        "offer-send",
    ]
    assert reply.occupies_machine is True and scan.occupies_machine is False
    effects = {spec.name: spec.side_effect for spec in (*SPECS, SEND_SPEC)}
    assert effects == {
        "loan.scan-mail": "read",
        "loan.enqueue": "write",
        "loan.look-up": "read",
        "loan.draft-replies": "write",
        "loan.offer-send": "write",
        "loan.send-reply": "external_side_effect",
    }
    for spec in (ENQUEUE_SPEC, DRAFT_SPEC, OFFER_SPEC, SEND_SPEC):
        assert spec.policy.approval_required is True
    assert SEND_SPEC.policy.risk == "high"
    # The send is declared, never a step of either Workflow.
    steps = {step.capability.key for step in (*scan.steps, *reply.steps)}  # type: ignore[union-attr]
    assert SEND_SPEC.identity.key not in steps
    assert [field["name"] for field in settings_fields(scan)] == [
        "mail_folder",
        "max_messages",
        "process_from",
        "require_sender",
        "sender_smtp",
        "exclude_categories",
    ]
    assert [field["name"] for field in form_fields(scan, "web")] == [
        "dry_run",
        "process_from_once",
    ]
    assert [field["name"] for field in form_fields(reply, "web")] == [
        "dry_run",
        "max_items",
        "offer_send",
    ]
    schema = agent_tool_schema(reply)
    assert "alert_recipient" not in schema["properties"]
    assert schema["properties"]["offer_send"]["default"] is False
    skill = loan_skill()
    assert {command.name for command in skill.commands} == {"scan", "reply"}


def test_no_credential_is_declared_or_stored() -> None:
    """Sign-in is the browser profile's; nothing asks for a password."""
    for manifest in (scan_workflow(), reply_workflow()):
        assert manifest.secrets == ()
        for field in manifest.parameters:
            said = f"{field.name} {field.label}".lower()
            assert not any(word in said for word in ("password", "token", "secret", "密碼"))


def test_the_workflows_ship_switched_off() -> None:
    from host_runtime.assets import shipped, shipped_off

    off = {item.metadata.identity.name for item in shipped_off()}
    assert off == {"rs-loan-reply", "rs-loan-customer-block-scan", "rs-loan-queue-reply"}
    assert not off & {item.metadata.identity.name for item in shipped()}


# -- producer -----------------------------------------------------------------


def test_the_scan_queues_one_item_per_borrow_number_and_offers_the_reply(
    tmp_path: Path,
) -> None:
    fake = FakeLoanHost(
        messages=[
            notice("DR26270135"),
            notice("DRHQ26270004"),
            notice("DR26270148", kind="否決"),
            {
                "entryId": "x",
                "subject": "Lunch",
                "htmlBody": "<p>hi</p>",
                "receivedTime": "2026-10-20T09:00:00",
            },
        ]
    )
    host = Host(tmp_path, fake)
    try:
        data = host.last(host.run(SCAN_WORKFLOW, {}, "scan"))
        assert data["enqueued"] == ["DR26270135", "DRHQ26270004"]
        assert host.counts()["pending"] == 2
        assert data["follow_up"]["workflow"] == REPLY_WORKFLOW.model_dump()
        assert "處理佇列中的 2 筆" in data["follow_up"]["label"]
        assert "否決通知，不處理" in data["preview"]
        assert data["verdict"] == {"ok": True, "summary": "排入 2 筆，待處理 2 筆"}
        assert fake.listed[0]["since"] == "2026-01-01T00:00:00"
        # Nothing was drafted or sent by a scan.
        assert fake.drafts == [] and fake.replies == []
    finally:
        host.close()


def test_a_rescan_does_not_duplicate_entries(tmp_path: Path) -> None:
    fake = FakeLoanHost(messages=[notice("DR26270135"), notice("DR26270135", entry="again")])
    host = Host(tmp_path, fake)
    try:
        first = host.last(host.run(SCAN_WORKFLOW, {}, "first"))
        second = host.last(host.run(SCAN_WORKFLOW, {}, "second"))
        assert first["enqueued"] == ["DR26270135"]
        assert second["enqueued"] == [] and host.counts()["pending"] == 1
        assert "已在佇列中或已處理過" in second["preview"]
        files = sorted(p.name for p in (host.root / "pending").glob("*.json"))
        assert files == ["DR26270135.json"]
    finally:
        host.close()


def test_a_scan_dry_run_writes_nothing_not_even_the_first_run_stamp(tmp_path: Path) -> None:
    fake = FakeLoanHost(messages=[notice("DR26270135", received="2099-01-01T00:00:00")])
    host = Host(tmp_path, fake, scan_settings={})
    try:
        dry = host.last(host.run(SCAN_WORKFLOW, {"dry_run": True}, "dry"))
        assert dry["dry_run"] is True and dry["enqueued"] == []
        assert "試跑：會排入佇列 1 筆：DR26270135" in dry["preview"]
        assert "第一次正式執行時會記下起算時間" in dry["preview"]
        assert dry["verdict"]["ok"] is None and dry["follow_up"] is None
        assert host.counts() == {"pending": 0, "claimed": 0, "done": 0, "failed": 0}
        assert not (host.root / ".processing-start").exists()
        real = host.last(host.run(SCAN_WORKFLOW, {}, "real"))
        assert real["stamped"] is True and real["enqueued"] == ["DR26270135"]
        assert (host.root / ".processing-start").is_file()
    finally:
        host.close()


def test_a_bad_process_from_and_no_outlook_are_refused(tmp_path: Path) -> None:
    host = Host(tmp_path / "bad", FakeLoanHost(), scan_settings={"process_from": "11/08 9am"})
    try:
        failed = host.run(SCAN_WORKFLOW, {}, "bad").workflow
        assert failed.run.failure.code == "loan_process_from_invalid"
    finally:
        host.close()
    host = Host(tmp_path / "none", FakeLoanHost(outlook=False))
    try:
        failed = host.run(SCAN_WORKFLOW, {}, "none").workflow
        assert failed.run.failure.code == "loan_outlook_unavailable"
        assert host.counts()["pending"] == 0
    finally:
        host.close()


# -- consumer -----------------------------------------------------------------


def _queued(host: Host, *borrows: str) -> None:
    for number in borrows:
        queue.enqueue(
            {
                "borrowNo": number,
                "loanUrl": FORM_URL,
                "entryId": f"mail-{number}",
                "category": "一般",
            },
            host.root,
        )


def test_a_reply_dry_run_reads_both_systems_but_drafts_and_claims_nothing(
    tmp_path: Path,
) -> None:
    fake = FakeLoanHost(blocks={"classificationDeliveryBlock": "Z1 Credit", "deliveryBlock": ""})
    host = Host(tmp_path, fake)
    try:
        _queued(host, "DR26270135")
        data = host.last(host.run(REPLY_WORKFLOW, {"dry_run": True}, "dry"))
        assert data["dry_run"] is True and data["drafted"] == 0 and data["action_cards"] == []
        assert "有配送限制回信" in data["preview"] and "Z1 Credit" in data["preview"]
        assert fake.drafts == [] and fake.replies == []
        assert host.counts()["pending"] == 1 and host.counts()["claimed"] == 0
        assert fake.gotos[0] == FORM_URL
    finally:
        host.close()


def test_replies_are_drafted_through_the_fake_outlook_and_never_sent(tmp_path: Path) -> None:
    fake = FakeLoanHost()
    host = Host(tmp_path, fake)
    try:
        _queued(host, "DR26270135")
        data = host.last(host.run(REPLY_WORKFLOW, {}, "real"))
        assert data["drafted"] == 1 and data["failed"] == 0
        (reply,) = fake.replies
        assert reply["entryId"] == "mail-DR26270135" and reply["send"] is False
        assert "配送中" in reply["body"]
        assert reply["attachments"] == [{"path": "C:/shots/shot.png"}]
        assert data["action_cards"] == [] and "請到 Outlook 草稿匣" in data["preview"]
        assert host.counts() == {"pending": 0, "claimed": 0, "done": 1, "failed": 0}
        done = json.loads((host.root / "done" / "DR26270135.json").read_text(encoding="utf-8"))
        assert done["outcome"] == "done" and done["result"]["outcome"] == "shipping"
        assert fake.sent == []
    finally:
        host.close()


def test_an_unknown_customer_gets_an_internal_notice_to_the_setting(tmp_path: Path) -> None:
    fake = FakeLoanHost(rows=())
    host = Host(tmp_path, fake)
    try:
        _queued(host, "DR26270135")
        data = host.last(host.run(REPLY_WORKFLOW, {}, "unknown"))
        (mail,) = fake.drafts
        assert mail["to"] == ["ops@example.com"] and "130895" in mail["subject"]
        assert fake.replies == [] and data["drafted"] == 1
        assert "C4C 查無客戶" in data["preview"]
    finally:
        host.close()


def test_a_failed_form_drafts_a_failure_notice_and_is_parked(tmp_path: Path) -> None:
    fake = FakeLoanHost(customer="")  # no 客戶名稱 on the form
    host = Host(tmp_path, fake)
    try:
        _queued(host, "DR26270135")
        data = host.last(host.run(REPLY_WORKFLOW, {}, "fail"))
        assert data["failed"] == 1 and data["verdict"]["ok"] is False
        (mail,) = fake.drafts
        assert "自動化失敗" in mail["subject"] and mail["send"] is False
        assert host.counts()["failed"] == 1 and host.counts()["pending"] == 0
    finally:
        host.close()


def test_a_link_to_another_site_is_never_opened(tmp_path: Path) -> None:
    assert trusted_link(FORM_URL, "https://rstw-portal.rsint.net")
    assert not trusted_link("https://evil.example/FastView.aspx", "https://rstw-portal.rsint.net")
    assert not trusted_link("http://rstw-portal.rsint.net/x", "https://rstw-portal.rsint.net")
    fake = FakeLoanHost()
    host = Host(tmp_path, fake)
    try:
        queue.enqueue(
            {
                "borrowNo": "DR26270199",
                "loanUrl": "https://evil.example/FastView.aspx",
                "entryId": "m",
            },
            host.root,
        )
        data = host.last(host.run(REPLY_WORKFLOW, {}, "evil"))
        assert fake.gotos == [] and data["failed"] == 1
        assert host.counts()["failed"] == 1
    finally:
        host.close()


def test_no_browser_or_no_outlook_hands_the_item_back(tmp_path: Path) -> None:
    host = Host(tmp_path / "browser", FakeLoanHost(browser=False))
    try:
        _queued(host, "DR26270135")
        outcome = host.run(REPLY_WORKFLOW, {}, "nobrowser").workflow
        assert outcome.run.failure.code == "loan_browser_unavailable"
        assert host.counts() == {"pending": 1, "claimed": 0, "done": 0, "failed": 0}
    finally:
        host.close()
    fake = FakeLoanHost(outlook=False)
    host = Host(tmp_path / "outlook", fake)
    try:
        _queued(host, "DR26270135", "DR26270136")
        data = host.last(host.run(REPLY_WORKFLOW, {"max_items": 2}, "nooutlook"))
        assert data["drafted"] == 0 and data["verdict"]["ok"] is False
        assert "Outlook 無法使用" in data["preview"]
        assert host.counts() == {"pending": 2, "claimed": 0, "done": 0, "failed": 0}
    finally:
        host.close()


def test_a_broken_template_stops_with_nothing_claimed(tmp_path: Path) -> None:
    templates = tmp_path / "tpl"
    templates.mkdir()
    (templates / "shipping-reply.txt").write_text("訂單 {borrowNumber}", encoding="utf-8")
    fake = FakeLoanHost()
    host = Host(
        tmp_path / "h",
        fake,
        reply_settings={**REPLY_SETTINGS, "template_dir": str(templates)},
    )
    try:
        _queued(host, "DR26270135")
        outcome = host.run(REPLY_WORKFLOW, {}, "tpl").workflow
        assert outcome.run.failure.code == "loan_template_invalid"
        assert host.counts()["pending"] == 1 and fake.replies == [] and fake.drafts == []
    finally:
        host.close()


def test_an_edited_template_reaches_the_draft(tmp_path: Path) -> None:
    templates = tmp_path / "tpl"
    templates.mkdir()
    (templates / "shipping-reply.txt").write_text(
        "Dear {customerName}, order {borrowNo} ({category}) is on its way.", encoding="utf-8"
    )
    fake = FakeLoanHost()
    host = Host(
        tmp_path / "h",
        fake,
        reply_settings={**REPLY_SETTINGS, "template_dir": str(templates)},
    )
    try:
        _queued(host, "DR26270135")
        host.last(host.run(REPLY_WORKFLOW, {}, "tpl"))
        assert fake.replies[0]["body"] == "Dear BTL Inc., order DR26270135 (一般) is on its way."
    finally:
        host.close()


def test_a_rerun_does_not_draft_a_form_twice(tmp_path: Path) -> None:
    fake = FakeLoanHost()
    host = Host(tmp_path, fake)
    try:
        _queued(host, "DR26270135")
        host.last(host.run(REPLY_WORKFLOW, {}, "one"))
        again = host.last(host.run(REPLY_WORKFLOW, {}, "two"))
        assert len(fake.replies) == 1 and again["drafted"] == 0
        # A second approval notice for the same number is not queued again.
        queue.enqueue({"borrowNo": "DR26270135", "loanUrl": FORM_URL}, host.root)
        assert host.counts()["pending"] == 0
    finally:
        host.close()


def test_send_cards_are_offered_one_per_draft_only_when_asked(tmp_path: Path) -> None:
    fake = FakeLoanHost()
    host = Host(tmp_path, fake)
    try:
        _queued(host, "DR26270135", "DR26270136")
        data = host.last(host.run(REPLY_WORKFLOW, {"max_items": 2, "offer_send": True}, "cards"))
        assert data["drafted"] == 2 and len(data["action_cards"]) == 2
        assert data["send_cards"] == data["action_cards"]
        assert "每封都要你在 Agent Web 按一次「寄出」" in data["preview"]
        cards = LoanReplyCards(host.layout.workspace_root)
        shown = [cards.card(card_id) for card_id in data["action_cards"]]
        assert all(card is not None and card.status == "pending" for card in shown)
        assert shown[0] is not None and shown[0].web_only is True
        assert fake.sent == []  # offering is not sending
    finally:
        host.close()


# -- producer -> consumer -------------------------------------------------------


def test_the_scan_hands_off_to_the_reply_which_the_person_starts(tmp_path: Path) -> None:
    fake = FakeLoanHost(messages=[notice("DR26270135")])
    host = Host(tmp_path, fake)
    try:
        scanned = host.last(host.run(SCAN_WORKFLOW, {}, "scan"))
        # The scan offered the reply and ran nothing of it.
        assert scanned["follow_up"]["workflow"]["name"] == "rs-loan-queue-reply"
        assert fake.gotos == [] and fake.replies == []
        # The person starts it; it works through what the scan queued.
        replied = host.last(host.run(REPLY_WORKFLOW, {}, "reply"))
        assert replied["drafted"] == 1
        assert fake.replies[0]["entryId"] == "mail-DR26270135"
        # With the queue empty, a further scan offers nothing.
        again = host.last(host.run(SCAN_WORKFLOW, {}, "again"))
        assert again["follow_up"] is None
    finally:
        host.close()


# -- forms ----------------------------------------------------------------------


def test_the_telegram_flow_asks_the_reply_questions_and_confirms_the_run() -> None:
    state = flow.start(reply_workflow(), "write", lambda _m, _s, _a: [])
    assert isinstance(state, flow.FlowState)
    # Nothing is required: the card comes first, with the defaults (owner 2026-10-25),
    # and a write Workflow is confirmed with a tap every time (owner 2026-10-05).
    card = flow.begin(state)
    assert card.prompt is not None and state.confirming
    assert "- 執行方式：正式執行（建 Outlook 草稿、更新佇列）（預設）" in card.prompt.text
    assert "- 這次處理幾筆？：1（預設）" in card.prompt.text
    assert card.prompt.buttons == [[("確認執行", "run:yes"), ("修改", "run:edit")]]
    flow.answer(state, "修改")
    asked = flow.answer(state, "edit:0")
    assert asked.prompt is not None and "執行方式" in asked.prompt.text
    # Each choice says what it does (owner 2026-10-25), never a bare Yes/No.
    assert asked.prompt.buttons == [
        [("只試跑（讀資料，不建草稿、不動佇列）", "yes")],
        [("正式執行（建 Outlook 草稿、更新佇列）", "no")],
    ]
    assert (
        "- 執行方式：正式執行（建 Outlook 草稿、更新佇列）\n"
        in (flow.answer(state, "no").prompt or flow.FlowPrompt("")).text
    )
    flow.answer(state, "這次處理幾筆 2")
    confirm = flow.answer(state, "草稿建好後 是")
    assert confirm.prompt is not None and "寄出" in confirm.prompt.text
    done = flow.answer(state, "run:yes")
    assert done.arguments == {"dry_run": False, "max_items": 2, "offer_send": True}
