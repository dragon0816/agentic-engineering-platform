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
    field:<card id>:<field>      {"value", "source", "history"}; value null = cleared;
                                 `history.old_evidence`: what a replaced value rested on
    evidence:<card id>:<field>   [evidence rows]
    proposal:<key>               {"card", "field", "value", "kind", "ref", "at", "import_id",
                                  "status"}
    import:<import id>           {"filename", "entity_type", "at", "by", "run_id", "undone"}
    decision:<key>               {"status"}: a person's decision on a replay conflict
    schema_change:<kind>:<...>   a compatible schema change on the version (`schema_merge`)

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
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from capabilities.bi_cards import (
    analyses,
    card_markdown,
    card_model,
    catalog,
    extract,
    homes,
    names,
    profile,
    schema_doc,
    schema_merge,
    schema_versions,
    vault_checks,
    vault_skills,
    vault_sources,
    vault_tools,
)
from capabilities.bi_cards.schema import Registry, norm_key, shipped
from capabilities.bi_cards.store import (
    DATASET_RE,
    DB_FILE,
    PUBLISHED_SOURCES,
    SCHEMA,
    SUBSCRIBED_DIR,
    VAULT_PREFIX,
    VAULT_REGISTRY,
    VAULTS_DIR,
    BiStore,
    BiStoreError,
    PlannedRow,
    add_missing_columns,
    card_id_for,
    evidence_unit,
    insert_evidence_unit,
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
#: What `bi.sqlite` was last built from (`Vault.rebuild`).
BUILD_FILE = "vault_build.json"
#: The local copy of the version the Agent reads (design §7), with `version.json`.
PUBLISHED_DIR = "published"

#: The 11 market segments of the owner's chart (BI_VAULT.md §4, §6.2): id and label.
#: `segment` values on cards, and no longer folders (BI_CARD_MODEL.md §1).
MARKET_SEGMENTS: tuple[tuple[str, str], ...] = (
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
#: The owner's default applications (BI_CARD_MODEL.md §1, 2026-11-04): folder name
#: and label. A vault may name its own at creation.
SEGMENTS: tuple[tuple[str, str], ...] = (
    ("aidc", "AIDC"),
    ("aerospace", "Aerospace"),
    ("robotics", "Robotics"),
    ("wireless", "Wireless"),
)

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
    "card_marks",
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


def _schema_conflict_key(item: Mapping[str, Any]) -> str:
    return _short(f"conflict:{item['commit_id']}:{item['unit']}")


def _schema_in_repo(repo: Any, ref: str) -> dict[str, Any] | None:
    """A version's document as this repository holds it; None when it is not there."""
    schema_id, _, version = ref.partition("@")
    for reg in shipped():
        if (reg.schema_id, reg.version) == (schema_id, version):
            return dict(reg.document)
    name = _schema_file_name(schema_id, version)
    for root in (repo.folder, repo.work / "files"):
        try:
            found = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        return found if isinstance(found, dict) else None
    return None


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


#: Written at publish; `cards/` is generated and never read back (design §6).
CARDS_DIR = "cards"
CARDS_MANIFEST = f"{CARDS_DIR}/_manifest.json"
SNAPSHOT_DIR = "published"


class BiType:
    """The `bi` repository type: card units and their checks."""

    name = REPO_TYPE
    layout = homes.LAYOUT
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
        if key.startswith(schema_merge.PREFIX):
            return schema_merge.unit_problem(key, value)
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

    def skill_binding(self, units: Mapping[str, Any], schema: str) -> dict[str, Any]:
        """What a skill revision is written against: the version, and the changes merged
        on it so far, so a later change can be told apart from these."""
        seen = sorted(schema_merge.stored_changes(units))
        return {
            "schema": catalog.base_ref(schema),
            **({"schema_seen": seen} if seen else {}),
        }

    def skill_review(
        self, repo: Any, name: str, value: Mapping[str, Any], units: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Whether the schema moved in a way that touches this skill (`BI_CARD_MODEL.md` §4.3)."""
        current = str(units.get(repo_engine.SCHEMA_UNIT) or "")
        written_for = catalog.base_ref(str(value.get("schema") or ""))
        changes = schema_merge.stored_changes(units)
        seen = set(value.get("schema_seen") or [])
        if not current or (written_for == current and seen == set(changes)):
            return {"needs_update": False, "update_blocks": False, "update_reason": ""}
        old_base, new_base = _schema_in_repo(repo, written_for), _schema_in_repo(repo, current)
        try:
            skill = repo_skills.read_skill(repo, name, units)
        except RepoError:
            return schema_merge.skill_verdict(None, None, "", (), str(value.get("role")))
        if old_base is None or new_base is None:
            return schema_merge.skill_verdict(None, None, "", (), skill.role)
        kept = {k: v for k, v in changes.items() if k in seen}
        verdict = schema_merge.skill_verdict(
            schema_merge.overlay(old_base, kept)[0],
            schema_merge.overlay(new_base, changes)[0],
            skill.body,
            skill.card_types,
            skill.role,
            gone=sorted(seen - set(changes)),
        )
        if skill.extra.get("generated") == "true" and not verdict["update_blocks"]:
            # Nobody edited it, and a run reads it as the schema is now (`run_rules`).
            return {"needs_update": False, "update_blocks": False, "update_reason": ""}
        return verdict

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


def _history_value(row: sqlite3.Row) -> dict[str, Any]:
    # Only when the change moved it, so a unit from before this stays as it was.
    moved = row["old_evidence"] if "old_evidence" in row.keys() else None  # noqa: SIM118
    return {
        "kind": row["kind"],
        "ref": row["ref"],
        "by": row["by"],
        "at": row["at"],
        "import_id": row["import_id"],
        "reason": row["reason"],
        **({} if moved is None else {"old_evidence": _load(moved)}),
    }


def units_from_db(db: sqlite3.Connection, *, keep_ids: bool = False) -> dict[str, Any]:
    """The units a BI database holds. A vault's database keeps its card ids
    (`keep_ids`); a dataset becoming a vault gets them from `card_id_for`."""
    db.row_factory = sqlite3.Row
    tables = _tables(db)
    units: dict[str, Any] = {}
    for r in db.execute("SELECT * FROM meta") if "meta" in tables else []:
        if r["key"] == "schema":
            # What the database reads may have changes merged on it; they are units of their own.
            units[repo_engine.SCHEMA_UNIT] = catalog.base_ref(r["value"])
        else:
            units[f"meta:{r['key']}"] = r["value"]
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
    cleared: dict[str, dict[str, str]] = {}
    if "card_marks" in tables:
        for r in db.execute("SELECT * FROM card_marks"):
            cleared[r["card_id"]] = {"at": r["at"], "by": r["by"], "reason": r["reason"]}
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
            **({"mark_cleared": cleared[r["id"]]} if r["id"] in cleared else {}),
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
                evidence_unit(r)
            )
    if "field_states" in tables:
        for r in db.execute("SELECT * FROM field_states WHERE origin = 'unit'"):
            if r["card_id"] not in ids:
                continue
            units[f"{card_model.STATE_PREFIX}{ids[r['card_id']]}:{r['field']}"] = {
                k: r[k] for k in ("state", "reason", "raw", "ref", "by", "at") if r[k] is not None
            }
    keys = {}
    if "vault_keys" in tables:
        keys = {
            int(r["proposal_id"]): str(r["key"]) for r in db.execute("SELECT * FROM vault_keys")
        }
    for r in db.execute("SELECT * FROM proposals ORDER BY id"):
        if r["card_id"] not in ids:
            continue
        key = keys.get(int(r["id"]))
        said = r["reason"] if "reason" in r.keys() else None  # noqa: SIM118 - a sqlite3.Row
        why = {"reason": said} if said else {}
        held = r["evidence"] if "evidence" in r.keys() else None  # noqa: SIM118 - a sqlite3.Row
        if key is not None and key.startswith("conflict:"):
            if r["status"] != "pending":
                units[f"decision:{_short(key)}"] = {"status": r["status"], **why}
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
            **why,
            **({"evidence": _load(held)} if held else {}),
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
                    "old_evidence": history.get("old_evidence"),
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


def _fill_relations(db: sqlite3.Connection, units: Mapping[str, Any], reg: Registry | None) -> None:
    """`relations` and `relation_evidence`: one row per link that resolves, derived
    and never a unit, then the relation units, which may set a derived row's status
    (`docs/phases/BI_CARD_MODEL.md` §3.3)."""
    targets = _LinkTargets(db)
    for key, value in sorted(units.items()) if reg is not None else ():
        if not key.startswith("field:") or value.get("value") is None:
            continue
        _, cid, name = key.split(":", 2)
        entity = reg.types.get(targets.kinds.get(cid, ""))  # type: ignore[union-attr]
        item = None if entity is None else entity.get(name)
        if item is None or not item.is_link:
            continue
        kind = item.relation_type or card_model.default_relation_type(name)
        held = value["value"] if isinstance(value["value"], list) else [value["value"]]
        for one in held:
            target = (
                one["card"]
                if card_model.is_link_item(one)
                else targets.find(str(one), item.link_to)
            )
            if target in targets.kinds:
                db.execute(
                    "INSERT OR IGNORE INTO relations (relation_id, from_card_id, relation_type, "
                    "to_card_id, status, origin, source_field) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        card_model.relation_id(cid, kind, target),
                        cid,
                        kind,
                        target,
                        card_model.UNREVIEWED,
                        card_model.SCHEMA_FIELD,
                        name,
                    ),
                )
    for key, value in sorted(units.items()):
        if key.startswith(card_model.RELATION_PREFIX):
            if value["from"] not in targets.kinds or value["to"] not in targets.kinds:
                continue  # a card it joined is gone
            relation = key[len(card_model.RELATION_PREFIX) :]
            derived = db.execute(
                "SELECT origin, source_field FROM relations WHERE relation_id = ?", (relation,)
            ).fetchone()
            db.execute(
                "INSERT OR REPLACE INTO relations (relation_id, from_card_id, relation_type, "
                "to_card_id, status, origin, source_field, scope, note, by, at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    relation,
                    value["from"],
                    value["type"],
                    value["to"],
                    value["status"],
                    derived["origin"] if derived else value["origin"],
                    derived["source_field"] if derived else None,
                    value.get("scope"),
                    value.get("note"),
                    value.get("by"),
                    value.get("at"),
                ),
            )
    for key, value in sorted(units.items()):
        if key.startswith(card_model.RELATION_EVIDENCE_PREFIX):
            if not db.execute(
                "SELECT 1 FROM relations WHERE relation_id = ?", (value["relation"],)
            ).fetchone():
                continue
            db.execute(
                "INSERT INTO relation_evidence (evidence_link_id, relation_id, basis_card_id, "
                "reference_id, stance, assessment, by, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key[len(card_model.RELATION_EVIDENCE_PREFIX) :],
                    value["relation"],
                    value["basis_card"],
                    value["reference_id"],
                    value["stance"],
                    None if value.get("assessment") is None else _dump(value["assessment"]),
                    value.get("by"),
                    value.get("at"),
                ),
            )


def _fill_homes(
    db: sqlite3.Connection,
    units: Mapping[str, Any],
    reg: Registry | None,
    profiles: Mapping[str, Mapping[str, Any]],
) -> None:
    """Derived, after everything else (`BI_CARD_MODEL.md` §1, §3.4): a card belongs to
    the homes whose sources gave it evidence, and a field is `not_applicable` only when
    one of those homes' profiles states it and none uses it. A field a profile merely
    omits reads `unknown` (owner 2026-11-04). A state or value already there wins."""
    folders = {
        str(value.get("id")): str(value.get("folder") or "")
        for key, value in units.items()
        if key.startswith(vault_sources.PREFIX) and isinstance(value, dict)
    }
    belongs: dict[str, set[str]] = {}
    gave = {(str(r[0]), str(r[1])) for r in db.execute(
        "SELECT DISTINCT card_id, source_id FROM evidence").fetchall()}  # fmt: skip
    # What a replaced value rested on gave evidence too: replacing it does not move the card.
    for row in db.execute(
        "SELECT card_id, old_evidence FROM history WHERE old_evidence IS NOT NULL"
    ).fetchall():
        gave.update((str(row[0]), str(item["source_id"])) for item in _load(row[1]))
    for card, source in sorted(gave):
        home = homes.home_of(folders.get(source, ""))
        if home is not None:
            belongs.setdefault(card, set()).add(home)
    db.executemany(
        "INSERT INTO card_app_folders (card_id, application) VALUES (?, ?)",
        [(card, home) for card, found in sorted(belongs.items()) for home in sorted(found)],
    )
    if not profiles or reg is None:
        return
    for row in db.execute("SELECT id, entity_type FROM cards").fetchall():
        card_id, entity = str(row[0]), reg.types.get(str(row[1]))
        if entity is None or card_id not in belongs:
            continue
        stated: dict[str, str | None] = {}
        used: set[str] = set()
        for home in sorted(belongs[card_id]):
            view = ((profiles.get(home) or {}).get("types") or {}).get(entity.name) or {}
            used.update(view.get("fields") or ())
            for item in view.get("not_applicable") or ():
                stated.setdefault(item["field"], item.get("reason"))
        if not stated:
            continue
        have = {
            str(item[0])
            for item in db.execute("SELECT field FROM fields WHERE card_id = ?", (card_id,))
        }
        db.executemany(
            "INSERT OR IGNORE INTO field_states (card_id, field, state, reason, origin) "
            "VALUES (?, ?, ?, ?, 'profile')",
            [
                (card_id, name, card_model.NOT_APPLICABLE, reason)
                for name, reason in sorted(stated.items())
                if name not in have and name not in used and entity.get(name) is not None
            ],
        )


def _evidence_read(
    units: Mapping[str, Any],
    entries: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """The evidence units as a card reads them. Field and evidence are separate units, so a
    commit can lose the field and still apply its evidence; the winning value must not show a
    citation of the lost one, which comes back with its value if the conflict is accepted.
    The unit stays as it is: `units_from_db` compares what this reads with itself."""
    read = {k: v for k, v in units.items() if k.startswith("evidence:")}
    last: dict[str, tuple[str, Any]] = {}
    for entry in entries:
        for change in entry["changes"]:
            unit = str(change["unit"])
            if change["applied"] and unit.startswith("evidence:"):
                last[unit] = (str(entry["group"]), change["before"])
    for conflict in conflicts:
        unit = f"evidence:{str(conflict['unit']).removeprefix('field:')}"
        if str(conflict["unit"]).startswith("field:") and unit in last:
            group, before = last[unit]
            if group == conflict["commit_id"]:
                read[unit] = before or []
    return read


def materialize(
    db: sqlite3.Connection,
    units: Mapping[str, Any],
    entries: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    reg: Registry | None = None,
    profiles: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    """Rebuild every BI table of `db` from `units` inside one transaction.
    Relations from link fields need `reg`, the schema the units are on; what a home
    does not use also needs its `profiles` (`profile.load_all`)."""
    db.row_factory = sqlite3.Row
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
                reads = reg.ref if reg is not None and catalog.base_ref(reg.ref) == value else value
                db.execute("INSERT INTO meta (key, value) VALUES ('schema', ?)", (reads,))
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
            mark = value.get("mark_cleared")
            if isinstance(mark, dict):
                db.execute(
                    "INSERT INTO card_marks (card_id, at, by, reason) VALUES (?, ?, ?, ?)",
                    (cid, str(mark.get("at")), str(mark.get("by")), str(mark.get("reason"))),
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
            elif key.startswith(card_model.STATE_PREFIX):
                _, cid, name = key.split(":", 2)
                if cid not in present:
                    continue
                db.execute(
                    "INSERT INTO field_states (card_id, field, state, reason, raw, origin, ref, "
                    "by, at) VALUES (?, ?, ?, ?, ?, 'unit', ?, ?, ?)",
                    (
                        cid,
                        name,
                        value["state"],
                        value.get("reason"),
                        value.get("raw"),
                        value.get("ref"),
                        value.get("by"),
                        value.get("at"),
                    ),
                )
        for key, value in sorted(_evidence_read(units, entries, conflicts).items()):
            _, cid, name = key.split(":", 2)
            if cid in present:
                for item in value:
                    insert_evidence_unit(db, cid, name, item)
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
                "reason, old_source, old_evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    None if row["old_evidence"] is None else _dump(row["old_evidence"]),
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
                "INSERT INTO proposals (card_id, field, value, kind, ref, at, import_id, status, "
                "reason, evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    value["card"],
                    value["field"],
                    _dump(value["value"]),
                    value["kind"],
                    value["ref"],
                    value["at"],
                    value.get("import_id"),
                    value["status"],
                    value.get("reason"),
                    _dump(value["evidence"]) if value.get("evidence") else None,
                ),
            )
            db.execute("INSERT INTO vault_keys VALUES (?, ?)", (cursor.lastrowid, key))
        # What a lost value rested on: its commit's evidence, itself lost or applied.
        cited = {
            (e["group"], str(c["unit"])): c["after"]
            for e in entries
            for c in e["changes"]
            if c["applied"] and str(c["unit"]).startswith("evidence:")
        }
        cited.update(
            {
                (c["commit_id"], str(c["unit"])): c["value"]
                for c in conflicts
                if str(c["unit"]).startswith("evidence:")
            }
        )
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
            rested = cited.get((conflict["commit_id"], f"evidence:{cid}:{name}"))
            cursor = db.execute(
                "INSERT INTO proposals (card_id, field, value, kind, ref, at, import_id, status, "
                "reason, evidence) VALUES (?, ?, ?, 'conflict', ?, ?, NULL, ?, ?, ?)",
                (
                    cid,
                    name,
                    _dump(card_model.render_link(lost.get("value"), shown)),
                    conflict["commit"],
                    (lost.get("history") or {}).get("at") or stamp,
                    decided["status"] if decided else "pending",
                    decided.get("reason") if decided else None,
                    _dump(rested) if rested else None,
                ),
            )
            db.execute("INSERT INTO vault_keys VALUES (?, ?)", (cursor.lastrowid, key))
        _fill_relations(db, units, reg)
        # A pending proposal's value is the candidate, so the empty field awaits it.
        db.execute(
            "INSERT OR IGNORE INTO field_states (card_id, field, state, origin, ref, at) "
            "SELECT card_id, field, ?, 'proposal', ref, at FROM proposals p "
            "WHERE status = 'pending' AND value != 'null' AND NOT EXISTS (SELECT 1 FROM fields f "
            "WHERE f.card_id = p.card_id AND f.field = p.field) ORDER BY id",
            (card_model.PENDING_CONFIRMATION,),
        )
        _fill_homes(db, units, reg, profiles or {})
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


def _library(value: Any) -> list[str]:
    if value is None:
        return list(homes.LIBRARY_ENTRIES)
    if not isinstance(value, list) or not value:
        raise BiStoreError("library_invalid", "library 必須是非空清單")
    for entry in value:
        problem = homes.entry_problem(entry)
        if problem:
            raise BiStoreError("library_invalid", f"library 項目「{entry}」{problem}")
    if len(set(value)) != len(value):
        raise BiStoreError("library_invalid", "library 項目重複")
    return list(value)


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
            built = self.local / BUILD_FILE
            built.unlink(missing_ok=True)  # back only if this build finishes
            mark = self._build_mark()
            with closing(sqlite3.connect(self.db_path, isolation_level=None)) as db:
                db.row_factory = sqlite3.Row
                units = self.repo.working_units()
                materialize(
                    db,
                    units,
                    self._entries(),
                    self.repo.conflicts(),
                    self._schema_of(units),
                    profile.load_all(self.repo, units),
                )
        from capabilities.bi_cards import search_index

        search_index.sync_quietly(BiStore(self.workspace, self.dataset))
        built.write_text(json.dumps(mark), encoding="utf-8")

    def _build_mark(self) -> dict[str, Any]:
        return {"inputs": self.repo.fingerprint(), "model": card_model.MODEL_VERSION}

    def _is_built(self) -> bool:
        """Whether `bi.sqlite` is what a rebuild would make now."""
        try:
            built = json.loads((self.local / BUILD_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return bool(self.db_path.is_file() and built == self._build_mark())

    def reads(self) -> dict[str, Any]:
        """What the Agent reads (decision 8): the published tag, or the pushed
        head of a vault never published (a published commit not applied here
        yet is read as the head until it arrives)."""
        record = self.repo.published()
        if record is not None and record["commit"] in self.repo.applied_ids():
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
            sources = folder / PUBLISHED_SOURCES
            if built == target and (folder / DB_FILE).is_file() and sources.is_file():
                return folder
            folder.mkdir(parents=True, exist_ok=True)
            commit = target["commit"]
            scratch = folder / f".{DB_FILE}.{uuid.uuid4().hex[:8]}.tmp"
            try:
                self._build_at(commit, scratch)
                repo_engine.replace_retrying(scratch, folder / DB_FILE)
            finally:
                scratch.unlink(missing_ok=True)
            # Which sources' Markdown this version holds, for the search index.
            sources.write_text(json.dumps(self._sources_at(commit)), encoding="utf-8")
            marker.write_text(json.dumps(target), encoding="utf-8")
            return folder

    def _sources_at(self, commit: str | None) -> dict[str, int]:
        """Source id to its newest Markdown revision as of `commit`."""
        units = self.repo.state_at(commit) if commit else {}
        return {
            str(value["id"]): max(int(item["rev"]) for item in value["markdown"])
            for key, value in units.items()
            if key.startswith(vault_sources.PREFIX) and value.get("markdown")
        }

    def _build_at(self, commit: str | None, path: Path) -> None:
        """A database at `path` as of `commit`, from its units."""
        units = self.repo.state_at(commit) if commit else {}
        entries = self._log_entries(until=commit) if commit else []
        with closing(sqlite3.connect(path, isolation_level=None)) as db:
            materialize(
                db,
                units,
                entries,
                [],
                self._schema_of(units),
                profile.load_all(self.repo, units),
            )

    def write_snapshot(self, tag: str, commit: str) -> dict[str, Any]:
        """`published/<tag>.sqlite` in the shared folder, written once (design §6.2),
        and its hash for the publish record. A second publish of the tag keeps the
        first. Nothing reads it yet: readers rebuild from the units, which stay the
        truth, so a failure here does not stop the publish."""
        relative = f"{SNAPSHOT_DIR}/{tag}.sqlite"
        target = self.folder / relative
        scratch = self.local / f".snapshot-{uuid.uuid4().hex[:8]}.tmp"
        partial = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            if not target.exists():
                self._build_at(commit, scratch)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(scratch, partial)
                if not target.exists():
                    repo_engine.replace_retrying(partial, target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            return {"snapshot": {"path": relative, "sha256": digest}}
        except (OSError, sqlite3.Error):
            return {"snapshot": None}
        finally:
            scratch.unlink(missing_ok=True)
            partial.unlink(missing_ok=True)

    def _manifest(self) -> dict[str, Any]:
        try:
            found = json.loads((self.folder / CARDS_MANIFEST).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return found if isinstance(found, dict) else {}

    def write_cards(self) -> dict[str, Any]:
        """`cards/<id>.md` of the version published now, whoever published it, so a
        slower publisher cannot put an older view back (design §6.1). Only pages whose
        hash differs from the manifest are written, and the manifest goes last. A
        failure leaves the publish in place: the view is behind until the next one."""
        started = time.monotonic()
        with self.lock:
            target = self.reads()
            if target["tag"] is None:
                return {"behind": False, "written": 0, "removed": 0, "unchanged": 0}
            try:
                folder = self.refresh_published()
                withdrawn = {
                    vault_sources.stable_id(sha) for sha in vault_sources.withdrawn_shas(self.repo)
                }
                with closing(sqlite3.connect(f"file:{folder / DB_FILE}?mode=ro", uri=True)) as db:
                    row = db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
                    pages = card_markdown.render_all(db, self._registry(str(row[0])), withdrawn)
                return self._write_pages(pages, target, started)
            except (OSError, sqlite3.Error, RepoError, BiStoreError) as failure:
                return {"behind": True, "problem": type(failure).__name__}

    def _write_pages(
        self, pages: Mapping[str, str], target: Mapping[str, Any], started: float
    ) -> dict[str, Any]:
        cards = self.folder / CARDS_DIR
        cards.mkdir(parents=True, exist_ok=True)
        manifest = self._manifest()
        known = manifest.get("hashes") if isinstance(manifest.get("hashes"), dict) else {}
        assert isinstance(known, dict)
        present = {p.name for p in cards.iterdir()}
        hashes: dict[str, str] = {}
        written = 0
        for card_id, text in pages.items():
            data = text.encode("utf-8")
            hashes[card_id] = hashlib.sha256(data).hexdigest()
            if known.get(card_id) == hashes[card_id] and f"{card_id}.md" in present:
                continue
            repo_engine._write_atomic(cards / f"{card_id}.md", data)
            written += 1
        gone = [card_id for card_id in known if card_id not in pages]
        for card_id in gone:
            (cards / f"{card_id}.md").unlink(missing_ok=True)
        if written or gone or manifest.get("commit") != target["commit"]:
            record = {
                "tag": target["tag"],
                "commit": target["commit"],
                "at": now(),
                "by": self.repo.author,
                "hashes": hashes,
            }
            repo_engine._write_atomic(
                self.folder / CARDS_MANIFEST,
                json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"),
            )
        return {
            "behind": False,
            "written": written,
            "removed": len(gone),
            "unchanged": len(pages) - written,
            "seconds": round(time.monotonic() - started, 2),
        }

    def cards_behind(self) -> bool:
        """Whether the pages in `cards/` are not the published version's."""
        target = self.reads()
        return target["tag"] is not None and self._manifest().get("commit") != target["commit"]

    def sync(self) -> dict[str, Any]:
        """Apply what the others pushed, and rebuild the local database only when
        what it is built from changed. `moved` says whether anything here or the
        version the feed shows did, so a caller can skip the work that follows."""
        with self.lock:
            self._require_folder()
            self._install_schemas()
            with _repo_errors():
                report = self.repo.sync()
                built = self._is_built()
                reads = self.reads()
            if report.get("applied") or not built:
                self.ensure_home_folders()
            if not built:
                vault_sources.sync_staging(self.repo, self.workspace, self.dataset)
                self.rebuild()
            state = self.local / STATE_FILE
            try:
                known = json.loads(state.read_text(encoding="utf-8")).get("reads")
            except (OSError, ValueError):
                known = None
            state.write_text(json.dumps({"at": now(), "reads": reads}), encoding="utf-8")
            # A first sync on this PC only records what it reads: nothing moved.
            return {**report, "moved": not built or (known is not None and known != reads)}

    def ensure_home_folders(self) -> None:
        """The folders of every pushed home a person created, in the shared folder. No file
        marks them: each PC makes them from the unit on push and sync, so nothing here can be
        taken for a source, skill or tool, and a folder lost in transfer comes back. Only an
        empty folder is at stake, so a refusal is not worth stopping a sync for."""
        for item in vault_skills.created_homes(self.repo.units()):
            for folder in homes.home_folders(item["home"]):
                try:
                    repo_engine.long_path(self.folder / folder).mkdir(parents=True, exist_ok=True)
                except OSError:
                    continue

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
                moved = changed.get(repo_engine.SCHEMA_UNIT)
                old = None
                if moved and before.get(repo_engine.SCHEMA_UNIT):
                    old = schema_merge.effective_ref(self.workspace, self.repo.working_units())
                    del changed[repo_engine.SCHEMA_UNIT]
                    moves = self._schema_units(str(moved))
                    if repo_engine.SCHEMA_UNIT not in moves:
                        # No version moved, and two PCs' additions must not meet on this list.
                        changed.pop("meta:schema_history", None)
                    changed.update(moves)
                self.repo.stage_many(dict(sorted(changed.items())))
                if changed.get(repo_engine.SCHEMA_UNIT):
                    self._stage_schema(str(changed[repo_engine.SCHEMA_UNIT]))
                if old and changed.get(repo_engine.SCHEMA_UNIT):
                    vault_skills.regenerate_classify(
                        self.repo, self._registry(old), self._registry()
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
        reg = self._schema_of(after)
        if reg is None:
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

    def _schema_units(self, target_ref: str) -> dict[str, Any]:
        """The units that move this vault to `target_ref`, a version just published on this
        PC. Additions become their own units and take no number. Anything more is a new
        version, numbered from its content so that two people's different versions are
        different refs and conflict as a unit, rather than one number with two contents."""
        target = catalog.resolve(self.workspace, target_ref)
        name = _schema_file_name(target.schema_id, target.version)
        if target.source != "installed" or (self.folder / "schemas" / name).is_file():
            return {repo_engine.SCHEMA_UNIT: target_ref}  # a version the vault already knows
        working = self.repo.working_units()
        old_ref = schema_merge.effective_ref(self.workspace, working)
        _, old = schema_versions.base_document(self.workspace, old_ref)
        _, new = schema_versions.base_document(self.workspace, target_ref)
        path = catalog.schema_path(self.workspace, target.schema_id, target.version)
        additions = schema_merge.changes_between(old, new)
        if additions is not None:
            path.unlink(missing_ok=True)  # never pushed, so it must not take the number
            schema_versions.renumbered(self.workspace, target_ref, None)
            return additions
        major, minor = catalog._version_tuple(target.version)[:2]  # noqa: SLF001
        content = repo_engine.canonical({k: v for k, v in new.items() if k != "version"})
        patch = int(hashlib.sha256(content.encode("utf-8")).hexdigest()[:5], 16)
        version = f"{major}.{minor}.{patch}"
        path.unlink(missing_ok=True)
        catalog.install(
            self.workspace,
            f"{version}.json",
            json.dumps({**new, "version": version}, ensure_ascii=False),
        )
        schema_versions.renumbered(self.workspace, target_ref, f"{target.schema_id}@{version}")
        absorbed = {k: None for k in schema_merge.stored_changes(working)}
        return {repo_engine.SCHEMA_UNIT: f"{target.schema_id}@{version}", **absorbed}

    def schema_conflicts(self) -> list[dict[str, Any]]:
        """Schema overlaps that landed with nobody to stop them, the same on every PC: a
        change that no longer fits its version, and a change that lost a race on one unit.
        A push stops at the first kind, and at the second before anything is written."""
        units = self.repo.working_units()
        found: list[dict[str, Any]] = [
            {
                "kind": "clash",
                "unit": item["unit"],
                "label": unit_label(units, item["unit"]),
                "reason": item["reason"],
                "value": units.get(item["unit"]),
            }
            for item in schema_merge.clashes(self.workspace, units)
        ]
        for item in self.repo.conflicts():
            unit = str(item["unit"])
            if not unit.startswith(schema_merge.PREFIX) and unit != repo_engine.SCHEMA_UNIT:
                continue
            decided = f"decision:{_schema_conflict_key(item)}"
            if decided in units or repo_engine.canonical(units.get(unit)) == repo_engine.canonical(
                item["value"]
            ):
                continue
            found.append(
                {
                    "kind": "race",
                    "unit": unit,
                    "label": unit_label(units, unit),
                    "reason": "兩個人同時改了這裡，先到的留下；要由人決定",
                    "value": item["value"],
                    "current": units.get(unit),
                }
            )
        return found

    def new_schema_clashes(self) -> list[str]:
        """What this PC's commits would clash with once on the head, in words."""
        head = {c["unit"] for c in schema_merge.clashes(self.workspace, self.repo.units())}
        units = self.repo.working_units()
        return [
            f"{unit_label(units, c['unit'])}：{c['reason']}"
            for c in schema_merge.clashes(self.workspace, units)
            if c["unit"] not in head
        ]

    def _schema_of(self, units: Mapping[str, Any]) -> Registry | None:
        """The schema these units are on; None when this PC has not got it."""
        try:
            return self._registry(schema_merge.effective_ref(self.workspace, units))
        except BiStoreError:
            return None

    def _registry(self, ref: str | None = None) -> Registry:
        """The schema `ref`, by default the working copy's."""
        if ref is None:
            ref = schema_merge.effective_ref(self.workspace, self.repo.working_units())
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
            "schema_conflicts": self.schema_conflicts() if reachable else [],
            "merges": [],
            "bad": state.get("bad") or [],
            "incomplete": [],
            "cards": cards,
            "last_sync": last,
            "cards_view_behind": self.cards_behind() if reachable else False,
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
) -> tuple[Vault, list[dict[str, str]], list[str]]:
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
    library = _library(given.get("library"))
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
    (repo.folder / homes.skills_dir("")).mkdir(parents=True, exist_ok=True)
    for home in (*(s["folder"] for s in segments), *(f"{homes.LIBRARY}/{e}" for e in library)):
        for folder in homes.home_folders(home):
            (repo.folder / folder).mkdir(parents=True, exist_ok=True)
    _register(
        workspace, {"id": vault_id, "path": str(repo.folder), "author": author, "joined": now()}
    )
    return Vault(workspace, vault_id), segments, library


def _stage_default_pack(vault: Vault, reg: Registry, given: Mapping[str, Any]) -> None:
    """A new vault's Dashboard: the built-in analyses its schema satisfies
    (design BI_ANALYSIS_DASHBOARD.md §4.2), unless `default_pack` is false."""
    if given.get("default_pack") is False:
        return
    from capabilities.bi_cards import packs

    packs.stage_pack(vault, reg, packs.default_pack())


def _segments_meta(segments: list[dict[str, str]]) -> str:
    return json.dumps(segments, ensure_ascii=False, sort_keys=True)


def _home_lists(segments: list[dict[str, str]], library: list[str]) -> dict[str, str]:
    """The units holding a new vault's applications and library entries."""
    return {
        vault_skills.SEGMENTS_UNIT: _segments_meta(segments),
        vault_skills.LIBRARY_UNIT: json.dumps(library, ensure_ascii=False),
    }


def create(workspace: Path, given: dict[str, Any], actor: str) -> dict[str, Any]:
    """A new vault folder under `path`, bound to `schema`, and this PC joined."""
    reg = catalog.resolve(workspace, str(given.get("schema") or ""))
    vault, segments, library = _new_vault(workspace, given, actor)
    with vault.lock, _repo_errors():
        vault.repo.stage(repo_engine.SCHEMA_UNIT, reg.ref)
        vault.repo.stage_many(_home_lists(segments, library))
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
    vault, segments, library = _new_vault(workspace, {"title": name, **given}, actor)
    with vault.lock, _repo_errors():
        units.update(_home_lists(segments, library))
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


@dataclass
class _Flight:
    done: threading.Event = field(default_factory=threading.Event)
    report: dict[str, Any] | None = None
    failure: BaseException | None = None


_FLIGHTS: dict[tuple[str, str], _Flight] = {}
_FLIGHTS_LOCK = threading.Lock()


def sync(workspace: Path, vault_id: str) -> dict[str, Any]:
    """Sync once at a time: a caller arriving during a sync of this vault, such as a
    second tab's page load, shares its answer instead of queueing behind it."""
    key = (str(workspace), vault_id)
    with _FLIGHTS_LOCK:
        flight = _FLIGHTS.get(key)
        leader = flight is None
        if flight is None:
            flight = _FLIGHTS[key] = _Flight()
    if not leader:
        flight.done.wait()
        if flight.failure is not None:
            raise flight.failure
        assert flight.report is not None
        return dict(flight.report)
    try:
        flight.report = Vault(workspace, vault_id).sync()
        return dict(flight.report)
    except BaseException as failure:
        flight.failure = failure
        raise
    finally:
        with _FLIGHTS_LOCK:
            del _FLIGHTS[key]
        flight.done.set()


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
    if kind == "state":
        return f"{card()} 的 {field} 狀態"
    if key.startswith(analyses.DASHBOARD_UNIT + ":"):
        return f"「{key[len(analyses.DASHBOARD_UNIT) + 1 :]}」的 Dashboard"
    if key.startswith(vault_skills.HOME_PREFIX):
        return f"領域「{key[len(vault_skills.HOME_PREFIX) :]}」"
    if kind == "meta":
        return {"domains": "領域設定", "dashboard": "Dashboard 的順序"}.get(rest, f"設定 {rest}")
    if key == repo_engine.SCHEMA_UNIT:
        return "schema 版本"
    if key.startswith(schema_merge.PREFIX):
        return schema_merge.describe(key)
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


def _card_homes(workspace: Path, vault_id: str) -> dict[str, list[str]]:
    """Each card's homes, from the working database; a card or a database not there yet
    simply has none, which the page counts as 其他."""
    found: dict[str, list[str]] = {}
    path = local_dir(workspace, vault_id) / "bi.sqlite"
    if not path.is_file():
        return found
    try:
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as db:
            for card_id, home in db.execute(
                "SELECT card_id, application FROM card_app_folders ORDER BY application"
            ):
                found.setdefault(card_id, []).append(home)
    except sqlite3.Error:
        return {}
    return found


def unit_homes(
    units: Mapping[str, Any], key: str, card_homes: Mapping[str, list[str]]
) -> list[str]:
    """The working domains a unit touches; none for what spans the vault."""
    kind, _, rest = key.partition(":")
    value = units.get(key)
    if kind in ("card", "field", "evidence", "state"):
        return list(card_homes.get(rest.partition(":")[0]) or [])
    if kind == "source" and isinstance(value, dict):
        home = homes.home_of(str(value.get("folder") or ""))
        return [home] if home else []
    if key.startswith(analyses.DASHBOARD_UNIT + ":"):
        return [key[len(analyses.DASHBOARD_UNIT) + 1 :]]
    if key.startswith(vault_skills.HOME_PREFIX):
        return [key[len(vault_skills.HOME_PREFIX) :]]
    if kind in ("skill", "tool"):
        home = rest.rpartition("/")[0]
        return [home] if home and not homes.home_problem(home) else []
    if kind == "profile":
        return [rest] if not homes.home_problem(rest) else []
    if key.startswith(vault_checks.QUESTION_PREFIX) and isinstance(value, dict):
        return [value["home"]] if value.get("home") else []
    if key.startswith(vault_checks.EXTRACT_PREFIX) and isinstance(value, dict):
        home = vault_checks.case_home(value)
        return [home] if home else []
    return []


def pending(workspace: Path, vault_id: str) -> dict[str, Any]:
    """What this PC has not pushed: uncommitted changes and local commits."""
    vault = _vault(workspace, vault_id)
    with vault.lock:
        # Against what this PC has committed: a card only committed here has its name, and
        # what a local commit added and the work removed is a change.
        head = vault.repo.working_units(pending=False)
        work = vault.repo._pending()
        units = {**head, **work["sets"]}
        shown = card_model.card_names_of(units)
        card_homes = _card_homes(workspace, vault_id)
        changes = [
            {
                "unit": k,
                "label": unit_label(units, k),
                "homes": unit_homes(units, k, card_homes),
                "before": card_model.render_links_within(head.get(k), shown),
                "after": card_model.render_links_within(v, shown),
            }
            for k, v in sorted(work["sets"].items())
            # Added and removed again before any commit: nothing has changed.
            if repo_engine.canonical(head.get(k)) != repo_engine.canonical(v)
        ]
        return {
            "uncommitted": changes,
            "files": sorted(work["files"]),
            "commits": vault.repo.local_commits(),
        }


def relation_ends(store: BiStore, item: Mapping[str, Any]) -> tuple[str, str] | None:
    """The two cards an inferred relation names; None unless each is a single
    card of the types its registered relation allows."""
    if store.vault_id is None:
        return None
    target = Vault(store.workspace, store.vault_id)
    reg = target._schema_of(target.repo.working_units())
    known = next(
        (r for r in (reg.relation_types if reg else ()) if r["name"] == item["type"]), None
    )
    if known is None or not store.exists:
        return None
    with closing(sqlite3.connect(store.path)) as db:
        db.row_factory = sqlite3.Row
        targets = _LinkTargets(db)
    start = targets.find(str(item["from"]), tuple(known["from"]))
    end = targets.find(str(item["to"]), tuple(known["to"]))
    return None if start is None or end is None else (start, end)


def relation_decided(store: BiStore, item: Mapping[str, Any]) -> bool:
    """Whether a person already decided the relation this inferred one means."""
    ends = relation_ends(store, item)
    if ends is None or store.vault_id is None:
        return False
    relation = card_model.relation_id(ends[0], str(item["type"]), ends[1])
    units = Vault(store.workspace, store.vault_id).repo.working_units()
    return f"{card_model.RELATION_PREFIX}{relation}" in units


def fill_domains(
    workspace: Path, vault_id: str, given: Mapping[str, Any], actor: str
) -> dict[str, Any]:
    """Give a card with no domain the domains of its applications, marked as inference.
    Without `confirm` it only says what it would do. A one-domain type with cards from
    several applications, or a card in none, is listed and left for a person."""
    vault = _vault(workspace, vault_id)
    store = BiStore(workspace, vault.dataset)
    reg = catalog.for_store(store)
    with closing(sqlite3.connect(store.path)) as db:
        cards = db.execute(
            "SELECT id, entity_type, canonical_key, name FROM cards c WHERE NOT EXISTS "
            "(SELECT 1 FROM fields f WHERE f.card_id = c.id AND f.field = 'domain')"
        ).fetchall()
        applications: dict[str, list[str]] = {}
        for card_id, home in db.execute("SELECT card_id, application FROM card_app_folders"):
            applications.setdefault(card_id, []).append(home)
    rows: list[tuple[PlannedRow, str, int | None]] = []
    left: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for card_id, kind, key, name in cards:
        definition = reg.type(kind).get("domain")
        if definition is None:
            continue
        domains = sorted(
            {
                found
                for home in applications.get(card_id, ())
                if (found := homes.domain_of_folder(reg.domains, homes.sources_dir(home)))
            }
        )
        if not domains or (len(domains) > 1 and not definition.is_list):
            left.append({"id": card_id, "name": name, "type": kind, "domains": domains})
            continue
        value, _problems = reg.normalize(definition, "；".join(domains))
        if value is None:
            left.append({"id": card_id, "name": name, "type": kind, "domains": domains})
            continue
        for found in domains:
            counts[found] = counts.get(found, 0) + 1
        card = store.card(card_id)
        version = None if card is None else int(card["version"])
        rows.append(
            (
                PlannedRow(
                    row=len(rows) + 1,
                    entity_type=kind,
                    canonical_key=key,
                    name=name,
                    values={"domain": value},
                    synthetic=False,
                    ref="application-default",
                    evidence={
                        "domain": [
                            {
                                "source_id": "",
                                "source_name": f"應用資料夾 {'、'.join(domains)}",
                                "locator": {"default": "application"},
                                "excerpt": "",
                                "basis": "inference",
                            }
                        ]
                    },
                ),
                card_id,
                version,
            )
        )
    plan = {"fill": len(rows), "by_domain": counts, "left": left}
    if given.get("confirm") is not True or not rows:
        return {**plan, "applied": False}
    text = f"依應用資料夾補上 {len(rows)} 張卡的 domain（推論，不是來源明寫）"
    with purpose(text):
        store.commit_run(
            f"home-domain-{uuid.uuid4().hex[:8]}", rows, filename="應用資料夾的 domain", actor=actor
        )
    return {**plan, "applied": True, "purpose": text}


def decide_relation(
    workspace: Path, vault_id: str, given: Mapping[str, Any], actor: str
) -> dict[str, Any]:
    """A person's decision on one relation, staged for their commit. A derived
    relation takes a status; any other needs a type the schema registers, between
    the types it allows; a confirmed AI-inferred one needs its evidence."""
    from_id, kind, to_id = (str(given.get(k) or "") for k in ("from", "type", "to"))
    status = str(given.get("status") or "")
    origin = str(given.get("origin") or "registered")
    if status not in ("confirmed", "rejected", "disputed", "pending"):
        raise BiStoreError("relation_status_invalid", "決定只能是確認、否決、有爭議或待確認")
    if origin not in ("ai_inferred", "registered"):
        raise BiStoreError("relation_origin_invalid", "來源只能是 AI 推論或登記")
    given_evidence = given.get("evidence") or []
    if not isinstance(given_evidence, list):
        raise BiStoreError("relation_evidence_invalid", "evidence 必須是清單")
    vault = _vault(workspace, vault_id)
    with vault.lock:
        units = vault.repo.working_units()
        ends = [units.get(f"card:{c}") for c in (from_id, to_id)]
        if not all(ends):
            raise BiStoreError("card_unknown", "關係的兩端都要是這個知識庫的卡片")
        relation = card_model.relation_id(from_id, kind, to_id)
        with closing(sqlite3.connect(vault.db_path)) as db:
            derived = db.execute(
                "SELECT 1 FROM relations WHERE relation_id = ? AND origin = ?",
                (relation, card_model.SCHEMA_FIELD),
            ).fetchone()
        if derived is None:
            reg = vault._schema_of(units)
            known = next(
                (r for r in (reg.relation_types if reg else ()) if r["name"] == kind), None
            )
            if known is None:
                raise BiStoreError("relation_type_unknown", f"schema 沒有登記關係「{kind}」")
            if ends[0]["type"] not in known["from"] or ends[1]["type"] not in known["to"]:  # type: ignore[index]
                raise BiStoreError(
                    "relation_type_mismatch",
                    f"關係「{kind}」只能從 {'/'.join(known['from'])} 到 {'/'.join(known['to'])}",
                )
            if origin == "ai_inferred" and status == "confirmed" and not given_evidence:
                raise BiStoreError("relation_evidence_required", "確認 AI 推論的關係要附依據")
        at = now()
        changes: dict[str, Any] = {}
        current = units.get(f"{card_model.RELATION_PREFIX}{relation}")
        # The same decision again only adds evidence, so two people adding
        # evidence to one relation do not conflict.
        if current is None or current["status"] != status:
            changes[f"{card_model.RELATION_PREFIX}{relation}"] = {
                "from": from_id,
                "type": kind,
                "to": to_id,
                "origin": card_model.SCHEMA_FIELD if derived else origin,
                "status": status,
                "scope": given.get("scope"),
                "note": given.get("note"),
                "by": actor,
                "at": at,
            }
        for item in given_evidence:
            if not isinstance(item, dict) or not item.get("reference_id"):
                raise BiStoreError("relation_evidence_invalid", "每筆依據都要有 reference_id")
            stance = str(item.get("stance") or card_model.SUPPORTS)
            if stance not in card_model.STANCES:
                raise BiStoreError("relation_evidence_invalid", f"立場「{stance}」不認得")
            basis = str(item.get("basis_card") or from_id)
            reference = str(item["reference_id"])
            link = card_model.evidence_link_id(relation, basis, reference)
            changes[f"{card_model.RELATION_EVIDENCE_PREFIX}{link}"] = {
                "relation": relation,
                "basis_card": basis,
                "reference_id": reference,
                "stance": stance,
                "by": actor,
                "at": at,
                **({"assessment": item["assessment"]} if item.get("assessment") else {}),
            }
        with _repo_errors():
            vault.repo.stage_many(changes)
        vault.rebuild()
    return {"relation_id": relation, "staged": sorted(changes)}


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
            vault.repo.sync()
            clashes = vault.new_schema_clashes()
            if clashes:
                return {"status": "blocked", "blocking": clashes, "notes": []}
            result = vault.repo.push()
            if result["status"] == "pushed":
                readme.write_readme(vault.repo)
                vault.ensure_home_folders()
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


def decide_schema_conflict(
    workspace: Path, vault_id: str, given: Mapping[str, Any]
) -> dict[str, Any]:
    """A person's decision on an entry of `schema_conflicts`, staged for their commit:
    `drop` a change, `keep` what stands, or `take` the change that lost."""
    vault = _vault(workspace, vault_id)
    unit, choice = str(given.get("unit") or ""), given.get("choice")
    if choice not in ("drop", "keep", "take"):
        raise BiStoreError("choice_invalid", "choice 必須是 drop、keep 或 take")
    with vault.lock, _repo_errors():
        entry = next((c for c in vault.schema_conflicts() if c["unit"] == unit), None)
        if entry is None:
            raise BiStoreError("schema_conflict_unknown", "這裡沒有這個 schema 衝突")
        if choice == "drop":
            if not unit.startswith(schema_merge.PREFIX):
                raise BiStoreError("choice_invalid", "schema 版本不能放棄，只能選一邊")
            vault.repo.stage(unit, None)
        else:
            if entry["kind"] != "race":
                raise BiStoreError("choice_invalid", "這個改動只能放棄")
            for item in vault.repo.conflicts():
                if str(item["unit"]) == unit:
                    key = _schema_conflict_key(item)
                    vault.repo.stage(f"decision:{key}", {"status": "decided", "reason": choice})
            if choice == "take":
                vault.repo.stage(unit, entry["value"])
                if unit == repo_engine.SCHEMA_UNIT:
                    vault._stage_schema(str(entry["value"]))
    vault.rebuild()
    return {"schema_conflicts": vault.schema_conflicts(), "status": vault.status()}


def resolve(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    vault = _vault(workspace, vault_id)
    unit, choice = str(given.get("unit") or ""), str(given.get("choice") or "")
    with _repo_errors():
        vault.repo.resolve(unit, choice, given.get("value"))
        if unit.startswith("field:") and choice in ("mine", "theirs"):
            # The citations go with the value chosen; the person can still choose otherwise.
            vault.repo.resolve(f"evidence:{unit.removeprefix('field:')}", choice)
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


def _summaries_missing(db: sqlite3.Connection, reg: Registry | None) -> dict[str, int]:
    """Cards with no summary, per type that has the field (`BI_CARD_MODEL.md` §3.6)."""
    if reg is None:
        return {}
    rows = db.execute(
        "SELECT entity_type, COUNT(*) FROM cards c WHERE NOT EXISTS (SELECT 1 FROM fields f "
        "WHERE f.card_id = c.id AND f.field = 'summary') GROUP BY entity_type ORDER BY entity_type"
    )
    return {
        name: int(count)
        for name, count in rows
        if name in reg.types and reg.types[name].get("summary") is not None
    }


def _publish_warnings(vault: Vault, folder: Path) -> dict[str, Any]:
    """What a publish tells and never blocks on: what profiles require and cards lack."""
    commit = vault.reads()["commit"]
    units = vault.repo.state_at(commit) if commit else {}
    found = profile.load_all(vault.repo, units) if commit else {}
    warnings: dict[str, Any] = {}
    with closing(sqlite3.connect(folder / DB_FILE)) as db:
        if found:
            warnings["profile_required_missing"] = profile.missing_required(db, found)
        missing = _summaries_missing(db, vault._schema_of(units))
    if missing:
        warnings["summary_missing"] = {"total": sum(missing.values()), "by_type": missing}
    return warnings


def publish(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Publish a tag. Only a person's confirm click calls this (design §7)."""
    if given.get("confirm") is not True:
        raise BiStoreError("confirm_required", "發佈要由人按確認")
    vault = _vault(workspace, vault_id)
    with _repo_errors():
        record = vault.repo.publish(str(given.get("tag") or ""), vault.write_snapshot)
        readme.write_readme(vault.repo)
    folder = vault.refresh_published()
    return {
        "published": record,
        **_publish_warnings(vault, folder),
        "cards": vault.write_cards(),
    }


def _profile_types(vault: Vault, folder: str, units: Mapping[str, Any]) -> list[str] | None:
    """The card types the profile of `folder`'s home uses; None without a profile."""
    if not folder:
        return None
    part = profile.rules_part(vault.repo, folder, units)
    return list((part.get("profile") or {}).get("types") or {}) or None


def _run_types(
    vault: Vault, units: Mapping[str, Any], reg: Registry, given: Mapping[str, Any]
) -> tuple[list[str], str, list[str] | None]:
    """(the card types a run with this extract skill produces, where they come from, the
    profile's types or None), as `ai_runs.run_types` decides them for its first folder."""
    from capabilities.bi_cards import ai_runs

    applies = list(given.get("applies_to") or [])
    used = _profile_types(vault, str(applies[0]) if applies else "", units)
    types, origin = ai_runs.run_types(reg, None, list(given.get("card_types") or []), used)
    return types, origin, used


def _run_types_view(
    vault: Vault, units: Mapping[str, Any], reg: Registry, skill: repo_skills.Skill
) -> dict[str, Any]:
    given = {"applies_to": list(skill.applies_to), "card_types": list(skill.card_types)}
    types, origin, _ = _run_types(vault, units, reg, given)
    return {"types": types, "from": origin}


def skill_run_types(
    workspace: Path, vault_id: str, given: Mapping[str, Any]
) -> tuple[list[str], str, list[str] | None]:
    """`_run_types` for a skill as given (a draft the skill AI checks, acceptance F17)."""
    vault = _vault(workspace, vault_id)
    return _run_types(vault, vault.repo.working_units(), vault._registry(), given)


def skills(workspace: Path, vault_id: str) -> dict[str, Any]:
    """The vault's current skills (working copy) with their text, and the
    source folders a skill may apply to (design §8). Each extract skill says the
    card types a run with it produces (`run_types`), and `profile_types` the types
    of each home with a profile, so the form can say it as the person types."""
    vault = _vault(workspace, vault_id)
    units = vault.repo.working_units()
    reg = vault._registry()
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
                    **(
                        {"run_types": _run_types_view(vault, units, reg, skill)}
                        if skill.role == "extract"
                        else {}
                    ),
                }
            )
    roots = [
        *vault.folder.glob(f"{homes.APPLICATIONS}/*/{homes.SOURCES}"),
        *vault.folder.glob(f"{homes.LIBRARY}/*/{homes.SOURCES}"),
    ]
    folders = sorted(
        {
            p.relative_to(vault.folder).as_posix()
            for root in (*roots, vault.folder / homes.SOURCES)
            for p in (root, *root.rglob("*"))
            if p.is_dir()
            and vault_sources.MARKDOWN_DIR not in p.relative_to(vault.folder).parts
            and p != vault.folder / homes.SOURCES
        }
    )
    return {
        "skills": found,
        "schema": str(units.get(repo_engine.SCHEMA_UNIT) or ""),
        "folders": ["sources", *folders],
        "homes": _working_domains(vault, units),
        "default_types": [t for t in extract.DEFAULT_TYPES],
        "profile_types": {
            key[len(card_model.PROFILE_PREFIX) :]: types
            for key in sorted(units)
            if key.startswith(card_model.PROFILE_PREFIX)
            and (
                types := _profile_types(
                    vault, homes.sources_dir(key[len(card_model.PROFILE_PREFIX) :]), units
                )
            )
        },
        "roles": ["classify", "extract"],
        "tools": vault_tools.current_tools(units),
    }


def create_home(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Stage a new application (`docs/phases/BI_PAGE_SIMPLE.md` §10). Uncommitted like any
    change; its folders exist in this PC's working copy now and in the shared one after push."""
    vault = _vault(workspace, vault_id)
    with vault.lock:
        units = vault.repo.working_units()
        item = vault_skills.new_home(given, units, vault._schema_of(units))
        key, value = vault_skills.home_unit(item)
        with _repo_errors():
            vault.repo.stage(key, value)
        for folder in homes.home_folders(item["home"]):
            repo_engine.long_path(vault.repo.work / "files" / folder).mkdir(
                parents=True, exist_ok=True
            )
        vault.rebuild()
        units = vault.repo.working_units()
        return {"home": item["home"], "homes": _working_domains(vault, units)}


def _working_domains(vault: Vault, units: Mapping[str, Any]) -> list[dict[str, Any]]:
    """What a person can work on (`docs/phases/BI_PAGE_SIMPLE.md` §9): the vault's homes and any
    other its sources are in, each with its folder and its schema domain. An empty folder makes
    no home: `library/skill-review` holds review copies and is not a place to work."""
    listed = {item["home"]: item["label"] for item in vault_skills.home_list(units)}
    source_folders = [
        str(value.get("folder") or "")
        for key, value in units.items()
        if key.startswith("source:") and isinstance(value, dict)
    ]
    for folder in source_folders:
        home = homes.home_of(folder)
        if home is not None:
            listed.setdefault(home, home)
    reg = vault._schema_of(units)
    domains = reg.domains if reg is not None else ()
    return [
        {
            "home": home,
            "label": label,
            "folder": homes.sources_dir(home),
            "domain": homes.domain_of_folder(domains, homes.sources_dir(home)),
        }
        for home, label in listed.items()
    ]


def save_skill(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Stage a new revision of a skill, bound to the vault's current schema
    (that is how a skill 「需要更新」 is updated); the person commits it."""
    vault = _vault(workspace, vault_id)
    with vault.lock, _repo_errors():
        skill = _checked_skill(vault, given)
        value = repo_skills.stage_skill(vault.repo, skill)
    return {"skill": {"name": skill.unit_name, **value}, "status": vault.status()}


def profiles(workspace: Path, vault_id: str) -> dict[str, Any]:
    """The vault's current profiles (working copy), and every home that may have one."""
    vault = _vault(workspace, vault_id)
    units = vault.repo.working_units()
    return {
        "profiles": profile.listed(vault.repo, units),
        "homes": vault_skills.home_list(units),
    }


def save_profile(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Stage a new revision of a home's profile; the person commits it."""
    vault = _vault(workspace, vault_id)
    home = str(given.get("home") or "")
    with vault.lock, _repo_errors():
        value = profile.stage(vault.repo, home, given.get("profile"), vault._registry())
    return {"profile": {"home": home, **value}, "status": vault.status()}


def save_tool(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Stage a new revision of a home's tool; the person commits it. Running it is
    `tool_runs`, after that person's approval on each PC."""
    vault = _vault(workspace, vault_id)
    with vault.lock, _repo_errors():
        value = vault_tools.stage_text(vault.repo, given)
    return {"tool": value, "status": vault.status()}


def checked_skill(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> repo_skills.Skill:
    """The skill `save_skill` would stage, checked the same way; nothing is
    written (an AI suggestion is checked with it before it is shown)."""
    vault = _vault(workspace, vault_id)
    with vault.lock, _repo_errors():
        return _checked_skill(vault, given)


def _checked_skill(vault: Vault, given: Mapping[str, Any]) -> repo_skills.Skill:
    units = vault.repo.working_units()
    # `<home>/<name>` is how the list names one; `home` chooses it for a new one.
    home, _, name = str(given.get("name") or "").strip().rpartition("/")
    home = home or str(given.get("home") or "").strip()
    if home and homes.home_problem(home):
        raise BiStoreError("skill_invalid", f"home「{home}」{homes.home_problem(home)}")
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
    unit_name = f"{home}/{name}" if home else name
    if repo_skills.skill_unit(unit_name) in units:
        extra = {
            k: v
            for k, v in repo_skills.read_skill(vault.repo, unit_name, units).extra.items()
            if k != "generated"
        }
    if home and not applies_to:  # a home's skill reads that home, not every source
        applies_to = [homes.sources_dir(home)]
    # Parsing the rendered file checks name, role, folders and text.
    parsed = repo_skills.parse_skill(
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
        ),
        layout=homes.LAYOUT,
    )
    return replace(parsed, home=home)


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
