"""Each domain's own Dashboard, and giving what exists to the domains (`BI_PAGE_SIMPLE.md` §12).

Owner, 2026-11-05: 「每個領域也要有各自的benchmark 問題和dashboard」. The vault's Dashboard and
what the feed reads stay as they are; a domain's starts empty; a panel that shows the whole vault
says so.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _commit, _ok, _push, _refused, _sync, _two_pcs

from capabilities.bi_cards import analyses, board, feed, packs, vault
from capabilities.bi_cards.store import BiStore

BY_DOMAIN = {
    "title": "這個領域的卡片數",
    "slug": "by-domain",
    "kind": "sql",
    "code": "SELECT :domain AS d, count(*) AS n FROM cards",
    "params": {"domain": {"type": "text", "default": "x"}},
    "chart": {"type": "table"},
}
ALL_CARDS = {
    "title": "全部卡片數",
    "slug": "all-cards",
    "kind": "sql",
    "code": "SELECT count(*) AS n FROM cards",
    "chart": {"type": "table"},
}
DECLARED_ONLY = {**ALL_CARDS, "slug": "declared", "params": BY_DOMAIN["params"]}


def _post(ws: Path, vault_id: str, body: dict[str, Any]) -> Any:
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/analyses", body)


def _listing(ws: Path, vault_id: str, home: str | None = None) -> dict[str, Any]:
    query = {"home": home} if home else {}
    return _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/analyses", **query))


def _saved(ws: Path, vault_id: str, *items: dict[str, Any]) -> None:
    for item in items:
        _ok(_post(ws, vault_id, {"save": item}))


def _board(ws: Path, dataset: str, home: str | None) -> dict[str, Any]:
    return board.board(ws, BiStore(ws, dataset), "robotics", False, {}, home)


def test_a_new_domain_starts_empty_and_the_vaults_dashboard_is_as_it_was(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    _saved(a, vault_id, BY_DOMAIN, ALL_CARDS)
    before = _listing(a, vault_id)
    assert before["order"] == ["all-cards", "by-domain"]

    assert _listing(a, vault_id, "aidc")["order"] == []
    drawn = _board(a, dataset, "aidc")
    assert drawn["sections"] == [] and drawn["home"] == "aidc"

    # The vault's Dashboard still shows everything, with its data-quality section.
    whole = _board(a, dataset, None)
    assert [s["id"] for s in whole["sections"]][:2] == ["all-cards", "by-domain"]
    assert len(whole["sections"]) == 3


def test_a_domains_dashboard_keeps_its_own_order_and_hidden(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _saved(a, vault_id, BY_DOMAIN, ALL_CARDS)
    layout = {"order": ["by-domain", "all-cards"], "hidden": []}
    reply = _ok(_post(a, vault_id, {"dashboard": layout, "home": "aidc"}))
    assert reply["order"] == ["by-domain", "all-cards"] and reply["home"] == "aidc"
    hidden = {"order": ["by-domain", "all-cards"], "hidden": ["all-cards"]}
    _ok(_post(a, vault_id, {"dashboard": hidden, "home": "wireless"}))

    assert _listing(a, vault_id, "aidc")["order"] == ["by-domain", "all-cards"]
    assert _listing(a, vault_id, "wireless")["order"] == ["by-domain"]
    assert _listing(a, vault_id, "robotics")["order"] == []
    # Nothing moved on the vault's.
    assert _listing(a, vault_id)["order"] == ["all-cards", "by-domain"]
    units = vault.Vault(a, vault_id).repo.working_units()
    assert "meta:dashboard:aidc" in units and "meta:dashboard:wireless" in units
    assert analyses.DASHBOARD_UNIT not in units or json.loads(units[analyses.DASHBOARD_UNIT]) == {
        "order": [],
        "hidden": [],
    }


@pytest.mark.parametrize(
    ("params", "code", "reads"),
    [
        (True, "SELECT :domain", True),
        (True, 'x = PARAMS["domain"]', True),
        (True, "x = PARAMS.get('domain')", True),
        # A built-in analysis: the helpers set `D`, and its own code passes it on.
        (True, 'D = str(PARAMS.get("domain") or "robotics")\nresult = out(f(cards(), D))', True),
        # The helpers alone, with nothing using `D`.
        (True, 'D = str(PARAMS.get("domain") or "robotics")\nresult = out(g(cards()))', False),
        (True, "SELECT count(*) FROM cards", False),
        (False, "SELECT :domain", False),
    ],
)
def test_whether_an_analysis_narrows_to_a_domain(params: bool, code: str, reads: bool) -> None:
    item = {"code": code, "params": {"domain": {}} if params else {}}
    assert analyses.uses_domain(item) is reads


def test_every_built_in_analysis_that_takes_a_domain_is_seen_to_read_it() -> None:
    # The one the pack declares for every card is the exception it names.
    pack = packs.default_pack()["analyses"]
    declared = [a for a in pack if "domain" in (a.get("params") or {})]
    assert declared
    assert [a["slug"] for a in declared if not analyses.uses_domain(a)] == []


def test_a_panel_asks_with_the_domain_and_one_that_cannot_says_so(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    _saved(a, vault_id, BY_DOMAIN, ALL_CARDS, DECLARED_ONLY)
    listed = {x["slug"]: x["filters_domain"] for x in _listing(a, vault_id)["analyses"]}
    assert listed == {"by-domain": True, "all-cards": False, "declared": False}
    _ok(
        _post(
            a,
            vault_id,
            {"dashboard": {"order": ["by-domain", "all-cards", "declared"]}, "home": "aidc"},
        )
    )
    store = BiStore(a, dataset)
    drawn = {
        s["id"]: s for s in board.board(a, store, "aidc-domain", False, {}, "aidc")["sections"]
    }
    assert drawn["by-domain"]["rows"][0][0] == "aidc-domain"
    assert "whole_vault" not in drawn["by-domain"]
    # Declaring the parameter is not enough: its code never reads it.
    assert drawn["declared"]["whole_vault"] and drawn["all-cards"]["whole_vault"]
    assert drawn["all-cards"]["title"].endswith("（全庫資料）")


def test_a_colleague_gets_a_domains_dashboard_through_sync(tmp_path: Path) -> None:
    drive, vault_id, _dataset, a, b = _two_pcs(tmp_path)
    _saved(a, vault_id, ALL_CARDS)
    _ok(_post(a, vault_id, {"dashboard": {"order": ["all-cards"]}, "home": "aidc"}))
    _commit(a, vault_id, "aidc 的 Dashboard")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _listing(b, vault_id, "aidc")["order"] == ["all-cards"]


def test_two_domains_never_meet_on_a_dashboard(tmp_path: Path) -> None:
    drive, vault_id, _dataset, a, b = _two_pcs(tmp_path)
    _saved(a, vault_id, ALL_CARDS)
    _commit(a, vault_id, "分析")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    _ok(_post(a, vault_id, {"dashboard": {"order": ["all-cards"]}, "home": "aidc"}))
    _ok(_post(b, vault_id, {"dashboard": {"order": ["all-cards"]}, "home": "wireless"}))
    _commit(a, vault_id, "a")
    _commit(b, vault_id, "b")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    assert _push(b, vault_id)["status"] == "pushed"


def test_what_the_feed_reads_is_not_changed_by_a_domains_dashboard() -> None:
    units = {
        feed.DASHBOARD_UNIT: json.dumps({"order": ["c", "a"], "hidden": ["x"]}),
        "meta:dashboard:aidc": json.dumps({"order": ["x"], "hidden": ["a", "c"]}),
    }
    assert feed.order(units, ["a", "b", "c", "x"]) == ["c", "a", "b"]
    assert feed.dashboard_layout(units) == {"order": ["c", "a"], "hidden": ["x"]}


def test_a_home_that_is_no_home_is_refused(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    _refused(_post(a, vault_id, {"dashboard": {"order": []}, "home": "../x"}), 400, "home_invalid")
    _refused(
        _call(a, "GET", "/api/bi/dashboard", dataset=dataset, home="../x"), 400, "home_invalid"
    )


# -- a dry run, then one step ------------------------------------------------------------------


def _questions(ws: Path, vault_id: str, *texts: str) -> None:
    for number, text in enumerate(texts):
        body = {"question": text, "slug": f"q{number}"}
        _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/checks", body))


@pytest.mark.parametrize(
    ("text", "suggested"),
    [
        ("wireless：Wi-Fi 7 影響哪些節點？", "wireless"),
        ("AIDC：虛構公司的營收是多少？", "aidc"),
        ("Robotics: 虛構題？", "robotics"),
        ("這是 aerospace 的題目嗎？", "aerospace"),
        ("誰是虛構供應商？", None),
        ("aidc 和 wireless 有什麼不同？", None),
        ("paidc 不是一個領域", None),
    ],
)
def test_the_plan_suggests_a_questions_domain_from_what_it_says(
    tmp_path: Path, text: str, suggested: str | None
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _questions(a, vault_id, text)
    plan = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/assign-plan"))
    (row,) = plan["questions"]
    assert row["suggested"] == suggested and row["basis"]


def test_the_plan_tells_a_shared_panel_from_a_whole_vault_one_and_writes_nothing(
    tmp_path: Path,
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    named = {**ALL_CARDS, "slug": "named", "title": "AIDC 的節點數"}
    _saved(a, vault_id, BY_DOMAIN, ALL_CARDS, named)
    repo = vault.Vault(a, vault_id).repo
    before = repo.working_units()
    plan = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/assign-plan"))
    assert repo.working_units() == before
    rows = {r["slug"]: r for r in plan["analyses"]}
    assert rows["by-domain"]["kind"] == "shared"
    assert set(rows["by-domain"]["suggested"]) >= {"aidc", "wireless", "robotics"}
    assert "library/products" not in rows["by-domain"]["suggested"]
    assert rows["all-cards"]["kind"] == "whole_vault" and rows["all-cards"]["suggested"] == []
    assert rows["named"]["kind"] == "one_domain" and rows["named"]["suggested"] == ["aidc"]


def test_an_approved_list_applies_in_one_step_uncommitted(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _questions(a, vault_id, "aidc：虛構？", "wireless：虛構？")
    _saved(a, vault_id, BY_DOMAIN, ALL_CARDS)
    before = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))["uncommitted"]
    reply = _ok(
        _call(
            a,
            "POST",
            f"/api/bi/vaults/{vault_id}/assign",
            {
                "questions": {
                    "check:question:main/q0": "aidc",
                    "check:question:main/q1": "wireless",
                },
                "analyses": {"by-domain": ["aidc", "wireless"], "all-cards": []},
            },
        )
    )
    assert reply["questions"] == 2 and reply["dashboards"] == 2
    checks = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/checks"))
    assert {q["slug"]: q["home"] for q in checks["questions"]} == {"q0": "aidc", "q1": "wireless"}
    assert _listing(a, vault_id, "aidc")["order"] == ["by-domain"]
    assert _listing(a, vault_id, "wireless")["order"] == ["by-domain"]
    # The whole-vault panel stays on the vault's Dashboard, which did not move.
    assert _listing(a, vault_id)["order"] == ["all-cards", "by-domain"]
    after = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))["uncommitted"]
    assert len(after) > len(before)
    assert not _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))["commits"][1:]


@pytest.mark.parametrize(
    "body",
    [
        {"questions": {"check:question:main/none": "aidc"}},
        {"questions": {"card:x": "aidc"}},
        {"questions": {"check:question:main/q0": "nowhere"}},
        {"analyses": {"none": ["aidc"]}},
        {"analyses": {"by-domain": ["nowhere"]}},
        {"analyses": {"by-domain": "aidc"}},
    ],
)
def test_a_list_with_anything_wrong_applies_nothing(tmp_path: Path, body: dict[str, Any]) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _questions(a, vault_id, "aidc：虛構？")
    _saved(a, vault_id, BY_DOMAIN)
    repo = vault.Vault(a, vault_id).repo
    before = repo.working_units()
    good = {"questions": {"check:question:main/q0": "aidc"}}
    _refused(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/assign", {**good, **body}),
        400,
        "assign_invalid",
    )
    assert repo.working_units() == before
