"""A BI schema as a Markdown document for people (knowledge repositories §8).

A repository keeps its schema file in `schemas/`; a JSON schema also gets this
readable `.md` beside it, so a maintainer can see how the data is classified
without reading JSON: each type, its fields (kind, label, allowed values, link
target, required) and the links between types. Pure: the same schema always
gives the same text.
"""

from __future__ import annotations

from aep_bi.cards.schema import FieldDef, Registry, TypeDef


def _cell(text: str) -> str:
    """Text safe inside a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _kind(item: FieldDef) -> str:
    kind = item.kind
    if item.is_list and not kind.endswith("list") and kind != "list":
        kind += " (list)"
    return kind


def _allowed(item: FieldDef) -> str:
    parts = []
    if item.enum:
        parts.append(", ".join(f"`{v}`" for v in item.enum))
    if item.range:
        low, high = item.range
        parts.append(f"{low:g} – {high:g}")
    return "; ".join(parts)


def _type_section(entity: TypeDef) -> list[str]:
    lines = [
        f"## {entity.name} — {entity.label}",
        "",
        f"- Named by: {', '.join(f'`{n}`' for n in entity.naming)}",
    ]
    if entity.domain:
        lines.append(f"- Domain: {entity.domain}")
    lines += [
        "",
        "| Field | Label | Kind | Allowed values | Links to | Required |",
        "|---|---|---|---|---|---|",
    ]
    for item in entity.fields:
        cells = [
            f"`{item.name}`",
            _cell(item.label),
            _kind(item),
            _cell(_allowed(item)),
            ", ".join(item.link_to) if item.is_link else "",
            "yes" if item.required else "",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def schema_markdown(reg: Registry) -> str:
    """The readable document of schema `reg`."""
    lines = [
        f"# {reg.title}",
        "",
        f"Schema `{reg.ref}`: {len(reg.types)} card types. Generated from the schema file; "
        "edit the schema (a new version), never this document.",
        "",
    ]
    if reg.domains:
        lines += [f"Domains: {', '.join(f'`{d}`' for d in reg.domains)}", ""]
    lines += ["## Types", "", "| Type | Label | Fields |", "|---|---|---|"]
    for entity in reg.types.values():
        lines.append(f"| `{entity.name}` | {_cell(entity.label)} | {len(entity.fields)} |")
    lines.append("")
    links = [
        (entity.name, item.name, target)
        for entity in reg.types.values()
        for item in entity.fields
        if item.is_link
        for target in item.link_to
    ]
    if links:
        lines += ["## Links between types", "", "| From | Field | To |", "|---|---|---|"]
        lines += [f"| `{source}` | `{name}` | `{target}` |" for source, name, target in links]
        lines.append("")
    for entity in reg.types.values():
        lines += _type_section(entity)
    return "\n".join(lines).rstrip("\n") + "\n"
