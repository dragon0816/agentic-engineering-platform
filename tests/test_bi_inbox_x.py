"""X (Twitter) links in the BI inbox (owner 2026-11-21): their own platform `x`, the post
read cleanly from the public no-login endpoints (syndication JSON, oEmbed) or the page's
meta without login-wall chrome, and the one article a post links to kept with it.

Everything comes from small fictional fixtures (`tests/fixtures/bi_inbox/x_*`); the
network is refused.
"""

from __future__ import annotations

import json
from pathlib import Path

import test_bi_inbox as base
from test_bi_ai_runs import Jobs
from test_bi_inbox import (
    ARTICLE,
    THREADS,
    WIRELESS_BOT,
    Messages,
    Web,
    _markdown,
    dataset,
    keys,
    page,
    processor,
    queued,
    web,
)

from aep_bi.cards import html_markdown
from aep_bi.cards.staging import Staging
from aep_bi.inbox import fetch, store, xpost
from aep_bi.inbox.store import Inbox

#: The inbox tests' fixtures: a workspace with two domains, and no network.
ws = base.ws
no_network = base.no_network

POST = "https://x.com/example_news/status/1900000000000000001?a=share&s=20"
CANONICAL = "https://x.com/example_news/status/1900000000000000001"
TCO = "https://t.co/AbCdEf1234"
ARTICLE_CLEAN = "https://news.example.com/5g/redcap"


class Api:
    """X's JSON endpoints by name: `syndication` and `oembed` answers, or a status."""

    def __init__(self, **answers: bytes | int) -> None:
        self.answers = answers
        self.asked: list[str] = []

    def __call__(self, url: str, limit: int, timeout_s: float) -> fetch.Fetched:
        name = "syndication" if "syndication" in url else "oembed"
        self.asked.append(name)
        assert limit == xpost.API_BYTES and timeout_s == xpost.API_TIMEOUT_S
        answer = self.answers.get(name, 404)
        if isinstance(answer, int):
            return fetch.Fetched(url, url, answer, b"", "", "http", f"http_{answer}")
        return fetch.Fetched(url, url, 200, answer, "application/json", "http")


def syndication(**change: object) -> bytes:
    value = json.loads(page("x_syndication.json"))
    value.update(change)
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def pages(**more: tuple[str, bytes]) -> Web:
    found = {
        POST: (POST, page("x_post_page.html")),
        ARTICLE_CLEAN: (ARTICLE_CLEAN, page("web_article.html")),
        TCO: (ARTICLE_CLEAN, page("web_article.html")),  # urllib follows t.co's redirect
    }
    found.update(more)
    return Web(found)


# -- detection -----------------------------------------------------------------------------------


def test_x_and_twitter_hosts_are_their_own_platform() -> None:
    assert [
        fetch.platform(url)
        for url in (
            POST,
            "https://twitter.com/example_news/status/1",
            "https://mobile.twitter.com/example_news/status/1",
            "https://www.x.com/example_news/status/1",
            "https://mobile.x.com/i/web/status/1",
            TCO,
            "https://netflix.com/title/1",
            "https://box.com/s/1",
            THREADS,
            ARTICLE,
        )
    ] == ["x", "x", "x", "x", "x", "x", "web", "web", "threads", "web"]
    assert xpost.status_of("https://mobile.twitter.com/Example_News/status/123/photo/1") == (
        "Example_News",
        "123",
    )
    assert xpost.status_of("https://x.com/i/web/status/123") == ("", "123")
    assert xpost.status_of("https://x.com/example_news") is None
    assert xpost.status_of("https://notx.com/a/status/1") is None


def test_an_x_post_normalizes_to_one_address_whatever_host_and_share_parameters() -> None:
    for url in (
        POST,
        "https://twitter.com/example_news/status/1900000000000000001?s=46&t=abc",
        "https://mobile.twitter.com/example_news/status/1900000000000000001/",
        "HTTPS://WWW.X.COM/example_news/status/1900000000000000001#reply",
    ):
        assert fetch.normalize(url) == CANONICAL
    assert fetch.normalize(ARTICLE) == ARTICLE_CLEAN  # other sites unchanged


def test_the_inbox_item_records_its_platform(ws: Path) -> None:
    first = queued(ws, POST)
    second = queued(ws, ARTICLE)
    inbox = Inbox(ws)
    assert inbox.item(first)["platform"] == "x"  # type: ignore[index]
    assert inbox.item(second)["platform"] == "web"  # type: ignore[index]
    assert inbox.item(first)["norm_url"] == CANONICAL  # type: ignore[index]


def test_an_inbox_made_before_the_platform_column_gains_it(tmp_path: Path) -> None:
    import sqlite3

    folder = tmp_path / "bi" / "inbox"
    folder.mkdir(parents=True)
    old = store.SCHEMA.replace(",\n  platform TEXT NOT NULL DEFAULT ''", "")
    assert "platform" not in old.split("CREATE TABLE IF NOT EXISTS picks")[0]
    db = sqlite3.connect(folder / "inbox.sqlite")
    db.executescript(old)
    db.close()
    inbox = Inbox(tmp_path)
    item_id = inbox.add(kind="link", actor="alice", url=POST, platform="x")
    assert inbox.item(item_id)["platform"] == "x"  # type: ignore[index]


# -- reading the post ----------------------------------------------------------------------------


def test_syndication_gives_author_text_time_and_expanded_links() -> None:
    api, web_pages = Api(syndication=syndication()), pages()
    read = xpost.read_post(POST, web_pages, api)
    post = read.post
    assert post is not None and post.via == "syndication"
    assert (post.handle, post.name) == ("example_news", "Example News 範例新聞")
    assert post.published == "2026-11-05T10:19:22.000Z" and post.url == CANONICAL
    assert post.text == f"RedCap 模組出貨量今年成長三倍，車用與穿戴先行 {ARTICLE_CLEAN}"
    assert "t.co" not in post.text  # the link expanded, the photo's link left out
    assert post.links == (ARTICLE_CLEAN,)
    assert api.asked == ["syndication"] and web_pages.fetched == []  # nothing more asked
    assert [(e.name, e.status, e.usable) for e in read.endpoints] == [("syndication", 200, True)]


def test_oembed_is_next_when_syndication_fails() -> None:
    api = Api(syndication=404, oembed=page("x_oembed.json"))
    read = xpost.read_post(POST, pages(), api)
    post = read.post
    assert post is not None and post.via == "oembed" and api.asked == ["syndication", "oembed"]
    assert (post.handle, post.name, post.published) == (
        "example_news",
        "Example News 範例新聞",
        "November 5, 2026",
    )
    assert post.text == f"RedCap 模組出貨量今年成長三倍 #RedCap\n車用與穿戴先行 {TCO}"
    assert "pic.twitter.com" not in post.text and post.links == (TCO,)
    assert [(e.name, e.code, e.usable) for e in read.endpoints] == [
        ("syndication", "http_404", False),
        ("oembed", None, True),
    ]


def test_a_tombstone_or_unparsable_answer_is_not_a_post() -> None:
    api = Api(syndication=syndication(__typename="TweetTombstone"), oembed=b"<html>")
    read = xpost.read_post(POST, pages(), api)
    assert read.post is not None and read.post.via == "page"
    assert [(e.name, e.usable) for e in read.endpoints] == [
        ("syndication", False),
        ("oembed", False),
        ("page", True),
    ]
    assert read.endpoints[1].code == "not_json"


def test_the_page_meta_is_the_last_resort_without_login_wall_chrome() -> None:
    read = xpost.read_post(POST, pages(), Api())
    post = read.post
    assert post is not None and post.via == "page"
    assert (post.handle, post.name) == ("example_news", "Example News 範例新聞")
    assert post.published == "2026-11-05T10:19:22+00:00"
    assert post.text == "RedCap 模組出貨量今年成長三倍，車用與穿戴先行 news.example.com/5g/redcap"
    for noise in ("Log in", "Sign up", "cookies", "happening", "Something went wrong"):
        assert noise not in post.text
    assert post.links == (ARTICLE_CLEAN,)  # written without its scheme, behind a ZWSP


def test_a_login_wall_with_only_the_x_slogan_gives_no_post() -> None:
    walled = pages(**{POST: (POST, page("x_login_wall.html"))})
    read = xpost.read_post(POST, walled, Api())
    assert read.post is None and read.page is not None
    assert xpost.clean("Log in\nSign up\nDon’t miss what’s happening\nReal words") == "Real words"


def test_links_in_text() -> None:
    zwsp = chr(0x200B)
    text = f"看 dlvr.{zwsp}it/AbC12 與 https://news.example.com/a?b=1。截斷的 example.org/long-pa…"
    assert xpost.links_in(text) == ["https://dlvr.it/AbC12", "https://news.example.com/a?b=1"]
    assert xpost.links_in("寄信 me@example.com/x 或 Node.js 版本") == []


# -- through the processor -----------------------------------------------------------------------


def _provenance(ws: Path, source_id: str) -> tuple[dict[str, object], str]:
    raw = Staging(ws, dataset(ws)).source_bytes(source_id).decode("utf-8")
    return html_markdown.provenance_of(raw)


def test_one_article_link_is_followed_and_kept_with_the_post(ws: Path) -> None:
    queued(ws, POST)
    web_pages, api = pages(), Api(syndication=syndication())
    done = processor(ws, Jobs(), Messages(), fetcher=web_pages, api_fetcher=api).collect(
        keys(ws)["AIDC"]
    )
    assert done["review"] == 1 and web_pages.fetched == [ARTICLE_CLEAN]
    [result] = Inbox(ws).results(item_id=1)
    source = Staging(ws, dataset(ws)).source(result["source_id"])
    assert source is not None and source["name"].startswith("x-Example-News")
    provenance, _ = _provenance(ws, result["source_id"])
    assert provenance["original_url"] == POST and provenance["post_url"] == CANONICAL
    assert provenance["platform"] == "x" and provenance["x_via"] == "syndication"
    assert provenance["article_rule"] == "one_link_followed"
    assert provenance["article_url"] == ARTICLE_CLEAN
    assert provenance["article_final_url"] == ARTICLE_CLEAN and provenance["article_status"] == 200
    assert provenance["summary_only"] is False
    markdown = _markdown(ws, result["source_id"])
    assert "X 貼文：Example News 範例新聞 (@example_news)" in markdown
    assert "RedCap 模組出貨量今年成長三倍，車用與穿戴先行" in markdown
    assert f"文章網址：{ARTICLE_CLEAN}" in markdown and "電信商認證" in markdown  # article body
    item = Inbox(ws).item(1)
    assert item is not None and item["platform"] == "x" and item["final_url"] == CANONICAL
    kept = sorted(p.name for p in (Inbox(ws).dir / "raw").iterdir())
    assert any("-x-syndication-" in name for name in kept)
    assert any("-x-article-" in name for name in kept)


def test_a_tco_link_is_expanded_before_its_article_is_fetched(ws: Path) -> None:
    queued(ws, POST)
    # oEmbed leaves the link as t.co; t.co answers a page naming where it leads.
    web_pages = pages(**{TCO: (TCO, page("tco_refresh.html"))})
    api = Api(syndication=500, oembed=page("x_oembed.json"))
    processor(ws, Jobs(), Messages(), fetcher=web_pages, api_fetcher=api).collect(keys(ws)["AIDC"])
    assert web_pages.fetched == [TCO, ARTICLE_CLEAN]
    provenance, _ = _provenance(ws, Inbox(ws).results(item_id=1)[0]["source_id"])
    assert provenance["article_url"] == TCO
    assert provenance["article_expanded_url"] == ARTICLE_CLEAN
    assert provenance["article_final_url"] == ARTICLE_CLEAN
    assert "電信商認證" in _markdown(ws, Inbox(ws).results(item_id=1)[0]["source_id"])


def test_a_tco_link_sent_to_the_bot_that_leads_to_a_post_is_read_as_that_post(ws: Path) -> None:
    queued(ws, TCO)
    web_pages = pages(**{TCO: (POST, page("x_post_page.html"))})
    api = Api(syndication=syndication())
    processor(ws, Jobs(), Messages(), fetcher=web_pages, api_fetcher=api).collect(keys(ws)["AIDC"])
    item = Inbox(ws).item(1)
    assert item is not None and item["platform"] == "x" and item["final_url"] == CANONICAL
    assert api.asked == ["syndication"]


def test_a_tco_link_sent_to_the_bot_that_leads_off_x_is_an_ordinary_page(ws: Path) -> None:
    queued(ws, TCO)
    web_pages, api = pages(), Api()
    processor(ws, Jobs(), Messages(), fetcher=web_pages, api_fetcher=api).collect(keys(ws)["AIDC"])
    item = Inbox(ws).item(1)
    assert item is not None and item["platform"] == "web" and api.asked == []
    assert web_pages.fetched == [TCO]  # fetched once, not again after expanding


def test_several_links_are_listed_and_not_followed(ws: Path) -> None:
    queued(ws, POST)
    many = syndication(
        text="兩篇報導 https://t.co/One1 https://t.co/Two2 以及 https://t.co/Post3",
        entities={
            "urls": [
                {"url": "https://t.co/One1", "expanded_url": "https://a.example.com/one"},
                {"url": "https://t.co/Two2", "expanded_url": "https://b.example.com/two"},
                {"url": "https://t.co/Post3", "expanded_url": "https://x.com/other/status/9"},
            ]
        },
    )
    web_pages = pages()
    processor(ws, Jobs(), Messages(), fetcher=web_pages, api_fetcher=Api(syndication=many)).collect(
        keys(ws)["AIDC"]
    )
    assert web_pages.fetched == []
    provenance, _ = _provenance(ws, Inbox(ws).results(item_id=1)[0]["source_id"])
    assert provenance["article_rule"] == "several_links_not_followed"
    assert provenance["links"] == [
        "https://a.example.com/one",
        "https://b.example.com/two",
        "https://x.com/other/status/9",
    ]
    markdown = _markdown(ws, Inbox(ws).results(item_id=1)[0]["source_id"])
    assert "- https://a.example.com/one" in markdown and "- https://b.example.com/two" in markdown


def test_a_link_to_another_x_post_is_never_followed(ws: Path) -> None:
    queued(ws, POST)
    quoting = syndication(
        text="看這則 https://t.co/Post3",
        entities={
            "urls": [{"url": "https://t.co/Post3", "expanded_url": "https://x.com/other/status/9"}]
        },
    )
    web_pages = pages()
    processor(
        ws, Jobs(), Messages(), fetcher=web_pages, api_fetcher=Api(syndication=quoting)
    ).collect(keys(ws)["AIDC"])
    assert web_pages.fetched == []
    provenance, _ = _provenance(ws, Inbox(ws).results(item_id=1)[0]["source_id"])
    assert provenance["article_rule"] == "no_link"
    # ...nor a t.co link that turns out to lead back to X.
    queued(ws, "https://x.com/example_news/status/1900000000000000002")
    to_x = syndication(
        id_str="1900000000000000002",
        text="看這則 https://t.co/Post4",
        entities={"urls": [{"url": "https://t.co/Post4", "expanded_url": "https://t.co/Post4"}]},
    )
    back = pages(**{"https://t.co/Post4": ("https://x.com/other/status/9", b"<p>x</p>")})
    processor(ws, Jobs(), Messages(), fetcher=back, api_fetcher=Api(syndication=to_x)).collect(
        keys(ws)["AIDC"]
    )
    assert back.fetched == ["https://t.co/Post4"]
    provenance, _ = _provenance(ws, Inbox(ws).results(item_id=2)[0]["source_id"])
    assert provenance["article_rule"] == "link_on_x_not_followed"


def test_a_failed_article_fetch_keeps_the_post(ws: Path) -> None:
    queued(ws, POST)
    web_pages = Web({})  # the article answers 404
    done = processor(
        ws, Jobs(), Messages(), fetcher=web_pages, api_fetcher=Api(syndication=syndication())
    ).collect(keys(ws)["AIDC"])
    assert done["review"] == 1 and web_pages.fetched == [ARTICLE_CLEAN]
    source_id = Inbox(ws).results(item_id=1)[0]["source_id"]
    provenance, _ = _provenance(ws, source_id)
    assert provenance["article_code"] == "http_404" and provenance["article_status"] == 404
    markdown = _markdown(ws, source_id)
    assert "RedCap 模組出貨量今年成長三倍" in markdown and "文章網址" not in markdown


def test_a_post_from_the_page_meta_alone_is_a_summary_and_its_sender_is_asked(ws: Path) -> None:
    queued(ws, POST)
    messages = Messages()
    only_page = Web({POST: (POST, page("x_post_page.html"))})  # article 404s
    done = processor(ws, Jobs(), messages, fetcher=only_page, api_fetcher=Api()).collect(
        keys(ws)["AIDC"]
    )
    assert done["summary"] == 1
    markdown = _markdown(ws, Inbox(ws).results(item_id=1)[0]["source_id"])
    assert "> 只取得摘要" in markdown and "Log in" not in markdown
    assert any(t.startswith("#1 只取得摘要") for t in messages.to("alice"))


def test_no_post_from_any_endpoint_asks_for_the_text(ws: Path) -> None:
    queued(ws, POST)
    walled = Web({POST: (POST, page("x_login_wall.html"))})
    processor(ws, Jobs(), Messages(), fetcher=walled, api_fetcher=Api()).collect(keys(ws)["AIDC"])
    # The generic path keeps the page's meta, marked as a summary, without a browser.
    item = Inbox(ws).item(1)
    assert item is not None and item["platform"] == "x"
    assert walled.fetched == [POST]  # the page is fetched once


def test_threads_is_unchanged(ws: Path) -> None:
    queued(ws, THREADS, bot=WIRELESS_BOT)
    api = Api()
    done = processor(ws, Jobs(), Messages(), fetcher=web(), api_fetcher=api).collect(
        keys(ws)["Wireless"]
    )
    assert done["summary"] == 1 and api.asked == []
    item = Inbox(ws).item(1)
    assert item is not None and item["platform"] == "threads"
    provenance, _ = _provenance(ws, Inbox(ws).results(item_id=1)[0]["source_id"])
    assert "platform" not in provenance and "links" not in provenance
