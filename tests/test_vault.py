"""Regression coverage for the adapted vault safety model (`knowledge.vault`)."""

import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from knowledge.contracts import KnowledgeSource
from knowledge.vault import (
    IndexEntry,
    PlannedPage,
    Vault,
    VaultError,
    VaultOutcome,
    WritePlan,
    carries_provenance,
    check_plan,
    ensure_conflicts_visible,
    insert_index_entries,
    log_block,
    provenance_lines,
    refusal_for,
    repair_wikilinks,
)

STAMP = "20260921-120000"
TODAY = date(2026, 9, 21)


def source() -> KnowledgeSource:
    return KnowledgeSource(
        source_id="src-report",
        original_ref="drop/report.pdf",
        sha256="a" * 64,
        raw_ref="raw/Study/report.md",
    )


def make_vault(root: Path) -> Vault:
    (root / "raw" / "Study").mkdir(parents=True)
    (root / "drop").mkdir()
    (root / "wiki" / "entities").mkdir(parents=True)
    (root / "index.md").write_text("# Index\n\n## Sources\n\n## Entities\n", encoding="utf-8")
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    (root / "raw" / "Study" / "report.md").write_text("original\n", encoding="utf-8")
    # The entity page the plans update already exists; the sources page does not.
    (root / "wiki" / "entities" / "Foo.md").write_text("old\n", encoding="utf-8")
    return Vault(root)


def sources_page(**changes: Any) -> PlannedPage:
    lines = "\n".join(provenance_lines(source()))
    data: dict[str, Any] = {
        "path": "wiki/sources/Report.md",
        "action": "create",
        "content": f"---\ntitle: Report\n{lines}\n---\nSee [[Foo]].\n",
    }
    data.update(changes)
    return PlannedPage.model_validate(data)


def plan(**changes: Any) -> WritePlan:
    data: dict[str, Any] = {
        "source": source(),
        "summary": "one source",
        "pages": (
            sources_page(),
            PlannedPage(
                path="wiki/entities/Foo.md", action="update", content="---\ntitle: Foo\n---\nFoo.\n"
            ),
        ),
        "index_entries": (IndexEntry(section="Sources", line="- [[Report]] — a report."),),
        "log_body": "- 來源：report。",
        "contradictions": (),
    }
    data.update(changes)
    return WritePlan.model_validate(data)


def codes(problems: tuple[Any, ...]) -> list[str]:
    return sorted(problem.code for problem in problems)


def test_layout_refusals_are_closed_codes() -> None:
    assert refusal_for("wiki/entities/Foo.md") is None
    assert refusal_for("index.md") is None and refusal_for("decisions.md") is None
    assert refusal_for("raw/Study/report.md") == "immutable_area"
    assert refusal_for("drop/report.pdf") == "immutable_area"
    assert refusal_for("notes.md") == "outside_writable"
    assert refusal_for("wiki") == "outside_writable"
    assert refusal_for("wiki/../../escaped.md") == "escapes_vault"
    assert refusal_for("C:/wiki/x.md") == "escapes_vault"
    assert refusal_for("") == "escapes_vault"
    assert refusal_for("\\wiki\\entities\\Foo.md") is None


def test_a_vault_needs_its_required_parts(tmp_path: Path) -> None:
    with pytest.raises(VaultError) as raised:
        Vault(tmp_path / "missing")
    assert raised.value.code == "not_a_vault"
    (tmp_path / "half" / "wiki").mkdir(parents=True)
    with pytest.raises(VaultError, match="not_a_vault"):
        Vault(tmp_path / "half")


def test_writes_are_confined_and_overwrites_backed_up(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    for rel, code in (
        ("raw/Study/report.md", "immutable_area"),
        ("drop/new.pdf", "immutable_area"),
        ("notes.md", "outside_writable"),
        ("wiki/../../escaped.md", "escapes_vault"),
    ):
        with pytest.raises(VaultError) as raised:
            vault.write(rel, "x", stamp=STAMP)
        assert (raised.value.code, raised.value.path) == (code, rel)
    assert (tmp_path / "raw" / "Study" / "report.md").read_text(encoding="utf-8") == "original\n"
    assert not (tmp_path.parent / "escaped.md").exists()

    assert vault.write("wiki/entities/Bar.md", "first\n", stamp=STAMP) is False
    assert vault.write("wiki/entities/Bar.md", "second\n", stamp=STAMP) is True
    backup = tmp_path / ".ingest-backup" / STAMP / "wiki" / "entities" / "Bar.md"
    assert backup.read_text(encoding="utf-8") == "first\n"
    assert vault.read("wiki/entities/Bar.md") == "second\n"
    assert vault.read("wiki/entities/Nope.md") == ""


def test_provenance_is_a_value_not_a_path() -> None:
    assert provenance_lines(source()) == ("source_id: src-report", f"source_sha256: {'a' * 64}")
    assert carries_provenance(sources_page().content, source())
    other = source().model_copy(update={"sha256": "b" * 64})
    assert not carries_provenance(sources_page().content, other)


def test_check_plan_names_every_broken_rule() -> None:
    assert check_plan(plan()) == ()
    assert codes(check_plan(plan(pages=()))) == ["no_pages"]
    assert codes(check_plan(plan(pages=(plan().pages[1],)))) == ["no_sources_page"]
    wrong = plan(
        pages=(sources_page(content="---\ntitle: Report\nsource_id: other\n---\n"), plan().pages[1])
    )
    assert codes(check_plan(wrong)) == ["missing_provenance"]
    outside = plan(
        pages=plan().pages
        + (PlannedPage(path="raw/Study/report.md", action="update", content="x"),)
    )
    assert [(p.code, p.path) for p in check_plan(outside)] == [
        ("outside_wiki", "raw/Study/report.md")
    ]
    escaping = plan(
        pages=plan().pages + (PlannedPage(path="wiki/../../x.md", action="create", content="x"),)
    )
    assert codes(check_plan(escaping)) == ["escapes_vault"]
    empty = plan(
        pages=(
            sources_page(),
            PlannedPage(path="wiki/entities/Foo.md", action="update", content=" \n"),
        )
    )
    assert codes(check_plan(empty)) == ["empty_content"]
    pathy = plan(
        pages=(
            sources_page(),
            PlannedPage(
                path="wiki/entities/Foo.md",
                action="update",
                content="[[wiki/entities/Bar]] [[CLAUDE.md]]",
            ),
        )
    )
    problems = check_plan(pathy)
    assert [(p.code, p.detail) for p in problems] == [("path_in_wikilink", "[[wiki/entities/Bar]]")]


def test_repairs_only_unambiguous_links() -> None:
    messy = plan(
        pages=(
            sources_page(),
            PlannedPage(
                path="wiki/entities/Foo.md",
                action="update",
                content=(
                    "[[wiki/entities/Bar]] [[raw/Study/Baz.md]] [[Qux.md]] "
                    "[[RFIC / FEM / AFE]] [[a/b]] [[Fine]]"
                ),
            ),
        )
    )
    repaired, repairs = repair_wikilinks(messy)
    # `.md` is stripped only from a path; [[Qux.md]] has no slash and stays, the
    # same reasoning that keeps a working [[CLAUDE.md]] link working.
    assert [(r.before, r.after) for r in repairs] == [
        ("wiki/entities/Bar", "[[Bar]]"),
        ("raw/Study/Baz.md", "[[Baz]]"),
        ("RFIC / FEM / AFE", "[[RFIC]] / [[FEM]] / [[AFE]]"),
    ]
    assert (
        repaired.pages[1].content
        == "[[Bar]] [[Baz]] [[Qux.md]] [[RFIC]] / [[FEM]] / [[AFE]] [[a/b]] [[Fine]]"
    )
    assert messy.pages[1].content.startswith("[[wiki/")  # the input is untouched
    assert codes(check_plan(repaired)) == ["path_in_wikilink"]
    assert repair_wikilinks(plan()) == (plan(), ())


def test_a_reported_conflict_lands_on_a_page() -> None:
    flagged = plan(contradictions=("A says X, B says Y",))
    marked, added = ensure_conflicts_visible(flagged)
    assert added is True
    assert marked.pages[1].content.endswith("\n\n## ⚠️ 待裁決的衝突\n\n⚠️ A says X, B says Y\n")
    assert "⚠️" not in marked.pages[0].content
    assert ensure_conflicts_visible(marked) == (marked, False)
    assert ensure_conflicts_visible(plan()) == (plan(), False)
    # With no entity or concept page, the first page carries it.
    only_source = plan(pages=(sources_page(),), contradictions=("X",))
    assert ensure_conflicts_visible(only_source)[0].pages[0].content.endswith("⚠️ X\n")


def test_index_insertion_and_log_block() -> None:
    text = "# Index\n\n## Sources\n\n## Entities\n"
    entries = (
        IndexEntry(section="Sources", line="- [[Report]] — a report."),
        IndexEntry(section="Sources", line="- [[Report]] — a report."),
        IndexEntry(section="Concepts", line="- [[Idea]] — new section at the end."),
    )
    assert insert_index_entries(text, entries) == (
        "# Index\n\n## Sources\n- [[Report]] — a report.\n\n## Entities\n\n"
        "## Concepts\n- [[Idea]] — new section at the end.\n"
    )
    block = log_block(plan(contradictions=("A vs B",)), TODAY)
    assert block == "\n## [2026-09-21] ingest | report\n- 來源：report。\n- ⚠️ A vs B\n"


def test_dry_run_reports_exactly_what_apply_would_write(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    (tmp_path / "wiki" / "entities" / "Foo.md").write_text("old\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    preview = vault.apply(plan(contradictions=("A vs B",)))
    assert preview.mode == "dry_run" and preview.accepted
    assert preview.written == (
        "wiki/sources/Report.md",
        "wiki/entities/Foo.md",
        "index.md",
        "log.md",
    )
    assert preview.backed_up == () and preview.conflict_marker_added is True
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before

    outcome = vault.apply(plan(contradictions=("A vs B",)), mode="apply", today=TODAY, stamp=STAMP)
    assert outcome.written == preview.written
    assert outcome.backed_up == ("wiki/entities/Foo.md", "index.md")
    assert (tmp_path / ".ingest-backup" / STAMP / "wiki" / "entities" / "Foo.md").read_text(
        encoding="utf-8"
    ) == "old\n"
    assert vault.read("wiki/entities/Foo.md").endswith("⚠️ A vs B\n")
    assert carries_provenance(vault.read("wiki/sources/Report.md"), source())
    assert (
        vault.read("index.md") == "# Index\n\n## Sources\n- [[Report]] — a report.\n\n## Entities\n"
    )
    assert (
        vault.read("log.md")
        == "# Log\n\n## [2026-09-21] ingest | report\n- 來源：report。\n- ⚠️ A vs B\n"
    )
    assert vault.read("raw/Study/report.md") == "original\n"
    assert not (tmp_path / ".ingest-backup" / STAMP / "log.md").exists()


def test_a_rejected_plan_leaves_the_vault_untouched(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    bad = plan(
        pages=plan().pages
        + (PlannedPage(path="raw/Study/report.md", action="update", content="x"),)
    )
    for mode in ("dry_run", "apply"):
        outcome = vault.apply(bad, mode=mode, today=TODAY, stamp=STAMP)
        assert not outcome.accepted and outcome.written == () and outcome.backed_up == ()
        assert codes(outcome.problems) == ["outside_wiki"]
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    assert not (tmp_path / ".ingest-backup").exists()


def test_repairs_happen_before_validation_and_are_reported(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    messy = plan(
        pages=(
            sources_page(
                content=sources_page().content.replace("[[Foo]]", "[[wiki/entities/Foo]]")
            ),
            plan().pages[1],
        )
    )
    outcome = vault.apply(messy, mode="apply", today=TODAY, stamp=STAMP)
    assert outcome.accepted and [(r.path, r.after) for r in outcome.repairs] == [
        ("wiki/sources/Report.md", "[[Foo]]")
    ]
    assert "[[Foo]]" in vault.read("wiki/sources/Report.md")


def test_root_files_match_exactly() -> None:
    assert refusal_for("index.md.bak") == "outside_writable"
    assert refusal_for("log.md/x") == "outside_writable"
    assert refusal_for("decisions.md") is None


def test_a_link_inside_wiki_cannot_reach_an_immutable_area(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    link = tmp_path / "wiki" / "link"
    try:
        os.symlink(tmp_path / "raw", link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory links need privileges on this machine")
    with pytest.raises(VaultError) as raised:
        vault.write("wiki/link/into_raw.md", "x", stamp=STAMP)
    assert raised.value.code == "immutable_area"
    assert not (tmp_path / "raw" / "into_raw.md").exists()
    sneaky = plan(
        pages=(
            sources_page(),
            PlannedPage(path="wiki/link/into_raw.md", action="create", content="x"),
        )
    )
    outcome = vault.apply(sneaky, mode="apply", today=TODAY, stamp=STAMP)
    assert [(p.code, p.detail) for p in outcome.problems] == [
        ("unwritable_target", "immutable_area")
    ]
    assert not (tmp_path / "wiki" / "sources").exists()


def test_reads_stay_inside_the_vault(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    (tmp_path.parent / "outside.md").write_text("secret", encoding="utf-8")
    try:
        with pytest.raises(VaultError, match="escapes_vault"):
            vault.read("../outside.md")
        assert vault.read("raw/Study/report.md") == "original\n"
        assert vault.read("wiki") == ""
    finally:
        (tmp_path.parent / "outside.md").unlink()


def test_written_lists_only_what_apply_writes(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    quiet = plan(index_entries=())
    preview = vault.apply(quiet)
    assert preview.written == ("wiki/sources/Report.md", "wiki/entities/Foo.md", "log.md")
    index_before = vault.read("index.md")
    outcome = vault.apply(quiet, mode="apply", today=TODAY, stamp=STAMP)
    assert outcome.written == preview.written and outcome.backed_up == ("wiki/entities/Foo.md",)
    assert vault.read("index.md") == index_before


def test_duplicate_pages_are_rejected_so_every_backup_is_real(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    (tmp_path / "wiki" / "entities" / "Foo.md").write_text("ORIGINAL\n", encoding="utf-8")
    twice = plan(
        pages=plan().pages
        + (PlannedPage(path="wiki\\entities\\Foo.md", action="update", content="B"),)
    )
    outcome = vault.apply(twice, mode="apply", today=TODAY, stamp=STAMP)
    assert [(p.code, p.path) for p in outcome.problems] == [
        ("duplicate_path", "wiki\\entities\\Foo.md")
    ]
    assert vault.read("wiki/entities/Foo.md") == "ORIGINAL\n"
    assert not (tmp_path / ".ingest-backup").exists()


def test_a_stamp_is_a_single_path_component(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    for bad in ("../escaped", "a/b", "", ".hidden", "x\\y"):
        with pytest.raises(ValueError, match="single path component"):
            vault.apply(plan(), mode="apply", today=TODAY, stamp=bad)
        with pytest.raises(ValueError, match="single path component"):
            vault.write("wiki/entities/Foo.md", "x", stamp=bad)
    assert not (tmp_path / "wiki" / "sources").exists()
    assert not (tmp_path.parent / "escaped").exists()
    # An automatic stamp is fine-grained enough that two applies do not share it.
    first = vault.apply(plan(), mode="apply", today=TODAY)
    assert first.accepted and (tmp_path / ".ingest-backup").is_dir()


def test_actions_are_checked_against_the_vault(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    # Without Foo, an update of it is a mismatch the plan's author must see.
    (tmp_path / "wiki" / "entities" / "Foo.md").unlink()
    outcome = vault.apply(plan())
    assert [(p.code, p.path) for p in outcome.problems] == [
        ("update_missing", "wiki/entities/Foo.md")
    ]
    (tmp_path / "wiki" / "entities" / "Foo.md").write_text("old\n", encoding="utf-8")
    assert vault.apply(plan()).accepted
    applied = vault.apply(plan(), mode="apply", today=TODAY, stamp=STAMP)
    assert applied.accepted
    # Now the sources page exists, so creating it again would replace it.
    again = vault.apply(plan(), mode="apply", today=TODAY, stamp="second")
    assert [(p.code, p.path) for p in again.problems] == [
        ("create_exists", "wiki/sources/Report.md")
    ]
    assert not (tmp_path / ".ingest-backup" / "second").exists()


def test_a_directory_target_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    (tmp_path / "wiki" / "entities" / "Foo.md").write_text("old\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    bad = plan(
        pages=plan().pages + (PlannedPage(path="wiki/entities/", action="create", content="x"),)
    )
    for mode in ("dry_run", "apply"):
        outcome = vault.apply(bad, mode=mode, today=TODAY, stamp=STAMP)
        assert [(p.code, p.detail) for p in outcome.problems] == [
            ("unwritable_target", "unwritable_target")
        ]
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_a_failed_write_rolls_the_whole_plan_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = make_vault(tmp_path)
    (tmp_path / "wiki" / "entities" / "Foo.md").write_text("old\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    def broken(rel: str, block: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(vault, "append", broken)
    with pytest.raises(VaultError, match="write_failed"):
        vault.apply(plan(contradictions=("X",)), mode="apply", today=TODAY, stamp=STAMP)
    # Pages and index are back to what they were; the new sources page is gone.
    files = {
        p: p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and ".ingest-backup" not in p.parts
    }
    assert files == before
    assert not (tmp_path / "wiki" / "sources" / "Report.md").exists()


def test_contradiction_notes_are_trimmed_like_the_source() -> None:
    padded = plan(contradictions=("  A vs B  ",))
    assert padded.notes == ("A vs B",)
    marked, added = ensure_conflicts_visible(padded)
    assert added and marked.pages[1].content.endswith("⚠️ A vs B\n")
    assert log_block(padded, TODAY).endswith("- ⚠️ A vs B\n")
    # The source dropped blank notes after the fact; the contract refuses them.
    with pytest.raises(ValidationError):
        plan(contradictions=("   ",))


def test_outcomes_and_plans_are_serializable_and_honest() -> None:
    encoded = plan(contradictions=("X",)).model_dump_json()
    assert WritePlan.model_validate_json(encoded) == plan(contradictions=("X",))
    with pytest.raises(ValidationError, match="rejected plan writes nothing"):
        VaultOutcome(mode="apply", problems=(check_plan(plan(pages=()))), written=("x",))
    with pytest.raises(ValidationError, match="dry run backs nothing up"):
        VaultOutcome(mode="dry_run", backed_up=("x",))
    with pytest.raises(ValidationError):
        PlannedPage.model_validate({"path": "wiki/x.md", "action": "delete"})
