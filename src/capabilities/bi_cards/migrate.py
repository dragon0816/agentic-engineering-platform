"""Move a vault's domain configuration into its schema and cards (BI D3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3: the domain configuration
(`aep.bi.domains/v1`, the unit `meta:domains`) is split up and removed, in one
change commit (purpose 「把領域設定搬進 schema 與卡片」):

- the schema is upgraded to one that has `aliases` and `chain` (3.0.0, D1);
- every `name_aliases` entry is written onto its card's `aliases` (a card is
  found by its name, compared loosely; an alias whose card is missing is listed
  in the report, never invented);
- every Node card's `chain` is set from the old chain patterns and lists
  (chains the schema does not allow are listed);
- `meta:domains` is removed (segments and technology areas are the schema's
  allowed values now; areas it does not allow are listed).

A dry run shows the change list and a token; applying needs that token, so what
the person confirmed is what is written.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog, domains, schema_versions, vault, vault_skills
from capabilities.bi_cards.schema import norm_key
from capabilities.bi_cards.store import BiStore, BiStoreError

PURPOSE = "把領域設定搬進 schema 與卡片"
TARGET = "bi.schema/v1.1"  # its newest version (3.0.0 or later)
NEEDED = (("Node", "chain"), ("Account", "aliases"))


def _plan(workspace: Path, vault_id: str) -> dict[str, Any]:
    target = vault.Vault(workspace, vault_id)
    store = BiStore(workspace, target.dataset)
    config = domains.read(store)
    if config is None:
        raise BiStoreError("domains_missing", "這個知識庫沒有領域設定，不需要搬")
    current = catalog.for_store(store)
    newest = catalog.resolve(workspace, TARGET)
    ready = all(current.types.get(t) and current.types[t].get(f) for t, f in NEEDED)
    after = current if ready else newest
    by_name: dict[str, list[Any]] = {}
    for row in store.card_rows():
        by_name.setdefault(norm_key(row["name"]), []).append(row)
    everything = store.all_fields()
    aliases: dict[str, dict[str, Any]] = {}
    missing = []
    for alias, name in sorted((config.document.get("name_aliases") or {}).items()):
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
        found = sorted(
            {
                code
                for d in config.document["domains"]
                for code in config.chains_of(str(row["name"]).removeprefix("SAMPLE-"), d["id"])
            }
        )
        kept = [c for c in found if c in allowed]
        dropped.update(c for c in found if c not in allowed)
        have = (everything.get(row["id"], {}).get("chain") or {}).get("value") or []
        if kept and sorted(have) != kept:
            chains.append({"card_id": row["id"], "node": row["name"], "chain": kept})
    area_field = next(
        (t.get("tech_areas") for t in after.types.values() if t.get("tech_areas")), None
    )
    known_areas = set(area_field.enum or ()) if area_field is not None else set()
    plan = {
        "vault": vault_id,
        "schema": None if ready else {"from": current.ref, "to": newest.ref},
        "aliases": [{"card_id": k, **v} for k, v in aliases.items() if v["add"]],
        "missing": missing,
        "chains": chains,
        "dropped_chains": sorted(dropped),
        "unknown_areas": [a["id"] for a in config.document["areas"] if a["id"] not in known_areas],
        "removes": vault_skills.DOMAINS_UNIT,
        "purpose": PURPOSE,
    }
    marker = f"{store.change_marker()}|{plan}"
    plan["token"] = hashlib.sha256(marker.encode("utf-8")).hexdigest()[:24]
    return plan


def migrate_domains(
    workspace: Path, vault_id: str, given: dict[str, Any], actor: str
) -> dict[str, Any]:
    """The dry run (no `apply`), or the migration as one commit (`apply` with its token)."""
    plan = _plan(workspace, vault_id)
    if given.get("apply") is not True:
        return {"dry_run": True, **plan}
    if given.get("token") != plan["token"]:
        raise BiStoreError("preview_stale", "知識庫在預覽後有變動，請重新預覽")
    target = vault._vault(workspace, vault_id)
    dataset = target.dataset
    with vault.purpose(PURPOSE):
        if plan["schema"] is not None:
            preview = schema_versions.upgrade_preview(workspace, dataset, plan["schema"]["to"])
            schema_versions.upgrade_apply(
                workspace, dataset, plan["schema"]["to"], preview["preview_token"], actor
            )
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
        with target.lock, vault._repo_errors():
            target.repo.stage(vault_skills.DOMAINS_UNIT, None)
            record = target.repo.commit(PURPOSE)
    target.rebuild()
    return {"dry_run": False, **plan, "commit": record}
