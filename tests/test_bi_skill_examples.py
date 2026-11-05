"""The example extraction skills under `docs/examples/bi-skills/` are valid skills.

Colleagues copy these into a vault, so each must parse under the rules the product
reads them with, target the shipped schema and say nothing a skill may not say.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from capabilities.bi_cards import homes, vault, vault_skills
from knowledge.repo import skills

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "examples" / "bi-skills"
SCHEMA = json.loads(
    (ROOT / "src" / "capabilities" / "bi_cards" / "bi_schema_v5.json").read_text(encoding="utf-8")
)
DOMAINS = ("aidc", "wireless", "robotics", "aerospace", "mobile")


def _text(domain: str) -> str:
    return (EXAMPLES / f"{domain}-extract" / "rev-1-example.md").read_text(encoding="utf-8")


def test_there_is_one_example_per_schema_domain() -> None:
    assert {d.lower() for d in SCHEMA["domains"]} == set(DOMAINS)
    assert sorted(p.name for p in EXAMPLES.iterdir() if p.is_dir()) == sorted(
        f"{d}-extract" for d in DOMAINS
    )


@pytest.mark.parametrize("domain", DOMAINS)
def test_an_example_parses_as_the_skill_of_its_application(domain: str) -> None:
    name = f"{domain}-extract"
    skill = skills.parse_skill(
        _text(domain),
        path=f"applications/{domain}/skills/{name}/rev-1-example.md",
        layout=homes.LAYOUT,
    )
    assert skill.name == name
    assert skill.role == "extract"
    assert skill.schema == f"{SCHEMA['schema_id']}@{SCHEMA['version']}"
    assert skill.applies_to == (homes.sources_dir(domain),)
    assert skill.card_types
    assert set(skill.card_types) <= {t["name"] for t in SCHEMA["types"]}
    # What it tells colleagues stays in the head: the model reads only the body.
    assert "同事通常會改" in _text(domain)
    assert "同事通常會改" not in skill.body


def test_the_mobile_example_says_it_was_never_tried() -> None:
    assert "尚未驗證" in _text("mobile")
    assert "尚未用真實資料試過" in skills.parse_skill(_text("mobile"), layout=homes.LAYOUT).body


@pytest.mark.parametrize("domain", DOMAINS)
def test_an_example_saved_in_a_vault_is_what_a_run_of_its_folder_reads(
    domain: str, tmp_path: Path
) -> None:
    example = skills.parse_skill(_text(domain), layout=homes.LAYOUT)
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    shared.mkdir()
    made = vault.create(
        workspace,
        {"path": str(shared), "title": "T", "purpose": "fictional", "schema": SCHEMA["schema_id"]},
        "alice",
    )
    vault_id = made["vault"]["id"]
    saved = vault.save_skill(
        workspace,
        vault_id,
        {
            "name": f"{domain}/{example.name}",  # as the guide says to type it on the page
            "role": example.role,
            "applies_to": list(example.applies_to),
            "card_types": list(example.card_types),
            "body": example.body,
        },
    )
    assert saved["skill"]["name"] == f"{domain}/{example.name}"
    rules = vault_skills.run_rules(vault.Vault(workspace, vault_id).repo, homes.sources_dir(domain))
    assert example.body in rules["text"]
    assert rules["card_types"] == list(example.card_types)


def test_a_review_copy_in_a_folder_with_no_sources_is_nobody_s_default(tmp_path: Path) -> None:
    """`market-intel` keeps the examples for colleagues to read this way
    (`docs/guides/BI_SKILL_EXAMPLES.zh-TW.md`): no run of any folder may pick them."""
    workspace = tmp_path / "workspace"
    shared = tmp_path / "shared"
    shared.mkdir()
    made = vault.create(
        workspace,
        {"path": str(shared), "title": "T", "purpose": "fictional", "schema": SCHEMA["schema_id"]},
        "alice",
    )
    vault_id = made["vault"]["id"]
    for domain in DOMAINS:
        example = skills.parse_skill(_text(domain), layout=homes.LAYOUT)
        vault.save_skill(
            workspace,
            vault_id,
            {
                "name": f"library/skill-review/{example.name}-review",
                "role": "extract",
                "applies_to": ["library/skill-review/sources"],
                "card_types": list(example.card_types),
                "body": example.body,
            },
        )
    target = vault.Vault(workspace, vault_id)
    for home in (*DOMAINS, "library/products"):
        rules = vault_skills.run_rules(target.repo, homes.sources_dir(home))
        assert [item["role"] for item in rules["skills"]] == ["classify"]
        assert rules["card_types"] == []
    assert "library/skill-review/sources" not in vault.skills(workspace, vault_id)["folders"]
