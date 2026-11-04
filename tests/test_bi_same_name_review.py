"""A model's new card named like a card of another type (R6: same_name 0 → 20 on a full
run). It waits for a person, and is never merged. All data is fictional; the model is
scripted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_run_merge import _detail, _post
from test_bi_vault import _call, _ok, _two_pcs

from capabilities.bi_cards import catalog, extract
from capabilities.bi_cards.store import BiStore, PlannedRow

NOTE = "# 虛構\n\nFAKE-CO 宣布新的生態系，FAKE-OTHER 也加入。\n"


def _seed(ws: Path, dataset: str, **values: Any) -> str:
    store = BiStore(ws, dataset)
    store.apply(
        [PlannedRow(1, "Account", "FAKE-CO", "FAKE-CO", {"name": "FAKE-CO", **values}, False)],
        filename="seed.csv",
        entity_type="Account",
        actor="alice",
    )
    card = store.find("Account", "FAKE-CO")
    assert card is not None
    return str(card["id"])


def _proposes(name: str, entity_type: str = "Ecosystem", **fields: Any) -> dict[str, Any]:
    named = {"name": {"value": name, "basis": "fact", "quote": "FAKE-CO"}, **fields}
    return {"candidates": [{"entity_type": entity_type, "name": name, "fields": named}]}


def _run(ws: Path, dataset: str, answer: dict[str, Any], kind: str = "Ecosystem") -> str:
    body = {"dataset": dataset, "name": "note.md", "text": NOTE}
    source = _ok(_post(ws, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    given = {"dataset": dataset, "kind": "ingest", "source_id": source, "types": [kind]}
    run = _ok(_post(ws, "/api/bi/runs", given, _runtime(Scripted(answer), jobs)))["run"]
    jobs.run_all()
    return str(run["id"])


def _candidate(ws: Path, dataset: str, run_id: str) -> dict[str, Any]:
    return dict(_detail(ws, dataset, run_id)["candidates"][0])


def _review(ws: Path, dataset: str, run_id: str, candidate: str, **body: Any) -> Any:
    path = f"/api/bi/runs/{run_id}/candidates/{candidate}"
    return _post(ws, path, {"dataset": dataset, **body})


def test_a_new_card_named_like_another_type_warns_and_needs_a_person(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    seed = _seed(a, dataset)
    run_id = _run(a, dataset, _proposes("FAKE-CO"))
    found = _candidate(a, dataset, run_id)
    assert found["action"] == "create"
    assert found["same_name"] == [{"id": seed, "name": "FAKE-CO", "type": "Account"}]
    warned = [w for w in found["warnings"] if w["code"] == "same_name_other_type"]
    assert len(warned) == 1 and "FAKE-CO" in warned[0]["message"]
    assert "Account" in warned[0]["message"]

    status, refused = _review(a, dataset, run_id, found["id"], review="accepted")
    assert (status, refused["code"]) == (400, "same_name_unconfirmed")
    assert _candidate(a, dataset, run_id)["review"] == "pending"

    _ok(_review(a, dataset, run_id, found["id"], review="accepted", confirm_same_name=True))
    assert _candidate(a, dataset, run_id)["review"] == "accepted"
    _ok(_post(a, f"/api/bi/runs/{run_id}/commit", {"dataset": dataset}))
    store = BiStore(a, dataset)
    # Both cards stand: nothing is merged.
    assert store.find("Ecosystem", "FAKE-CO") is not None
    assert store.find("Account", "FAKE-CO") is not None


def test_a_person_can_say_it_is_the_same_and_not_create_it(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset)
    run_id = _run(a, dataset, _proposes("FAKE-CO"))
    found = _candidate(a, dataset, run_id)
    _ok(_review(a, dataset, run_id, found["id"], review="rejected"))
    assert _candidate(a, dataset, run_id)["review"] == "rejected"
    assert BiStore(a, dataset).find("Ecosystem", "FAKE-CO") is None


def test_a_card_alias_answers_both_ways_and_spelling_is_loose(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    seed = _seed(a, dataset, aliases=["FAKE CO Ltd"])
    run_id = _run(a, dataset, _proposes("fake-co ltd"))
    assert [c["id"] for c in _candidate(a, dataset, run_id)["same_name"]] == [seed]
    aliased = _proposes(
        "FAKE-NEW", aliases={"value": ["FAKE-CO"], "basis": "fact", "quote": "FAKE-CO"}
    )
    run_id = _run(a, dataset, aliased)
    assert [c["id"] for c in _candidate(a, dataset, run_id)["same_name"]] == [seed]


def test_a_different_name_and_the_same_type_are_not_flagged(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset)
    other = _candidate(a, dataset, _run(a, dataset, _proposes("FAKE-OTHER")))
    assert other["same_name"] == []
    assert not [w for w in other["warnings"] if w["code"] == "same_name_other_type"]
    same_type = _candidate(a, dataset, _run(a, dataset, _proposes("FAKE-CO", "Account"), "Account"))
    assert same_type["match"] == "existing"
    assert same_type["same_name"] == []


def test_a_card_appearing_after_accepting_returns_it_to_pending(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    run_id = _run(a, dataset, _proposes("FAKE-CO"))
    found = _candidate(a, dataset, run_id)
    assert found["same_name"] == []
    _ok(_review(a, dataset, run_id, found["id"], review="accepted"))
    _seed(a, dataset)
    again = _ok(_post(a, f"/api/bi/runs/{run_id}/recheck", {"dataset": dataset}))
    assert again["changed"] == [found["id"]]
    assert again["candidates"][0]["review"] == "pending"


def test_an_import_of_rows_is_not_held_back(tmp_path: Path) -> None:
    """A person's own table may name both: only a model's guess waits."""
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset)
    body = {"dataset": dataset, "name": "t.csv", "text": "技術\nFAKE-CO\n"}
    source = _ok(_post(a, "/api/bi/sources", body))["source"]["id"]
    run = _ok(
        _post(a, "/api/bi/runs", {"dataset": dataset, "kind": "ingest", "source_id": source,
                                  "entity_type": "Technology"})
    )["run"]  # fmt: skip
    found = _candidate(a, dataset, run["id"])
    assert "same_name" not in found
    _ok(_review(a, dataset, run["id"], found["id"], review="accepted"))


def test_the_prompt_names_only_other_types_the_excerpt_writes(tmp_path: Path) -> None:
    reg = catalog.resolve(tmp_path, "bi.schema/v1.1")
    chunk = extract.chunks(NOTE)[0]
    known = {
        "Account": ["FAKE-CO", "FAKE-ABSENT"],
        "Ecosystem": ["FAKE-OTHER"],
        "Node": ["x"],  # too short to tell from any text
    }
    body = extract.messages(reg, ["Ecosystem"], "", known, chunk, "note.md")[1].text
    assert "- Ecosystem: FAKE-OTHER" in body
    assert "- Account: FAKE-CO" in body
    assert "FAKE-ABSENT" not in body
    assert "- Node" not in body
    plain = extract.messages(reg, ["Ecosystem"], "", {"Account": ["FAKE-ABSENT"]}, chunk, "n")
    assert "other types" not in plain[1].text


def test_the_review_detail_keeps_the_confirmation(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    seed = _seed(a, dataset)
    run_id = _run(a, dataset, _proposes("FAKE-CO"))
    found = _candidate(a, dataset, run_id)
    _ok(_review(a, dataset, run_id, found["id"], confirm_same_name=True))
    held = _candidate(a, dataset, run_id)
    assert held["same_name_confirmed"] == [seed]
    assert held["review"] == "pending"  # confirming alone decides nothing
    _ok(_review(a, dataset, run_id, found["id"], review="accepted"))
    assert _ok(_call(a, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))
