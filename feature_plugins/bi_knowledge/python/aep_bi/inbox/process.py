"""A domain's collect time and review time, and what follows an import (owner 2026-11-19).

Collect: each item sent to the domain's collection bot is claimed once (AGENTS rule 21)
and fetched over HTTP (a Threads/Instagram login wall may go to the local browser when
the owner turned that on), kept whole as an immutable `.html` source whose first line
records who sent it, when, the original address and when and how it was fetched (AGENTS
rule 7), deduplicated by address and content, converted to Markdown, and given to an AI
ingest run that stops at review: nothing is accepted, committed or pushed here. A file or
words sent to the bot go in as uploaded sources do. A page that gave only its summary is
marked 「只取得摘要」 and its sender is asked to Reply with the text. Every message goes
from the bot the item came through, to its sender only.

Review: the senders of the domain's items still in review hear how many candidate cards
wait. After 「全部接受並匯入」 (or 「確認匯入」) of such a run, the domain's tests run, its
Dashboard is drawn again, and the senders get the result.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aep_bi.cards import ai_runs, board, catalog, homes, html_markdown
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, BiStoreError
from aep_bi.inbox import domains as dom
from aep_bi.inbox import fetch, store
from aep_bi.inbox.domains import Domain
from aep_bi.inbox.store import Inbox
from host_runtime.features import Messenger

WHERE = "這台電腦的 Agent Web → BI（知識庫 {vault}／領域 {label}）"
_UNSAFE = re.compile(r"[\\/:*?\"<>|\s]+")


def _slug(text: str, limit: int = 50) -> str:
    return _UNSAFE.sub("-", text).strip("-.")[:limit] or "page"


@dataclass
class Processor:
    """Collect and remind for one workspace. `browser` fetches a login-walled social
    post with the local headless browser; None leaves such a post as its summary."""

    workspace: Path
    ai: ai_runs.AiRuntime | None
    messenger: Messenger | None = None
    fetcher: fetch.Fetcher = fetch.http_fetch
    browser: Callable[[str], fetch.Fetched] | None = None
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    @property
    def inbox(self) -> Inbox:
        return Inbox(self.workspace)

    def _send(self, who: tuple[str, str], text: str) -> bool:
        """From the collection bot `who[0]` to its mapped sender `who[1]`."""
        bot, actor = who
        return self.messenger is not None and self.messenger.send(bot, actor, text)

    @staticmethod
    def _who(item: dict[str, Any]) -> tuple[str, str]:
        return str(item.get("bot") or ""), str(item["actor"])

    # -- collect ---------------------------------------------------------------------------------

    def collect(self, key: str) -> dict[str, Any]:
        """Process every item waiting for domain `key`; a summary of what happened."""
        listed = dom.listed(self.workspace)
        domain = dom.by_key(listed, key)
        if domain is None:
            return {"ok": False, "code": "domain_unknown"}
        counts = {name: 0 for name in (store.REVIEW, store.SUMMARY, store.DUPLICATE, store.FAILED)}
        asks: list[tuple[tuple[str, str], str]] = []
        senders: set[tuple[str, str]] = set()
        for item in self.inbox.due(key):
            item_id = int(item["id"])
            if not self.inbox.claim(item_id, key):
                continue
            senders.add(self._who(item))
            try:
                status = self._one(item, domain)
            except Exception as failure:  # noqa: BLE001 - one item never stops the others
                status = store.FAILED
                self.inbox.finish(item_id, key, store.FAILED, code=type(failure).__name__)
            counts[status] = counts.get(status, 0) + 1
            fresh = self.inbox.item(item_id) or item
            if status == store.SUMMARY or fresh["status"] == store.NEEDS_TEXT:
                what = "只取得摘要" if status == store.SUMMARY else "沒有取得內容"
                asks.append(
                    (
                        self._who(item),
                        f"#{item_id} {what}（{(fresh['title'] or fresh['url'] or '')[:60]}）。"
                        "請回覆這則訊息，貼上貼文或頁面的文字。",
                    )
                )
        self._tell(domain, senders, asks, counts)
        return {"ok": True, **counts}

    def _tell(
        self,
        domain: Domain,
        senders: set[tuple[str, str]],
        asks: list[tuple[tuple[str, str], str]],
        counts: dict[str, int],
    ) -> None:
        """One line per sender about the run, then each request for missing text."""
        converted = counts[store.REVIEW] + counts[store.SUMMARY]
        line = (
            f"{domain.label} 收集完成：{converted} 筆已轉換待審"
            + (f"、{counts[store.DUPLICATE]} 筆重複略過" if counts[store.DUPLICATE] else "")
            + (
                f"、{counts[store.FAILED]} 筆失敗（/bi links 看原因）"
                if counts[store.FAILED]
                else ""
            )
            + "。"
        )
        for who in sorted(senders):
            self._send(who, line)
        for who, text in asks:
            self._send(who, text)

    def _fetch(self, item: dict[str, Any]) -> tuple[fetch.Fetched, html_markdown.Page, bool]:
        """(the fetch, its page, whether a login wall stood in the way)."""
        url = str(item["url"])
        got = self.fetcher(url, fetch.MAX_PAGE_BYTES, fetch.TIMEOUT_S)
        walled = got.ok and fetch.platform(url) != "web" and fetch.login_page(got)
        if walled and self.browser is not None:
            # The clear second path: the local headless browser, only when turned on.
            rendered = self.browser(url)
            if rendered.ok and not fetch.login_page(rendered):
                got, walled = rendered, False
        page = (
            html_markdown.read(html_markdown.decode(got.body)) if got.ok else html_markdown.Page()
        )
        return got, page, walled

    def _one(self, item: dict[str, Any], domain: Domain) -> str:
        item_id, key = int(item["id"]), domain.key
        sender = str(item["actor"])
        if item["kind"] == "link":
            got, page, walled = self._fetch(item)
            if not got.ok:
                self.inbox.finish(item_id, key, store.FAILED, code=got.code or f"http_{got.status}")
                return store.FAILED
            if page.empty or (walled and not page.description):
                self.inbox.finish(
                    item_id, key, store.FAILED, code="login_required" if walled else "no_content"
                )
                self.inbox.update(item_id, status=store.NEEDS_TEXT)
                return store.FAILED
            summary_only = walled or page.summary_only
            fetched_at = self.clock().isoformat(timespec="seconds")
            self.inbox.update(
                item_id,
                fetched_at=fetched_at,
                fetch_method=got.method,
                http_status=got.status,
                final_url=got.final_url,
                content_sha256=got.sha256,
                summary_only=int(summary_only),
                title=item["title"] or page.title[:200],
            )
            earlier = self.inbox.seen_before(key, str(item["norm_url"]), got.sha256, item_id)
            if earlier is not None:
                self.inbox.finish(item_id, key, store.DUPLICATE, code=f"same_as_{earlier}")
                return store.DUPLICATE
            provenance = {
                "original_url": item["url"],
                "final_url": got.final_url,
                "sender": sender,
                "sender_name": item["sender_name"],
                "sent_at": item["received_at"],
                "fetched_at": fetched_at,
                "fetch_method": got.method,
                "http_status": got.status,
                "content_sha256": got.sha256,
                "summary_only": summary_only,
                "item": item_id,
                **({"note": item["note"]} if item["note"] else {}),
            }
            data = html_markdown.provenance_comment(provenance).encode("ascii") + got.body
            raw = self.inbox.dir / "raw" / f"{item_id}-{got.sha256[:12]}.html"
            raw.parent.mkdir(parents=True, exist_ok=True)
            if not raw.exists():
                raw.write_bytes(data)
            self.inbox.update(item_id, raw_path=str(raw))
            url = str(item["url"])
            name = f"{fetch.platform(url)}-{_slug(page.title or url)}-{item_id}.html"
            status = store.SUMMARY if summary_only else store.REVIEW
            return self._ingest(item_id, domain, name, data, "text/html", sender, status)
        if item["kind"] == "file":
            data = Path(str(item["file_path"])).read_bytes()
            digest = str(item["file_sha256"])
            earlier = self.inbox.seen_before(key, f"file:{digest}", digest, item_id)
            if earlier is not None:
                self.inbox.finish(item_id, key, store.DUPLICATE, code=f"same_as_{earlier}")
                return store.DUPLICATE
            return self._ingest(
                item_id, domain, str(item["file_name"]), data, None, sender, store.REVIEW
            )
        # A person's text for an item that only had a summary.
        text = self._text_source(item)
        return self._ingest(
            item_id,
            domain,
            f"note-{item['parent']}-{item_id}.md" if item["parent"] else f"text-{item_id}.md",
            text.encode("utf-8"),
            "text/markdown",
            sender,
            store.REVIEW,
        )

    def _text_source(self, item: dict[str, Any]) -> str:
        return (
            f"# {item['title'] or '補充內文'}\n\n"
            f"> 原始網址：{item['url'] or ''}\n"
            f"> 內容由傳送者 {item['actor']} 於 {item['received_at']} 以 Telegram 傳送"
            + (f"（補 #{item['parent']}）" if item["parent"] else "")
            + f"\n\n{item['note']}\n"
        )

    def _ingest(
        self,
        item_id: int,
        domain: Domain,
        name: str,
        data: bytes,
        media_type: str | None,
        sender: str,
        status: str,
    ) -> str:
        """Keep the bytes as a source in the domain's folder and start an AI ingest run
        that stops at review."""
        folder = homes.sources_dir(domain.home)
        who = f"{sender} via telegram"
        staging = Staging(self.workspace, domain.dataset)
        try:
            source = staging.add_source(
                name,
                content_base64=base64.b64encode(data).decode("ascii"),
                media_type=media_type,
                folder=folder,
                actor=who,
            )
        except BiStoreError as error:
            self.inbox.finish(
                item_id, domain.key, store.FAILED, code=error.code, message=error.message[:300]
            )
            return store.FAILED
        source_id = str(source["id"])
        try:
            run = ai_runs.start(
                self.workspace,
                domain.dataset,
                self.ai,
                kind="ingest",
                source_id=source_id,
                instructions=None,
                types=None,
                actor=who,
                folder=folder,
            )
        except BiStoreError as error:
            # The source stays; a person can start its ingest on the page.
            self.inbox.finish(
                item_id,
                domain.key,
                store.FAILED,
                source_id=source_id,
                code=error.code,
                message=error.message[:300],
            )
            return store.FAILED
        self.inbox.finish(item_id, domain.key, status, source_id=source_id, run_id=str(run["id"]))
        return status

    # -- review reminder -------------------------------------------------------------------------

    def waiting(self, key: str, dataset: str) -> tuple[int, set[tuple[str, str]]]:
        """(candidate cards still undecided in the domain's inbox runs, their senders)."""
        staging = Staging(self.workspace, dataset)
        count: int = 0
        senders: set[tuple[str, str]] = set()
        for result in self.inbox.results(domain=key):
            run_id = result["run_id"]
            if not run_id:
                continue
            run = staging.run_row(str(run_id))
            if run is None or run.get("status") not in ("review", "partial"):
                continue
            pending = sum(
                1
                for c in staging.candidates(str(run_id))
                if c.get("review") == "pending" and c.get("action") != "skip"
            )
            if pending:
                count += pending
                item = self.inbox.item(int(result["item"]))
                if item is not None:
                    senders.add(self._who(item))
        return count, senders

    def remind(self, key: str) -> int:
        """Tell the domain's reviewers (its items' senders) how many cards wait; how
        many were told."""
        domain = dom.by_key(dom.listed(self.workspace), key)
        if domain is None:
            return 0
        count, senders = self.waiting(key, domain.dataset)
        if not count:
            return 0
        where = WHERE.format(vault=domain.vault_title, label=domain.label)
        text = f"{domain.label} 有 {count} 張候選卡待審：在{where}審核，可按「全部接受並匯入」。"
        return sum(1 for who in sorted(senders) if self._send(who, text))

    # -- after an import -------------------------------------------------------------------------

    def after_commit(
        self, dataset: str, run_id: str, committed: dict[str, Any], bench: Any
    ) -> bool:
        """When an inbox run was imported: run the domain's tests and draw its Dashboard
        in the background, then tell the senders. False when the run is not the inbox's."""
        rows = self.inbox.results(run_id=run_id)
        if not rows or committed.get("already"):
            # Not the inbox's run, or a repeated press answered with the earlier write.
            return False
        key = str(rows[0]["domain"])
        domain = dom.by_key(dom.listed(self.workspace), key)
        if domain is None:
            return False
        senders = sorted(
            {self._who(i) for r in rows if (i := self.inbox.item(int(r["item"]))) is not None}
        )
        applied = committed.get("applied") or committed.get("run", {}).get("commit") or {}

        def work() -> None:
            tested = "沒有測試"
            if bench is not None:
                try:
                    from aep_bi.host import bi_bench

                    actor = senders[0][1] if senders else "bi-inbox"
                    report = bi_bench.run(
                        self.workspace,
                        domain.vault_id,
                        ask=bench.ask_for(domain.vault_id, actor),
                        extract=bench.extract_for(domain.vault_id, actor),
                        actor=f"{actor} via telegram",
                        home=domain.home,
                    )
                    tested = _tested(report)
                except Exception as failure:  # noqa: BLE001 - said in the result message
                    tested = f"測試沒有跑完（{type(failure).__name__}）"
            drawn = _dashboard(self.workspace, domain)
            text = (
                f"{domain.label} 已匯入：新建 {applied.get('created', 0)}、"
                f"更新 {applied.get('updated', 0)}。{tested}。{drawn}。"
            )
            for who in senders:
                self._send(who, text)

        background = getattr(bench, "background", None)
        if callable(background):
            background(f"BI 收集箱：{domain.label} 測試與 Dashboard", work)
        else:
            work()
        return True


def _tested(report: dict[str, Any]) -> str:
    if report.get("status") == "failed":
        return f"測試失敗（{report.get('error') or '原因不明'}）"
    total = int(report.get("total") or 0)
    passed = sum(
        1
        for r in report.get("results", [])
        if ((r.get("working") or {}).get("grade") or {}).get("passed") is True
    )
    cases = report.get("cases", [])
    return f"測試 {passed}/{total} 題通過" + (f"、{len(cases)} 個判讀案例" if cases else "")


def _dashboard(workspace: Path, domain: Domain) -> str:
    try:
        bi_store = BiStore(workspace, domain.dataset)
        reg = catalog.for_store(bi_store)
        if not reg.is_bi:
            return "這個知識庫沒有 Dashboard"
        name = homes.domain_of_folder(reg.domains, homes.sources_dir(domain.home)) or ""
        drawn = board.board(workspace, bi_store, name, False, {}, domain.home)
    except Exception as failure:  # noqa: BLE001 - said in the result message
        return f"Dashboard 沒有更新（{type(failure).__name__}）"
    sections = drawn.get("sections") or []
    return f"Dashboard 已更新（{len(sections)} 項分析）"


def collect_all(processor: Processor, keys: Sequence[str]) -> dict[str, Any]:
    return {key: processor.collect(key) for key in keys}
