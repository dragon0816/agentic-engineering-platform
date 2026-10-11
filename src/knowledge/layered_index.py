"""Layered bilingual index for a large wiki (K2, owner 2026-10-11).

`docs/phases/KNOWLEDGE_K2.md`. Karpathy's index is read whole, which works for a
few hundred pages; rs-k has 2,007 pages and a 364,000-character Chinese
`index.md`. So the wiki gets a short top index of categories (the 5 market x
4 product-line domain matrix, technical, companies, sources by year) and one
sub-index per category under `wiki/index/`, each line bilingual.

Categories come from rules first (tags, title, the opening text) and from the
Gateway model for the rest. The same batched model pass writes each page's
`aliases` and one-line `summary` in both languages into its frontmatter; only
the frontmatter changes, a page whose body would change is refused, and every
write is backed up by the vault.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from common.base import Contract
from common.execution import TraceIdentifiers
from knowledge.vault import Vault
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

INDEX_DIR = "wiki/index"
BATCH = 20
# One sub-index page must fit a prompt comfortably (about 20,000 characters).
MAX_ENTRIES = 150
MAX_ALIASES = 8
MAX_ALIAS_CHARS = 60
MAX_SUMMARY_CHARS = 160
# Rules aim at precision: the title, tags, aliases and only the page's first
# lines (a 1,500-character opening put half of rs-k under AI). The model pass
# adds what the rules miss.
OPENING_CHARS = 300


@dataclass(frozen=True)
class Category:
    key: str
    title_zh: str
    title_en: str
    keywords: tuple[str, ...] = ()


MARKETS = (
    Category("market-wireless", "無線通訊", "Wireless communication",
             ("wireless", "5g", "5g-nr", "3gpp", "lte", "wlan", "wi-fi", "wifi", "802.11",
              "cellular", "無線通訊", "基地台", "small cell", "fwa", "cpe")),
    Category("market-aerospace-defense", "航太／國防", "Aerospace / defense",
             ("aerospace", "defense", "defence", "satellite", "radar", "avionics", "ntn", "leo",
              "航太", "國防", "衛星", "雷達")),
    Category("market-automotive-uav", "車用／無人機", "Automotive / UAV",
             ("automotive", "vehicle", "v2x", "ecall", "adas", "uav", "drone", "車用", "汽車",
              "無人機")),
    Category("market-ai", "AI", "AI",
             ("ai", "data-center", "data center", "ai server", "ai-chip", "edge-ai", "gpu",
              "人工智慧", "資料中心", "伺服器")),
    Category("market-semiconductor", "半導體", "Semiconductor",
             ("semiconductor", "wafer", "foundry", "ic ", "rfic", "package", "hbm", "substrate",
              "osat", "半導體", "晶圓", "封裝")),
)
PRODUCTS = (
    Category("product-wireless-tester", "無線通訊綜合測試儀（signaling / non-signaling）",
             "Wireless communication testers (signaling / non-signaling)",
             ("cmx500", "cmp180", "cmp200", "cmw", "signaling", "non-signaling",
              "綜合測試儀", "信令")),
    Category("product-signal-generator-analyzer", "訊號產生器／訊號分析儀",
             "Signal generators / signal analyzers",
             ("smw", "sma100", "smb100", "fsw", "fsv", "fpl", "signal generator", "signal analyzer",
              "spectrum analyzer", "訊號產生器", "訊號分析儀", "頻譜分析儀")),
    Category("product-oscilloscope", "示波器", "Oscilloscopes",
             ("oscilloscope", "rto", "rtp", "mxo", "rtb", "rte", "示波器")),
    Category("product-vna", "VNA 網路分析儀", "Vector network analyzers",
             ("vna", "network analyzer", "zna", "znb", "znl", "znle", "s-parameter",
              "網路分析儀")),
)
TECHNICAL = Category("technical", "技術", "Technical concepts")
COMPANIES = Category("companies", "公司與組織", "Companies and organisations")
FIXED = (*MARKETS, *PRODUCTS, TECHNICAL, COMPANIES)
KEYS = frozenset(c.key for c in FIXED)
ALL_TITLE = "Index — 全部（舊版扁平目錄）"


def category_title(key: str) -> str:
    category = next((c for c in FIXED if c.key == key), None)
    if category is not None:
        return f"{category.title_zh} / {category.title_en}"
    area = key.split("-", 1)[1] if key.startswith("sources-") else key
    return f"來源：{area} / Sources: {area}"

ENRICH_PROMPT = (
    "You index a bilingual (Traditional Chinese / English) engineering wiki about test and "
    "measurement. For each page below reply with one JSON object "
    '{"pages": [{"path": "...", "summary_zh": "one line in Traditional Chinese", '
    '"summary_en": "one line in English", "aliases": ["English or Chinese names, '
    'abbreviations, model numbers"], "categories": ["keys"]}]}. Use only what the page says. '
    "Choose categories only from: " + ", ".join(sorted(KEYS)) + ". A page may have several "
    "or none."
)

_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_TAGS = re.compile(r"^tags:\s*\[(.*?)\]", re.MULTILINE)


class PageEntry(Contract):
    path: str
    title: str
    kind: str
    categories: tuple[str, ...] = ()
    summary_zh: str = ""
    summary_en: str = ""
    aliases: tuple[str, ...] = ()
    area: str | None = None


class EnrichReport(Contract):
    done: int = 0
    remaining: int = 0
    failed_batches: int = 0
    refused: tuple[str, ...] = ()


class IndexReport(Contract):
    pages: int = 0
    categories: dict[str, int] = Field(default_factory=dict)
    unassigned: int = 0
    written: tuple[str, ...] = ()


def _front(text: str) -> tuple[str, str]:
    """(frontmatter body, rest); no frontmatter gives ('', text)."""
    text = text.replace("\r\n", "\n")
    found = _FRONT.match(text)
    return (found.group(1), text[found.end():]) if found else ("", text)


def _field(front: str, name: str) -> str:
    found = re.search(rf"^{name}:\s*(.*)$", front, re.MULTILINE)
    return found.group(1).strip().strip("\"'") if found else ""


def _list(front: str, name: str) -> tuple[str, ...]:
    raw = _field(front, name)
    if raw.startswith("["):
        try:
            value = json.loads(raw)
        except ValueError:
            value = [item.strip().strip("\"'") for item in raw.strip("[]").split(",")]
        return tuple(str(v) for v in value if str(v).strip())
    return ()


def read_entry(vault: Vault, rel: str) -> PageEntry:
    front, body = _front(vault.read(rel))
    kind = rel.split("/")[1] if rel.count("/") >= 2 else "page"
    tags = _TAGS.search(front)
    # Most sources carry no document date (rs-k: 30 of 508), so they are grouped
    # by the Raw area they came from (Market, Productions, Knowledge, ...).
    source_path = _field(front, "source_path") or _field(front, "raw_ref")
    parts = source_path.replace("\\", "/").split("/")
    area = parts[1] if len(parts) > 2 and parts[0] == "raw" else None
    entry = PageEntry(
        path=rel, title=_field(front, "title") or rel.rsplit("/", 1)[-1][:-3], kind=kind,
        summary_zh=_field(front, "summary_zh"), summary_en=_field(front, "summary_en"),
        aliases=_list(front, "aliases"), area=area)
    text = " ".join((entry.title, tags.group(1) if tags else "", " ".join(entry.aliases),
                     body[:OPENING_CHARS])).lower()
    return entry.model_copy(update={"categories": tuple(sorted(rule_categories(text, kind)))})


def rule_categories(text: str, kind: str) -> set[str]:
    found = {c.key for c in (*MARKETS, *PRODUCTS)
             if any(_matches(word, text) for word in c.keywords)}
    if kind == "entities" and re.search(r"\b(company|organization|organisation|公司)\b", text):
        found.add(COMPANIES.key)
    return found


def _matches(word: str, text: str) -> bool:
    if re.search(r"[一-鿿]", word):
        return word in text
    return re.search(rf"(?<![a-z0-9]){re.escape(word.strip())}(?![a-z0-9])", text) is not None


def enriched(entry: PageEntry) -> bool:
    return bool(entry.summary_zh and entry.summary_en)


def _yaml_list(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def with_frontmatter(text: str, updates: dict[str, str]) -> str:
    """Set the given frontmatter keys; nothing outside the frontmatter changes."""
    normalized = text.replace("\r\n", "\n")
    front, body = _front(normalized)
    lines = [line for line in front.split("\n") if line and not any(
        line.startswith(f"{key}:") for key in updates)] if front else []
    lines += [f"{key}: {value}" for key, value in updates.items()]
    return "---\n" + "\n".join(lines) + "\n---\n" + body


KIND_TITLES = {"concepts": "概念 / Concepts", "entities": "實體 / Entities",
               "syntheses": "綜合 / Syntheses", "sources": "來源 / Sources"}


def part_title(part: str) -> str:
    product = next((p for p in PRODUCTS if p.key == part), None)
    if product is not None:
        return f"{product.title_zh} / {product.title_en}"
    kind = part.removeprefix("kind-")
    return KIND_TITLES.get(kind, kind)


def _page(title: str, members: list[PageEntry]) -> str:
    lines = [f"---\ntitle: Index — {title}\ntype: index\n---\n", f"# {title}\n"]
    for e in sorted(members, key=lambda m: m.title.lower()):
        summary = " / ".join(s for s in (e.summary_zh, e.summary_en) if s)
        alias = f" (aliases: {', '.join(e.aliases)})" if e.aliases else ""
        lines.append(f"- [[{e.title}]] — {summary or e.kind}{alias}")
    return "\n".join(lines) + "\n"


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


class LayeredIndex:
    def __init__(self, vault: Vault, model: ModelClient | None = None,
                 alias: str | None = None) -> None:
        self.vault = vault
        self.model = model
        self.alias = alias

    def entries(self) -> list[PageEntry]:
        return [read_entry(self.vault, rel) for rel in self.vault.wiki_files()
                if not rel.startswith(INDEX_DIR + "/")]

    def _ask(self, batch: list[PageEntry]) -> dict[str, dict[str, Any]]:
        assert self.model is not None and self.alias is not None
        shown = "\n\n".join(
            f"### {e.path}\ntitle: {e.title}\n{_front(self.vault.read(e.path))[1][:1200]}"
            for e in batch)
        response = self.model.generate(ModelRequest(
            trace=TraceIdentifiers(trace_id="layered-index", request_id="enrich", span_id="enrich"),
            model_alias=self.alias,
            messages=(ModelMessage(role="system", text=ENRICH_PROMPT),
                      ModelMessage(role="user", text=shown)),
            requirements=ModelRequirements(structured_output=True),
            output_contract="knowledge_layered_index", max_output_tokens=6000))
        if response.failure is not None:
            return {}
        data = response.structured_output
        if not isinstance(data, dict):
            try:
                data = json.loads(response.text or "")
            except ValueError:
                return {}
        pages = data.get("pages") if isinstance(data, dict) else None
        if not isinstance(pages, list):
            return {}
        return {str(p.get("path")): p for p in pages if isinstance(p, dict)}

    def enrich(self, *, limit: int = 3 * BATCH, stamp: str | None = None) -> EnrichReport:
        """Write bilingual aliases, summary and model categories for up to `limit`
        pages not yet enriched; call again until `remaining` is 0."""
        if self.model is None or self.alias is None:
            raise ValueError("no_model")
        label = stamp or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        todo = [e for e in self.entries() if not enriched(e)]
        work, failed, refused = todo[:limit], 0, []
        done = 0
        for start in range(0, len(work), BATCH):
            batch = work[start:start + BATCH]
            answers = self._ask(batch)
            if not answers:
                failed += 1
                continue
            for entry in batch:
                answer = answers.get(entry.path)
                if not answer:
                    continue
                categories = sorted({*entry.categories, *(
                    c for c in answer.get("categories") or [] if c in KEYS)})
                aliases = tuple(dict.fromkeys(
                    _clean(a, MAX_ALIAS_CHARS) for a in answer.get("aliases") or []
                    if str(a).strip()))[:MAX_ALIASES]
                original = self.vault.read(entry.path)
                updated = with_frontmatter(original, {
                    "summary_zh": json.dumps(_clean(answer.get("summary_zh"), MAX_SUMMARY_CHARS),
                                             ensure_ascii=False),
                    "summary_en": json.dumps(_clean(answer.get("summary_en"), MAX_SUMMARY_CHARS),
                                             ensure_ascii=False),
                    "aliases": _yaml_list(aliases),
                    "index_categories": _yaml_list(tuple(categories)),
                })
                if _front(updated)[1] != _front(original)[1]:
                    refused.append(entry.path)  # only the frontmatter may change
                    continue
                self.vault.write(entry.path, updated, stamp=label)
                done += 1
        return EnrichReport(done=done, remaining=len(todo) - done, failed_batches=failed,
                            refused=tuple(refused))

    def build(self, *, mode: str = "dry_run", stamp: str | None = None) -> IndexReport:
        """The top index and one sub-index per category; the old flat index.md
        moves, unchanged, to wiki/index/all.md."""
        entries = self.entries()
        groups: dict[str, list[PageEntry]] = {c.key: [] for c in FIXED}
        unassigned = 0
        for entry in entries:
            front, _ = _front(self.vault.read(entry.path))
            keys = set(_list(front, "index_categories")) or set(entry.categories)
            if entry.kind == "sources":
                keys.add(f"sources-{entry.area or 'other'}")
            elif not keys & {c.key for c in (*MARKETS, *PRODUCTS, COMPANIES)}:
                keys.add(TECHNICAL.key)
            if not keys:
                unassigned += 1
            for key in keys:
                groups.setdefault(key, []).append(entry)
        files: dict[str, str] = {}
        titles: dict[str, str] = {}
        for key, members in sorted(groups.items()):
            if not members:
                continue
            titles[key] = category_title(key)
            if len(members) <= MAX_ENTRIES:
                files[f"{INDEX_DIR}/{key}.md"] = _page(titles[key], members)
                continue
            # Too long to read in one prompt: a hub page of smaller parts. A
            # market splits by product line first (the domain matrix cells).
            parts: dict[str, list[PageEntry]] = {}
            for e in members:
                cells = [p.key for p in PRODUCTS if p.key in e.categories] \
                    if key.startswith("market-") else []
                for part in cells or [f"kind-{e.kind}"]:
                    parts.setdefault(part, []).append(e)
            hub = [f"---\ntitle: Index — {titles[key]}\ntype: index\n---\n",
                   f"# {titles[key]}\n"]
            for part, chunk_members in sorted(parts.items()):
                ordered = sorted(chunk_members, key=lambda m: m.title.lower())
                chunks = [ordered[i:i + MAX_ENTRIES] for i in range(0, len(ordered), MAX_ENTRIES)]
                for number, chunk in enumerate(chunks, 1):
                    label = part_title(part) + (f" ({number}/{len(chunks)})" if len(chunks) > 1
                                                else "")
                    title = f"{titles[key]} — {label}"
                    files[f"{INDEX_DIR}/{key}--{part}-{number}.md"] = _page(title, chunk)
                    hub.append(f"- [[Index — {title}]] — {len(chunk)} pages")
            files[f"{INDEX_DIR}/{key}.md"] = "\n".join(hub) + "\n"
        top = ["# Index — 分類目錄 / Categories\n",
               "每個分類一頁目錄，每行一句中英雙語說明。 Each category has its own index page.\n"]
        top += [f"- [[Index — {titles[key]}]] — {len(groups[key])} pages" for key in titles]
        top.append(f"- [[{ALL_TITLE}]] — the previous flat index, unchanged")
        written = (*sorted(files), f"{INDEX_DIR}/all.md", "index.md")
        report = IndexReport(pages=len(entries), unassigned=unassigned,
                             categories={k: len(v) for k, v in groups.items() if v},
                             written=written)
        if mode != "apply":
            return report
        label = stamp or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        old = self.vault.read("index.md")
        if not self.vault.exists(f"{INDEX_DIR}/all.md"):
            self.vault.write(f"{INDEX_DIR}/all.md",
                             f"---\ntitle: {ALL_TITLE}\ntype: index\n---\n" + old, stamp=label)
        for rel, content in files.items():
            self.vault.write(rel, content, stamp=label)
        self.vault.write("index.md", "\n".join(top) + "\n", stamp=label)
        return report
