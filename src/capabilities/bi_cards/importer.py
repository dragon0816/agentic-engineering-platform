"""CSV import for BI cards (AEP-K14, Case A): preview, then apply.

The preview writes nothing (DQ-9, Case A §4.7 item 1): it shows each cell's
raw and normalised value, the value stored now and what would change, and
warns about unknown columns, missing link targets, link and type mismatches
and the ignored Application priority (#222). Behaviour follows the
fixture's `bi_ingest.py` (column aliases, dates with ROC years, list
splitting, enum aliases, integer ranges, `skip_rows`, `defaults`,
`enum_aliases`) without importing it; lenient conversions are warnings, not
silent guesses.

A preview is kept in memory only (never searchable, never in the store)
until it is applied or expires.
"""

from __future__ import annotations

import csv
import io
import re
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from capabilities.bi_cards import domains, names
from capabilities.bi_cards.catalog import for_store
from capabilities.bi_cards.schema import Registry, TypeDef, norm_key
from capabilities.bi_cards.store import ApplyResult, BiStore, PlannedRow

#: The fixture marks example data in the text (「(虛構範例)」, 「[範例資料,待業務/FAE
#: 驗證]」); such a card is synthetic and never trusted (DQ-1).
FICTIONAL = re.compile(r"虛構|範例|示範|待[^,，。]{0,10}驗證|待查證|^SAMPLE-")
MAX_PREVIEWS = 50


class ImportError_(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Preview:
    preview_id: str
    dataset: str
    entity_type: str
    filename: str
    kind: str
    columns: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    planned: dict[int, PlannedRow] = field(default_factory=dict)

    def summary(self) -> dict[str, int]:
        counts = {"create": 0, "update": 0, "unchanged": 0, "skip": 0}
        for row in self.rows:
            counts[row["action"]] += 1
        warnings = sum(len(r["warnings"]) for r in self.rows) + sum(
            1 for c in self.columns if c["status"] in ("unknown", "ignored")
        )
        return {**counts, "warnings": warnings}

    def to_api(self) -> dict[str, Any]:
        return {
            "preview_id": self.preview_id,
            "entity_type": self.entity_type,
            "columns": self.columns,
            "rows": self.rows,
            "summary": self.summary(),
        }


_PREVIEWS: OrderedDict[str, Preview] = OrderedDict()
_LOCK = threading.Lock()


def remember(preview: Preview) -> None:
    with _LOCK:
        _PREVIEWS[preview.preview_id] = preview
        while len(_PREVIEWS) > MAX_PREVIEWS:
            _PREVIEWS.popitem(last=False)


def recall(preview_id: str) -> Preview | None:
    with _LOCK:
        return _PREVIEWS.get(preview_id)


def forget(preview_id: str) -> None:
    with _LOCK:
        _PREVIEWS.pop(preview_id, None)


def canonical_key(entity: TypeDef, values: dict[str, Any]) -> str:
    parts = [str(values.get(name) or "").strip() for name in entity.naming]
    if not all(parts):
        return ""
    return re.sub(r"\s+", " ", "-".join(parts))


def read_rows(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    text = csv_text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    try:
        headers = [h.strip() for h in next(reader)]
    except StopIteration as error:
        raise ImportError_("csv_empty", "CSV 沒有內容") from error
    rows = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue
        rows.append({h: (values[i] if i < len(values) else "") for i, h in enumerate(headers)})
    return headers, rows


def _skipped(row: dict[str, str], rules: list[dict[str, Any]]) -> bool:
    for rule in rules:
        cell = str(row.get(str(rule.get("column", "")), "")).lower()
        if any(str(word).lower() in cell for word in rule.get("contains", [])):
            return True
    return False


def _canonical_names(configured: Any, entity: TypeDef, item: Any, value: Any) -> Any:
    """A card name or link target in its canonical spelling (the cards'
    `aliases`, then the configuration's `name_aliases`; `names.Names`)."""
    if not (item.is_link or item.name == entity.naming_field):
        return value
    if isinstance(value, list):
        return list(dict.fromkeys(configured.canon(v) for v in value))
    return configured.canon(value)


def preview(
    store: BiStore,
    *,
    entity_type: str | None,
    filename: str,
    csv_text: str,
    mapping: dict[str, Any] | None = None,
    kind: str = "import",
    extra_keys: dict[str, set[str]] | None = None,
    schema: Registry | None = None,
) -> Preview:
    """Read, map and normalise a CSV against the store and the dataset's
    schema; writes nothing."""
    reg = schema or for_store(store)
    mapping = dict(mapping or {})
    headers, raw_rows = read_rows(csv_text)
    explicit: dict[str, str] = {
        norm_key(k): str(v) for k, v in dict(mapping.get("columns") or {}).items()
    }
    chosen = (
        entity_type
        or mapping.get("entity_type")
        or reg.type_in_filename(filename)
        or reg.guess_type(headers)
    )
    if not chosen:
        raise ImportError_("entity_type_unknown", "無法從欄名判斷卡片類型，請指定類型")
    try:
        entity = reg.type(str(chosen))
    except KeyError as error:
        raise ImportError_("entity_type_unknown", f"沒有這種卡片類型：{chosen}") from error
    columns: list[dict[str, Any]] = []
    by_header: dict[str, str] = {}
    for header in headers:
        target = explicit.get(norm_key(header))
        if target is not None:
            if entity.get(target) is not None:
                columns.append(
                    {"source": header, "field": target, "status": "mapped", "note": "mapping 指定"}
                )
                by_header[header] = target
                continue
            columns.append(
                {
                    "source": header,
                    "field": None,
                    "status": "unknown",
                    "note": f"mapping 指定的欄位 {target} 不在 {entity.name}",
                }
            )
            continue
        name, status, note = reg.map_column(entity, header)
        if name is not None and name in by_header.values():
            columns.append(
                {"source": header, "field": None, "status": "ignored", "note": "重複對應同一欄位"}
            )
            continue
        columns.append({"source": header, "field": name, "status": status, "note": note})
        if name is not None:
            by_header[header] = name
    # The dataset's per-domain configuration (BI vault V10): its enum aliases
    # under the mapping's, and its name aliases for names and link targets.
    configured = domains.read(store)
    canonical = names.from_store(store, configured)  # the cards' aliases (BI D2)
    extra_aliases = {
        **(configured.enum_aliases if configured is not None else {}),
        **dict(mapping.get("enum_aliases") or {}),
    }
    defaults = dict(mapping.get("defaults") or {})
    skip_rules = list(mapping.get("skip_rows") or [])
    ignored_priority = [
        c
        for c in columns
        if c["status"] == "ignored" and c["field"] is None and "優先度" in c["note"]
    ]

    # Keys known for link resolution: the store, this file, and callers' extras.
    known: dict[str, set[str]] = {}
    for card in store.card_rows():
        known.setdefault(card["entity_type"], set()).add(card["canonical_key"])
    for type_name, keys in (extra_keys or {}).items():
        known.setdefault(type_name, set()).update(keys)

    staged: list[tuple[int, dict[str, Any], dict[str, str], list[dict[str, str]], bool]] = []
    for number, raw in enumerate(raw_rows, start=2):
        warnings: list[dict[str, str]] = []
        if _skipped(raw, skip_rules):
            staged.append(
                (number, {}, {}, [{"code": "row_skipped", "message": "skip_rows 規則"}], False)
            )
            continue
        values: dict[str, Any] = {}
        raws: dict[str, str] = {}
        for header, name in by_header.items():
            item = entity.get(name)
            assert item is not None
            cell = raw.get(header, "")
            value, problems = reg.normalize(item, cell, extra_aliases)
            if canonical and value is not None:
                value = _canonical_names(canonical, entity, item, value)
            raws[name] = cell
            warnings.extend({"code": c, "message": m} for c, m in problems)
            if value is not None:
                values[name] = value
        if entity.get("node") and entity.get("nodes") and values.get("node"):
            merged = [values["node"], *[n for n in values.get("nodes", []) if n != values["node"]]]
            values["nodes"] = merged
        synthetic = kind == "fixture" or any(FICTIONAL.search(str(v)) for v in raw.values())
        if values.get("confidence") == "verified" and synthetic:
            values["confidence"] = "assumed"
            warnings.append(
                {
                    "code": "fictional_not_trusted",
                    "message": "來源標示為範例或虛構資料：信心度維持 assumed，不視為已驗證",
                }
            )
        for column in ignored_priority:
            if str(raw.get(column["source"], "")).strip():
                warnings.append({"code": "priority_ignored", "message": column["note"]})
        staged.append((number, values, raws, warnings, synthetic))
        key = canonical_key(entity, values)
        if key:
            known.setdefault(entity.name, set()).add(key)

    result = Preview(
        preview_id=uuid.uuid4().hex[:12],
        dataset=store.dataset,
        entity_type=entity.name,
        filename=filename,
        kind=kind,
        columns=columns,
        rows=[],
    )
    for number, values, raws, warnings, synthetic in staged:
        key = canonical_key(entity, values)
        if not key:
            if not any(w["code"] == "row_skipped" for w in warnings):
                warnings.append(
                    {"code": "name_missing", "message": f"沒有{entity.naming_field}，略過這一列"}
                )
            result.rows.append(
                {
                    "row": number,
                    "canonical_key": "",
                    "action": "skip",
                    "fields": [],
                    "warnings": warnings,
                }
            )
            continue
        # Links: a target must exist as the right type (DQ-3, DQ-5).
        for name, value in values.items():
            item = entity.get(name)
            if item is None or not item.is_link:
                continue
            for target in value if isinstance(value, list) else [value]:
                if item.link_to and any(target in known.get(t, set()) for t in item.link_to):
                    continue
                if not item.link_to and any(target in keys for keys in known.values()):
                    continue
                other = [t for t, keys in known.items() if target in keys]
                if other:
                    warnings.append(
                        {
                            "code": "link_type_mismatch",
                            "message": f"{item.label}「{target}」是 {other[0]} 卡，"
                            f"不是 {'/'.join(item.link_to)}",
                        }
                    )
                else:
                    warnings.append(
                        {
                            "code": "link_missing",
                            "message": f"{item.label}「{target}」找不到對應卡片（不建立連結）",
                        }
                    )
        existing = store.find(entity.name, key)
        current = store.fields(existing["id"]) if existing is not None else {}
        if existing is None:
            for name, default in defaults.items():
                item = entity.get(name)
                if item is not None and name not in values:
                    adopted, _ = reg.normalize(item, str(default), extra_aliases)
                    if adopted is not None:
                        values[name] = adopted
                        raws.setdefault(name, "")
            for item in entity.fields:
                if item.default not in (None, "today") and item.name not in values:
                    values[item.name] = item.default
                    raws.setdefault(item.name, "")
        cells: list[dict[str, Any]] = []
        changes = 0
        for name, value in values.items():
            stored = current.get(name)
            if stored is None:
                change = "add"
                changes += 1
            elif stored["value"] == value:
                change = "same"
            elif stored["kind"] == "human":
                change = "human_kept"
            else:
                change = "change"
                changes += 1
            cells.append(
                {
                    "field": name,
                    "raw": raws.get(name, ""),
                    "normalized": value,
                    "current": None if stored is None else stored["value"],
                    "change": change,
                }
            )
        for name, cell in raws.items():
            if name not in values and cell.strip():
                cells.append(
                    {
                        "field": name,
                        "raw": cell,
                        "normalized": None,
                        "current": None if name not in current else current[name]["value"],
                        "change": "same",
                    }
                )
        action = "create" if existing is None else ("update" if changes else "unchanged")
        result.rows.append(
            {
                "row": number,
                "canonical_key": key,
                "action": action,
                "fields": cells,
                "warnings": warnings,
            }
        )
        name_value = str(values.get(entity.naming[-1]) or key)
        result.planned[number] = PlannedRow(
            row=number,
            entity_type=entity.name,
            canonical_key=key,
            name=name_value,
            values=values,
            synthetic=synthetic,
        )
    return result


def apply(store: BiStore, prepared: Preview, rows: list[int] | None, *, actor: str) -> ApplyResult:
    chosen = [
        planned
        for number, planned in sorted(prepared.planned.items())
        if rows is None or number in rows
    ]
    return store.apply(
        chosen,
        filename=prepared.filename,
        entity_type=prepared.entity_type,
        actor=actor,
        kind=prepared.kind,
    )
