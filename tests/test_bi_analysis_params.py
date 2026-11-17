"""Analysis parameters, requirements and the Dashboard's order on the page routes (BI P1).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.1: the page lists each analysis's
parameter inputs (enum values from the schema) and whether the schema offers
it, runs it with chosen values, and keeps the Dashboard's order and hidden
analyses in `meta:dashboard`, committed and pushed like any unit. All data is
fictional.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _ok, _refused

from aep_bi.cards import analyses, feed, vault
from aep_bi.cards.store import BiStoreError
from scripts import bi_feed_fixtures as fixtures

URL = f"/api/bi/vaults/{fixtures.VAULT_ID}/analyses"


def _joined(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)
    return workspace


def _listed(ws: Path) -> dict[str, Any]:
    return _ok(_call(ws, "GET", URL))


def test_the_page_lists_inputs_offers_and_the_order(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    listed = _listed(ws)
    by_slug = {a["slug"]: a for a in listed["analyses"]}
    assert listed["order"] == ["node-coverage", "accounts-by-region", "tech-updates", "draft-only"]
    assert listed["dashboard"] == {"order": fixtures.LAYOUT["order"], "hidden": []}
    domain = by_slug["accounts-by-region"]["inputs"]["domain"]
    assert domain["default"] == "robotics" and "AIDC" in domain["values"]
    assert by_slug["accounts-by-region"]["params"] == fixtures.DOMAIN  # as stored
    assert all(a["offered"] for a in listed["analyses"])
    ran = _ok(_call(ws, "POST", URL, {"run": "accounts-by-region", "params": {"domain": "AIDC"}}))
    assert ran["params"] == {"domain": "AIDC"} and ran["table"]["rows"] == [["TW", 2], ["US", 2]]
    _refused(_call(ws, "POST", URL, {"run": "accounts-by-region", "params": {"domain": "x"}}),
             400, "param_invalid")  # fmt: skip


def test_an_analysis_the_schema_cannot_answer_is_not_offered(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    given = {"title": "技術領域", "slug": "by-area", "kind": "sql",
             "code": "SELECT count(*) AS n FROM cards",
             "requires": {"fields": ["Account.tech_areas"]}}  # fmt: skip
    _ok(_call(ws, "POST", URL, {"save": given}))
    listed = _listed(ws)
    assert not next(a for a in listed["analyses"] if a["slug"] == "by-area")["offered"]
    assert "by-area" not in listed["order"]


def test_the_dashboard_order_is_a_unit_that_is_committed_and_pushed(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    layout = {"order": ["tech-updates", "node-coverage"], "hidden": ["accounts-by-region"]}
    saved = _ok(_call(ws, "POST", URL, {"dashboard": layout}))
    assert saved["order"] == ["tech-updates", "node-coverage", "draft-only"]
    pending = _ok(_call(ws, "GET", f"/api/bi/vaults/{fixtures.VAULT_ID}/pending"))
    assert "Dashboard 的順序" in {c["label"] for c in pending["uncommitted"]}
    for wrong in ({"order": "x"}, {"hidden": ["Not A Slug"]}, ["x"]):
        _refused(_call(ws, "POST", URL, {"dashboard": wrong}), 400, "dashboard_invalid")
    _ok(_call(ws, "POST", f"/api/bi/vaults/{fixtures.VAULT_ID}/commit", {"purpose": "排序"}))
    _ok(_call(ws, "POST", f"/api/bi/vaults/{fixtures.VAULT_ID}/push", {}))
    units = vault.Vault(ws, fixtures.VAULT_ID).repo.units()
    assert json.loads(units[feed.DASHBOARD_UNIT]) == layout
    # The feed still shows the published v1 order until a new version is published.
    assert feed.listing(ws, fixtures.VAULT_ID)["order"] == fixtures.LAYOUT["order"]


def test_an_ai_proposal_may_declare_parameters(tmp_path: Path) -> None:
    from aep_bi.cards import analysis_session

    ws = _joined(tmp_path)
    found = analyses_run_default(ws)
    proposal = {**fixtures.ANALYSES[0], "slug": "by-region-ai"}
    answer = {"reply": "依地區", "analysis": proposal, "preview": found}
    assert analysis_session.check(answer) == []
    wrong = {**answer, "analysis": {**proposal, "params": {"domain": {"type": "list"}}}}
    assert analysis_session.check(wrong) != []


def analyses_run_default(ws: Path) -> dict[str, Any]:
    from aep_bi.cards import analyses

    return dict(analyses.run_saved(ws, fixtures.VAULT_ID, "accounts-by-region")["table"])


def test_an_enum_value_is_matched_without_case_and_given_as_the_schema_spells_it() -> None:
    # The page sends `aidc`; on market-intel, 30 of 37 panels failed to draw for its `AIDC`.
    declared = {"domain": {"type": "enum", "values": ["wireless", "AIDC"], "default": "wireless"}}
    values = analyses.resolve_params(declared, {"domain": "aidc"}, None, today="2026-11-05")
    assert values["domain"] == "AIDC"
    assert analyses.resolve_params(declared, {}, None, today="2026-11-05")["domain"] == "wireless"
    with pytest.raises(BiStoreError):
        analyses.resolve_params(declared, {"domain": "nowhere"}, None, today="2026-11-05")
