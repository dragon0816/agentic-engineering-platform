"""Knowledge repositories R3 (common part): skill files inside a repository
(docs/phases/KNOWLEDGE_REPO.md §8)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from knowledge.repo import CheckReport, RepoError, Repository, create, join, register_type
from knowledge.repo.skills import (
    Skill,
    current_skills,
    parse_skill,
    read_skill,
    render_skill,
    revision_path,
    runnable,
    skill_for,
    skill_paths,
    stage_skill,
)


class AnyType:
    """Every JSON value is a unit value; nothing blocks a push."""

    name = "test-any"

    def unit_problem(self, key: str, value: Any) -> str | None:
        return None

    def check(self, before: Mapping[str, Any], after: Mapping[str, Any]) -> CheckReport:
        return CheckReport()


register_type(AnyType())

SCHEMA = "bi.schema/v1.1@2.0.0"


def skill(name: str = "aidc-supply-chain", **changes: Any) -> Skill:
    values: dict[str, Any] = {
        "name": name,
        "revision": 1,
        "schema": SCHEMA,
        "role": "extract",
        "applies_to": ("sources/aidc-computing", "sources/aidc-power"),
        "body": "ODM 是 Account；晶片廠是 Ecosystem。",
        "card_types": ("SupplyLink", "Account"),
    }
    values.update(changes)
    return Skill(**values)


@pytest.fixture
def pcs(tmp_path: Path) -> tuple[Repository, Repository]:
    shared = tmp_path / "shared"
    shared.mkdir()
    a = create(
        tmp_path / "pc-a",
        shared,
        repo_id="market",
        title="Market",
        purpose="test",
        kind="test-any",
        author="alice",
    )
    b = join(tmp_path / "pc-b", shared / "market", author="bob")
    return a, b


def test_render_and_parse_round_trip() -> None:
    original = skill(
        table_recipes=({"match_headers": ["客戶", "營收占比"], "type": "RevenueFact"},),
        extra={"description": "AIDC: 供應鏈"},
    )
    text = render_skill(original)
    assert text.startswith("---\nname: aidc-supply-chain\nrevision: 1\n")
    assert parse_skill(text) == original
    assert parse_skill(text, path="skills/aidc-supply-chain/rev-1-alice.md") == original


def test_parse_reads_hand_written_frontmatter() -> None:
    text = (
        "---\n"
        "name: wiki-market\n"
        "revision: 2\n"
        "schema: 'wiki.schema@1.0.0'\n"
        "role: ingest  # chosen by folder\n"
        "applies_to: [sources/Market, sources/Market/AI]\n"
        "---\n\n"
        "Write one page per company.\n"
    )
    parsed = parse_skill(text)
    assert parsed.schema == "wiki.schema@1.0.0"
    assert parsed.role == "ingest"
    assert parsed.applies_to == ("sources/Market", "sources/Market/AI")
    assert parsed.body == "Write one page per company."


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("name: x\n", "frontmatter"),
        ("---\nname: x\n", "結束"),
        ("---\nname: Bad Name\nrevision: 1\nschema: s@1\nrole: extract\n---\nbody\n", "name"),
        ("---\nname: x\nrevision: 0\nschema: s@1\nrole: extract\n---\nbody\n", "revision"),
        ("---\nname: x\nrevision: 1\nschema: s\nrole: extract\n---\nbody\n", "schema"),
        ("---\nname: x\nrevision: 1\nschema: s@1\nrole: guess\n---\nbody\n", "role"),
        (
            "---\nname: x\nrevision: 1\nschema: s@1\nrole: extract\n"
            "applies_to: [wiki/x]\n---\nbody\n",
            "sources/",
        ),
        ("---\nname: x\nrevision: 1\nschema: s@1\nrole: extract\n---\n\n", "說明"),
    ],
)
def test_invalid_skill_files_are_refused(text: str, fragment: str) -> None:
    with pytest.raises(RepoError) as failure:
        parse_skill(text)
    assert failure.value.code == "skill_invalid"
    assert fragment in failure.value.message


def test_path_must_match_the_content() -> None:
    with pytest.raises(RepoError) as failure:
        parse_skill(render_skill(skill()), path="skills/aidc-supply-chain/rev-2-alice.md")
    assert failure.value.code == "skill_invalid"
    assert (
        revision_path("aidc-supply-chain", 3, "leo.chi")
        == "skills/aidc-supply-chain/rev-3-leo.chi.md"
    )


def test_a_skill_revision_travels_with_commits(pcs: tuple[Repository, Repository]) -> None:
    a, b = pcs
    a.stage("schema", SCHEMA)
    value = stage_skill(a, skill())
    assert value["path"] == "skills/aidc-supply-chain/rev-1-alice.md"
    assert (
        read_skill(a, "aidc-supply-chain").body == "ODM 是 Account；晶片廠是 Ecosystem。"
    )  # staged
    a.commit("add the AIDC extraction skill")
    a.push()
    assert skill_paths(a.folder) == ["skills/aidc-supply-chain/rev-1-alice.md"]
    b.sync()
    assert current_skills(b, b.units())[0]["revision"] == 1
    # A new revision from the other PC becomes current; the first file stays.
    stage_skill(b, skill(body="ODM、電源廠是 Account。"))
    b.commit("ODM and power makers are accounts")
    b.push()
    a.sync()
    assert read_skill(a, "aidc-supply-chain", a.units()).revision == 2
    assert skill_paths(a.folder) == [
        "skills/aidc-supply-chain/rev-1-alice.md",
        "skills/aidc-supply-chain/rev-2-bob.md",
    ]
    # Revert brings the earlier revision back.
    a.revert(a.history()[1]["id"], "the new rule was wrong")
    a.push()
    assert read_skill(a, "aidc-supply-chain", a.units()).revision == 1


def test_a_skill_for_another_schema_needs_an_update(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    a.stage("schema", SCHEMA)
    stage_skill(a, skill())
    a.commit("skill")
    a.push()
    assert runnable(a, "aidc-supply-chain").revision == 1
    a.stage("schema", {"ref": "bi.schema/v1.1@2.1.0", "from": SCHEMA})
    a.commit("upgrade the schema")
    a.push()
    assert current_skills(a, a.units())[0]["needs_update"] is True
    with pytest.raises(RepoError) as failure:
        runnable(a, "aidc-supply-chain", a.units())
    assert failure.value.code == "skill_needs_update"
    assert failure.value.detail["schema"] == "bi.schema/v1.1@2.1.0"
    stage_skill(a, skill(schema="bi.schema/v1.1@2.1.0"))
    assert runnable(a, "aidc-supply-chain").revision == 2
    with pytest.raises(RepoError) as failure:
        runnable(a, "missing")
    assert failure.value.code == "skill_unknown"


def test_the_skill_for_a_source_is_the_longest_folder(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    stage_skill(a, skill("classify-all", role="classify", applies_to=()))
    stage_skill(a, skill("aidc", applies_to=("sources/aidc-computing",)))
    stage_skill(a, skill("aidc-gpu", applies_to=("sources/aidc-computing/gpu",)))
    stage_skill(a, skill("library", applies_to=("sources",)))

    def choose(source: str, role: str) -> str | None:
        found = skill_for(a, source, role)
        return None if found is None else str(found["name"])

    assert choose("sources/aidc-computing/gpu/nvidia.pdf", "extract") == "aidc-gpu"
    assert choose("sources/aidc-computing/tsmc.pdf", "extract") == "aidc"
    assert choose("sources/aidc-computing-old/x.pdf", "extract") == "library"
    assert choose("sources/robotics/x.pdf", "classify") == "classify-all"
    assert choose("sources/robotics/x.pdf", "ingest") is None
