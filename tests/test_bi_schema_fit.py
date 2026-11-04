"""Schema fit per knowledge item (proposal §8.1): every item is recorded with why, what
does not fit is kept, and nothing registers without review. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_card_links import _put, _row
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok, _two_pcs

from capabilities.bi_cards import catalog, profile, vault
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route

NOTE = (
    "# 虛構筆記\n\nFAKE-ROVER 的負載是 30 公斤。\n太空任務 FAKE-MISSION 要追蹤參與公司與里程碑。\n"
)
FOLDER = "applications/aidc/sources"
LOAD = "FAKE-ROVER 的負載是 30 公斤"
MISSION = "太空任務 FAKE-MISSION 要追蹤參與公司與里程碑"
FOUR = {
    "unit_boundary": "一個任務一張卡",
    "why_not_existing": "沒有卡型有里程碑",
    "why_independent": "有自己的時程",
    "business_use": "查任務進度",
}
PROFILE = {
    "format": "aep.bi.profile/v1",
    "application": "aidc",
    "types": {"CustomerProduct": {"fields": {"product_name": {"use": "required"}}}},
}
CANDIDATE = {
    "entity_type": "CustomerProduct",
    "name": "FAKE-ROVER",
    "fields": {"product_name": {"value": "FAKE-ROVER", "basis": "fact", "quote": "FAKE-ROVER"}},
}
EXTEND: dict[str, Any] = {
    "summary": "產品的負載",
    "action": ["update_card", "extend_schema"],
    "reason": "負載沒有欄位",
    "quote": LOAD,
    "card": "FAKE-ROVER",
    "proposal": {
        "type": "CustomerProduct",
        "field": "payload_kg",
        "definition": {"label": "負載", "kind": "float", "class": "sourced"},
    },
}
NEW_TYPE = {
    "summary": "太空任務",
    "action": "propose_type",
    "reason": "需要獨立追蹤",
    "quote": MISSION,
    "proposal": {"name": "Mission", "definition": "一個任務", **FOUR},
}


def _post(ws: Path, path: str, body: Any, ai: Any = None) -> Any:
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _run(ws: Path, dataset: str, *items: dict[str, Any], kind: str = "ingest") -> tuple[str, Any]:
    body = {"dataset": dataset, "name": "note.md", "text": NOTE, "folder": FOLDER}
    source = _ok(_post(ws, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    model = Scripted({"candidates": [CANDIDATE], "items": list(items)})
    # A different scripted answer to the same request: not the kept one.
    given = {"dataset": dataset, "kind": kind, "source_id": source, "folder": FOLDER, "fresh": True}
    run = _ok(_post(ws, "/api/bi/runs", given, _runtime(model, jobs)))["run"]
    jobs.run_all()
    return str(run["id"]), model


def _items(ws: Path, dataset: str, run_id: str) -> list[dict[str, Any]]:
    run = _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))["run"]
    return list(run["items"])


def _decide(ws: Path, dataset: str, run_id: str, item: str, status: str, reason: str = "") -> Any:
    body = {"dataset": dataset, "status": status, "reason": reason}
    return _post(ws, f"/api/bi/runs/{run_id}/items/{item}", body)


def _held(repo: Any) -> list[dict[str, Any]]:
    document = profile.read(repo, "aidc", repo.working_units())
    assert document is not None
    return list(document["proposals"])


def _start(tmp_path: Path) -> tuple[str, str, Path]:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _ok(_post(a, f"/api/bi/vaults/{vault_id}/profiles", {"home": "aidc", "profile": PROFILE}))
    return vault_id, dataset, a


def test_the_model_is_told_the_order_and_every_item_is_recorded(tmp_path: Path) -> None:
    _, dataset, a = _start(tmp_path)
    run_id, model = _run(a, dataset, EXTEND, NEW_TYPE)
    system = model.requests[0].messages[0].text
    assert "propose_type" in system and "never justify a new type" in system
    by_summary = {i["summary"]: i for i in _items(a, dataset, run_id)}
    # The candidate says it creates, whatever the model called it; the extension stays.
    assert by_summary["產品的負載"]["actions"] == ["create_card", "extend_schema"]
    assert by_summary["產品的負載"]["status"] == "proposed"
    assert by_summary["產品的負載"]["excerpt"] == LOAD and by_summary["產品的負載"]["locator"]
    assert by_summary["太空任務"]["actions"] == ["propose_type"]
    assert by_summary["太空任務"]["schema"] == "bi.schema/v1.1@5.0.0"


def test_a_candidate_the_model_gave_no_item_gets_one(tmp_path: Path) -> None:
    _, dataset, a = _start(tmp_path)
    run_id, _ = _run(a, dataset)
    (item,) = _items(a, dataset, run_id)
    assert item["actions"] == ["create_card"] and item["card"] == "FAKE-ROVER"
    assert item["status"] == "through_candidate" and item["reason"] == "模型沒有說明理由"
    status, body = _decide(a, dataset, run_id, item["id"], "approved")
    assert (status, body["code"]) == (400, "fit_item_not_reviewed")


def test_an_existing_card_is_an_update(tmp_path: Path) -> None:
    _, dataset, a = _start(tmp_path)
    _put(a, dataset, _row("CustomerProduct", "FAKE-ROVER", product_name="FAKE-ROVER"))
    run_id, _ = _run(a, dataset, {**EXTEND, "action": ["create_card"], "proposal": None})
    (item,) = _items(a, dataset, run_id)
    assert item["actions"] == ["update_card"] and item["target_card"]


def test_a_new_type_needs_its_four_answers(tmp_path: Path) -> None:
    _, dataset, a = _start(tmp_path)
    for missing in FOUR:
        answers = {k: v for k, v in FOUR.items() if k != missing}
        partial = {**NEW_TYPE, "proposal": {"name": "Mission", **answers}}
        run_id, _ = _run(a, dataset, partial)
        item = next(i for i in _items(a, dataset, run_id) if i["summary"] == "太空任務")
        assert item["actions"] == ["needs_clarification"], missing
        assert "缺少必要說明" in item["questions"][0]
        # Kept, not dropped: the proposal and what the model said, for the person.
        assert item["proposal"]["name"] == "Mission" and item["excerpt"] == MISSION
        assert item["model_actions"] == ["propose_type"]
    same = {**NEW_TYPE, "proposal": {"name": "Account", **FOUR}}
    run_id, _ = _run(a, dataset, same)
    item = next(i for i in _items(a, dataset, run_id) if i["summary"] == "太空任務")
    assert item["actions"] == ["needs_clarification"] and "已經有類型" in item["questions"][0]


def test_what_the_model_cannot_back_is_kept_as_a_question(tmp_path: Path) -> None:
    _, dataset, a = _start(tmp_path)
    run_id, _ = _run(
        a,
        dataset,
        {**NEW_TYPE, "quote": "來源沒有這句"},
        {"summary": "看不懂的動作", "action": "invent", "quote": LOAD},
        {"summary": "沒有候選卡", "action": "update_card", "card": "FAKE-NONE", "quote": LOAD},
        {
            **EXTEND,
            "summary": "已有欄位",
            "proposal": {**EXTEND["proposal"], "field": "product_name"},
        },
    )
    items = {i["summary"]: i for i in _items(a, dataset, run_id)}
    assert items["太空任務"]["actions"] == ["needs_clarification"]
    assert "不在來源中" in items["太空任務"]["questions"][0]
    assert items["看不懂的動作"]["actions"] == ["needs_clarification"]
    assert items["沒有候選卡"]["actions"] == ["needs_clarification"]
    assert "沒有為這項知識提出候選卡" in items["沒有候選卡"]["questions"][0]
    assert "已經有欄位" in items["已有欄位"]["questions"][0]


def test_nothing_registers_until_a_person_approves(tmp_path: Path) -> None:
    vault_id, dataset, a = _start(tmp_path)
    run_id, _ = _run(a, dataset, EXTEND, NEW_TYPE)
    repo = vault.Vault(a, vault_id).repo
    reg = catalog.for_store(BiStore(a, dataset))
    assert "Mission" not in reg.types
    assert reg.types["CustomerProduct"].get("payload_kg") is None
    assert _held(repo) == []

    items = {i["summary"]: i for i in _items(a, dataset, run_id)}
    # An approved new type is a recorded decision; a schema version is still Session A's.
    done = _ok(_decide(a, dataset, run_id, items["太空任務"]["id"], "approved"))
    assert done["item"]["status"] == "approved" and "alice" in done["item"]["decided_by"]
    assert "Mission" not in catalog.for_store(BiStore(a, dataset)).types

    # An approved field becomes the profile's proposal, for its own merge.
    _ok(_decide(a, dataset, run_id, items["產品的負載"]["id"], "approved"))
    held = _held(repo)
    assert [(p["type"], p["field"], p["status"]) for p in held] == [
        ("CustomerProduct", "payload_kg", "proposed")
    ]
    fresh = catalog.for_store(BiStore(a, dataset))
    assert fresh.types["CustomerProduct"].get("payload_kg") is None
    status, body = _decide(a, dataset, run_id, items["產品的負載"]["id"], "rejected", "no")
    assert (status, body["code"]) == (400, "fit_item_decided")


def test_a_rejection_keeps_its_reason_and_clarifying_can_be_decided_later(tmp_path: Path) -> None:
    _, dataset, a = _start(tmp_path)
    run_id, _ = _run(a, dataset, NEW_TYPE)
    item = next(i for i in _items(a, dataset, run_id) if i["summary"] == "太空任務")
    status, body = _decide(a, dataset, run_id, item["id"], "rejected")
    assert (status, body["code"]) == (400, "reason_required")
    _ok(_decide(a, dataset, run_id, item["id"], "needs_clarification", "問領域負責人"))
    kept = next(i for i in _items(a, dataset, run_id) if i["id"] == item["id"])
    assert kept["decision_reason"] == "問領域負責人"
    done = _ok(_decide(a, dataset, run_id, item["id"], "rejected", "順帶提到而已"))
    assert done["item"]["status"] == "rejected" and done["item"]["excerpt"] == MISSION


def test_a_question_cannot_be_approved_and_a_trial_decides_nothing(tmp_path: Path) -> None:
    _, dataset, a = _start(tmp_path)
    run_id, _ = _run(
        a, dataset, {"summary": "不清楚", "action": "needs_clarification", "quote": LOAD}
    )
    item = next(i for i in _items(a, dataset, run_id) if i["summary"] == "不清楚")
    status, body = _decide(a, dataset, run_id, item["id"], "approved")
    assert (status, body["code"]) == (400, "fit_needs_clarification")
    trial, _ = _run(a, dataset, NEW_TYPE, kind="trial")
    item = next(i for i in _items(a, dataset, trial) if i["summary"] == "太空任務")
    status, body = _decide(a, dataset, trial, item["id"], "approved")
    assert body["code"] == "run_trial" and status != 200


def test_a_field_needs_a_home_with_a_profile(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    run_id, _ = _run(a, dataset, EXTEND)
    item = next(i for i in _items(a, dataset, run_id) if i["summary"] == "產品的負載")
    status, body = _decide(a, dataset, run_id, item["id"], "approved")
    assert body["code"] == "profile_missing" and status != 200
    still = next(i for i in _items(a, dataset, run_id) if i["id"] == item["id"])
    assert still["status"] == "proposed"  # it can be approved once there is a profile


def test_a_dataset_that_is_no_vault_is_not_asked(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    _ok(_post(ws, "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    body = {"dataset": "lab", "name": "note.md", "text": NOTE}
    source = _ok(_post(ws, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    model = Scripted({"candidates": []})
    given = {"dataset": "lab", "kind": "ingest", "source_id": source}
    _ok(_post(ws, "/api/bi/runs", given, _runtime(model, jobs)))
    jobs.run_all()
    assert "propose_type" not in model.requests[0].messages[0].text


def test_what_a_real_model_got_wrong_stays_visible(tmp_path: Path) -> None:
    """From a real run: invented field values, and a question on a plain new card."""
    _, dataset, a = _start(tmp_path)
    invented = {"label": "負載", "kind": "quantity", "class": "product_spec"}
    run_id, model = _run(
        a,
        dataset,
        {**EXTEND, "proposal": {**EXTEND["proposal"], "definition": invented}},
        {**EXTEND, "summary": "沒有定義", "card": "", "action": "extend_schema", "proposal": None},
        {
            "summary": "階段用語",
            "action": "create_card",
            "card": "FAKE-ROVER",
            "reason": "可以建卡",
            "quote": LOAD,
            "questions": ["這個用語是不是樣品階段的同義詞？"],
        },
    )
    system = model.requests[0].messages[0].text
    assert "linklist" in system and "language of the source" in system
    items = {i["summary"]: i for i in _items(a, dataset, run_id)}
    item = items["產品的負載"]
    assert "needs_clarification" in item["actions"] and "extend_schema" not in item["actions"]
    assert "不是 schema 允許的值" in item["questions"][0]
    assert item["proposal"]["definition"] == invented and item["status"] == "proposed"
    assert items["沒有定義"]["actions"] == ["needs_clarification"]
    # A question reaches the person, not only the candidates' review.
    asked = items["階段用語"]
    assert asked["actions"] == ["create_card", "needs_clarification"]
    assert asked["status"] == "proposed"
    status, body = _decide(a, dataset, run_id, asked["id"], "approved")
    assert (status, body["code"]) == (400, "fit_needs_clarification")
