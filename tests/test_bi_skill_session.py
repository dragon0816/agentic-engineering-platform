"""Session B on a skill of a BI vault (knowledge repositories R3, BI part).

The AI suggests a new text for one skill, without tools and checked by code;
「套用」 stages the skill's next revision, committed and pushed like any change
and read by the other PC. A sample source travels as fenced data. A skill that
needs updating is brought to the current schema this way. The model is
scripted; all data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _commit, _ok, _push, _refused, _sync, _two_pcs

from capabilities.bi_cards.extract import DATA_FENCE
from host_runtime.bi_cards_api import route

NEW_BODY = "類型與資料夾照 schema。\n電源相關的規格表：額定功率一律放在 specs。"


def _skills(ws: Path, vault_id: str) -> dict[str, dict[str, Any]]:
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/skills"))
    return {s["name"]: s for s in listed["skills"]}


def _post(ws: Path, path: str, body: dict[str, Any], model: Scripted | None = None) -> Any:
    ai = _runtime(model, Jobs()) if model is not None else None
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _session(ws: Path, dataset: str, name: str) -> dict[str, Any]:
    body = {"dataset": dataset, "kind": "skill", "target": name}
    return dict(_ok(_post(ws, "/api/bi/sessions", body))["session"])


def test_an_applied_suggestion_is_a_skill_revision_to_commit_and_push(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    before = _skills(a, vault_id)["classify"]
    sheet = {"dataset": dataset, "name": "sheet.md", "text": "虛構電源模組 PSU-9，額定 3 kW。"}
    source = _ok(_post(a, "/api/bi/sources", sheet))
    session = _session(a, dataset, "classify")
    assert session["kind"] == "skill" and session["target_ref"] == "skill:classify"
    model = Scripted(
        {"reply": "多一條規則", "changes": {"recipe": "x"}},  # a key a skill cannot change
        {
            "reply": "加上電源規格的規則。",
            "changes": {"body": NEW_BODY},
            "reasons": ["規格表常把額定功率寫在表頭"],
            "needs_engineering": ["掃描的 PDF 需要 OCR"],
        },
    )
    turn = {"dataset": dataset, "message": "電源規格表的額定功率放在 specs",
            "source_ids": [source["source"]["id"]]}  # fmt: skip
    turned = _ok(_post(a, f"/api/bi/sessions/{session['id']}/turns", turn, model))["session"]
    answer = turned["turns"][-1]
    assert answer["attempts"] == 2 and answer["error"] is None
    suggestion = answer["suggestion"]
    assert suggestion["changes"] == {"body": NEW_BODY}
    assert suggestion["needs_engineering"] == ["掃描的 PDF 需要 OCR"]
    assert [d["key"] for d in suggestion["result"]["diff"]] == ["body"]
    assert answer["sent"]["skill_revision"] == before["revision"]
    # What was sent: the skill and the sample as fenced data, no tools.
    first = model.requests[0]
    sent = "\n".join(m.text for m in first.messages)
    assert "The skill now (revision 1)" in sent and DATA_FENCE in sent
    assert "PSU-9" not in first.messages[0].text  # the sample never goes in the system message
    assert first.output_contract == "aep.bi.skill_suggestion.v1"
    # Nothing changed until 「套用」.
    assert _skills(a, vault_id)["classify"]["body"] == before["body"]
    applied = _ok(_post(a, f"/api/bi/sessions/{session['id']}/apply",
                        {"dataset": dataset, "turn": 1}))  # fmt: skip
    assert applied["skill"]["revision"] == 2
    assert applied["session"]["turns"][1]["applied"]["revision"] == 2
    _refused(_post(a, f"/api/bi/sessions/{session['id']}/apply", {"dataset": dataset, "turn": 1}),
             409, "suggestion_applied")  # fmt: skip
    now = _skills(a, vault_id)["classify"]
    assert now["body"] == NEW_BODY and now["revision"] == 2 and not now["generated"]
    # Committed and pushed like any change; the other PC reads it.
    _commit(a, vault_id, "電源規格的判讀規則")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _skills(b, vault_id)["classify"]["body"] == NEW_BODY


def test_a_skill_session_needs_a_vault_a_skill_and_a_model(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _refused(_post(a, "/api/bi/sessions", {"dataset": dataset, "kind": "skill",
                                           "target": "nobody"}), 404, "skill_unknown")  # fmt: skip
    _refused(_post(a, "/api/bi/sessions", {"dataset": "demo", "kind": "skill",
                                           "target": "classify"}), 400, "not_a_vault")  # fmt: skip
    session = _session(a, dataset, "classify")
    turn = {"dataset": dataset, "message": "更短一點"}
    _refused(_post(a, f"/api/bi/sessions/{session['id']}/turns", turn), 400, "model_unavailable")
    # An answer whose new skill is not valid is asked again, then reported.
    bad = {"reply": "改成摘要", "changes": {"card_types": ["NoSuchType"]}}
    model = Scripted(bad, bad, bad)
    turned = _ok(_post(a, f"/api/bi/sessions/{session['id']}/turns", turn, model))["session"]
    answer = turned["turns"][-1]
    assert answer["suggestion"] is None and answer["error"]["code"] == "model_output_invalid"
    assert "NoSuchType" in answer["error"]["message"]
