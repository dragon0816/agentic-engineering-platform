"""Generate the shipped BI schema registry `bi.schema/v1.1` from schema v4.

One-off converter (owner 2026-10-21, docs/DECISIONS.md): it *reads* the
robotics sample's `tools/bi_schema.py` (schema v4) with `ast`, never imports
or runs it, and writes `src/capabilities/bi_cards/bi_schema_v1_1.json`. The
id rules and field classes come from `bi.schema/v1` (the proposal file).

    python scripts/build_bi_schema_v1_1.py

`tests/test_bi_cards.py` checks that the committed JSON covers every v4 type
and field, so a change to v4 means running this again.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
V4 = REPO / "tests" / "fixtures" / "robotics_kb_sample" / "tools" / "bi_schema.py"
V1 = REPO / "docs" / "proposals" / "bi_schema_v1" / "bi_schema_v1.json"
OUT = REPO / "src" / "capabilities" / "bi_cards" / "bi_schema_v1_1.json"

TYPE_LABELS = {
    "Opportunity": "商機",
    "TestSolution": "測試方案",
    "Application": "應用",
    "Competitor": "競品",
    "CustomerProduct": "客戶產品",
    "Ecosystem": "生態系",
    "Account": "客戶",
    "Node": "價值鏈節點",
    "Technology": "技術",
    "Concept": "概念",
    "Trend": "趨勢",
    "Signal": "訊號",
}
#: Link targets: v4 links are untyped; these follow v1's relationship ranges
#: plus the v4 additions (CustomerProduct `ecosystem` may name an Account).
LINK_TARGETS: dict[str, list[str]] = {
    "vendor": ["Competitor"],
    "applications": ["Application"],
    "technologies": ["Technology"],
    "nodes": ["Node"],
    "node": ["Node"],
    "affects_nodes": ["Node"],
    "affected_nodes": ["Node"],
    "upstream": ["Node"],
    "downstream": ["Node"],
    "competing_solutions": ["TestSolution"],
    "reference_customers": ["Account"],
    "trends": ["Trend"],
    "account": ["Account"],
    "chipset_modules": ["Ecosystem", "Account"],
    "ecosystem": ["Ecosystem", "Account"],
    "inferred_applications": ["Application"],
    "key_suppliers": ["Ecosystem", "Account"],
    "key_customers": ["Account", "Ecosystem"],
    "influence_on": ["Account"],
    "related_tech": ["Technology"],
    "related_applications": ["Application"],
    "related": [],
    "test_solutions": ["TestSolution"],
    "related_concepts": ["Concept"],
    "customer_product": ["CustomerProduct"],
    "our_solutions": ["TestSolution"],
    "competitors": ["Competitor"],
    "lost_to": ["Competitor"],
}
#: ADR-K11 judgement fields (owner 2026-10-19), less the Trend ratings the
#: owner called facts on 2026-10-21 (market_impact, measurement_impact, our_fit).
JUDGEMENT = {
    "confidence",
    "Trend.stage",
    "Trend.time_to_demand",
    "Technology.maturity",
    "Competitor.strengths",
    "Competitor.weaknesses",
    "Competitor.pricing_position",
    "CustomerProduct.volume_tier",
    "Ecosystem.relationship_to_us",
    "Concept.audience",
    "Concept.review_status",
    "Signal.so_what",
    "Signal.reliability",
    "TestSolution.competing_solutions",
    "Ecosystem.influence_on",
    "CustomerProduct.inferred_applications",
}
DERIVED = {"updated"}
PRIORITY_REASON = "優先度由 Skill 依事實判斷，不存資料"


class _Reader:
    """Evaluates the literal subset of bi_schema.py: F(...) and schema(...)."""

    def __init__(self, tree: ast.Module) -> None:
        self.names: dict[str, ast.expr] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    self.names[target.id] = node.value

    def value(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self.value(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            return {
                self.value(k): self.value(v)
                for k, v in zip(node.keys, node.values, strict=True)
                if k is not None
            }
        if isinstance(node, ast.Name):
            return self.value(self.names[node.id])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.value(node.left) + self.value(node.right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [self.value(a) for a in node.args]
            kwargs = {k.arg: self.value(k.value) for k in node.keywords if k.arg}
            if node.func.id == "F":
                return _field(*args, **kwargs)
            if node.func.id == "schema":
                return _schema(*args, **kwargs)
            if node.func.id in ("list", "dict"):
                return args[0] if args else ([] if node.func.id == "list" else {})
        raise ValueError(f"unsupported expression at line {getattr(node, 'lineno', '?')}")


def _field(
    kind: str,
    aliases: Any = (),
    required: bool = False,
    enum: Any = None,
    default: Any = None,
    rng: Any = None,
    allowed: Any = None,
) -> dict[str, Any]:
    # v7+ names a list field's allowed values `allowed`; the registry keeps
    # them as the field's `enum` (BI vault V9).
    return {
        "kind": kind,
        "aliases": list(aliases),
        "required": required,
        "enum": enum if enum is not None else allowed,
        "default": default,
        "range": rng,
    }


DOMAINS: list[str] = []
DOMAIN_ALIASES: list[str] = []


def _schema(
    folder: str,
    filename: list[str],
    fields: list[Any],
    body: Any,
    tail: bool = True,
    domain: str = "one",
) -> dict[str, Any]:
    items = [(name, spec) for name, spec in fields]
    if domain == "one":
        domain_field = _field("enum", DOMAIN_ALIASES, enum=DOMAINS, default="wireless")
        items.insert(1, ("domain", domain_field))
    elif domain == "multi":
        items.insert(1, ("domain", _field("list", DOMAIN_ALIASES)))
    if tail:
        items.append(
            (
                "confidence",
                _field(
                    "enum", ["信心度", "可信度"], enum=["verified", "assumed"], default="assumed"
                ),
            )
        )
        items.append(("updated", _field("date", ["更新日期", "更新", "最後更新"], default="today")))
    return {
        "folder": folder,
        "filename": filename,
        "fields": items,
        "tail": tail,
        "domain": domain,
    }


def _label(name: str, aliases: list[str]) -> str:
    for alias in aliases:
        if any("一" <= ch <= "鿿" for ch in alias):
            return alias
    return name


def build() -> dict[str, Any]:
    return build_from(
        V4,
        labels=TYPE_LABELS,
        links=LINK_TARGETS,
        judgement=JUDGEMENT,
        meta={
            "schema_id": "bi.schema/v1.1",
            "version": "1.1.0",
            "status": "poc-contract",
            "title": (
                "BI Knowledge Schema v1.1 (schema v4 of the robotics sample; owner 2026-10-21)"
            ),
            "primary": "tests/fixtures/robotics_kb_sample/tools/bi_schema.py",
            "generator": "scripts/build_bi_schema_v1_1.py",
        },
    )


def build_from(
    path: Path,
    *,
    labels: dict[str, str],
    links: dict[str, list[str]],
    judgement: set[str],
    meta: dict[str, str],
) -> dict[str, Any]:
    """The registry document of one `bi_schema.py`. `links` is keyed by field
    name, or by `Type.field` where one name links differently per type."""
    source = path.read_bytes()
    tree = ast.parse(source.decode("utf-8"))
    reader = _Reader(tree)
    DOMAINS[:] = reader.value(reader.names["DOMAINS"])
    DOMAIN_ALIASES[:] = reader.value(reader.names["DOMAIN_ALIASES"])
    schemas = reader.value(reader.names["SCHEMAS"])
    global_aliases = reader.value(reader.names["GLOBAL_ALIASES"])
    enum_aliases = reader.value(reader.names["ENUM_ALIASES"])
    v1 = json.loads(V1.read_text(encoding="utf-8"))
    types: list[dict[str, Any]] = []
    ignored: dict[str, list[dict[str, Any]]] = {}
    for code_key, spec in schemas.items():
        name = spec["folder"]
        fields: list[dict[str, Any]] = []
        for field_name, field in spec["fields"]:
            if name == "Application" and field_name == "priority":
                # #222: priority is judged by the Skill and never stored.
                ignored.setdefault(name, []).append(
                    {"field": "priority", "aliases": field["aliases"], "reason": PRIORITY_REASON}
                )
                continue
            kind = field["kind"]
            klass = (
                "derived"
                if field_name in DERIVED
                else "judgement"
                if field_name in judgement or f"{name}.{field_name}" in judgement
                else "sourced"
            )
            link = kind in ("link", "linklist")
            qualified = f"{name}.{field_name}"
            known = qualified in links or field_name in links
            targets = links.get(qualified, links.get(field_name, [])) if link else []
            if link and not known:
                raise ValueError(f"no link target for {qualified}")
            fields.append(
                {
                    "name": field_name,
                    "label": "領域"
                    if field_name == "domain"
                    else _label(field_name, field["aliases"]),
                    "kind": kind,
                    "class": klass,
                    "enum": field["enum"],
                    "aliases": field["aliases"],
                    "required": field["required"],
                    "default": field["default"],
                    "range": field["range"],
                    "link_to": targets,
                    "list": kind in ("list", "linklist"),
                }
            )
        fields.append(
            {
                "name": "body",
                "label": "備註",
                "kind": "str",
                "class": "sourced",
                "enum": None,
                "aliases": global_aliases["body"],
                "required": False,
                "default": None,
                "range": None,
                "link_to": [],
                "list": False,
            }
        )
        types.append(
            {
                "name": name,
                "label": labels[name],
                "code_key": code_key,
                "naming": spec["filename"],
                "domain": spec["domain"],
                "has_confidence": spec["tail"],
                "fields": fields,
            }
        )
    return {
        "schema_id": meta["schema_id"],
        "version": meta["version"],
        "status": meta["status"],
        "title": meta["title"],
        "source": {
            "primary": meta["primary"],
            # LF-normalised, so a CRLF checkout gives the same digest.
            "primary_sha256": hashlib.sha256(source.replace(b"\r\n", b"\n")).hexdigest(),
            "read_without_executing": True,
            "generator": meta["generator"],
            "kept_from": "bi.schema/v1 (id_rules, field_classes)",
        },
        "id_rules": v1["id_rules"],
        "field_classes": v1["field_classes"],
        "domains": list(DOMAINS),
        "enum_aliases": enum_aliases,
        "ignored_fields": ignored,
        "computed_fields": {
            "Trend": [
                {
                    "name": "priority",
                    "label": "優先度",
                    "formula": "measurement_impact * our_fit",
                    "stored": False,
                }
            ]
        },
        "types": types,
    }


def main() -> None:
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
