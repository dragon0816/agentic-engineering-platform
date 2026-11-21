"""An X (Twitter) post read from static, no-login answers (owner 2026-11-21).

A plain request for an `x.com` post gets the post's teaser in its `og:` meta and a
page of login-wall chrome ("Log in", "Sign up", cookie text). Two public endpoints
answer without a login and carry the post itself: the syndication JSON
(`cdn.syndication.twimg.com/tweet-result`, author, full text, time, expanded links)
and oEmbed (`publish.twitter.com/oembed`, author and the post's HTML). They are tried
in that order, each with its own small size and time limit, and the post page's meta
is the last resort; login, cookie and UI boilerplate never reaches the text.

Links (`docs/CONTRACTS.md` BI inbox): every link in the post is kept. Links to X
itself (other posts, photos, profiles) are never followed. When exactly one link
leads off X, it is followed (a `t.co` link expanded first) and the article it names
is fetched with the inbox's ordinary static page fetch; with several, all are listed
and none is fetched. A failed article fetch keeps the post.
"""

from __future__ import annotations

import html
import json
import math
import re
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from aep_bi.cards import html_markdown
from aep_bi.inbox import fetch

#: The JSON endpoints are small: at most 1 MB and 10 seconds each.
API_BYTES = 1024 * 1024
API_TIMEOUT_S = 10.0
SYNDICATION = "https://cdn.syndication.twimg.com/tweet-result?id={id}&lang=en&token={token}"
OEMBED = "https://publish.twitter.com/oembed?omit_script=1&dnt=1&url={url}"

_X_HOSTS = ("x.com", "twitter.com")
_SHORT_HOSTS = ("t.co",)
_STATUS = re.compile(
    r"^/(?:(?P<user>[A-Za-z0-9_]{1,15})|i(?:/web)?)/status(?:es)?/(?P<id>\d{1,25})(?:/|$)"
)
_TITLE_HANDLE = re.compile(r"^(?P<name>.*?)\s*\(@(?P<handle>[A-Za-z0-9_]{1,15})\)")
#: A link written in the text, with or without its scheme: `dlvr.it/AbC`, `https://…`.
_LINK = re.compile(
    r"(?<![@\w.])((?:https?://)?(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,24}/[!-~]*)",
    re.IGNORECASE,
)
#: What may not end a link: closing punctuation and quotes written after it.
_LINK_TAIL = ".,;:!?)]}>'\""
#: Zero-width characters X puts inside a link it chose not to link.
_INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
#: Lines that are the login wall, cookie banner or page chrome, never the post.
_BOILERPLATE = re.compile(
    r"^(?:log ?in|sign ?in|sign ?up|create account|new to x\??|"
    r"don.t miss what.s happening|people on x are the first to know\.?|"
    r"sign up now to get your own personalized timeline!?|"
    r"see new posts|trending now|what.s happening|terms of service|privacy policy|"
    r"cookie policy|accessibility|ads info|more|retry|"
    r"something went wrong\.?( try reloading\.?)?|"
    r"javascript is not available\.?|"
    r"we.ve detected that javascript is disabled.*|"
    r"did someone say.*cookies.*|"
    r"x and its partners use cookies.*|"
    r"accept all cookies|refuse non-essential cookies|"
    r"©\s*\d{4}\s*x corp\.?|"
    r"from breaking news and entertainment to sports and politics.*)$",
    re.IGNORECASE,
)


def _host(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower().split(":")[0]


def _under(host: str, names: tuple[str, ...]) -> bool:
    return any(host == name or host.endswith("." + name) for name in names)


def is_x(url: str) -> bool:
    """On X itself: `x.com`, `twitter.com` and their subdomains (`mobile.`, `www.`,
    `pic.`)."""
    return _under(_host(url), _X_HOSTS)


def is_short(url: str) -> bool:
    """X's link shortener `t.co`."""
    return _under(_host(url), _SHORT_HOSTS)


def status_of(url: str) -> tuple[str, str] | None:
    """(handle, post id) of a post address on X; the handle is empty for `/i/status/`."""
    if not is_x(url):
        return None
    found = _STATUS.match(urllib.parse.urlsplit(url).path)
    if found is None:
        return None
    return found.group("user") or "", found.group("id")


def post_url(handle: str, post_id: str) -> str:
    """The post's address without what says who shared it."""
    return f"https://x.com/{handle or 'i'}/status/{post_id}"


def token(post_id: str) -> str:
    """The syndication token: (id / 1e15 * pi) in base 36 without zeros and the point,
    as the public embed computes it (the endpoint did not check it on 2026-11-21)."""
    value = (int(post_id) / 1e15) * math.pi
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    whole, part = int(value), value - int(value)
    out = ""
    while whole:
        out = digits[whole % 36] + out
        whole //= 36
    out = (out or "0") + "."
    for _ in range(12):
        part *= 36
        out += digits[int(part)]
        part -= int(part)
    return re.sub(r"0+|\.", "", out) or "0"


def clean(text: str) -> str:
    """The post's words: invisible characters, boilerplate lines and blank runs gone."""
    lines: list[str] = []
    for line in _INVISIBLE.sub("", html.unescape(text)).splitlines():
        line = line.strip()
        if line and _BOILERPLATE.match(line):
            continue
        if line or (lines and lines[-1]):
            lines.append(line)
    return "\n".join(lines).strip()


def links_in(text: str) -> list[str]:
    """Links written in the text, with `https://` added where it was left out."""
    found = []
    plain = _INVISIBLE.sub("", text)
    for match in _LINK.finditer(plain):
        if plain[match.end() : match.end() + 1] == "\u2026":
            continue  # cut short by "…": not a usable address
        link = match.group(1).rstrip(_LINK_TAIL)
        if not re.match(r"https?://", link, re.IGNORECASE):
            link = "https://" + link
        found.append(link)
    return list(dict.fromkeys(found))


@dataclass(frozen=True)
class Endpoint:
    """One endpoint asked: its HTTP status (None when no answer), failure code, and
    whether it gave the post."""

    name: str  # syndication | oembed | page
    url: str
    status: int | None
    code: str | None
    usable: bool
    sha256: str = ""

    def record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "status": self.status,
            "code": self.code,
            "usable": self.usable,
            **({"sha256": self.sha256} if self.sha256 else {}),
        }


@dataclass(frozen=True)
class Post:
    url: str
    handle: str
    name: str
    text: str
    published: str
    links: tuple[str, ...]
    via: str  # syndication | oembed | page


@dataclass
class Read:
    """What reading a post gave: the post (None when no endpoint gave it), every
    endpoint asked, the raw answers by endpoint, and the post page when it was fetched."""

    post: Post | None
    endpoints: list[Endpoint] = field(default_factory=list)
    raw: list[tuple[str, str, bytes]] = field(default_factory=list)  # (name, suffix, bytes)
    page: fetch.Fetched | None = None


def _json(got: fetch.Fetched) -> dict[str, Any] | None:
    if not got.ok:
        return None
    try:
        value = json.loads(got.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _from_syndication(value: dict[str, Any], url: str) -> Post | None:
    text = value.get("text")
    user = value.get("user")
    if value.get("__typename") not in (None, "Tweet") or not isinstance(text, str):
        return None
    if not isinstance(user, dict):
        return None
    given = value.get("entities")
    entities: dict[str, Any] = given if isinstance(given, dict) else {}
    expanded: list[str] = []
    for entry in entities.get("urls") or []:
        if not isinstance(entry, dict) or not entry.get("url"):
            continue
        target = str(entry.get("expanded_url") or entry["url"])
        text = text.replace(str(entry["url"]), target)
        expanded.append(target)
    for entry in [*(entities.get("media") or []), *(value.get("mediaDetails") or [])]:
        if isinstance(entry, dict) and entry.get("url"):
            text = text.replace(str(entry["url"]), "")
    words = clean(text)
    if not words:
        return None
    handle = str(user.get("screen_name") or "")
    found = status_of(url)
    post_id = str(value.get("id_str") or (found[1] if found else ""))
    return Post(
        url=post_url(handle, post_id) if handle and post_id else url,
        handle=handle,
        name=str(user.get("name") or ""),
        text=words,
        published=str(value.get("created_at") or ""),
        links=tuple(dict.fromkeys([*expanded, *links_in(words)])),
        via="syndication",
    )


class _Blockquote(HTMLParser):
    """The oEmbed `blockquote`: the post's paragraph (links as their address, photos
    left out) and the date line's text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.date = ""
        self._in_p = False
        self._href: str | None = None
        self._anchor: list[str] = []
        self._after_p = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._in_p = True
        elif tag == "br" and self._in_p:
            self.text.append("\n")
        elif tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._anchor = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self._in_p, self._after_p = False, True
        elif tag == "a" and self._href is not None:
            words = "".join(self._anchor).strip()
            if self._in_p:
                if words.lower().startswith(("pic.twitter.com", "pic.x.com")):
                    pass
                elif is_short(self._href) or words.startswith(("http", "www.")):
                    self.text.append(self._href)
                else:
                    self.text.append(words)
            elif self._after_p:
                self.date = words
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._anchor.append(data)
        elif self._in_p:
            self.text.append(data)


def _from_oembed(value: dict[str, Any], url: str) -> Post | None:
    markup = value.get("html")
    if not isinstance(markup, str):
        return None
    reader = _Blockquote()
    try:
        reader.feed(markup)
        reader.close()
    except Exception:  # noqa: BLE001 - a broken answer is just not usable
        return None
    words = clean("".join(reader.text))
    if not words:
        return None
    author = str(value.get("author_url") or "")
    handle = urllib.parse.urlsplit(author).path.strip("/").split("/")[0] if author else ""
    found = status_of(str(value.get("url") or url)) or status_of(url)
    return Post(
        url=post_url(handle or (found[0] if found else ""), found[1]) if found else url,
        handle=handle,
        name=str(value.get("author_name") or ""),
        text=words,
        published=reader.date,
        links=tuple(links_in(words)),
        via="oembed",
    )


def _from_page(got: fetch.Fetched, url: str) -> Post | None:
    page = html_markdown.read(html_markdown.decode(got.body[:2_000_000]))
    words = clean(page.description)
    if not words:
        return None
    named = _TITLE_HANDLE.match(page.title)
    found = status_of(page.url or got.final_url) or status_of(url)
    handle = named.group("handle") if named else (found[0] if found else "")
    return Post(
        url=post_url(handle, found[1]) if found else url,
        handle=handle,
        name=named.group("name").strip() if named else "",
        text=words,
        published=page.published,
        links=tuple(links_in(words)),
        via="page",
    )


def _digest(got: fetch.Fetched) -> str:
    return got.sha256 if got.body else ""


def read_post(url: str, pages: fetch.Fetcher, api: fetch.Fetcher) -> Read:
    """The post at `url` (an X post address) from syndication, oEmbed, then the page."""
    found = status_of(url)
    if found is None:
        return Read(None)
    handle, post_id = found
    canonical = post_url(handle, post_id)
    read = Read(None)
    steps: list[tuple[str, str]] = [
        ("syndication", SYNDICATION.format(id=post_id, token=token(post_id))),
        ("oembed", OEMBED.format(url=urllib.parse.quote(canonical, safe=""))),
    ]
    for name, address in steps:
        got = api(address, API_BYTES, API_TIMEOUT_S)
        value = _json(got)
        if value is None:
            post = None
        elif name == "syndication":
            post = _from_syndication(value, canonical)
        else:
            post = _from_oembed(value, canonical)
        code = got.code or (None if value is not None or not got.ok else "not_json")
        read.endpoints.append(
            Endpoint(name, address, got.status, code, post is not None, _digest(got))
        )
        if got.body:
            read.raw.append((name, ".json", got.body))
        if post is not None:
            read.post = post
            return read
    got = pages(url, fetch.MAX_PAGE_BYTES, fetch.TIMEOUT_S)
    read.page = got
    post = _from_page(got, canonical) if got.ok else None
    read.endpoints.append(
        Endpoint("page", url, got.status, got.code, post is not None, _digest(got))
    )
    read.post = post
    return read


def expanded(got: fetch.Fetched) -> str:
    """Where a `t.co` link leads: the address after redirects, or the one its page
    names (a refresh meta, the `<title>`, or `location.replace`)."""
    if not is_short(got.final_url):
        return got.final_url
    if not got.body:
        return ""
    text = html_markdown.decode(got.body[:100_000])
    for pattern in (
        r"http-equiv=[\"']?refresh[\"']?[^>]*url=([^\"'>\s]+)",
        r"<title>\s*(https?://[^<\s]+)\s*</title>",
        r"location\.replace\([\"'](https?:[^\"']+)",
    ):
        hit = re.search(pattern, text, re.IGNORECASE)
        if hit:
            return html.unescape(hit.group(1)).replace("\\/", "/")
    return ""


def outbound(links: tuple[str, ...]) -> list[str]:
    """The links that may lead off X: everything not on X itself (a `t.co` link counts
    until it is expanded)."""
    return [link for link in links if not is_x(link)]


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _lines_html(text: str) -> list[str]:
    """Markdown lines from `html_markdown.read` back as simple HTML."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = min(len(heading.group(1)) + 2, 6)
            out.append(f"<h{level}>{_esc(heading.group(2))}</h{level}>")
        elif line.startswith("- "):
            out.append(f"<ul><li>{_esc(line[2:])}</li></ul>")
        else:
            out.append(f"<p>{_esc(line)}</p>")
    return out


def title(post: Post) -> str:
    who = post.name or (f"@{post.handle}" if post.handle else "X")
    first = post.text.splitlines()[0] if post.text else ""
    return f"{who}：{first[:80]}"


def document(
    post: Post,
    article_url: str = "",
    article: html_markdown.Page | None = None,
) -> bytes:
    """One HTML page holding the post (author, time, text, links) and, when one was
    fetched, the article's title and text: what the `.html` source carries."""
    author = post.name + (f" (@{post.handle})" if post.handle else "")
    head = [
        '<meta charset="utf-8">',
        f"<title>{_esc(title(post))}</title>",
        '<meta property="og:site_name" content="X">',
        f'<meta property="og:url" content="{_esc(post.url)}">',
        f'<meta property="og:description" content="{_esc(post.text)}">',
    ]
    if post.published:
        head.append(f'<meta property="article:published_time" content="{_esc(post.published)}">')
    body = [f"<h2>X 貼文：{_esc(author or post.url)}</h2>"]
    body += [f"<p>{_esc(line)}</p>" for line in post.text.splitlines() if line.strip()]
    body.append(f"<p>貼文網址：{_esc(post.url)}</p>")
    if post.published:
        body.append(f"<p>發佈時間：{_esc(post.published)}</p>")
    if post.links:
        body.append("<h2>貼文中的連結</h2>")
        body.append("<ul>" + "".join(f"<li>{_esc(link)}</li>" for link in post.links) + "</ul>")
    if article is not None:
        body.append(f"<h2>文章：{_esc(article.title or article_url)}</h2>")
        body.append(f"<p>文章網址：{_esc(article_url)}</p>")
        if article.published:
            body.append(f"<p>文章發佈時間：{_esc(article.published)}</p>")
        if article.description and article.description not in article.text:
            body.append(f"<p>{_esc(article.description)}</p>")
        body += _lines_html(article.text)
    page = (
        "<!doctype html>\n<html><head>"
        + "".join(head)
        + "</head><body><article>"
        + "\n".join(body)
        + "</article></body></html>\n"
    )
    return page.encode("utf-8")
