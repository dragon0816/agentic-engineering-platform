"""BI vaults on the common knowledge repository engine (knowledge repositories R2).

Design: `docs/phases/KNOWLEDGE_REPO.md` (the BI type, §3, §5, §8); contract:
`docs/CONTRACTS.md` "Knowledge repositories: the BI type (R2)". The version
mechanism itself (commits, push, revert, tags, publish) is
`knowledge.repo.repository`; this module maps BI cards onto its units and keeps
the local `bi.sqlite` a function of them.

A vault registered on this PC is the dataset `vault-<vault id>` (registry
`<workspace>/bi/vaults/registry.json`) and the repository `<vault id>` of type
`bi` (registry `<workspace>/knowledge-repos/registry.json`). Its units:

    schema                       the schema version (`<id>@<version>`)
    meta:<key>                   any other dataset meta (domain configuration …)
    card:<card id>               {"type", "key", "name", "synthetic"}
    field:<card id>:<field>      {"value", "source", "history"}; value null = cleared
    evidence:<card id>:<field>   [evidence rows]
    proposal:<key>               {"card", "field", "value", "kind", "ref", "at", "import_id",
                                  "status"}
    import:<import id>           {"filename", "entity_type", "at", "by", "run_id", "undone"}
    decision:<key>               {"status"}: a person's decision on a replay conflict

A card id is `card_id_for(type, key)` at its creation, the same on every PC, and
never changes: a rename keeps it (`docs/phases/BI_CARD_MODEL.md` §3.1). `bi.sqlite` holds
the working state (the head, this PC's local commits and its uncommitted
changes): every store write runs on it inside a transaction that is always
rolled back (`capture`), the units it changed are staged in the working copy,
and the database is rebuilt from the units. Field history is derived from the
commits, so it is the same on every PC. 「確認匯入」 (a new import) commits at
once with a drafted purpose; every other write waits for the person's commit.
A field change that lost a race on replay is shown as a pending proposal of
kind `conflict`.
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import re
import sqlite3
import tempfile
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from capabilities.bi_cards import (
    analyses,
    card_model,
    catalog,
    names,
    schema_doc,
    vault_checks,
    vault_skills,
    vault_sources,
)
from capabilities.bi_cards.schema import Registry, norm_key
from capabilities.bi_cards.store import (
    DATASET_RE,
    DB_FILE,
    SCHEMA,
    SUBSCRIBED_DIR,
    VAULT_PREFIX,
    VAULT_REGISTRY,
    VAULTS_DIR,
    BiStore,
    BiStoreError,
    add_missing_columns,
    card_id_for,
    is_subscribed,
    now,
    vault_registry,
)
from knowledge.repo import readme
from knowledge.repo import repository as repo_engine
from knowledge.repo import skills as repo_skills
from knowledge.repo.repository import CheckReport, RepoError, Repository

REPO_TYPE = "bi"
VAULT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_VAULT_ID = 40 - len(VAULT_PREFIX)
AUTHOR_RE = repo_engine.AUTHOR_RE
MAX_AUTHOR = repo_engine.MAX_AUTHOR
STATE_FILE = "vault_sync.json"
#: The local copy of the version the Agent reads (design §7), with `version.json`.
PUBLISHED_DIR = "published"

#: The 11 market segments of the owner's chart (BI_VAULT.md §4, §6.2):
#: folder name and label. A vault may name its own at creation.
SEGMENTS: tuple[tuple[str, str], ...] = (
    ("cell-phone", "Cell Phone"),
    ("ap-cpe", "AP/CPE"),
    ("module-iot", "Module/IoT"),
    ("aidc-computing", "AIDC Computing"),
    ("aidc-power", "AIDC Power"),
    ("car-ebus-electronics", "Car/eBus electronics"),
    ("robotics-amr", "Robotics/AMR"),
    ("space-satellite", "Space Satellite"),
    ("uav", "UAV"),
    ("radar-ew", "Radar/EW"),
    ("osat", "OSAT"),
)
LIBRARY = ("products", "competitors", "technologies")

#: The vault's own table in the local `bi.sqlite`: which unit each proposal
#: row stands for (`conflict:<commit id>:<unit>` for a replay conflict).
VAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_keys (
  proposal_id INTEGER PRIMARY KEY,
  key TEXT NOT NULL
);
"""
TABLES = (
    "cards",
    "fields",
    "history",
    "proposals",
    "meta",
    "imports",
    "evidence",
    "vault_keys",
    "relations",
    "relation_evidence",
    "field_states",
    "card_names",
    "card_app_folders",
)
UNIT_PREFIXES = (
    "meta:",
    "card:",
    "field:",
    "evidence:",
    "proposal:",
    "import:",
    "decision:",
    vault_sources.PREFIX,
    *card_model.UNIT_PREFIXES,
)

#: The purpose of the next commit made by a capture (「確認匯入」), when the
#: caller has one; otherwise it is drafted.
_PURPOSE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "bi_vault_purpose", default=None
)


@contextmanager
def purpose(text: str | None) -> Iterator[None]:
    """Give the commit a capture makes in this block its purpose."""
    token = _PURPOSE.set(text.strip() if text and text.strip() else None)
    try:
        yield
    finally:
        _PURPOSE.reset(token)


def _dump(value: Any) -> str:
    """A stored value's text, exactly as the store writes it."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(text: str | None) -> Any:
    return None if text is None else json.loads(text)


def _short(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def dataset_name(vault_id: str) -> str:
    return VAULT_PREFIX + vault_id


def local_dir(workspace: Path, vault_id: str) -> Path:
    return workspace / "bi" / VAULTS_DIR / vault_id


def _schema_file_name(schema_id: str, version: str) -> str:
    return f"{schema_id.replace('/', '__')}@{version}.json"


def _to_bi_error(failure: RepoError) -> BiStoreError:
    return BiStoreError(failure.code, failure.message, **failure.detail)


@contextmanager
def _repo_errors() -> Iterator[None]:
    try:
        yield
    except RepoError as failure:
        raise _to_bi_error(failure) from None


# -- the BI type -------------------------------------------------------------------


class _LinkTargets:
    """Which card a link's text means: a name or key first, then an alias or a
    former name. Only a single answer among the field's `link_to` types counts."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.kinds: dict[str, str] = {}
        self.names: dict[str, str] = {}
        self.named: dict[str, set[str]] = {}
        self.others: dict[str, set[str]] = {}
        for r in db.execute("SELECT id, entity_type, canonical_key, name FROM cards"):
            self.kinds[r["id"]] = r["entity_type"]
            self.names[r["id"]] = r["name"]
            for text in (r["name"], r["canonical_key"]):
                self.named.setdefault(norm_key(text), set()).add(r["id"])
        for r in db.execute("SELECT card_id, name FROM card_names"):
            self.others.setdefault(norm_key(r["name"]), set()).add(r["card_id"])

    def find(self, text: str, link_to: tuple[str, ...]) -> str | None:
        for table in (self.named, self.others):
            hits = {
                card
                for card in table.get(norm_key(text), ())
                if card in self.kinds and (not link_to or self.kinds[card] in link_to)
            }
            if hits:
                return next(iter(hits)) if len(hits) == 1 else None
        return None

    def stored(self, value: Any, link_to: tuple[str, ...]) -> Any:
        """A link value as its unit holds it: by id, or text when no single card answers."""
        if isinstance(value, list):
            return [self.stored(item, link_to) for item in value]
        if not isinstance(value, str):
            return value
        card = self.find(value, link_to)
        return value if card is None else card_model.link_item(card, self.names[card])


def _same_keys(units: Mapping[str, Any]) -> set[tuple[str, str]]:
    """The (type, key) held by more than one card."""
    seen: set[tuple[str, str]] = set()
    same: set[tuple[str, str]] = set()
    for key, value in units.items():
        if key.startswith("card:") and isinstance(value, dict):
            slot = (str(value.get("type")), str(value.get("key")))
            (same if slot in seen else seen).add(slot)
    return same


class BiType:
    """The `bi` repository type: card units and their checks."""

    name = REPO_TYPE
    #: The benchmark push check (`set_benchmark`, BI T1): (units before, units
    #: after) -> a report whose `blocking` lists the questions that regressed.
    benchmark: Callable[[Mapping[str, Any], Mapping[str, Any]], CheckReport] | None = None

    def unit_problem(self, key: str, value: Any) -> str | None:
        if key.startswith(vault_checks.PREFIX):
            return vault_checks.unit_problem(key, value)
        if key.startswith(analyses.PREFIX):
            return analyses.unit_problem(key, value)
        if key == repo_engine.SCHEMA_UNIT:
            return (
                None if isinstance(value, str) and "@" in value else "schema must be <id>@<version>"
            )
        if key.startswith(repo_engine.SKILL_UNIT_PREFIX):
            return None
        if not key.startswith(UNIT_PREFIXES):
            return "not a BI unit"
        if key.startswith(vault_sources.PREFIX):
            return vault_sources.unit_problem(value)
        if key.startswith(card_model.UNIT_PREFIXES):
            return card_model.unit_problem(key, value)
        if key.startswith("meta:"):
            return None if isinstance(value, str) else "meta value must be text"
        if key.startswith("evidence:"):
            return None if isinstance(value, list) else "evidence must be a list"
        if not isinstance(value, dict):
            return "value must be an object"
        if key.startswith("card:") and not all(
            isinstance(value.get(k), str) for k in ("type", "key", "name")
        ):
            return "card needs type, key and name"
        if key.startswith("field:") and "value" not in value:
            return "field needs value"
        return None

    def check(self, before: Mapping[str, Any], after: Mapping[str, Any]) -> CheckReport:
        cards = {k for k in after if k.startswith("card:")}
        added = len(cards - set(before))
        removed = len({k for k in before if k.startswith("card:")} - cards)
        changed = sum(
            1
            for k in after
            if k.startswith("field:")
            and repo_engine.canonical(before.get(k)) != repo_engine.canonical(after.get(k))
        )
        notes = [f"新增 {added} 張卡、刪除 {removed} 張卡、改了 {changed} 個欄位"]
        blocking = [
            f"兩張 {kind} 卡片都叫「{key}」，請先把其中一張改名"
            for kind, key in sorted(_same_keys(after) - _same_keys(before))
        ]
        if self.benchmark is None:
            return CheckReport(blocking=blocking, notes=notes)
        gate = self.benchmark(before, after)
        return CheckReport(blocking=[*blocking, *gate.blocking], notes=[*notes, *gate.notes])


BI_TYPE = BiType()
repo_engine.register_type(BI_TYPE)


def set_benchmark(
    benchmark: Callable[[Mapping[str, Any], Mapping[str, Any]], CheckReport] | None,
) -> None:
    """Set (or clear) the benchmark check run on every BI vault push."""
    BI_TYPE.benchmark = benchmark


# -- units <-> the BI tables ---------------------------------------------------------


def _tables(db: sqlite3.Connection) -> set[str]:
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _history_value(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": row["kind"],
        "ref": row["ref"],
        "by": row["by"],
        "at": row["at"],
        "import_id": row["import_id"],
        "reason": row["reason"],
    }


def units_from_db(db: sqlite3.Connection, *, keep_ids: bool = False) -> dict[str, Any]:
    """The units a BI database holds. A vault's database keeps its card ids
    (`keep_ids`); a dataset becoming a vault gets them from `card_id_for`."""
    db.row_factory = sqlite3.Row
    tables = _tables(db)
    units: dict[str, Any] = {}
    for r in db.execute("SELECT * FROM meta") if "meta" in tables else []:
        units[repo_engine.SCHEMA_UNIT if r["key"] == "schema" else f"meta:{r['key']}"] = r["value"]
    columns = {r[1] for r in db.execute("PRAGMA table_info(imports)")}
    for r in db.execute("SELECT * FROM imports"):
        units[f"import:{r['id']}"] = {
            "filename": r["filename"],
            "entity_type": r["entity_type"],
            "at": r["at"],
            "by": r["by"],
            "run_id": r["run_id"] if "run_id" in columns else None,
            "undone": bool(r["undone"]),
        }
    ids: dict[str, str] = {}
    former: dict[str, list[str]] = {}
    if "card_names" in tables:
        for r in db.execute("SELECT * FROM card_names WHERE kind = 'former' ORDER BY name"):
            former.setdefault(r["card_id"], []).append(r["name"])
    for r in db.execute("SELECT * FROM cards"):
        # The key as its unit holds it: a lost key shows with a suffix (`_card_keys`).
        card_key = str(r["canonical_key"]).removesuffix(f"#{r['id']}")
        cid = r["id"] if keep_ids else card_id_for(r["entity_type"], card_key)
        ids[r["id"]] = cid
        units[f"card:{cid}"] = {
            "type": r["entity_type"],
            "key": card_key,
            "name": r["name"],
            "synthetic": bool(r["synthetic"]),
            **({"former_keys": former[r["id"]]} if r["id"] in former else {}),
        }
    latest = {
        (r["card_id"], r["field"]): _history_value(r)
        for r in db.execute(
            "SELECT * FROM history WHERE seq IN "
            "(SELECT MAX(seq) FROM history GROUP BY card_id, field)"
        )
    }
    stored = set()
    for r in db.execute("SELECT * FROM fields"):
        if r["card_id"] not in ids:
            continue
        stored.add((r["card_id"], r["field"]))
        units[f"field:{ids[r['card_id']]}:{r['field']}"] = {
            "value": _load(r["value"]),
            "source": {"kind": r["kind"], "ref": r["ref"], "by": r["by"], "at": r["at"]},
            "history": latest.get((r["card_id"], r["field"])),
        }
    for (card_id, name), history in latest.items():
        if card_id in ids and (card_id, name) not in stored:
            units[f"field:{ids[card_id]}:{name}"] = {
                "value": None,
                "source": None,
                "history": history,
            }
    if "evidence" in tables:
        for r in db.execute("SELECT * FROM evidence ORDER BY seq"):
            if r["card_id"] not in ids:
                continue
            units.setdefault(f"evidence:{ids[r['card_id']]}:{r['field']}", []).append(
                {
                    "run_id": r["run_id"],
                    "source_id": r["source_id"],
                    "source_name": r["source_name"],
                    "locator": _load(r["locator"]),
                    "excerpt": r["excerpt"],
                    "basis": r["basis"],
                    "at": r["at"],
                }
            )
    keys = {}
    if "vault_keys" in tables:
        keys = {
            int(r["proposal_id"]): str(r["key"]) for r in db.execute("SELECT * FROM vault_keys")
        }
    for r in db.execute("SELECT * FROM proposals ORDER BY id"):
        if r["card_id"] not in ids:
            continue
        key = keys.get(int(r["id"]))
        if key is not None and key.startswith("conflict:"):
            if r["status"] != "pending":
                units[f"decision:{_short(key)}"] = {"status": r["status"]}
            continue
        value = {
            "card": ids[r["card_id"]],
            "field": r["field"],
            "value": _load(r["value"]),
            "kind": r["kind"],
            "ref": r["ref"],
            "at": r["at"],
            "import_id": r["import_id"],
            "status": r["status"],
        }
        if key is None:
            identity = {k: value[k] for k in ("card", "field", "value", "kind", "ref", "at")}
            key = f"proposal:{_short(repo_engine.canonical(identity))}"
        units[key] = value
    return units


def _field_history(
    entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """History rows from the changes of the commits (and the working copy),
    and per card its first and last change: `created`, `updated`, `groups`."""
    rows: list[dict[str, Any]] = []
    cards: dict[str, dict[str, Any]] = {}
    for entry in entries:
        for change in entry["changes"]:
            unit = str(change["unit"])
            if not change["applied"]:
                continue
            if unit.startswith("card:") and change["after"] is not None:
                cid = unit[5:]
                info = cards.setdefault(
                    cid, {"created": entry["at"], "updated": entry["at"], "groups": set()}
                )
                info.setdefault("created", entry["at"])
            if not unit.startswith("field:"):
                continue
            _, cid, name = unit.split(":", 2)
            after, before = change["after"], change["before"]
            history = (after or {}).get("history") or {}
            old = None if before is None else before.get("value")
            new = None if after is None else after.get("value")
            if not history:
                continue  # a value without a history row (converted) keeps none
            info = cards.setdefault(
                cid, {"created": entry["at"], "updated": entry["at"], "groups": set()}
            )
            info["updated"] = history.get("at") or entry["at"]
            info["groups"].add(entry["group"])
            info.setdefault("first_import", history.get("import_id"))
            rows.append(
                {
                    "card_id": cid,
                    "field": name,
                    "old": old,
                    "new": new,
                    "kind": history.get("kind") or "edit",
                    "ref": history.get("ref") or entry["ref"],
                    "by": history.get("by") or entry["author"],
                    "at": history.get("at") or entry["at"],
                    "import_id": history.get("import_id"),
                    "reason": history.get("reason"),
                    "old_source": None if before is None else before.get("source"),
                }
            )
    return rows, cards


def _card_keys(units: Mapping[str, Any], info: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """Each card's key in `cards`. Two PCs can give two cards one key (rename X to
    Y while the other creates Y). The card created first keeps it, on every PC;
    the other shows as `<key>#<id>` until a person renames it."""
    keys: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    order = sorted(
        (str(info.get(k[5:], {}).get("created") or ""), k[5:], v)
        for k, v in units.items()
        if k.startswith("card:")
    )
    for _, cid, value in order:
        slot = (str(value["type"]), str(value["key"]))
        keys[cid] = slot[1] if slot not in seen else f"{slot[1]}#{cid}"
        seen.add(slot)
    return keys


def materialize(
    db: sqlite3.Connection,
    units: Mapping[str, Any],
    entries: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    """Rebuild every BI table of `db` from `units` inside one transaction."""
    db.executescript(SCHEMA)
    add_missing_columns(db)
    db.executescript(VAULT_SCHEMA)
    history, info = _field_history(entries)
    db.execute("BEGIN IMMEDIATE")
    try:
        for table in TABLES:
            db.execute(f"DELETE FROM {table}")  # noqa: S608
        db.execute("DELETE FROM sqlite_sequence WHERE name IN ('history', 'proposals', 'evidence')")
        for key, value in sorted(units.items()):
            if key == repo_engine.SCHEMA_UNIT:
                db.execute("INSERT INTO meta (key, value) VALUES ('schema', ?)", (value,))
            elif key.startswith("meta:"):
                db.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (key[5:], value))
            elif key.startswith("import:"):
                db.execute(
                    "INSERT INTO imports (id, filename, entity_type, at, by, undone, run_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        key[7:],
                        value["filename"],
                        value["entity_type"],
                        value["at"],
                        value["by"],
                        int(bool(value.get("undone"))),
                        value.get("run_id"),
                    ),
                )
        stamp = now()
        card_keys = _card_keys(units, info)
        shown = card_model.card_names_of(units)
        for key, value in sorted(units.items()):
            if not key.startswith("card:"):
                continue
            cid = key[5:]
            card = info.get(cid, {})
            for name in value.get("former_keys") or ():
                db.execute(
                    "INSERT OR IGNORE INTO card_names (card_id, name, kind) "
                    "VALUES (?, ?, 'former')",
                    (cid, name),
                )
            db.execute(
                "INSERT INTO cards (id, entity_type, canonical_key, name, version, synthetic, "
                "created, updated, created_by_import) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cid,
                    value["type"],
                    card_keys[cid],
                    value["name"],
                    1 + len(card.get("groups", ())),
                    int(bool(value.get("synthetic"))),
                    card.get("created", stamp),
                    card.get("updated", card.get("created", stamp)),
                    card.get("first_import"),
                ),
            )
        present = {k[5:] for k in units if k.startswith("card:")}
        for key, value in sorted(units.items()):
            if key.startswith("field:") and value.get("value") is not None:
                _, cid, name = key.split(":", 2)
                if cid not in present:
                    continue
                if name == names.FIELD:
                    held = value["value"] if isinstance(value["value"], list) else [value["value"]]
                    db.executemany(
                        "INSERT OR IGNORE INTO card_names (card_id, name, kind) "
                        "VALUES (?, ?, 'alias')",
                        [(cid, str(a)) for a in held if str(a).strip()],
                    )
                source = value.get("source") or {}
                db.execute(
                    "INSERT INTO fields (card_id, field, value, kind, ref, by, at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        cid,
                        name,
                        _dump(card_model.render_link(value["value"], shown)),
                        source.get("kind") or "edit",
                        source.get("ref") or "",
                        source.get("by") or "",
                        source.get("at") or stamp,
                    ),
                )
            elif key.startswith("evidence:"):
                _, cid, name = key.split(":", 2)
                if cid not in present:
                    continue
                for item in value:
                    db.execute(
                        "INSERT INTO evidence (card_id, field, run_id, source_id, source_name, "
                        "locator, excerpt, basis, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            cid,
                            name,
                            item["run_id"],
                            item["source_id"],
                            item["source_name"],
                            _dump(item["locator"]),
                            item["excerpt"],
                            item["basis"],
                            item["at"],
                        ),
                    )
        for row in history:
            # Only fields that are units: a field a revert removed keeps no
            # history, or the rows would read back as a cleared field.
            if (
                row["card_id"] not in present
                or f"field:{row['card_id']}:{row['field']}" not in units
            ):
                continue
            db.execute(
                "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, import_id, "
                "reason, old_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["card_id"],
                    row["field"],
                    None
                    if row["old"] is None
                    else _dump(card_model.render_link(row["old"], shown)),
                    None
                    if row["new"] is None
                    else _dump(card_model.render_link(row["new"], shown)),
                    row["kind"],
                    row["ref"],
                    row["by"],
                    row["at"],
                    row["import_id"],
                    row["reason"],
                    None if row["old_source"] is None else _dump(row["old_source"]),
                ),
            )
        proposals = sorted(
            ((k, v) for k, v in units.items() if k.startswith("proposal:")),
            key=lambda item: (str(item[1]["at"]), item[0]),
        )
        for key, value in proposals:
            if value["card"] not in present:
                continue
            cursor = db.execute(
                "INSERT INTO proposals (card_id, field, value, kind, ref, at, import_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    value["card"],
                    value["field"],
                    _dump(value["value"]),
                    value["kind"],
                    value["ref"],
                    value["at"],
                    value.get("import_id"),
                    value["status"],
                ),
            )
            db.execute("INSERT INTO vault_keys VALUES (?, ?)", (cursor.lastrowid, key))
        for conflict in conflicts:
            unit = str(conflict["unit"])
            if not unit.startswith("field:"):
                continue
            _, cid, name = unit.split(":", 2)
            if cid not in present:
                continue
            key = f"conflict:{conflict['commit_id']}:{unit}"
            decided = units.get(f"decision:{_short(key)}")
            lost = conflict["value"] or {}
            cursor = db.execute(
                "INSERT INTO proposals (card_id, field, value, kind, ref, at, import_id, status) "
                "VALUES (?, ?, ?, 'conflict', ?, ?, NULL, ?)",
                (
                    cid,
                    name,
                    _dump(card_model.render_link(lost.get("value"), shown)),
                    conflict["commit"],
                    (lost.get("history") or {}).get("at") or stamp,
                    decided["status"] if decided else "pending",
                ),
            )
            db.execute("INSERT INTO vault_keys VALUES (?, ?)", (cursor.lastrowid, key))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    db.execute(f"PRAGMA user_version = {card_model.MODEL_VERSION}")


# -- the local registry -----------------------------------------------------------------


def _registry_path(workspace: Path) -> Path:
    return workspace / "bi" / VAULTS_DIR / VAULT_REGISTRY


def registry_entry(workspace: Path, vault_id: str) -> dict[str, Any] | None:
    return next((i for i in vault_registry(workspace) if i["id"] == vault_id), None)


def _register(workspace: Path, item: dict[str, Any]) -> None:
    items = [i for i in vault_registry(workspace) if i["id"] != item["id"]]
    items.append(item)
    items.sort(key=lambda i: str(i["id"]))
    path = _registry_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"vaults": items}, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )


def default_author(actor: str) -> str:
    return repo_engine.default_author(actor)


def _checked_author(value: Any, actor: str) -> str:
    author = str(value or "").strip().lower() or default_author(actor)
    if len(author) > MAX_AUTHOR or AUTHOR_RE.match(author) is None:
        raise BiStoreError(
            "author_invalid", "作者名稱只能用小寫英數字與 . _ -（最多 40 個字），例如 leo.chi"
        )
    return author


def _folder(value: Any, *, must_exist: bool) -> Path:
    text = str(value or "").strip()
    if not text:
        raise BiStoreError("path_missing", "需要資料夾路徑")
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise BiStoreError("path_invalid", "請給完整的資料夾路徑（例如 C:\\Users\\...\\Vaults）")
    if must_exist and not path.is_dir():
        raise BiStoreError("path_missing", f"找不到資料夾 {path}")
    return path


def _slug(text: str, limit: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].strip("-")


def _segments(value: Any) -> list[dict[str, str]]:
    if value is None:
        return [{"folder": folder, "label": label} for folder, label in SEGMENTS]
    if not isinstance(value, list) or not value:
        raise BiStoreError("segments_invalid", "segments 必須是非空清單")
    found = []
    for item in value:
        label = str(item.get("label") if isinstance(item, dict) else item or "").strip()
        folder = str(item.get("folder") or "") if isinstance(item, dict) else ""
        folder = folder or _slug(label, 40)
        if not label or VAULT_ID_RE.match(folder) is None:
            raise BiStoreError("segments_invalid", f"應用領域「{label}」需要英數字的資料夾名稱")
        found.append({"folder": folder, "label": label})
    if len({f["folder"] for f in found}) != len(found):
        raise BiStoreError("segments_invalid", "應用領域的資料夾名稱重複")
    return found


def read_vault_json(folder: Path) -> dict[str, Any]:
    """The folder's `repo.json`, checked to be a BI repository."""
    with _repo_errors():
        document = repo_engine.read_repo_json(folder)
    if document["type"] != REPO_TYPE:
        raise BiStoreError("vault_invalid", f"這個知識庫的類型是 {document['type']}，不是 BI")
    return document


# -- the vault -------------------------------------------------------------------------------


class Vault:
    """One registered BI vault on this PC."""

    def __init__(self, workspace: Path, vault_id: str) -> None:
        entry = registry_entry(workspace, vault_id)
        if entry is None:
            raise BiStoreError("vault_unknown", f"這台電腦沒有知識庫「{vault_id}」")
        self.workspace = workspace
        self.id = vault_id
        self.folder = Path(str(entry.get("path") or ""))
        self.author = str(entry.get("author") or "")
        self.dataset = dataset_name(vault_id)
        self.local = local_dir(workspace, vault_id)
        self.db_path = self.local / DB_FILE
        with _repo_errors():
            self.repo = Repository(workspace, vault_id)
        self.lock = self.repo.lock

    @property
    def reachable(self) -> bool:
        return (self.folder / repo_engine.REPO_FILE).is_file()

    def _require_folder(self) -> None:
        if not self.reachable:
            raise BiStoreError(
                "vault_unreachable",
                f"讀不到知識庫資料夾 {self.folder}（OneDrive 是否已同步、路徑是否改了？）",
            )

    def _install_schemas(self) -> None:
        """Install the schema files the vault holds; the vault's file is
        authoritative, so one that differs from this PC's copy refuses."""
        root = self.folder / "schemas"
        for path in sorted(root.glob("*.json")) if root.is_dir() else []:
            try:
                catalog.install(self.workspace, path.name, path.read_text(encoding="utf-8"))
            except catalog.SchemaInstallError as failure:
                raise BiStoreError(
                    "schema_mismatch",
                    f"知識庫的 schema 檔 schemas/{path.name} 和這台電腦上的同一版本內容不同；"
                    "以知識庫的檔案為準，請更新 AEP 或請維護者確認",
                    file=f"schemas/{path.name}",
                    reason=failure.code,
                ) from None

    def _log_entries(self, until: str | None = None) -> list[dict[str, Any]]:
        """The applied commits' changes in order, up to and including commit `until`."""
        entries = []
        for item in self.repo.log():
            commit = item["commit"]
            entries.append(
                {
                    "group": commit["id"],
                    "at": commit["created"],
                    "author": commit["author"],
                    "ref": f"commit:{commit['id'][:12]}",
                    "changes": item["changes"],
                }
            )
            if commit["id"] == until:
                break
        return entries

    def _entries(self) -> list[dict[str, Any]]:
        """The commits' changes, then this PC's local commits and uncommitted changes."""
        entries = self._log_entries()
        state = self.repo.units()
        stages = [
            (f"local:{r['number']}", r["created"], r["ops"]) for r in self.repo.local_commits()
        ]
        pending = self.repo._pending()["sets"]
        stages.append(
            (
                "pending",
                now(),
                [{"unit": k, "value": v, "base": None} for k, v in sorted(pending.items())],
            )
        )
        for group, at, ops in stages:
            changes = []
            for op in ops:
                before = state.get(op["unit"])
                if op["value"] is None:
                    state.pop(op["unit"], None)
                else:
                    state[op["unit"]] = op["value"]
                changes.append(
                    {"unit": op["unit"], "before": before, "after": op["value"], "applied": True}
                )
            entries.append(
                {"group": group, "at": at, "author": self.author, "ref": group, "changes": changes}
            )
        return entries

    def rebuild(self) -> None:
        """Rebuild `bi.sqlite` from the working units."""
        with self.lock:
            self.local.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.db_path, isolation_level=None)) as db:
                db.row_factory = sqlite3.Row
                materialize(db, self.repo.working_units(), self._entries(), self.repo.conflicts())
        from capabilities.bi_cards import search_index

        search_index.sync_quietly(BiStore(self.workspace, self.dataset))

    def reads(self) -> dict[str, Any]:
        """What the Agent reads (decision 8): the published tag, or the pushed
        head of a vault never published (a published commit not applied here
        yet is read as the head until it arrives)."""
        record = self.repo.published()
        applied = {c["id"] for c in self.repo.history(limit=10**9)}
        if record is not None and record["commit"] in applied:
            return {"tag": record["tag"], "commit": record["commit"]}
        return {"tag": None, "commit": self.repo.head()}

    def refresh_published(self) -> Path:
        """Rebuild the Agent's copy when the version it reads has changed;
        this PC's local commits and uncommitted changes never reach it."""
        folder = self.local / PUBLISHED_DIR
        marker = folder / "version.json"
        with self.lock:
            target = {**self.reads(), "model": card_model.MODEL_VERSION}
            try:
                built = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                built = None
            if built == target and (folder / DB_FILE).is_file():
                return folder
            folder.mkdir(parents=True, exist_ok=True)
            commit = target["commit"]
            units = self.repo.state_at(commit) if commit else {}
            entries = self._log_entries(until=commit) if commit else []
            scratch = folder / f".{DB_FILE}.{uuid.uuid4().hex[:8]}.tmp"
            try:
                with closing(sqlite3.connect(scratch, isolation_level=None)) as db:
                    materialize(db, units, entries, [])
                repo_engine.replace_retrying(scratch, folder / DB_FILE)
            finally:
                scratch.unlink(missing_ok=True)
            marker.write_text(json.dumps(target), encoding="utf-8")
            return folder

    def sync(self) -> dict[str, Any]:
        """Apply what the others pushed, then rebuild the local database."""
        with self.lock:
            self._require_folder()
            self._install_schemas()
            with _repo_errors():
                report = self.repo.sync()
            vault_sources.sync_staging(self.repo, self.workspace, self.dataset)
            self.rebuild()
            (self.local / STATE_FILE).write_text(json.dumps({"at": now()}), encoding="utf-8")
            return report

    @contextmanager
    def capture(self, store: BiStore) -> Iterator[sqlite3.Connection]:
        """Run a store write on the local database, stage the units it changed,
        roll it back and rebuild; a new import commits at once."""
        with self.lock:
            self._require_folder()
            if not self.db_path.is_file():
                self.rebuild()
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            try:
                before = units_from_db(connection, keep_ids=True)
                yield connection
                after = units_from_db(connection, keep_ids=True)
                targets = _LinkTargets(connection)
            finally:
                connection.rollback()
                connection.close()
            changed = {
                k: after.get(k)
                for k in set(before) | set(after)
                if repo_engine.canonical(before.get(k)) != repo_engine.canonical(after.get(k))
            }
            if not changed:
                return
            self._links_by_id(changed, after, targets)
            with _repo_errors():
                self.repo.stage_many(dict(sorted(changed.items())))
                if changed.get(repo_engine.SCHEMA_UNIT):
                    self._stage_schema(str(changed[repo_engine.SCHEMA_UNIT]))
                    old = before.get(repo_engine.SCHEMA_UNIT)
                    if old:
                        vault_skills.regenerate_classify(
                            self.repo, self._registry(str(old)), self._registry()
                        )
                if vault_skills.DOMAINS_UNIT in changed:
                    # A domain's notes live in its extract skill (design §8, decision 2).
                    vault_skills.move_notes(self.repo, self._registry())
                imports = [
                    v
                    for k, v in changed.items()
                    if k.startswith("import:") and v and k not in before
                ]
                if imports:
                    vault_sources.commit_split(
                        self.repo, _PURPOSE.get() or _draft(imports, changed)
                    )
            self.rebuild()

    def _links_by_id(
        self, changed: dict[str, Any], after: Mapping[str, Any], targets: _LinkTargets
    ) -> None:
        """Store the link fields that changed by card id. An unchanged one is not
        here, so it keeps its unit, text or id, and a capture makes no false diff."""
        try:
            reg = self._registry(str(after.get(repo_engine.SCHEMA_UNIT) or ""))
        except BiStoreError:
            return  # a schema this PC has not got: the links stay text, as written
        if "relation_types" not in reg.document:
            return  # a schema from before the card model keeps its commits as they were
        for key, value in changed.items():
            if not key.startswith("field:") or not value or value.get("value") is None:
                continue
            _, cid, name = key.split(":", 2)
            entity = reg.types.get(str((after.get(f"card:{cid}") or {}).get("type")))
            item = None if entity is None else entity.get(name)
            if item is not None and item.is_link:
                changed[key] = {**value, "value": targets.stored(value["value"], item.link_to)}

    def _registry(self, ref: str | None = None) -> Registry:
        """The schema `ref`, by default the working copy's."""
        if ref is None:
            ref = str(self.repo.working_units().get(repo_engine.SCHEMA_UNIT) or "")
        return catalog.resolve(self.workspace, ref)

    def _stage_schema(self, ref: str) -> None:
        """Put the schema file into the working copy (decision 1: every
        vault holds the schema it uses, built in or not)."""
        reg = catalog.resolve(self.workspace, ref)
        name = _schema_file_name(reg.schema_id, reg.version)
        readable = name[: -len(".json")] + ".md"
        with tempfile.TemporaryDirectory() as scratch:
            if not (self.folder / "schemas" / name).is_file():
                if reg.source == "installed":
                    # The installed file as it is, so every PC installs the same bytes.
                    source = catalog.schema_path(self.workspace, reg.schema_id, reg.version)
                else:
                    source = Path(scratch) / name
                    source.write_text(catalog.canonical(reg.document), encoding="utf-8")
                self.repo.stage_file(f"schemas/{name}", source)
            if not (self.folder / "schemas" / readable).is_file():
                # The readable document beside it (design §8), generated from the schema.
                doc = Path(scratch) / readable
                doc.write_text(schema_doc.schema_markdown(reg), encoding="utf-8")
                self.repo.stage_file(f"schemas/{readable}", doc)

    def status(self) -> dict[str, Any]:
        """The vault header (compatible with the V4 page) and the version state."""
        reachable = self.reachable
        state: dict[str, Any] = {}
        if reachable:
            with _repo_errors():
                state = self.repo.status()
        conflicts = []
        cards = 0
        if self.db_path.is_file():
            with closing(sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row
                for r in db.execute("SELECT * FROM proposals WHERE kind = 'conflict' ORDER BY id"):
                    conflicts.append(
                        {
                            "card_id": r["card_id"],
                            "field": r["field"],
                            "proposal_id": r["id"],
                            "file": r["ref"],
                            "open": r["status"] == "pending",
                        }
                    )
                cards = int(db.execute("SELECT COUNT(*) FROM cards").fetchone()[0])
        try:
            last = json.loads((self.local / STATE_FILE).read_text(encoding="utf-8")).get("at")
        except (OSError, ValueError):
            last = None
        applied = len(self.repo.history(limit=10**9)) if reachable else 0
        return {
            "vault": self.describe(),
            "reachable": reachable,
            "files": applied + int(state.get("behind") or 0),
            "applied": applied,
            "behind": int(state.get("behind") or 0),
            "ahead": int(state.get("ahead") or 0),
            "uncommitted": int(state.get("uncommitted") or 0),
            "waiting": state.get("waiting") or [],
            "published": state.get("published"),
            "head": state.get("head"),
            "reads": self.reads() if reachable else None,
            "conflicts": conflicts,
            "merges": [],
            "bad": state.get("bad") or [],
            "incomplete": [],
            "cards": cards,
            "last_sync": last,
        }

    def describe(self) -> dict[str, Any]:
        document: dict[str, Any] = {}
        try:
            document = read_vault_json(self.folder)
        except BiStoreError:
            document = {}
        schema = None
        if self.db_path.is_file():
            with closing(sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)) as db:
                try:
                    row = db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
                except sqlite3.OperationalError:
                    row = None
                schema = None if row is None else str(row[0])
        return {
            "id": self.id,
            "dataset": self.dataset,
            "title": document.get("title"),
            "purpose": document.get("purpose"),
            "schema": schema,
            "path": str(self.folder),
            "author": self.author,
            "reachable": bool(document),
        }


def _draft(imports: list[dict[str, Any]], changed: Mapping[str, Any]) -> str:
    """A drafted purpose for an import commit (the person can give their own)."""
    names = "、".join(sorted({str(i["filename"]) for i in imports}))
    cards = sum(1 for k, v in changed.items() if k.startswith("card:") and v is not None)
    fields = sum(1 for k in changed if k.startswith("field:"))
    return f"匯入 {names}：{cards} 張卡、{fields} 個欄位"[: repo_engine.MAX_PURPOSE]


def ensure_current(store: BiStore) -> None:
    """Rebuild a vault's local database once when an older AEP built it, so a
    reader finds the current tables. No rebuild is possible without the
    repository; the next one that is possible does it."""
    if not store.exists or store.vault_id is None:
        return
    with contextlib.suppress(OSError, sqlite3.Error, BiStoreError, RepoError):
        with closing(sqlite3.connect(f"file:{store.path}?mode=ro", uri=True)) as db:
            built = int(db.execute("PRAGMA user_version").fetchone()[0])
        if built < card_model.MODEL_VERSION:
            Vault(store.workspace, store.vault_id).rebuild()


@contextmanager
def capture(store: BiStore) -> Iterator[sqlite3.Connection]:
    """`BiStore._db(write=True)` of a vault dataset (see `Vault.capture`)."""
    if store.vault_id is None:
        raise BiStoreError("vault_unknown", "不是知識庫資料集")
    with Vault(store.workspace, store.vault_id).capture(store) as connection:
        yield connection


# -- create, join, convert, list ----------------------------------------------------------


def _free_name(workspace: Path, vault_id: str) -> None:
    if registry_entry(workspace, vault_id) is not None:
        raise BiStoreError("vault_exists", f"這台電腦已經有知識庫「{vault_id}」")
    if (workspace / "bi" / dataset_name(vault_id)).exists():
        raise BiStoreError(
            "vault_exists", f"已經有一個名為「{dataset_name(vault_id)}」的本機資料集，請換一個 id"
        )
    if local_dir(workspace, vault_id).exists():
        raise BiStoreError("vault_exists", f"本機已有知識庫「{vault_id}」的資料夾")


def _new_vault(
    workspace: Path, given: dict[str, Any], actor: str
) -> tuple[Vault, list[dict[str, str]]]:
    parent = _folder(given.get("path"), must_exist=True)
    title = str(given.get("title") or "").strip()
    if not title:
        raise BiStoreError("title_missing", "需要知識庫名稱")
    vault_id = str(given.get("id") or "").strip().lower()
    if not vault_id:
        base = _slug(title, MAX_VAULT_ID - 7) or "vault"
        vault_id = f"{base}-{uuid.uuid4().hex[:6]}"
    if len(vault_id) > MAX_VAULT_ID or not VAULT_ID_RE.match(vault_id):
        raise BiStoreError(
            "vault_id_invalid", f"知識庫 id 只能用小寫英數字與 -，最多 {MAX_VAULT_ID} 個字"
        )
    _free_name(workspace, vault_id)
    author = _checked_author(given.get("author"), actor)
    segments = _segments(given.get("segments"))
    if (parent / vault_id).exists():
        raise BiStoreError("vault_exists", f"資料夾 {parent / vault_id} 已經存在")
    with _repo_errors():
        repo = repo_engine.create(
            workspace,
            parent,
            repo_id=vault_id,
            title=title,
            purpose=str(given.get("purpose") or ""),
            kind=REPO_TYPE,
            author=author,
        )
    for item in segments:
        (repo.folder / "sources" / "applications" / item["folder"]).mkdir(
            parents=True, exist_ok=True
        )
    for name in LIBRARY:
        (repo.folder / "sources" / "library" / name).mkdir(parents=True, exist_ok=True)
    _register(
        workspace, {"id": vault_id, "path": str(repo.folder), "author": author, "joined": now()}
    )
    return Vault(workspace, vault_id), segments


def _stage_default_pack(vault: Vault, reg: Registry, given: Mapping[str, Any]) -> None:
    """A new vault's Dashboard: the built-in analyses its schema satisfies
    (design BI_ANALYSIS_DASHBOARD.md §4.2), unless `default_pack` is false."""
    if given.get("default_pack") is False:
        return
    from capabilities.bi_cards import packs

    packs.stage_pack(vault, reg, packs.default_pack())


def _segments_meta(segments: list[dict[str, str]]) -> str:
    return json.dumps(segments, ensure_ascii=False, sort_keys=True)


def create(workspace: Path, given: dict[str, Any], actor: str) -> dict[str, Any]:
    """A new vault folder under `path`, bound to `schema`, and this PC joined."""
    reg = catalog.resolve(workspace, str(given.get("schema") or ""))
    vault, segments = _new_vault(workspace, given, actor)
    with vault.lock, _repo_errors():
        vault.repo.stage(repo_engine.SCHEMA_UNIT, reg.ref)
        vault.repo.stage("meta:vault_segments", _segments_meta(segments))
        vault._stage_schema(reg.ref)
        vault_skills.stage_classify(vault.repo, reg)
        _stage_default_pack(vault, reg, given)
        vault.repo.commit(f"建立知識庫，使用 schema {reg.ref}", kind="schema")
        pushed = vault.repo.push()
        readme.write_readme(vault.repo)
    report = vault.sync()
    return {"vault": vault.describe(), "push": pushed["status"], "sync": report}


def join(workspace: Path, given: dict[str, Any], actor: str) -> dict[str, Any]:
    """Use an existing vault folder on this PC."""
    folder = _folder(given.get("path"), must_exist=True)
    document = read_vault_json(folder)
    vault_id = str(document["id"])
    author = _checked_author(given.get("author"), actor)
    known = registry_entry(workspace, vault_id)
    if known is not None and Path(str(known.get("path"))) != folder:
        # The same vault at a new place (the folder was moved or re-synced).
        _register(workspace, {**known, "path": str(folder)})
        author = str(known.get("author") or author)
    elif known is None:
        _free_name(workspace, vault_id)
        own = folder / repo_engine.COMMITS_DIR / author
        if own.is_dir() and any(own.glob("*.json")) and not given.get("resume"):
            raise BiStoreError(
                "author_taken",
                f"知識庫裡已經有作者「{author}」的 commit；若是你本人換電腦，請勾選「接續」"
                "（resume），否則請用別的作者名稱",
                author=author,
            )
        _register(
            workspace, {"id": vault_id, "path": str(folder), "author": author, "joined": now()}
        )
    else:
        author = str(known.get("author") or author)
    with _repo_errors():
        repo_engine.join(workspace, folder, author=author)
    vault = Vault(workspace, vault_id)
    report = vault.sync()
    return {"vault": vault.describe(), "sync": report}


def convert(workspace: Path, given: dict[str, Any], actor: str) -> dict[str, Any]:
    """A new vault holding a local dataset as one `import` commit (every card,
    value with its source and latest history, proposal and piece of
    evidence). The dataset itself is left as it was."""
    name = str(given.get("dataset") or "").strip()
    if not DATASET_RE.match(name) or is_subscribed(name) or name == SUBSCRIBED_DIR:
        raise BiStoreError("dataset_invalid", "只能轉換這台電腦自己的資料集")
    source = BiStore(workspace, name)
    if source.vault_id is not None:
        raise BiStoreError("dataset_invalid", "這個資料集已經是知識庫")
    if not source.exists:
        raise BiStoreError("dataset_unknown", f"沒有這個資料集「{name}」")
    with closing(sqlite3.connect(f"file:{source.path}?mode=ro", uri=True)) as db:
        units = units_from_db(db)
    units.setdefault(repo_engine.SCHEMA_UNIT, source.schema_ref())
    vault, segments = _new_vault(workspace, {"title": name, **given}, actor)
    with vault.lock, _repo_errors():
        units["meta:vault_segments"] = _segments_meta(segments)
        vault.repo.stage_many(dict(sorted(units.items())))
        vault._stage_schema(str(units[repo_engine.SCHEMA_UNIT]))
        reg = catalog.resolve(workspace, str(units[repo_engine.SCHEMA_UNIT]))
        vault_skills.stage_classify(vault.repo, reg)
        vault_skills.move_notes(vault.repo, reg)
        _stage_default_pack(vault, reg, given)
        vault.repo.commit(f"把資料集「{name}」轉成知識庫", kind="import")
        pushed = vault.repo.push()
        readme.write_readme(vault.repo)
    report = vault.sync()
    return {
        "vault": vault.describe(),
        "push": pushed["status"],
        "sync": report,
        "dataset": name,
        "sources": _copy_sources(workspace, name, vault.dataset),
    }


def _copy_sources(workspace: Path, dataset: str, target: str) -> dict[str, Any]:
    """The dataset's sources in the new vault: copied to its local staging and
    staged for the shared folder (`docs/phases/BI_SOURCES_IN_REPOSITORY.md` S5);
    commit and push stay the person's. They keep their ids, which the converted
    evidence uses. The vault exists by now, so a failure here is reported and the
    sources can be added again by hand."""
    from capabilities.bi_cards.staging import Staging

    try:
        staging = Staging(workspace, target)
        report: dict[str, Any] = dict(staging.copy_sources_from(Staging(workspace, dataset)))
        staged = 0
        repo = staging._vault_repo()
        for source in staging.sources() if repo is not None else ():
            with repo.lock:
                vault_sources.stage_source(repo, staging, source["id"])
            staged += 1
        return {**report, "staged": staged}
    except (OSError, sqlite3.Error, BiStoreError, RepoError) as failure:
        return {"copied": 0, "skipped": 0, "staged": 0, "error": type(failure).__name__}


def listing(workspace: Path) -> list[dict[str, Any]]:
    """The vaults this PC uses, with their purpose and card count."""
    found = []
    for item in vault_registry(workspace):
        try:
            vault = Vault(workspace, str(item["id"]))
        except BiStoreError:
            continue
        described = vault.describe()
        store = BiStore(workspace, vault.dataset)
        described["cards"] = len(store.card_rows()) if store.exists else 0
        found.append(described)
    return found


def sync(workspace: Path, vault_id: str) -> dict[str, Any]:
    return Vault(workspace, vault_id).sync()


def status(workspace: Path, vault_id: str) -> dict[str, Any]:
    return Vault(workspace, vault_id).status()


# -- version operations (design §5–§7) --------------------------------------------------------


def _vault(workspace: Path, vault_id: str) -> Vault:
    vault = Vault(workspace, vault_id)
    vault._require_folder()
    return vault


def unit_label(units: Mapping[str, Any], key: str) -> str:
    """A unit in words for the page: card name and field rather than ids."""
    kind, _, rest = key.partition(":")
    card_id, _, field = rest.partition(":")

    def card() -> str:
        value = units.get(f"card:{card_id}")
        if isinstance(value, dict):
            return f"{value.get('type')}「{value.get('name') or value.get('key')}」"
        return f"卡片 {card_id}"

    if kind == "card":
        return card()
    if kind == "field":
        return f"{card()} 的 {field}"
    if kind == "evidence":
        return f"{card()} 的 {field} 證據"
    if kind == "meta":
        return {"domains": "領域設定", "dashboard": "Dashboard 的順序"}.get(rest, f"設定 {rest}")
    if key == repo_engine.SCHEMA_UNIT:
        return "schema 版本"
    if kind == "skill":
        return f"skill「{rest}」"
    if kind == "source":
        value = units.get(key)
        return f"來源「{value.get('name') if isinstance(value, dict) else rest[:8]}」"
    if kind == "check":
        return vault_checks.label(key, units)
    if kind == "analysis":
        value = units.get(key)
        return f"分析「{value.get('title') if isinstance(value, dict) else rest}」"
    return {"proposal": "待審提議", "import": "匯入紀錄", "decision": "衝突決定"}.get(kind, key)


def pending(workspace: Path, vault_id: str) -> dict[str, Any]:
    """What this PC has not pushed: uncommitted changes and local commits."""
    vault = _vault(workspace, vault_id)
    with vault.lock:
        head = vault.repo.units()
        work = vault.repo._pending()
        units = {**head, **work["sets"]}
        shown = card_model.card_names_of(units)
        changes = [
            {
                "unit": k,
                "label": unit_label(units, k),
                "before": card_model.render_links_within(head.get(k), shown),
                "after": card_model.render_links_within(v, shown),
            }
            for k, v in sorted(work["sets"].items())
        ]
        return {
            "uncommitted": changes,
            "files": sorted(work["files"]),
            "commits": vault.repo.local_commits(),
        }


def commit(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    with vault.lock, _repo_errors():
        record = vault_sources.commit_split(vault.repo, str(given.get("purpose") or ""))
    vault.rebuild()
    return {"commit": record}


def discard(workspace: Path, vault_id: str) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    with vault.lock, _repo_errors():
        vault.repo.discard()
    vault.rebuild()
    return {"discarded": True}


def push(workspace: Path, vault_id: str) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    with vault.lock:
        vault._install_schemas()
        with _repo_errors():
            result = vault.repo.push()
            if result["status"] == "pushed":
                readme.write_readme(vault.repo)
        if result["status"] == "conflicts":
            units = vault.repo.working_units()
            shown = card_model.card_names_of(units)
            result["conflicts"] = [
                {
                    **card_model.render_links_within(item, shown),
                    "label": unit_label(units, item["unit"]),
                }
                for item in result["conflicts"]
            ]
        vault.rebuild()
        return result


def resolve(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    with _repo_errors():
        vault.repo.resolve(
            str(given.get("unit") or ""), str(given.get("choice") or ""), given.get("value")
        )
    return {"resolved": True}


def history(workspace: Path, vault_id: str, limit: int = 50) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    with _repo_errors():
        return {
            "commits": vault.repo.history(limit),
            "tags": vault.repo.tags(),
            "published": vault.repo.published(),
        }


def diff(workspace: Path, vault_id: str, commit_id: str) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    with _repo_errors():
        target = vault.repo.resolve_version(commit_id)
        changes = vault.repo.diff(target)
        units = {**vault.repo.units(), **vault.repo.state_at(target)}
    shown = card_model.card_names_of(units)
    return {
        "changes": [
            {**card_model.render_links_within(c, shown), "label": unit_label(units, c["unit"])}
            for c in changes
        ]
    }


def revert(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    with vault.lock, _repo_errors():
        record = vault.repo.revert(str(given.get("version") or ""), str(given.get("purpose") or ""))
    vault.rebuild()
    return {"commit": record}


def tag(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    with _repo_errors():
        version = str(given.get("version") or "") or None
        record = vault.repo.tag(
            str(given.get("name") or ""), str(given.get("purpose") or ""), version=version
        )
        readme.write_readme(vault.repo)
    return {"tag": record}


def publish(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Publish a tag. Only a person's confirm click calls this (design §7)."""
    if given.get("confirm") is not True:
        raise BiStoreError("confirm_required", "發佈要由人按確認")
    vault = _vault(workspace, vault_id)
    with _repo_errors():
        record = vault.repo.publish(str(given.get("tag") or ""))
        readme.write_readme(vault.repo)
    vault.refresh_published()
    return {"published": record}


def skills(workspace: Path, vault_id: str) -> dict[str, Any]:
    """The vault's current skills (working copy) with their text, and the
    source folders a skill may apply to (design §8)."""
    vault = _vault(workspace, vault_id)
    units = vault.repo.working_units()
    found = []
    with _repo_errors():
        for item in repo_skills.current_skills(vault.repo, units):
            try:
                skill = repo_skills.read_skill(vault.repo, item["name"], units)
            except RepoError as failure:
                found.append({**item, "problem": failure.message})
                continue
            found.append(
                {
                    **item,
                    "card_types": list(skill.card_types),
                    "body": skill.body,
                    "generated": skill.extra.get("generated") == "true",
                }
            )
    folders = sorted(
        p.relative_to(vault.folder).as_posix()
        for p in (vault.folder / "sources").rglob("*")
        if p.is_dir() and vault_sources.MARKDOWN_DIR not in p.relative_to(vault.folder).parts
    )
    return {
        "skills": found,
        "schema": str(units.get(repo_engine.SCHEMA_UNIT) or ""),
        "folders": ["sources", *folders],
        "roles": ["classify", "extract"],
    }


def save_skill(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Stage a new revision of a skill, bound to the vault's current schema
    (that is how a skill 「需要更新」 is updated); the person commits it."""
    vault = _vault(workspace, vault_id)
    with vault.lock, _repo_errors():
        skill = _checked_skill(vault, given)
        value = repo_skills.stage_skill(vault.repo, skill)
    return {"skill": {"name": skill.name, **value}, "status": vault.status()}


def checked_skill(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> repo_skills.Skill:
    """The skill `save_skill` would stage, checked the same way; nothing is
    written (an AI suggestion is checked with it before it is shown)."""
    vault = _vault(workspace, vault_id)
    with vault.lock, _repo_errors():
        return _checked_skill(vault, given)


def _checked_skill(vault: Vault, given: Mapping[str, Any]) -> repo_skills.Skill:
    units = vault.repo.working_units()
    name = str(given.get("name") or "").strip()
    role = str(given.get("role") or "extract")
    if role not in ("classify", "extract"):
        raise BiStoreError("skill_invalid", "BI 的 skill 只有 classify 與 extract 兩種")
    body = str(given.get("body") or "")
    applies_to = given.get("applies_to") or []
    card_types = given.get("card_types") or []
    for value, key in ((applies_to, "applies_to"), (card_types, "card_types")):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise BiStoreError("skill_invalid", f"{key} 必須是文字清單")
    reg = vault._registry()
    unknown = [t for t in card_types if t not in reg.types]
    if unknown:
        raise BiStoreError("skill_invalid", f"schema 沒有這些類型：{'、'.join(unknown)}")
    extra: dict[str, str] = {}
    if repo_skills.skill_unit(name) in units:
        extra = {
            k: v
            for k, v in repo_skills.read_skill(vault.repo, name, units).extra.items()
            if k != "generated"
        }
    # Parsing the rendered file checks name, role, folders and text.
    return repo_skills.parse_skill(
        repo_skills.render_skill(
            repo_skills.Skill(
                name=name,
                revision=1,
                schema=reg.ref,
                role=role,
                applies_to=tuple(str(a).strip().rstrip("/") for a in applies_to),
                body=body,
                card_types=tuple(card_types),
                extra=extra,
            )
        )
    )


def reading_store(workspace: Path, dataset: str) -> BiStore:
    """The store the Agent reads (design §7, decision 8): for a vault, a
    read-only copy of its published version (the pushed head when never
    published); any other dataset as it is."""
    store = BiStore(workspace, dataset)
    if store.vault_id is None:
        return store
    vault = Vault(workspace, store.vault_id)
    if not vault.reachable and not (vault.local / PUBLISHED_DIR / DB_FILE).is_file():
        raise BiStoreError("vault_unreachable", f"讀不到知識庫資料夾 {vault.folder}")
    if vault.reachable:
        with _repo_errors():
            folder = vault.refresh_published()
    else:
        folder = vault.local / PUBLISHED_DIR  # the last copy this PC built
    return BiStore(workspace, dataset, view=folder)
