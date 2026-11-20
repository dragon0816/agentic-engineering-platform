"""What a domain's collection bot answers (owner 2026-11-20: one Telegram bot per BI domain).

Everything a mapped person sends to the bot goes to the bot's domain — the domain it is
bound to in BI 「管理」 → 「Telegram 收集」, else the `target` it was configured with. No
question, no buttons: a link, a file or words are recorded at once and answered
「已收進 <領域>，<時間> 處理（#12）」. A Reply to the bot's 「#12 只取得摘要」 message adds the
person's text to that item. `/links` lists the person's items, `/unlink <id>` withdraws
one before it is processed. Fetching and ingest happen at the domain's collect time
(`process`).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePath
from typing import Any

from aep_bi.cards import convert
from aep_bi.inbox import domains as dom
from aep_bi.inbox import fetch, store
from aep_bi.inbox.domains import Domain
from aep_bi.inbox.store import Inbox
from host_runtime.features import TelegramAnswer, TelegramItem

_URL = re.compile(r"https?://[^\s<>\"'「」（）]+", re.IGNORECASE)
_ITEM_REF = re.compile(r"#(\d{1,9})\b")
MAX_URLS = 5
MAX_FILES = 5
MAX_NOTE = 500
MAX_TEXT = 20_000
UNBOUND = (
    "這個 bot 還沒有綁定 BI 領域：到 Agent Web → BI → 管理 → Telegram 收集，"
    "在領域那一列選這個 bot。"
)


def _short(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Bot:
    """The inbox's answers for one workspace."""

    def __init__(
        self, workspace: Path, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.workspace = workspace
        self.inbox = Inbox(workspace)
        self.clock = clock

    def domain_of(self, item: TelegramItem, listed: Sequence[Domain]) -> Domain | None:
        """The bot's domain: its page binding, else its configured target (a key or a
        name only one domain has)."""
        key = self.inbox.bound(item.bot)
        if key is not None:
            return dom.by_key(listed, key)
        found = dom.resolve(listed, item.target) if item.target else []
        return found[0] if len(found) == 1 else None

    def handle(self, item: TelegramItem) -> TelegramAnswer:
        words = item.text.strip()
        if words.startswith("/links"):
            return TelegramAnswer(self._listing(item.actor, dom.listed(self.workspace)))
        if words.startswith("/unlink"):
            return TelegramAnswer(self._unlink(item.actor, words[len("/unlink") :]))
        listed = dom.listed(self.workspace)
        domain = self.domain_of(item, listed)
        if domain is None:
            return TelegramAnswer(UNBOUND)
        if item.kind == "reply":
            added = self._reply(item, domain)
            if added is not None:
                return added
        if item.kind == "file":
            return self._files(item, domain)
        if item.kind == "link":
            return self._links(item, domain)
        return self._text(item, domain)

    # -- receiving -------------------------------------------------------------------------------

    def _when(self, domain: Domain) -> str:
        setting = self.inbox.settings().get(domain.key)
        clock = setting.collect_at if setting is not None and setting.enabled else None
        return dom.when(clock, self.clock())

    def _received(self, domain: Domain, made: Sequence[int], extra: str = "") -> TelegramAnswer:
        refs = "、".join(f"#{n}" for n in made)
        return TelegramAnswer(
            f"已收進 {domain.label}，{self._when(domain)}處理（{refs}）。{extra}".strip()
        )

    def _new(self, item: TelegramItem, domain: Domain, **values: Any) -> int:
        item_id = self.inbox.add(
            actor=item.actor, bot=item.bot, sender_name=item.sender_name, **values
        )
        self.inbox.pick(item_id, domain.key, "bot")
        return item_id

    def _links(self, item: TelegramItem, domain: Domain) -> TelegramAnswer:
        note = _short(_URL.sub(" ", item.text), MAX_NOTE)
        made: list[int] = []
        already: list[int] = []
        batch: int | None = None
        for url in list(dict.fromkeys(item.urls))[:MAX_URLS]:
            normal = fetch.normalize(url)
            earlier = self.inbox.active_url(normal)
            if earlier is not None:
                already.append(int(earlier["id"]))
                continue
            item_id = self._new(
                item, domain, kind="link", batch=batch, url=url, norm_url=normal, note=note
            )
            batch = batch or item_id
            made.append(item_id)
        refs = "、".join(f"#{n}" for n in already)
        if not made:
            return TelegramAnswer(f"這個網址已經在佇列（{refs}），略過。")
        return self._received(domain, made, f"（{refs} 已經在佇列，略過）" if already else "")

    def _files(self, item: TelegramItem, domain: Domain) -> TelegramAnswer:
        made: list[int] = []
        skipped: list[str] = []
        batch: int | None = None
        files_dir = self.inbox.dir / "files"
        for sent in item.files[:MAX_FILES]:
            name = PurePath(sent.name).name.strip() or "file"
            if convert.kind(name) is None:
                skipped.append(f"{name}（不支援這種檔案）")
                continue
            try:
                data = sent.read()
            except Exception as error:  # noqa: BLE001 - told to the person by code
                skipped.append(
                    f"{name}（下載失敗：{getattr(error, 'code', type(error).__name__)}）"
                )
                continue
            digest = hashlib.sha256(data).hexdigest()
            item_id = self._new(
                item,
                domain,
                kind="file",
                batch=batch,
                file_name=name,
                file_sha256=digest,
                title=name,
                note=_short(item.text, MAX_NOTE),
            )
            files_dir.mkdir(parents=True, exist_ok=True)
            path = files_dir / f"{item_id}-{digest[:12]}{PurePath(name).suffix.lower()}"
            path.write_bytes(data)
            self.inbox.update(item_id, file_path=str(path))
            batch = batch or item_id
            made.append(item_id)
        if not made:
            return TelegramAnswer("沒有收下：" + "；".join(skipped))
        return self._received(domain, made, f"沒有收下：{'；'.join(skipped)}" if skipped else "")

    def _text(self, item: TelegramItem, domain: Domain) -> TelegramAnswer:
        """Words alone are a source too (a note, a pasted post)."""
        text = item.text.strip()[:MAX_TEXT]
        item_id = self._new(item, domain, kind="text", note=text, title=_short(text, 40))
        return self._received(domain, [item_id])

    def _reply(self, item: TelegramItem, domain: Domain) -> TelegramAnswer | None:
        """A person's text for an item that only had a summary, by Reply to its message."""
        refs = _ITEM_REF.findall(item.quoted or "")
        if not refs or not item.text.strip():
            return None
        parent = self.inbox.item(int(refs[0]))
        if (
            parent is None
            or parent["actor"] != item.actor
            or not (parent["status"] == store.NEEDS_TEXT or parent["summary_only"])
        ):
            return None
        child = self._new(
            item,
            domain,
            kind="text",
            parent=parent["id"],
            url=parent["url"],
            note=item.text.strip()[:MAX_TEXT],
            title=parent["title"],
        )
        if parent["status"] == store.NEEDS_TEXT:
            self.inbox.update(parent["id"], status=store.DONE)
        return TelegramAnswer(
            f"已補上 #{parent['id']} 的內文（#{child}），{self._when(domain)}處理。"
        )

    # -- /links and /unlink ----------------------------------------------------------------------

    def _unlink(self, actor: str, text: str) -> str:
        number = text.strip().lstrip("#")
        if not number.isdigit():
            return "用法：/unlink <編號>，例如 /unlink 12"
        outcome = self.inbox.withdraw(int(number), actor)
        return {
            store.WITHDRAWN: f"已撤回 #{number}。",
            "already": f"#{number} 已經撤回過了。",
            "processed": f"#{number} 已經處理，不能撤回；要移除請到 BI 頁刪除這個來源。",
        }.get(outcome, f"找不到你的 #{number}。")

    def _state(self, item: dict[str, Any], listed: Sequence[Domain]) -> str:
        if item["status"] == store.WITHDRAWN:
            return "已撤回"
        results = self.inbox.results(item_id=int(item["id"]))
        parts = [
            store.RESULT_WORDS.get(r["status"], r["status"])
            + (f"（{r['code']}）" if r["status"] == store.FAILED and r["code"] else "")
            for r in results
        ]
        if item["status"] == store.NEEDS_TEXT:
            parts.append("沒有取得內容，回覆那則訊息補上文字")
        if item["status"] == store.QUEUED and not results:
            picks = self.inbox.picks(int(item["id"]))
            domain = dom.by_key(listed, picks[0]["domain"]) if picks else None
            parts.append("待處理" + (f"（{self._when(domain)}）" if domain else ""))
        return "；".join(parts) or store.STATUS_WORDS.get(item["status"], item["status"])

    def _listing(self, actor: str, listed: Sequence[Domain]) -> str:
        since = (self.clock() - timedelta(days=7)).isoformat(timespec="seconds")
        items = [
            i
            for i in self.inbox.items(actor=actor, limit=50)
            if i["received_at"] >= since or i["status"] == store.QUEUED
        ][:15]
        if not items:
            return "你最近 7 天沒有傳東西給這個 bot。"
        lines = [
            f"#{i['id']} {_short(i['title'] or i['file_name'] or i['url'] or '', 40)}："
            f"{self._state(i, listed)}"
            for i in items
        ]
        return "\n".join(["你最近 7 天傳的：", *lines, "撤回：/unlink <編號>"])
