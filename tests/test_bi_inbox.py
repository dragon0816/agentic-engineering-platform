"""The BI inbox: links and files sent to the Telegram bot, collected into BI domains
(docs/phases/TELEGRAM_LINK_COLLECTION_ASSESSMENT_20261119.md §8, owner consent 2026-11-19).

Receiving: domain buttons with the AI's suggestion first, multi-select, `#tag`, the
person's default, `/bi link|links|unlink|domain`, a Reply with text for a summary-only
item. Processing at a domain's collect time: fetched from fixtures (never the network),
kept whole with provenance, deduplicated, ingested to review and never further.
Reminders and the result after an import go only to the items' senders. All data is
fictional.
"""

from __future__ import annotations

import json
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
from aep_bi.inbox.bot import Bot
from aep_bi.inbox.domains import listed
from aep_bi.inbox.process import Processor
from aep_bi.inbox.scheduler import Scheduler
from aep_bi.inbox.store import Inbox
from host_runtime.features import TelegramAnswer, TelegramFile, TelegramItem

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bi_inbox"
ARTICLE = "https://news.example.com/5g/redcap?utm_source=line&fbclid=abc"
THREADS = "https://www.threads.net/@example.user/post/ABC123?igshid=x"
INSTAGRAM = "https://www.instagram.com/p/XYZ789/?igsh=abc"
LOGIN = "https://www.instagram.com/accounts/login/?next=/p/XYZ789/"
ALICE, BOB = "alice", "bob"


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


class Suggesting:
    """The suggestion model: always answers with one domain number."""

    def __init__(self, number: int, confidence: float) -> None:
        self.answer = json.dumps({"domain": number, "confidence": confidence})
        self.calls = 0

    def generate(self, request: Any) -> Any:
        from models.contracts import ModelResponse

        self.calls += 1
        return ModelResponse(trace=request.trace, model_alias="m", text=self.answer)

    def stream(self, request: Any) -> Any:
        raise NotImplementedError


class Messages:
    """A messenger that knows only mapped actors, as `TelegramIngress.send`."""

    def __init__(self, mapped: tuple[str, ...] = (ALICE, BOB)) -> None:
        self.mapped = mapped
        self.sent: list[tuple[str, str]] = []

    def send(self, actor: str, text: str, buttons: Any = ()) -> bool:
        if actor not in self.mapped:
            return False
        self.sent.append((actor, text))
        return True

    def to(self, actor: str) -> list[str]:
        return [text for who, text in self.sent if who == actor]


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
    return workspace


def keys(ws: Path) -> dict[str, str]:
    return {d.label: d.key for d in listed(ws)}


def dataset(ws: Path) -> str:
    return listed(ws)[0].dataset


def item(kind: str, text: str = "", actor: str = ALICE, **extra: Any) -> TelegramItem:
    return TelegramItem(kind=kind, actor=actor, text=text, received_at=datetime.now(UTC), **extra)  # type: ignore[arg-type]


def link(text: str, *urls: str, actor: str = ALICE) -> TelegramItem:
    return item("link", text, actor, urls=urls or (text,))


def tap(data: str, actor: str = ALICE) -> TelegramItem:
    return item("tap", actor=actor, data=data)


def command(name: str, text: str = "", actor: str = ALICE) -> TelegramItem:
    return item("command", text, actor, data=f"bi {name}")


def bot(ws: Path, model: Any = None) -> Bot:
    return Bot(ws, model=lambda: None if model is None else (model, "m"), preview=web())


def payloads(answer: TelegramAnswer) -> list[tuple[str, str]]:
    return [button for row in answer.buttons for button in row]


def processor(ws: Path, jobs: Jobs, messages: Messages, **extra: Any) -> Processor:
    ai = AiRuntime(model=lambda: (Scripted(), "test-model"), background=jobs)
    return Processor(ws, ai, messages, fetcher=extra.pop("fetcher", web()), **extra)


def queued(ws: Path, text: str, *urls: str, actor: str = ALICE) -> int:
    answer = bot(ws).handle(link(text, *urls, actor=actor))
    assert answer is not None
    return int(answer.text.split()[0].lstrip("#"))


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


def test_a_link_asks_with_the_suggestion_first_and_one_tap_decides(ws: Path) -> None:
    model = Suggesting(2, 0.9)  # 2 = Wireless
    answer = bot(ws, model).handle(link(ARTICLE))
    assert answer is not None and model.calls == 1
    lines = answer.text.splitlines()
    assert lines[0] == "#1 RedCap 模組出貨量今年成長三倍"
    assert lines[-1] == "收進哪個領域？（可複選）"
    buttons = payloads(answer)
    assert buttons[0] == ("Wireless（建議）", "bi.t.1.0")
    assert ("更多…", "bi.m.1") in buttons or len(listed(ws)) <= len(buttons)
    assert Inbox(ws).picks(1) == []
    picked = bot(ws).handle(tap("bi.t.1.0"))
    assert picked is not None and picked.edit
    assert picked.text.splitlines()[-1] == "已收進 Wireless，尚未設定處理時間處理"
    assert payloads(picked)[0][0] == "✓ Wireless"
    assert [p["domain"] for p in Inbox(ws).picks(1)] == [keys(ws)["Wireless"]]


def test_several_domains_and_taking_one_back(ws: Path) -> None:
    Inbox(ws).save_setting(keys(ws)["AIDC"], enabled=True, collect_at="07:30", review_at="17:00")
    bot(ws).handle(link(ARTICLE))
    offered = Inbox(ws).item(1)["offered"]  # type: ignore[index]
    first, second = offered.index(keys(ws)["AIDC"]), offered.index(keys(ws)["Wireless"])
    bot(ws).handle(tap(f"bi.t.1.{first}"))
    both = bot(ws).handle(tap(f"bi.t.1.{second}"))
    assert (
        both is not None
        and "已收進 AIDC（" in both.text
        and "Wireless（尚未設定處理時間）" in both.text
    )
    assert {p["domain"] for p in Inbox(ws).picks(1)} == {keys(ws)["AIDC"], keys(ws)["Wireless"]}
    back = bot(ws).handle(tap(f"bi.t.1.{second}"))
    assert back is not None and "Wireless" not in back.text.splitlines()[-1]
    assert [p["domain"] for p in Inbox(ws).picks(1)] == [keys(ws)["AIDC"]]


def test_more_shows_every_domain(ws: Path) -> None:
    bot(ws).handle(link(ARTICLE))
    more = bot(ws).handle(tap("bi.m.1"))
    assert more is not None and more.edit
    labels = [label for label, _ in payloads(more)]
    assert {d.label for d in listed(ws)} <= set(labels) and "更多…" not in labels


def test_a_tag_or_the_default_decides_without_asking(ws: Path) -> None:
    tagged = bot(ws).handle(link(f"#aidc {ARTICLE}", ARTICLE))
    assert tagged is not None and "收進哪個領域" not in tagged.text
    assert Inbox(ws).picks(1)[0]["by"] == "tag"
    set_default = bot(ws).handle(command("domain", "wireless"))
    assert set_default is not None and set_default.text.startswith("預設領域：Wireless")
    by_default = bot(ws).handle(link(THREADS))
    assert by_default is not None and "已收進 Wireless" in by_default.text
    assert Inbox(ws).picks(2)[0]["by"] == "default"
    cleared = bot(ws).handle(command("domain", "無"))
    assert cleared is not None and Inbox(ws).default(ALICE) is None


def test_bi_link_names_its_domain(ws: Path) -> None:
    answer = bot(ws).handle(command("link", f"aidc {ARTICLE} 這篇給 PM"))
    assert answer is not None and "已收進 AIDC" in answer.text
    assert Inbox(ws).item(1)["note"] == "這篇給 PM"  # type: ignore[index]
    unknown = bot(ws).handle(command("link", f"marine {THREADS}"))
    assert unknown is not None and unknown.text.startswith("找不到領域「marine」")
    usage = bot(ws).handle(command("link", "aidc"))
    assert usage is not None and usage.text.startswith("用法")


def test_the_same_address_waiting_is_not_queued_twice(ws: Path) -> None:
    queued(ws, ARTICLE)
    again = bot(ws).handle(link("https://news.example.com/5g/redcap/"))
    assert again is not None and again.text == "這個網址已經在佇列（#1），略過。"
    assert len(Inbox(ws).items()) == 1


def test_links_lists_and_unlink_withdraws_for_good(ws: Path) -> None:
    queued(ws, f"#aidc {ARTICLE}", ARTICLE)
    queued(ws, THREADS)
    listing = bot(ws).handle(command("links"))
    assert listing is not None
    assert "#1 RedCap 模組出貨量今年成長三倍：待處理：AIDC" in listing.text
    assert "#2" in listing.text and "待選領域" in listing.text
    assert bot(ws).handle(command("unlink", "2")).text == "已撤回 #2。"  # type: ignore[union-attr]
    assert bot(ws).handle(command("unlink", "#2")).text == "#2 已經撤回過了。"  # type: ignore[union-attr]
    assert bot(ws, None).handle(command("unlink", "1", actor=BOB)).text == "找不到你的 #1。"  # type: ignore[union-attr]
    assert not Inbox(ws).claim(2, keys(ws)["AIDC"])
    tapped = bot(ws).handle(tap("bi.t.2.0"))
    assert tapped is not None and tapped.text.endswith("已撤回。")


def test_a_file_is_kept_as_sent(ws: Path) -> None:
    data = "# 會議紀錄\n\n客戶 A 公司表示正在評估 TSN。\n".encode()
    sent = item(
        "file",
        "#wireless",
        files=(
            TelegramFile("meeting.md", len(data), lambda: data),
            TelegramFile("clip.mp4", 10, lambda: b"x"),
        ),
    )
    answer = bot(ws).handle(sent)
    assert answer is not None and "#1 meeting.md" in answer.text
    assert "clip.mp4（不支援這種檔案）" in answer.text
    kept = Inbox(ws).item(1)
    assert kept is not None and Path(kept["file_path"]).read_bytes() == data


def test_without_any_domain_a_link_stays_a_message(tmp_path: Path) -> None:
    assert Bot(tmp_path, preview=web()).handle(link(ARTICLE)) is None
    told = Bot(tmp_path, preview=web()).handle(command("domain"))
    assert told is not None and "還沒有 BI 知識庫的領域" in told.text


# -- processing ----------------------------------------------------------------------------------


def _markdown(ws: Path, source_id: str) -> str:
    staging = Staging(ws, dataset(ws))
    rev, _ = source_markdown.current(staging, source_id)
    return staging.markdown_text(source_id, rev)


def test_collect_keeps_the_page_with_provenance_and_stops_at_review(ws: Path) -> None:
    queued(ws, f"#aidc 這篇給 PM {ARTICLE}", ARTICLE)
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
    queued(ws, f"#aidc {ARTICLE}", ARTICLE)
    processor(ws, Jobs(), Messages(), fetcher=pages).collect(aidc)
    queued(ws, f"#aidc {ARTICLE}", ARTICLE)
    processor(ws, Jobs(), Messages(), fetcher=pages).collect(aidc)
    assert Inbox(ws).results(item_id=2)[0]["status"] == store.DUPLICATE
    pages.pages[ARTICLE] = (
        ARTICLE,
        page("web_article.html").replace("三倍".encode(), "四倍".encode()),
    )
    queued(ws, f"#aidc {ARTICLE}", ARTICLE)
    processor(ws, Jobs(), Messages(), fetcher=pages).collect(aidc)
    assert Inbox(ws).results(item_id=3)[0]["status"] == store.REVIEW
    assert len(Staging(ws, dataset(ws)).sources()) == 2


def test_threads_and_instagram_posts_are_summaries_and_their_senders_are_asked(ws: Path) -> None:
    wireless = keys(ws)["Wireless"]
    queued(ws, f"#wireless {THREADS}", THREADS)
    queued(ws, f"#wireless {INSTAGRAM}", INSTAGRAM, actor=BOB)
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
    queued(ws, f"#wireless {THREADS}", THREADS)
    messages = Messages()
    processor(ws, Jobs(), messages).collect(wireless)
    asked = next(t for t in messages.to(ALICE) if t.startswith("#1"))
    answer = bot(ws).handle(
        item("reply", "完整貼文：三家廠商展示 Wi-Fi 7 工業路由器。", quoted=asked)
    )
    assert answer is not None and answer.text.startswith("已補上 #1 的內文（#2）")
    assert bot(ws).handle(item("reply", "隨便說說", quoted="沒有編號的訊息")) is None
    processor(ws, Jobs(), Messages()).collect(wireless)
    note = Inbox(ws).results(item_id=2)[0]
    assert note["status"] == store.REVIEW
    markdown = _markdown(ws, note["source_id"])
    assert "內容由傳送者 alice" in markdown and "三家廠商展示 Wi-Fi 7" in markdown
    assert f"> 原始網址：{THREADS}" in markdown


def test_an_instagram_login_wall_needs_text_unless_the_browser_is_on(ws: Path) -> None:
    wireless = keys(ws)["Wireless"]
    walled = Web({INSTAGRAM: (LOGIN, page("instagram_login.html"))})
    queued(ws, f"#wireless {INSTAGRAM}", INSTAGRAM)
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
    queued(ws, f"#wireless {other}", other)
    processor(ws, Jobs(), Messages(), fetcher=walled, browser=browser).collect(wireless)
    done = Inbox(ws).results(item_id=2)[0]
    assert done["status"] == store.REVIEW and opened == [other]
    assert "電池壽命五年" in _markdown(ws, done["source_id"])


def test_untapped_items_take_a_confident_suggestion_else_unassigned(ws: Path) -> None:
    aidc = keys(ws)["AIDC"]
    sure = Bot(ws, model=lambda: (Suggesting(1, 0.9), "m"), preview=web())
    unsure = Bot(ws, model=lambda: (Suggesting(1, 0.3), "m"), preview=web())
    sure.handle(link(ARTICLE))
    unsure.handle(link(THREADS))
    done = processor(ws, Jobs(), Messages()).collect(aidc)
    assert (done["suggested"], done["unassigned"], done["review"]) == (1, 1, 1)
    assert Inbox(ws).picks(1)[0]["by"] == "ai"
    assert Inbox(ws).item(2)["status"] == store.UNASSIGNED  # type: ignore[index]
    shown = _ok(route(ws, ALICE, "GET", "/api/bi/inbox", {"dataset": dataset(ws)}, None))
    assert [i["id"] for i in shown["unassigned"]] == [2]
    assert {d["label"] for d in shown["domains"]} >= {"AIDC", "Wireless"}
    _ok(route(ws, ALICE, "POST", "/api/bi/inbox/assign", {}, {"item": 2, "domain": aidc}))
    assert Inbox(ws).item(2)["status"] == store.QUEUED  # type: ignore[index]
    processor(ws, Jobs(), Messages()).collect(aidc)
    assert Inbox(ws).results(item_id=2)[0]["status"] == store.SUMMARY


def test_files_go_in_as_uploaded_sources(ws: Path) -> None:
    data = "# 會議紀錄\n\n客戶 A 公司表示正在評估 TSN。\n".encode()
    sent = item("file", "#aidc", files=(TelegramFile("meeting.md", len(data), lambda: data),))
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
    queued(ws, f"#aidc {url}", url, actor=actor)
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


def test_a_shared_link_end_to_end_through_the_bot(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update

    from aep_bi.feature import FEATURE
    from aep_bi.inbox import runtime
    from host_runtime.features import FeatureSet

    # This test's workspace, no schedule thread, and nothing left behind for others.
    for name, value in (("workspace", ws), ("scheduler", object()), ("messenger", None)):
        monkeypatch.setattr(runtime.RUNTIME, name, value)
    monkeypatch.setattr(runtime.RUNTIME, "host", None)
    monkeypatch.setattr(fetch, "http_fetch", web())
    tapped = {
        "update_id": 2,
        "callback_query": {
            "id": "cb-2",
            "from": {"id": OWNER, "is_bot": False},
            "message": {"message_id": 1, "chat": {"id": OWNER, "type": "private"}, "text": "q"},
            "data": "fi:bi.t.1.0",
        },
    }
    transport = FakeTransport([[update(1, OWNER, f"看這篇 {ARTICLE}")], [tapped]])
    bot_ingress, _agent, _runner = ingress(ws.parent / "telegram", transport)
    bot_ingress.attach_features(FeatureSet([FEATURE]), None)
    assert runtime.RUNTIME.messenger is bot_ingress
    poll(bot_ingress)
    asked = [p for url, p in transport.calls if url.endswith("/sendMessage")][-1]
    assert asked["text"].startswith("#1 RedCap 模組出貨量今年成長三倍")
    first = asked["reply_markup"]["inline_keyboard"][0][0]
    assert first["callback_data"] == "fi:bi.t.1.0"
    poll(bot_ingress)
    edited = [p for url, p in transport.calls if url.endswith("/editMessageText")][-1]
    assert "已收進" in edited["text"] and edited["message_id"] == 1
    assert Inbox(ws).item(1)["actor"] == "engineer"  # type: ignore[index]
    assert len(Inbox(ws).picks(1)) == 1
