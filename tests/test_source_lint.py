"""Offline characterization of the pinned static lint (`brain.py` `page_name`,
`scan`, `fix_links`); no platform imports. The excerpt is executed with the
pinned ingest and conflicts excerpts supplying `Vault`, `find_conflicts` and
`detect_manual_edits`, exactly as the source wired them."""

import hashlib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from test_source_vault import CONFLICTS_SHA, INGEST_SHA, make_vault, pinned

FIXTURES = Path(__file__).parent / "fixtures"
LINT_SHA = "01f8c88b7f13b4793d7644e81ac1c8c697a3ab4e2cde7eee1e18c4c32a401155"


@pytest.fixture
def lint() -> Any:
    ingest = pinned("source_vault_ingest.txt", INGEST_SHA)
    conflicts = pinned("source_vault_conflicts.txt", CONFLICTS_SHA)
    source = (FIXTURES / "source_vault_lint.txt").read_text(encoding="utf-8")
    assert hashlib.sha256(source.encode()).hexdigest() == LINT_SHA
    module = ModuleType("pinned_source_vault_lint")
    module.__dict__.update(
        Vault=ingest.Vault,
        find_conflicts=conflicts.find_conflicts,
        detect_manual_edits=conflicts.detect_manual_edits,
    )
    exec(compile(source, "source_vault_lint.txt", "exec"), module.__dict__)
    module.__dict__["_ingest"] = ingest
    return module


def populate(root: Path) -> None:
    make_vault(root)
    (root / "wiki" / "concepts").mkdir()
    pages = {
        "wiki/overview.md": "---\ntitle: Overview\n---\n[[Foo]] [[Continue.dev]] [[Openhands]]\n",
        "wiki/entities/Foo.md": (
            "---\ntitle: Foo\ntype: entity\n---\n"
            "See [[wiki/entities/Bar]] and [[Missing]] and [[CLAUDE.md]].\n"
        ),
        "wiki/entities/Bar.md": (
            "---\ntitle: Bar\ntype: entity\n---\n[[Missing]] [[Missing]] [[Foo.md]]\n"
            "- ⚠️ Foo says X, Bar says Y\n"
        ),
        "wiki/entities/Continue.dev.md": "---\ntitle: Continue.dev\ntype: entity\n---\n[[Foo]]\n",
        "wiki/entities/OpenHands.md": (
            "---\ntitle: OpenHands\ntype: entity\n---\n[[raw/Study/Openhands]]\n"
        ),
        "wiki/concepts/Lonely.md": "no frontmatter here\n",
        "wiki/sources/Report.md": (
            "---\ntitle: Report\ntype: source\nsource_path: raw/Study/report.md\n---\n[[Foo]]\n"
        ),
        "wiki/sources/Gone.md": (
            "---\ntitle: Gone\ntype: source\nsource_path: raw/Study/gone.md\n---\n[[Bar]]\n"
        ),
    }
    for rel, text in pages.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / "raw" / "Study" / "report.md").write_text("body\n", encoding="utf-8")
    (root / "raw" / "Study" / "never.md").write_text("never ingested\n", encoding="utf-8")
    (root / "index.md").write_text(
        "# Index\n\n## Sources\n- [[Report]]\n- [[Gone]]\n", encoding="utf-8"
    )


def test_source_page_name_strips_only_md(lint: Any) -> None:
    assert lint.page_name("wiki/entities/Continue.dev.md") == "Continue.dev"
    assert lint.page_name("Continue.dev") == "Continue.dev"
    assert lint.page_name("CLAUDE.md") == "CLAUDE"


def test_source_scan_computes_every_finding(lint: Any, tmp_path: Path) -> None:
    populate(tmp_path)
    report = lint.scan(lint._ingest.Vault(tmp_path))
    assert sorted(report["wiki_pages"]) == [
        "wiki/concepts/Lonely.md",
        "wiki/entities/Bar.md",
        "wiki/entities/Continue.dev.md",
        "wiki/entities/Foo.md",
        "wiki/entities/OpenHands.md",
        "wiki/overview.md",
        "wiki/sources/Gone.md",
        "wiki/sources/Report.md",
    ]
    # Names match case-sensitively, so the lowercase [[Openhands]] reaches no page
    # and OpenHands counts as an orphan — the case `fix_links` is built to repair.
    assert report["orphans"] == ["wiki/concepts/Lonely.md", "wiki/entities/OpenHands.md"]
    # [[CLAUDE.md]] is not a wiki page, so the source counts it dangling too.
    assert report["dangling"] == [
        ("Missing", 3),
        ("CLAUDE.md", 1),
        ("raw/Study/Openhands", 1),
        ("Openhands", 1),
    ]
    assert sorted(report["pathy_links"]) == [
        ("wiki/entities/Bar.md", "Foo.md"),
        ("wiki/entities/Foo.md", "wiki/entities/Bar"),
        ("wiki/entities/OpenHands.md", "raw/Study/Openhands"),
    ]
    assert report["missing_frontmatter"] == ["wiki/concepts/Lonely.md"]
    assert report["broken_source_path"] == [("wiki/sources/Gone.md", "raw/Study/gone.md")]
    assert report["pending_sources"] == ["raw/Study/never.md"]
    assert report["open_conflicts"] == [
        {"page": "wiki/entities/Bar.md", "line": 6, "text": "Foo says X, Bar says Y"}
    ]
    assert report["manual_edits"]["first_run"] is True
    assert report["pages"]["wiki/entities/Foo.md"]["type"] == "entity"


def test_source_fix_links_rewrites_only_flagged_links_with_real_names(
    lint: Any, tmp_path: Path
) -> None:
    populate(tmp_path)
    vault = lint._ingest.Vault(tmp_path)
    changed = lint.fix_links(vault, lint.scan(vault))
    assert sorted(changed) == [
        "wiki/entities/Bar.md",
        "wiki/entities/Foo.md",
        "wiki/entities/OpenHands.md",
    ]
    assert vault.read("wiki/entities/Foo.md").endswith(
        "See [[Bar]] and [[Missing]] and [[CLAUDE.md]].\n"
    )
    assert "[[Foo]]\n" in vault.read("wiki/entities/Bar.md")
    # The case-corrected real page name replaces the path, so nothing dangles.
    assert vault.read("wiki/entities/OpenHands.md").endswith("[[OpenHands]]\n")
    assert list((tmp_path / ".ingest-backup").glob("*/wiki/entities/Foo.md"))
    assert lint.scan(vault)["pathy_links"] == []
