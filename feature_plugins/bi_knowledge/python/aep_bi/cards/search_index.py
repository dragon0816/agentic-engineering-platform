"""The search index of a BI dataset: SQLite FTS5 with the trigram tokenizer.

BI vault phase V3 (`docs/phases/BI_VAULT.md` §6.1, owner 2026-10-28;
contract in `docs/CONTRACTS.md` "BI search index"). Before V3 a search
scanned every card; the vault also needs to find passages in the sources'
Markdown, which a scan of the cards cannot. The trigram tokenizer matches
any three characters, so Chinese is found without a word splitter.

The index is a cache, never the truth: it lives in its own file
`<dataset>/search.sqlite` (not in `bi.sqlite`), is rebuilt from the cards and
the Markdown at any time (`rebuild`), and a failure to update it never fails
the write that caused it (`sync_quietly`; the status then says it is behind).

- **Cards**: one row per card holding its name, key and the values of the
  fields its schema has now (a retired field is not searched, as in
  `service.search`). A card is re-indexed when its `version` moves, and every
  card when the dataset's schema changes.
- **Markdown**: the current revision of every source, cut into chunks of
  about `CHUNK_CHARS` characters along headings and paragraphs
  (`extract.chunks`), each with its source, revision and line range.

`sync` brings the index up to date incrementally; `BiStore` calls it after
every write (commit, edit, proposal, undo, schema upgrade, demo load) and a
Markdown save calls it too. A query term shorter than three characters
cannot use the trigram index, so such a query scans the indexed rows
(`mode: "scan"`). `service.search` is unchanged.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from aep_bi.cards import catalog, extract
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import PUBLISHED_SOURCES, BiStore, BiStoreError, now

INDEX_FILE = "search.sqlite"
TOKENIZER = "trigram"
CHUNK_CHARS = 1200
SNIPPET_CHARS = 160
MAX_TERMS = 8
MAX_QUERY_CHARS = 200
DEFAULT_LIMIT = 20
#: Passages one `bi__query` search returns.
PASSAGE_LIMIT = 5
MAX_LIMIT = 100

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cards (
  card_id TEXT PRIMARY KEY,
  version INTEGER NOT NULL,
  entity_type TEXT NOT NULL,
  name TEXT NOT NULL,
  canonical_key TEXT NOT NULL,
  fields TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS card_text USING fts5(
  text, card_id UNINDEXED, tokenize='{TOKENIZER}'
);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  rev INTEGER NOT NULL,
  name TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_text USING fts5(
  text, source_id UNINDEXED, rev UNINDEXED, line_start UNINDEXED, line_end UNINDEXED,
  tokenize='{TOKENIZER}'
);
"""


def index_path(store: BiStore) -> Path:
    return store.dir / INDEX_FILE


def _has_data(store: BiStore) -> bool:
    """Whether there is anything to index; reading an empty dataset must not
    create files in the workspace."""
    return store.exists or index_path(store).is_file() or (store.dir / "staging.sqlite").is_file()


@contextmanager
def _db(store: BiStore) -> Iterator[sqlite3.Connection]:
    path = index_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(SCHEMA)
        yield connection
        connection.commit()
    finally:
        connection.close()


def _meta(db: sqlite3.Connection, key: str) -> str | None:
    row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return None if row is None else str(row[0])


def _set_meta(db: sqlite3.Connection, key: str, value: str) -> None:
    db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


def _flat(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(v) for v in value if v is not None)
    return "" if value is None else str(value)


# -- what the index should hold ------------------------------------------------


def _card_versions(store: BiStore) -> dict[str, int]:
    return {str(c["id"]): int(c["version"]) for c in store.card_rows()} if store.exists else {}


def _source_revisions(store: BiStore) -> dict[str, int]:
    if store.view is not None and store.read_only:
        return _published_revisions(store)
    if store.read_only:
        return {}  # a subscribed copy has no sources on this PC
    return dict(Staging(store.workspace, store.dataset).markdown_sources())


def _published_revisions(store: BiStore) -> dict[str, int]:
    """A vault's published view: the revisions in that version (written beside it
    by `refresh_published`), and of those what this PC still has, so a source
    withdrawn since is gone and an unpushed one was never here. No such file: no
    sources, as for a benchmark's chosen version."""
    assert store.view is not None
    try:
        listed = json.loads((store.view / PUBLISHED_SOURCES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    held = {str(s["id"]) for s in Staging(store.workspace, store.dataset).sources()}
    return {str(k): int(v) for k, v in listed.items() if str(k) in held}


def _behind(db: sqlite3.Connection, store: BiStore) -> dict[str, int | bool]:
    cards = _card_versions(store)
    indexed = {str(r["card_id"]): int(r["version"]) for r in db.execute("SELECT * FROM cards")}
    if _meta(db, "schema") != store.schema_ref():
        stale_cards = len(cards) + len(set(indexed) - set(cards))
    else:
        stale_cards = sum(1 for k, v in cards.items() if indexed.get(k) != v) + len(
            set(indexed) - set(cards)
        )
    sources = _source_revisions(store)
    done = {str(r["source_id"]): int(r["rev"]) for r in db.execute("SELECT * FROM sources")}
    stale_sources = sum(1 for k, v in sources.items() if done.get(k) != v) + len(
        set(done) - set(sources)
    )
    return {
        "cards": stale_cards,
        "sources": stale_sources,
        "behind": bool(stale_cards or stale_sources),
    }


# -- keeping it current --------------------------------------------------------


def _index_cards(db: sqlite3.Connection, store: BiStore, *, full: bool) -> int:
    """Re-index the cards whose version moved (all when `full`); returns how many."""
    cards = {str(c["id"]): c for c in store.card_rows()} if store.exists else {}
    reg = catalog.for_store(store)
    schema = store.schema_ref()
    if full or _meta(db, "schema") != schema:
        db.execute("DELETE FROM cards")
        db.execute("DELETE FROM card_text")
    indexed = {str(r["card_id"]): int(r["version"]) for r in db.execute("SELECT * FROM cards")}
    for gone in set(indexed) - set(cards):
        db.execute("DELETE FROM cards WHERE card_id = ?", (gone,))
        db.execute("DELETE FROM card_text WHERE card_id = ?", (gone,))
    changed = [c for k, c in cards.items() if indexed.get(k) != int(c["version"])]
    everything = store.all_fields() if changed else {}
    for card in changed:
        card_id = str(card["id"])
        entity = reg.types.get(card["entity_type"])
        values = everything.get(card_id, {})
        fields = {
            name: _flat(item["value"])
            for name, item in values.items()
            if (entity is None or entity.get(name) is not None) and _flat(item["value"])
        }
        db.execute("DELETE FROM card_text WHERE card_id = ?", (card_id,))
        db.execute(
            "INSERT OR REPLACE INTO cards (card_id, version, entity_type, name, canonical_key, "
            "fields) VALUES (?, ?, ?, ?, ?, ?)",
            (
                card_id,
                int(card["version"]),
                card["entity_type"],
                card["name"],
                card["canonical_key"],
                json.dumps(fields, ensure_ascii=False),
            ),
        )
        text = "\n".join([card["name"], card["canonical_key"], *fields.values()])
        db.execute("INSERT INTO card_text (text, card_id) VALUES (?, ?)", (text, card_id))
    _set_meta(db, "schema", schema)
    return len(changed)


def _index_sources(db: sqlite3.Connection, store: BiStore, *, full: bool) -> int:
    """Re-index the sources whose current Markdown revision moved."""
    if full:
        db.execute("DELETE FROM sources")
        db.execute("DELETE FROM chunk_text")
    wanted = _source_revisions(store)
    done = {str(r["source_id"]): int(r["rev"]) for r in db.execute("SELECT * FROM sources")}
    for gone in set(done) - set(wanted):
        db.execute("DELETE FROM sources WHERE source_id = ?", (gone,))
        db.execute("DELETE FROM chunk_text WHERE source_id = ?", (gone,))
    changed = [k for k, v in wanted.items() if done.get(k) != v]
    if not changed:
        return 0
    staging = Staging(store.workspace, store.dataset)
    for source_id in changed:
        rev = wanted[source_id]
        source = staging.source(source_id) or {}
        try:
            text = staging.markdown_text(source_id, rev)
        except (BiStoreError, OSError):
            continue  # not readable now (a file only in the cloud): tried again next sync
        db.execute("DELETE FROM chunk_text WHERE source_id = ?", (source_id,))
        for chunk in extract.chunks(text, CHUNK_CHARS):
            db.execute(
                "INSERT INTO chunk_text (text, source_id, rev, line_start, line_end) "
                "VALUES (?, ?, ?, ?, ?)",
                (chunk.text, source_id, rev, chunk.line_start, chunk.line_end),
            )
        db.execute(
            "INSERT OR REPLACE INTO sources (source_id, rev, name) VALUES (?, ?, ?)",
            (source_id, rev, str(source.get("name") or "")),
        )
    return len(changed)


def sync(store: BiStore) -> dict[str, Any]:
    """Bring the index up to date with the cards and the Markdown."""
    if not _has_data(store):
        return {"cards": 0, "sources": 0}
    with _db(store) as db:
        cards = _index_cards(db, store, full=False)
        sources = _index_sources(db, store, full=False)
        _set_meta(db, "updated_at", now())
    return {"cards": cards, "sources": sources}


def sync_quietly(store: BiStore) -> None:
    """`sync` after a write; a failure leaves the index behind, never the
    write failed (the status shows it, `rebuild` repairs it)."""
    try:
        sync(store)
    except Exception:  # noqa: BLE001 - the index is a rebuildable cache
        return


def rebuild(workspace: Path, dataset: str) -> dict[str, Any]:
    """Build the index again from nothing. Sources added before V2 are
    converted first (their first need), so their Markdown is indexed too."""
    from aep_bi.cards import source_markdown

    store = BiStore(workspace, dataset)
    failed = []
    if not store.read_only:
        staging = Staging(workspace, dataset)
        for source in staging.sources():
            if source["markdown_rev"] or source["format"] is None:
                continue
            try:
                source_markdown.current(staging, source["id"])
            except Exception as error:  # noqa: BLE001 - reported per source
                failed.append(
                    {
                        "source_id": source["id"],
                        "name": source["name"],
                        "code": getattr(error, "code", type(error).__name__),
                    }
                )
    with _db(store) as db:
        _index_cards(db, store, full=True)
        _index_sources(db, store, full=True)
        at = now()
        _set_meta(db, "built_at", at)
        _set_meta(db, "updated_at", at)
    return {**status(store), "not_converted": failed}


def status(store: BiStore) -> dict[str, Any]:
    """Cards and chunks indexed, when it was built and updated, whether it is behind."""
    if not index_path(store).is_file() or not _has_data(store):
        cards = len(_card_versions(store))
        sources = len(_source_revisions(store))
        return {
            "exists": False,
            "tokenizer": TOKENIZER,
            "cards": 0,
            "chunks": 0,
            "sources": 0,
            "built_at": None,
            "updated_at": None,
            "behind": bool(cards or sources),
            "behind_cards": cards,
            "behind_sources": sources,
        }
    with _db(store) as db:
        behind = _behind(db, store)
        return {
            "exists": True,
            "tokenizer": TOKENIZER,
            "cards": int(db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]),
            "chunks": int(db.execute("SELECT COUNT(*) FROM chunk_text").fetchone()[0]),
            "sources": int(db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]),
            "built_at": _meta(db, "built_at"),
            "updated_at": _meta(db, "updated_at"),
            "behind": behind["behind"],
            "behind_cards": behind["cards"],
            "behind_sources": behind["sources"],
        }


# -- searching ---------------------------------------------------------------


def terms(query: str) -> list[str]:
    """The query's words (at most `MAX_TERMS`), duplicates dropped."""
    words = query[:MAX_QUERY_CHARS].split()
    return list(dict.fromkeys(w for w in words if w))[:MAX_TERMS]


def _match(words: list[str]) -> str:
    """An FTS5 query: every word as a quoted phrase, all required."""
    return " AND ".join('"' + w.replace('"', '""') + '"' for w in words)


def _like(word: str) -> str:
    escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _rows(
    db: sqlite3.Connection,
    table: str,
    columns: str,
    words: list[str],
    limit: int,
    sources: Sequence[str] | None = None,
) -> tuple[list[sqlite3.Row], str]:
    """`sources` keeps a chunk search to those source ids."""
    within = "" if sources is None else f" AND source_id IN ({','.join('?' * len(sources))})"
    chosen = tuple(sources or ())
    if all(len(w) >= 3 for w in words):
        rows = db.execute(
            f"SELECT {columns} FROM {table} WHERE {table} MATCH ?{within} ORDER BY rank LIMIT ?",
            (_match(words), *chosen, limit),
        ).fetchall()
        return rows, "index"
    # A word shorter than a trigram cannot use the index: scan the rows.
    where = " AND ".join("text LIKE ? ESCAPE '\\'" for _ in words)
    rows = db.execute(
        f"SELECT {columns} FROM {table} WHERE {where}{within} LIMIT ?",
        (*[_like(w) for w in words], *chosen, limit),
    ).fetchall()
    return rows, "scan"


def snippet(text: str, words: list[str], width: int = SNIPPET_CHARS) -> dict[str, Any]:
    """A window of `text` around the first word found, with every found word
    marked as [start, end) offsets into the snippet (case ignored)."""
    lowered = text.lower()
    found = [(lowered.find(w.lower()), w) for w in words]
    hits = [p for p, _ in found if p >= 0]
    first = min(hits) if hits else 0
    start = max(0, min(first - width // 4, len(text) - width))
    end = min(len(text), start + width)
    piece = text[start:end]
    low_piece = piece.lower()
    marks: list[list[int]] = []
    for word in words:
        needle = word.lower()
        at = low_piece.find(needle)
        while at >= 0 and needle:
            marks.append([at, at + len(needle)])
            at = low_piece.find(needle, at + len(needle))
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    shift = len(prefix)
    return {
        "snippet": prefix + piece + suffix,
        "marks": sorted([a + shift, b + shift] for a, b in marks),
    }


def _limit(value: Any) -> int:
    try:
        number = int(str(value)) if value not in (None, "") else DEFAULT_LIMIT
    except ValueError:
        number = DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, number))


def _passages(
    db: sqlite3.Connection, words: list[str], limit: int, sources: Sequence[str] | None = None
) -> list[dict[str, Any]]:
    rows, _ = _rows(
        db, "chunk_text", "text, source_id, rev, line_start, line_end", words, limit, sources
    )
    names = {str(r["source_id"]): r["name"] for r in db.execute("SELECT * FROM sources")}
    found = []
    for row in rows:
        text = str(row["text"])
        lines = text.split("\n")
        first_line = next(
            (i for i, line in enumerate(lines) if any(w.lower() in line.lower() for w in words)),
            0,
        )
        found.append(
            {
                "source_id": row["source_id"],
                "source_name": names.get(str(row["source_id"]), ""),
                "rev": int(row["rev"]),
                "line_start": int(row["line_start"]),
                "line_end": int(row["line_end"]),
                "line": int(row["line_start"]) + first_line,
                **snippet(text, words),
            }
        )
    return found


def passages(
    store: BiStore, query: Any, *, approved: Collection[str], limit: int = PASSAGE_LIMIT
) -> dict[str, Any]:
    """Passages for the model: only from sources of a data class approved for it.
    `withheld` counts the matching chunks left out for that (at most `limit`), so
    the answer can say so. No marks: they point into the snippet for a page."""
    empty: dict[str, Any] = {"passages": [], "withheld": 0}
    words = terms(str(query or ""))
    if not words or not _has_data(store) or (store.read_only and store.view is None):
        return empty
    sync_quietly(store)
    classes = {
        str(s["id"]): str(s["classification"])
        for s in Staging(store.workspace, store.dataset).sources()
    }
    allowed = [k for k, v in classes.items() if v in approved]
    refused = [k for k, v in classes.items() if v not in approved]
    with _db(store) as db:
        found = _passages(db, words, limit, allowed) if allowed else []
        withheld = len(_rows(db, "chunk_text", "source_id", words, limit, refused)[0])
    return {
        "passages": [{k: v for k, v in item.items() if k != "marks"} for item in found],
        "withheld": withheld if refused else 0,
    }


def search(store: BiStore, query: Any, *, limit: Any = None) -> dict[str, Any]:
    """Cards and Markdown passages matching every word of `query`."""
    words = terms(str(query or ""))
    count = _limit(limit)
    sync_quietly(store)  # a dataset from before V3 gets its index here
    if not words or not _has_data(store):
        mode = "none" if not words else "index"
        return {"query": " ".join(words), "terms": words, "mode": mode, "cards": [], "passages": []}
    with _db(store) as db:
        card_rows, mode = _rows(db, "card_text", "card_id", words, count)
        cards = []
        for row in card_rows:
            card = db.execute("SELECT * FROM cards WHERE card_id = ?", (row["card_id"],)).fetchone()
            if card is None:
                continue
            fields = json.loads(card["fields"])
            hits = []
            for name, text in [("name", card["name"]), *fields.items()]:
                if any(w.lower() in str(text).lower() for w in words):
                    hits.append({"field": name, **snippet(str(text), words)})
            cards.append(
                {
                    "id": card["card_id"],
                    "entity_type": card["entity_type"],
                    "name": card["name"],
                    "canonical_key": card["canonical_key"],
                    "version": int(card["version"]),
                    "hits": hits,
                }
            )
        passages = _passages(db, words, count)
    return {
        "query": " ".join(words),
        "terms": words,
        "mode": mode,
        "cards": cards,
        "passages": passages,
    }
