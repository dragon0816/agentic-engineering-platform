"""Reading BI cards and loading the shipped demo set.

Only committed card fields are searchable: previews (raw extracts) live in
memory and proposals are never matched by a query (Case A §4.7 item 6). A
card is trusted only when a person set `confidence: verified` and the card
is not synthetic (DQ-1); every shipped demo card is synthetic.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Sequence
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
#: How far `bi__query` walks the relations, and how many cards it brings back.
MAX_HOPS = 3
MAX_RELATED = 30
#: A card's direct relations listed on it, at most.
MAX_DIRECT = 20
#: How far a relation's status lets the answer state it, surest first. A field on a
#: card holds a derived one; a person confirmed the others that count as fact.
CLAIMS = ("fact", "inferred", "pending", "disputed")
_STATED_BY_STATUS = {
    "confirmed": "fact",
    "unreviewed": "fact",
    "inferred": "inferred",
    "pending": "pending",
    "disputed": "disputed",
}
RELATED_RULE = (
    "related 是沿關係走到的卡片，path 是怎麼走到的。claim 是 fact 才能當事實說；"
    "inferred 要說是推論，pending 要說待確認，disputed 要說有爭議。"
)


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


def current_fields(
    reg: Registry, entity_type: str, fields: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """The values the schema has now: a field removed by a schema upgrade
    keeps its value but is not searched (BI ingest §5.3)."""
    entity = reg.types.get(entity_type)
    if entity is None:
        return fields
    return {name: item for name, item in fields.items() if entity.get(name) is not None}


def _in_domain(fields: dict[str, dict[str, Any]], domain: str, reg: Registry) -> bool:
    value = _value(fields, "domain")
    if value is None and reg.is_bi:
        value = "wireless"  # v4: no domain = wireless
    values = value if isinstance(value, list) else [value]
    return domain.lower() in {str(v).lower() for v in values if v is not None}


#: A text of at least this many words, none matching in full, shows the cards with most of them.
MIN_CLOSEST_WORDS = 2


def _words_found(card: Any, fields: dict[str, dict[str, Any]], words: list[str]) -> int:
    """How many of `words` stand somewhere on the card, each in any of its fields."""
    held = [card["name"].lower(), card["canonical_key"].lower()]
    for item in fields.values():
        value = item["value"]
        held.extend(str(part).lower() for part in (value if isinstance(value, list) else [value]))
    return sum(1 for word in words if any(word in part for part in held))


def _matches(card: Any, fields: dict[str, dict[str, Any]], text: str) -> bool:
    """Every word of `text` on the card. A question's words rarely stand in one field."""
    words = text.lower().split()
    return _words_found(card, fields, words) == len(words)


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
        fields = current_fields(reg, card["entity_type"], everything.get(card["id"], {}))
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


def _reviewable(store: BiStore, relation: dict[str, Any]) -> dict[str, Any]:
    return {**relation, "references": store.relation_references(relation["relation_id"])}


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
                # Kept from before a schema upgrade; shown, not editable.
                "retired": entity is not None and definition is None,
            }
        )
    summary = card_summary(card, fields)
    return {
        "card": {**summary, "version": int(card["version"])},
        "fields": shown,
        "links": links(store, card, fields),
        "relations": [_reviewable(store, r) for r in store.relations(card_id)],
        "rejected_relations": [
            _reviewable(store, r) for r in store.relations(card_id, rejected=True)
        ],
        "field_states": store.field_states(card_id),
        "proposals": store.proposals(card_id),
        "evidence": store.evidence(card_id),
    }


def _claim(status: str) -> str:
    return _STATED_BY_STATUS.get(status, "inferred")


def _weakest(claims: Iterable[str]) -> str:
    return max(claims, key=CLAIMS.index, default="fact")


def _step(relation: dict[str, Any]) -> dict[str, Any]:
    return {
        "relation_id": relation["relation_id"],
        "type": relation["type"],
        "direction": relation["direction"],
        "status": relation["status"],
        "origin": relation["origin"],
        "claim": _claim(str(relation["status"])),
        "to_name": relation["other_name"],
        "to_type": relation["other_type"],
    }


def walk_relations(
    store: BiStore, seeds: Sequence[str], *, hops: int, max_nodes: int = MAX_RELATED
) -> dict[str, Any]:
    """The cards `hops` steps from `seeds` over the relations, both ways, breadth
    first: each once by a shortest path, no seed among them, so a cycle ends. A
    rejected relation is not walked (`BiStore.relations`). `truncated` when the
    node limit left cards out."""
    paths: dict[str, list[dict[str, Any]]] = {seed: [] for seed in seeds}
    origin = {seed: seed for seed in seeds}
    reached: list[dict[str, Any]] = []
    frontier = list(dict.fromkeys(seeds))
    truncated = False
    for depth in range(1, hops + 1):
        following: list[str] = []
        for card_id in frontier:
            between: dict[str, list[dict[str, Any]]] = {}
            for relation in store.relations(card_id):
                other = str(relation["other_id"])
                if other not in paths:  # also a relation of a card to itself
                    between.setdefault(other, []).append(relation)
            for other, relations in between.items():
                if len(reached) >= max_nodes:
                    truncated = True
                    break
                # The surest relation carries the path; none between the two is lost.
                first, *rest = sorted(
                    relations, key=lambda r: CLAIMS.index(_claim(str(r["status"])))
                )
                step = _step(first)
                if rest:
                    step["also"] = [_step(r) for r in rest]
                paths[other] = [*paths[card_id], step]
                origin[other] = origin[card_id]
                reached.append(
                    {
                        "card_id": other,
                        "name": first["other_name"],
                        "hops": depth,
                        "from_id": origin[other],
                        "path": paths[other],
                        "claim": _weakest(s["claim"] for s in paths[other]),
                    }
                )
                following.append(other)
        frontier = following
    return {"reached": reached, "truncated": truncated}


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
    hops: int = 0,
    approved: Collection[str] | None = None,
) -> dict[str, Any]:
    """The chat capability's answer: cards with per-field source evidence, and
    with `hops` the cards their relations reach, each with its path."""
    found = search(
        store, entity_type=entity_type, text=text, domain=domain, field=field, value=value
    )
    words = (text or "").lower().split()
    closest = False
    if not found and len(words) >= MIN_CLOSEST_WORDS:
        # Question words such as 營收 are often on no card: say so, and show the nearest.
        scored = [
            (_words_found(card, fields, words), card, fields)
            for card, fields in search(
                store, entity_type=entity_type, domain=domain, field=field, value=value
            )
        ]
        near = [item for item in scored if item[0] >= MIN_CLOSEST_WORDS]
        near.sort(key=lambda item: -item[0])
        found = [(card, fields) for _, card, fields in near]
        closest = bool(found)
    cards = []
    classes: dict[str, set[str]] = {}
    if words and approved:
        from capabilities.bi_cards.staging import Staging

        for source_id, name, classification in Staging(
            store.workspace, store.dataset
        ).source_classes():
            classes[source_id] = {classification}
            classes.setdefault("name:" + name, set()).add(classification)
    for card, fields in found[:limit]:
        entry = _card_entry(store, card, fields)
        snippet = _body_snippet(store, card, fields, words, approved, classes)
        if snippet is not None:
            entry["body_snippet"] = snippet
        if follow_links:
            entry["links"] = [
                {**link, "card": None if link["missing"] else link["target_key"]}
                for link in links(store, card, fields)
            ]
        if hops:
            # Those between two cards found here are not walked to, so listed here.
            entry["relations"] = [_step(r) for r in store.relations(card["id"])[:MAX_DIRECT]]
        cards.append(entry)
    note = f"以上只來自資料集「{store.dataset}」的卡片；沒有找到的，只能說「在這份資料集中沒有」。"
    if closest:
        note += (
            f"沒有一張卡片含「{text}」的所有字詞；以上是含最多字詞的卡片，最接近的在前，"
            "不一定是答案，請看內容再回答。"
        )
    elif not found and text:
        note += "沒有卡片含這些字詞；回答「沒有」之前，請換較短的字詞（例如公司名）再查一次。"
    if words and (entity_type or domain or field):
        note += _filter_note(store, found, text or "", entity_type, domain)
    related: list[dict[str, Any]] = []
    if hops:
        walked = walk_relations(store, [c["card_id"] for c in cards], hops=hops)
        related = _related(store, walked["reached"])
        if related:
            note += RELATED_RULE
        if walked["truncated"]:
            note += f"關係太多，只列出最近的 {MAX_RELATED} 張卡片。"
    return {
        "dataset": store.dataset,
        "total": len(found),
        "cards": cards,
        "related": related,
        "scope_note": note,
    }


def _filter_note(
    store: BiStore,
    found: list[tuple[Any, dict[str, dict[str, Any]]]],
    text: str,
    entity_type: str | None,
    domain: str | None,
) -> str:
    """Count excluded exact word matches; no extra card entries, links or evidence reads."""
    selected = {card["id"] for card, _ in found}
    outside = [(c, f) for c, f in search(store, text=text) if c["id"] not in selected]
    if not outside:
        return ""
    selected_types = (
        {entity_type.lower()} if entity_type else {c["entity_type"].lower() for c, _ in found}
    )
    types = Counter(
        c["entity_type"] for c, _ in outside if c["entity_type"].lower() not in selected_types
    )
    note = ""
    if types:
        note += (
            f"其他類型也有 {sum(types.values())} 張卡符合："
            + "、".join(f"{k} {types[k]}" for k in sorted(types))
            + "。"
        )
    if domain:
        reg = for_store(store)
        domains: Counter[str] = Counter()
        for _, fields in outside:
            if _in_domain(fields, domain, reg):
                continue
            value = _value(fields, "domain")
            if value is None and reg.is_bi:
                value = "wireless"
            domains.update(
                {str(v) for v in (value if isinstance(value, list) else [value]) if v is not None}
            )
        if domains:
            count = sum(not _in_domain(f, domain, reg) for _, f in outside)
            note += (
                f"其他領域也有 {count} 張卡符合："
                + "、".join(f"{k} {domains[k]}" for k in sorted(domains))
                + "。"
            )
    if not note:
        note = f"另有 {len(outside)} 張卡符合字詞，但被目前篩選排除。"
    return (
        note + "若以上沒有答案，請用相同 text 再查，移除 entity_type、domain、field、value 篩選；"
        "計數不是答案，需讀卡片內容。"
    )


BODY_SNIPPET_CHARS = 300


def _body_snippet(
    store: BiStore,
    card: Any,
    fields: dict[str, dict[str, Any]],
    words: list[str],
    approved: Collection[str] | None,
    classes: dict[str, set[str]],
) -> dict[str, str] | None:
    """A matched stored body excerpt, never an entire unrestricted body or raw source."""
    body = fields.get("body")
    if body is None or not words or not approved:
        return None
    text = str(body["value"] or "")
    positions = [text.lower().find(word) for word in words if word in text.lower()]
    if not positions:
        return None
    sources = {
        e["source_id"]
        for e in store.evidence(card["id"])
        if e["field"] == "body" and e["source_id"]
    }
    # Curated/imported card text without source classification defaults to INTERNAL.
    levels = {level for source in sources for level in classes.get(source, {"UNKNOWN"})}
    if not sources:
        filename = str(body["ref"]).split("#row", 1)[0]
        levels = classes.get("name:" + filename, {"INTERNAL"})
    if not levels.issubset(approved):
        return None
    start = max(0, min(positions) - 80)
    end = min(len(text), start + BODY_SNIPPET_CHARS - 2)
    snippet = ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
    return {"field": "body", "text": snippet, "source": f"{body['kind']}:{body['ref']}"}


def _card_entry(store: BiStore, card: Any, fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
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
        "field_states": {
            name: {k: state[k] for k in ("state", "reason", "origin") if state[k] is not None}
            for name, state in store.field_states(card["id"]).items()
        },
    }


def _related(store: BiStore, reached: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The reached cards as a search returns cards, with `from`, `hops`, `path`, `claim`."""
    reg = for_store(store)
    everything = store.all_fields() if reached else {}
    found = []
    for node in reached:
        card = store.card(node["card_id"])
        start = store.card(node["from_id"])
        if card is None or start is None:
            continue
        fields = current_fields(reg, card["entity_type"], everything.get(card["id"], {}))
        found.append(
            {
                **_card_entry(store, card, fields),
                "from": f"{start['entity_type']}:{start['canonical_key']}",
                "hops": node["hops"],
                "path": node["path"],
                "claim": node["claim"],
            }
        )
    return found
