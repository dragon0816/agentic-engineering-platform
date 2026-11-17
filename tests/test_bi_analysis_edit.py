"""The Knowledge page's analysis AI changes saved analyses (BI P2, P3).

`docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md`: a proposal on a saved slug is an
edit, shown before and after; what the model leaves out stays; a session on one
analysis keeps its slug; applying refuses when the analysis moved on since the
proposal, and a dashboard may hold edits too. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_analyses import BY_BODY
from test_bi_dashboard_proposal import COUNT, TYPES, _units, _vault
from test_bi_vault import _call, _ok
from test_business_cards_conversation import Conversation

from aep_bi.cards import analyses
from aep_bi.host import bi_analysis_agent, bi_bench
from aep_bi.host.bi_cards_api import route
from host_runtime.host import build_runtime

BODIES_CHART = {"type": "bar", "x": "body", "y": "n"}
PARAM = {"body": {"type": "text", "default": "IEEE"}}


def _session(ws: Path, dataset: str, target: str) -> dict[str, Any]:
    opened = {"dataset": dataset, "kind": "analysis", "target": target}
    return dict(_ok(_call(ws, "POST", "/api/bi/sessions", opened))["session"])


def _turn(
    config: Any, ws: Path, dataset: str, session: dict[str, Any], *replies: dict[str, Any]
) -> tuple[dict[str, Any], Conversation]:
    (host, layout) = config
    with build_runtime(host, layout=layout) as runtime:
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
        body = {"dataset": dataset, "message": "改一下"}
        status, answer = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/turns",
                               {}, body, None, None, bench)  # fmt: skip
        assert status == 200, answer
    return answer, agent


def _apply(ws: Path, dataset: str, session: dict[str, Any], answer: dict[str, Any]) -> Any:
    index = len(answer["session"]["turns"]) - 1
    return route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/apply",
                 {}, {"dataset": dataset, "turn": index})  # fmt: skip


def _save(ws: Path, vault_id: str, **given: Any) -> None:
    analysis = {"title": "kept", "slug": "kept", "kind": "sql", "code": COUNT,
                "chart": {"type": "table"}, **given}  # fmt: skip
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"save": analysis}))


def _proposal(**changes: Any) -> dict[str, Any]:
    return {"title": "標準組織", "slug": "kept", "kind": "sql", "code": BY_BODY,
            "chart": BODIES_CHART, **changes}  # fmt: skip


def test_an_edit_session_shows_the_changes_and_apply_stages_them(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    before = _units(ws, vault_id)
    session = _session(ws, dataset, "kept")
    answer, agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__read", {"slug": "kept"}),
                   ("bi_analysis__propose", _proposal())]},
        {"text": "改成看各標準組織的技術數。"},
    )  # fmt: skip
    turn = answer["session"]["turns"][-1]
    assert turn["error"] is None, turn
    told = "\n".join(m.text for m in agent.requests[1].messages if m.role == "tool")
    assert COUNT in told  # bi_analysis__read returned the saved code
    first = agent.requests[0].messages[-1].text
    assert "older: older" in first  # the context lists the vault's analyses
    edit = turn["suggestion"]["edit"]
    assert [c["field"] for c in edit["changes"]] == ["title", "code", "chart"]
    code = next(c for c in edit["changes"] if c["field"] == "code")
    assert code["before"] == COUNT and code["after"] == BY_BODY
    assert edit["base"] == analyses.digest(analyses.content(before["analysis:kept"]))
    assert edit["preview"]["columns"] == ["type", "n"]  # the saved version's result
    assert turn["suggestion"]["preview"]["columns"] == ["body", "n"]
    assert _units(ws, vault_id) == before  # nothing staged by the proposal

    status, applied = _apply(ws, dataset, session, answer)
    assert status == 200, applied
    unit = _units(ws, vault_id)["analysis:kept"]
    assert unit["code"] == BY_BODY and unit["chart"] == BODIES_CHART and unit["title"] == "標準組織"


def test_a_session_on_one_analysis_keeps_its_slug(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    session = _session(ws, dataset, "kept")
    answer, agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose", _proposal(slug="another"))]},
        {"tools": [("bi_analysis__propose", _proposal())]},
        {"text": "好了。"},
    )  # fmt: skip
    told = "\n".join(m.text for m in agent.requests[1].messages if m.role == "tool")
    assert "代號不能換" in told
    suggestion = answer["session"]["turns"][-1]["suggestion"]
    assert suggestion["analysis"]["slug"] == "kept" and suggestion["edit"]["changes"]
    assert "analysis:another" not in _units(ws, vault_id)


def test_a_saved_slug_in_a_new_session_is_shown_as_an_edit(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    session = _session(ws, dataset, "new")
    answer, _agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose", _proposal())]},
        {"text": "好了。"},
    )  # fmt: skip
    assert answer["session"]["turns"][-1]["suggestion"]["edit"]["changes"]
    assert _apply(ws, dataset, session, answer)[0] == 200
    assert _units(ws, vault_id)["analysis:kept"]["code"] == BY_BODY


def test_what_the_model_leaves_out_stays_and_an_empty_value_clears(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    requires = {"types": ["Technology"], "fields": []}
    _save(ws, vault_id, question="有哪些卡片？", params=PARAM, requires=requires)
    session = _session(ws, dataset, "kept")
    kept_chart = {"type": "bar", "x": "type", "y": "n"}
    same = {"title": "kept", "slug": "kept", "kind": "sql", "code": COUNT, "chart": kept_chart}
    answer, _agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose", same)]},
        {"text": "換成長條圖。"},
    )  # fmt: skip
    edit = answer["session"]["turns"][-1]["suggestion"]["edit"]
    assert [c["field"] for c in edit["changes"]] == ["chart"]
    assert _apply(ws, dataset, session, answer)[0] == 200
    unit = _units(ws, vault_id)["analysis:kept"]
    assert unit["params"] == PARAM and unit["requires"] == requires
    assert unit["question"] == "有哪些卡片？"

    session = _session(ws, dataset, "kept")
    answer, _agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose", {**same, "params": {}, "requires": {}})]},
        {"text": "拿掉參數。"},
    )  # fmt: skip
    edit = answer["session"]["turns"][-1]["suggestion"]["edit"]
    assert [c["field"] for c in edit["changes"]] == ["params", "requires"]
    assert _apply(ws, dataset, session, answer)[0] == 200
    unit = _units(ws, vault_id)["analysis:kept"]
    assert "params" not in unit and "requires" not in unit


def test_an_edit_that_changes_nothing_is_not_applied(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    session = _session(ws, dataset, "kept")
    same = {"title": "kept", "slug": "kept", "kind": "sql", "code": COUNT,
            "chart": {"type": "table"}}  # fmt: skip
    answer, _agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose", same)]},
        {"text": "看起來不用改。"},
    )  # fmt: skip
    assert answer["session"]["turns"][-1]["suggestion"]["edit"]["changes"] == []
    status, refused = _apply(ws, dataset, session, answer)
    assert status == 400 and refused["code"] == "analysis_unchanged", refused


def test_a_change_meanwhile_stops_the_edit(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    session = _session(ws, dataset, "kept")
    answer, _agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose", _proposal())]},
        {"text": "好了。"},
    )  # fmt: skip
    _save(ws, vault_id, title="別人改的")
    before = _units(ws, vault_id)
    status, refused = _apply(ws, dataset, session, answer)
    assert status == 409 and refused["code"] == "analysis_stale", refused
    assert _units(ws, vault_id) == before


def test_a_slug_saved_after_a_new_proposal_is_not_overwritten(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    session = _session(ws, dataset, "new")
    answer, _agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose", _proposal(slug="fresh"))]},
        {"text": "好了。"},
    )  # fmt: skip
    assert "edit" not in answer["session"]["turns"][-1]["suggestion"]
    _save(ws, vault_id, slug="fresh", title="別人先存了")
    before = _units(ws, vault_id)
    status, refused = _apply(ws, dataset, session, answer)
    assert status == 400 and refused["code"] == "analysis_exists", refused
    assert _units(ws, vault_id) == before


def test_a_dashboard_may_change_saved_analyses(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    session = _session(ws, dataset, "new")
    proposal = {"analyses": [_proposal(), TYPES], "order": ["kept", "by-type"]}
    answer, _agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose_dashboard", proposal)]},
        {"text": "好了。"},
    )  # fmt: skip
    dashboard = answer["session"]["turns"][-1]["suggestion"]["dashboard"]
    assert set(dashboard["edits"]) == {"kept"}
    assert "code" in {c["field"] for c in dashboard["edits"]["kept"]["changes"]}
    status, applied = _apply(ws, dataset, session, answer)
    assert status == 200, applied
    units = _units(ws, vault_id)
    assert units["analysis:kept"]["code"] == BY_BODY and "analysis:by-type" in units
    assert analyses.dashboard_layout(units) == {"order": ["kept", "by-type"], "hidden": ["older"]}


def test_a_change_meanwhile_stops_the_whole_dashboard(tmp_path: Path) -> None:
    config, ws, vault_id, dataset = _vault(tmp_path)
    session = _session(ws, dataset, "new")
    proposal = {"analyses": [TYPES, _proposal()], "order": ["kept", "by-type"]}
    answer, _agent = _turn(
        config, ws, dataset, session,
        {"tools": [("bi_analysis__propose_dashboard", proposal)]},
        {"text": "好了。"},
    )  # fmt: skip
    _save(ws, vault_id, title="別人改的")
    before = _units(ws, vault_id)
    status, refused = _apply(ws, dataset, session, answer)
    assert status == 409 and refused["code"] == "analysis_stale", refused
    assert _units(ws, vault_id) == before  # the new analysis was not staged either
