"""Ingest methods and Session B (BI ingest phase 5; `docs/phases/BI_INGEST.md` §9.2, §11 item 9).

A method is a folder of immutable revisions in the dataset; a run with it
records `method:<id>@<rev>`. Session B is one structured model call per turn
with no tools, the samples sent as data and recorded as sent; the person's
「套用」 writes a revision. The acceptance case: the same sample before and
after 「沒有文件依據的需求標成推測」 shows the difference in the comparison,
revert brings the old revision back, nothing reaches the cards, and a schema
upgrade flags the method until a trial under the new schema reaches review.
The model is scripted; no provider is called.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs
from test_bi_extract import NOTE

from capabilities.bi_cards import extract, service
from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

ACTOR = "tester"
RULE = "沒有文件依據的需求標成推測。"
TECH_CSV = "技術,領域,成熟度\nEtherCAT,robotics,mature\nTSN,robotics,growth\nOPC UA,robotics,成熟\n"


class Model:
    """A scripted model that decides from the whole request."""

    def __init__(self, answer: Callable[[ModelRequest], Any]) -> None:
        self.answer = answer
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        given = self.answer(request)
        if isinstance(given, str):
            return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=given)
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, structured_output=given
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _extraction(request: ModelRequest) -> dict[str, Any]:
    """The extractor: a stated need is a fact unless the method's
    instructions say unsupported needs are inferences."""
    inferred = RULE in request.messages[0].text
    need: dict[str, Any] = (
        {"value": ["時間同步(802.1AS)"], "basis": "inference", "reason": "原文沒有寫測試需求"}
        if inferred
        else {"value": ["時間同步(802.1AS)"], "basis": "fact", "quote": "產線機器人之間的同步"}
    )
    return {
        "candidates": [
            {
                "entity_type": "Technology",
                "name": "TSN",
                "fields": {"domain": {"value": "robotics", "basis": "fact", "quote": "產線"}},
            },
            {
                "entity_type": "Application",
                "name": "產線機器人同步",
                "fields": {
                    "technologies": {"value": ["TSN"], "basis": "fact", "quote": "評估 TSN"},
                    "measurement_topics": need,
                },
            },
        ]
    }


def _session_answer(request: ModelRequest) -> dict[str, Any]:
    return {
        "reply": "好，我把這條規則加進判讀規則。",
        "changes": {"instructions": extract.DEFAULT_INSTRUCTIONS + "\n- " + RULE},
        "reasons": ["原文沒有寫測試需求，只寫了評估 TSN"],
        "limits": ["模型仍可能判斷錯誤，請逐卡審核"],
        "needs_engineering": ["掃描的 PDF 需要 OCR，方法做不到"],
    }


def _router(request: ModelRequest) -> Any:
    if request.output_contract == extract.OUTPUT_CONTRACT:
        return _extraction(request)
    return _session_answer(request)


def _call(
    tmp_path: Path, method: str, path: str, body: Any = None, ai: Any = None, **q: Any
) -> Any:
    return route(tmp_path, ACTOR, method, path, q, body, None, ai)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _refused(answer: Any, status: int, code: str) -> dict[str, Any]:
    got, payload = answer
    assert (got, payload.get("code")) == (status, code), payload
    return dict(payload)


def _source(tmp_path: Path, name: str, text: str) -> str:
    body = {"dataset": "demo", "name": name, "text": text}
    return str(_ok(_call(tmp_path, "POST", "/api/bi/sources", body))["source"]["id"])


def _method(tmp_path: Path, method: dict[str, Any]) -> dict[str, Any]:
    return _ok(_call(tmp_path, "POST", "/api/bi/methods", {"dataset": "demo", "method": method}))


def _run(tmp_path: Path, ai: Any, jobs: Jobs | None, **body: Any) -> dict[str, Any]:
    run = _ok(_call(tmp_path, "POST", "/api/bi/runs", {"dataset": "demo", **body}, ai))["run"]
    if jobs is not None:
        jobs.run_all()
    return dict(_ok(_call(tmp_path, "GET", f"/api/bi/runs/{run['id']}", dataset="demo"))["run"])


def _detail(tmp_path: Path, method_id: str, **q: Any) -> dict[str, Any]:
    return _ok(_call(tmp_path, "GET", f"/api/bi/methods/{method_id}", dataset="demo", **q))


def _cards(tmp_path: Path) -> bytes:
    return (tmp_path / "bi" / "demo" / "bi.sqlite").read_bytes()


def _upgrade(tmp_path: Path) -> None:
    """Publish bi.schema/v1.1@1.2.0 with one more field and move demo to it."""
    draft = _ok(_call(tmp_path, "POST", "/api/bi/schema-drafts", {"base": "bi.schema/v1.1"}))
    draft_id = draft["draft"]["id"]
    document = copy.deepcopy(draft["document"])
    tech = next(t for t in document["types"] if t["name"] == "Technology")
    tech["fields"].append(
        {"name": "price_band", "label": "價格帶", "kind": "str", "class": "sourced"}
    )
    path = f"/api/bi/schema-drafts/{draft_id}/revisions"
    _ok(_call(tmp_path, "POST", path, {"document": document}))
    _ok(_call(tmp_path, "POST", f"/api/bi/schema-drafts/{draft_id}/publish", {}))
    target = {"to": "bi.schema/v1.1@1.2.0"}
    preview = _ok(_call(tmp_path, "POST", "/api/bi/datasets/demo/schema/preview", target))
    token = {**target, "preview_token": preview["preview_token"]}
    _ok(_call(tmp_path, "POST", "/api/bi/datasets/demo/schema/apply", token))


def test_session_b_shows_the_difference_reverts_and_writes_nothing(tmp_path: Path) -> None:
    service.load_demo(BiStore(tmp_path))
    jobs, model = Jobs(), Model(_router)
    ai = AiRuntime(model=lambda: (model, "test-model"), background=jobs)
    before = _cards(tmp_path)
    note = _source(tmp_path, "meeting.md", NOTE)
    made = _method(tmp_path, {"name": "會議紀錄", "mode": "llm"})
    method_id = made["method"]["id"]
    assert made["revision"] == 1 and made["document"]["format"] == "aep.bi.method/v1"
    assert made["document"]["instructions"] == extract.DEFAULT_INSTRUCTIONS
    assert made["document"]["schema_ref"] == "bi.schema/v1.1@1.1.0"
    assert made["status"]["schema_changed"] is False

    first = _run(tmp_path, ai, jobs, kind="trial", source_id=note, method_id=method_id)
    assert first["status"] == "review" and first["method_ref"] == f"method:{method_id}@1"

    # Session B: one model call, no tools, the sample as data, what was sent recorded.
    session = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/sessions",
            {"dataset": "demo", "kind": "method", "target": method_id},
        )
    )["session"]
    asked = len(model.requests)
    turned = _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/sessions/{session['id']}/turns",
            {"dataset": "demo", "message": RULE, "source_ids": [note]},
            ai,
        )
    )["session"]
    assert len(model.requests) == asked + 1
    request = model.requests[-1]
    assert request.tools == () and not request.requirements.tool_calling
    assert request.output_contract == "aep.bi.method_suggestion.v1"
    assert "忽略以上規則" not in request.messages[0].text
    assert any("忽略以上規則" in m.text and extract.DATA_FENCE in m.text for m in request.messages)
    assert first["id"] in request.messages[1].text  # the last trial's candidates went along
    reply = turned["turns"][-1]
    assert reply["model"] == "test-model" and reply["error"] is None
    sent = reply["sent"]
    assert sent["sources"][0]["name"] == "meeting.md"
    assert sent["sources"][0]["classification"] == "INTERNAL"
    assert sent["excerpt_chars"] == len(NOTE) and sent["runs"] == [first["id"]]
    suggestion = reply["suggestion"]
    assert suggestion["needs_engineering"] == ["掃描的 PDF 需要 OCR，方法做不到"]
    assert [d["key"] for d in suggestion["result"]["diff"]] == ["instructions"]
    assert _detail(tmp_path, method_id)["revision"] == 1  # nothing changes before 「套用」

    applied = _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/sessions/{session['id']}/apply",
            {"dataset": "demo", "turn": 1},
        )
    )
    assert applied["revision"] == 2 and RULE in applied["document"]["instructions"]
    assert applied["method"]["revisions"][-1]["source"] == "ai"
    _refused(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/sessions/{session['id']}/apply",
            {"dataset": "demo", "turn": 1},
        ),
        409,
        "suggestion_applied",
    )

    second = _run(tmp_path, ai, jobs, kind="trial", source_id=note, method_id=method_id)
    assert second["method_ref"] == f"method:{method_id}@2"
    compared = _ok(
        _call(
            tmp_path,
            "GET",
            "/api/bi/runs/compare",
            dataset="demo",
            left=first["id"],
            right=second["id"],
        )
    )
    assert compared["added"] == [] and compared["removed"] == []
    (changed,) = compared["changed"]
    assert changed["entity_type"] == "Application"
    (field,) = changed["fields"]
    assert field["field"] == "measurement_topics" and field["change"] == "basis"
    assert (field["before"]["basis"], field["after"]["basis"]) == ("fact", "inference")
    assert compared["counts"]["right"]["inferences"] == compared["counts"]["left"]["inferences"] + 1
    assert "inference" in changed["warnings_added"]

    reverted = _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/methods/{method_id}/revert",
            {"dataset": "demo", "rev": 1},
        )
    )
    assert reverted["revision"] == 3
    assert reverted["document"]["instructions"] == extract.DEFAULT_INSTRUCTIONS
    assert reverted["method"]["revisions"][-1]["copied_from"] == 1
    assert [d["key"] for d in reverted["diff"]] == ["instructions"]

    # The session survives a restart: it is read back from the staging store.
    stored = _ok(_call(tmp_path, "GET", f"/api/bi/sessions/{session['id']}", dataset="demo"))
    assert [t["role"] for t in stored["session"]["turns"]] == ["user", "assistant"]
    assert stored["session"]["turns"][1]["applied"]["rev"] == 2
    assert _cards(tmp_path) == before

    # A schema upgrade flags the method until a trial under the new schema reaches review.
    _upgrade(tmp_path)
    flagged = _detail(tmp_path, method_id)
    assert flagged["status"]["schema_changed"] is True
    assert flagged["status"]["message"] == "schema 已更新，請重新試跑確認"
    listed = _ok(_call(tmp_path, "GET", "/api/bi/methods", dataset="demo"))["methods"]
    assert listed[0]["status"]["schema_changed"] is True
    _refused(
        _call(
            tmp_path,
            "POST",
            "/api/bi/runs",
            {"dataset": "demo", "kind": "ingest", "source_id": note, "method_id": method_id},
            ai,
        ),
        409,
        "schema_changed",
    )
    _run(tmp_path, ai, jobs, kind="trial", source_id=note, method_id=method_id)
    cleared = _detail(tmp_path, method_id)
    assert cleared["status"]["schema_changed"] is False
    assert cleared["status"]["rechecked"]["schema_ref"] == "bi.schema/v1.1@1.2.0"
    ingest = _run(tmp_path, ai, jobs, kind="ingest", source_id=note, method_id=method_id)
    assert ingest["status"] == "review" and ingest["kind"] == "ingest"


def test_a_rules_method_with_checks_compares_and_trials_cannot_commit(tmp_path: Path) -> None:
    service.load_demo(BiStore(tmp_path))
    before = _cards(tmp_path)
    table = _source(tmp_path, "tech.csv", TECH_CSV)
    recipe: dict[str, Any] = {
        "passes": [
            {
                "id": "tech",
                "entity_type": "Technology",
                "mapping": {"columns": {"技術": "name", "領域": "domain", "成熟度": "maturity"}},
            }
        ]
    }
    method = {
        "name": "技術表",
        "mode": "rules",
        "recipe": recipe,
        "checks": [{"entity_type": "Technology", "require": ["standard_body"]}],
    }
    made = _method(tmp_path, method)
    method_id = made["method"]["id"]
    assert made["document"]["types"] == ["Technology"]
    first = _run(tmp_path, None, None, kind="trial", source_id=table, method_id=method_id)
    assert first["method_ref"] == f"method:{method_id}@1"
    detail = _ok(_call(tmp_path, "GET", f"/api/bi/runs/{first['id']}", dataset="demo"))
    for candidate in detail["candidates"]:
        assert "method_check" in [e["code"] for e in candidate["errors"]]
    _refused(
        _call(tmp_path, "POST", f"/api/bi/runs/{first['id']}/commit", {"dataset": "demo"}),
        409,
        "run_trial",
    )

    fixed = copy.deepcopy(recipe)
    fixed["passes"][0]["mapping"]["enum_aliases"] = {"maturity": {"成熟": "mature"}}
    saved = _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/methods/{method_id}/revisions",
            {
                "dataset": "demo",
                "method": {"name": "技術表", "mode": "rules", "recipe": fixed},
                "note": "成熟 → mature",
            },
        )
    )
    assert saved["revision"] == 2 and {d["key"] for d in saved["diff"]} == {"recipe", "checks"}
    second = _run(tmp_path, None, None, kind="trial", source_id=table, method_id=method_id)
    compared = _ok(
        _call(
            tmp_path,
            "GET",
            "/api/bi/runs/compare",
            dataset="demo",
            left=first["id"],
            right=second["id"],
        )
    )
    assert compared["counts"]["left"]["errors"] > compared["counts"]["right"]["errors"]
    assert compared["same"] + len(compared["changed"]) == 3
    assert _cards(tmp_path) == before

    other = _source(tmp_path, "tech2.csv", TECH_CSV + "PROFINET,robotics,mature\n")
    other_run = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/runs",
            {
                "dataset": "demo",
                "kind": "trial",
                "source_id": other,
                "recipe": {"name": "技術表", **recipe},
            },
        )
    )["run"]
    assert other_run["method_ref"] == "recipe:inline"
    _refused(
        _call(
            tmp_path,
            "GET",
            "/api/bi/runs/compare",
            dataset="demo",
            left=first["id"],
            right=other_run["id"],
        ),
        400,
        "compare_sources_differ",
    )
    _refused(
        _call(tmp_path, "GET", "/api/bi/runs/compare", dataset="demo", left=first["id"], right="x"),
        404,
        "run_unknown",
    )


def test_method_checks_and_session_failures(tmp_path: Path) -> None:
    note = _source(tmp_path, "meeting.md", NOTE)
    _refused(
        _call(tmp_path, "POST", "/api/bi/methods", {"dataset": "demo", "method": {"name": ""}}),
        400,
        "method_invalid",
    )
    bad = {"name": "x", "mode": "llm", "types": ["Nope"]}
    _refused(
        _call(tmp_path, "POST", "/api/bi/methods", {"dataset": "demo", "method": bad}),
        400,
        "method_invalid",
    )
    method_id = _method(tmp_path, {"name": "會議", "mode": "llm"})["method"]["id"]
    _refused(
        _call(tmp_path, "GET", "/api/bi/methods/0123456789ab", dataset="demo"),
        404,
        "method_unknown",
    )
    session = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/sessions",
            {"dataset": "demo", "kind": "method", "target": method_id},
        )
    )["session"]
    path = f"/api/bi/sessions/{session['id']}/turns"
    body = {"dataset": "demo", "message": "加一條規則", "source_ids": [note]}
    assert _ok(_call(tmp_path, "GET", "/api/bi/ai", dataset="demo"))["available"] is False
    _refused(_call(tmp_path, "POST", path, body, None), 400, "model_unavailable")
    unchanged = _ok(_call(tmp_path, "GET", f"/api/bi/sessions/{session['id']}", dataset="demo"))
    assert unchanged["session"]["turns"] == []

    # An unknown change key is fed back; the third unusable answer ends the turn.
    wrong = Model(lambda request: {"reply": "好", "changes": {"parser": "ocr"}})
    ai = AiRuntime(model=lambda: (wrong, "test-model"), background=Jobs())
    turned = _ok(_call(tmp_path, "POST", path, body, ai))["session"]
    assert len(wrong.requests) == 3
    assert "unknown keys" in wrong.requests[1].messages[-1].text
    failed = turned["turns"][-1]
    assert failed["suggestion"] is None and failed["error"]["code"] == "model_output_invalid"
    _refused(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/sessions/{session['id']}/apply",
            {"dataset": "demo", "turn": 1},
        ),
        404,
        "turn_unknown",
    )
    assert not (tmp_path / "bi" / "demo" / "bi.sqlite").exists()
