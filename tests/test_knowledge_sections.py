"""Section-level page edits and the deletion guard (K3.2, owner 2026-10-11)."""

from pathlib import Path
from typing import Any

import pytest
from test_planning import PlanningModel, document, good_plan_json
from test_raw import make_vault

from knowledge.planning import PLAN_CONTRACT, RELEVANCE_CONTRACT, IngestPlanner
from knowledge.sections import SectionError, apply_op, lost_lines, parse
from knowledge.vault import Vault

PAGE = """---
title: CMX500
type: entity
updated: 2026-01-01
---
CMX500 是 5G 綜合測試儀。

## 規格

- 頻率到 8 GHz，見 [[CMX500 datasheet]]
- ⚠️ [[Deck A]]（2025-01）說 6 GHz，但 [[CMX500 datasheet]]（2025-06）說 8 GHz

## 相關來源

- [[CMX500 datasheet]]
"""
SOURCES = {"cmx500 datasheet", "deck a"}


def test_operations_change_only_their_section() -> None:
    added = apply_op(PAGE, {"op": "add_section", "heading": "Option", "content": "- K100"})
    assert added.startswith(PAGE.rstrip("\n")) and added.endswith("## Option\n\n- K100\n")
    appended = apply_op(PAGE, {"op": "append_to_section", "heading": "規格",
                               "content": "- 頻寬 400 MHz，見 [[Deck B]]"})
    spec = parse(appended).sections[0][1]
    assert spec[-2] == "- 頻寬 400 MHz，見 [[Deck B]]"
    assert parse(appended).sections[1] == parse(PAGE).sections[1]
    front = apply_op(PAGE, {"op": "set_frontmatter",
                            "fields": {"updated": "2026-10-11", "aliases": ["CMX 500"]}})
    assert "updated: 2026-10-11\n" in front and "aliases: [CMX 500]" in front
    assert parse(front).sections == parse(PAGE).sections
    with pytest.raises(SectionError, match="section_missing"):
        apply_op(PAGE, {"op": "replace_section", "heading": "Nope", "content": "x"})
    with pytest.raises(SectionError, match="bad_field"):
        apply_op(PAGE, {"op": "set_frontmatter", "fields": {"title": "Other"}})


def test_sourced_lines_are_what_the_guard_protects() -> None:
    replaced = apply_op(PAGE, {"op": "replace_section", "heading": "規格",
                               "content": "- 頻率到 8 GHz"})
    lost = lost_lines(PAGE, replaced, SOURCES)
    assert len(lost) == 2 and lost[1].startswith("- ⚠️")
    # Moving a line or re-indenting it is not a loss; plain prose is not guarded.
    moved = PAGE.replace("CMX500 是 5G 綜合測試儀。", "").replace(
        "## 相關來源\n", "## 相關來源\n  - 頻率到 8 GHz，見 [[CMX500 datasheet]]\n")
    assert lost_lines(PAGE, moved, SOURCES) == []


def _planner(tmp_path: Path, pages: list[dict[str, Any]]) -> tuple[IngestPlanner, Vault]:
    vault = make_vault(tmp_path)
    for rel, text in {"wiki/entities/CMX500.md": PAGE,
                      "wiki/sources/CMX500 datasheet.md": "---\ntitle: CMX500 datasheet\n---\nx\n",
                      "wiki/sources/Deck A.md": "---\ntitle: Deck A\n---\nx\n"}.items():
        (vault.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (vault.root / rel).write_bytes(text.encode("utf-8"))  # LF on every OS
    answer = good_plan_json()
    answer["pages"] = [answer["pages"][0], *pages]
    model = PlanningModel({RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: answer})
    return IngestPlanner(model, vault, alias="planner"), vault


def test_a_plan_of_section_operations_becomes_one_whole_page(tmp_path: Path) -> None:
    planner, vault = _planner(tmp_path, [
        {"path": "wiki/entities/CMX500.md", "op": "append_to_section", "heading": "相關來源",
         "content": "- [[MCP notes]]"},
        {"path": "wiki/entities/CMX500.md", "op": "set_frontmatter",
         "fields": {"updated": "2026-10-11"}},
    ])
    outcome = planner.plan(document(), today="2026-10-11")
    assert outcome.status == "planned", outcome.problems
    assert outcome.plan is not None
    page = next(p for p in outcome.plan.pages if p.path == "wiki/entities/CMX500.md")
    assert page.action == "update" and page.content.endswith("- [[MCP notes]]\n")
    assert "updated: 2026-10-11" in page.content and "⚠️" in page.content
    assert len(outcome.plan.pages) == 2  # one entry per page


def test_dropping_a_sourced_line_refuses_the_plan(tmp_path: Path) -> None:
    whole = PAGE.split("## 規格")[0] + "## 規格\n\n- 頻率到 8 GHz\n"
    planner, _ = _planner(tmp_path, [{"path": "wiki/entities/CMX500.md", "content": whole}])
    outcome = planner.plan(document(), today="2026-10-11")
    assert outcome.status == "invalid"
    assert [p.code for p in outcome.problems] == ["drops_sourced_line"]


def test_a_correction_may_replace_the_lines_of_its_own_section(tmp_path: Path) -> None:
    replace = {"path": "wiki/entities/CMX500.md", "op": "replace_section", "heading": "規格",
               "content": "- 頻率到 8 GHz，見 [[MCP notes]]"}
    planner, _ = _planner(tmp_path, [replace])
    assert planner.plan(document(), today="2026-10-11").status == "invalid"
    corrected = {**replace, "correction": {"reason": "datasheet 2025-06 supersedes",
                                           "source": "[[CMX500 datasheet]]"}}
    (tmp_path / "b").mkdir()
    planner, _ = _planner(tmp_path / "b", [corrected])
    assert planner.plan(document(), today="2026-10-11").status == "planned"


def test_human_pages_and_bad_operations_are_refused(tmp_path: Path) -> None:
    planner, _ = _planner(tmp_path, [
        {"path": "wiki/paths/入門.md", "content": "---\ntitle: 入門\n---\nx\n"},
        {"path": "wiki/entities/CMX500.md", "op": "replace_section", "heading": "Nope",
         "content": "x"},
        {"path": "wiki/entities/New.md", "op": "add_section", "heading": "A", "content": "x"},
    ])
    outcome = planner.plan(document(), today="2026-10-11")
    assert outcome.status == "invalid"
    assert [p.code for p in outcome.problems] == [
        "human_page", "section_operation", "section_operation"]


def test_a_windows_page_keeps_its_line_endings(tmp_path: Path) -> None:
    planner, vault = _planner(tmp_path, [
        {"path": "wiki/entities/CMX500.md", "op": "append_to_section", "heading": "相關來源",
         "content": "- [[MCP notes]]"}])
    page = vault.root / "wiki/entities/CMX500.md"
    page.write_bytes(PAGE.replace("\n", "\r\n").encode("utf-8"))
    outcome = planner.plan(document(), today="2026-10-11")
    assert outcome.status == "planned" and outcome.plan is not None
    written = next(p for p in outcome.plan.pages if p.path == "wiki/entities/CMX500.md").content
    assert written.count("\r\n") == written.count("\n")
    assert written.endswith("- [[MCP notes]]\r\n")
