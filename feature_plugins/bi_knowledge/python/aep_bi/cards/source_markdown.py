"""A source's Markdown: read it, convert it on first need, save a person's edit.

BI vault phase V2 (`docs/phases/BI_VAULT.md` §5, owner 2026-10-28; contract
in `docs/CONTRACTS.md` "BI source Markdown"). Every run reads the current
revision of its source's Markdown and records which one, so an evidence
line number always points into a text that still exists: a revision is
never changed, a person's edit is a new revision, and the original file is
never touched.

A source added before V2 has no Markdown; the first thing that needs it (a
run, a session sample, the Markdown view) converts it then, as the person
who added the source. A conversion that fails is recorded on the source
(`convert_error`) and tried again the next time.

Table sources (CSV, TSV, Excel) are read back from their Markdown in the
exact mode (`readers.markdown_tables(..., exact=True)`); a Markdown report
keeps the phase 3 reading.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import Any

from aep_bi.cards import convert, readers
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStoreError

MAX_MARKDOWN_CHARS = 2_000_000
MAX_NOTE_CHARS = 300


def _source(staging: Staging, source_id: str) -> dict[str, Any]:
    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    return source


def _convert(staging: Staging, source: dict[str, Any]) -> int:
    """Convert a source that has no Markdown yet; its revision number."""
    staging.store.refuse_write()
    try:
        text, assets = convert.convert_with_assets(
            source["name"], staging.source_bytes(source["id"])
        )
    except BiStoreError as error:
        staging.record_conversion_failure(source["id"], error)
        raise
    try:
        record, _ = staging.add_markdown(
            source["id"],
            text,
            origin="conversion",
            note="轉檔",
            actor=str(source["by"]),
            base_rev=0,
            converter=convert.CONVERTER,
            assets=assets,
        )
    except BiStoreError as error:
        if error.code != "markdown_stale":
            raise
        return int(error.detail["current_rev"])  # converted at the same moment elsewhere
    _index(staging)
    return int(record["rev"])


def current(staging: Staging, source_id: str) -> tuple[int, str]:
    """(revision, text) of the source's current Markdown, converted first
    when it has none."""
    source = _source(staging, source_id)
    rev = int(source["markdown_rev"] or 0) or _convert(staging, source)
    return rev, staging.markdown_text(source_id, rev)


def tables(source: dict[str, Any], text: str) -> list[dict[str, Any]]:
    """The tables a rule run reads from a source's Markdown: a converted
    table source exactly (an Excel table remembers its sheet), a Markdown
    report as phase 3 read it."""
    name = PurePath(source["name"]).name
    if convert.kind(source["name"]) != "table":
        return readers.markdown_tables(text, name)
    found = readers.markdown_tables(text, name, exact=True)
    if readers.suffix(source["name"]) in readers.EXCEL:
        for table in found:
            table["sheet"] = table["title"]
    return found


def view(workspace: Path, dataset: str, source_id: str, rev: Any = None) -> dict[str, Any]:
    """The current Markdown (or revision `rev`) with every revision listed."""
    staging = Staging(workspace, dataset)
    current_rev, text = current(staging, source_id)
    chosen = current_rev
    if rev is not None:
        chosen = _rev(rev)
        text = staging.markdown_text(source_id, chosen)
    revisions = staging.markdown_revisions(source_id)
    record = next((r for r in revisions if r["rev"] == chosen), None)
    return {
        "source": _source(staging, source_id),
        "current_rev": current_rev,
        "revision": record,
        "markdown": text,
        "revisions": revisions,
    }


def _rev(value: Any) -> int:
    if isinstance(value, bool):
        raise BiStoreError("markdown_rev_invalid", "rev 必須是正整數")
    try:
        number = int(str(value))
    except ValueError as error:
        raise BiStoreError("markdown_rev_invalid", "rev 必須是正整數") from error
    if number < 1:
        raise BiStoreError("markdown_rev_invalid", "rev 必須是正整數")
    return number


def save(
    workspace: Path,
    dataset: str,
    source_id: str,
    *,
    markdown: Any,
    base_rev: Any,
    note: Any,
    actor: str,
) -> dict[str, Any]:
    """A person's edit as the next revision. `base_rev` is the revision the
    edit was made from (0 for a source that could not be converted)."""
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    source = _source(staging, source_id)
    if not isinstance(markdown, str) or not markdown.strip():
        raise BiStoreError("markdown_missing", "沒有 Markdown 內容")
    if len(markdown) > MAX_MARKDOWN_CHARS:
        raise BiStoreError("markdown_too_large", f"Markdown 最多 {MAX_MARKDOWN_CHARS} 個字")
    if isinstance(base_rev, bool) or not isinstance(base_rev, int):
        raise BiStoreError("base_rev_missing", "需要 base_rev（你修改的是第幾版）")
    text_note = str(note or "").strip()
    if len(text_note) > MAX_NOTE_CHARS:
        raise BiStoreError("note_too_long", f"說明最多 {MAX_NOTE_CHARS} 個字")
    if not source["markdown_rev"]:
        try:
            _convert(staging, source)
        except BiStoreError as error:
            if error.code in ("source_unknown", "dataset_read_only"):
                raise
            # It cannot be converted: the person's text becomes revision 1.
    record, already = staging.add_markdown(
        source_id,
        markdown.replace("\r\n", "\n"),
        origin="edit",
        note=text_note,
        actor=actor,
        base_rev=base_rev,
    )
    if not already:
        _index(staging)
    return {
        "source": _source(staging, source_id),
        "revision": record,
        "current_rev": record["rev"],
        "already": already,
    }


def _index(staging: Staging) -> None:
    """Keep the search index current (BI vault V3); never fails the write."""
    from aep_bi.cards import search_index

    search_index.sync_quietly(staging.store)
