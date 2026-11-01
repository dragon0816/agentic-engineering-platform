"""The analysis AI proposes a dashboard, applied in one step (BI K1).

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` K1: on the Agent harness
the analysis AI calls `bi_analysis__propose_dashboard` with new analyses and the
Dashboard's order; each analysis is run and checked like one proposal, a
problem goes back to the model, and nothing is staged until the person applies
it. 「套用」 stages every analysis and `meta:dashboard` together; the vault's
analyses not in the order are hidden, never deleted. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_analyses import BY_BODY
from test_bi_vault import _call, _import, _ok, _row
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from capabilities.bi_cards import analyses, analysis_session, vault
from capabilities.bi_cards.store import BiStoreError
from host_runtime import bi_analysis_agent, bi_bench, skill_packs
from host_runtime.assets import shipped
from host_runtime.bi_cards_api import route
from host_runtime.host import build_runtime

COUNT = "SELECT entity_type AS type, count(*) AS n FROM cards GROUP BY 1 ORDER BY 1"
BODIES = {"title": "各標準組織的技術數", "slug": "by-body", "kind": "sql", "code": BY_BODY,
          "chart": {"type": "bar", "x": "body", "y": "n"}}  # fmt: skip
TYPES = {"title": "各類型的卡片數", "slug": "by-type", "kind": "sql", "code": COUNT,
         "chart": {"type": "table"}}  # fmt: skip


def _vault(tmp_path: Path) -> tuple[Any, Path, str, str]:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    ws = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(_call(ws, "POST", "/api/bi/vaults", {
        "path": str(shared), "title": "Market", "purpose": "虛構", "schema": "bi.schema/v1.1",
        "author": "alice", "default_pack": False}))  # fmt: skip
    vault_id, dataset = made["vault"]["id"], made["vault"]["dataset"]
    _import(ws, dataset, _row("TSN", standard_body="IEEE"), _row("PROFINET", standard_body="IEEE"),
            _row("EtherCAT", standard_body="ETG"))  # fmt: skip
    # Already in the vault: one analysis the new Dashboard keeps, one it hides.
    for slug in ("kept", "older"):
        _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"save": {
            "title": slug, "slug": slug, "kind": "sql", "code": COUNT,
            "chart": {"type": "table"}}}))  # fmt: skip
    return (config, layout), ws, vault_id, dataset


def _turn(config: Any, ws: Path, dataset: str, *replies: dict[str, Any]) -> tuple[Any, Any]:
    opened = {"dataset": dataset, "kind": "analysis", "target": "new"}
    session = _ok(_call(ws, "POST", "/api/bi/sessions", opened))["session"]
    with build_runtime(config[0], layout=config[1]) as runtime:
        gateway = runtime.agent.gateway
        agent = Conversation()
        gateway.router.model = agent
        agent.then(*replies)
        bench = bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {},
            extract_for=lambda _v, _a: lambda c: [],
            background=lambda _t, work: work(),
            analysis_asker_for=lambda d, a: bi_analysis_agent.harness_asker(
                gateway, ws, d, a, "engineering"
            ),
        )
        body = {"dataset": dataset, "message": "做一個標準與卡片類型的 Dashboard"}
        status, answer = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/turns",
                               {}, body, None, None, bench)  # fmt: skip
        assert status == 200, answer
    return session, (answer, agent)


def _units(ws: Path, vault_id: str) -> dict[str, Any]:
    return dict(vault.Vault(ws, vault_id).repo.working_units())


def test_the_ai_proposes_a_dashboard_and_one_apply_stages_it(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    before = _units(ws, vault_id)
    wrong = {"analyses": [BODIES, TYPES], "order": ["by-body", "nowhere"]}
    right = {"reply": "Dashboard", "analyses": [BODIES, TYPES],
             "order": ["by-body", "kept", "by-type"]}  # fmt: skip
    session, (answer, agent) = _turn(
        config, ws, dataset,
        {"tools": [("bi_analysis__propose_dashboard", wrong)]},
        {"tools": [("bi_analysis__propose_dashboard", right)]},
        {"text": "IEEE 的技術最多；下面是各類型的卡片數。"},
    )  # fmt: skip
    turn = answer["session"]["turns"][-1]
    assert turn["error"] is None, turn
    assert "bi_analysis__propose_dashboard" in {t.name for t in agent.requests[0].tools}
    told = "\n".join(m.text for m in agent.requests[1].messages if m.role == "tool")
    assert "nowhere" in told  # the unknown slug went back to the model
    suggestion = turn["suggestion"]
    assert suggestion["analysis"] is None
    assert suggestion["dashboard"]["order"] == ["by-body", "kept", "by-type"]
    assert [a["slug"] for a in suggestion["dashboard"]["analyses"]] == ["by-body", "by-type"]
    assert suggestion["previews"]["by-body"]["rows"] == [["IEEE", 2], ["ETG", 1]]
    assert {d["key"] for d in suggestion["result"]["diff"]} == {
        "analysis:by-body", "analysis:by-type", "meta:dashboard"
    }  # fmt: skip
    assert _units(ws, vault_id) == before  # nothing staged by the proposal

    index = len(answer["session"]["turns"]) - 1
    status, applied = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/apply",
                            {}, {"dataset": dataset, "turn": index})  # fmt: skip
    assert status == 200, applied
    assert applied["units"] == ["analysis:by-body", "analysis:by-type", "meta:dashboard"]
    units = _units(ws, vault_id)
    assert units["analysis:by-body"]["chart"] == BODIES["chart"]
    layout = analyses.dashboard_layout(units)
    assert layout == {"order": ["by-body", "kept", "by-type"], "hidden": ["older"]}
    assert "analysis:older" in units  # hidden, never deleted
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/analyses"))
    assert listed["order"][:3] == ["by-body", "kept", "by-type"]
    again = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/apply",
                  {}, {"dataset": dataset, "turn": index})  # fmt: skip
    assert again[0] == 409 and again[1]["code"] == "suggestion_applied"


def test_a_slug_saved_meanwhile_stops_the_whole_apply(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    right = {"analyses": [BODIES, TYPES], "order": ["by-body", "by-type"]}
    session, (answer, _agent) = _turn(
        config, ws, dataset,
        {"tools": [("bi_analysis__propose_dashboard", right)]},
        {"text": "好了。"},
    )  # fmt: skip
    analyses.save(ws, vault_id, {**TYPES})
    before = _units(ws, vault_id)
    index = len(answer["session"]["turns"]) - 1
    status, refused = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/apply",
                            {}, {"dataset": dataset, "turn": index})  # fmt: skip
    assert status == 400 and refused["code"] == "analysis_exists", refused
    assert _units(ws, vault_id) == before  # nothing staged


def test_a_broken_analysis_in_a_dashboard_goes_back_to_the_model(tmp_path: Path) -> None:
    config, ws, _vault_id, dataset = _vault(tmp_path)
    broken = {**TYPES, "chart": {"type": "bar", "x": "type", "y": "count"}}
    fixed = {"analyses": [BODIES, TYPES], "order": ["by-body", "by-type"]}
    _session, (answer, agent) = _turn(
        config, ws, dataset,
        {"tools": [("bi_analysis__propose_dashboard",
                    {"analyses": [BODIES, broken], "order": ["by-body", "by-type"]})]},
        {"tools": [("bi_analysis__propose_dashboard", fixed)]},
        {"text": "好了。"},
    )  # fmt: skip
    told = "\n".join(m.text for m in agent.requests[1].messages if m.role == "tool")
    assert "by-type" in told and "欄位" in told
    turn = answer["session"]["turns"][-1]
    assert turn["attempts"] == 2 and turn["suggestion"]["dashboard"]["order"] == [
        "by-body",
        "by-type",
    ]


@pytest.mark.parametrize(
    ("order", "proposed", "says"),
    [
        ([], ["a"], "清單"),
        (["a", "a"], ["a"], "重複"),
        (["a", "Not A Slug"], ["a"], "清單"),
        (["a", "x"], ["a"], "x"),
    ],
)
def test_the_order_names_distinct_proposed_or_saved_analyses(
    order: list[str], proposed: list[str], says: str
) -> None:
    problem = analysis_session.order_problem(order, proposed, ["saved"])
    assert problem is not None and says in problem
    assert analysis_session.order_problem(["saved", "a"], ["a"], ["saved"]) is None
    assert analysis_session.order_problem(["a"], ["a", "a"], []) is not None


def test_a_dashboard_without_analyses_or_order_is_not_a_suggestion() -> None:
    assert analysis_session.check({"reply": "x", "dashboard": {"analyses": [], "order": []}})
    assert analysis_session.check({"reply": "x", "dashboard": "nope"})
    with pytest.raises(BiStoreError):
        analyses.checked({"slug": "x"})
