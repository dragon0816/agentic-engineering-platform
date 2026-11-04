"""A model's supply link by its two ends, a repeated answer, a domain from the application
(owner, 2026-11-04; `docs/phases/BI_EXTRACTION_VARIANCE.md`). All data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok, _two_pcs

from capabilities.bi_cards import answer_cache, vault
from capabilities.bi_cards.store import BiStore, PlannedRow, card_id_for
from host_runtime.bi_cards_api import route

KIND = "SupplyLink"
SEED = "FAKE-A→FAKE-B-舊的產品"
QUOTE = "FAKE-A 供應 FAKE-B"
NOTE = f"# 虛構\n\n{QUOTE}。\n"
FOLDER = "applications/aidc/sources"


def _fact(value: Any, quote: str = QUOTE) -> dict[str, Any]:
    return {"value": value, "basis": "fact", "quote": quote}


def _link(
    name: str, supplier: str = "FAKE-A", customer: str = "FAKE-B", **more: Any
) -> dict[str, Any]:
    fields = {
        "name": _fact(name, "FAKE-A"),
        "supplier": _fact(supplier),
        "customer": _fact(customer),
        **more,
    }
    return {"entity_type": KIND, "name": name, "fields": fields}


def _seed(ws: Path, dataset: str, name: str = SEED, **values: Any) -> str:
    BiStore(ws, dataset).apply(
        [
            PlannedRow(
                row=1,
                entity_type=KIND,
                canonical_key=name,
                name=name,
                values={"name": name, "supplier": "FAKE-A", "customer": "FAKE-B", **values},
                synthetic=False,
            )
        ],
        filename="seed.csv",
        entity_type=KIND,
        actor="alice",
    )
    return card_id_for(KIND, name)


def _post(ws: Path, path: str, body: Any, ai: Any = None) -> Any:
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _run(ws: Path, dataset: str, *candidates: dict[str, Any], **given: Any) -> tuple[str, Scripted]:
    body = {"dataset": dataset, "name": "note.md", "text": NOTE, "folder": FOLDER}
    source = _ok(_post(ws, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    model = Scripted({"candidates": list(candidates)})
    start = {"dataset": dataset, "kind": "ingest", "source_id": source, "types": [KIND], **given}
    run = _ok(_post(ws, "/api/bi/runs", start, _runtime(model, jobs)))["run"]
    jobs.run_all()
    return str(run["id"]), model


def _detail(ws: Path, dataset: str, run_id: str) -> dict[str, Any]:
    return _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))


def _review(ws: Path, dataset: str, run_id: str, cid: str, **body: Any) -> Any:
    return _post(ws, f"/api/bi/runs/{run_id}/candidates/{cid}", {"dataset": dataset, **body})


def test_a_models_supply_link_updates_the_card_of_its_pair(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    card = _seed(a, dataset, product="舊的產品")
    run_id, _ = _run(a, dataset, _link("FAKE-A→FAKE-B-晶片製造", product=_fact("新的產品")))
    (candidate,) = _detail(a, dataset, run_id)["candidates"]
    assert (candidate["match"], candidate["action"]) == ("existing", "update")
    assert candidate["match_ids"] == [card] and candidate["canonical_key"] == SEED
    by_field = {f["field"]: f for f in candidate["fields"]}
    assert by_field["name"]["merge"] == "key_kept" and by_field["product"]["merge"] == "proposal"

    _ok(_review(a, dataset, run_id, candidate["id"], review="accepted"))
    _ok(_post(a, f"/api/bi/runs/{run_id}/commit", {"dataset": dataset}))
    store = BiStore(a, dataset)
    assert [c["canonical_key"] for c in store.card_rows()] == [SEED]  # the seed keeps its identity
    assert store.fields(card)["name"]["value"] == SEED
    assert store.fields(card)["product"]["value"] == "舊的產品"
    assert [p["value"] for p in store.proposals(card)] == ["新的產品"]


def test_a_new_pair_is_a_new_card_and_an_import_keeps_its_own_key(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset)
    run_id, _ = _run(a, dataset, _link("FAKE-A→FAKE-C-模組", customer="FAKE-C"))
    (candidate,) = _detail(a, dataset, run_id)["candidates"]
    assert candidate["action"] == "create"
    # Not a model's: a row of another name on the same pair stays its own card.
    _seed(a, dataset, name="FAKE-A→FAKE-B-另一個")
    assert len(BiStore(a, dataset).card_rows()) == 2


def test_several_cards_on_a_pair_are_for_a_person(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    one = _seed(a, dataset)
    two = _seed(a, dataset, name="FAKE-A→FAKE-B-另一個")
    run_id, _ = _run(a, dataset, _link("FAKE-A→FAKE-B-第三種"))
    (candidate,) = _detail(a, dataset, run_id)["candidates"]
    assert candidate["match"] == "ambiguous" and sorted(candidate["match_ids"]) == sorted(
        [one, two]
    )
    assert "match_unresolved" in {e["code"] for e in candidate["errors"]}
    status, body = _review(a, dataset, run_id, candidate["id"], review="accepted")
    assert (status, body["code"]) == (400, "candidate_invalid")
    done = _ok(
        _review(a, dataset, run_id, candidate["id"], match={"action": "update", "card_id": two})
    )
    assert done["candidate"]["match_ids"] == [two] and not done["candidate"]["errors"]


def test_several_candidates_for_one_pair_are_for_a_person(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    run_id, _ = _run(
        a,
        dataset,
        _link("FAKE-A→FAKE-B-甲"),
        _link("FAKE-A→FAKE-B-乙"),
        _link("FAKE-A→FAKE-C-丙", customer="FAKE-C"),
    )
    found = {c["name"]: c for c in _detail(a, dataset, run_id)["candidates"]}
    first, second = found["FAKE-A→FAKE-B-甲"], found["FAKE-A→FAKE-B-乙"]
    assert "pair_repeated" in {e["code"] for e in first["errors"]}
    assert second["pair_repeats"] == ["FAKE-A→FAKE-B-甲"]
    assert not found["FAKE-A→FAKE-C-丙"]["errors"]
    status, body = _review(a, dataset, run_id, first["id"], review="accepted")
    assert (status, body["code"]) == (400, "candidate_invalid")
    # Skip one: the other is free; nothing merged.
    _ok(_review(a, dataset, run_id, second["id"], match={"action": "skip"}))
    after = {c["name"]: c for c in _detail(a, dataset, run_id)["candidates"]}
    assert not after["FAKE-A→FAKE-B-甲"]["errors"]
    _ok(_review(a, dataset, run_id, first["id"], review="accepted"))


def test_a_recheck_applies_the_match_to_a_run_with_no_model_call(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    run_id, model = _run(a, dataset, _link("FAKE-A→FAKE-B-晶片製造"))
    asked = len(model.requests)
    assert _detail(a, dataset, run_id)["candidates"][0]["action"] == "create"
    card = _seed(a, dataset)  # the pair gets a card afterwards
    done = _ok(_post(a, f"/api/bi/runs/{run_id}/recheck", {"dataset": dataset}))
    assert done["candidates"][0]["match_ids"] == [card] and len(model.requests) == asked


def test_an_identical_request_reuses_its_answer(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    answer = _link("FAKE-A→FAKE-B-晶片製造")
    first, model = _run(a, dataset, answer)
    assert len(model.requests) == 1
    held = _detail(a, dataset, first)["run"]["answers"]
    assert (held["reused"], held["asked"]) == (0, 1)
    # The same prompt again: no call, the same candidates.
    second, again = _run(a, dataset, _link("會被忽略的回答"))
    assert again.requests == []
    assert _detail(a, dataset, second)["run"]["answers"]["reused"] == 1
    assert [c["name"] for c in _detail(a, dataset, second)["candidates"]] == [answer["name"]]
    # A person can ask anyway.
    third, fresh = _run(a, dataset, answer, fresh=True)
    assert len(fresh.requests) == 1 and _detail(a, dataset, third)["run"]["answers"]["reused"] == 0


def test_a_changed_prompt_asks_again_and_a_failure_is_not_kept(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _, model = _run(a, dataset, _link("FAKE-A→FAKE-B-晶片製造"))
    assert len(model.requests) == 1
    # A card named in the known list changes the prompt.
    _seed(a, dataset)
    _, changed = _run(a, dataset, _link("FAKE-A→FAKE-B-晶片製造"))
    assert len(changed.requests) == 1

    from common.execution import Failure

    body = {
        "dataset": dataset,
        "name": "other.md",
        "text": "# 虛構\n\n另一段。\n",
        "folder": FOLDER,
    }
    source = _ok(_post(a, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    bad = Scripted(Failure(code="model_http_error", message="503"))
    start = {"dataset": dataset, "kind": "ingest", "source_id": source, "types": [KIND]}
    _ok(_post(a, "/api/bi/runs", start, _runtime(bad, jobs)))
    jobs.run_all()
    jobs = Jobs()
    good = Scripted({"candidates": []})
    _ok(_post(a, "/api/bi/runs", start, _runtime(good, jobs)))
    jobs.run_all()
    assert len(good.requests) == 1


def test_clearing_removes_the_kept_answers(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _run(a, dataset, _link("FAKE-A→FAKE-B-晶片製造"))
    folder = BiStore(a, dataset).dir / answer_cache.FOLDER
    assert list(folder.glob("*.json"))
    answer_cache.clear(BiStore(a, dataset).dir)
    assert not folder.exists()


def _pages(ws: Path, dataset: str, text: str, **given: Any) -> dict[str, Any]:
    body = {"dataset": dataset, "pages": [{"path": "technology.csv", "text": text}], **given}
    return _ok(_post(ws, "/api/bi/import/pages/preview", body))


def test_an_import_takes_the_domain_of_its_application(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    plan = _pages(a, dataset, "name\nFAKE-TECH\n", folder=FOLDER)
    _ok(_post(a, "/api/bi/import/pages/apply", {"preview_id": plan["preview_id"]}))
    store = BiStore(a, dataset)
    card = card_id_for("Technology", "FAKE-TECH")
    assert store.fields(card)["domain"]["value"] == ["AIDC"]
    held = [e for e in store.evidence(card) if e["field"] == "domain"]
    assert [e["basis"] for e in held] == ["inference"]
    # A row that says its domain keeps it; a library folder has none to give.
    plan = _pages(a, dataset, "name,domain\nFAKE-OWN,robotics\n", folder=FOLDER)
    _ok(_post(a, "/api/bi/import/pages/apply", {"preview_id": plan["preview_id"]}))
    own = BiStore(a, dataset).fields(card_id_for("Technology", "FAKE-OWN"))
    assert own["domain"]["value"] == ["robotics"]
    plan = _pages(a, dataset, "name\nFAKE-LIB\n", folder="library/products/sources")
    _ok(_post(a, "/api/bi/import/pages/apply", {"preview_id": plan["preview_id"]}))
    assert "domain" not in BiStore(a, dataset).fields(card_id_for("Technology", "FAKE-LIB"))
    # With no folder, as before.
    plan = _pages(a, dataset, "name\nFAKE-NONE\n")
    _ok(_post(a, "/api/bi/import/pages/apply", {"preview_id": plan["preview_id"]}))
    assert "domain" not in BiStore(a, dataset).fields(card_id_for("Technology", "FAKE-NONE"))


def test_cards_with_no_domain_take_their_applications_in_one_commit(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    for name, folder in (
        ("FAKE-ONE", FOLDER),
        ("FAKE-TWO", FOLDER),
        ("FAKE-TWO", "applications/robotics/sources"),
        ("FAKE-LIB", "library/products/sources"),
    ):
        # Different text: the same text is one source, kept in its first folder.
        text = f"name,body\n{name},虛構內容 {folder}\n"
        plan = _ok(
            _post(
                a,
                "/api/bi/import/pages/preview",
                {
                    "dataset": dataset,
                    "pages": [{"path": f"technology-{folder.split('/')[1]}.csv", "text": text}],
                },
            )
        )
        _ok(
            _post(
                a,
                "/api/bi/import/pages/apply",
                {"preview_id": plan["preview_id"], "folder": folder},
            )
        )
    url = f"/api/bi/vaults/{vault_id}/fill-domains"
    target = vault.Vault(a, vault_id)
    commits = len(target.repo.local_commits())
    looked = _ok(_post(a, url, {}))
    assert looked["applied"] is False and looked["fill"] == 2
    assert [c["name"] for c in looked["left"]] == ["FAKE-LIB"]
    assert len(target.repo.local_commits()) == commits  # nothing written
    done = _ok(_post(a, url, {"confirm": True}))
    assert done["applied"] is True and "推論" in done["purpose"]
    commit = target.repo.local_commits()[-1]
    assert len(target.repo.local_commits()) == commits + 1 and "推論" in json.dumps(
        commit, ensure_ascii=False
    )
    store = BiStore(a, dataset)
    one = card_id_for("Technology", "FAKE-ONE")
    two = card_id_for("Technology", "FAKE-TWO")
    assert store.fields(one)["domain"]["value"] == ["AIDC"]
    assert store.fields(two)["domain"]["value"] == ["AIDC", "robotics"]
    assert [e["basis"] for e in store.evidence(one) if e["field"] == "domain"] == ["inference"]
    assert not target.repo._pending()["sets"]
    # Again: nothing left to do.
    assert _ok(_post(a, url, {"confirm": True}))["fill"] == 0
