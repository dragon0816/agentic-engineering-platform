"""Offline characterization of the pinned vault safety core; no platform imports.

The ingest excerpt keeps `Vault`, `validate`, `repair_wikilinks`,
`ensure_conflicts_visible`, `update_index` and `append_log`; the conflicts
excerpt is the whole module. Tests drive both against temporary vault
directories. No model, gateway, network or real vault is touched.
"""

import hashlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
INGEST_SHA = "5c59ef1e526fc483d89e627eb0509fbd44d07e33d6a171cea3c8001585a33143"
CONFLICTS_SHA = "82327028acf265d181209c8cd6fd4a3da78eddf51b8ae1702b68252f15bdaabb"


def pinned(name: str, digest: str) -> Any:
    source = (FIXTURES / name).read_text(encoding="utf-8")
    assert hashlib.sha256(source.encode()).hexdigest() == digest
    module = ModuleType(f"pinned_{name}")
    exec(compile(source, name, "exec"), module.__dict__)
    return module


@pytest.fixture
def ingest() -> Any:
    return pinned("source_vault_ingest.txt", INGEST_SHA)


@pytest.fixture
def conflicts() -> Any:
    return pinned("source_vault_conflicts.txt", CONFLICTS_SHA)


def make_vault(root: Path) -> Path:
    """The five things the source insists on before it will touch a directory."""
    (root / "raw" / "Study").mkdir(parents=True)
    (root / "wiki" / "sources").mkdir(parents=True)
    (root / "wiki" / "entities").mkdir(parents=True)
    (root / "CLAUDE.md").write_text("# schema\n", encoding="utf-8")
    (root / "index.md").write_text("# Index\n\n## Sources\n\n## Entities\n", encoding="utf-8")
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    return root


def plan_for(source_rel: str, **changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "one source",
        "pages": [
            {
                "path": "wiki/sources/Report.md",
                "action": "create",
                "content": f"---\ntitle: Report\nsource_path: {source_rel}\n---\nSee [[Foo]].\n",
            },
            {
                "path": "wiki/entities/Foo.md",
                "action": "update",
                "content": "---\ntitle: Foo\n---\nFoo.\n",
            },
        ],
        "index_entries": [{"section": "Sources", "line": "- [[Report]] — a report."}],
        "log_body": "- 來源：`raw/Study/report.md`。",
        "contradictions": [],
        "_source": source_rel,
    }
    base.update(changes)
    return base


def test_source_refuses_to_open_something_that_is_not_a_vault(ingest: Any, tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        ingest.Vault(tmp_path / "missing")
    (tmp_path / "half").mkdir()
    with pytest.raises(SystemExit):
        ingest.Vault(tmp_path / "half")


def test_source_safe_write_confines_writes_and_backs_up(ingest: Any, tmp_path: Path) -> None:
    vault = ingest.Vault(make_vault(tmp_path))
    with pytest.raises(ValueError, match="outside wiki/"):
        vault.safe_write("raw/Study/report.md", "x")
    with pytest.raises(ValueError, match="outside wiki/"):
        vault.safe_write("notes.md", "x")
    with pytest.raises(ValueError, match="escapes the vault"):
        vault.safe_write("wiki/../../escaped.md", "x")
    assert not (tmp_path / "escaped.md").exists()

    target = vault.safe_write("wiki/entities/Foo.md", "first\n")
    assert target.read_text(encoding="utf-8") == "first\n"
    assert (
        not list((tmp_path / ".ingest-backup").glob("*"))
        if (tmp_path / ".ingest-backup").exists()
        else True
    )
    vault.safe_write("wiki/entities/Foo.md", "second\n")
    backups = list((tmp_path / ".ingest-backup").glob("*/wiki/entities/Foo.md"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "first\n"
    assert target.read_text(encoding="utf-8") == "second\n"


def test_source_inventory_and_pending_use_the_path_as_dedup_key(
    ingest: Any, tmp_path: Path
) -> None:
    vault = ingest.Vault(make_vault(tmp_path))
    (tmp_path / "raw" / "Study" / "report.md").write_text("body", encoding="utf-8")
    (tmp_path / "raw" / "README.md").write_text("about raw", encoding="utf-8")
    (tmp_path / "raw" / "Study" / "assets").mkdir()
    (tmp_path / "raw" / "Study" / "assets" / "pic.md").write_text("asset", encoding="utf-8")
    assert vault.raw_sources() == ["raw/Study/report.md"]
    assert vault.pending() == ["raw/Study/report.md"]
    (tmp_path / "wiki" / "sources" / "Report.md").write_text(
        "---\ntitle: Report\nsource_path: raw/Study/report.md\n---\n", encoding="utf-8"
    )
    assert vault.ingested_paths() == {"raw/Study/report.md"}
    assert vault.pending() == []
    # The sharp edge the source documents: a moved source looks un-ingested.
    (tmp_path / "raw" / "Moved").mkdir()
    (tmp_path / "raw" / "Study" / "report.md").rename(tmp_path / "raw" / "Moved" / "report.md")
    assert vault.pending() == ["raw/Moved/report.md"]
    assert vault.wiki_inventory() == [("wiki/sources/Report.md", "Report")]


def test_source_validate_rejects_each_rule_break(ingest: Any) -> None:
    rel = "raw/Study/report.md"
    assert ingest.validate(plan_for(rel), rel) == []
    assert "no pages returned" in ingest.validate(plan_for(rel, pages=[]), rel)
    only_entity = plan_for(rel)
    only_entity["pages"] = only_entity["pages"][1:]
    assert "no wiki/sources/ page" in ingest.validate(only_entity, rel)
    wrong = plan_for(rel)
    wrong["pages"][0]["content"] = "---\ntitle: Report\nsource_path: raw/Other.md\n---\n"
    assert any(
        "missing `source_path: raw/Study/report.md`" in p for p in ingest.validate(wrong, rel)
    )
    outside = plan_for(rel)
    outside["pages"].append({"path": "raw/Study/report.md", "action": "update", "content": "x"})
    assert any("outside wiki/" in p for p in ingest.validate(outside, rel))
    empty = plan_for(rel)
    empty["pages"][1]["content"] = "   \n"
    assert any("empty content" in p for p in ingest.validate(empty, rel))
    pathy = plan_for(rel)
    pathy["pages"][1]["content"] = "See [[wiki/entities/Bar]] and [[CLAUDE.md]].\n"
    problems = ingest.validate(pathy, rel)
    assert len(problems) == 1 and "[[wiki/entities/Bar]]" in problems[0]


def test_source_repairs_only_unambiguous_links(ingest: Any) -> None:
    plan = plan_for("raw/Study/report.md")
    plan["pages"][1]["content"] = (
        "[[wiki/entities/Bar]] [[raw/Study/Baz.md]] [[Qux.md]] "
        "[[RFIC / FEM / AFE]] [[a/b]] [[Fine]]"
    )
    repaired = ingest.repair_wikilinks(plan)
    assert repaired == [
        "wiki/entities/Bar -> [[Bar]]",
        "raw/Study/Baz.md -> [[Baz]]",
        "RFIC / FEM / AFE -> [[RFIC]] / [[FEM]] / [[AFE]]",
    ]
    assert (
        plan["pages"][1]["content"]
        == "[[Bar]] [[Baz]] [[Qux.md]] [[RFIC]] / [[FEM]] / [[AFE]] [[a/b]] [[Fine]]"
    )
    assert any("[[a/b]]" in p for p in ingest.validate(plan, "raw/Study/report.md"))


def test_source_makes_a_reported_conflict_visible_on_a_page(ingest: Any) -> None:
    plan = plan_for("raw/Study/report.md", contradictions=["A says X, B says Y"])
    assert ingest.ensure_conflicts_visible(plan) is True
    entity = plan["pages"][1]["content"]
    assert entity.endswith("\n\n## ⚠️ 待裁決的衝突\n\n⚠️ A says X, B says Y\n")
    assert "⚠️" not in plan["pages"][0]["content"]
    # Already visible, or nothing reported: nothing is added.
    assert ingest.ensure_conflicts_visible(plan) is False
    assert ingest.ensure_conflicts_visible(plan_for("raw/Study/report.md")) is False


def test_source_index_and_log_updates(ingest: Any, tmp_path: Path) -> None:
    vault = ingest.Vault(make_vault(tmp_path))
    ingest.update_index(
        vault,
        [
            {"section": "Sources", "line": "- [[Report]] — a report."},
            {"section": "Sources", "line": "- [[Report]] — a report."},
            {"section": "Concepts", "line": "- [[Idea]] — new section at the end."},
        ],
    )
    assert vault.read("index.md") == (
        "# Index\n\n## Sources\n- [[Report]] — a report.\n\n## Entities\n\n"
        "## Concepts\n- [[Idea]] — new section at the end.\n"
    )
    plan = plan_for("raw/Study/report.md", contradictions=["A vs B"])
    ingest.append_log(vault, plan)
    log = vault.read("log.md")
    assert (
        log.startswith("# Log\n\n## [")
        and "] ingest | report\n- 來源：`raw/Study/report.md`。\n- ⚠️ A vs B\n" in log
    )


def test_source_decisions_are_append_only_and_injected(conflicts: Any, tmp_path: Path) -> None:
    root = make_vault(tmp_path)
    assert conflicts.decisions_for_prompt(root) == "（尚無裁決紀錄）"
    conflicts.append_decision(
        root, "Skill 的定義", "skill-as-instruction", "skill == function", "why", ["技能"]
    )
    text = (root / "decisions.md").read_text(encoding="utf-8")
    assert text.startswith(conflicts.DECISIONS_HEADER)
    assert (
        "- 保留：skill-as-instruction\n- 否決：skill == function\n"
        "- 理由：why\n- 影響頁面：[[技能]]\n"
    ) in text
    assert conflicts.decisions_for_prompt(root) == text.strip()


def test_source_conflict_markers_are_found_by_reading(conflicts: Any, tmp_path: Path) -> None:
    root = make_vault(tmp_path)
    page = root / "wiki" / "entities" / "Foo.md"
    page.write_text("---\ntitle: Foo\n---\n\n- ⚠️ first claim\ntext\n  ⚠️ second\n", encoding="utf-8")
    found = conflicts.find_conflicts(root)
    assert found == [
        {"page": "wiki/entities/Foo.md", "line": 5, "text": "first claim"},
        {"page": "wiki/entities/Foo.md", "line": 7, "text": "second"},
    ]
    assert conflicts.clear_conflict(root, "wiki/entities/Foo.md", 5) is True
    assert conflicts.clear_conflict(root, "wiki/entities/Foo.md", 5) is False
    assert page.read_text(encoding="utf-8") == "---\ntitle: Foo\n---\n\ntext\n  ⚠️ second\n"


def test_source_manual_edits_exclude_what_the_tool_wrote(conflicts: Any, tmp_path: Path) -> None:
    root = make_vault(tmp_path)
    page = root / "wiki" / "entities" / "Foo.md"
    page.write_text("v1", encoding="utf-8")
    assert conflicts.detect_manual_edits(root)["first_run"] is True
    conflicts.write_state(root, {"wiki/entities/Foo.md"})
    state = json.loads((root / ".brain-state.json").read_text(encoding="utf-8"))
    assert state["tool_written"] == ["wiki/entities/Foo.md"] and "index.md" in state["hashes"]
    page.write_text("v2", encoding="utf-8")
    (root / "wiki" / "entities" / "Bar.md").write_text("new", encoding="utf-8")
    report = conflicts.detect_manual_edits(root)
    # Foo changed but was tool-written last run, so it is not a human edit.
    assert report["edited"] == [] and report["added"] == ["wiki/entities/Bar.md"]
    conflicts.write_state(root)
    page.write_text("v3", encoding="utf-8")
    assert conflicts.detect_manual_edits(root)["edited"] == ["wiki/entities/Foo.md"]
