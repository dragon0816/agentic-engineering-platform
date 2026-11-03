"""The folder layout of a BI vault: homes, skills, tools (BI_CARD_MODEL.md §4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from capabilities.bi_cards import homes, vault_skills, vault_sources
from capabilities.bi_cards.store import BiStoreError
from capabilities.bi_cards.vault import BI_TYPE, Vault, create
from knowledge.repo import readme_text, skills
from knowledge.repo.repository import DEFAULT_LAYOUT, RepoError, layout_of, path_problem
from knowledge.repo.wiki import WIKI

SCHEMA = "bi.schema/v1.1@5.0.0"


def _vault(tmp_path: Path, **given: Any) -> Vault:
    (tmp_path / "drive").mkdir(exist_ok=True)
    made = create(
        tmp_path / "ws",
        {
            "path": str(tmp_path / "drive"),
            "title": "Homes",
            "id": "homes",
            "author": "alice",
            "schema": SCHEMA,
            "default_pack": False,
            **given,
        },
        "alice",
    )
    return Vault(tmp_path / "ws", made["vault"]["id"])


@pytest.mark.parametrize(
    "folder",
    [
        "sources",
        "sources/whatever",
        "sources/applications/aidc-power",
        "sources/library/products",
        "applications/aidc/sources",
        "applications/aidc/sources/reports/2026",
        "library/products/sources",
        "library/corrections/sources",
    ],
)
def test_a_source_folder_may_be_a_homes_or_one_from_before_them(folder: str) -> None:
    assert vault_skills.checked_folder(folder) == folder


@pytest.mark.parametrize(
    "folder",
    [
        "applications",
        "applications/aidc",
        "applications/aidc/skills",
        "applications/AIDC/sources",
        "applications/aidc/sources/../../x",
        "applications/aidc/sources/.hidden",
        "library/sources",
        "library/skills/sources",
        "library/products",
        "schemas/x",
        "skills/x",
        "cards",
        "other/sources",
    ],
)
def test_any_other_source_folder_is_refused(folder: str) -> None:
    with pytest.raises(BiStoreError) as failure:
        vault_skills.checked_folder(folder)
    assert failure.value.code == "folder_invalid"


def test_the_paths_of_a_home_are_exact() -> None:
    assert homes.home_dir("aidc") == "applications/aidc"
    assert homes.home_dir("library/products") == "library/products"
    assert homes.sources_dir("aidc") == "applications/aidc/sources"
    assert homes.sources_dir("library/products") == "library/products/sources"
    assert homes.skills_dir("aidc") == "applications/aidc/skills"
    assert homes.skills_dir("library/products") == "library/products/skills"
    assert homes.skills_dir("") == "library/skills"
    assert homes.tool_path("aidc", "fetch", 2, "alice", ".py") == (
        "applications/aidc/tools/fetch/rev-2-alice.py"
    )
    assert homes.tool_path("library/products", "fetch", 1, "a.b", ".xlsx") == (
        "library/products/tools/fetch/rev-1-a.b.xlsx"
    )
    assert homes.profile_path("aidc", 3, "alice") == "applications/aidc/profile/rev-3-alice.json"
    assert homes.profile_path("library/products", 1, "alice") == (
        "library/products/profile/rev-1-alice.json"
    )


def test_an_application_called_like_an_entry_is_another_home() -> None:
    assert homes.home_dir("products") == "applications/products"
    assert homes.home_dir("library/products") == "library/products"
    assert homes.home_of("applications/products/sources/a.pdf") == "products"
    assert homes.home_of("library/products/sources/a.pdf") == "library/products"


@pytest.mark.parametrize(
    ("path", "home"),
    [
        ("applications/aidc/sources", "aidc"),
        ("applications/aidc/sources/x/a.pdf", "aidc"),
        ("library/products/sources/a.pdf", "library/products"),
        ("sources/applications/aidc-power/a.pdf", "aidc-power"),
        ("sources/applications/aidc-power", "aidc-power"),
        ("sources/library/products/a.pdf", "library/products"),
        ("sources/a.pdf", None),
        ("sources", None),
        ("library/skills/classify/rev-1-a.md", None),
    ],
)
def test_the_home_of_a_path(path: str, home: str | None) -> None:
    assert homes.home_of(path) == home


@pytest.mark.parametrize("home", ["library/skills", "library/", "library/a/b", "AIDC", "", "a b"])
def test_a_bad_home_is_refused(home: str) -> None:
    assert homes.home_problem(home) is not None


def test_a_vault_starts_in_the_new_layout(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    folder = vault.folder
    for application in ("aidc", "aerospace", "robotics", "wireless"):
        for part in ("sources", "skills", "tools", "profile"):
            assert (folder / "applications" / application / part).is_dir()
    for entry in ("products", "technologies", "competitors"):
        for part in ("sources", "skills", "tools", "profile"):
            assert (folder / "library" / entry / part).is_dir()
    assert (folder / "library/skills").is_dir()
    # Nothing of the old layout in a new vault.
    assert not (folder / "skills").exists()
    assert not (folder / "sources").exists()
    # The lists are data, in the vault.
    units = vault.repo.working_units()
    assert [s["folder"] for s in json.loads(units[vault_skills.SEGMENTS_UNIT])] == [
        "aidc",
        "aerospace",
        "robotics",
        "wireless",
    ]
    assert json.loads(units[vault_skills.LIBRARY_UNIT]) == [
        "products",
        "technologies",
        "competitors",
    ]


def test_a_vault_may_name_its_own_applications_and_entries(tmp_path: Path) -> None:
    vault = _vault(tmp_path, segments=["Space Things"], library=["patents"])
    assert (vault.folder / "applications/space-things/sources").is_dir()
    assert (vault.folder / "library/patents/sources").is_dir()
    assert not (vault.folder / "applications/aidc").exists()
    assert not (vault.folder / "library/products").exists()


@pytest.mark.parametrize("library", [["skills"], [], ["Bad Name"], ["a", "a"], "products"])
def test_a_bad_library_list_is_refused(tmp_path: Path, library: Any) -> None:
    with pytest.raises(BiStoreError) as failure:
        _vault(tmp_path, library=library)
    assert failure.value.code == "library_invalid"
    assert not (tmp_path / "drive/homes").exists()


def test_the_classify_skill_is_in_the_library_and_spans_everything(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    units = vault.repo.units()
    value = units["skill:classify"]
    assert value["path"] == "library/skills/classify/rev-1-alice.md"
    assert (vault.folder / value["path"]).is_file()
    skill = skills.read_skill(vault.repo, "classify", units)
    assert skill.home == "" and skill.unit_name == "classify" and skill.applies_to == ()
    assert "applications/<資料夾>/sources" in skill.body
    assert "library/<項目>/sources" in skill.body
    assert "- aidc：AIDC" in skill.body
    assert "products、technologies、competitors" in skill.body
    assert "sources/applications" not in skill.body


def _skill(vault: Vault, name: str, home: str = "", **more: Any) -> skills.Skill:
    return skills.Skill(
        name=name,
        revision=1,
        schema=SCHEMA,
        role="extract",
        applies_to=(),
        body="Read the source.",
        home=home,
        **more,
    )


def test_a_homes_skill_has_its_own_unit_and_folder(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with vault.lock:
        a = skills.stage_skill(vault.repo, _skill(vault, "extract", "aidc"))
        b = skills.stage_skill(vault.repo, _skill(vault, "extract", "library/products"))
        again = skills.stage_skill(vault.repo, _skill(vault, "extract", "aidc"))
    assert a["path"] == "applications/aidc/skills/extract/rev-1-alice.md"
    assert b["path"] == "library/products/skills/extract/rev-1-alice.md"
    assert again["path"] == "applications/aidc/skills/extract/rev-2-alice.md"
    units = vault.repo.working_units()
    assert units["skill:aidc/extract"]["revision"] == 2
    assert units["skill:library/products/extract"]["revision"] == 1
    assert "skill:extract" not in units
    read = skills.read_skill(vault.repo, "aidc/extract", units)
    assert (read.name, read.home, read.revision) == ("extract", "aidc", 2)
    assert read.unit_name == "aidc/extract"
    # They go through a commit and push like any other, and read back from the folder.
    vault.repo.commit("add skills")
    assert vault.repo.push()["status"] == "pushed"
    pushed = vault.repo.units()
    assert skills.read_skill(vault.repo, "library/products/extract", pushed).home == (
        "library/products"
    )


@pytest.mark.parametrize("home", ["library/skills", "AIDC", "a/b"])
def test_a_skill_in_no_real_home_is_refused(tmp_path: Path, home: str) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(RepoError) as failure:
        skills.stage_skill(vault.repo, _skill(vault, "extract", home))
    assert failure.value.code == "home_invalid"


def test_an_entrys_skills_never_collide_with_the_library_skills(tmp_path: Path) -> None:
    pattern = homes.SKILL_PATH_RE
    assert pattern.match("library/skills/classify/rev-1-a.md")
    assert pattern.match("library/products/skills/classify/rev-1-a.md")
    assert pattern.match("applications/aidc/skills/x/rev-1-a.md")
    assert pattern.match("skills/classify/rev-1-a.md")  # an old vault's
    assert not pattern.match("library/skills/skills/x/rev-1-a.md")
    assert not pattern.match("applications/skills/x/rev-1-a.md")
    assert not pattern.match("other/skills/x/rev-1-a.md")


def test_the_extract_skill_of_a_source_is_its_homes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with vault.lock:
        skills.stage_skill(
            vault.repo,
            skills.Skill(
                name="extract",
                revision=1,
                schema=SCHEMA,
                role="extract",
                applies_to=("applications/aidc/sources",),
                body="AIDC rules.",
                home="aidc",
            ),
        )
    rules = vault_skills.run_rules(vault.repo, "applications/aidc/sources/reports")
    assert [s["name"] for s in rules["skills"]] == ["classify", "aidc/extract"]
    assert "AIDC rules." in rules["text"]
    other = vault_skills.run_rules(vault.repo, "applications/wireless/sources")
    assert [s["name"] for s in other["skills"]] == ["classify"]


def test_the_tools_of_a_home_are_stored_and_listed_never_run(tmp_path: Path) -> None:
    from capabilities.bi_cards import vault_tools

    vault = _vault(tmp_path)
    script = tmp_path / "fetch.py"
    marker = tmp_path / "ran"
    script.write_text(f"open({str(marker)!r}, 'w').close()\n", encoding="utf-8")
    with vault.lock:
        first = vault_tools.stage_file(vault.repo, "aidc", "fetch", script)
        second = vault_tools.stage_file(vault.repo, "library/products", "fetch", script)
        again = vault_tools.stage_file(vault.repo, "aidc", "fetch", script)
    assert first["path"] == "applications/aidc/tools/fetch/rev-1-alice.py"
    assert second["path"] == "library/products/tools/fetch/rev-1-alice.py"
    assert again["path"] == "applications/aidc/tools/fetch/rev-2-alice.py"
    vault.repo.commit("add tools")
    assert vault.repo.push()["status"] == "pushed"
    assert (vault.folder / first["path"]).read_bytes() == script.read_bytes()
    units = vault.repo.units()
    assert BI_TYPE.unit_problem("tool:aidc/fetch", units["tool:aidc/fetch"]) is None
    assert [t["name"] for t in vault_tools.current_tools(units)] == [
        "aidc/fetch",
        "library/products/fetch",
    ]
    assert not marker.exists()


@pytest.mark.parametrize(
    "given",
    [
        {"home": "AIDC", "name": "x", "suffix": ".py", "text": "1"},
        {"home": "library/skills", "name": "x", "suffix": ".py", "text": "1"},
        {"home": "aidc", "name": "Bad Name", "suffix": ".py", "text": "1"},
        {"home": "aidc", "name": "x", "suffix": "py", "text": "1"},
        {"home": "aidc", "name": "x", "suffix": ".py", "text": " "},
    ],
)
def test_a_bad_tool_is_refused(tmp_path: Path, given: dict[str, Any]) -> None:
    from capabilities.bi_cards import vault_tools

    vault = _vault(tmp_path)
    with pytest.raises(BiStoreError) as failure:
        vault_tools.stage_text(vault.repo, given)
    assert failure.value.code == "tool_invalid"
    assert not any(k.startswith("tool:") for k in vault.repo.working_units())


def test_a_source_file_is_told_from_the_rest_of_a_home() -> None:
    assert vault_sources.is_source_change("applications/aidc/sources/a.pdf")
    assert vault_sources.is_source_change("library/products/sources/m/x/rev-1-a.md")
    assert vault_sources.is_source_change("sources/applications/aidc/a.pdf")
    assert vault_sources.is_source_change("source:abc")
    assert not vault_sources.is_source_change("applications/aidc/skills/x/rev-1-a.md")
    assert not vault_sources.is_source_change("applications/aidc/tools/x/rev-1-a.py")
    assert not vault_sources.is_source_change("applications/aidc/profile/rev-1-a.json")
    assert not vault_sources.is_source_change("library/skills/classify/rev-1-a.md")


def test_the_wiki_type_keeps_the_default_layout_exactly() -> None:
    assert layout_of(WIKI) is DEFAULT_LAYOUT
    assert DEFAULT_LAYOUT.areas == ("schemas", "skills", "sources")
    assert DEFAULT_LAYOUT.new_areas == ("schemas", "skills", "sources")
    assert path_problem("applications/aidc/sources/a.pdf") is not None
    assert path_problem("library/products/sources/a.pdf") is not None
    assert not DEFAULT_LAYOUT.is_source_path("applications/aidc/sources/a.pdf")
    assert DEFAULT_LAYOUT.source_folder_problem("applications/aidc/sources") is not None
    assert DEFAULT_LAYOUT.source_folder_problem("sources/x") is None
    assert DEFAULT_LAYOUT.skill_path_re is None
    assert DEFAULT_LAYOUT.skill_area("") == "skills"
    with pytest.raises(RepoError):
        DEFAULT_LAYOUT.skill_area("aidc")
    # The unit key stays a bare name on a wiki.
    assert WIKI.unit_problem("skill:aidc/extract", {"path": "skills/extract/rev-1-a.md"})
    assert WIKI.unit_problem("skill:x", {"path": "applications/a/skills/x/rev-1-a.md"})


SEGMENTS = [
    {"folder": "aidc-computing", "label": "AIDC Computing"},
    {"folder": "aidc-power", "label": "AIDC Power"},
    {"folder": "uav", "label": "UAV"},
]


def test_a_domains_folders_are_the_applications_its_segments_name() -> None:
    domain = {
        "id": "aidc",
        "segments": [{"id": "aidc-computing", "label": "x"}, {"id": "y", "label": "AIDC Power"}],
    }
    assert vault_skills.domain_folders(domain, SEGMENTS) == [
        "applications/aidc-computing/sources",
        "applications/aidc-power/sources",
    ]
    assert vault_skills.domain_folders({"id": "Air Space", "segments": []}, SEGMENTS) == [
        "applications/air-space/sources"
    ]


def test_a_domains_folders_keep_the_old_ones_where_sources_stayed() -> None:
    domain = {"id": "drones", "segments": [{"id": "uav", "label": "UAV"}]}
    assert vault_skills.domain_folders(domain, SEGMENTS, old_folders=True) == [
        "applications/uav/sources",
        "sources/applications/uav",
    ]


def test_an_old_classify_text_still_counts_as_not_edited(tmp_path: Path) -> None:
    """A vault made before the homes holds the old text: a schema change still
    regenerates it, or every AI run after an upgrade would refuse."""
    vault = _vault(tmp_path)
    reg = vault._registry()
    old_body = vault_skills._old_classify_body(reg, [{"folder": "aidc", "label": "AIDC"}])
    with vault.lock:
        skills.stage_skill(
            vault.repo,
            skills.Skill(
                name="classify",
                revision=1,
                schema="bi.schema/v1.1@4.0.0",
                role="classify",
                applies_to=(),
                body=old_body,
            ),
        )
        vault.repo.stage(
            vault_skills.SEGMENTS_UNIT, json.dumps([{"folder": "aidc", "label": "AIDC"}])
        )
        vault_skills.regenerate_classify(vault.repo, reg, reg_with_ref(reg, "x/y@9.9.9"))
    current = skills.read_skill(vault.repo, "classify")
    assert current.schema == "x/y@9.9.9" and "applications/<資料夾>/sources" in current.body


def reg_with_ref(reg: Any, ref: str) -> Any:
    class Renamed:
        types = reg.types

    Renamed.ref = ref  # type: ignore[attr-defined]
    return Renamed


def test_a_source_kept_in_an_old_folder_can_still_be_read_and_withdrawn(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    original = tmp_path / "a.txt"
    original.write_text("fictional", encoding="utf-8")
    path = "sources/applications/aidc-power/aaaaaaaa-a.txt"
    with vault.lock:
        staged = vault.repo.stage_file(path, original)
        vault.repo.commit("add one in the old place")
        assert vault.repo.push()["status"] == "pushed"
    assert (vault.folder / path).is_file()
    vault.repo.withdraw([{"path": path, "sha256": staged["sha256"]}], "fictional")
    assert not (vault.folder / path).exists()


def test_only_a_source_can_be_withdrawn_from_a_home(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(RepoError) as failure:
        vault.repo.withdraw(
            [{"path": "library/skills/classify/rev-1-alice.md", "sha256": "0" * 64}], "no"
        )
    assert failure.value.code == "path_invalid"
    original = tmp_path / "a.txt"
    original.write_text("fictional", encoding="utf-8")
    path = "applications/aidc/sources/aaaaaaaa-a.txt"
    with vault.lock:
        staged = vault.repo.stage_file(path, original)
        vault.repo.commit("add one")
        vault.repo.push()
    vault.repo.withdraw([{"path": path, "sha256": staged["sha256"]}], "fictional")
    assert not (vault.folder / path).exists()


def test_a_file_outside_every_area_is_refused(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    original = tmp_path / "a.txt"
    original.write_text("fictional", encoding="utf-8")
    for path in ("other/a.txt", "cards/x.md", "published/x.sqlite"):
        with pytest.raises(RepoError) as failure:
            vault.repo.stage_file(path, original)
        assert failure.value.code == "path_invalid"


def test_the_readme_lists_a_homes_source_folders(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    original = tmp_path / "a.txt"
    original.write_text("fictional", encoding="utf-8")
    with vault.lock:
        vault.repo.stage_file("applications/aidc/sources/aaaaaaaa-a.txt", original)
        vault.repo.commit("add one")
        vault.repo.push()
    text = readme_text(vault.repo)
    assert "`applications/aidc/sources/`" in text
