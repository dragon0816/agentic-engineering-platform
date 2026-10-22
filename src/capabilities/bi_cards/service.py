"""Reading BI cards and loading the shipped demo set.

Only committed card fields are searchable: previews (raw extracts) live in
memory and proposals are never matched by a query (Case A §4.7 item 6). A
card is trusted only when a person set `confidence: verified` and the card
is not synthetic (DQ-1); every shipped demo card is synthetic.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from capabilities.bi_cards import importer
from capabilities.bi_cards.catalog import for_store
from capabilities.bi_cards.schema import BI_PREFIX, Registry, TypeDef, registry
from capabilities.bi_cards.store import BiStore, datasets

#: The robotics demo (owner 2026-10-21): every type, loaded so links resolve.
DEMO_FILES = (
    ("Node", "nodes_robotics.csv"),
    ("Technology", "technology_robotics.csv"),
    ("Trend", "trend_robotics.csv"),
    ("Competitor", "competitors_robotics.csv"),
    ("Ecosystem", "ecosystem_robotics.csv"),
    ("Account", "accounts_core_robotics.csv"),
    ("Application", "application_robotics.csv"),
    ("CustomerProduct", "customer_products_robotics.csv"),
    ("TestSolution", "test_solutions_robotics.csv"),
    ("Opportunity", "opportunities_robotics.csv"),
    ("Signal", "signals_robotics.csv"),
    ("Concept", "concepts_robotics.csv"),
)
DEMO_ACTOR = "demo-fixture"


def demo_text(name: str) -> str:
    return (resources.files("capabilities.bi_cards") / "demo" / name).read_text(
        encoding="utf-8-sig"
    )


def load_demo(store: BiStore) -> dict[str, int]:
    """Import the demo CSVs in dependency order; idempotent."""
    totals = {"created": 0, "updated": 0, "unchanged": 0}
    # Every demo key first, so a link to a later file is not reported missing.
    keys: dict[str, set[str]] = {}
    for entity_type, name in DEMO_FILES:
        prepared = importer.preview(
            store,
            entity_type=entity_type,
            filename=f"demo/{name}",
            csv_text=demo_text(name),
            kind="fixture",
        )
        keys.setdefault(entity_type, set()).update(
            p.canonical_key for p in prepared.planned.values()
        )
    for entity_type, name in DEMO_FILES:
        prepared = importer.preview(
            store,
            entity_type=entity_type,
            filename=f"demo/{name}",
            csv_text=demo_text(name),
            kind="fixture",
            extra_keys=keys,
        )
        result = importer.apply(store, prepared, None, actor=DEMO_ACTOR)
        totals["created"] += result.created
        totals["updated"] += result.updated
        totals["unchanged"] += result.unchanged
    return totals


def dataset_list(workspace: Path) -> list[dict[str, Any]]:
    found = []
    for name in datasets(workspace):
        store = BiStore(workspace, name)
        schema = store.schema_ref()
        found.append(
            {
                "name": name,
                "cards": len(store.card_rows()),
                "updated": store.last_updated(),
                "schema": schema,
                "dashboard": schema.startswith(BI_PREFIX),
                "subscribed": False,
                "read_only": False,
            }
        )
    # Datasets subscribed from the Shared Platform: read only, after the local ones.
    from capabilities.bi_cards import subscriptions

    for item in subscriptions.listing(workspace):
        found.append({**item, "dashboard": str(item["schema"]).startswith(BI_PREFIX)})
    return found


def schema_api(reg: Registry | None = None) -> dict[str, Any]:
    reg = reg or registry()
    return {
        "schema_id": reg.schema_id,
        "version": reg.version,
        "ref": reg.ref,
        "title": reg.title,
        "bi": reg.is_bi,
        "domains": list(reg.domains),
        "types": [
            {
                "name": t.name,
                "label": t.label,
                "fields": [
                    {
                        "name": f.name,
                        "label": f.label,
                        "type": f.kind,
                        "class": f.klass,
                        "enum": list(f.enum) if f.enum else None,
                        "link_to": f.link_to[0] if f.link_to else None,
                        "list": f.is_list,
                    }
                    for f in t.fields
                ],
            }
            for t in reg.types.values()
        ],
    }


def _value(fields: dict[str, dict[str, Any]], name: str) -> Any:
    item = fields.get(name)
    return None if item is None else item["value"]


def trusted(card: Any, fields: dict[str, dict[str, Any]]) -> bool:
    confidence = fields.get("confidence")
    return bool(
        not card["synthetic"]
        and confidence is not None
        and confidence["value"] == "verified"
        and confidence["kind"] == "human"
    )


def card_summary(card: Any, fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    domain = _value(fields, "domain")
    return {
        "id": card["id"],
        "entity_type": card["entity_type"],
        "canonical_key": card["canonical_key"],
        "name": card["name"],
        "review_status": "verified" if trusted(card, fields) else "draft",
        "synthetic": bool(card["synthetic"]),
        "domain": domain,
        "updated": card["updated"],
        "fields": len(fields),
    }


def _in_domain(fields: dict[str, dict[str, Any]], domain: str, reg: Registry) -> bool:
    value = _value(fields, "domain")
    if value is None and reg.is_bi:
        value = "wireless"  # v4: no domain = wireless
    values = value if isinstance(value, list) else [value]
    return domain.lower() in {str(v).lower() for v in values if v is not None}


def _matches(card: Any, fields: dict[str, dict[str, Any]], text: str) -> bool:
    needle = text.lower()
    if needle in card["name"].lower() or needle in card["canonical_key"].lower():
        return True
    for item in fields.values():
        value = item["value"]
        for part in value if isinstance(value, list) else [value]:
            if needle in str(part).lower():
                return True
    return False


def search(
    store: BiStore,
    *,
    entity_type: str | None = None,
    text: str | None = None,
    domain: str | None = None,
    field: str | None = None,
    value: str | None = None,
) -> list[tuple[Any, dict[str, dict[str, Any]]]]:
    reg = for_store(store)
    if not reg.domains:
        domain = None  # a schema without domains has nothing to filter by
    everything = store.all_fields()
    found = []
    for card in store.card_rows():
        if entity_type and card["entity_type"].lower() != entity_type.lower():
            continue
        fields = everything.get(card["id"], {})
        if domain and not _in_domain(fields, domain, reg):
            continue
        if text and not _matches(card, fields, text):
            continue
        if field:
            current = _value(fields, field)
            parts = current if isinstance(current, list) else [current]
            if current is None or (
                value and not any(value.lower() in str(p).lower() for p in parts)
            ):
                continue
        found.append((card, fields))
    return found


def _type_of(reg: Registry, name: str) -> TypeDef | None:
    try:
        return reg.type(name)
    except KeyError:
        return None


def links(store: BiStore, card: Any, fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    reg = for_store(store)
    entity = _type_of(reg, card["entity_type"])
    if entity is None:
        return []
    index: dict[tuple[str, str], str] = {
        (c["entity_type"], c["canonical_key"]): c["id"] for c in store.card_rows()
    }
    by_key: dict[str, str] = {}
    for (_type_name, key), card_id in index.items():
        by_key.setdefault(key, card_id)
    result = []
    for item in entity.fields:
        if not item.is_link or item.name not in fields:
            continue
        value = fields[item.name]["value"]
        for target in value if isinstance(value, list) else [value]:
            target_id = (
                next((index[(t, target)] for t in item.link_to if (t, target) in index), None)
                if item.link_to
                else by_key.get(target)
            )
            result.append(
                {
                    "field": item.name,
                    "target_id": target_id,
                    "target_key": target,
                    "missing": target_id is None,
                }
            )
    return result


def card_detail(store: BiStore, card_id: str) -> dict[str, Any] | None:
    card = store.card(card_id)
    if card is None:
        return None
    fields = store.fields(card_id)
    counts = store.history_counts(card_id)
    entity = _type_of(for_store(store), card["entity_type"])
    order = [f.name for f in entity.fields] if entity is not None else []
    shown = []
    for name in sorted(fields, key=lambda n: order.index(n) if n in order else len(order)):
        definition = entity.get(name) if entity is not None else None
        item = fields[name]
        shown.append(
            {
                "field": name,
                "label": definition.label if definition else name,
                "value": item["value"],
                "class": definition.klass if definition else "sourced",
                "source": {
                    "kind": item["kind"],
                    "ref": item["ref"],
                    "at": item["at"],
                    "by": item["by"],
                },
                "history": counts.get(name, 0),
            }
        )
    summary = card_summary(card, fields)
    return {
        "card": {**summary, "version": int(card["version"])},
        "fields": shown,
        "links": links(store, card, fields),
        "proposals": store.proposals(card_id),
    }


def query_cards(
    store: BiStore,
    *,
    entity_type: str | None,
    text: str | None,
    domain: str | None,
    field: str | None,
    value: str | None,
    follow_links: bool,
    limit: int,
) -> dict[str, Any]:
    """The chat capability's answer: cards with per-field source evidence."""
    found = search(
        store, entity_type=entity_type, text=text, domain=domain, field=field, value=value
    )
    cards = []
    for card, fields in found[:limit]:
        entry = {
            "card": f"{card['entity_type']}:{card['canonical_key']}",
            "card_id": card["id"],
            "entity_type": card["entity_type"],
            "name": card["name"],
            "trusted": trusted(card, fields),
            "synthetic": bool(card["synthetic"]),
            "fields": {
                name: {
                    "value": item["value"],
                    "source": f"{item['kind']}:{item['ref']}",
                }
                for name, item in fields.items()
                if name != "body"
            },
        }
        if follow_links:
            entry["links"] = [
                {**link, "card": None if link["missing"] else link["target_key"]}
                for link in links(store, card, fields)
            ]
        cards.append(entry)
    return {
        "dataset": store.dataset,
        "total": len(found),
        "cards": cards,
        "scope_note": f"以上只來自資料集「{store.dataset}」的卡片；沒有找到的，只能說"
        f"「在這份資料集中沒有」。",
    }
