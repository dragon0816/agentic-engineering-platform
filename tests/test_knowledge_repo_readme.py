"""Knowledge repositories R5 (part): the generated REPO.md (docs/phases/KNOWLEDGE_REPO.md §9)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from knowledge.repo import CheckReport, Repository, create, join, register_type
from knowledge.repo.readme import readme_text, write_readme
from knowledge.repo.skills import Skill, stage_skill

SCHEMA = "bi.schema/v1.1@2.0.0"


class AnyType:
    name = "test-readme"

    def unit_problem(self, key: str, value: Any) -> str | None:
        return None

    def check(self, before: Mapping[str, Any], after: Mapping[str, Any]) -> CheckReport:
        return CheckReport()


register_type(AnyType())


@pytest.fixture
def pcs(tmp_path: Path) -> tuple[Repository, Repository]:
    shared = tmp_path / "shared"
    shared.mkdir()
    a = create(
        tmp_path / "pc-a",
        shared,
        repo_id="market-bi",
        title="市場 BI 知識庫",
        purpose="看市場需求與訊號。",
        kind="test-readme",
        author="alice",
    )
    return a, join(tmp_path / "pc-b", shared / "market-bi", author="bob")


def _build(a: Repository, tmp_path: Path) -> None:
    schema_file = tmp_path / "schema.json"
    schema_file.write_text("{}", encoding="utf-8")
    doc = tmp_path / "schema.md"
    doc.write_text("# schema", encoding="utf-8")
    a.stage_file("schemas/bi.schema__v1.1@2.0.0.json", schema_file)
    a.stage_file("schemas/bi.schema__v1.1@2.0.0.md", doc)
    a.stage("schema", SCHEMA)
    stage_skill(
        a,
        Skill(
            name="aidc-supply-chain",
            revision=1,
            schema=SCHEMA,
            role="extract",
            applies_to=("sources/aidc-power",),
            body="rules",
        ),
    )
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF")
    a.stage_file("sources/aidc-power/3f9a1c2b-report.pdf", report)
    a.commit("set up the schema, the AIDC skill and the first report")
    a.push()


def test_readme_names_schema_skills_versions_and_next_steps(
    pcs: tuple[Repository, Repository], tmp_path: Path
) -> None:
    a, _ = pcs
    _build(a, tmp_path)
    a.tag("2026q4-review", "first review")
    a.publish("2026q4-review")
    a.stage("x", "1")
    a.commit("one more | fact")
    a.push()
    text = readme_text(a)
    assert text.startswith("# 市場 BI 知識庫\n\n看市場需求與訊號。\n")
    assert "- Version: `bi.schema/v1.1@2.0.0`" in text
    assert "- File: `schemas/bi.schema__v1.1@2.0.0.json`" in text
    assert "- Readable description: `schemas/bi.schema__v1.1@2.0.0.md`" in text
    assert "| `aidc-supply-chain` | 1 | extract | `sources/aidc-power/` |" in text
    assert "- Published: tag `2026q4-review` (by alice)" in text
    assert "- The maintenance head is 1 commit(s) ahead of it." in text
    assert "one more \\| fact" in text
    assert "`sources/aidc-power/` → read by `aidc-supply-chain`" in text
    assert "Source folders in use: `sources/aidc-power/`" in text


def test_readme_marks_skills_that_need_an_update(
    pcs: tuple[Repository, Repository], tmp_path: Path
) -> None:
    a, _ = pcs
    _build(a, tmp_path)
    a.stage("schema", {"ref": "bi.schema/v1.1@2.1.0", "from": SCHEMA})
    a.commit("upgrade the schema")
    a.push()
    text = readme_text(a)
    assert "- Upgraded from: `bi.schema/v1.1@2.0.0`" in text
    assert "| needs update |" in text
    assert "not run until they are updated: aidc-supply-chain" in text


def test_readme_is_the_same_on_every_pc(pcs: tuple[Repository, Repository], tmp_path: Path) -> None:
    a, b = pcs
    _build(a, tmp_path)
    path = write_readme(a)
    b.sync()
    assert readme_text(b) == path.read_text(encoding="utf-8")
    assert readme_text(a) == readme_text(a)


def test_an_empty_repository_says_what_is_missing(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    text = readme_text(a)
    assert "No schema has been committed yet." in text
    assert "No skill has been committed yet." in text
    assert "Published: nothing yet; the Agent reads the maintenance head." in text
    assert "No commit has been pushed yet." in text
