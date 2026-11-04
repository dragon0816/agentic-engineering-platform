"""Knowledge repositories R4 core: the `wiki` type (docs/phases/KNOWLEDGE_REPO.md §3, §11).

Two PCs are two workspaces sharing one repository folder, as in
`tests/test_knowledge_repo.py`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from knowledge.repo import CheckReport, RepoError, Repository, create, join
from knowledge.repo.wiki import (
    READ_ONLY_NOTE,
    SCHEMA_REF,
    WIKI,
    import_vault,
    materialize,
    page_units,
    pages,
    render_page,
    set_benchmark,
    stage_page,
)

PRODUCT = """---
title: CMX500
aliases: [CMX, "CMX 500"]
tags:
  - product
  - tester
updated: 2026-10-01
---
# CMX500

Intro line.

## Overview

CMX500 is a one-box tester. [[cmx500-datasheet]]

## Options

- K100 base

## Notes

### Deep heading
text

## Notes

second notes section
"""

SOURCE_PAGE = """---
title: CMX500 datasheet
---
# CMX500 datasheet

Summary of the datasheet.
"""


@pytest.fixture(autouse=True)
def no_benchmark() -> Iterator[None]:
    set_benchmark(None)
    yield
    set_benchmark(None)


def make_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "wiki" / "entities").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "wiki" / "entities" / "cmx500.md").write_text(PRODUCT, encoding="utf-8")
    (vault / "wiki" / "sources" / "cmx500-datasheet.md").write_text(SOURCE_PAGE, encoding="utf-8")
    (vault / "index.md").write_text("# Index\n\n- [[cmx500]]\n", encoding="utf-8")
    (vault / "log.md").write_text("# Log\n\n## [2026-10-01] ingest | datasheet\n", encoding="utf-8")
    (vault / "CLAUDE.md").write_text("# Schema\n\nPages are entities.\n", encoding="utf-8")
    (vault / "skills" / "ingest-market").mkdir(parents=True)
    (vault / "skills" / "ingest-market" / "SKILL.md").write_text(
        "---\nname: ingest-market\napplies_to: raw/Market\n---\nRules.\n", encoding="utf-8"
    )
    (vault / "raw" / "Market").mkdir(parents=True)
    (vault / "raw" / "Market" / "report.pdf").write_bytes(b"%PDF-1.4 report")
    (vault / "drop" / "Productions").mkdir(parents=True)
    (vault / "drop" / "Productions" / "spec.docx").write_bytes(b"docx bytes")
    return vault


@pytest.fixture
def pcs(tmp_path: Path) -> tuple[Repository, Repository, Path]:
    shared = tmp_path / "shared"
    shared.mkdir()
    a = create(
        tmp_path / "pc-a",
        shared,
        repo_id="rs-k",
        title="RS Knowledge",
        purpose="test",
        kind="wiki",
        author="alice",
    )
    vault = make_vault(tmp_path)
    summary = import_vault(a, vault)
    assert summary["pages"] == 4 and summary["originals"] == 2
    a.commit("import the rs-k copy", kind="import")
    assert a.push()["status"] == "pushed"
    b = join(tmp_path / "pc-b", shared / "rs-k", author="bob")
    b.sync()
    return a, b, vault


PAGE = "wiki/entities/cmx500.md"


def edit(repo: Repository, purpose: str, old: str, new: str) -> None:
    text = pages(repo.working_units())[PAGE]
    assert old in text
    stage_page(repo, PAGE, text.replace(old, new))
    repo.commit(purpose)


def test_import_and_materialize_round_trip(
    pcs: tuple[Repository, Repository, Path], tmp_path: Path
) -> None:
    a, b, vault = pcs
    assert a.history()[0]["kind"] == "import"
    view = tmp_path / "view"
    result = materialize(b.units(), view, repo_folder=b.folder)
    assert result["pages"] == 4
    for name in (PAGE, "wiki/sources/cmx500-datasheet.md", "index.md", "log.md"):
        assert (view / name).read_text(encoding="utf-8") == (vault / name).read_text(
            encoding="utf-8"
        )
    assert (view / "CLAUDE.md").read_text(encoding="utf-8") == "# Schema\n\nPages are entities.\n"
    # The skill comes back as the same SKILL.md; Raw under the name pages cite.
    assert (view / "skills" / "ingest-market" / "SKILL.md").read_text(encoding="utf-8") == (
        vault / "skills" / "ingest-market" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert (view / "raw" / "Market" / "report.pdf").read_bytes() == b"%PDF-1.4 report"
    assert not (view / "raw" / "Productions").exists()  # drop/ originals stay in sources/
    assert (view / READ_ONLY_NOTE).is_file()
    units = b.units()
    assert units["schema"] == SCHEMA_REF
    assert units["skill:ingest-market"]["path"] == "skills/ingest-market/rev-1-alice.md"
    assert units["skill:ingest-market"]["role"] == "ingest"
    assert units["raw:Market/report.pdf"]["file"].startswith("sources/Market/")
    files = {
        p.relative_to(b.folder).as_posix() for p in (b.folder / "sources").rglob("*") if p.is_file()
    }
    assert {f.split("/")[1] for f in files} == {"Market", "Productions"}
    assert all(f.split("/")[-1][8] == "-" for f in files)  # <sha8>-<name>


def test_units_of_a_page(pcs: tuple[Repository, Repository, Path]) -> None:
    units = page_units(PAGE, PRODUCT)
    assert f"page:{PAGE}#Notes" in units and f"page:{PAGE}#Notes (2)" in units
    assert units[f"page:{PAGE}#Notes"]["body"].startswith("\n### Deep heading")
    assert units[f"front:{PAGE}:tags"]["text"] == "tags:\n  - product\n  - tester"
    assert units[f"page:{PAGE}#(preamble)"]["body"].startswith("# CMX500")
    assert render_page(units) == PRODUCT


def test_different_sections_merge(pcs: tuple[Repository, Repository, Path]) -> None:
    a, b, _ = pcs
    edit(a, "a adds an option", "- K100 base", "- K100 base\n- K200 NR")
    edit(b, "b rewrites the intro", "Intro line.", "Intro line, revised.")
    assert a.push()["status"] == "pushed"
    assert b.push()["status"] == "pushed"
    a.sync()
    text = pages(a.units())[PAGE]
    assert "- K200 NR" in text and "Intro line, revised." in text
    assert pages(a.units()) == pages(b.units())


def test_a_new_section_keeps_the_others_untouched(pcs: tuple[Repository, Repository, Path]) -> None:
    a, b, _ = pcs
    edit(a, "a adds a section", "## Options", "## Pricing\n\nOn request.\n\n## Options")
    edit(b, "b edits options", "- K100 base", "- K100 base, updated")
    assert a.push()["status"] == "pushed"
    assert b.push()["status"] == "pushed"
    text = pages(b.units())[PAGE]
    assert text.index("## Overview") < text.index("## Pricing") < text.index("## Options")
    assert "- K100 base, updated" in text


def test_same_section_is_a_conflict(pcs: tuple[Repository, Repository, Path]) -> None:
    a, b, _ = pcs
    edit(a, "a edits options", "- K100 base", "- K100 base (a)")
    edit(b, "b edits options", "- K100 base", "- K100 base (b)")
    a.push()
    result = b.push()
    assert result["status"] == "conflicts"
    assert [c["unit"] for c in result["conflicts"]] == [f"page:{PAGE}#Options"]


def test_frontmatter_fields_merge(pcs: tuple[Repository, Repository, Path]) -> None:
    a, b, _ = pcs
    edit(a, "a dates it", "updated: 2026-10-01", "updated: 2026-10-30")
    edit(b, "b adds an alias", 'aliases: [CMX, "CMX 500"]', 'aliases: [CMX, "CMX 500", 康]')
    a.push()
    assert b.push()["status"] == "pushed"
    text = pages(b.units())[PAGE]
    assert "updated: 2026-10-30" in text and '"CMX 500", 康]' in text
    assert text.startswith("---\ntitle: CMX500\naliases:")


def test_deletion_guard_blocks_a_lost_sourced_line(
    pcs: tuple[Repository, Repository, Path],
) -> None:
    a, _, _ = pcs
    edit(a, "drop the overview source", " [[cmx500-datasheet]]", "")
    result = a.push()
    assert result["status"] == "blocked"
    assert "CMX500 is a one-box tester. [[cmx500-datasheet]]" in result["blocking"][0]


def test_a_correction_lets_the_line_go(pcs: tuple[Repository, Repository, Path]) -> None:
    a, _, _ = pcs
    edit(a, "correct the overview", " [[cmx500-datasheet]]", "")
    key = f"page:{PAGE}#Overview"
    value = dict(a.working_units()[key])
    value["correction"] = {"reason": "the datasheet was withdrawn", "source": "cmx500-datasheet"}
    a.drop_local_commit(1)
    text = pages(a.working_units())[PAGE].replace(" [[cmx500-datasheet]]", "")
    stage_page(a, PAGE, text)
    a.stage(key, value)
    a.commit("correct the overview")
    assert a.push()["status"] == "pushed"


def test_moving_a_sourced_line_is_not_a_loss(pcs: tuple[Repository, Repository, Path]) -> None:
    a, _, _ = pcs
    line = "CMX500 is a one-box tester. [[cmx500-datasheet]]"
    text = (
        pages(a.working_units())[PAGE]
        .replace(line + "\n", "")
        .replace("- K100 base", f"- K100 base\n{line}")
    )
    stage_page(a, PAGE, text)
    a.commit("move the line")
    assert a.push()["status"] == "pushed"


def test_benchmark_regression_blocks(pcs: tuple[Repository, Repository, Path]) -> None:
    a, _, _ = pcs
    seen: list[tuple[int, int]] = []

    def bench(before: Mapping[str, str], after: Mapping[str, str]) -> CheckReport:
        seen.append((len(before), len(after)))
        regressed = "K100" not in after.get(PAGE, "")
        return CheckReport(blocking=["Q3 regressed"] if regressed else [], notes=["2/2 questions"])

    set_benchmark(bench)
    edit(a, "rename the base option", "- K100 base", "- base option")
    result = a.push()
    assert result == {
        "status": "blocked",
        "blocking": ["Q3 regressed"],
        "notes": ["pages added 0, changed 1, removed 0", "2/2 questions"],
    }
    assert seen == [(4, 4)]


def test_push_notes_without_benchmark(pcs: tuple[Repository, Repository, Path]) -> None:
    a, _, _ = pcs
    edit(a, "a adds an option", "- K100 base", "- K100 base\n- K200 NR")
    notes = a.push()["notes"]
    assert notes[0] == "pages added 0, changed 1, removed 0"
    assert "benchmark did not run" in notes[1]


def test_removing_and_adding_pages(pcs: tuple[Repository, Repository, Path]) -> None:
    a, b, _ = pcs
    stage_page(a, "wiki/concepts/nr.md", "# NR\n\n## Definition\n\n5G New Radio.\n")
    stage_page(a, "log.md", None)
    a.commit("add NR, drop the log")
    assert a.push()["status"] == "pushed"
    b.sync()
    assert "wiki/concepts/nr.md" in pages(b.units()) and "log.md" not in pages(b.units())


def test_unit_checks(pcs: tuple[Repository, Repository, Path]) -> None:
    a, _, _ = pcs
    for path in ("wiki/paths/my-path.md", "notes/x.md", "wiki/x.txt", "wiki/../x.md"):
        with pytest.raises(RepoError) as failure:
            stage_page(a, path, "# x\n")
        assert failure.value.code == "page_invalid"
    assert WIKI.unit_problem(f"page:{PAGE}#Overview", {"pos": 0, "heading": "Overview", "body": ""})
    assert WIKI.unit_problem("schema", "wiki.md") == "schema must be wiki.schema@<version>"
    assert WIKI.unit_problem("schema", "wiki.schema@1.0.0") is None
    assert WIKI.unit_problem("raw:../x.md", {"file": "sources/x", "sha256": "0"})
    assert WIKI.unit_problem("raw:a/x.md", {"file": "raw/x", "sha256": "0"})
    assert WIKI.unit_problem("skill:x", "skills/x/rev-1-a.md")  # the shared object form only
    assert WIKI.unit_problem("other", 1) == "unknown wiki unit"
    bad = {"pos": 0, "heading": "## X", "body": "", "correction": {"reason": "", "source": "s"}}
    assert WIKI.unit_problem(f"page:{PAGE}#X", bad) == "correction needs a reason and a source"


def test_materialize_never_replaces_a_persons_folder(
    pcs: tuple[Repository, Repository, Path], tmp_path: Path
) -> None:
    a, _, vault = pcs
    with pytest.raises(RepoError) as failure:
        materialize(a.units(), vault)
    assert failure.value.code == "target_not_materialized"
    view = tmp_path / "view"
    materialize(a.units(), view)
    (view / "wiki" / "stray.md").write_text("edited by hand", encoding="utf-8")
    materialize(a.units(), view)  # rebuilt: the hand edit is gone
    assert not (view / "wiki" / "stray.md").exists()
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".view")] == []


def _refuse_rename(monkeypatch: pytest.MonkeyPatch, times: int, suffix: str = "") -> None:
    """Windows refusing a folder's rename, as while another process holds a file inside."""
    real, left = Path.rename, [times]

    def rename(self: Path, target: Path) -> Path:
        if left[0] and self.name.endswith(suffix):
            left[0] -= 1
            raise PermissionError(13, "Access is denied")
        return real(self, target)

    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr("knowledge.repo.repository.time.sleep", lambda _s: None)


def test_materialize_waits_out_a_brief_refusal(
    pcs: tuple[Repository, Repository, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _, _ = pcs
    view = tmp_path / "view"
    _refuse_rename(monkeypatch, 3)
    materialize(a.units(), view)
    assert (view / READ_ONLY_NOTE).is_file()


def test_materialize_keeps_the_view_when_still_refused(
    pcs: tuple[Repository, Repository, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _, _ = pcs
    view = tmp_path / "view"
    materialize(a.units(), view)
    (view / "wiki" / "kept.md").write_text("the previous view", encoding="utf-8")
    _refuse_rename(monkeypatch, 1000, suffix=".tmp")
    with pytest.raises(PermissionError):
        materialize(a.units(), view)
    assert (view / "wiki" / "kept.md").is_file()
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".view")] == []
