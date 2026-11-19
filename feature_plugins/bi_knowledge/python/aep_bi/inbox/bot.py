"""What the bot answers when a person sends a link or a file (owner 2026-11-19).

A link or file is recorded at once and answered with its title line and domain buttons:
the AI's suggestion first, then the person's recent domains, then 「更多…」; several may
be chosen, and each tap edits the same message. `#<domain>` in the message, the person's
default (`/bi domain <d>`) or `/bi link <d> <url>` choose without asking. `/bi links`
lists the person's items and `/bi unlink <id>` withdraws one before it is processed.
A Reply to an item that only had a summary adds the person's text to it. Nothing is
fetched in full or ingested here: the domain's collect time does that (`process`).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePath
from typing import Any

from aep_bi.cards import convert, html_markdown
from aep_bi.inbox import domains as dom
from aep_bi.inbox import fetch, store
from aep_bi.inbox.domains import Domain
from aep_bi.inbox.store import Inbox
from host_runtime.features import Buttons, TelegramAnswer, TelegramItem
from models.contracts import ModelClient

COMMANDS = (("bi", "link"), ("bi", "links"), ("bi", "unlink"), ("bi", "domain"))
_URL = re.compile(r"https?://[^\s<>\"'「」（）]+", re.IGNORECASE)
_TAG = re.compile(r"(?<!\S)#([^\s#]{1,40})")
_ITEM_REF = re.compile(r"#(\d{1,9})\b")
_TAP = re.compile(r"^bi\.(t|m)\.(\d{1,9})(?:\.(\d{1,3}))?$")
MAX_URLS = 5
MAX_FILES = 5
RECENT = 3
#: How many domains 「更多…」 shows (two per row).
MAX_SHOWN = 24
MAX_NOTE = 500
UNASSIGNED_LABEL = "未分類"

USAGE = {
    "link": "用法：/bi link <領域> <網址>，或 /bi link <網址>（用預設領域）",
    "unlink": "用法：/bi unlink <編號>，例如 /bi unlink 12",
}


def _short(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Bot:
    """The inbox's Telegram answers for one workspace."""

    def __init__(
        self,
        workspace: Path,
        *,
        model: Callable[[], tuple[ModelClient, str] | None] = lambda: None,
        preview: fetch.Fetcher | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.workspace = workspace
        self.inbox = Inbox(workspace)
        self.model = model
        self.preview = preview if preview is not None else fetch.http_fetch
        self.clock = clock

    # -- entry -----------------------------------------------------------------------------------

    def handle(self, item: TelegramItem) -> TelegramAnswer | None:
        # Cheap refusals first: a Reply without an item number, a button that is not ours.
        if item.kind == "reply" and not _ITEM_REF.search(item.quoted or ""):
            return None
        if item.kind == "tap" and not _TAP.match(item.data):
            return None
        listed = dom.listed(self.workspace)
        if item.kind == "command":
            return self._command(item, listed)
        if not listed:
            # No BI domain on this PC: the message stays an ordinary one.
            return None
        if item.kind == "link":
            return self._links(item.actor, item.sender_name, item.text, item.urls, listed, None)
        if item.kind == "file":
            return self._files(item, listed)
        if item.kind == "tap":
            return self._tap(item, listed)
        if item.kind == "reply":
            return self._reply(item, listed)
        return None

    # -- receiving -------------------------------------------------------------------------------

    def _tag_picks(self, text: str, listed: Sequence[Domain]) -> list[str]:
        picks: list[str] = []
        for tag in _TAG.findall(text):
            found = dom.resolve(listed, tag)
            if len(found) == 1 and found[0].key not in picks:
                picks.append(found[0].key)
        return picks

    def _note(self, text: str) -> str:
        return _short(_TAG.sub(" ", _URL.sub(" ", text)), MAX_NOTE)

    def _choose(
        self, actor: str, text: str, listed: Sequence[Domain], given: list[str] | None
    ) -> tuple[list[str], str]:
        """(domains chosen without asking, by whom): given, else `#tags`, else default."""
        if given:
            return given, "person"
        tagged = self._tag_picks(text, listed)
        if tagged:
            return tagged, "tag"
        default = self.inbox.default(actor)
        if default is not None and dom.by_key(listed, default) is not None:
            return [default], "default"
        return [], ""

    def _offer(self, actor: str, suggested: str | None, listed: Sequence[Domain]) -> list[str]:
        """The domains on the buttons: the suggestion, then recent ones (else the first)."""
        offered = [suggested] if suggested and dom.by_key(listed, suggested) else []
        recent = [k for k in self.inbox.recent(actor, RECENT + 1) if dom.by_key(listed, k)]
        for key in recent or [d.key for d in listed[:RECENT]]:
            if key not in offered and len(offered) < RECENT + 1:
                offered.append(key)
        return offered

    def _preview(self, url: str) -> tuple[str, str]:
        """A link's title and summary, read quickly for the reply; ('', '') when slow."""
        try:
            got = self.preview(url, fetch.PREVIEW_BYTES, fetch.PREVIEW_TIMEOUT_S)
        except Exception:  # noqa: BLE001 - the reply goes without a title then
            return "", ""
        if not got.ok or fetch.login_page(got):
            return "", ""
        page = html_markdown.read(html_markdown.decode(got.body))
        return _short(page.title, 120), _short(page.description or page.text, 200)

    def _links(
        self,
        actor: str,
        sender_name: str,
        text: str,
        urls: Sequence[str],
        listed: Sequence[Domain],
        given: list[str] | None,
    ) -> TelegramAnswer:
        chosen, by = self._choose(actor, text, listed, given)
        note = self._note(text)
        made: list[int] = []
        already: list[int] = []
        batch: int | None = None
        for url in list(dict.fromkeys(urls))[:MAX_URLS]:
            normal = fetch.normalize(url)
            earlier = self.inbox.active_url(normal)
            if earlier is not None:
                already.append(int(earlier["id"]))
                continue
            title, summary = self._preview(url)
            suggested, confidence = (None, 0.0)
            if not chosen:
                suggested, confidence = dom.suggest(self.model(), listed, title, summary or note)
            item_id = self.inbox.add(
                kind="link",
                actor=actor,
                sender_name=sender_name,
                batch=batch,
                url=url,
                norm_url=normal,
                note=note,
                title=title,
                summary=summary,
                suggested=suggested,
                confidence=confidence,
                offered=self._offer(actor, suggested, listed),
            )
            batch = batch or item_id
            made.append(item_id)
        if not made:
            refs = "、".join(f"#{n}" for n in already)
            return TelegramAnswer(f"這個網址已經在佇列（{refs}），略過。")
        for key in chosen:
            for item_id in made:
                self.inbox.pick(item_id, key, by)
            self.inbox.note_recent(actor, key)
        answer = self._message(made[0], listed)
        if already:
            refs = "、".join(f"#{n}" for n in already)
            answer = TelegramAnswer(f"{answer.text}\n（{refs} 已經在佇列，略過）", answer.buttons)
        return answer

    def _files(self, item: TelegramItem, listed: Sequence[Domain]) -> TelegramAnswer:
        chosen, by = self._choose(item.actor, item.text, listed, None)
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
            item_id = self.inbox.add(
                kind="file",
                actor=item.actor,
                sender_name=item.sender_name,
                batch=batch,
                file_name=name,
                file_sha256=digest,
                title=name,
                offered=self._offer(item.actor, None, listed),
            )
            files_dir.mkdir(parents=True, exist_ok=True)
            path = files_dir / f"{item_id}-{digest[:12]}{PurePath(name).suffix.lower()}"
            path.write_bytes(data)
            self.inbox.update(item_id, file_path=str(path))
            batch = batch or item_id
            made.append(item_id)
        if not made:
            return TelegramAnswer("沒有收下：" + "；".join(skipped))
        for key in chosen:
            for item_id in made:
                self.inbox.pick(item_id, key, by)
            self.inbox.note_recent(item.actor, key)
        answer = self._message(made[0], listed)
        if skipped:
            answer = TelegramAnswer(
                f"{answer.text}\n沒有收下：{'；'.join(skipped)}", answer.buttons
            )
        return answer

    # -- the message and its buttons -------------------------------------------------------------

    def _times(self, keys: Sequence[str], listed: Sequence[Domain]) -> str:
        settings = self.inbox.settings()
        now = self.clock()
        parts: list[tuple[str, str]] = []
        for key in keys:
            setting = settings.get(key)
            clock = setting.collect_at if setting is not None and setting.enabled else None
            parts.append((dom.labels(listed, [key]), dom.when(clock, now)))
        if len({at for _, at in parts}) == 1:
            return f"已收進 {'、'.join(name for name, _ in parts)}，{parts[0][1]}處理"
        return "已收進 " + "、".join(f"{name}（{at}）" for name, at in parts)

    def _message(
        self, item_id: int, listed: Sequence[Domain], more: bool = False
    ) -> TelegramAnswer:
        """The item's message: its title lines, then where it went or the question."""
        items = self.inbox.batch(item_id)
        first = items[0]
        lines = []
        for item in items:
            title = item["title"] or item["file_name"] or item["url"] or ""
            lines.append(f"#{item['id']} {_short(title, 80)}")
        if len(items) == 1 and first["summary"]:
            lines.append(_short(first["summary"], 100))
        if first["status"] == store.WITHDRAWN:
            return TelegramAnswer("\n".join([*lines, "已撤回。"]))
        picked = [p["domain"] for p in self.inbox.picks(first["id"])]
        offered: list[str] = list(first["offered"])
        if more:
            offered = [d.key for d in listed[:MAX_SHOWN]]
            self.inbox.update(first["id"], offered=offered)
        for key in picked:
            if key not in offered:
                offered.append(key)
                self.inbox.update(first["id"], offered=offered)
        lines.append(self._times(picked, listed) if picked else "收進哪個領域？（可複選）")
        row: list[tuple[str, str]] = []
        rows: list[tuple[tuple[str, str], ...]] = []
        for index, key in enumerate(offered):
            domain = dom.by_key(listed, key)
            if domain is None:
                continue
            mark = "✓ " if key in picked else ""
            hint = "（建議）" if key == first["suggested"] and not picked else ""
            row.append((f"{mark}{domain.label}{hint}"[:64], f"bi.t.{first['id']}.{index}"))
            if len(row) == 2:
                rows.append(tuple(row))
                row = []
        if row:
            rows.append(tuple(row))
        if not more and len(listed) > len([k for k in offered if dom.by_key(listed, k)]):
            rows.append((("更多…", f"bi.m.{first['id']}"),))
        buttons: Buttons = tuple(rows)
        return TelegramAnswer("\n".join(lines), buttons, edit=True)

    def _tap(self, item: TelegramItem, listed: Sequence[Domain]) -> TelegramAnswer | None:
        tapped = _TAP.match(item.data)
        if tapped is None:
            return None
        op, number, index = tapped.group(1), int(tapped.group(2)), tapped.group(3)
        found = self.inbox.item(number)
        if found is None or found["actor"] != item.actor:
            return TelegramAnswer("找不到這一筆。", edit=True)
        first = self.inbox.batch(number)[0]
        if op == "m":
            return self._message(first["id"], listed, more=True)
        offered = list(first["offered"])
        if index is None or int(index) >= len(offered) or first["status"] == store.WITHDRAWN:
            return self._message(first["id"], listed)
        key = offered[int(index)]
        picked = {p["domain"] for p in self.inbox.picks(first["id"])}
        for member in self.inbox.batch(number):
            if key in picked:
                self.inbox.unpick(member["id"], key)
            else:
                self.inbox.pick(member["id"], key, "person")
        if key not in picked:
            self.inbox.note_recent(item.actor, key)
        return self._message(first["id"], listed)

    def _reply(self, item: TelegramItem, listed: Sequence[Domain]) -> TelegramAnswer | None:
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
        keys = [p["domain"] for p in self.inbox.picks(parent["id"])]
        child = self.inbox.add(
            kind="text",
            actor=item.actor,
            sender_name=item.sender_name,
            parent=parent["id"],
            url=parent["url"],
            norm_url=None,
            note=item.text.strip()[:20_000],
            title=parent["title"],
            offered=keys,
        )
        for key in keys:
            self.inbox.pick(child, key, "person")
        if parent["status"] == store.NEEDS_TEXT:
            self.inbox.update(parent["id"], status=store.DONE)
        times = self._times(keys, listed) if keys else "會在處理時分類"
        return TelegramAnswer(f"已補上 #{parent['id']} 的內文（#{child}）。{times}")

    # -- commands --------------------------------------------------------------------------------

    def _command(self, item: TelegramItem, listed: Sequence[Domain]) -> TelegramAnswer:
        name = item.data.partition(" ")[2]
        if not listed and name != "links":
            return TelegramAnswer("這台電腦還沒有 BI 知識庫的領域。先在 Agent Web 的 BI 頁建立。")
        if name == "link":
            return self._link_command(item, listed)
        if name == "links":
            return TelegramAnswer(self._listing(item.actor, listed))
        if name == "unlink":
            return TelegramAnswer(self._unlink(item.actor, item.text))
        return TelegramAnswer(self._domain_command(item.actor, item.text, listed))

    def _link_command(self, item: TelegramItem, listed: Sequence[Domain]) -> TelegramAnswer:
        words = item.text.split()
        urls = _URL.findall(item.text)
        if not urls:
            return TelegramAnswer(USAGE["link"])
        given: list[str] | None = None
        if words and not _URL.match(words[0]):
            found = dom.resolve(listed, words[0])
            if len(found) != 1:
                return TelegramAnswer(self._unknown(words[0], listed, found))
            given = [found[0].key]
        # The domain word is not part of the person's note.
        text = item.text.split(None, 1)[1] if given else item.text
        return self._links(item.actor, item.sender_name, text, urls, listed, given)

    def _unknown(self, name: str, listed: Sequence[Domain], found: Sequence[Domain]) -> str:
        if found:
            return f"「{name}」不只一個：{'、'.join(d.label for d in found)}。請寫完整名稱。"
        return f"找不到領域「{name}」。可用：{'、'.join(d.label for d in listed[:MAX_SHOWN])}"

    def _domain_command(self, actor: str, text: str, listed: Sequence[Domain]) -> str:
        wanted = text.strip()
        if not wanted:
            current = self.inbox.default(actor)
            named = dom.labels(listed, [current]) if current else "沒有"
            return (
                f"你的預設領域：{named}。\n用 /bi domain <領域> 設定，/bi domain 無 取消。\n"
                f"可用：{'、'.join(d.label for d in listed[:MAX_SHOWN])}"
            )
        if wanted in ("無", "取消", "off", "none"):
            self.inbox.set_default(actor, None)
            return "已取消預設領域：之後傳連結會先問你。"
        found = dom.resolve(listed, wanted)
        if len(found) != 1:
            return self._unknown(wanted, listed, found)
        self.inbox.set_default(actor, found[0].key)
        return f"預設領域：{found[0].label}。之後傳連結或檔案就直接收進這裡。"

    def _unlink(self, actor: str, text: str) -> str:
        number = text.strip().lstrip("#")
        if not number.isdigit():
            return USAGE["unlink"]
        outcome = self.inbox.withdraw(int(number), actor)
        return {
            store.WITHDRAWN: f"已撤回 #{number}。",
            "already": f"#{number} 已經撤回過了。",
            "processed": f"#{number} 已經處理，不能撤回；要移除請到 BI 頁刪除這個來源。",
        }.get(outcome, f"找不到你的 #{number}。")

    def _state(self, item: dict[str, Any], listed: Sequence[Domain]) -> str:
        if item["status"] == store.WITHDRAWN:
            return "已撤回"
        if item["status"] == store.UNASSIGNED:
            return UNASSIGNED_LABEL
        results = self.inbox.results(item_id=int(item["id"]))
        parts = [
            dom.labels(listed, [r["domain"]])
            + " "
            + store.RESULT_WORDS.get(r["status"], r["status"])
            + (f"（{r['code']}）" if r["status"] == store.FAILED and r["code"] else "")
            for r in results
        ]
        if item["status"] == store.NEEDS_TEXT:
            parts.append("沒有取得內容，回覆那則訊息補上文字")
        waiting = [
            p["domain"]
            for p in self.inbox.picks(int(item["id"]))
            if p["domain"] not in {r["domain"] for r in results}
        ]
        if waiting and item["status"] == store.QUEUED:
            parts.append(self._times(waiting, listed).replace("已收進 ", "待處理："))
        elif not results and item["status"] == store.QUEUED:
            parts.append("待選領域")
        return "；".join(parts) or store.STATUS_WORDS.get(item["status"], item["status"])

    def _listing(self, actor: str, listed: Sequence[Domain]) -> str:
        since = (self.clock() - timedelta(days=7)).isoformat(timespec="seconds")
        items = [
            i
            for i in self.inbox.items(actor=actor, limit=50)
            if i["received_at"] >= since or i["status"] in (store.QUEUED, store.UNASSIGNED)
        ][:15]
        if not items:
            return "你最近 7 天沒有傳連結或檔案。"
        lines = [
            f"#{i['id']} {_short(i['title'] or i['file_name'] or i['url'] or '', 40)}："
            f"{self._state(i, listed)}"
            for i in items
        ]
        return "\n".join(["你的連結與檔案（最近 7 天）：", *lines, "撤回：/bi unlink <編號>"])
