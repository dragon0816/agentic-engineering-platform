"""The BI inbox: what a BI domain's Telegram collection bot receives, collected into that
domain (owner 2026-11-20, one bot per BI domain; docs/DECISIONS.md).

Receiving: links, files and words go to the bot's bound domain at once, `/links`,
`/unlink`, a Reply with text for a summary-only item. Processing at a domain's collect
time: fetched from fixtures (never the network), kept whole with provenance,
deduplicated, ingested to review and never further.
Reminders and the result after an import go only to the items' senders. All data is
fictional.
"""

from __future__ import annotations

import re
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_bi_ai_runs import Jobs
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok

from aep_bi.cards import html_markdown, source_markdown
from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.cards.staging import Staging
from aep_bi.host.bi_cards_api import route
from aep_bi.inbox import fetch, store
from aep_bi.inbox.bot import UNBOUND, Bot
from aep_bi.inbox.domains import listed
from aep_bi.inbox.process import Processor
from aep_bi.inbox.scheduler import Scheduler
from aep_bi.inbox.store import Inbox
from host_runtime.features import TelegramFile, TelegramItem

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bi_inbox"
ARTICLE = "https://news.example.com/5g/redcap?utm_source=line&fbclid=abc"
THREADS = "https://www.threads.net/@example.user/post/ABC123?igshid=x"
INSTAGRAM = "https://www.instagram.com/p/XYZ789/?igsh=abc"
LOGIN = "https://www.instagram.com/accounts/login/?next=/p/XYZ789/"
ALICE, BOB = "alice", "bob"
AIDC_BOT, WIRELESS_BOT = "bi_aidc", "bi_wireless"


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("no real network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def page(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class Web:
    """Fixture pages by address; counts each fetch."""

    def __init__(self, pages: dict[str, tuple[str, bytes]]) -> None:
        self.pages = pages
        self.fetched: list[str] = []

    def __call__(self, url: str, limit: int, timeout_s: float) -> fetch.Fetched:
        self.fetched.append(url)
        found = self.pages.get(url)
        if found is None:
            return fetch.Fetched(url, url, 404, b"", "", "http", "http_404")
        final, body = found
        return fetch.Fetched(url, final, 200, body, "text/html; charset=utf-8", "http")


def web() -> Web:
    return Web(
        {
            ARTICLE: (ARTICLE, page("web_article.html")),
            THREADS: (THREADS, page("threads_post.html")),
            INSTAGRAM: (INSTAGRAM, page("instagram_post.html")),
        }
    )


class Messages:
    """A messenger that knows only each bot's mapped actors, as `TelegramCollector.send`."""

    def __init__(self, mapped: tuple[str, ...] = (ALICE, BOB)) -> None:
        self.mapped = mapped
        self.sent: list[tuple[str, str, str]] = []

    def bots(self) -> tuple[Any, ...]:
        return ()

    def send(self, bot: str, actor: str, text: str) -> bool:
        if actor not in self.mapped or not bot:
            return False
        self.sent.append((bot, actor, text))
        return True

    def to(self, actor: str) -> list[str]:
        return [text for _, who, text in self.sent if who == actor]


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    shared = tmp_path / "shared"
    shared.mkdir()
    given = {"path": str(shared), "title": "Market", "purpose": "虛構", "schema": "bi.schema/v1.1"}
    made = _ok(_call(workspace, "POST", "/api/bi/vaults", {**given, "author": ALICE}))
    vault_id = made["vault"]["id"]
    for name in ("AIDC", "Wireless"):
        _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/homes", {"name": name}))
    inbox = Inbox(workspace)
    for label, bot_name in (("AIDC", AIDC_BOT), ("Wireless", WIRELESS_BOT)):
        domain = keys(workspace)[label]
        inbox.save_setting(domain, enabled=False, collect_at=None, review_at=None, bot=bot_name)
    return workspace


def keys(ws: Path) -> dict[str, str]:
    return {d.label: d.key for d in listed(ws)}


def dataset(ws: Path) -> str:
    return listed(ws)[0].dataset


def item(
    kind: str, text: str = "", actor: str = ALICE, bot: str = AIDC_BOT, **extra: Any
) -> TelegramItem:
    return TelegramItem(
        feature="bi-knowledge",
        bot=bot,
        target=extra.pop("target", ""),
        kind=kind,  # type: ignore[arg-type]
        actor=actor,
        text=text,
        received_at=datetime.now(UTC),
        **extra,
    )


def link(text: str, *urls: str, actor: str = ALICE, bot: str = AIDC_BOT) -> TelegramItem:
    return item("link", text, actor, bot, urls=urls or (text,))


def bot(ws: Path) -> Bot:
    return Bot(ws)


def processor(ws: Path, jobs: Jobs, messages: Messages, **extra: Any) -> Processor:
    ai = AiRuntime(model=lambda: (Scripted(), "test-model"), background=jobs)
    return Processor(ws, ai, messages, fetcher=extra.pop("fetcher", web()), **extra)


def queued(ws: Path, text: str, *urls: str, actor: str = ALICE, bot: str = AIDC_BOT) -> int:
    answer = Bot(ws).handle(link(text, *urls, actor=actor, bot=bot))
    found = re.search(r"#(\d+)", answer.text)
    assert found is not None, answer.text
    return int(found.group(1))


# -- the converter -------------------------------------------------------------------------------


def test_a_web_page_becomes_markdown_without_its_chrome() -> None:
    text = html_markdown.markdown(page("web_article.html").decode("utf-8"))
    assert text.startswith("# RedCap 模組出貨量今年成長三倍")
    assert "## 摘要" in text and "## 內文" in text and "- RF 一致性測試" in text
    assert "![圖片](https://news.example.com/img/redcap.jpg)" in text
    assert "tracking" not in text and "首頁" not in text and "analytics" not in text
    assert not html_markdown.read(page("web_article.html").decode()).summary_only


def test_threads_and_instagram_html_give_their_summary() -> None:
    threads = html_markdown.read(page("threads_post.html").decode())
    assert threads.summary_only and "Wi-Fi 7" in threads.description
    insta = html_markdown.read(page("instagram_post.html").decode())
    assert insta.summary_only and "UWB" in insta.description and insta.image
    walled = fetch.Fetched(LOGIN, LOGIN, 200, page("instagram_login.html"), "text/html", "http")
    assert fetch.login_page(walled)
    same_place = fetch.Fetched(INSTAGRAM, INSTAGRAM, 200, page("instagram_login.html"), "", "http")
    assert fetch.login_page(same_place)
    post = fetch.Fetched(INSTAGRAM, INSTAGRAM, 200, page("instagram_post.html"), "", "http")
    assert not fetch.login_page(post)


def test_addresses_lose_what_only_tracks_the_sharer() -> None:
    assert fetch.normalize(ARTICLE) == "https://news.example.com/5g/redcap"
    assert fetch.normalize("HTTPS://News.Example.com/a/?b=1&utm_medium=x#top") == (
        "https://news.example.com/a?b=1"
    )
    assert [fetch.platform(u) for u in (ARTICLE, THREADS, INSTAGRAM)] == [
        "web",
        "threads",
        "instagram",
    ]


def test_provenance_survives_any_page_encoding() -> None:
    comment = html_markdown.provenance_comment({"sender": "小明", "note": "a--b"})
    assert comment.isascii() and "--" not in comment[4:-5]
    value, rest = html_markdown.provenance_of(comment + "<p>x</p>")
    assert value == {"sender": "小明", "note": "a--b"} and rest == "<p>x</p>"


# -- receiving -----------------------------------------------------------------------------------


def test_everything_a_domain_bot_gets_goes_to_its_domain(ws: Path) -> None:
    got = bot(ws).handle(link(f"這篇給 PM {ARTICLE}", ARTICLE))
    assert got.text == "已收進 AIDC，尚未設定處理時間處理（#1）。"
    assert Inbox(ws).picks(1) == [
        {"item": 1, "domain": keys(ws)["AIDC"], "by": "bot", "at": Inbox(ws).picks(1)[0]["at"]}
    ]
    assert Inbox(ws).item(1)["note"] == "這篇給 PM"  # type: ignore[index]
    Inbox(ws).save_setting(
        keys(ws)["Wireless"], enabled=True, collect_at="07:30", review_at=None, bot=WIRELESS_BOT
    )
    said = bot(ws).handle(item("text", "展場聽到：三家廠商推 Wi-Fi 7 工業路由器", bot=WIRELESS_BOT))
    assert said.text.startswith("已收進 Wireless，") and "07:30處理（#2）" in said.text
    assert Inbox(ws).item(2)["kind"] == "text"  # type: ignore[index]
    assert Inbox(ws).picks(2)[0]["domain"] == keys(ws)["Wireless"]


def test_a_bot_without_binding_uses_its_target_or_says_so(ws: Path) -> None:
    by_target = bot(ws).handle(
        item("link", ARTICLE, bot="bi_other", target="wireless", urls=(ARTICLE,))
    )
    assert by_target.text.startswith("已收進 Wireless")
    nothing = bot(ws).handle(item("link", THREADS, bot="bi_none", urls=(THREADS,)))
    assert nothing.text == UNBOUND
    assert len(Inbox(ws).items()) == 1


def test_binding_a_bot_moves_it(ws: Path) -> None:
    Inbox(ws).save_setting(
        keys(ws)["Wireless"], enabled=False, collect_at=None, review_at=None, bot=AIDC_BOT
    )
    assert Inbox(ws).bound(AIDC_BOT) == keys(ws)["Wireless"]
    assert Inbox(ws).settings()[keys(ws)["AIDC"]].bot is None


def test_the_same_address_waiting_is_not_queued_twice(ws: Path) -> None:
    queued(ws, ARTICLE)
    again = bot(ws).handle(link("https://news.example.com/5g/redcap/"))
    assert again.text == "這個網址已經在佇列（#1），略過。"
    assert len(Inbox(ws).items()) == 1


def test_links_lists_and_unlink_withdraws_for_good(ws: Path) -> None:
    queued(ws, ARTICLE)
    queued(ws, THREADS)
    listing = bot(ws).handle(item("text", "/links"))
    assert "#1 " in listing.text and "待處理（尚未設定處理時間）" in listing.text
    assert bot(ws).handle(item("text", "/unlink 2")).text == "已撤回 #2。"
    assert bot(ws).handle(item("text", "/unlink #2")).text == "#2 已經撤回過了。"
    assert bot(ws).handle(item("text", "/unlink 1", actor=BOB)).text == "找不到你的 #1。"
    assert not Inbox(ws).claim(2, keys(ws)["AIDC"])
    assert bot(ws).handle(item("text", "/unlink")).text.startswith("用法")


def test_a_file_is_kept_as_sent(ws: Path) -> None:
    data = "# 會議紀錄\n\n客戶 A 公司表示正在評估 TSN。\n".encode()
    sent = item(
        "file",
        bot=WIRELESS_BOT,
        files=(
            TelegramFile("meeting.md", len(data), lambda: data),
            TelegramFile("clip.mp4", 10, lambda: b"x"),
        ),
    )
    answer = bot(ws).handle(sent)
    assert answer.text.startswith("已收進 Wireless") and "（#1）" in answer.text
    assert "clip.mp4（不支援這種檔案）" in answer.text
    kept = Inbox(ws).item(1)
    assert kept is not None and Path(kept["file_path"]).read_bytes() == data


def test_without_any_domain_the_bot_says_it_is_not_bound(tmp_path: Path) -> None:
    assert Bot(tmp_path).handle(link(ARTICLE)).text == UNBOUND


# -- processing ----------------------------------------------------------------------------------


def _markdown(ws: Path, source_id: str) -> str:
    staging = Staging(ws, dataset(ws))
    rev, _ = source_markdown.current(staging, source_id)
    return staging.markdown_text(source_id, rev)


def test_collect_keeps_the_page_with_provenance_and_stops_at_review(ws: Path) -> None:
    queued(ws, f"這篇給 PM {ARTICLE}", ARTICLE)
    jobs, messages, pages = Jobs(), Messages(), web()
    done = processor(ws, jobs, messages, fetcher=pages).collect(keys(ws)["AIDC"])
    assert done["review"] == 1 and pages.fetched == [ARTICLE]
    [result] = Inbox(ws).results(item_id=1)
    assert result["status"] == store.REVIEW
    staging = Staging(ws, dataset(ws))
    source = staging.source(result["source_id"])
    assert source is not None and source["name"].startswith("web-RedCap")
    raw = staging.source_bytes(result["source_id"]).decode("utf-8")
    provenance, rest = html_markdown.provenance_of(raw)
    assert rest.encode("utf-8") == page("web_article.html")  # kept whole
    assert provenance["original_url"] == ARTICLE and provenance["sender"] == ALICE
    assert provenance["note"] == "這篇給 PM" and provenance["fetch_method"] == "http"
    assert provenance["sent_at"] and provenance["fetched_at"]
    markdown = _markdown(ws, result["source_id"])
    assert f"> 原始網址：{ARTICLE}" in markdown and f"> 傳送者：{ALICE}" in markdown
    assert "電信商認證" in markdown
    run = staging.run_row(result["run_id"])
    assert run is not None and run["status"] == "extracting"
    jobs.run_all()
    after = staging.run_row(result["run_id"])
    assert after is not None and after["status"] == "review" and after.get("commit") is None
    assert messages.to(ALICE) == ["AIDC 收集完成：1 筆已轉換待審。"]
    # At most once: the next collect neither fetches nor adds anything.
    again = processor(ws, Jobs(), Messages(), fetcher=pages).collect(keys(ws)["AIDC"])
    assert again["review"] == 0 and pages.fetched == [ARTICLE]
    assert len(staging.sources()) == 1


def test_a_page_sent_again_is_kept_only_when_it_changed(ws: Path) -> None:
    aidc = keys(ws)["AIDC"]
    pages = web()
    queued(ws, ARTICLE)
    processor(ws, Jobs(), Messages(), fetcher=pages).collect(aidc)
    queued(ws, ARTICLE)
    processor(ws, Jobs(), Messages(), fetcher=pages).collect(aidc)
    assert Inbox(ws).results(item_id=2)[0]["status"] == store.DUPLICATE
    pages.pages[ARTICLE] = (
        ARTICLE,
        page("web_article.html").replace("三倍".encode(), "四倍".encode()),
    )
    queued(ws, ARTICLE)
    processor(ws, Jobs(), Messages(), fetcher=pages).collect(aidc)
    assert Inbox(ws).results(item_id=3)[0]["status"] == store.REVIEW
    assert len(Staging(ws, dataset(ws)).sources()) == 2


def test_threads_and_instagram_posts_are_summaries_and_their_senders_are_asked(ws: Path) -> None:
    wireless = keys(ws)["Wireless"]
    queued(ws, THREADS, bot=WIRELESS_BOT)
    queued(ws, INSTAGRAM, actor=BOB, bot=WIRELESS_BOT)
    messages = Messages()
    done = processor(ws, Jobs(), messages).collect(wireless)
    assert done["summary"] == 2
    threads = Inbox(ws).results(item_id=1)[0]
    markdown = _markdown(ws, threads["source_id"])
    assert "> 只取得摘要" in markdown and "Wi-Fi 7 的工業路由器" in markdown
    assert Staging(ws, dataset(ws)).source(threads["source_id"])["name"].startswith("threads-")  # type: ignore[index]
    insta = _markdown(ws, Inbox(ws).results(item_id=2)[0]["source_id"])
    assert "FiRa 2.0" in insta and "![圖片](https://scontent.example.net/ig/post.jpg)" in insta
    assert any(t.startswith("#1 只取得摘要") and "請回覆這則訊息" in t for t in messages.to(ALICE))
    assert any(t.startswith("#2 只取得摘要") for t in messages.to(BOB))
    assert not any("#2" in t for t in messages.to(ALICE))


def test_a_reply_adds_the_text_and_the_next_collect_takes_it(ws: Path) -> None:
    wireless = keys(ws)["Wireless"]
    queued(ws, THREADS, bot=WIRELESS_BOT)
    messages = Messages()
    processor(ws, Jobs(), messages).collect(wireless)
    asked = next(t for t in messages.to(ALICE) if t.startswith("#1"))
    answer = bot(ws).handle(
        item("reply", "完整貼文：三家廠商展示 Wi-Fi 7 工業路由器。", bot=WIRELESS_BOT, quoted=asked)
    )
    assert answer.text.startswith("已補上 #1 的內文（#2）")
    # A Reply to anything else is just words for the domain.
    other = bot(ws).handle(item("reply", "隨便說說", bot=WIRELESS_BOT, quoted="沒有編號的訊息"))
    assert other.text.startswith("已收進 Wireless") and "（#3）" in other.text
    processor(ws, Jobs(), Messages()).collect(wireless)
    note = Inbox(ws).results(item_id=2)[0]
    assert note["status"] == store.REVIEW
    markdown = _markdown(ws, note["source_id"])
    assert "內容由傳送者 alice" in markdown and "三家廠商展示 Wi-Fi 7" in markdown
    assert f"> 原始網址：{THREADS}" in markdown


def test_an_instagram_login_wall_needs_text_unless_the_browser_is_on(ws: Path) -> None:
    wireless = keys(ws)["Wireless"]
    walled = Web({INSTAGRAM: (LOGIN, page("instagram_login.html"))})
    queued(ws, INSTAGRAM, bot=WIRELESS_BOT)
    messages = Messages()
    processor(ws, Jobs(), messages, fetcher=walled).collect(wireless)
    result = Inbox(ws).results(item_id=1)[0]
    assert (result["status"], result["code"]) == (store.FAILED, "login_required")
    assert Inbox(ws).item(1)["status"] == store.NEEDS_TEXT  # type: ignore[index]
    assert any(t.startswith("#1 沒有取得內容") for t in messages.to(ALICE))
    # The browser path: a second item, the rendered post.
    rendered = page("instagram_rendered.html")
    opened: list[str] = []

    def browser(url: str) -> fetch.Fetched:
        opened.append(url)
        return fetch.Fetched(url, INSTAGRAM, 200, rendered, "text/html", "browser")

    other = "https://www.instagram.com/p/OTHER1/"
    walled.pages[other] = (LOGIN, page("instagram_login.html"))
    queued(ws, other, bot=WIRELESS_BOT)
    processor(ws, Jobs(), Messages(), fetcher=walled, browser=browser).collect(wireless)
    done = Inbox(ws).results(item_id=2)[0]
    assert done["status"] == store.REVIEW and opened == [other]
    assert "電池壽命五年" in _markdown(ws, done["source_id"])


def test_files_go_in_as_uploaded_sources(ws: Path) -> None:
    data = "# 會議紀錄\n\n客戶 A 公司表示正在評估 TSN。\n".encode()
    sent = item("file", files=(TelegramFile("meeting.md", len(data), lambda: data),))
    bot(ws).handle(sent)
    bot(ws).handle(sent)  # the same file again
    processor(ws, Jobs(), Messages()).collect(keys(ws)["AIDC"])
    statuses = [Inbox(ws).results(item_id=n)[0]["status"] for n in (1, 2)]
    assert statuses == [store.REVIEW, store.DUPLICATE]
    [source] = Staging(ws, dataset(ws)).sources()
    assert source["name"] == "meeting.md" and source["by"] == "alice via telegram"


# -- settings, schedule, reminder and result -----------------------------------------------------


def test_settings_take_two_times_and_a_switch(ws: Path) -> None:
    aidc = keys(ws)["AIDC"]
    body = {"domain": aidc, "enabled": True, "collect_at": "07:30", "review_at": "17:00"}
    saved = _ok(route(ws, ALICE, "POST", "/api/bi/inbox/settings", {}, body))
    assert saved["domain"]["collect_at"] == "07:30" and saved["domain"]["enabled"]
    assert saved["domain"]["bot"] is None  # no bot chosen this time
    unknown = route(ws, ALICE, "POST", "/api/bi/inbox/settings", {}, {**body, "bot": "nope"})
    assert unknown[0] == 404 and unknown[1]["code"] == "bot_unknown"
    shown = _ok(route(ws, ALICE, "GET", "/api/bi/inbox", {"dataset": dataset(ws)}, None))
    assert {d["label"] for d in shown["domains"]} >= {"AIDC", "Wireless"}
    bad = route(ws, ALICE, "POST", "/api/bi/inbox/settings", {}, {**body, "collect_at": "7點"})
    assert bad[0] == 400 and bad[1]["code"] == "time_invalid"
    off = route(ws, ALICE, "POST", "/api/bi/inbox/settings", {}, {**body, "collect_at": None})
    assert off[1]["code"] == "collect_time_missing"


def test_the_schedule_runs_each_time_once(ws: Path) -> None:
    aidc = keys(ws)["AIDC"]
    Inbox(ws).save_setting(aidc, enabled=True, collect_at="07:30", review_at="17:00")
    saved_local = datetime.now().astimezone().replace(hour=6, minute=0, second=0, microsecond=0)
    with Inbox(ws)._db() as db:
        db.execute("UPDATE settings SET saved_at = ?", (saved_local.astimezone(UTC).isoformat(),))
    started: list[tuple[str, str]] = []
    clock = [saved_local.replace(hour=7, minute=31)]

    def job(kind: str, key: str) -> Callable[[], None]:
        return lambda: started.append((kind, key))

    def run(title: str, work: Callable[[], None]) -> None:
        work()

    scheduler = Scheduler(ws, job, run, clock=lambda: clock[0])
    assert scheduler.tick() == [("collect", aidc)]
    assert scheduler.tick() == []  # claimed once
    assert Scheduler(ws, job, run, clock=lambda: clock[0]).tick() == []  # a restart too
    clock[0] = saved_local.replace(hour=17, minute=5)
    assert scheduler.tick() == [("review", aidc)]
    assert started == [("collect", aidc), ("review", aidc)]
    Inbox(ws).save_setting(aidc, enabled=False, collect_at="07:30", review_at="17:00")
    clock[0] = clock[0] + timedelta(days=1)
    assert scheduler.tick() == []


def _reviewable(ws: Path, actor: str, url: str, answer: dict[str, Any]) -> str:
    aidc = keys(ws)["AIDC"]
    queued(ws, url, actor=actor)
    jobs = Jobs()
    ai = AiRuntime(model=lambda: (Scripted(answer), "test-model"), background=jobs)
    Processor(ws, ai, Messages(), fetcher=web()).collect(aidc)
    jobs.run_all()
    return str(Inbox(ws).results(domain=aidc)[-1]["run_id"])


SIGNAL = {
    "candidates": [
        {
            "entity_type": "Technology",
            "name": "RedCap",
            "fields": {"summary": {"value": "5G RedCap", "basis": "fact", "quote": "5G RedCap"}},
        }
    ]
}


def test_the_reminder_goes_to_the_senders_only(ws: Path) -> None:
    run_id = _reviewable(ws, BOB, ARTICLE, SIGNAL)
    staging = Staging(ws, dataset(ws))
    assert staging.run_row(run_id)["status"] == "review"  # type: ignore[index]
    pending = [c for c in staging.candidates(run_id) if c["review"] == "pending"]
    assert pending
    messages = Messages(mapped=(BOB,))
    told = Processor(ws, None, messages).remind(keys(ws)["AIDC"])
    assert told == 1 and messages.sent == [
        (
            AIDC_BOT,
            BOB,
            f"AIDC 有 {len(pending)} 張候選卡待審：在這台電腦的 Agent Web → BI（知識庫 Market／"
            "領域 AIDC）審核，可按「全部接受並匯入」。",
        )
    ]
    # Someone the bot does not know is never messaged.
    nobody = Messages(mapped=())
    assert Processor(ws, None, nobody).remind(keys(ws)["AIDC"]) == 0 and nobody.sent == []


class Bench:
    def __init__(self) -> None:
        self.ran: list[str] = []

    def ask_for(self, vault_id: str, actor: str) -> Any:
        self.ran.append(vault_id)
        return lambda question, side: {"ok": True, "answer": ""}

    def extract_for(self, vault_id: str, actor: str) -> Any:
        return lambda case: []

    def background(self, title: str, work: Callable[[], None]) -> None:
        work()


def test_an_import_runs_the_domains_tests_and_tells_the_senders(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aep_bi.inbox import runtime

    run_id = _reviewable(ws, BOB, ARTICLE, SIGNAL)
    messages = Messages()
    monkeypatch.setattr(runtime.RUNTIME, "messenger", messages)
    staging = Staging(ws, dataset(ws))
    ids = [c["id"] for c in staging.candidates(run_id)]
    bench = Bench()
    _ok(
        route(
            ws,
            ALICE,
            "POST",
            f"/api/bi/runs/{run_id}/accept",
            {},
            {"dataset": dataset(ws), "ids": ids},
            None,
            None,
            bench,
        )
    )
    _ok(
        route(
            ws,
            ALICE,
            "POST",
            f"/api/bi/runs/{run_id}/commit",
            {},
            {"dataset": dataset(ws)},
            None,
            None,
            bench,
        )
    )
    assert bench.ran and len(messages.to(BOB)) == 1
    text = messages.to(BOB)[0]
    assert text.startswith("AIDC 已匯入：新建 ") and "測試 " in text and "Dashboard" in text
    assert messages.to(ALICE) == []
    # Pressed again: the host answers with the same write and nothing is sent twice.
    _ok(
        route(
            ws,
            ALICE,
            "POST",
            f"/api/bi/runs/{run_id}/commit",
            {},
            {"dataset": dataset(ws)},
            None,
            None,
            bench,
        )
    )
    assert len(messages.to(BOB)) == 1


def test_a_page_run_that_is_not_the_inboxs_sends_nothing(ws: Path) -> None:
    messages = Messages()
    assert not Processor(ws, None, messages).after_commit(dataset(ws), "run-x", {}, Bench())
    assert messages.sent == []


def test_a_shared_link_end_to_end_through_a_collection_bot(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_telegram_collect import collector, message, wire

    from aep_bi.feature import FEATURE
    from aep_bi.inbox import runtime
    from channels import telegram_collect
    from host_runtime.features import FeatureSet

    # This test's workspace, no schedule thread, and nothing left behind for others.
    for name, value in (("workspace", ws), ("scheduler", object()), ("messenger", None)):
        monkeypatch.setattr(runtime.RUNTIME, name, value)
    monkeypatch.setattr(runtime.RUNTIME, "host", None)
    bot_ = collector(ws.parent / "telegram", [[message(1, f"看這篇 {ARTICLE}")]], name=AIDC_BOT)
    telegram_collect.attach([bot_], FeatureSet([FEATURE]), None)
    assert runtime.RUNTIME.messenger is not None
    assert [b.name for b in runtime.RUNTIME.messenger.bots()] == [AIDC_BOT]
    handled = bot_poll(bot_)
    assert handled == [(1, "answered")]
    said = wire(bot_).sent()
    assert said == ["已收進 AIDC，尚未設定處理時間處理（#1）。"]
    assert Inbox(ws).item(1)["actor"] == "engineer"  # type: ignore[index]
    assert Inbox(ws).item(1)["bot"] == AIDC_BOT  # type: ignore[index]


def bot_poll(bot_: Any) -> Any:
    import asyncio

    return asyncio.run(bot_.poll_once())


# -- questions (owner 2026-11-21) ------------------------------------------------------------------


def test_a_question_gets_bi_query_scoped_to_the_bots_domain(ws: Path) -> None:
    import asyncio

    from aep_bi.inbox.bot import QUERY_TOOL
    from agent.gateway import HostTool, HostToolOutcome
    from host_runtime.features import TelegramAnswer, TelegramQuestion
    from models.contracts import ModelTool

    seen: list[dict[str, Any]] = []

    async def query(context: Any, arguments: dict[str, Any]) -> HostToolOutcome:
        seen.append(arguments)
        return HostToolOutcome(status="succeeded", data={})

    def tool(name: str) -> HostTool:
        return HostTool(
            ModelTool(name=name, description="d", input_contract=f"host.{name}.v1"), query
        )

    asked = bot(ws).question(item("text", "液冷？"), [tool("bi__atlas_show"), tool(QUERY_TOOL)])
    assert isinstance(asked, TelegramQuestion)
    assert [t.tool.name for t in asked.tools] == [QUERY_TOOL]
    assert "「AIDC」" in asked.guidance and "say so plainly" in asked.guidance
    # Whatever dataset the model names, the call reads the bot's domain's dataset.
    asyncio.run(asked.tools[0].handler(None, {"text": "液冷", "dataset": "demo"}))
    assert seen == [{"text": "液冷", "dataset": dataset(ws)}]
    # No bi__query among the Host's tools: nothing to offer; an unbound bot says so.
    assert bot(ws).question(item("text", "液冷？"), [tool("bi__atlas_show")]) is None
    unbound = bot(ws).question(item("text", "液冷？", bot="bi_other"), [tool(QUERY_TOOL)])
    assert unbound == TelegramAnswer(UNBOUND)


def test_the_feature_offers_no_question_tool_while_the_bi_skill_is_off(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from aep_bi.feature import FEATURE
    from aep_bi.inbox import runtime

    monkeypatch.setattr(runtime.RUNTIME, "workspace", ws)
    # No switched-on BI Skill on this gateway: `bi_cards_tools` offers nothing.
    assert FEATURE.telegram_question(item("text", "液冷？"), None, SimpleNamespace()) is None


def test_the_bot_form_sets_its_domains_collect_time_in_one_save(ws: Path) -> None:
    # Settings → Agents → 新增 BI 收集 bot (owner 2026-11-21): the target names one domain.
    path = "/api/bi/inbox/bot-time"
    inbox = Inbox(ws)
    aidc = keys(ws)["AIDC"]
    inbox.save_setting(aidc, enabled=False, collect_at=None, review_at="09:00", bot=AIDC_BOT)
    body = {"bot": "bi_new", "target": "aidc", "enabled": True, "collect_at": "18:00"}
    # Checked first, nothing written.
    checked = _ok(route(ws, ALICE, "POST", path, {}, {**body, "dry_run": True}))
    assert checked["domain"] == {"domain": aidc, "label": "AIDC"}
    assert inbox.settings()[aidc].bot == AIDC_BOT
    saved = _ok(route(ws, ALICE, "POST", path, {}, body))["domain"]
    assert (saved["bot"], saved["enabled"], saved["collect_at"]) == ("bi_new", True, "18:00")
    assert saved["review_at"] == "09:00" and "18:00" in saved["next"]
    assert inbox.bound("bi_new") == aidc and inbox.bound(AIDC_BOT) is None
    # Not exactly one domain, a bad time, 開啟 without a time: said, nothing written.
    unknown = route(ws, ALICE, "POST", path, {}, {**body, "target": "robotics"})
    assert unknown[0] == 409 and unknown[1]["code"] == "domain_unresolved"
    assert "找不到領域「robotics」" in unknown[1]["message"]
    bad = route(ws, ALICE, "POST", path, {}, {**body, "collect_at": "6pm"})
    assert bad[1]["code"] == "time_invalid"
    missing = route(ws, ALICE, "POST", path, {}, {**body, "collect_at": None})
    assert missing[1]["code"] == "collect_time_missing"
    assert inbox.settings()[aidc].collect_at == "18:00"


def test_a_target_two_domains_share_is_refused_with_both_names() -> None:
    from aep_bi.inbox.api import unresolved
    from aep_bi.inbox.domains import Domain

    two = [
        Domain("v1:applications/aidc", "v1", "vault-v1", "applications/aidc", "A／AIDC"),
        Domain("v2:applications/aidc", "v2", "vault-v2", "applications/aidc", "B／AIDC"),
    ]
    said = unresolved("aidc", two)
    assert "對到 2 個領域（A／AIDC、B／AIDC）" in said and "知識庫／領域" in said
