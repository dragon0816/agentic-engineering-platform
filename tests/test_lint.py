"""Regression coverage for the adapted static lint (`knowledge.lint`)."""

import os
from datetime import date
from pathlib import Path

from test_raw import make_vault

from knowledge.lint import (
    BrokenSourcePath,
    DanglingLink,
    LintReport,
    OpenConflict,
    PathLink,
    UnknownSource,
    fix_links,
    page_name,
    scan,
)
from knowledge.raw import DropIntake, PlainTextExtractor
from knowledge.vault import Vault, provenance_lines

TODAY = date(2026, 9, 21)


def populate(vault: Vault) -> None:
    root = vault.root
    pages = {
        "wiki/overview.md": "---\ntitle: Overview\n---\n[[Foo]] [[Continue.dev]] [[Openhands]]\n",
        "wiki/entities/Foo.md": (
            "---\ntitle: Foo\ntype: entity\n---\n"
            "See [[wiki/entities/Bar]] and [[Missing]] and [[CLAUDE.md]].\n"
        ),
        "wiki/entities/Bar.md": (
            "---\ntitle: Bar\ntype: entity\n---\n[[Missing]] [[Missing]] [[Foo.md|the foo]]\n"
            "- ⚠️ Foo says X, Bar says Y\n"
        ),
        "wiki/entities/Continue.dev.md": "---\ntitle: Continue.dev\ntype: entity\n---\n[[Foo]]\n",
        "wiki/entities/OpenHands.md": (
            "---\ntitle: OpenHands\ntype: entity\n---\n[[raw/Study/Openhands#History]]\n"
        ),
        "wiki/concepts/Lonely.md": "no frontmatter here\n",
        "wiki/sources/Gone.md": (
            "---\ntitle: Gone\ntype: source\nsource_path: raw/Study/gone.md\n---\n[[Bar]]\n"
        ),
        "wiki/sources/Legacy.md": (
            "---\ntitle: Legacy\ntype: source\nsource_path: raw/Study/legacy.md\n---\n[[Foo]]\n"
        ),
        "wiki/sources/Stale.md": (
            "---\ntitle: Stale\ntype: source\nsource_id: src-0000\n---\n[[Foo]]\n"
        ),
    }
    for rel, text in pages.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / "raw" / "Study").mkdir(parents=True, exist_ok=True)
    (root / "raw" / "Study" / "legacy.md").write_text("legacy body\n", encoding="utf-8")
    (root / "index.md").write_text(
        "# Index\n\n## Sources\n- [[Gone]]\n- [[Legacy]]\n", encoding="utf-8"
    )


def test_page_name_strips_only_md() -> None:
    assert page_name("wiki/entities/Continue.dev.md") == "Continue.dev"
    assert page_name("Continue.dev") == "Continue.dev"
    assert page_name("CLAUDE.md") == "CLAUDE"
    assert page_name("wiki\\entities\\Foo.md") == "Foo"


def test_scan_computes_every_finding_as_typed_values(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    populate(vault)
    # Two typed Raw sources: one carried by a sources page, one never ingested.
    intake = DropIntake(vault, [PlainTextExtractor()])
    (tmp_path / "drop" / "done.txt").write_bytes(b"done")
    (tmp_path / "drop" / "never.txt").write_bytes(b"never")
    done = intake.intake("drop/done.txt", mode="apply", today=TODAY)
    intake.intake("drop/never.txt", mode="apply", today=TODAY)
    assert done.source is not None
    id_line, sha_line = provenance_lines(done.source)
    (tmp_path / "wiki" / "sources" / "Done.md").write_text(
        f"---\ntitle: Done\ntype: source\n{id_line}\n{sha_line}\n---\n[[Foo]]\n", encoding="utf-8"
    )

    report = scan(vault)
    assert report.pages == 10 and not report.clean
    assert report.types == (("(untyped)", 2), ("entity", 4), ("source", 4))
    # Names match case-sensitively (as in the source), so the lowercase
    # [[Openhands]] reaches no page and OpenHands is an orphan until fix_links.
    assert report.orphans == (
        "wiki/concepts/Lonely.md",
        "wiki/entities/OpenHands.md",
        "wiki/sources/Done.md",
        "wiki/sources/Stale.md",
    )
    # Ranked by references; ties keep first-seen order, as in the source. A link
    # to a root file such as [[CLAUDE.md]] is not a wiki page and so dangles.
    assert report.dangling == (
        DanglingLink(target="Missing", count=3),
        DanglingLink(target="CLAUDE.md", count=1),
        DanglingLink(target="raw/Study/Openhands", count=1),
        DanglingLink(target="Openhands", count=1),
    )
    assert report.path_links == (
        PathLink(page="wiki/entities/Bar.md", link="Foo.md"),
        PathLink(page="wiki/entities/Foo.md", link="wiki/entities/Bar"),
        PathLink(page="wiki/entities/OpenHands.md", link="raw/Study/Openhands"),
    )
    assert report.missing_frontmatter == ("wiki/concepts/Lonely.md",)
    assert report.broken_source_path == (
        BrokenSourcePath(page="wiki/sources/Gone.md", source_path="raw/Study/gone.md"),
    )
    assert report.unknown_source_id == (
        UnknownSource(page="wiki/sources/Stale.md", source_id="src-0000"),
    )
    assert report.pending_sources == ("raw/never.md",)
    assert report.open_conflicts == (
        OpenConflict(page="wiki/entities/Bar.md", line=6, text="Foo says X, Bar says Y"),
    )
    assert LintReport.model_validate_json(report.model_dump_json()) == report
    assert LintReport(pages=0).clean


def test_fix_links_rewrites_only_flagged_links_keeps_aliases_and_backs_up(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    populate(vault)
    before = scan(vault)
    changed = fix_links(vault, before, stamp="lint-1")
    assert changed == ("wiki/entities/Bar.md", "wiki/entities/Foo.md", "wiki/entities/OpenHands.md")
    assert vault.read("wiki/entities/Foo.md").endswith(
        "See [[Bar]] and [[Missing]] and [[CLAUDE.md]].\n"
    )
    assert "[[Foo|the foo]]" in vault.read("wiki/entities/Bar.md")
    # The case-corrected real page name replaces the path and keeps its anchor.
    assert vault.read("wiki/entities/OpenHands.md").endswith("[[OpenHands#History]]\n")
    backup = tmp_path / ".ingest-backup" / "lint-1" / "wiki" / "entities" / "Foo.md"
    assert backup.read_text(encoding="utf-8") == populate_text("wiki/entities/Foo.md")
    after = scan(vault)
    assert after.path_links == () and fix_links(vault, after, stamp="lint-2") == ()
    assert not (tmp_path / ".ingest-backup" / "lint-2").exists()
    # A link the scan did not flag is not touched, and the raw area is never written.
    assert vault.read("raw/Study/legacy.md") == "legacy body\n"


def populate_text(rel: str) -> str:
    if rel == "wiki/entities/Foo.md":
        return (
            "---\ntitle: Foo\ntype: entity\n---\n"
            "See [[wiki/entities/Bar]] and [[Missing]] and [[CLAUDE.md]].\n"
        )
    raise KeyError(rel)


def test_a_link_leaving_the_vault_is_not_a_page(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    populate(vault)
    (tmp_path.parent / "outside.md").write_text("---\ntitle: Out\n---\n[[Foo]]\n", encoding="utf-8")
    try:
        try:
            os.symlink(tmp_path.parent / "outside.md", tmp_path / "wiki" / "entities" / "Out.md")
        except (OSError, NotImplementedError):
            return
        report = scan(vault)
        assert all(item != "wiki/entities/Out.md" for item in report.orphans)
        assert report.pages == 9
    finally:
        (tmp_path.parent / "outside.md").unlink()
