"""Relations a model inferred: only with a quote, and each decided by a person
(`docs/phases/BI_CARD_MODEL.md` §3.3). All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_card_links import _put, _row
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok, _two_pcs

from capabilities.bi_cards import card_model, catalog, extract, vault
from capabilities.bi_cards.store import BiStore, card_id_for
from host_runtime.bi_cards_api import route

NOTE = "# 虛構會議\n\nFAKE-PRODUCT 需要 FAKE-TEST 才能量產。\n"
QUOTE = "FAKE-PRODUCT 需要 FAKE-TEST"
PRODUCT = card_id_for("CustomerProduct", "FAKE-PRODUCT")
TEST = card_id_for("TestSolution", "FAKE-TEST")
RELATION = card_model.relation_id(PRODUCT, "requires_test", TEST)
INFERRED = {
    "type": "requires_test",
    "from": "FAKE-PRODUCT",
    "to": "FAKE-TEST",
    "quote": QUOTE,
    "reason": "量產前要測",
}


def _ai_call(ws: Path, path: str, body: Any, ai: Any = None) -> Any:
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _run(ws: Path, dataset: str, *relations: dict[str, Any]) -> tuple[str, Scripted]:
    body = {"dataset": dataset, "name": "meeting.md", "text": NOTE}
    source = _ok(_ai_call(ws, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    model = Scripted({"candidates": [], "relations": list(relations)})
    given = {"dataset": dataset, "kind": "ingest", "source_id": source}
    run = _ok(_ai_call(ws, "/api/bi/runs", given, _runtime(model, jobs)))["run"]
    jobs.run_all()
    return str(run["id"]), model


def _view(ws: Path, dataset: str, run_id: str) -> dict[str, Any]:
    return dict(_ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))["run"])


def _decide(ws: Path, dataset: str, run_id: str, relation: str, status: str) -> Any:
    path = f"/api/bi/runs/{run_id}/relations/{relation}"
    return _ai_call(ws, path, {"dataset": dataset, "status": status})


def _cards(ws: Path, dataset: str) -> None:
    _put(ws, dataset, _row("CustomerProduct", "FAKE-PRODUCT"), _row("TestSolution", "FAKE-TEST"))


def test_a_vault_run_asks_for_registered_types_and_keeps_what_has_a_quote(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    run_id, model = _run(
        a,
        dataset,
        INFERRED,
        {**INFERRED, "quote": "這句話不在來源裡"},
        {**INFERRED, "type": "invented"},
        {**INFERRED, "to": ""},
    )
    system = model.requests[0].messages[0].text
    assert "requires_test" in system and '"relations"' in system
    run = _view(a, dataset, run_id)
    assert [r["id"] for r in run["relations"]] == ["r1"]
    found = run["relations"][0]
    assert found["excerpt"] == QUOTE and found["decision"] is None and found["locator"]
    assert [w["code"] for w in run["warnings"]].count("relation_unsupported") == 3


def test_a_dataset_that_is_no_vault_is_not_asked(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    _ok(_ai_call(ws, "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    run_id, model = _run(ws, "lab", INFERRED)
    assert "requires_test" not in model.requests[0].messages[0].text
    assert _view(ws, "lab", run_id)["relations"] == []
    status, body = _decide(ws, "lab", run_id, "r1", "confirmed")
    assert (status, body["code"]) == (400, "relation_vault_only")


def test_a_schema_with_no_registered_types_is_not_asked(tmp_path: Path) -> None:
    reg = catalog.resolve(tmp_path, "bi.schema/v1.1@4.0.0")
    chunk = extract.chunks(NOTE)[0]
    said = extract.messages(reg, ["Signal"], "", {}, chunk, "m.md", infer_relations=True)
    assert '"relations"' not in said[0].text
    assert extract.read_relations(reg, {"relations": [INFERRED]}, chunk, "s")[0] == []


def test_confirming_needs_the_cards_and_stores_the_decision(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    run_id, _ = _run(a, dataset, INFERRED)
    assert _view(a, dataset, run_id)["relations"][0]["decision"] is None

    # Nothing is written until a person decides, and only with both cards.
    units = vault.Vault(a, vault_id).repo.working_units()
    assert not [k for k in units if k.startswith("relation")]
    status, body = _decide(a, dataset, run_id, "r1", "confirmed")
    assert (status, body["code"]) == (404, "relation_card_unknown")

    _cards(a, dataset)
    decided = _ok(_decide(a, dataset, run_id, "r1", "confirmed"))
    assert decided["relation"]["decision"] == "confirmed"
    units = vault.Vault(a, vault_id).repo.working_units()
    unit = units[f"relation:{RELATION}"]
    assert unit["origin"] == "ai_inferred" and unit["status"] == "confirmed"
    assert unit["note"] == "量產前要測" and "alice" in unit["by"]
    shown = BiStore(a, dataset).relations(PRODUCT)[0]
    assert shown["origin"] == "ai_inferred" and len(shown["evidence"]) == 1
    # Its evidence is the place in the source a field's evidence would name.
    item = _view(a, dataset, run_id)["relations"][0]
    assert shown["evidence"][0]["reference_id"] == card_model.reference_id(
        item["source_id"], item["locator"]
    )


def test_a_decided_relation_is_not_asked_again(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _cards(a, dataset)
    run_id, _ = _run(a, dataset, INFERRED)
    _ok(_decide(a, dataset, run_id, "r1", "rejected"))
    assert BiStore(a, dataset).relations(PRODUCT) == []  # a rejected one is not used

    again, _ = _run(a, dataset, INFERRED)
    assert _view(a, dataset, again)["relations"] == []


def test_rejecting_one_whose_cards_never_came_needs_nothing_stored(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    run_id, _ = _run(a, dataset, INFERRED)
    assert _ok(_decide(a, dataset, run_id, "r1", "rejected"))["relation"]["decision"] == "rejected"
    units = vault.Vault(a, vault_id).repo.working_units()
    assert not [k for k in units if k.startswith("relation")]
    assert _view(a, dataset, run_id)["relations"][0]["decision"] == "rejected"


def test_a_bad_decision_is_refused(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    run_id, _ = _run(a, dataset, INFERRED)
    status, body = _decide(a, dataset, run_id, "r1", "maybe")
    assert (status, body["code"]) == (400, "relation_status_invalid")
    status, body = _decide(a, dataset, run_id, "r9", "confirmed")
    assert body["code"] == "relation_unknown" and status in (400, 404)
