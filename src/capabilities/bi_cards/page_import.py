"""Import Obsidian card pages (`docs/phases/BI_CARD_PAGE_IMPORT.md`, owner 2026-11-03).

A page's frontmatter is read strictly and goes through `importer.preview`, the same
mapping and normalisation as a CSV; no model is involved. Nothing is invented: what
cannot be read is a listed problem, an unknown field a listed column, an invalid
value a listed warning. On apply each page becomes a source, kept with the cards as
their evidence, and the rows are written in one transaction through `commit_run`.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from typing import Any

from capabilities.bi_cards import importer
from capabilities.bi_cards.catalog import for_store
from capabilities.bi_cards.schema import Registry, norm_key
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore, BiStoreError, PlannedRow

MAX_PAGES = 5000
MAX_EXCERPT = 500
MAX_PREVIEWS = 10
_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")
_ITEM = re.compile(r"^\s*-\s*(.*)$")
_LINK = re.compile(r"^\[\[([^\]|]+)(?:\|[^\]]*)?\]\]$")


def _problem(path: str, code: str, message: str, line: int | None = None) -> dict[str, Any]:
    found: dict[str, Any] = {"path": path, "code": code, "message": message}
    return found if line is None else {**found, "line": line}


def _scalar(text: str) -> str:
    value = text.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    linked = _LINK.match(value.strip())
    return linked.group(1).strip() if linked else value


def _inline_list(text: str) -> list[str] | None:
    """`[a, "b, c", [[d]]]` as items; None when it does not close."""
    items: list[str] = []
    buf: list[str] = []
    quote = ""
    depth = 0
    body = text.strip()[1:]
    for index, ch in enumerate(body):
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'" and not "".join(buf).strip():
            quote = ch
            buf.append(ch)
        elif ch == "[":
            depth += 1
            buf.append(ch)
        elif ch == "]" and depth:
            depth -= 1
            buf.append(ch)
        elif ch == "]":
            if body[index + 1 :].strip():
                return None
            last = "".join(buf).strip()
            return [*items, *([_scalar(last)] if last else [])]
        elif ch == "," and not depth:
            items.append(_scalar("".join(buf)))
            buf = []
        else:
            buf.append(ch)
    return None


@dataclass
class Page:
    """What one page's frontmatter says."""

    path: str
    values: dict[str, Any] = field(default_factory=dict)
    lines: dict[str, int] = field(default_factory=dict)
    raw: dict[str, str] = field(default_factory=dict)
    problems: list[dict[str, Any]] = field(default_factory=list)
    has_frontmatter: bool = False


def parse_page(path: str, text: str) -> Page:
    """Read the frontmatter; anything outside the subset is a listed problem."""
    page = Page(path)
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return page
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        page.problems.append(_problem(path, "frontmatter_open", "frontmatter 沒有結束的 ---", 1))
        return page
    page.has_frontmatter = True
    current: str | None = None
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = _ITEM.match(line)
        if item is not None and current is not None and isinstance(page.values[current], list):
            page.values[current].append(_scalar(item.group(1)))
            page.raw[current] += "\n" + line
            continue
        found = _KEY.match(line)
        if found is None or line[0].isspace():
            page.problems.append(
                _problem(path, "frontmatter_line", f"看不懂這一行：{line[:80]}", number)
            )
            current = None
            continue
        key, value = found.group(1), found.group(2).strip()
        page.lines[key] = number
        page.raw[key] = line
        if key in page.values:
            page.problems.append(_problem(path, "frontmatter_repeat", f"{key} 重複了", number))
        current = None
        if not value:
            page.values[key] = []
            current = key
        elif value.startswith("["):
            if value.startswith("[["):
                page.values[key] = _scalar(value)
                continue
            parsed = _inline_list(value)
            if parsed is None:
                page.problems.append(
                    _problem(path, "frontmatter_list", f"{key} 的清單沒有結束", number)
                )
                page.values.pop(key, None)
            else:
                page.values[key] = parsed
        elif value.startswith("{"):
            page.problems.append(
                _problem(path, "frontmatter_map", f"{key} 是巢狀結構，不支援", number)
            )
        else:
            page.values[key] = _scalar(value)
    return page


def _type_of(reg: Registry, given: Any) -> str | None:
    wanted = norm_key(str(given or "")).replace("_", "")
    return (
        next((n for n in reg.types if norm_key(n).replace("_", "") == wanted), None)
        if wanted
        else None
    )


def _skip_reason(path: str, text: str) -> str | None:
    parts = PurePosixPath(path).parts
    if any(part == "_Templates" or part.startswith(".") for part in parts):
        return "範本或設定資料夾"
    if PurePosixPath(path).name.startswith("Dashboard-"):
        return "Dataview 產生的 Dashboard 頁"
    if "<%" in text.split("\n---", 1)[0]:
        return "Templater 範本"
    return None


@dataclass
class PagePreview:
    preview_id: str
    dataset: str
    samples: bool
    previews: list[importer.Preview]
    #: For each preview, the file each of its rows came from, in row order.
    origins: list[list[str]]
    pages: dict[str, str]
    parsed: dict[str, Page]
    problems: list[dict[str, Any]]
    skipped: list[dict[str, str]]

    def to_api(self) -> dict[str, Any]:
        counts = {"create": 0, "update": 0, "unchanged": 0, "skip": 0, "warnings": 0}
        for item in self.previews:
            for key, value in item.summary().items():
                counts[key] = counts.get(key, 0) + value
        planned = [p for item in self.previews for p in item.planned.values()]
        return {
            "preview_id": self.preview_id,
            "summary": {
                **counts,
                "pages": len(self.pages),
                "samples": sum(1 for p in planned if p.synthetic),
                "problems": len(self.problems),
                "skipped": len(self.skipped),
            },
            "types": [
                {
                    "entity_type": item.entity_type,
                    "filename": item.filename,
                    "columns": item.columns,
                    "rows": item.rows,
                }
                for item in self.previews
            ],
            "problems": self.problems,
            "skipped": self.skipped,
        }


_PREVIEWS: OrderedDict[str, PagePreview] = OrderedDict()
_LOCK = threading.Lock()


def recall(preview_id: str) -> PagePreview | None:
    with _LOCK:
        return _PREVIEWS.get(preview_id)


def forget(preview_id: str) -> None:
    with _LOCK:
        _PREVIEWS.pop(preview_id, None)


def _remember(preview: PagePreview) -> None:
    with _LOCK:
        _PREVIEWS[preview.preview_id] = preview
        while len(_PREVIEWS) > MAX_PREVIEWS:
            _PREVIEWS.popitem(last=False)


def _checked_pages(given: Any) -> list[tuple[str, str]]:
    if not isinstance(given, list) or not given:
        raise BiStoreError("pages_missing", "沒有選到卡片頁")
    if len(given) > MAX_PAGES:
        raise BiStoreError("pages_too_many", f"一次最多 {MAX_PAGES} 個檔案")
    pages = []
    for item in given:
        path = item.get("path") if isinstance(item, dict) else None
        text = item.get("text") if isinstance(item, dict) else None
        if not isinstance(path, str) or not path or not isinstance(text, str):
            raise BiStoreError("pages_invalid", "每個檔案都要有 path 和 text")
        pages.append((path.replace("\\", "/"), text))
    return pages


def preview(store: BiStore, given: Any, *, samples: bool = False) -> PagePreview:
    """Read the files and preview every type; writes nothing."""
    reg = for_store(store)
    problems: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    parsed: dict[str, Page] = {}
    kept: dict[str, str] = {}
    by_type: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    tables: list[tuple[str, str]] = []
    for path, text in _checked_pages(given):
        reason = _skip_reason(path, text)
        if reason is not None:
            skipped.append({"path": path, "reason": reason})
            continue
        if path.lower().endswith(".csv"):
            tables.append((path, text))
            kept[path] = text
            continue
        if not path.lower().endswith(".md"):
            skipped.append({"path": path, "reason": "不是 .md 或 .csv"})
            continue
        page = parse_page(path, text)
        problems.extend(page.problems)
        if not page.has_frontmatter:
            if not page.problems:
                skipped.append({"path": path, "reason": "沒有 frontmatter，不是卡片頁"})
            continue
        chosen = _type_of(reg, page.values.get("type"))
        if chosen is None:
            problems.append(
                _problem(
                    path,
                    "type_unknown",
                    f"不認得卡片類型：{page.values.get('type')!r}",
                    page.lines.get("type"),
                )  # fmt: skip
            )
            continue
        parsed[path] = page
        kept[path] = text
        row = {k: v for k, v in page.values.items() if k != "type"}
        by_type.setdefault(chosen, []).append((path, row))

    def previews(
        known: dict[str, set[str]] | None, renamed: dict[str, str] | None = None
    ) -> list[tuple[importer.Preview, list[str]]]:
        found = []
        for entity_type, rows in sorted(by_type.items()):
            headers = sorted({k for _, row in rows for k in row})
            found.append((
                importer.preview(
                    store, entity_type=entity_type, filename=f"pages:{entity_type}",
                    csv_text="", rows=(headers, [row for _, row in rows]),
                    extra_keys=known, samples=samples, links_renamed=renamed,
                ),
                [path for path, _ in rows],
            ))  # fmt: skip
        for path, text in tables:
            try:
                prepared = importer.preview(
                    store, entity_type=None, filename=PurePosixPath(path).name, csv_text=text,
                    extra_keys=known, samples=samples, links_renamed=renamed,
                )  # fmt: skip
            except importer.ImportError_ as failure:
                problems.append(_problem(path, failure.code, failure.message))
                continue
            found.append((prepared, [path] * len(prepared.rows)))
        return found

    first = previews(None)
    known: dict[str, set[str]] = {}
    renamed: dict[str, str] = {}
    for item, _ in first:
        renamed.update(item.renamed)
        for planned in item.planned.values():
            known.setdefault(planned.entity_type, set()).add(planned.canonical_key)
    problems[:] = [p for p in problems if p["code"] not in _TABLE_CODES]
    final = previews(known, renamed)
    result = PagePreview(
        preview_id=uuid.uuid4().hex[:12],
        dataset=store.dataset,
        samples=samples,
        previews=[item for item, _ in final],
        origins=[paths for _, paths in final],
        pages=kept,
        parsed=parsed,
        problems=problems,
        skipped=skipped,
    )
    _remember(result)
    return result


#: Codes `previews` reports for a table on each pass: the first pass's are dropped.
_TABLE_CODES = frozenset({"csv_empty", "entity_type_unknown"})


def _evidence(
    prepared: PagePreview, path: str, planned: PlannedRow, source: dict[str, Any], number: int
) -> dict[str, list[dict[str, Any]]]:
    page = prepared.parsed.get(path)
    found: dict[str, list[dict[str, Any]]] = {}
    for name in planned.values:
        if page is None:  # a table: the row is the locator
            locator: dict[str, Any] = {"line": number, "column": name}
            excerpt = ""
        else:
            key = next((k for k in page.lines if norm_key(k) == norm_key(name)), name)
            locator = {"line": page.lines.get(key), "key": key}
            excerpt = page.raw.get(key, "")[:MAX_EXCERPT]
        found[name] = [{"source_id": source["id"], "source_name": source["name"],
                        "locator": locator, "excerpt": excerpt, "basis": "fact"}]  # fmt: skip
    return found


def apply(
    store: BiStore, prepared: PagePreview, *, actor: str, folder: Any = None
) -> dict[str, Any]:
    """Keep each file as a source and write every row in one transaction."""
    staging = Staging(store.workspace, store.dataset)
    rows: list[tuple[PlannedRow, str, int | None]] = []
    sources: dict[str, dict[str, Any]] = {}
    for item, paths in zip(prepared.previews, prepared.origins, strict=True):
        for number, planned in sorted(item.planned.items()):
            path = paths[number - 2]
            if not planned.canonical_key:
                continue
            action = next((r["action"] for r in item.rows if r.get("row") == number), "create")
            if action in ("skip", "unchanged"):
                continue
            if path not in sources:
                sources[path] = staging.add_source(
                    PurePosixPath(path).name, text=prepared.pages[path], folder=folder, actor=actor
                )
            current = store.find(planned.entity_type, planned.canonical_key)
            proof = _evidence(prepared, path, planned, sources[path], number)
            rows.append(
                (
                    replace(planned, ref=path, evidence=proof),
                    f"page-{number}",
                    None if current is None else int(current["version"]),
                )
            )
    if not rows:
        return {"written": False, "sources": len(sources), "applied": None}
    run_id = staging.create_run(
        kind="ingest",
        method_ref="page-import",
        schema_ref=for_store(store).ref,
        model=None,
        source_ids=[s["id"] for s in sources.values()],
        actor=actor,
    )
    applied = store.commit_run(run_id, rows, filename=f"卡片頁（{len(sources)} 頁）", actor=actor)
    staging.set_status(
        run_id,
        "committed",
        commit_result={"import_id": applied.import_id, "created": applied.created,
                       "updated": applied.updated},
    )  # fmt: skip
    return {
        "written": True,
        "sources": len(sources),
        "import_id": applied.import_id,
        "applied": {
            "created": applied.created,
            "updated": applied.updated,
            "unchanged": applied.unchanged,
            "proposals": applied.proposals,
        },
    }
