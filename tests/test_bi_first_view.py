"""What a joiner or a new vault's creator sees first (second-PC acceptance F22, F23, 2026-11-06).

F22: a vault holding only 海事 listed AIDC, Aerospace, Robotics, Wireless and three library
entries, from the vault's default list. F23: a joiner's sources say who added them, so that
withdrawing a colleague's file is not a casual click. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_vault import _call, _commit, _ok, _push, _sync, _two_pcs

LIBRARY = ["library/products", "library/technologies", "library/competitors"]


def _listed(ws: Path, vault_id: str) -> list[str]:
    reply = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/skills"))
    return [str(item["home"]) for item in reply["homes"]]


def _homes(ws: Path, vault_id: str) -> list[str]:
    """The domains listed; the library entries are always listed, last."""
    listed = _listed(ws, vault_id)
    assert listed[-len(LIBRARY) :] == LIBRARY
    return listed[: -len(LIBRARY)]


def _profile_homes(ws: Path, vault_id: str) -> list[str]:
    reply = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/profiles"))
    return [str(item["home"]) for item in reply["homes"]]


def test_only_homes_with_something_in_them_are_listed(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    # Made with the default list, and nothing in any of it yet.
    assert _homes(a, vault_id) == []
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/homes", {"name": "海事", "folder": "marine"}))
    assert _homes(a, vault_id) == ["marine"]
    _commit(a, vault_id, "新增領域 海事")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _homes(b, vault_id) == ["marine"]

    # Something in a home makes it one: a question, a source.
    question = {"question": "虛構題？", "must": ["好"], "slug": "q1", "home": "aidc"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/checks", question))
    body = {"dataset": dataset, "name": "n.md", "text": "# 虛構\n",
            "folder": "library/products/sources"}  # fmt: skip
    _ok(_call(a, "POST", "/api/bi/sources", body))
    assert set(_homes(a, vault_id)) == {"marine", "aidc"}
    # The profile list is the same list.
    assert _profile_homes(a, vault_id) == _listed(a, vault_id)


def test_a_shared_source_says_who_added_it(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    body = {"dataset": dataset, "name": "n.md", "text": "# 虛構\n",
            "folder": "applications/aidc/sources"}  # fmt: skip
    _ok(_call(a, "POST", "/api/bi/sources", body))
    _commit(a, vault_id, "加來源")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    listed: Any = _ok(_call(b, "GET", "/api/bi/sources", dataset=dataset))["sources"]
    (source,) = [s for s in listed if s["name"] == "n.md"]
    assert source["shared"] == "pushed"
    assert str(source["added_by"]).split(" ")[0] != "bob" and source["added_by"]
