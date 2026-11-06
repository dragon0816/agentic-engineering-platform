"""Creating a working domain (`docs/phases/BI_PAGE_SIMPLE.md` §10).

Owner, 2026-11-05: 「需要讓使用者可以create domain」, 「新增domain時，需要可以按照規則生成相對應的
檔案folder結構」. A home's folders follow the one rule; it is uncommitted until pushed; a colleague
gets the same structure; one domain cannot exist twice; its cards can carry it, with no new schema
version.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _commit, _ok, _push, _refused, _sync, _two_pcs

from capabilities.bi_cards import homes, vault, vault_skills
from capabilities.bi_cards.store import BiStore


def _create(ws: Path, vault_id: str, **body: Any) -> Any:
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/homes", body)


def _homes(ws: Path, vault_id: str) -> dict[str, Any]:
    reply = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/skills"))
    return {item["home"]: item for item in reply["homes"]}


def _shared(a: Path, vault_id: str) -> Path:
    return vault.Vault(a, vault_id).folder


def _folders(root: Path, home: str) -> list[bool]:
    return [(root / folder).is_dir() for folder in homes.home_folders(home)]


def test_the_structure_has_one_definition() -> None:
    assert homes.home_folders("aidc") == tuple(
        f"applications/aidc/{name}" for name in homes.HOME_FOLDERS
    )
    assert homes.home_folders("library/products")[0] == "library/products/sources"


def test_a_new_domain_is_listed_with_its_domain_and_stays_local_until_pushed(
    tmp_path: Path,
) -> None:
    drive, vault_id, _dataset, a, b = _two_pcs(tmp_path)
    reply = _ok(_create(a, vault_id, name="Automotive"))
    assert reply["home"] == "automotive"
    listed = _homes(a, vault_id)["automotive"]
    assert listed["label"] == "Automotive"
    assert listed["folder"] == "applications/automotive/sources"
    assert listed["domain"] == "automotive"

    # Uncommitted like anything else: it shows as a change, here only.
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    assert any(c["unit"] == "meta:home:automotive" for c in pending["uncommitted"])
    assert all(_folders(vault.Vault(a, vault_id).repo.work / "files", "automotive"))
    assert not any(_folders(_shared(a, vault_id), "automotive"))
    _sync(b, vault_id)
    assert "automotive" not in _homes(b, vault_id)

    _commit(a, vault_id, "新增領域 Automotive")
    assert not any(_folders(_shared(a, vault_id), "automotive"))
    assert _push(a, vault_id)["status"] == "pushed"
    assert all(_folders(_shared(a, vault_id), "automotive"))

    # A colleague gets the home on sync, and its folders even when only files travel.
    assert not any(_folders(vault.Vault(b, vault_id).folder, "automotive"))
    drive.deliver("a", "b", vault_id)
    assert not any(_folders(vault.Vault(b, vault_id).folder, "automotive"))
    _sync(b, vault_id)
    assert _homes(b, vault_id)["automotive"]["label"] == "Automotive"
    assert all(_folders(vault.Vault(b, vault_id).folder, "automotive"))


def test_a_rule_can_apply_to_a_new_domain_before_it_is_pushed(tmp_path: Path) -> None:
    # Acceptance F9: the folders a rule may apply to were read from the shared folder only, so
    # an unpushed domain was missing and the page fell back to another domain's folder.
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ok(_create(a, vault_id, name="Marine"))
    assert not any(_folders(_shared(a, vault_id), "marine"))
    reply = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/skills"))
    assert "applications/marine/sources" in reply["folders"]
    assert len(reply["folders"]) == len(set(reply["folders"]))
    body = {"name": "marine-extract", "role": "extract", "body": "虛構",
            "applies_to": ["applications/marine/sources"], "card_types": []}  # fmt: skip
    saved = _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/skills", body))
    assert saved["skill"]["applies_to"] == ["applications/marine/sources"]


def test_someone_joining_later_gets_the_same_structure(tmp_path: Path) -> None:
    drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ok(_create(a, vault_id, name="Automotive"))
    _commit(a, vault_id, "新增領域")
    _push(a, vault_id)
    c = drive.workspace("c")
    shared = drive.clone("a", "c", vault_id)
    for folder in reversed(homes.home_folders("automotive")):
        (shared / folder).rmdir()
    _ok(_call(c, "POST", "/api/bi/vaults/join", {"path": str(shared), "author": "carol"}))
    assert "automotive" in _homes(c, vault_id)
    assert all(_folders(shared, "automotive"))


def test_nothing_of_the_structure_counts_as_a_source_skill_or_tool(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    before = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/skills"))
    _ok(_create(a, vault_id, name="Automotive"))
    _commit(a, vault_id, "新增領域")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    for ws in (a, b):
        after = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/skills"))
        assert [s["name"] for s in after["skills"]] == [s["name"] for s in before["skills"]]
        assert after["tools"] == before["tools"]
        listed = _ok(_call(ws, "GET", "/api/bi/sources", dataset=dataset))
        assert listed["sources"] == []
        assert not [
            path
            for path in (vault.Vault(ws, vault_id).folder / "applications/automotive").rglob("*")
            if path.is_file()
        ]


@pytest.mark.parametrize(
    "name",
    ["AIDC", "aidc", "Aidc", " aidc ", "A-IDC", "Wireless", "Robotics"],
)
def test_a_name_differing_only_in_case_or_spelling_is_the_same_domain(
    tmp_path: Path, name: str
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    # Domains in use: a question in each (only those are listed, acceptance F22).
    for home in ("aidc", "wireless", "robotics"):
        body = {"question": "虛構題？", "must": ["好"], "slug": f"q-{home}", "home": home}
        _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/checks", body))
    _refused(_create(a, vault_id, name=name), 400, "home_exists")
    assert len(_homes(a, vault_id)) == 3 + 3  # and the three library entries


def test_naming_an_unused_default_domain_takes_it_up(tmp_path: Path) -> None:
    # Acceptance F22: the default list's AIDC with nothing in it is not listed, so 新增領域
    # 「AIDC」 must not answer that it exists.
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    assert not [h for h in _homes(a, vault_id) if not h.startswith("library/")]
    reply = _ok(_create(a, vault_id, name="AIDC"))
    assert reply["home"] == "aidc"
    assert [h for h in _homes(a, vault_id) if not h.startswith("library/")] == ["aidc"]
    assert _homes(a, vault_id)["aidc"]["domain"] == "AIDC"
    _refused(_create(a, vault_id, name="aidc"), 400, "home_exists")


def test_a_folder_name_that_exists_is_refused_whatever_the_label(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    body = {"question": "虛構題？", "must": ["好"], "slug": "q1", "home": "aidc"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/checks", body))
    _refused(_create(a, vault_id, name="全新名稱", folder="aidc"), 400, "home_exists")


def test_an_alias_is_the_domain_it_stands_for(tmp_path: Path, monkeypatch: Any) -> None:
    from capabilities.bi_cards.schema import Registry

    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    units = vault.Vault(a, vault_id).repo.working_units()
    reg: Registry | None = vault.Vault(a, vault_id)._schema_of(units)
    assert reg is not None
    monkeypatch.setitem(reg.enum_aliases, "domain", {"無線": "wireless", "手機": "mobile"})
    monkeypatch.setattr(reg, "domains", ("AIDC", "wireless", "mobile"))
    with pytest.raises(Exception, match="已經有領域"):
        vault_skills.new_home({"name": "無線"}, units, reg)
    # Its domain has no folder yet: this is how it gets one.
    made = vault_skills.new_home({"name": "手機"}, units, reg)
    assert made == {"home": "mobile", "label": "手機", "domain": ""}


@pytest.mark.parametrize(
    "name",
    [
        "skills",
        "sources",
        "tools",
        "profile",
        "library",
        "applications",
        "skill-review",
        "nul",
        "COM1",
    ],
)
def test_a_reserved_name_is_refused(tmp_path: Path, name: str) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _refused(_create(a, vault_id, name=name), 400, "home_reserved")


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": ""}, "home_name_missing"),
        ({"name": "a/b"}, "home_name_invalid"),
        ({"name": "x" * 41}, "home_name_invalid"),
        ({"name": "車用"}, "home_folder_needed"),
        ({"name": "車用", "folder": "../x"}, "home_folder_invalid"),
        ({"name": "車用", "folder": "a b"}, "home_folder_invalid"),
        ({"name": "車用", "folder": "x" * 41}, "home_folder_invalid"),
    ],
)
def test_a_name_or_folder_that_cannot_be_is_refused(
    tmp_path: Path, body: dict[str, str], code: str
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _refused(_create(a, vault_id, **body), 400, code)
    assert not (vault.Vault(a, vault_id).repo.work / "files/applications").exists()


def test_a_chinese_name_shows_and_its_folder_is_safe(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ok(_create(a, vault_id, name="車用電子", folder="automotive"))
    listed = _homes(a, vault_id)["automotive"]
    assert listed["label"] == "車用電子" and listed["domain"] == "automotive"


def test_two_people_creating_the_same_domain_get_one(tmp_path: Path) -> None:
    drive, vault_id, _dataset, a, b = _two_pcs(tmp_path)
    _ok(_create(a, vault_id, name="Automotive"))
    _ok(_create(b, vault_id, name="Automotive"))
    _commit(a, vault_id, "a 新增")
    _commit(b, vault_id, "b 新增")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    for ws in (a, b):
        found = [h for h in _homes(ws, vault_id) if "auto" in h]
        assert found == ["automotive"]


def test_two_people_creating_different_domains_do_not_meet(tmp_path: Path) -> None:
    drive, vault_id, _dataset, a, b = _two_pcs(tmp_path)
    _ok(_create(a, vault_id, name="Automotive"))
    _ok(_create(b, vault_id, name="Satellite"))
    _commit(a, vault_id, "a 新增")
    _commit(b, vault_id, "b 新增")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    for ws in (a, b):
        assert {"automotive", "satellite"} <= set(_homes(ws, vault_id))


def test_cards_of_a_new_domain_can_carry_it_with_no_new_schema_version(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    target = vault.Vault(a, vault_id)
    schema_before = target.repo.working_units()["schema"]
    skills_before = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/skills"))["skills"]
    _ok(_create(a, vault_id, name="Automotive"))
    units = target.repo.working_units()
    assert units["schema"] == schema_before

    from capabilities.bi_cards import catalog

    reg = catalog.for_store(BiStore(a, dataset))
    assert "automotive" in reg.domains
    assert homes.domain_of_folder(reg.domains, "applications/automotive/sources") == "automotive"
    # The schema itself is not changed, for this vault or anyone else's.
    assert "automotive" not in catalog.resolve(a, schema_before).domains
    # Nobody's skill turns 「需要更新」.
    after = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/skills"))["skills"]
    assert [s.get("needs_update") for s in after] == [s.get("needs_update") for s in skills_before]
    # The Dashboard's and cards' domain lists offer it.
    assert "automotive" in _ok(_call(a, "GET", "/api/bi/schema", dataset=dataset))["domains"]


def test_an_empty_folder_makes_no_home(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    shared = _shared(a, vault_id)
    (shared / "library/skill-review/sources").mkdir(parents=True)
    (shared / "applications/stray/sources").mkdir(parents=True)
    listed = _homes(a, vault_id)
    assert "library/skill-review" not in listed and "stray" not in listed
