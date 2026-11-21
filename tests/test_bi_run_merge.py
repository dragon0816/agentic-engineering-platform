"""An AI run merges onto cards that exist; it never overwrites them (V1 on the AIDC reports:
253 fields changed, `confidence` raised on 93). All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok, _push, _sync, _two_pcs

from aep_bi.cards import extract, vault
from aep_bi.cards.store import BiStore, PlannedRow, card_id_for
from aep_bi.host.bi_cards_api import route

KIND = "SupplyLink"
KEY = "FAKE-LINK"
CARD = card_id_for(KIND, KEY)
QUOTE = "FAKE-LINK 由 FAKE-A 供應"
NOTE = f"# 虛構\n\n{QUOTE}。\n\n後面又寫 FAKE-LINK 由 FAKE-B 供應。\n"
OTHER_QUOTE = "FAKE-LINK 由 FAKE-B 供應"


def _fact(value: Any, quote: str = QUOTE) -> dict[str, Any]:
    return {"value": value, "basis": "fact", "quote": quote}


def _seed(ws: Path, dataset: str, **values: Any) -> None:
    BiStore(ws, dataset).apply(
        [
            PlannedRow(
                row=1,
                entity_type=KIND,
                canonical_key=KEY,
                name=KEY,
                values={"name": KEY, **values},
                synthetic=False,
            )
        ],
        filename="seed.csv",
        entity_type=KIND,
        actor="alice",
    )


def _post(ws: Path, path: str, body: Any, ai: Any = None) -> Any:
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _run(ws: Path, dataset: str, *answers: Any, text: str = NOTE) -> str:
    body = {"dataset": dataset, "name": "note.md", "text": text}
    source = _ok(_post(ws, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    given = {"dataset": dataset, "kind": "ingest", "source_id": source, "types": [KIND]}
    run = _ok(_post(ws, "/api/bi/runs", given, _runtime(Scripted(*answers), jobs)))["run"]
    jobs.run_all()
    return str(run["id"])


def _answer(**fields: Any) -> dict[str, Any]:
    named = {"name": _fact(KEY, "FAKE-LINK"), **fields}
    return {"candidates": [{"entity_type": KIND, "name": KEY, "fields": named}]}


def _detail(ws: Path, dataset: str, run_id: str) -> dict[str, Any]:
    return _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))


def _accept_and_commit(ws: Path, dataset: str, run_id: str) -> None:
    for candidate in _detail(ws, dataset, run_id)["candidates"]:
        path = f"/api/bi/runs/{run_id}/candidates/{candidate['id']}"
        _ok(_post(ws, path, {"dataset": dataset, "review": "accepted"}))
    _ok(_post(ws, f"/api/bi/runs/{run_id}/commit", {"dataset": dataset}))


def _value(ws: Path, dataset: str, field: str) -> Any:
    held = BiStore(ws, dataset).fields(CARD).get(field)
    return None if held is None else held["value"]


def _pending(ws: Path, dataset: str) -> dict[str, dict[str, Any]]:
    listed = _ok(_call(ws, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
    return {p["field"]: p for p in listed}


def test_accepting_everything_fills_joins_and_proposes_but_never_overwrites(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset, product="舊的產品", tech_areas=["rf"])
    run_id = _run(
        a,
        dataset,
        _answer(
            product=_fact("新的產品"),
            supplier=_fact("FAKE-A"),
            tech_areas=_fact(["EMC"]),
        ),
    )
    detail = _detail(a, dataset, run_id)
    by_field = {f["field"]: f for f in detail["candidates"][0]["fields"]}
    assert by_field["product"]["merge"] == "proposal"
    assert by_field["supplier"]["merge"] == "fill"
    assert by_field["tech_areas"]["merge"] == "join"
    merge = detail["run"]["merge"]
    assert (merge["fill"], merge["join"], merge["proposal"]) == (1, 1, 1)

    _accept_and_commit(a, dataset, run_id)
    assert _value(a, dataset, "product") == "舊的產品"  # the seed's value stands
    assert _value(a, dataset, "supplier") == "FAKE-A"
    assert _value(a, dataset, "tech_areas") == ["rf", "emc"]  # nothing lost, old items first
    pending = _pending(a, dataset)
    assert list(pending) == ["product"] and pending["product"]["value"] == "新的產品"
    # The proposal carries its own evidence; the value it did not change gets none of it.
    assert pending["product"]["evidence"][0]["excerpt"] == QUOTE
    assert "note.md" in pending["product"]["evidence"][0]["source_name"]
    assert not [e for e in BiStore(a, dataset).evidence(CARD) if e["field"] == "product"]


def test_a_person_may_choose_the_new_value_field_by_field(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset, product="舊的產品", body="舊的內文")
    run_id = _run(a, dataset, _answer(product=_fact("新的產品"), body=_fact("新的內文")))
    cid = _detail(a, dataset, run_id)["candidates"][0]["id"]
    path = f"/api/bi/runs/{run_id}/candidates/{cid}"
    reply = _ok(_post(a, path, {"dataset": dataset, "take_new": {"product": True}}))
    by_field = {f["field"]: f for f in reply["candidate"]["fields"]}
    assert by_field["product"]["merge"] == "take" and by_field["body"]["merge"] == "proposal"
    assert reply["run"]["merge"]["take"] == 1

    _accept_and_commit(a, dataset, run_id)
    assert _value(a, dataset, "product") == "新的產品"  # chosen
    assert _value(a, dataset, "body") == "舊的內文"  # not chosen
    assert list(_pending(a, dataset)) == ["body"]


def test_an_edit_by_a_person_is_a_choice_too(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset, product="舊的產品")
    run_id = _run(a, dataset, _answer(product=_fact("模型的產品")))
    cid = _detail(a, dataset, run_id)["candidates"][0]["id"]
    path = f"/api/bi/runs/{run_id}/candidates/{cid}"
    _ok(_post(a, path, {"dataset": dataset, "fields": {"product": "人寫的產品"}}))
    _accept_and_commit(a, dataset, run_id)
    assert _value(a, dataset, "product") == "人寫的產品" and _pending(a, dataset) == {}


def test_a_run_never_settles_confidence_or_evidence_grade(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset, confidence="assumed", evidence_grade="B")
    run_id = _run(a, dataset, _answer(confidence=_fact("verified"), evidence_grade=_fact("D")))
    cid = _detail(a, dataset, run_id)["candidates"][0]["id"]
    path = f"/api/bi/runs/{run_id}/candidates/{cid}"
    for field in ("confidence", "evidence_grade"):
        status, body = _post(a, path, {"dataset": dataset, "take_new": {field: True}})
        assert (status, body["code"]) == (400, "field_protected"), field
    # Not by editing either: it still goes to the proposals.
    _ok(_post(a, path, {"dataset": dataset, "fields": {"evidence_grade": "C"}}))
    _accept_and_commit(a, dataset, run_id)
    assert _value(a, dataset, "confidence") == "assumed"
    assert _value(a, dataset, "evidence_grade") == "B"
    pending = _pending(a, dataset)
    assert pending["confidence"]["value"] == "verified"
    assert pending["evidence_grade"]["value"] == "C"

    # Only a person's decision on the proposal makes it verified, and marks it as theirs.
    item = pending["confidence"]
    answer = _post(
        a,
        f"/api/bi/cards/{CARD}/proposals/{item['id']}",
        {
            "dataset": dataset,
            "action": "accept",
            "base_version": item["version"],
            "reason": "親自確認過",
        },
    )
    _ok(answer)
    held = BiStore(a, dataset).fields(CARD)["confidence"]
    assert held["value"] == "verified" and held["kind"] == "human"


def test_an_ai_run_never_writes_verified_even_on_a_new_card(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    for seeded in (False, True):  # a new card, then a card with the field empty
        name = "FAKE-NEW" if not seeded else KEY
        if seeded:
            _seed(a, dataset)
        fields = {"name": _fact(name, "FAKE-LINK" if seeded else "FAKE"),
                  "supplier": _fact("FAKE-A"), "customer": _fact("FAKE-B", "FAKE-B"),
                  "confidence": _fact("verified")}  # fmt: skip
        answer = {"candidates": [{"entity_type": KIND, "name": name, "fields": fields}]}
        run_id = _run(a, dataset, answer)
        merge = _detail(a, dataset, run_id)["run"]["merge"]
        assert (merge["capped"], merge["proposal"]) == (1, 1), name
        _accept_and_commit(a, dataset, run_id)
        store = BiStore(a, dataset)
        card = store.find(KIND, name)
        assert card is not None
        assert store.fields(card["id"])["confidence"]["value"] == "assumed", name
        claims = [
            p
            for p in _ok(_call(a, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
            if p["card_id"] == card["id"] and p["field"] == "confidence"
        ]
        assert [p["value"] for p in claims] == ["verified"], name
        assert claims[0]["evidence"][0]["excerpt"]  # the model's claim keeps its evidence
        # The stored level does not rest on evidence that said something else.
        assert not [e for e in store.evidence(card["id"]) if e["field"] == "confidence"]


def test_many_proposals_can_be_decided_at_once(tmp_path: Path) -> None:
    """Owner 2026-11-20 changed two rules here: the reason is optional (an empty one used to be
    400 `reason_required`), and the judgement field `confidence` is decided with the others
    (it used to be left out unless the filter named it, `left_out`)."""
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset, product="舊的", body="舊的內文", confidence="assumed")
    run_id = _run(
        a,
        dataset,
        _answer(product=_fact("新的"), body=_fact("新的內文"), confidence=_fact("verified")),
    )
    _accept_and_commit(a, dataset, run_id)
    assert not vault.Vault(a, vault_id).repo._pending()["sets"]
    pending = _pending(a, dataset)
    assert sorted(pending) == ["body", "confidence", "product"]
    origin = pending["body"]["origin"]
    assert "note.md" in origin and pending["confidence"]["protected"] is True

    def decide(**given: Any) -> Any:
        body = {"dataset": dataset, "action": "accept", "reason": "看過了", **given}
        return _post(a, "/api/bi/proposals/decide", body)

    # The count is what the person saw, `confidence` included: a list that moved refuses.
    status, body = decide(count=2)
    assert (status, body["code"]) == (409, "proposals_changed")
    assert sorted(_pending(a, dataset)) == ["body", "confidence", "product"]

    # Filtered by origin, without a reason: all three, the judgement field too.
    done = _ok(decide(count=3, origin=origin, reason=" "))
    assert (done["decided"], done["left_out"]) == (3, 0)
    assert _value(a, dataset, "product") == "新的" and _value(a, dataset, "body") == "新的內文"
    assert _value(a, dataset, "confidence") == "verified"
    assert _pending(a, dataset) == {}
    # One write: one set of changes for one commit; who and when are in the history.
    history = BiStore(a, dataset).history(CARD)
    assert any(h["field"] == "confidence" and h["by"] and h["at"] for h in history)

    # A reason, when given, is kept: the one decided proposal goes back and is rejected.
    item = next(p for p in _ok(_call(a, "GET", "/api/bi/proposals", dataset=dataset))["decided"]
                if p["field"] == "confidence")  # fmt: skip
    _ok(_post(a, f"/api/bi/cards/{CARD}/proposals/{item['id']}",
              {"dataset": dataset, "action": "pending"}))  # fmt: skip
    assert _value(a, dataset, "confidence") == "assumed"
    done = _ok(decide(count=1, field="confidence", action="reject", reason="沒有依據"))
    assert done["decided"] == 1 and _pending(a, dataset) == {}
    assert _value(a, dataset, "confidence") == "assumed"
    rejected = _ok(_call(a, "GET", "/api/bi/proposals", dataset=dataset))["decided"]
    assert [
        (p["field"], p["status"], p["reason"]) for p in rejected if p["field"] == "confidence"
    ] == [("confidence", "rejected", "沒有依據")]


def test_a_value_that_differs_inside_a_run_becomes_a_proposal(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    # Two chunks of one source, each naming the same card with a different supplier.
    padding = "\n\n".join(f"段落 {n} 的虛構內容。" * 30 for n in range(20))
    text = f"# 虛構\n\n{QUOTE}。\n\n{padding}\n\n{OTHER_QUOTE}。\n\n{padding}\n"
    assert len(extract.chunks(text)) >= 2

    def answer(chunk: str) -> dict[str, Any]:
        if QUOTE in chunk:
            return _answer(supplier=_fact("FAKE-A"))
        if OTHER_QUOTE in chunk:
            return _answer(supplier=_fact("FAKE-B", OTHER_QUOTE))
        return {"candidates": []}

    run_id = _run(a, dataset, answer, text=text)
    detail = _detail(a, dataset, run_id)
    item = next(f for f in detail["candidates"][0]["fields"] if f["field"] == "supplier")
    assert item["value"] == "FAKE-A"
    assert [o["value"] for o in item["alternatives"]] == ["FAKE-B"]
    assert detail["run"]["merge"]["proposal"] == 1
    assert "value_conflict" in {w["code"] for w in detail["candidates"][0]["warnings"]}

    _accept_and_commit(a, dataset, run_id)
    assert _value(a, dataset, "supplier") == "FAKE-A"
    pending = _pending(a, dataset)
    assert pending["supplier"]["value"] == "FAKE-B"
    assert pending["supplier"]["evidence"][0]["excerpt"] == OTHER_QUOTE


def test_a_proposals_evidence_travels_and_a_rebuild_makes_no_false_change(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _seed(a, dataset, product="舊的產品")
    run_id = _run(a, dataset, _answer(product=_fact("新的產品")))
    _accept_and_commit(a, dataset, run_id)
    assert not vault.Vault(a, vault_id).repo._pending()["sets"]
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _pending(b, dataset)["product"]["evidence"][0]["excerpt"] == QUOTE


def test_reading_fields_are_asked_for_in_the_source_language() -> None:
    assert "language of the source" in extract.READING_RULES
