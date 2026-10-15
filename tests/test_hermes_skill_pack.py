"""The Hermes skill pack (owner request 2026-10-15): the Hermes agent's MIT
skills, plus the scrubbed `business-cards`, as AEP Skill manifests and as
coding-agent skill folders, all switched off by default.
See `docs/phases/HERMES_SKILL_PACK.md`."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from agent.skills import SkillManifest
from capabilities.runtime import InstalledCapabilities
from host_runtime.skill_authoring import MAX_INSTRUCTIONS_CHARS, check_skill
from scripts import port_hermes_skills as port

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "packages" / "hermes-skill-pack"
VENDOR = PACK / "skills" / "vendor"


def _index() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((PACK / "pack.json").read_text(encoding="utf-8"))
    return data


def _entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = _index()["skills"]
    return entries


def _manifests() -> dict[str, SkillManifest]:
    return {
        path.name: SkillManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((PACK / "manifests").glob("*.json"))
    }


def test_the_pack_holds_the_mit_skills_and_business_cards_only() -> None:
    sources = {entry["source"] for entry in _entries()}
    assert not sources & port.SKIPPED
    assert sources & port.PERSONAL == {"productivity/business-cards"}
    assert len(sources) == len(_entries()) == 51
    for entry in _entries():
        expected = "Internal use" if entry["name"] == "business-cards" else "MIT"
        assert entry["license"] == expected, entry["source"]
        assert entry["author"].strip(), entry["source"]


def test_manifests_folders_and_index_agree() -> None:
    names = {entry["name"] for entry in _entries()}
    manifests = _manifests()
    assert {m.metadata.identity.name for m in manifests.values()} == names
    assert {path.name for path in VENDOR.iterdir()} == {f"hermes-{name}" for name in names}
    for entry in _entries():
        assert (PACK / entry["manifest"]).is_file()
        assert (PACK / entry["agent_folder"] / "SKILL.md").is_file()


def test_every_manifest_passes_the_hosts_skill_check() -> None:
    manifests = _manifests()
    aliases = [m.alias for m in manifests.values()]
    assert len(aliases) == len(set(aliases))
    for file_name, manifest in manifests.items():
        identity = manifest.metadata.identity
        assert file_name == f"{identity.namespace}__{identity.name}__{identity.version}.json"
        assert identity.namespace == "hermes"
        assert manifest.metadata.owner.type == "organization"
        assert manifest.metadata.visibility == "organization"
        assert manifest.metadata.lifecycle == "published"
        assert "hermes" in manifest.metadata.categories
        assert manifest.metadata.provenance and manifest.metadata.provenance[0].source.startswith(
            "Hermes agent skill "
        )
        assert manifest.selector_hint
        assert not manifest.commands and not manifest.rules and not manifest.script_tools
        assert len(manifest.instructions) <= MAX_INSTRUCTIONS_CHARS
        raw = manifest.model_dump(mode="json")
        others = [m for name, m in manifests.items() if name != file_name]
        checked, problems = check_skill(
            raw,
            raw,
            actor="owner",
            installed=InstalledCapabilities(),
            workflows=[],
            skills=others,
        )
        assert problems == [], (file_name, problems)
        assert checked == manifest


def test_instructions_name_no_hermes_tool_in_backticks() -> None:
    hermes_tools = re.compile(r"(?<!`)`(" + "|".join(port.TOOL_WORDS) + r"|browser_[a-z_]+)`")
    for file_name, manifest in _manifests().items():
        body = manifest.instructions.split(")\n\n", 1)[1]
        assert not hermes_tools.search(body), file_name
        own = manifest.metadata.identity.name
        assert f"~/.hermes/skills/{own}/" not in body, file_name


def test_agent_skill_folders_are_named_for_the_coding_agents() -> None:
    for folder in VENDOR.iterdir():
        text = (folder / "SKILL.md").read_text(encoding="utf-8")
        front, _ = port.split_frontmatter(text)
        fields = port.parse_frontmatter(front).fields
        assert fields["name"] == folder.name
        assert fields["description"]
    for path in VENDOR.rglob("*"):
        assert path.name != "__pycache__" and path.suffix != ".pyc", path


def test_everything_in_the_pack_is_switched_off_by_default() -> None:
    index = _index()
    assert index["default_enabled"] is False
    assert all(entry["default_enabled"] is False for entry in _entries())


def test_notice_names_every_skill_with_its_license() -> None:
    notice = (PACK / "NOTICE.md").read_text(encoding="utf-8")
    for entry in _entries():
        assert f"| hermes-{entry['name']} | {entry['source']} |" in notice
    # The licence texts the skills ship with stay beside them.
    for name in ("docx", "pdf", "powerpoint", "xlsx", "humanizer"):
        assert (VENDOR / f"hermes-{name}" / "LICENSE").is_file()


def test_no_credentials_or_owner_data_anywhere_in_the_pack() -> None:
    problems = port.scan_tree(PACK, personal=False)
    assert problems == []
    script = (REPO / "scripts" / "port_hermes_skills.py").read_text(encoding="utf-8")
    assert not port.REAL_CREDENTIAL.search(script)


def test_business_cards_ships_scrubbed() -> None:
    folder = VENDOR / "hermes-business-cards"
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    code = (folder / "scripts" / "cards.py").read_text(encoding="utf-8")
    manifest = _manifests()["hermes__business-cards__1.0.0.json"]
    for blob in (text, code, manifest.instructions):
        for marker in (
            "Leo",
            "hermes send",
            "%LOCALAPPDATA%",
            "鴻鼎",
            "陳建宏",
            "rs-workflow-jobs",
        ):
            assert marker not in blob
    assert "BUSINESS_CARDS_HOME" in code and "HERMES_HOME" not in code


# The converter itself, on a synthetic Hermes folder.

SKILL = """---
name: {name}
description: "Demo {name}: does a thing."
version: 1.2.0
author: Someone
license: {license}
platforms: [linux, windows]
metadata:
  hermes:
    tags: [Demo, Two Words]
    homepage: https://example.com/{name}
prerequisites:
  commands: [curl]
  env_vars: [DEMO_API_KEY]
---

# {name}

Use `terminal` to run `curl -H "Authorization: Bearer $DEMO_API_KEY" x`.
Then `browser_click` and `web_extract`; keep `git`.
Script: `~/.hermes/skills/{name}/scripts/run.py`.
{extra}
"""


def _skill(root: Path, key: str, *, license: str = "MIT", extra: str = "") -> None:
    folder = root / key
    folder.mkdir(parents=True)
    name = key.rsplit("/", 1)[-1]
    (folder / "SKILL.md").write_text(
        SKILL.format(name=name, license=license, extra=extra), encoding="utf-8"
    )
    (folder / "scripts").mkdir()
    (folder / "scripts" / "run.py").write_text("print('hi')\n", encoding="utf-8")
    (folder / "__pycache__").mkdir()
    (folder / "__pycache__" / "run.cpython-311.pyc").write_bytes(b"\0")


def test_frontmatter_subset() -> None:
    front, body = port.split_frontmatter(
        SKILL.format(name="demo", license="MIT", extra="").replace("\n", "\r\n")
    )
    parsed = port.parse_frontmatter(front)
    assert parsed.fields["description"] == "Demo demo: does a thing."
    assert parsed.tags == ["Demo", "Two Words"]
    assert parsed.platforms == ["linux", "windows"]
    assert parsed.commands == ["curl"] and parsed.env_vars == ["DEMO_API_KEY"]
    assert parsed.homepage == "https://example.com/demo"
    assert body.lstrip().startswith("# demo")


def test_redaction_keeps_the_code_balanced() -> None:
    text, found = port.redact_credentials('-H "Authorization: Bearer $KEY" | jq\nAPI_KEY=abc\n')
    assert text == '-H "Authorization: Bearer [redacted]" | jq\nAPI_KEY=[redacted]\n'
    assert len(found) == 2


def test_port_writes_manifests_and_agent_folders(tmp_path: Path) -> None:
    source = tmp_path / "hermes"
    _skill(source, "cat/demo")
    _skill(source, "apple/findmy")
    _skill(source, "research/rs-knowledge-base", license="UNLICENSED")
    out, personal = tmp_path / "pack", tmp_path / "personal"
    shipped, personal_only = port.port(source, out, personal_out=personal, log=lambda _: None)
    assert [item.name for item in shipped] == ["demo"]
    assert [item.name for item in personal_only] == ["rs-knowledge-base"]
    manifest = SkillManifest.model_validate_json(
        (out / "manifests" / "hermes__demo__1.2.0.json").read_text(encoding="utf-8")
    )
    assert manifest.metadata.categories == ("hermes", "cat", "demo", "two-words")
    assert manifest.metadata.compatibility.platforms == ("linux", "windows")
    assert manifest.alias == "demo"
    body = manifest.instructions
    assert "Use shell to run" in body and "browser (click)" in body and "web page reader" in body
    assert "`git`" in body
    assert "<this skill's folder>/scripts/run.py" in body
    assert "Bearer [redacted]" in body and "(DEMO_API_KEY)" in body
    assert "Needs: commands curl; environment variables DEMO_API_KEY." in body
    agent = out / "skills" / "vendor" / "hermes-demo"
    assert (agent / "scripts" / "run.py").is_file()
    assert not (agent / "__pycache__").exists()
    assert "name: hermes-demo" in (agent / "SKILL.md").read_text(encoding="utf-8")
    # The agent copy keeps the original text otherwise.
    assert "`terminal`" in (agent / "SKILL.md").read_text(encoding="utf-8")
    index = json.loads((out / "pack.json").read_text(encoding="utf-8"))
    assert index["default_enabled"] is False and "apple/findmy" in index["skipped"]
    private = SkillManifest.model_validate_json(
        (personal / "manifests" / "hermes__rs-knowledge-base__1.2.0.json").read_text(
            encoding="utf-8"
        )
    )
    assert private.metadata.visibility == "private"
    assert private.metadata.owner.type == "user"
    assert not (out / "skills" / "vendor" / "hermes-rs-knowledge-base").exists()


def test_internal_skills_stay_out_without_a_personal_folder(tmp_path: Path) -> None:
    source = tmp_path / "hermes"
    _skill(source, "productivity/leo-work-automation", license="UNLICENSED")
    shipped, personal_only = port.port(source, tmp_path / "pack", log=lambda _: None)
    assert shipped == [] and personal_only == []


@pytest.mark.parametrize(
    ("extra", "license", "reason"),
    [
        ("Ask Leo first.", "MIT", "personal marker"),
        ("Mail someone@corp-internal.net.", "MIT", "email address"),
        ("token ghp_" + "a" * 36, "MIT", "real credential"),
        ("", "Apache-2.0", "is not MIT"),
    ],
)
def test_port_refuses_what_must_not_ship(
    tmp_path: Path, extra: str, license: str, reason: str
) -> None:
    source = tmp_path / "hermes"
    _skill(source, "cat/demo", license=license, extra=extra)
    with pytest.raises(SystemExit, match=reason):
        port.port(source, tmp_path / "pack", log=lambda _: None)


def test_a_changed_source_stops_the_scrub(tmp_path: Path) -> None:
    folder = tmp_path / "skill"
    folder.mkdir()
    (folder / "SKILL.md").write_text("nothing to replace\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected 1"):
        port._apply_scrubs(folder, (port.Scrub("SKILL.md", "Leo", "the user", "owner name"),))


def test_personal_output_must_be_outside_the_repository() -> None:
    with pytest.raises(SystemExit):
        port.main(["--source", "x", "--out", "y", "--personal-out", str(REPO / "tmp-personal")])
