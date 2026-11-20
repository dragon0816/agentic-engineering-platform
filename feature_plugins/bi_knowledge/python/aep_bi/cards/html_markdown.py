"""A web page as Markdown, with the standard library only (Telegram link collection P1).

`docs/phases/TELEGRAM_LINK_COLLECTION_ASSESSMENT_20261119.md` §3/§8: a page a person
shared is kept as fetched (an immutable `.html` source) and read through its Markdown.
This reads what a shared link's HTML carries without running it: the `og:` / `twitter:`
meta (title, description, image, site, time), the `<title>`, and the visible text
(headings, paragraphs, list items, table rows), leaving out scripts, styles, navigation,
forms and other page chrome. Threads and Instagram pages are rendered by script, so their
HTML often holds only the meta: `Page.summary_only` says so.

A page fetched by the BI inbox starts with one `<!-- aep-bi-link-provenance {...} -->`
comment (who sent it, when, the original address, when and how it was fetched); the
Markdown opens with that provenance, so it survives the conversion (AGENTS rule 7).
"""

from __future__ import annotations

import codecs
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

#: The comment the BI inbox puts before a fetched page.
PROVENANCE_MARK = "aep-bi-link-provenance"
_PROVENANCE_RE = re.compile(r"^\s*<!--\s*" + PROVENANCE_MARK + r"\s*(\{.*?\})\s*-->\n?", re.DOTALL)
#: Visible text at least this long is the page's content. Shorter text that adds
#: little to the description (`MIN_EXTRA_CHARS`) is a page whose words are not in its
#: HTML (a script-rendered post): only its summary was obtained.
MIN_BODY_CHARS = 200
MIN_EXTRA_CHARS = 40
MAX_MARKDOWN_CHARS = 1_000_000
SUMMARY_ONLY = "只取得摘要"

_SKIP = frozenset(
    {
        "script",
        "style",
        "noscript",
        "svg",
        "template",
        "head",
        "nav",
        "footer",
        "form",
        "button",
        "iframe",
        "select",
        "textarea",
        "canvas",
        "object",
        "dialog",
    }
)
_VOID = frozenset(
    {"br", "hr", "img", "meta", "link", "input", "source", "area", "base", "col", "wbr", "track"}
)
_BLOCKS = frozenset(
    {
        "p",
        "div",
        "section",
        "article",
        "main",
        "header",
        "aside",
        "blockquote",
        "ul",
        "ol",
        "table",
        "tr",
        "pre",
        "figure",
        "figcaption",
        "dl",
        "dt",
        "dd",
        "address",
    }
)
_HEADINGS = {f"h{n}": n for n in range(1, 7)}
_META_KEYS = {
    "og:title": "title",
    "twitter:title": "title",
    "og:description": "description",
    "twitter:description": "description",
    "description": "description",
    "og:image": "image",
    "twitter:image": "image",
    "og:site_name": "site",
    "og:url": "url",
    "article:published_time": "published",
    "og:type": "type",
}


@dataclass
class Page:
    """What a page's HTML says. `text` is its visible text as Markdown lines."""

    title: str = ""
    description: str = ""
    image: str = ""
    site: str = ""
    url: str = ""
    published: str = ""
    type: str = ""
    text: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def summary_only(self) -> bool:
        """Only the meta came through: the visible text is too short to be the content."""
        if not (self.description or self.title) or len(self.text) >= MIN_BODY_CHARS:
            return False
        return len(self.text) < len(self.description) + MIN_EXTRA_CHARS

    @property
    def empty(self) -> bool:
        return not (self.title or self.description or self.text.strip())


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.lines: list[str] = []
        self._line: list[str] = []
        self._skip = 0
        self._in_title = False
        self._prefix = ""
        self._pre = 0
        self.stack: list[str] = []

    def _flush(self) -> None:
        text = "".join(self._line)
        text = text if self._pre else re.sub(r"\s+", " ", text).strip()
        if text:
            self.lines.append(self._prefix + text)
        self._line = []
        self._prefix = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            target = _META_KEYS.get(key)
            content = values.get("content", "").strip()
            if target and content and target not in self.meta:
                self.meta[target] = content
            return
        if tag == "link" and "canonical" in values.get("rel", "").lower():
            self.meta.setdefault("canonical", values.get("href", "").strip())
            return
        if tag == "title":
            self._in_title = True
        if tag in _VOID:
            if tag == "br" and not self._skip:
                self._flush()
            return
        self.stack.append(tag)
        if tag in _SKIP or values.get("aria-hidden") == "true" or "hidden" in values:
            self._skip += 1
            return
        if self._skip:
            return
        if tag in _HEADINGS:
            self._flush()
            self._prefix = "#" * _HEADINGS[tag] + " "
        elif tag == "li":
            self._flush()
            self._prefix = "- "
        elif tag in ("td", "th"):
            self._line.append(" | " if self._line else "")
        elif tag in _BLOCKS:
            self._flush()
            if tag == "pre":
                self._pre += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in _VOID or tag not in self.stack:
            return
        while self.stack:
            opened = self.stack.pop()
            if opened in _SKIP:
                self._skip = max(0, self._skip - 1)
            if opened == tag:
                break
        if self._skip:
            return
        if tag in _HEADINGS or tag == "li" or tag in _BLOCKS:
            self._flush()
            if tag == "pre":
                self._pre = max(0, self._pre - 1)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
            return
        if not self._skip:
            self._line.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def provenance_of(html: str) -> tuple[dict[str, Any], str]:
    """The inbox's provenance comment (empty when there is none) and the page after it."""
    found = _PROVENANCE_RE.match(html)
    if found is None:
        return {}, html
    try:
        value = json.loads(found.group(1))
    except ValueError:
        return {}, html
    return (value if isinstance(value, dict) else {}), html[found.end() :]


def provenance_comment(value: dict[str, Any]) -> str:
    """The comment that carries `value` before a page: ASCII only, so it reads in any
    page encoding, and `--` never appears inside it."""
    text = json.dumps(value, ensure_ascii=True, sort_keys=True).replace("--", "-\\u002d")
    return f"<!-- {PROVENANCE_MARK} {text} -->\n"


def _deduped(lines: list[str]) -> list[str]:
    kept: list[str] = []
    for line in lines:
        if kept and kept[-1] == line:
            continue
        kept.append(line)
    return kept


def read(html: str) -> Page:
    """The page's meta and visible text."""
    provenance, rest = provenance_of(html)
    reader = _Reader()
    try:
        reader.feed(rest)
        reader.close()
    except Exception:  # noqa: BLE001 - a broken page still yields what was read
        reader._flush()
    meta = reader.meta
    title = meta.get("title") or re.sub(r"\s+", " ", "".join(reader.title_parts)).strip()
    return Page(
        title=title,
        description=meta.get("description", ""),
        image=meta.get("image", ""),
        site=meta.get("site", ""),
        url=meta.get("url") or meta.get("canonical", ""),
        published=meta.get("published", ""),
        type=meta.get("type", ""),
        text="\n".join(_deduped(reader.lines)),
        provenance=provenance,
    )


def _provenance_lines(value: dict[str, Any]) -> list[str]:
    if not value:
        return []
    lines = [f"> 原始網址：{value.get('original_url', '')}"]
    if value.get("final_url") and value.get("final_url") != value.get("original_url"):
        lines.append(f"> 實際網址：{value['final_url']}")
    lines.append(f"> 傳送者：{value.get('sender', '')}・傳送時間：{value.get('sent_at', '')}")
    method = value.get("fetch_method", "")
    status = value.get("http_status")
    lines.append(
        f"> 抓取時間：{value.get('fetched_at', '')}・方式：{method}"
        + (f" {status}" if status is not None else "")
    )
    if value.get("summary_only"):
        lines.append(f"> {SUMMARY_ONLY}：頁面內文沒有取得，以下只有標題與摘要")
    return [*lines, ""]


def markdown(html: str) -> str:
    """The page as Markdown: provenance, title, summary, image, then the visible text."""
    page = read(html)
    lines = _provenance_lines(page.provenance)
    if page.title:
        lines += [f"# {page.title}", ""]
    facts = [
        f"- {label}：{value}"
        for label, value in (
            ("網站", page.site),
            ("網址", page.url),
            ("發佈時間", page.published),
        )
        if value
    ]
    if facts:
        lines += [*facts, ""]
    if page.description:
        lines += ["## 摘要", "", page.description, ""]
    if page.image:
        lines += [f"![圖片]({page.image})", ""]
    if page.text.strip() and page.text.strip() != page.description.strip():
        lines += ["## 內文", "", page.text, ""]
    text = "\n".join(lines).strip() + "\n"
    return text[:MAX_MARKDOWN_CHARS]


_CHARSET_RE = re.compile(rb"<meta[^>]+charset=[\"']?([A-Za-z0-9_-]+)", re.IGNORECASE)


def decode(data: bytes, declared: str | None = None) -> str:
    """A page's characters: its byte order mark, the charset it declares (or the
    server's), else UTF-8; bytes that still do not decode are replaced, as a browser
    shows them, since a fetched page is kept whole anyway."""
    for bom, name in ((codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16")):
        if data.startswith(bom):
            return data.decode(name, errors="replace")
    named = _CHARSET_RE.search(data[:4096])
    for candidate in (named.group(1).decode("ascii") if named else None, declared, "utf-8"):
        if not candidate:
            continue
        try:
            return data.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")
