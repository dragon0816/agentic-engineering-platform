"""建議 schema (`BI_PAGE_SIMPLE.md` S2, acceptance F5) and the readable version (F6): the fit
question alone, on a press, writing no card; every row quoted from the source; a new field
added as units on the version, never a new one. All data is fictional."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok, _two_pcs

from aep_bi.cards import catalog, schema_suggest, schema_versions, vault
from aep_bi.cards.store import BiStore, BiStoreError
from aep_bi.host.bi_cards_api import route

NOTE = (
    "# 虛構筆記\n\nFAKE-ROVER 的冷卻方式是液冷。\n"
    "太空任務 FAKE-MISSION 要追蹤里程碑。\nFAKE-5G 是一項技術。\n"
)
FOLDER = "applications/aidc/sources"
COOLING: dict[str, Any] = {
    "summary": "技術的冷卻方式",
    "action": ["update_card", "extend_schema"],
    "reason": "沒有欄位放冷卻方式",
    "quote": "FAKE-ROVER 的冷卻方式是液冷",
    "card": "FAKE-ROVER",
    "proposal": {
        "type": "Technology",
        "field": "cooling",
        "definition": {"label": "冷卻方式", "kind": "str", "class": "sourced"},
    },
}
MISSION: dict[str, Any] = {
    "summary": "太空任務",
    "action": "propose_type",
    "reason": "任務要獨立追蹤",
    "quote": "太空任務 FAKE-MISSION 要追蹤里程碑",
    "proposal": {
        "name": "Mission",
        "definition": "一個任務",
        "unit_boundary": "一個任務一張卡",
        "why_not_existing": "沒有卡型有里程碑",
        "why_independent": "有自己的時程",
        "business_use": "查任務進度",
    },
}
FITS = {
    "summary": "FAKE-5G",
    "action": "create_card",
    "card": "FAKE-5G",
    "quote": "FAKE-5G 是一項技術",
}
INVENTED = {
    **COOLING,
    "summary": "價格",
    "quote": "這句話不在來源裡",
    "proposal": {
        "type": "Technology",
        "field": "price",
        "definition": {"kind": "float", "class": "sourced"},
    },
}


def _post(ws: Path, path: str, body: Any, ai: Any = None) -> Any:
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _source(ws: Path, dataset: str, name: str = "note.md", text: str = NOTE) -> str:
    body = {"dataset": dataset, "name": name, "text": text, "folder": FOLDER}
    return str(_ok(_post(ws, "/api/bi/sources", body))["source"]["id"])


def _suggest(
    ws: Path, dataset: str, sources: list[str], *answers: Any, only_new: bool = False
) -> Any:
    jobs, model = Jobs(), Scripted(*answers)
    body = {"dataset": dataset, "source_ids": sources, "only_new": only_new}
    started = _ok(_post(ws, "/api/bi/schema-suggest", body, _runtime(model, jobs)))["suggestion"]
    assert started["status"] == "running" and not model.requests  # nothing asked yet
    jobs.run_all()
    done = _ok(_call(ws, "GET", "/api/bi/schema-suggest", dataset=dataset))["suggestion"]
    return done, model


def test_a_press_asks_only_the_fit_question_and_writes_no_card(tmp_path: Path) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _source(a, dataset)
    cards = BiStore(a, dataset).card_rows()
    done, model = _suggest(a, dataset, [source], {"items": [COOLING, MISSION, FITS, INVENTED]})
    system = model.requests[0].messages[0].text
    assert "You write no cards here" in system and "propose_type" in system
    assert "Technology" in system  # the whole schema, so nothing it has is proposed again
    assert done["status"] == "done" and done["sources"] == [{"id": source, "name": "note.md"}]
    assert done["seconds"] is not None and done["answers"]["asked"] == 1
    by_kind = {r["kind"]: r for r in done["items"]}
    assert set(by_kind) == {"extend_schema", "propose_type"}
    assert by_kind["extend_schema"]["quote"] == COOLING["quote"]
    assert by_kind["extend_schema"]["what"] == "新增欄位 Technology.cooling（冷卻方式）"
    assert by_kind["extend_schema"]["applies"] and not by_kind["propose_type"]["applies"]
    # The invented quote is no suggestion; what fits is counted, not listed.
    assert (done["unquoted"], done["fits"]) == (1, 1)
    assert BiStore(a, dataset).card_rows() == cards


def test_nothing_to_change_is_an_answer_and_a_type_the_schema_has_is_a_question(
    tmp_path: Path,
) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _source(a, dataset)
    done, _ = _suggest(a, dataset, [source], {"items": [FITS]})
    assert done["status"] == "done" and done["items"] == [] and done["fits"] == 1
    again = {**MISSION, "proposal": {**MISSION["proposal"], "name": "Technology"}}
    # The same source and schema again reuse the kept answer: another source asks anew.
    assert _suggest(a, dataset, [source], {"items": [again]})[0]["answers"]["reused"] == 1
    other = _source(a, dataset, "other.md", NOTE + "\n另一份。\n")
    done, _ = _suggest(a, dataset, [other], {"items": [again]})
    (row,) = done["items"]
    assert row["kind"] == "needs_clarification" and not row["applies"]
    assert "schema 已經有類型 Technology" in row["questions"][0]


def test_only_new_leaves_out_what_an_ingest_read_and_says_when_nothing_is_left(
    tmp_path: Path,
) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _source(a, dataset)
    jobs = Jobs()
    run = {"dataset": dataset, "kind": "ingest", "source_id": source, "folder": FOLDER}
    _ok(_post(a, "/api/bi/runs", run, _runtime(Scripted({"candidates": []}), jobs)))
    jobs.run_all()
    body = {"dataset": dataset, "source_ids": [source], "only_new": True}
    status, answer = _post(a, "/api/bi/schema-suggest", body, _runtime(Scripted(), Jobs()))
    assert (status, answer["code"]) == (400, "suggest_no_sources")
    other = _source(a, dataset, "other.md", NOTE + "\n另一份。\n")
    done, _ = _suggest(a, dataset, [source, other], {"items": []}, only_new=True)
    assert [s["name"] for s in done["sources"]] == ["other.md"]


def test_applying_a_field_adds_units_on_the_version_and_the_label_says_so(
    tmp_path: Path,
) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _source(a, dataset)
    done, _ = _suggest(a, dataset, [source], {"items": [COOLING, MISSION]})
    row = next(r for r in done["items"] if r["kind"] == "extend_schema")
    body = {"dataset": dataset, "id": done["id"], "row": row["id"]}
    applied = _ok(_post(a, "/api/bi/schema-suggest/apply", body))
    assert applied["schema"]["label"] == "5.0 加 1 項新增"
    assert applied["schema"]["additions"] == ["schema 的欄位 Technology.cooling"]
    units = vault.Vault(a, vault_id).repo.working_units()
    assert "schema_change:field:Technology.cooling" in units
    assert units["schema"] == "bi.schema/v1.1@5.0.0"  # no new version
    assert catalog.for_store(BiStore(a, dataset)).types["Technology"].get("cooling") is not None
    # The draft that carried it is gone, and nothing offers a version without it.
    assert _ok(_call(a, "GET", "/api/bi/schema-drafts"))["drafts"] == []
    shown = _ok(_call(a, "GET", "/api/bi/schema", dataset=dataset))
    assert shown["label"] == "5.0 加 1 項新增" and shown["upgrades"] == []
    status, refused = _post(
        a, f"/api/bi/datasets/{dataset}/schema/preview", {"to": "bi.schema/v1.1@5.0.0"}
    )
    assert (status, refused["code"]) == (400, "schema_drops_additions")
    # Decided once; a type needs the AI; a reject keeps its reason.
    status, again = _post(a, "/api/bi/schema-suggest/apply", body)
    assert (status, again["code"]) == (409, "suggest_row_decided")
    mission = next(r for r in done["items"] if r["kind"] == "propose_type")
    status, typed = _post(a, "/api/bi/schema-suggest/apply", {**body, "row": mission["id"]})
    assert (status, typed["code"]) == (400, "suggest_not_direct")
    rejected = _ok(
        _post(
            a, "/api/bi/schema-suggest/reject", {**body, "row": mission["id"], "reason": "不需要"}
        )
    )["suggestion"]
    assert next(r for r in rejected["items"] if r["id"] == mission["id"])["status"] == "rejected"


def test_upgrades_list_only_newer_versions(tmp_path: Path) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    shown = _ok(_call(a, "GET", "/api/bi/schema", dataset=dataset))
    assert shown["label"] == "5.0" and shown["additions"] == []
    # 1.1 to 4.0 are shipped and older: never offered as an upgrade.
    assert shown["upgrades"] == []
    assert schema_suggest.MAX_SOURCES >= 1


def test_a_list_field_with_no_values_needs_the_ai_and_one_with_values_applies(
    tmp_path: Path,
) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _source(a, dataset)
    bare = {"label": "冷卻方式", "kind": "enum", "class": "sourced"}
    given = {**bare, "values": ["氣冷", "液冷"]}
    rows = [
        {**COOLING, "proposal": {**COOLING["proposal"], "field": "cooling", "definition": bare}},
        {**COOLING, "proposal": {**COOLING["proposal"], "field": "cooling2", "definition": given}},
    ]
    done, _ = _suggest(a, dataset, [source], {"items": rows})
    applies = {r["proposal"]["field"]: r["applies"] for r in done["items"]}
    assert applies == {"cooling": False, "cooling2": True}
    row = next(r for r in done["items"] if r["applies"])
    _ok(
        _post(
            a,
            "/api/bi/schema-suggest/apply",
            {"dataset": dataset, "id": done["id"], "row": row["id"]},
        )
    )
    added = catalog.for_store(BiStore(a, dataset)).types["Technology"].get("cooling2")
    assert added is not None and list(added.enum or ()) == ["氣冷", "液冷"]


def test_one_add_at_a_time_and_a_stopped_add_goes_back_without_a_version(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The owner's 「加入時沒反應」: an add takes half a minute on a shared vault, so a
    second press ran a second add beside the first, and 「不要」 decided the row under it.
    Now the row is 「加入中」 until it ends; a second press and a 「不要」 wait; an add that
    stops leaves the row to decide again and no published version offered as an upgrade."""
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _source(a, dataset)
    done, _ = _suggest(a, dataset, [source], {"items": [COOLING]})
    row = done["items"][0]
    body = {"dataset": dataset, "id": done["id"], "row": row["id"]}
    real, started, release = schema_versions.upgrade_apply, threading.Event(), threading.Event()

    def held(*args: Any, **kwargs: Any) -> Any:
        started.set()
        assert release.wait(30)
        return real(*args, **kwargs)

    monkeypatch.setattr(schema_versions, "upgrade_apply", held)
    first: list[Any] = []
    worker = threading.Thread(
        target=lambda: first.append(_post(a, "/api/bi/schema-suggest/apply", body))
    )
    worker.start()
    assert started.wait(30)
    shown = _ok(_call(a, "GET", "/api/bi/schema-suggest", dataset=dataset))["suggestion"]
    assert shown["items"][0]["status"] == "applying"
    for path, extra in (("apply", {}), ("reject", {"reason": "x"})):
        status, busy = _post(a, f"/api/bi/schema-suggest/{path}", {**body, **extra})
        assert (status, busy["code"]) == (409, "suggest_row_busy")
    release.set()
    worker.join(60)
    status, applied = first[0]
    assert status == 200 and applied["suggestion"]["items"][0]["status"] == "applied"
    assert "applying_at" not in applied["suggestion"]["items"][0]
    units = vault.Vault(a, vault_id).repo.working_units()
    assert "schema_change:field:Technology.cooling" in units

    # An add that stops: the row is proposed again and the version made on the way is gone.
    other = {**COOLING, "proposal": {**COOLING["proposal"], "field": "weight"}}
    done, _ = _suggest(a, dataset, [source], {"items": [other]})
    body = {"dataset": dataset, "id": done["id"], "row": done["items"][0]["id"]}
    before = {r.ref for r in catalog.available(a)}

    def stops(*_args: Any, **_kwargs: Any) -> Any:
        raise BiStoreError("preview_stale", "資料集在預覽後有變動，請重新預覽")

    monkeypatch.setattr(schema_versions, "upgrade_apply", stops)
    status, failed = _post(a, "/api/bi/schema-suggest/apply", body)
    assert (status, failed["code"]) == (409, "preview_stale")
    again = _ok(_call(a, "GET", "/api/bi/schema-suggest", dataset=dataset))["suggestion"]
    assert again["items"][0]["status"] == "proposed"
    assert {r.ref for r in catalog.available(a)} == before
    assert _ok(_call(a, "GET", "/api/bi/schema", dataset=dataset))["upgrades"] == []
    monkeypatch.setattr(schema_versions, "upgrade_apply", real)
    assert _ok(_post(a, "/api/bi/schema-suggest/apply", body))["schema"]["label"] == (
        "5.0 加 2 項新增"
    )
