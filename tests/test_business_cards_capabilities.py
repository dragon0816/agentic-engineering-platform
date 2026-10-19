"""The business-cards capabilities through the Bridge (docs/phases/BUSINESS_CARDS.md).

The org chart renders a real PNG without Graphviz, with its legend; people
who left are left out or drawn grey. Signature harvesting reads only mail in
the person's scope from the named domain, sends only signature blocks to the
(fake) gateway model and stores nothing. The contact-store writes run on a
model's choice without a per-call confirmation, and nothing else does.
Fakes only: no mail, gateway or network.
"""

from __future__ import annotations

import asyncio
import sqlite3
import struct
import subprocess
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from capabilities.business_cards.handlers import (
    CHART_SPEC,
    HARVEST_SPEC,
    WRITE_SPECS,
    bindings,
)
from capabilities.business_cards.signatures import signature_block
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import ExecutionDependencies
from common.execution import RequestContext, TraceIdentifiers
from integrations.outlook_mail import MailError, MailMessage, MailScope, MailSummary
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent
from workflow.dispatch import BridgeExecutor

NOW = datetime.now(UTC)


class FakeMail:
    """A mailbox in memory; records what was opened."""

    def __init__(self, messages: Sequence[MailMessage]) -> None:
        self.messages = {item.message_id: item for item in messages}
        self.opened: list[str] = []
        self.listed: list[tuple[str, datetime]] = []

    def list(self, folder: str, since: datetime, limit: int) -> list[MailSummary]:
        self.listed.append((folder, since))
        return [
            MailSummary(**item.model_dump(exclude={"body", "cc"}))
            for item in self.messages.values()
            if item.folder == folder or item.folder.startswith(folder + "/")
        ]

    def get(self, message_id: str) -> MailMessage:
        self.opened.append(message_id)
        return self.messages[message_id]

    def save_attachment(self, message_id: str, name: str, target: Path) -> Path:
        raise AssertionError("no attachment is ever saved")


class SignatureModel:
    """Reads each block's first line as the name and returns structured JSON."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        text = request.messages[-1].text
        people = []
        for number, block in enumerate(text.split("===== block ")[1:]):
            lines = [line for line in block.split("\n")[1:] if line.strip()]
            people.append(
                {
                    "i": number,
                    "name": lines[0].strip(),
                    "title": lines[1].strip() if len(lines) > 1 else "",
                    "company": "範例科技",
                    "uncertain": ["title"],
                }
            )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            structured_output={"people": people},
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _context(actor: str = "alice", channel: str = "local", session: str = "s-1") -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor=actor,
        namespace="engineering",
        message="cards",
        channel=channel,
        session_id=session,
    )


def _bridge(
    tmp_path: Path,
    *,
    mail: FakeMail | None = None,
    scope: MailScope | None = None,
    model: SignatureModel | None = None,
    confirm: bool = True,
    actors: tuple[str, ...] = ("alice", "bob"),
) -> BridgeExecutor:
    installed = InstalledCapabilities()
    specs: list[CapabilitySpec] = []
    for spec, handler, request, response in bindings(
        tmp_path / "workspace",
        reader=lambda: mail if mail is not None else FakeMail(()),
        scope=lambda: scope or MailScope(),
        model=model,
        alias="company",
    ):
        installed.register(
            spec, handler, request, response, ExecutionDependencies(central_required=False)
        )
        specs.append(spec)
    policy = LocalPolicy(
        tuple(
            CapabilityGrant(
                actor=actor,
                asset=spec.identity,
                permissions=spec.policy.required_permissions,
                policy_refs=spec.policy.policy_refs,
                approval_ref="device-owner",
            )
            for actor in actors
            for spec in specs
        ),
        owner_mode=True,
    )
    if confirm:
        for spec in WRITE_SPECS:
            policy.confirm_writes(spec)
    return BridgeExecutor(installed, policy)


def _run(
    bridge: BridgeExecutor,
    name: str,
    arguments: dict[str, Any],
    *,
    actor: str = "alice",
    channel: str = "local",
    session: str = "s-1",
) -> Any:
    """The `CapabilityResult`, typed loosely so tests can read its JSON data."""
    spec = next(binding for binding in bridge.installed.discover() if binding.identity.name == name)
    return asyncio.run(
        bridge.execute(
            CapabilityInvocation(
                context=_context(actor, channel, session),
                origin="model",
                target=spec.identity,
                arguments=arguments,
            )
        )
    )


def _people(bridge: BridgeExecutor) -> None:
    for card in (
        {
            "name": "王小明",
            "company": "範例科技",
            "business_group": "網通事業群",
            "division": "研發處",
            "department": "射頻部",
            "title": "協理",
            "email": "hm.wang@example.com",
        },
        {"name": "李大華", "company": "範例科技", "division": "研發處", "title": "工程師"},
        {"name": "陳美", "company": "範例科技", "division": "業務處", "title": "業務"},
        {"name": "林離", "company": "範例科技", "division": "業務處", "title": "經理"},
    ):
        assert _run(bridge, "add-card", card).status == "succeeded"


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_writes_run_on_the_models_choice_only_when_confirmed_standing(tmp_path: Path) -> None:
    confirmed = _bridge(tmp_path / "a")
    assert _run(confirmed, "add-card", {"name": "王小明", "company": "範例科技"}).status == (
        "succeeded"
    )
    unconfirmed = _bridge(tmp_path / "b", confirm=False)
    refused = _run(unconfirmed, "add-card", {"name": "王小明", "company": "範例科技"})
    assert refused.failure is not None and refused.failure.code == "approval_required"
    # A read never waits; and only a low-risk local write can be confirmed.
    assert _run(unconfirmed, "find", {"query": "王"}).status == "succeeded"
    with pytest.raises(ValueError):
        LocalPolicy().confirm_writes(CHART_SPEC)
    execute = CapabilitySpec.model_validate(
        {
            **WRITE_SPECS[0].model_dump(),
            "side_effect": "execute",
        }
    )
    with pytest.raises(ValueError):
        LocalPolicy().confirm_writes(execute)


def test_the_org_chart_is_a_png_without_graphviz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_process(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the chart must not start a process (no Graphviz)")

    monkeypatch.setattr(subprocess, "run", no_process)
    monkeypatch.setattr(subprocess, "Popen", no_process)
    monkeypatch.setenv("PATH", "")
    bridge = _bridge(tmp_path)
    _people(bridge)
    assert (
        _run(
            bridge,
            "set-reporting-line",
            {
                "person": {"name": "李大華"},
                "manager": {"name": "王小明"},
                "evidence_kind": "signature",
                "evidence_ref": "<msg-9>",
            },
        ).status
        == "succeeded"
    )
    inferred = _run(
        bridge,
        "set-reporting-line",
        {
            "person": {"name": "陳美"},
            "manager": {"name": "王小明"},
            "evidence_kind": "title_inference",
        },
    )
    assert inferred.data is not None and inferred.data["inferred"] is True
    assert (
        _run(
            bridge,
            "set-status",
            {"person": {"name": "林離"}, "status": "left", "reason": "left in September"},
        ).status
        == "succeeded"
    )
    drawn = _run(bridge, "org-chart", {"company": "範例科技"})
    assert drawn.status == "succeeded", drawn.failure
    data = drawn.data
    assert data is not None
    png = Path(data["png_path"])
    width, height = _png_size(png)
    assert 400 <= width <= 4000 and 150 <= height <= 4000
    assert png.stat().st_size > 2_000
    assert (data["people"], data["left_omitted"], data["left_shown"]) == (3, 1, 0)
    assert (data["lines_evidenced"], data["lines_inferred"]) == (1, 1)
    legend = data["legend_markdown"]
    assert "| 李大華 | 王小明 | 簽名檔（<msg-9>） | 否（實線） |" in legend
    assert "| 陳美 | 王小明 | 依職稱推論 | 是（虛線） |" in legend
    assert "已離職的 1 人沒有畫出" in legend and "林離" not in legend
    assert Path(data["legend_path"]).read_text(encoding="utf-8").strip() == legend
    assert [item["media_type"] for item in data["attach"]] == ["image/png", "text/markdown"]
    # Asked for, people who left are drawn (grey) and counted.
    with_left = _run(bridge, "org-chart", {"company": "範例科技", "include_left": True})
    assert with_left.data is not None
    assert (with_left.data["people"], with_left.data["left_shown"]) == (4, 1)
    assert "已離職的人以灰色顯示" in with_left.data["legend_markdown"]
    grey = _png_size(Path(with_left.data["png_path"]))
    assert grey[1] >= height


def test_a_chart_without_evidenced_lines_says_it_is_no_reporting_chart(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _people(bridge)
    drawn = _run(bridge, "org-chart", {"company": "範例科技"})
    assert drawn.data is not None
    assert "不代表誰向誰報告" in drawn.data["legend_markdown"]
    assert "不代表誰向誰報告" in drawn.data["note"]
    missing = _run(bridge, "org-chart", {"company": "沒有這家"})
    assert missing.failure is not None and missing.failure.code == "company_has_no_contacts"


def _message(
    message_id: str, sender: str, body: str, *, days_ago: int = 1, folder: str = "Inbox"
) -> MailMessage:
    return MailMessage(
        message_id=message_id,
        folder=folder,
        sender=sender,
        subject="weekly sync",
        received=NOW - timedelta(days=days_ago),
        snippet=body[:40],
        body=body,
    )


BODY = (
    "Hi team,\nThe secret plan for project Falcon is attached. password=hunter2\n\n"
    "Best regards,\n{name}\n{title}\nTel: +886-2-2345-6789 #{ext}\n"
    "Mobile: 0912-000-{ext}\n\n-----Original Message-----\nFrom: someone.else@other.com\n"
    "Quoted Person\nDirector\nTel: 03-000-0000\n"
)


def test_signature_harvest_respects_the_scope_and_stores_nothing(tmp_path: Path) -> None:
    mail = FakeMail(
        [
            _message(
                "m1",
                "Wang <hm.wang@example.com>",
                BODY.format(name="王小明", title="協理", ext="312"),
            ),
            _message(
                "m2", "lee@example.com", BODY.format(name="李大華", title="工程師", ext="100")
            ),
            # Same sender, older: only the newest message per person is read.
            _message(
                "m3",
                "Wang <hm.wang@example.com>",
                BODY.format(name="王小明", title="經理", ext="312"),
                days_ago=5,
            ),
            _message("m4", "x@other.com", BODY.format(name="外人", title="經理", ext="1")),
            # Outside the scope: an excluded folder, and older than max_days.
            _message(
                "m5",
                "hr@example.com",
                BODY.format(name="不該讀", title="HR", ext="2"),
                folder="Inbox/HR",
            ),
            _message(
                "m6", "old@example.com", BODY.format(name="太舊", title="舊", ext="3"), days_ago=40
            ),
        ]
    )
    scope = MailScope(folders=("Inbox",), max_days=30, excluded_folders=("Inbox/HR",))
    model = SignatureModel()
    bridge = _bridge(tmp_path, mail=mail, scope=scope, model=model)
    harvested = _run(bridge, "harvest-signatures", {"domain": "example.com", "days": 365})
    assert harvested.status == "succeeded", harvested.failure
    data = harvested.data
    assert data is not None
    names = {item["name"]: item for item in data["candidates"]}
    assert set(names) == {"王小明", "李大華"}
    assert names["王小明"]["email"] == "hm.wang@example.com"
    assert names["王小明"]["message_id"] == "m1"
    assert names["王小明"]["uncertain"] == ["title"]
    assert set(mail.opened) == {"m1", "m2"}
    # days beyond the scope's max_days are capped.
    assert all(NOW - since <= timedelta(days=30, minutes=1) for _, since in mail.listed)
    sent = "\n".join(message.text for request in model.requests for message in request.messages)
    for leaked in ("Falcon", "hunter2", "Quoted Person", "someone.else", "不該讀", "外人"):
        assert leaked not in sent
    assert "Tel: +886-2-2345-6789 #312" in sent
    # Nothing was stored by the harvest.
    found = _run(bridge, "find", {"query": "王小明"})
    assert found.data is not None and found.data["total"] == 0
    stored = _run(
        bridge,
        "add-from-signature",
        {
            "entries": [
                {
                    **{k: v for k, v in names["王小明"].items() if k not in _NOT_ENTRY},
                }
            ]
        },
    )
    assert stored.status == "succeeded", stored.failure
    db = next((tmp_path / "workspace" / "business-cards").glob("*/cards.db"))
    with sqlite3.connect(db) as con:
        dumped = "\n".join(str(row) for row in con.iterdump())
    for leaked in ("Falcon", "hunter2", "Hi team", "Quoted Person"):
        assert leaked not in dumped
    assert "m1" in dumped and "email_signature" in dumped


_NOT_ENTRY = {"existing_person_id", "would_change", "candidate_id"}


def test_harvest_needs_a_model_and_a_domain(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, mail=FakeMail(()))
    refused = _run(bridge, "harvest-signatures", {"domain": "example.com"})
    assert refused.failure is not None and refused.failure.code == "model_not_configured"
    bad = _run(
        _bridge(tmp_path / "x", model=SignatureModel()), "harvest-signatures", {"domain": "x"}
    )
    assert bad.failure is not None and bad.failure.code == "invalid_input"


def test_a_signature_block_is_cut_before_the_quote() -> None:
    block = signature_block(BODY.format(name="王小明", title="協理", ext="312"))
    assert block is not None
    assert block.splitlines()[0] == "王小明"
    assert "Original Message" not in block and "Falcon" not in block
    assert signature_block("just a line\nno signature here") is None


def test_each_actor_sees_only_their_own_contacts(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    assert _run(bridge, "add-card", {"name": "王小明", "company": "範例科技"}).status == "succeeded"
    mine = _run(bridge, "find", {"query": "王小明"}, actor="alice")
    theirs = _run(bridge, "find", {"query": "王小明"}, actor="bob")
    assert mine.data is not None and mine.data["total"] == 1
    assert theirs.data is not None and theirs.data["total"] == 0
    refused = _run(bridge, "org-chart", {"company": "範例科技"}, actor="bob")
    assert refused.failure is not None


def test_add_card_keeps_only_the_hash_of_an_attached_photo(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    photo = tmp_path / "workspace" / "attachments" / "abc" / "att-1" / "card.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"\xff\xd8 synthetic photo bytes")
    outside = tmp_path / "elsewhere.jpg"
    outside.write_bytes(b"other")
    first = _run(
        bridge, "add-card", {"name": "王小明", "company": "範例科技", "image_path": str(photo)}
    )
    second = _run(
        bridge, "add-card", {"name": "陳美", "company": "範例科技", "image_path": str(outside)}
    )
    assert first.status == second.status == "succeeded"
    history = _run(bridge, "history", {"person": {"name": "王小明"}})
    assert history.data is not None
    assert history.data["observations"][0]["source_ref"].startswith("sha256:")
    other = _run(bridge, "history", {"person": {"name": "陳美"}})
    assert other.data is not None and other.data["observations"][0]["source_ref"] == ""


def test_harvest_is_read_only_and_the_writes_are_low_risk() -> None:
    assert HARVEST_SPEC.side_effect == "read"
    for spec in WRITE_SPECS:
        assert spec.side_effect == "write" and spec.policy.risk == "low"
        assert spec.policy.policy_refs == ("personal-contacts-policy",)


def test_harvest_follows_a_six_month_scope(tmp_path: Path) -> None:
    """The scope is whatever Settings says (the owner allows 6 months): a
    message 100 days old is read, one 200 days old is not."""
    mail = FakeMail(
        [
            _message(
                "r1", "a@example.com", BODY.format(name="近期", title="經理", ext="1"), days_ago=100
            ),
            _message(
                "r2", "b@example.com", BODY.format(name="太舊", title="經理", ext="2"), days_ago=200
            ),
        ]
    )
    model = SignatureModel()
    bridge = _bridge(tmp_path, mail=mail, scope=MailScope(max_days=180), model=model)
    harvested = _run(bridge, "harvest-signatures", {"domain": "example.com", "days": 365})
    assert harvested.status == "succeeded", harvested.failure
    assert [item["name"] for item in harvested.data["candidates"]] == ["近期"]
    assert mail.opened == ["r1"]
    assert all(NOW - since <= timedelta(days=180, minutes=1) for _, since in mail.listed)


class FlakyMail(FakeMail):
    """One message cannot be opened (Outlook said `message_unknown`)."""

    def get(self, message_id: str) -> MailMessage:
        if message_id == "bad":
            self.opened.append(message_id)
            raise MailError("message_unknown")
        return super().get(message_id)


def test_harvest_skips_a_message_it_cannot_read_and_says_so(tmp_path: Path) -> None:
    mail = FlakyMail(
        [
            _message("bad", "x@example.com", BODY.format(name="讀不到", title="經理", ext="9")),
            _message(
                "ok1",
                "a@example.com",
                BODY.format(name="王小明", title="協理", ext="1"),
                days_ago=2,
            ),
            _message(
                "ok2",
                "b@example.com",
                BODY.format(name="李大華", title="工程師", ext="2"),
                days_ago=3,
            ),
        ]
    )
    bridge = _bridge(tmp_path, mail=mail, model=SignatureModel())
    harvested = _run(bridge, "harvest-signatures", {"domain": "example.com"})
    assert harvested.status == "succeeded", harvested.failure
    data = harvested.data
    assert [item["name"] for item in data["candidates"]] == ["王小明", "李大華"]
    assert data["skipped"] == [{"code": "message_unknown", "count": 1}]
    assert "1 封信無法讀取（message_unknown），已略過" in data["skipped_note"]
    assert "其餘 2 封已處理" in data["skipped_note"]


def test_who_is_recorded_comes_from_the_request_never_from_the_model(tmp_path: Path) -> None:
    """Live test 2026-10-20 stored the model's "使用者" as status_set_by. Every
    write records the request's actor and channel; the model gives a reason only."""
    bridge = _bridge(tmp_path)
    _people(bridge)
    told = _run(
        bridge,
        "set-status",
        {"person": {"name": "林離"}, "status": "left", "said_by": "使用者"},
        channel="telegram",
    )
    assert told.failure is not None and told.failure.code == "invalid_input"
    left = _run(
        bridge,
        "set-status",
        {"person": {"name": "林離"}, "status": "left", "reason": "他說的"},
        channel="telegram",
    )
    assert left.status == "succeeded", left.failure
    _run(
        bridge,
        "edit-person",
        {"person": {"name": "陳美"}, "fields": {"title": "資深業務"}},
        channel="telegram",
    )
    _run(
        bridge,
        "set-reporting-line",
        {"person": {"name": "陳美"}, "manager": {"name": "王小明"}, "evidence_kind": "user"},
    )
    _run(bridge, "undo", {"change_id": left.data["change_id"]}, channel="telegram")
    gone = _run(bridge, "history", {"person": {"name": "林離"}}).data
    assert gone["person"]["status"] == "active"
    actors = {(item["kind"], item["actor"]) for item in gone["history"]}
    assert actors >= {("status", "alice via telegram")}
    _run(bridge, "set-status", {"person": {"name": "林離"}, "status": "left"})
    view = _run(bridge, "history", {"person": {"name": "林離"}}).data["person"]
    assert view["status_set_by"] == "alice via local"
    chen = _run(bridge, "history", {"person": {"name": "陳美"}}).data["history"]
    assert {(item["kind"], item["actor"]) for item in chen} >= {
        ("field", "alice via telegram"),
        ("line_add", "alice via local"),
    }
    assert all("使用者" not in item["actor"] for item in chen)


def test_a_field_is_confirmed_in_chat_through_edit_person(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    card = {"name": "范例", "company": "範例科技", "email": "ryan.rj.fan@example.com"}
    first = _run(bridge, "add-card", {**card, "uncertain": ["email"]}).data
    assert first["needs_confirmation"] == ["email"]
    rescan = _run(bridge, "add-card", card).data
    assert rescan["needs_confirmation"] == ["email"]
    found = _run(bridge, "find", {"query": "范例"}).data["people"][0]
    assert found["needs_confirmation"] == ["email"]
    confirmed = _run(
        bridge,
        "edit-person",
        {"person": {"name": "范例"}, "confirm": ["email"], "reason": "email 正確"},
        channel="telegram",
    )
    assert confirmed.status == "succeeded", confirmed.failure
    assert confirmed.data["confirmed"] == ["email"] and confirmed.data["change_id"]
    found = _run(bridge, "find", {"query": "范例"}).data["people"][0]
    assert found["needs_confirmation"] == []


class RomanisingModel(SignatureModel):
    """Adds a romanised name to every person, printed in the block or not."""

    def generate(self, request: ModelRequest) -> ModelResponse:
        response = super().generate(request)
        output: Any = response.structured_output
        for person in output["people"]:
            person["romanised_name"] = "Hsiao-Ming Wang" if person["name"] == "王小明" else "Da Lee"
        return response


def test_a_signature_keeps_a_romanised_name_only_when_the_block_prints_it(
    tmp_path: Path,
) -> None:
    body = BODY.replace("{name}\n", "{name}\nHsiao-Ming Wang\n", 1)
    mail = FakeMail(
        [
            _message(
                "m1", "hm.wang@example.com", body.format(name="王小明", title="協理", ext="1")
            ),
            _message(
                "m2",
                "lee@example.com",
                BODY.format(name="李大華", title="工程師", ext="2"),
                days_ago=2,
            ),
        ]
    )
    bridge = _bridge(tmp_path, mail=mail, model=RomanisingModel())
    data = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    names = {item["name"]: item["romanised_name"] for item in data["candidates"]}
    assert names == {"王小明": "Hsiao-Ming Wang", "李大華": ""}


def test_a_wrong_value_can_be_cleared_in_chat(tmp_path: Path) -> None:
    """The romanised name invented in the live test must be removable."""
    bridge = _bridge(tmp_path)
    _run(
        bridge,
        "add-card",
        {
            "name": "范例",
            "company": "範例科技",
            "romanised_name": "Yanji Fan",
            "romanised_name_printed": "Yanji Fan",
        },
    )
    cleared = _run(
        bridge,
        "edit-person",
        {"person": {"name": "范例"}, "clear": ["romanised_name"], "reason": "不在名片上"},
    )
    assert cleared.status == "succeeded", cleared.failure
    assert cleared.data["changes"] == [{"field": "romanised_name", "old": "Yanji Fan", "new": ""}]
    person = _run(bridge, "find", {"query": "范例"}).data["people"][0]
    assert person["romanised_name"] == ""
    # A later scan does not bring it back: the person's empty value is kept.
    again = _run(
        bridge,
        "add-card",
        {
            "name": "范例",
            "company": "範例科技",
            "romanised_name": "Yanji Fan",
            "romanised_name_printed": "Yanji Fan",
        },
    ).data
    assert [item["reason"] for item in again["kept"]] == ["user_set"]
    undone = _run(bridge, "undo", {"change_id": cleared.data["change_id"]})
    assert undone.status == "succeeded", undone.failure


def _harvest_mail() -> FakeMail:
    return FakeMail(
        [
            _message(
                "m-wang",
                "Wang <hm.wang@example.com>",
                BODY.format(name="王小明", title="協理", ext="1"),
            ),
            _message(
                "m-lee",
                "lee@example.com",
                BODY.format(name="李大華", title="工程師", ext="2"),
                days_ago=2,
            ),
        ]
    )


def test_harvested_candidates_are_stored_by_id_without_copying_message_ids(
    tmp_path: Path,
) -> None:
    """Live test 2026-10-20: on 「都存進去」 the model re-ran the harvest, because
    the candidates' message ids and dates were not in its context. The Host
    keeps the candidates of this conversation and stores them by short id."""
    mail = _harvest_mail()
    bridge = _bridge(tmp_path, mail=mail, model=SignatureModel())
    harvested = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    ids = {item["name"]: item["candidate_id"] for item in harvested["candidates"]}
    assert sorted(ids.values()) == ["s1", "s2"]
    assert "store_candidates" in harvested["note"] and harvested["expires_at"]
    opened = list(mail.opened)
    stored = _run(bridge, "store-candidates", {"candidate_ids": ["all"]})
    assert stored.status == "succeeded", stored.failure
    assert sorted(stored.data["stored"]) == ["s1", "s2"]
    assert {item["outcome"] for item in stored.data["results"]} == {"created"}
    assert mail.opened == opened  # no second harvest
    history = _run(bridge, "history", {"person": {"name": "王小明"}}).data
    assert [(o["source"], o["source_ref"]) for o in history["observations"]] == [
        ("email_signature", "m-wang")
    ]
    assert history["observations"][0]["source_date"] == (NOW - timedelta(days=1)).date().isoformat()
    # Stored once: asking again stores nothing more.
    again = _run(bridge, "store-candidates", {"candidate_ids": ["s1"]}).data
    assert again["stored"] == [] and again["already_stored"] == ["s1"]


def test_only_the_named_candidates_are_stored_and_unknown_ids_are_reported(
    tmp_path: Path,
) -> None:
    bridge = _bridge(tmp_path, mail=_harvest_mail(), model=SignatureModel())
    harvested = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    lee = next(c["candidate_id"] for c in harvested["candidates"] if c["name"] == "李大華")
    stored = _run(bridge, "store-candidates", {"candidate_ids": [lee, "s9"]}).data
    assert stored["stored"] == [lee] and stored["unknown"] == ["s9"]
    assert _run(bridge, "find", {"query": "王小明"}).data["total"] == 0
    assert _run(bridge, "find", {"query": "李大華"}).data["total"] == 1


def test_candidates_expire_and_belong_to_one_conversation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from capabilities.business_cards import store as store_module

    bridge = _bridge(tmp_path, mail=_harvest_mail(), model=SignatureModel())
    assert _run(bridge, "harvest-signatures", {"domain": "example.com"}).status == "succeeded"
    # Another actor (another store) has no candidates.
    other = _run(bridge, "store-candidates", {"candidate_ids": ["all"]}, actor="bob")
    assert other.failure is not None and other.failure.code == "candidates_expired"
    # Another conversation of the same person has none either.
    elsewhere = _run(bridge, "store-candidates", {"candidate_ids": ["all"]}, session="s-2")
    assert elsewhere.failure is not None and elsewhere.failure.code == "candidates_expired"
    later = datetime.now(UTC) + store_module.CANDIDATE_TTL + timedelta(minutes=1)
    monkeypatch.setattr(store_module, "_clock", lambda: later)
    expired = _run(bridge, "store-candidates", {"candidate_ids": ["all"]})
    assert expired.failure is not None and expired.failure.code == "candidates_expired"
