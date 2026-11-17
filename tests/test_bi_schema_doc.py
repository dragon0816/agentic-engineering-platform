"""The readable Markdown of a BI schema (docs/phases/KNOWLEDGE_REPO.md §8)."""

from __future__ import annotations

from aep_bi.cards.schema import Registry, shipped
from aep_bi.cards.schema_doc import schema_markdown


def _v2() -> Registry:
    return next(reg for reg in shipped() if reg.version == "2.0.0")


def test_every_type_and_field_appears() -> None:
    reg = _v2()
    text = schema_markdown(reg)
    assert text.startswith(f"# {reg.title}\n")
    assert f"Schema `{reg.ref}`: {len(reg.types)} card types." in text
    for entity in reg.types.values():
        assert f"## {entity.name} — {entity.label}" in text
        for item in entity.fields:
            assert f"| `{item.name}` |" in text


def test_allowed_values_links_and_required_are_listed() -> None:
    reg = _v2()
    text = schema_markdown(reg)
    link = reg.types["SupplyLink"].get("supplier")
    assert link is not None and link.is_link
    for target in link.link_to:
        assert f"| `SupplyLink` | `supplier` | `{target}` |" in text
    grade = reg.types["SupplyLink"].get("evidence_grade")
    assert grade is not None and grade.enum
    assert ", ".join(f"`{v}`" for v in grade.enum) in text
    required = [f for e in reg.types.values() for f in e.fields if f.required]
    assert required and "| yes |" in text


def test_the_document_is_stable() -> None:
    reg = _v2()
    assert schema_markdown(reg) == schema_markdown(reg)
