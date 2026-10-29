"""BI dataset snapshots: `aep-bi-dataset-snapshot/1` (BI dataset sharing slice 1).

`docs/proposals/BI_DATASET_SHARING.md` §4 and §6, owner answers of 2026-10-22
(§8.5), contract `docs/CONTRACTS.md` "BI dataset sharing".

A snapshot is a gzip stream of one canonical JSON object: the dataset's
schema (id@version and the schema JSON itself), its cards with field
provenance and history, the import records history refers to, statistics and
a content digest. Building is deterministic, so the same dataset always gives
the same bytes and digest.

What is left out or reduced (owner Q3): pending proposals are never read;
folders in refs and import file names are dropped, only the file name stays;
actor names are mapped to platform accounts through an optional mapping and
kept as they are when the mapping has no entry. Any string that looks like a
credential fails the build, naming the card and field and never the value.

Reading validates everything and checks the digest before anything uses the
content; installing builds the read-only copy in a temporary folder and
renames it into place, so a failure leaves nothing behind.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import uuid
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from capabilities.bi_cards import catalog, schema_versions
from capabilities.bi_cards.schema import BI_PREFIX, shipped
from capabilities.bi_cards.store import DB_FILE, SCHEMA, BiStore
from common.assets import SECRET_FIELD, SECRET_PATTERN

SNAPSHOT_FORMAT = "aep-bi-dataset-snapshot/1"
CLASSIFICATION = "INTERNAL"
#: The largest snapshot (gzip) built or read by default; the platform's own
#: limit is configured separately (`max_bi_dataset_bytes`).
MAX_SNAPSHOT_BYTES = 20 * 1024 * 1024
#: The largest decompressed JSON; guards against a compression bomb.
MAX_SNAPSHOT_JSON_BYTES = 256 * 1024 * 1024
MAX_CARDS = 50_000
SNAPSHOT_FILE = "snapshot.json"

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
DATASET_NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
ACTOR_REF = "agent-web:"
MAX_TEXT = 10_000

SchemaState = Literal["shipped", "present", "missing", "conflict", "unavailable"]

_TOP_KEYS = {
    "format",
    "classification",
    "dataset",
    "schema",
    "cards",
    "imports",
    "meta",
    "digest",
    "publication",
}
_SCHEMA_KEYS = {"ref", "id", "version", "source", "sha256", "document"}
_CARD_KEYS = {
    "id",
    "entity_type",
    "canonical_key",
    "name",
    "version",
    "synthetic",
    "created",
    "updated",
    "created_by_import",
    "fields",
    "history",
}
_FIELD_KEYS = {"value", "kind", "ref", "by", "at"}
_HISTORY_KEYS = {
    "seq",
    "field",
    "old",
    "new",
    "kind",
    "ref",
    "by",
    "at",
    "import_id",
    "reason",
    "old_source",
}
_SOURCE_KEYS = {"kind", "ref", "by", "at"}
_IMPORT_KEYS = {"id", "filename", "entity_type", "at", "by", "undone"}
_META_KEYS = {"source_last_updated", "stats"}
_STATS_KEYS = {"cards", "cards_by_type", "fields", "history", "imports"}
_PUBLICATION_KEYS = {
    "namespace",
    "name",
    "version",
    "base_version",
    "published_by",
    "published_at",
    "note",
}


class SnapshotError(Exception):
    """Why a snapshot could not be built, read or installed. The message
    never carries a field value; `card` and `field` say where."""

    def __init__(
        self,
        code: str,
        message: str = "",
        *,
        card: str | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.card = card
        self.field = field


@dataclass(frozen=True)
class Publication:
    """What the platform stamps on a published snapshot."""

    namespace: str
    name: str
    version: str
    base_version: str | None
    published_by: str
    published_at: str
    note: str

    @property
    def reference(self) -> str:
        return f"{self.namespace}/{self.name}@{self.version}"

    def as_json(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "name": self.name,
            "version": self.version,
            "base_version": self.base_version,
            "published_by": self.published_by,
            "published_at": self.published_at,
            "note": self.note,
        }


@dataclass(frozen=True)
class Snapshot:
    """A validated snapshot whose digest matched."""

    document: dict[str, Any]
    digest: str
    dataset: str
    schema_ref: str
    schema_id: str
    schema_version: str
    schema_source: str
    schema_sha256: str
    schema_document: dict[str, Any]
    publication: Publication | None
    stats: dict[str, Any]
    cards: int


@dataclass(frozen=True)
class InstalledSnapshot:
    """What `install_snapshot` wrote."""

    path: Path
    dataset: str
    version: str | None
    schema_ref: str
    digest: str
    publication: Publication | None


# -- canonical bytes ---------------------------------------------------------


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def content_digest(document: Mapping[str, Any]) -> str:
    """The digest of everything but `digest` and `publication`."""
    body = {k: v for k, v in document.items() if k not in ("digest", "publication")}
    return hashlib.sha256(canonical_json(body)).hexdigest()


def schema_sha256(document: Any) -> str:
    return hashlib.sha256(catalog.canonical(document).encode("utf-8")).hexdigest()


def _gzip(document: Mapping[str, Any]) -> bytes:
    return gzip.compress(canonical_json(document), compresslevel=9, mtime=0)


# -- reducing what leaves the owner's PC -------------------------------------


def _file_name(text: str) -> str:
    return re.split(r"[\\/]", text)[-1]


def _reduce_ref(ref: str, accounts: Mapping[str, str]) -> str:
    """Only the file name of a file ref; the mapped actor of an edit's ref."""
    if ref.startswith(ACTOR_REF):
        actor = ref[len(ACTOR_REF) :]
        return ACTOR_REF + accounts.get(actor, actor)
    if "#" in ref:
        head, tail = ref.rsplit("#", 1)
        return f"{_file_name(head)}#{tail}"
    if "/" in ref or "\\" in ref:
        return _file_name(ref)
    return ref


def _account(actor: str, accounts: Mapping[str, str]) -> str:
    return accounts.get(actor, actor)


# -- secrets -----------------------------------------------------------------


def _secret_in(value: Any) -> bool:
    if isinstance(value, str):
        return SECRET_PATTERN.search(value) is not None
    if isinstance(value, dict):
        return any(
            (isinstance(k, str) and SECRET_FIELD.fullmatch(k) is not None) or _secret_in(v)
            for k, v in value.items()
        )
    if isinstance(value, list):
        return any(_secret_in(item) for item in value)
    return False


def _secret_found(card: str | None, field: str | None) -> SnapshotError:
    where = f"卡片 {card}" if card else "資料集"
    if field:
        where += f" 的欄位 {field}"
    return SnapshotError(
        "secret_found",
        f"{where} 含有像密碼或 token 的內容，不能發佈；請先移除再發佈",
        card=card,
        field=field,
    )


def scan_secrets(document: Mapping[str, Any]) -> None:
    """Fail on the first credential-like string, naming card and field."""
    for card in document.get("cards", ()):
        label = f"{card.get('entity_type')}:{card.get('canonical_key')}"
        for key in ("entity_type", "canonical_key", "name"):
            if _secret_in(card.get(key)):
                raise _secret_found(label, key)
        for name, field in card.get("fields", {}).items():
            if SECRET_FIELD.fullmatch(name) or _secret_in(field):
                raise _secret_found(label, name)
        for entry in card.get("history", ()):
            if SECRET_FIELD.fullmatch(str(entry.get("field"))) or _secret_in(entry):
                raise _secret_found(label, str(entry.get("field")))
    for entry in document.get("imports", ()):
        if _secret_in(entry):
            raise _secret_found(None, f"import {entry.get('id')}")
    if _secret_in(document.get("schema")):
        raise _secret_found(None, "schema")
    for key in ("dataset", "meta", "publication"):
        if _secret_in(document.get(key)):
            raise _secret_found(None, key)


# -- building ----------------------------------------------------------------


def _schema_block(store: BiStore) -> dict[str, Any]:
    ref = store.schema_ref()
    reg = catalog.resolve(store.workspace, ref)
    if reg.source == "shipped":
        document = json.loads(json.dumps(reg.document))
    else:
        path = catalog.schema_path(store.workspace, reg.schema_id, reg.version)
        document = json.loads(path.read_text(encoding="utf-8"))
    return {
        "ref": f"{reg.schema_id}@{reg.version}",
        "id": reg.schema_id,
        "version": reg.version,
        "source": reg.source,
        "sha256": schema_sha256(document),
        "document": document,
    }


def _loads(text: str | None) -> Any:
    return None if text is None else json.loads(text)


def build_snapshot(
    store: BiStore,
    *,
    accounts: Mapping[str, str] | None = None,
    max_bytes: int = MAX_SNAPSHOT_BYTES,
) -> bytes:
    """The gzip snapshot of one local dataset. Deterministic for the same
    dataset and mapping; raises `SnapshotError` (`dataset_missing`,
    `schema_missing`, `secret_found`, `artifact_too_large`)."""
    names = dict(accounts or {})
    if not store.exists:
        raise SnapshotError("dataset_missing", f"資料集「{store.dataset}」沒有資料，不能發佈")
    try:
        schema_block = _schema_block(store)
    except Exception:  # noqa: BLE001 - a missing or broken schema file is one answer
        raise SnapshotError(
            "schema_missing", f"資料集「{store.dataset}」使用的 schema 不在這台電腦上"
        ) from None
    connection = sqlite3.connect(f"file:{store.path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        card_rows = list(
            connection.execute("SELECT * FROM cards ORDER BY entity_type, canonical_key")
        )
        if len(card_rows) > MAX_CARDS:
            raise SnapshotError("artifact_too_large", f"卡片超過 {MAX_CARDS} 張，不能發佈")
        # A value the schema no longer has (a field removed by an upgrade)
        # stays on this PC and is not shared (BI ingest §5.3).
        reg = catalog.for_store(store)
        card_types = {row["id"]: row["entity_type"] for row in card_rows}
        fields: dict[str, dict[str, Any]] = {}
        for row in connection.execute("SELECT * FROM fields ORDER BY card_id, field"):
            entity = reg.types.get(card_types.get(row["card_id"], ""))
            if entity is not None and entity.get(row["field"]) is None:
                continue
            fields.setdefault(row["card_id"], {})[row["field"]] = {
                "value": _loads(row["value"]),
                "kind": row["kind"],
                "ref": _reduce_ref(row["ref"], names),
                "by": _account(row["by"], names),
                "at": row["at"],
            }
        history: dict[str, list[dict[str, Any]]] = {}
        for row in connection.execute("SELECT * FROM history ORDER BY seq"):
            source = _loads(row["old_source"])
            if isinstance(source, dict):
                source = {
                    "kind": str(source.get("kind", "")),
                    "ref": _reduce_ref(str(source.get("ref", "")), names),
                    "by": _account(str(source.get("by", "")), names),
                    "at": str(source.get("at", "")),
                }
            else:
                source = None
            history.setdefault(row["card_id"], []).append(
                {
                    "seq": int(row["seq"]),
                    "field": row["field"],
                    "old": _loads(row["old"]),
                    "new": _loads(row["new"]),
                    "kind": row["kind"],
                    "ref": _reduce_ref(row["ref"], names),
                    "by": _account(row["by"], names),
                    "at": row["at"],
                    "import_id": row["import_id"],
                    "reason": row["reason"],
                    "old_source": source,
                }
            )
        imports = [
            {
                "id": row["id"],
                "filename": _file_name(row["filename"]),
                "entity_type": row["entity_type"],
                "at": row["at"],
                "by": _account(row["by"], names),
                "undone": bool(row["undone"]),
            }
            for row in connection.execute("SELECT * FROM imports ORDER BY at, id")
        ]
    finally:
        connection.close()
    cards = []
    by_type: dict[str, int] = {}
    for row in card_rows:
        by_type[row["entity_type"]] = by_type.get(row["entity_type"], 0) + 1
        cards.append(
            {
                "id": row["id"],
                "entity_type": row["entity_type"],
                "canonical_key": row["canonical_key"],
                "name": row["name"],
                "version": int(row["version"]),
                "synthetic": bool(row["synthetic"]),
                "created": row["created"],
                "updated": row["updated"],
                "created_by_import": row["created_by_import"],
                "fields": fields.get(row["id"], {}),
                "history": history.get(row["id"], []),
            }
        )
    document: dict[str, Any] = {
        "format": SNAPSHOT_FORMAT,
        "classification": CLASSIFICATION,
        "dataset": store.dataset,
        "schema": schema_block,
        "cards": cards,
        "imports": imports,
        "meta": {
            "source_last_updated": max((c["updated"] for c in cards), default=None),
            "stats": {
                "cards": len(cards),
                "cards_by_type": dict(sorted(by_type.items())),
                "fields": sum(len(c["fields"]) for c in cards),
                "history": sum(len(c["history"]) for c in cards),
                "imports": len(imports),
            },
        },
        "publication": None,
    }
    scan_secrets(document)
    document["digest"] = content_digest(document)
    data = _gzip(document)
    if len(data) > max_bytes:
        raise SnapshotError(
            "artifact_too_large",
            f"快照壓縮後 {len(data)} bytes，超過上限 {max_bytes} bytes",
        )
    return data


# -- reading -----------------------------------------------------------------


def _invalid(where: str) -> SnapshotError:
    return SnapshotError("snapshot_invalid", f"快照格式不正確（{where}）")


def _exact(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _invalid(where)
    return value


def _str(value: Any, where: str, *, empty: bool = False, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or len(value) > limit or (not empty and not value):
        raise _invalid(where)
    return value


def _opt_str(value: Any, where: str) -> str | None:
    return None if value is None else _str(value, where, empty=True)


def _int(value: Any, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _invalid(where)
    return value


def _bool(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise _invalid(where)
    return value


def _json_value(value: Any, where: str, depth: int = 0) -> None:
    if depth > 20:
        raise _invalid(where)
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, (int, float)):
        return
    if isinstance(value, list):
        for item in value:
            _json_value(item, where, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _str(key, where, empty=True)
            _json_value(item, where, depth + 1)
        return
    raise _invalid(where)


def _source(value: Any, where: str) -> None:
    item = _exact(value, _SOURCE_KEYS, where)
    for key in ("kind", "ref", "by", "at"):
        _str(item[key], f"{where}.{key}", empty=True)


def _iso(value: Any, where: str) -> str:
    text = _str(value, where)
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise _invalid(where) from None
    if moment.tzinfo is None:
        raise _invalid(where)
    return text


def _publication(value: Any) -> Publication | None:
    if value is None:
        return None
    item = _exact(value, _PUBLICATION_KEYS, "publication")
    namespace = _str(item["namespace"], "publication.namespace")
    name = _str(item["name"], "publication.name")
    version = _str(item["version"], "publication.version")
    base = item["base_version"]
    if not SLUG.match(namespace) or not SLUG.match(name) or not SEMVER.match(version):
        raise _invalid("publication")
    if base is not None and not (isinstance(base, str) and SEMVER.match(base)):
        raise _invalid("publication.base_version")
    return Publication(
        namespace=namespace,
        name=name,
        version=version,
        base_version=base,
        published_by=_str(item["published_by"], "publication.published_by"),
        published_at=_iso(item["published_at"], "publication.published_at"),
        note=_str(item["note"], "publication.note"),
    )


def _schema(value: Any) -> dict[str, Any]:
    block = _exact(value, _SCHEMA_KEYS, "schema")
    schema_id = _str(block["id"], "schema.id")
    version = _str(block["version"], "schema.version")
    if block["ref"] != f"{schema_id}@{version}" or not SEMVER.match(version):
        raise _invalid("schema.ref")
    if block["source"] not in ("shipped", "installed"):
        raise _invalid("schema.source")
    if not isinstance(block["sha256"], str) or not SHA256.match(block["sha256"]):
        raise _invalid("schema.sha256")
    document = block["document"]
    if not isinstance(document, dict):
        raise _invalid("schema.document")
    if document.get("schema_id") != schema_id or str(document.get("version") or "") != version:
        raise _invalid("schema.document")
    if schema_sha256(document) != block["sha256"]:
        raise SnapshotError("digest_mismatch", "快照內的 schema 與它的 digest 不符")
    if block["source"] == "installed":
        # A local `bi.schema/*` version is valid only as a compatible superset
        # of the shipped one (`catalog.bi_problems`, BI ingest §5.2).
        normalised, problems = catalog.validate(document)
        if problems or normalised is None:
            raise _invalid("schema.document")
    elif not schema_id.startswith(BI_PREFIX):
        raise _invalid("schema.source")
    return block


def _decompress(data: bytes, max_bytes: int) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise _invalid("gzip")
    if len(data) > max_bytes:
        raise SnapshotError(
            "artifact_too_large", f"快照 {len(data)} bytes，超過上限 {max_bytes} bytes"
        )
    inflater = zlib.decompressobj(wbits=31)
    try:
        raw = inflater.decompress(bytes(data), MAX_SNAPSHOT_JSON_BYTES + 1)
    except zlib.error:
        raise _invalid("gzip") from None
    if len(raw) > MAX_SNAPSHOT_JSON_BYTES:
        raise SnapshotError("artifact_too_large", "快照解壓後太大")
    if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise _invalid("gzip")
    return raw


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _refuse_constant(name: str) -> Any:
    raise ValueError(name)


def read_snapshot(data: bytes, *, max_bytes: int = MAX_SNAPSHOT_BYTES) -> Snapshot:
    """A snapshot validated strictly, with its digest checked. Raises
    `SnapshotError`: `artifact_too_large`, `snapshot_invalid`,
    `digest_mismatch`, `secret_found`."""
    raw = _decompress(data, max_bytes)
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicates,
            parse_constant=_refuse_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise _invalid("json") from None
    top = _exact(document, _TOP_KEYS, "top level")
    if top["format"] != SNAPSHOT_FORMAT:
        raise _invalid("format")
    if top["classification"] != CLASSIFICATION:
        raise _invalid("classification")
    dataset = _str(top["dataset"], "dataset")
    if not DATASET_NAME.match(dataset):
        raise _invalid("dataset")
    schema = _schema(top["schema"])
    cards = top["cards"]
    if not isinstance(cards, list) or len(cards) > MAX_CARDS:
        raise _invalid("cards")
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    seqs: set[int] = set()
    by_type: dict[str, int] = {}
    field_total = history_total = 0
    for index, value in enumerate(cards):
        where = f"cards[{index}]"
        card = _exact(value, _CARD_KEYS, where)
        card_id = _str(card["id"], f"{where}.id", limit=100)
        entity_type = _str(card["entity_type"], f"{where}.entity_type", limit=100)
        key = (entity_type, _str(card["canonical_key"], f"{where}.canonical_key"))
        if card_id in seen_ids or key in seen_keys:
            raise _invalid(f"{where} duplicate")
        seen_ids.add(card_id)
        seen_keys.add(key)
        by_type[entity_type] = by_type.get(entity_type, 0) + 1
        _str(card["name"], f"{where}.name", empty=True)
        if _int(card["version"], f"{where}.version") < 1:
            raise _invalid(f"{where}.version")
        _bool(card["synthetic"], f"{where}.synthetic")
        _str(card["created"], f"{where}.created")
        _str(card["updated"], f"{where}.updated")
        _opt_str(card["created_by_import"], f"{where}.created_by_import")
        fields = card["fields"]
        if not isinstance(fields, dict):
            raise _invalid(f"{where}.fields")
        for name, field in fields.items():
            _str(name, f"{where}.fields", limit=200)
            item = _exact(field, _FIELD_KEYS, f"{where}.fields.{name}")
            if item["value"] is None:
                raise _invalid(f"{where}.fields.{name}.value")
            _json_value(item["value"], f"{where}.fields.{name}.value")
            for part in ("kind", "ref", "by", "at"):
                _str(item[part], f"{where}.fields.{name}.{part}", empty=True)
        field_total += len(fields)
        history = card["history"]
        if not isinstance(history, list):
            raise _invalid(f"{where}.history")
        for position, entry in enumerate(history):
            spot = f"{where}.history[{position}]"
            item = _exact(entry, _HISTORY_KEYS, spot)
            seq = _int(item["seq"], f"{spot}.seq")
            if seq in seqs:
                raise _invalid(f"{spot}.seq")
            seqs.add(seq)
            _str(item["field"], f"{spot}.field", limit=200)
            _json_value(item["old"], f"{spot}.old")
            _json_value(item["new"], f"{spot}.new")
            for part in ("kind", "ref", "by", "at"):
                _str(item[part], f"{spot}.{part}", empty=True)
            _opt_str(item["import_id"], f"{spot}.import_id")
            _opt_str(item["reason"], f"{spot}.reason")
            if item["old_source"] is not None:
                _source(item["old_source"], f"{spot}.old_source")
        history_total += len(history)
    imports = top["imports"]
    if not isinstance(imports, list):
        raise _invalid("imports")
    import_ids: set[str] = set()
    for index, value in enumerate(imports):
        where = f"imports[{index}]"
        item = _exact(value, _IMPORT_KEYS, where)
        import_id = _str(item["id"], f"{where}.id", limit=100)
        if import_id in import_ids:
            raise _invalid(f"{where}.id")
        import_ids.add(import_id)
        filename = _str(item["filename"], f"{where}.filename", empty=True)
        if "/" in filename or "\\" in filename:
            raise _invalid(f"{where}.filename")
        for part in ("entity_type", "at", "by"):
            _str(item[part], f"{where}.{part}", empty=True)
        _bool(item["undone"], f"{where}.undone")
    meta = _exact(top["meta"], _META_KEYS, "meta")
    _opt_str(meta["source_last_updated"], "meta.source_last_updated")
    stats = _exact(meta["stats"], _STATS_KEYS, "meta.stats")
    expected = {
        "cards": len(cards),
        "cards_by_type": dict(sorted(by_type.items())),
        "fields": field_total,
        "history": history_total,
        "imports": len(imports),
    }
    if stats != expected:
        raise _invalid("meta.stats")
    digest = top["digest"]
    if not isinstance(digest, str) or not SHA256.match(digest):
        raise _invalid("digest")
    if content_digest(top) != digest:
        raise SnapshotError("digest_mismatch", "快照內容與它的 digest 不符")
    publication = _publication(top["publication"])
    scan_secrets(top)
    return Snapshot(
        document=top,
        digest=digest,
        dataset=dataset,
        schema_ref=schema["ref"],
        schema_id=schema["id"],
        schema_version=schema["version"],
        schema_source=schema["source"],
        schema_sha256=schema["sha256"],
        schema_document=schema["document"],
        publication=publication,
        stats=stats,
        cards=len(cards),
    )


def stamp_publication(snapshot: Snapshot, publication: Publication) -> bytes:
    """The platform's stored bytes: the same content with `publication`
    set. The content digest does not change."""
    document = dict(snapshot.document)
    document["publication"] = publication.as_json()
    _publication(document["publication"])
    return _gzip(document)


# -- the schema on the subscriber's PC ---------------------------------------


def schema_state(snapshot: Snapshot, workspace: Path) -> SchemaState:
    """Whether the snapshot's schema can be used on this PC as it is. A
    shipped schema is matched by id@version (an AEP release that ships it
    is enough); an installed one by its canonical content."""
    if snapshot.schema_source == "shipped":
        wanted = (snapshot.schema_id, snapshot.schema_version)
        if any((reg.schema_id, reg.version) == wanted for reg in shipped()):
            return "shipped"
        return "unavailable"
    path = catalog.schema_path(workspace, snapshot.schema_id, snapshot.schema_version)
    if not path.is_file():
        return "missing"
    try:
        present = path.read_text(encoding="utf-8")
    except OSError:
        return "conflict"
    if present == catalog.canonical(snapshot.schema_document):
        return "present"
    return "conflict"


def install_schema(snapshot: Snapshot, workspace: Path) -> SchemaState:
    """Make the snapshot's schema available; installs it when missing.
    Raises `schema_conflict` or `schema_unavailable` and writes nothing then."""
    state = schema_state(snapshot, workspace)
    if state == "conflict":
        raise SnapshotError(
            "schema_conflict",
            f"這台電腦已有 {snapshot.schema_ref}，但內容不同；請發佈者換一個 schema 版本號",
        )
    if state == "unavailable":
        raise SnapshotError(
            "schema_unavailable",
            f"這個 AEP 版本沒有內建 {snapshot.schema_ref}；請先更新 AEP",
        )
    if state == "missing":
        try:
            catalog.install(
                workspace,
                f"{snapshot.schema_ref}.json",
                catalog.canonical(snapshot.schema_document),
            )
        except catalog.SchemaInstallError as error:
            if error.code == "schema_version_exists":
                raise SnapshotError(
                    "schema_conflict",
                    f"這台電腦已有 {snapshot.schema_ref}，但內容不同；請發佈者換一個 schema 版本號",
                ) from None
            raise SnapshotError("snapshot_invalid", "快照內的 schema 無法安裝") from None
    return state


# -- installing the read-only copy -------------------------------------------


def _dumps(value: Any) -> str:
    # The store's own encoding of a stored value.
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _write_store(path: Path, snapshot: Snapshot) -> None:
    document = snapshot.document
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        meta = {
            "schema": snapshot.schema_ref,
            "snapshot_format": SNAPSHOT_FORMAT,
            "snapshot_digest": snapshot.digest,
            "read_only": "1",
        }
        if snapshot.publication is not None:
            meta["published_version"] = snapshot.publication.version
        connection.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", sorted(meta.items()))
        for card in document["cards"]:
            connection.execute(
                "INSERT INTO cards (id, entity_type, canonical_key, name, version, synthetic, "
                "created, updated, created_by_import) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card["id"],
                    card["entity_type"],
                    card["canonical_key"],
                    card["name"],
                    card["version"],
                    int(card["synthetic"]),
                    card["created"],
                    card["updated"],
                    card["created_by_import"],
                ),
            )
            connection.executemany(
                "INSERT INTO fields (card_id, field, value, kind, ref, by, at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        card["id"],
                        name,
                        _dumps(field["value"]),
                        field["kind"],
                        field["ref"],
                        field["by"],
                        field["at"],
                    )
                    for name, field in sorted(card["fields"].items())
                ],
            )
            connection.executemany(
                "INSERT INTO history (seq, card_id, field, old, new, kind, ref, by, at, "
                "import_id, reason, old_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        entry["seq"],
                        card["id"],
                        entry["field"],
                        None if entry["old"] is None else _dumps(entry["old"]),
                        None if entry["new"] is None else _dumps(entry["new"]),
                        entry["kind"],
                        entry["ref"],
                        entry["by"],
                        entry["at"],
                        entry["import_id"],
                        entry["reason"],
                        None if entry["old_source"] is None else _dumps(entry["old_source"]),
                    )
                    for entry in card["history"]
                ],
            )
        connection.executemany(
            "INSERT INTO imports (id, filename, entity_type, at, by, undone) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    item["id"],
                    item["filename"],
                    item["entity_type"],
                    item["at"],
                    item["by"],
                    int(item["undone"]),
                )
                for item in document["imports"]
            ],
        )
        connection.commit()
    finally:
        connection.close()


def _summary(snapshot: Snapshot) -> dict[str, Any]:
    document = snapshot.document
    return {
        "format": SNAPSHOT_FORMAT,
        "classification": CLASSIFICATION,
        "dataset": snapshot.dataset,
        "schema": {
            "ref": snapshot.schema_ref,
            "source": snapshot.schema_source,
            "sha256": snapshot.schema_sha256,
        },
        "meta": document["meta"],
        "digest": snapshot.digest,
        "publication": None if snapshot.publication is None else snapshot.publication.as_json(),
    }


def install_snapshot(snapshot: Snapshot, dest_dir: Path) -> InstalledSnapshot:
    """Write the read-only dataset store for `snapshot` at `dest_dir`
    (`bi.sqlite` and `snapshot.json`). `dest_dir` must not exist or be an
    empty folder. Validates everything first and builds in a temporary
    sibling folder, so nothing is left at `dest_dir` on failure."""
    if not isinstance(snapshot, Snapshot):
        raise SnapshotError("snapshot_invalid", "不是已驗證的快照")
    # Validate again from the document itself: a Snapshot is a plain
    # dataclass and the bytes it came from are not kept.
    checked = read_snapshot(_gzip(snapshot.document), max_bytes=MAX_SNAPSHOT_JSON_BYTES)
    if checked.digest != snapshot.digest:
        raise SnapshotError("digest_mismatch", "快照內容與它的 digest 不符")
    target = Path(dest_dir)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise SnapshotError("install_target_exists", f"{target} 已經存在")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{target.name}.installing-{uuid.uuid4().hex[:8]}"
    staging.mkdir()
    try:
        _write_store(staging / DB_FILE, checked)
        (staging / SNAPSHOT_FILE).write_text(
            json.dumps(_summary(checked), ensure_ascii=False, sort_keys=True, indent=1) + "\n",
            encoding="utf-8",
        )
        if target.exists():
            target.rmdir()
        # Waits out a virus scanner or the indexer briefly holding the new folder
        # (seen once in the full suite on Windows).
        schema_versions.replace(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return InstalledSnapshot(
        path=target,
        dataset=checked.dataset,
        version=None if checked.publication is None else checked.publication.version,
        schema_ref=checked.schema_ref,
        digest=checked.digest,
        publication=checked.publication,
    )
