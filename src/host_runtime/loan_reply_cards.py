"""Send cards for the loan reply drafts: one press, one mail (owner 2026-10-20).

`engineering/rs-loan-queue-reply` saves its replies as Outlook drafts. When
the person ticked "a send card per draft", its last step hands each saved
draft here and an `ls-` card shows to, cc, subject, attachments and the text
with **寄出** (Send) and **留在草稿匣** (Keep as draft):

- every message is its own card and its own press; there is no "send all"
  and no conversation-wide allow;
- the press is a person's, in Agent Web: Telegram shows the card and says
  where to answer (`web_only`), as for the agent's mail cards;
- what is sent is the draft the card showed: `integrations.outlook_send`
  compares recipients, subject and attachment names first and sends nothing
  if the draft was changed in Outlook;
- a card nobody answers within a day expires and the draft stays in Drafts.

No Workflow step, tool or model reaches `decide`; the only callers are Agent
Web's card route and Telegram's card tap (refused here). A source test keeps
it that way (tests/test_loan_reply_send.py).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

from capabilities.loan_reply.contracts import SendOffer
from common.action_cards import ActionCard, CardButton
from host_runtime.card_store import CardStore, PendingRecord, new_card_id
from integrations.outlook_send import DraftSender, SendError, draft_fingerprint

CARD_PREFIX = "ls"
CARDS_FILE = Path("loan-reply") / "send-cards.json"
#: How long a card waits for a press before the draft simply stays a draft.
CARD_TTL = timedelta(hours=24)
STATUS_LABELS = {
    "pending": "等你決定",
    "sent": "已寄出",
    "kept": "留在 Outlook 草稿匣",
    "expired": "一天內沒有回應：留在草稿匣",
    "failed": "沒有寄出",
}
SEND_FAILURES = {
    "draft_changed": "這封草稿在卡片顯示後已在 Outlook 被修改，沒有寄出；"
    "請在 Outlook 檢查後自行寄出。",
    "draft_unknown": "Outlook 裡已找不到這封草稿，沒有寄出。",
    "send_failed": "Outlook 沒有寄出，草稿仍在草稿匣。",
    "library_missing": "這台電腦上的 AEP 無法連到 Outlook。",
    "outlook_missing": "這台電腦沒有安裝 Outlook。",
}


class LoanReplyCard(PendingRecord):
    borrow_no: str
    entry_id: str
    fingerprint: str
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    subject: str = ""
    body: str = ""
    attachments: tuple[str, ...] = ()
    outcome: str = ""
    outcome_ok: bool | None = None
    channel: str = ""


class _SharedStore(CardStore[LoanReplyCard]):
    """Re-read before every use: the Workflow step that offers cards and the
    Agent Web route that decides them share one file."""

    def _reload(self) -> None:
        fresh: CardStore[LoanReplyCard] = CardStore(self.path, self.model, keep=self.keep)
        self._records = {item.card_id: item for item in fresh.records()}

    def get(self, card_id: str) -> LoanReplyCard | None:
        with self.lock:
            self._reload()
            return super().get(card_id)

    def records(self) -> list[LoanReplyCard]:
        with self.lock:
            self._reload()
            return super().records()

    def put(self, record: LoanReplyCard) -> LoanReplyCard:
        with self.lock:
            self._reload()
            return super().put(record)


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(str(path.resolve()).casefold(), threading.RLock())


class LoanReplyCards:
    def __init__(
        self,
        workspace_root: Path,
        *,
        sender: Callable[[], DraftSender] | None = None,
        clock: Callable[[], Any] | None = None,
    ) -> None:
        path = workspace_root / CARDS_FILE
        self.store = _SharedStore(path, LoanReplyCard, keep=500, clock=clock)
        self.store.lock = _lock_for(path)
        self.sender = sender

    # -- offering (the Workflow's last step) --------------------------------

    def offer(self, offers: Sequence[SendOffer]) -> list[str]:
        """One pending card per draft; returns the card ids."""
        made: list[str] = []
        now = self.store.now()
        for item in offers:
            record = LoanReplyCard(
                card_id=new_card_id(CARD_PREFIX),
                created_at=now,
                expires_at=now + CARD_TTL,
                borrow_no=item.borrow_no,
                entry_id=item.entry_id,
                fingerprint=draft_fingerprint(item.to, item.cc, item.subject, item.attachments),
                to=item.to,
                cc=item.cc,
                subject=item.subject,
                body=item.body[:12_000],
                attachments=item.attachments,
            )
            self.store.put(record)
            made.append(record.card_id)
        return made

    # -- cards ----------------------------------------------------------------

    def _settle(
        self, record: LoanReplyCard, status: str, outcome: str, ok: bool | None, channel: str = ""
    ) -> LoanReplyCard:
        return self.store.put(
            record.model_copy(
                update={
                    "status": status,
                    "outcome": outcome[:2_000],
                    "outcome_ok": ok,
                    "decided_at": self.store.now(),
                    "channel": channel,
                }
            )
        )

    def _current(self, card_id: str) -> LoanReplyCard | None:
        record = self.store.get(card_id)
        if record is not None and self.store.expired(record):
            record = self._settle(record, "expired", "留在 Outlook 草稿匣。", None)
        return record

    def card(self, card_id: str) -> ActionCard | None:
        with self.store.lock:
            record = self._current(card_id)
        return None if record is None else draw(record)

    def open_cards(self) -> list[ActionCard]:
        with self.store.lock:
            found = [
                self._current(item.card_id)
                for item in self.store.records()
                if item.status == "pending"
            ]
        return [draw(item) for item in found if item is not None and item.status == "pending"]

    def decide(self, card_id: str, action: str, *, channel: str = "local") -> dict[str, Any]:
        """寄出 or 留在草稿匣, pressed by a person on this one card."""
        if channel == "telegram":
            card = self.card(card_id)
            return {
                "ok": False,
                "code": "web_only",
                "message": "借用單回信的寄出確認只在 Agent Web 按。",
                **({"card": card.model_dump(mode="json")} if card else {}),
            }
        with self.store.lock:
            record = self._current(card_id)
            if record is None:
                return {"ok": False, "code": "card_unknown", "message": "找不到這張卡片。"}
            if record.status != "pending":
                return {
                    "ok": False,
                    "code": f"mail_{record.status}",
                    "message": STATUS_LABELS.get(record.status, record.status),
                    "card": draw(record).model_dump(mode="json"),
                }
            if action == "keep_draft":
                record = self._settle(record, "kept", "留在 Outlook 草稿匣。", None, channel)
            elif action == "send":
                if self.sender is None:
                    record = self._settle(
                        record, "failed", SEND_FAILURES["library_missing"], False, channel
                    )
                else:
                    try:
                        self.sender().send(record.entry_id, record.fingerprint)
                    except SendError as error:
                        record = self._settle(
                            record,
                            "failed",
                            SEND_FAILURES.get(error.code, error.code),
                            False,
                            channel,
                        )
                    else:
                        record = self._settle(
                            record, "sent", "已從你的 Outlook 寄出。", True, channel
                        )
            else:
                return {
                    "ok": False,
                    "code": "card_action_unknown",
                    "message": "這張卡片只有「寄出」和「留在草稿匣」。",
                }
        return {
            "ok": record.status in ("sent", "kept"),
            "code": record.status,
            "message": record.outcome,
            "card": draw(record).model_dump(mode="json"),
        }


def draw(record: LoanReplyCard) -> ActionCard:
    lines = [f"收件者：{', '.join(record.to)}"]
    if record.cc:
        lines.append(f"副本：{', '.join(record.cc)}")
    lines.append(f"主旨：{record.subject}")
    if record.attachments:
        lines.append("附件：" + ", ".join(record.attachments))
    lines += ["", record.body]
    return ActionCard(
        card_id=record.card_id,
        kind="loan_reply_send",
        title=f"寄出借用單 {record.borrow_no} 的回信？"[:160],
        preview="\n".join(lines)[:20_000],
        effects=("按「寄出」只會從你的 Outlook 寄出這一封；每一封都要各按一次。",),
        buttons=(
            CardButton(action="send", label="寄出", style="primary"),
            CardButton(action="keep_draft", label="留在草稿匣"),
        ),
        status=record.status,
        status_label=STATUS_LABELS.get(record.status, record.status),
        outcome=record.outcome,
        outcome_ok=record.outcome_ok,
        expires_at=record.expires_at,
        web_only=True,
        message="借用單回信草稿已建立，等你決定是否寄出。",
    )
