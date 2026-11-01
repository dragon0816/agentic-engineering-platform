"""Move a dataset's old domain configuration into its schema, cards and skills (BI D3, D4).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3: the domain configuration
(`aep.bi.domains/v1`, kept in the dataset's `meta` under `domains`; in a vault
the unit `meta:domains`) is retired. Nothing reads it any more except this
migration, which splits it up and removes it (owner 2026-11-01: move as much as
possible automatically):

- the schema is upgraded to one that has `aliases` and `chain` (3.0.0, D1) when
  it lacks them and is a `bi.schema/v1.1` version;
- `enum_aliases` (value aliases) and `node_name_pattern` (the Node `name_pattern`)
  go into a new local schema version made from the current one;
- every `name_aliases` entry is written onto its card's `aliases` (a card is
  found by its name, loosely; an alias whose card is missing is listed, never
  invented);
- every Node card's `chain` is set from the old chain patterns and lists (chains
  the schema does not allow are listed);
- the domains' node lists: listed names without a Node card are listed (a Node
  card is the list now);
- the domains' extraction `notes` go into the vault's `<domain>-extract` skills,
  or, for a dataset only on this PC, into one `llm` ingest method;
- the configuration is removed (segments and technology areas are the schema's
  allowed values; areas it does not allow are listed).

In a vault this is one change commit (purpose 「把領域設定搬進 schema 與卡片」); a
dataset only on this PC is written directly. A dry run shows the change list and
a token; applying needs that token, so what the person confirmed is what is
written.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog, extract, methods, schema_versions, vault, vault_skills
from capabilities.bi_cards.schema import Registry, norm_key
from capabilities.bi_cards.store import BiStore, BiStoreError

PURPOSE = "把領域設定搬進 schema 與卡片"
TARGET = "bi.schema/v1.1"  # its newest version (3.0.0 or later)
NEEDED = (("Node", "chain"), ("Account", "aliases"))
META_KEY = "domains"
METHOD_NAME = "領域判讀規則（從領域設定搬來）"


# -- the old document, read for the migration only ------------------------------------------


def legacy(store: BiStore) -> dict[str, Any] | None:
    """The dataset's old configuration; None when it has none."""
    text = store.meta_value(META_KEY)
    if not text:
        return None
    try:
        document = json.loads(text)
    except ValueError:
        return None
    if not isinstance(document, dict) or not isinstance(document.get("domains"), list):
        return None
    return document


def has_legacy(store: BiStore) -> bool:
    return legacy(store) is not None


def _domains(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [d for d in document["domains"] if isinstance(d, dict)]


def chains_of(document: dict[str, Any], node_name: str) -> list[str]:
    """The chains a node belonged to: listed by name or matched by a chain's `node_pattern`."""
    found: list[str] = []
    for domain in _domains(document):
        for chain in domain.get("chains") or []:
            listed = any(norm_key(n) == norm_key(node_name) for n in chain.get("nodes") or [])
            pattern = chain.get("node_pattern")
            if (listed or (pattern and re.search(pattern, node_name))) and (
                chain["id"] not in found
            ):
                found.append(chain["id"])
    return found


def _notes(document: dict[str, Any]) -> str:
    """Every domain's notes, one line each (what an AI extraction used to add)."""
    return "\n".join(
        f"- {d.get('label') or d['id']}（{d['id']}）：{str(d['notes']).strip()}"
        for d in _domains(document)
        if str(d.get("notes") or "").strip()
    )


def _allowed(registry: Registry, field_name: str) -> set[str]:
    if field_name == "domain":
        return set(registry.domains)
    return {
        v
        for t in registry.types.values()
        if (f := t.get(field_name)) is not None and f.enum
        for v in f.enum
    }


# -- the plan -------------------------------------------------------------------------------


def _plan(workspace: Path, dataset: str) -> dict[str, Any]:
    store = BiStore(workspace, dataset)
    document = legacy(store)
    if document is None:
        raise BiStoreError("domains_missing", "這個資料集沒有領域設定，不需要搬")
    current = catalog.for_store(store)
    newest = catalog.resolve(workspace, TARGET)
    ready = all(current.types.get(t) and current.types[t].get(f) for t, f in NEEDED)
    upgrade = not ready and current.schema_id == newest.schema_id
    after = newest if upgrade else current
    by_name: dict[str, list[Any]] = {}
    for row in store.card_rows():
        by_name.setdefault(norm_key(row["name"]), []).append(row)
    everything = store.all_fields()
    aliases: dict[str, dict[str, Any]] = {}
    missing = []
    for alias, name in sorted((document.get("name_aliases") or {}).items()):
        rows = [r for r in by_name.get(norm_key(name), []) if after.types.get(r["entity_type"])
                and after.types[r["entity_type"]].get("aliases")]  # fmt: skip
        if not rows:
            missing.append({"alias": alias, "name": name})
            continue
        for row in rows:
            entry = aliases.setdefault(
                row["id"], {"card": row["name"], "type": row["entity_type"], "add": []}
            )
            have = (everything.get(row["id"], {}).get("aliases") or {}).get("value") or []
            if alias not in have and alias not in entry["add"]:
                entry["add"].append(alias)
    node = after.types.get("Node")
    chain_field = node.get("chain") if node is not None else None
    allowed = set(chain_field.enum or ()) if chain_field is not None else set()
    chains: list[dict[str, Any]] = []
    dropped: set[str] = set()
    for row in store.card_rows():
        if row["entity_type"] != "Node":
            continue
        found = sorted(set(chains_of(document, str(row["name"]).removeprefix("SAMPLE-"))))
        kept = [c for c in found if c in allowed]
        dropped.update(c for c in found if c not in allowed)
        have = (everything.get(row["id"], {}).get("chain") or {}).get("value") or []
        if kept and sorted(have) != kept:
            chains.append({"card_id": row["id"], "node": row["name"], "chain": kept})
    area_field = next(
        (t.get("tech_areas") for t in after.types.values() if t.get("tech_areas")), None
    )
    known_areas = set(area_field.enum or ()) if area_field is not None else set()
    # Value aliases and the node name rule: into a new local schema version.
    enum_adds: dict[str, dict[str, str]] = {}
    enum_dropped = []
    for field_name, table in sorted((document.get("enum_aliases") or {}).items()):
        values = _allowed(after, field_name)
        have = after.enum_aliases.get(field_name, {})
        for alias, value in sorted((table or {}).items()):
            if value not in values:
                enum_dropped.append({"field": field_name, "alias": alias, "value": value})
            elif have.get(alias) != value:
                enum_adds.setdefault(field_name, {})[alias] = value
    pattern = str(document.get("node_name_pattern") or "")
    name_pattern = (
        pattern if pattern and node is not None and node.name_pattern != pattern else None
    )
    listed = {n for d in _domains(document) for n in d.get("nodes") or []} | {
        n for d in _domains(document) for c in d.get("chains") or [] for n in c.get("nodes") or []
    }
    nodes = {norm_key(r["name"]) for r in store.card_rows() if r["entity_type"] == "Node"}
    notes = [
        {"domain": d["id"], "label": d.get("label") or d["id"]}
        for d in _domains(document)
        if str(d.get("notes") or "").strip()
    ]
    plan = {
        "dataset": dataset,
        "vault": store.vault_id,
        "writes": "commit" if store.vault_id is not None else "direct",
        "schema": {"from": current.ref, "to": newest.ref} if upgrade else None,
        "schema_adds": {"enum_aliases": enum_adds, "name_pattern": name_pattern}
        if enum_adds or name_pattern
        else None,
        "aliases": [{"card_id": k, **v} for k, v in aliases.items() if v["add"]],
        "missing": missing,
        "chains": chains,
        "dropped_chains": sorted(dropped),
        "unknown_areas": [
            a["id"] for a in document.get("areas") or [] if a.get("id") not in known_areas
        ],
        "enum_aliases_dropped": enum_dropped,
        "missing_nodes": sorted(n for n in listed if norm_key(n) not in nodes),
        "notes": notes,
        "notes_to": ("skills" if store.vault_id is not None else "method") if notes else None,
        "removes": vault_skills.DOMAINS_UNIT,
        "purpose": PURPOSE,
    }
    marker = f"{store.change_marker()}|{plan}"
    plan["token"] = hashlib.sha256(marker.encode("utf-8")).hexdigest()[:24]
    return plan


# -- applying -------------------------------------------------------------------------------


def _upgrade(workspace: Path, dataset: str, to: str, actor: str) -> None:
    preview = schema_versions.upgrade_preview(workspace, dataset, to)
    schema_versions.upgrade_apply(workspace, dataset, to, preview["preview_token"], actor)


def _local_version(workspace: Path, dataset: str, adds: dict[str, Any], actor: str) -> str:
    """A new local schema version with the value aliases and the Node name rule."""
    base = catalog.for_store(BiStore(workspace, dataset)).ref
    made = schema_versions.create_draft(workspace, base, PURPOSE, actor)
    document = dict(made["document"])
    merged = {k: dict(v) for k, v in (document.get("enum_aliases") or {}).items()}
    for field_name, table in adds["enum_aliases"].items():
        merged.setdefault(field_name, {}).update(table)
    document["enum_aliases"] = merged
    if adds["name_pattern"]:
        document["types"] = [
            {**t, "name_pattern": adds["name_pattern"]} if t["name"] == "Node" else t
            for t in document["types"]
        ]
    draft_id = made["draft"]["id"]
    saved = schema_versions.save_revision(workspace, draft_id, document=document, json_text=None,
                                          note=PURPOSE, source="edit", actor=actor)  # fmt: skip
    if saved["errors"]:
        raise BiStoreError("schema_invalid", saved["errors"][0]["message"])
    return str(schema_versions.publish(workspace, draft_id, None, actor)["ref"])


def migrate_domains(
    workspace: Path, dataset: str, given: dict[str, Any], actor: str
) -> dict[str, Any]:
    """The dry run (no `apply`), or the migration (`apply` with its token)."""
    plan = _plan(workspace, dataset)
    if given.get("apply") is not True:
        return {"dry_run": True, **plan}
    if given.get("token") != plan["token"]:
        raise BiStoreError("preview_stale", "資料集在預覽後有變動，請重新預覽")
    target = vault._vault(workspace, plan["vault"]) if plan["vault"] is not None else None
    BiStore(workspace, dataset).refuse_write()
    scope = vault.purpose(PURPOSE) if target is not None else contextlib.nullcontext()
    record = None
    with scope:
        if plan["schema"] is not None:
            _upgrade(workspace, dataset, plan["schema"]["to"], actor)
        if plan["schema_adds"] is not None:
            ref = _local_version(workspace, dataset, plan["schema_adds"], actor)
            _upgrade(workspace, dataset, ref, actor)
        store = BiStore(workspace, dataset)
        for item in plan["aliases"]:
            card = store.card(item["card_id"])
            if card is None:
                continue
            have = (store.fields(item["card_id"]).get("aliases") or {}).get("value") or []
            store.set_field(item["card_id"], "aliases", [*have, *item["add"]],
                            base_version=int(card["version"]), actor=actor,
                            reason=PURPOSE)  # fmt: skip
        for item in plan["chains"]:
            card = store.card(item["card_id"])
            if card is not None:
                store.set_field(item["card_id"], "chain", item["chain"],
                                base_version=int(card["version"]), actor=actor,
                                reason=PURPOSE)  # fmt: skip
        if target is not None:
            with target.lock, vault._repo_errors():
                vault_skills.move_notes(target.repo, catalog.for_store(store))
                target.repo.stage(vault_skills.DOMAINS_UNIT, None)
                record = target.repo.commit(PURPOSE)
        else:
            text = store.meta_value(META_KEY)
            document = legacy(store)
            notes = _notes(document) if document is not None else ""
            if notes:
                rules = f"{extract.DEFAULT_INSTRUCTIONS}\n\n各領域的判讀規則：\n{notes}"
                body = {"name": METHOD_NAME, "mode": "llm", "instructions": rules,
                        "description": PURPOSE}  # fmt: skip
                methods.create(workspace, dataset, body, actor)
            if text is not None:
                store.delete_meta_value(META_KEY, base=text)
    if target is not None:
        target.rebuild()
    return {"dry_run": False, **plan, "commit": record}
