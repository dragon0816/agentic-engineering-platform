"""A vault's Dashboard tab draws its analyses (BI P3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.3: the analyses in the vault's order
with the parameters at the top, `level` badges, the counts summed for the
strip, card names linked; quality stays a coded section. A dataset only on this
PC draws the built-in pack (P5). All data is fictional.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from test_bi_vault import _call, _import, _ok, _row

from aep_bi.cards import analyses, vault
from aep_bi.cards.store import BiStore
from scripts import bi_feed_fixtures as fixtures

DATASET = vault.dataset_name(fixtures.VAULT_ID)


def _joined(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)
    return workspace


def _board(ws: Path, **query: str) -> dict[str, Any]:
    return _ok(_call(ws, "GET", "/api/bi/dashboard", dataset=DATASET, **query))


def test_the_dashboard_is_the_vaults_analyses_in_its_order(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    found = _board(ws, domain="robotics")
    assert found["source"] == "vault" and found["ordered"] is True
    drawn = [s for s in found["sections"] if s.get("analysis")]
    # The working copy's order: the published three, then the pushed draft.
    assert [s["id"] for s in drawn] == [*fixtures.LAYOUT["order"], "draft-only"]
    assert found["sections"][-1]["id"] == "Q"  # quality stays a coded section
    nodes = drawn[0]
    assert nodes["columns"] == ["node", "solutions"]  # `level` became flags
    assert [f["level"] for f in nodes["flags"]] == ["red", "warn", "warn"]
    first = nodes["rows"][0][0]
    assert (first["label"], first["cite"]) == ("Vision Module", "Node:vision-module")  # linked
    assert found["summary"]["red"] >= 1 and found["summary"]["warn"] >= 2
    assert drawn[1]["chart"] == {"type": "bar", "x": "region", "y": "accounts"}
    aidc = _board(ws, domain="AIDC")
    by_region = next(s for s in aidc["sections"] if s["id"] == "accounts-by-region")
    assert [r[1] for r in by_region["rows"]] == [2, 2]  # a TW and a US region, two accounts each


def test_extra_parameters_are_at_the_top_and_hidden_ones_are_not_drawn(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    one = {"title": "某類型的卡片數", "slug": "one-type", "kind": "sql",
           "code": "SELECT count(*) AS n FROM cards WHERE entity_type = :t",
           "params": {"t": {"type": "enum", "values": ["Node", "Account"]}}}  # fmt: skip
    _ok(_call(ws, "POST", f"/api/bi/vaults/{fixtures.VAULT_ID}/analyses", {"save": one}))
    analyses.set_dashboard(
        ws, fixtures.VAULT_ID, {"order": ["one-type"], "hidden": ["tech-updates", "draft-only"]}
    )
    found = _board(ws, domain="robotics")
    assert found["params"]["t"]["values"] == ["Node", "Account"]
    drawn = [s["id"] for s in found["sections"] if s.get("analysis")]
    assert drawn == ["one-type", "accounts-by-region", "node-coverage"]
    counted = next(s for s in found["sections"] if s["id"] == "one-type")
    assert counted["rows"] == [[8]]
    accounts = _board(ws, domain="robotics", **{"param.t": "Account"})
    assert next(s for s in accounts["sections"] if s["id"] == "one-type")["rows"] == [[13]]


def test_results_are_cached_and_a_failure_is_a_note(tmp_path: Path, monkeypatch: Any) -> None:
    ws = _joined(tmp_path)
    _board(ws, domain="robotics")
    ran: list[str] = []
    real = analyses.run

    def counting(db: Path, kind: str, code: str, params: Any = None) -> dict[str, Any]:
        ran.append(kind)
        return real(db, kind, code, params)

    monkeypatch.setattr(analyses, "run", counting)
    _board(ws, domain="robotics")
    assert ran == []  # same analyses, same data, same parameters
    broken = {"title": "壞掉的", "slug": "broken", "kind": "sql", "code": "SELECT 1 AS one"}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{fixtures.VAULT_ID}/analyses", {"save": broken}))
    target = vault.Vault(ws, fixtures.VAULT_ID)
    with target.lock:
        target.repo.stage("analysis:broken", {**analyses.checked(broken)[1], "code": "SELECT x"})
    found = _board(ws, domain="robotics")
    failed = next(s for s in found["sections"] if s["id"] == "broken")
    assert failed["rows"] == [] and failed["note"].startswith("沒有畫出來")


def test_a_dataset_only_on_this_pc_draws_the_built_in_pack(tmp_path: Path) -> None:
    from aep_bi.cards import service
    from aep_bi.cards.store import BiStore

    service.load_demo(BiStore(tmp_path))
    found = _ok(_call(tmp_path, "GET", "/api/bi/dashboard", dataset="demo", domain="robotics"))
    assert found["source"] == "pack" and found["sections"][0]["id"] == "gaps"
    assert found["sections"][-1]["id"] == "Q"
    assert not {"6", "A", "A2", "A3"} & {s["id"] for s in found["sections"]}


def test_the_board_says_whether_there_is_a_sample_card_to_include(tmp_path: Path) -> None:
    # The page offers 「含 SAMPLE 示範卡」 only when there is one (owner 2026-11-19, H1).
    ws = _joined(tmp_path)
    names = [str(row["name"]) for row in BiStore(ws, DATASET).card_rows()]
    assert _board(ws, domain="robotics")["has_sample"] is any(
        name.startswith("SAMPLE-") for name in names
    )
    _import(ws, DATASET, _row("SAMPLE-虛構技術"))
    assert _board(ws, domain="robotics")["has_sample"] is True
