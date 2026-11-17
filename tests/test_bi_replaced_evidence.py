"""A run's commit that replaces a value: the citations follow it (owner, 2026-11-05).

The new evidence replaces, and the old goes to history with the old value. Only for a replaced
value: where a value stays and another source adds to it, evidence appends, as for one card
reached from two domains. Undo gives back what it took. Fictional data.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_card_page_import import _apply, _preview
from test_bi_evidence_review import JUDGED
from test_bi_extract import Scripted
from test_bi_vault import _call, _commit, _Drive, _ok, _push, _sync, _two_pcs
from test_bi_vault_sources import FOLDER

from aep_bi.cards import card_markdown, catalog, vault
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore
from aep_bi.host.bi_cards_api import route

PAGE = "---\ntype: technology\nname: FAKE-1\n---\n\n## 說明\n虛構的內容。\n"
CSV_OLD = "技術,領域,成熟度\nFAKE-1,robotics,mature\n"
CSV_NEW = "技術,領域,成熟度\nFAKE-1,robotics,growth\n"


def _vault(tmp_path: Path) -> tuple[_Drive, str, str, Path, Path, str]:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _apply(
        a, _preview(a, dataset, [{"path": "BI/p.md", "text": PAGE}], folder=FOLDER)["preview_id"]
    )
    found = BiStore(a, dataset).find("Technology", "FAKE-1")
    assert found is not None
    return drive, vault_id, dataset, a, b, str(found["id"])


def _answer(**fields: Any) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "entity_type": "Technology",
                "name": "FAKE-1",
                "fields": {
                    name: {"value": value, "basis": "fact", "quote": quote}
                    for name, (value, quote) in fields.items()
                },
            }
        ]
    }


def _start(ws: Path, dataset: str, name: str, text: str, answer: Any = None) -> str:
    """A run of the source, asking the model anew: the same text would repeat a kept answer."""
    source = Staging(ws, dataset).add_source(name, text=text, actor="alice", folder=FOLDER)
    jobs = Jobs()
    body = {
        "dataset": dataset,
        "kind": "ingest",
        "source_id": source["id"],
        "path": "ai" if answer is not None else "rules",
        "fresh": True,
    }
    ai = _runtime(None if answer is None else Scripted(answer), jobs)
    run = _ok(route(ws, "alice", "POST", "/api/bi/runs", {}, body, None, ai))["run"]
    jobs.run_all()
    return str(run["id"])


def _commit_run(ws: Path, dataset: str, run_id: str, **review: Any) -> str:
    found = _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))
    for candidate in found["candidates"]:
        _ok(
            _call(ws, "POST", f"/api/bi/runs/{run_id}/candidates/{candidate['id']}",
                  {"dataset": dataset, "review": "accepted", **review})
        )  # fmt: skip
    done = _ok(_call(ws, "POST", f"/api/bi/runs/{run_id}/commit", {"dataset": dataset}))
    return str(done["run"]["commit"]["import_id"])


def _cited(ws: Path, dataset: str, card: str, field: str) -> list[str]:
    evidence = BiStore(ws, dataset).evidence(card)
    return sorted(e["source_name"] for e in evidence if e["field"] == field)


def _moved(ws: Path, dataset: str, card: str, field: str) -> list[dict[str, Any]]:
    history = BiStore(ws, dataset).history(card)
    return [h for h in history if h["field"] == field and h.get("old_evidence")]


def _value(ws: Path, dataset: str, card: str, field: str) -> Any:
    return BiStore(ws, dataset).fields(card)[field]["value"]


def _page(ws: Path, dataset: str, card: str) -> str:
    store = BiStore(ws, dataset)
    with closing(sqlite3.connect(store.path)) as db:
        return card_markdown.render_all(db, catalog.for_store(store))[card]


def _undo(ws: Path, dataset: str, import_id: str) -> None:
    _ok(_call(ws, "POST", "/api/bi/import/undo", {"dataset": dataset, "import_id": import_id}))


def test_a_rules_run_replacing_a_value_replaces_its_citation(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, card = _vault(tmp_path)
    _commit_run(a, dataset, _start(a, dataset, "舊.csv", CSV_OLD))
    assert _value(a, dataset, card, "maturity") == "mature"
    assert _cited(a, dataset, card, "maturity") == ["舊.csv"]
    assert _cited(a, dataset, card, "domain") == ["舊.csv"]

    second = _commit_run(a, dataset, _start(a, dataset, "新.csv", CSV_NEW))
    assert _value(a, dataset, card, "maturity") == "growth"
    assert _cited(a, dataset, card, "maturity") == ["新.csv"]
    moved = _moved(a, dataset, card, "maturity")[-1]
    assert moved["old"] == "mature" and moved["new"] == "growth"
    assert [e["source_name"] for e in moved["old_evidence"]] == ["舊.csv"]
    # The value that stayed: another source adds to its citations.
    assert _cited(a, dataset, card, "domain") == ["新.csv", "舊.csv"]
    assert _moved(a, dataset, card, "domain") == []

    # Another PC and a rebuild have the same, and the page says the same.
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _cited(b, dataset, card, "maturity") == ["新.csv"]
    assert _moved(b, dataset, card, "maturity") == _moved(a, dataset, card, "maturity")
    assert _page(b, dataset, card) == _page(a, dataset, card)
    references = _page(a, dataset, card).split("## 參考來源")[1]
    assert "舊.csv" in references  # for 領域
    assert not [line for line in references.splitlines() if "成熟度" in line and "舊.csv" in line]

    # Undone: the old value with the old citation, and the added citation gone.
    _undo(a, dataset, second)
    assert _value(a, dataset, card, "maturity") == "mature"
    assert _cited(a, dataset, card, "maturity") == ["舊.csv"]
    assert _cited(a, dataset, card, "domain") == ["舊.csv"]
    vault.Vault(a, vault_id).rebuild()
    assert _cited(a, dataset, card, "maturity") == ["舊.csv"]
    assert _cited(a, dataset, card, "domain") == ["舊.csv"]


def test_taking_the_new_value_in_review_replaces_its_citation(tmp_path: Path) -> None:
    _, _, dataset, a, _, card = _vault(tmp_path)
    first = _answer(body=("舊的內容", "舊的內容"))
    _commit_run(a, dataset, _start(a, dataset, "舊.md", "# 舊\n\n舊的內容\n", first))
    run = _start(a, dataset, "新.md", "# 新\n\n新的內容\n", _answer(body=("新的內容", "新的內容")))
    taken = _commit_run(a, dataset, run, take_new={"body": True})
    assert _value(a, dataset, card, "body") == "新的內容"
    assert _cited(a, dataset, card, "body") == ["新.md"]
    assert [e["source_name"] for e in _moved(a, dataset, card, "body")[-1]["old_evidence"]] == [
        "舊.md"
    ]
    assert "舊.md" not in _page(a, dataset, card) and "新.md" in _page(a, dataset, card)
    _undo(a, dataset, taken)
    assert _value(a, dataset, card, "body") == "舊的內容"
    assert _cited(a, dataset, card, "body") == ["舊.md"]


def test_a_second_source_of_the_same_value_adds_to_the_citations(tmp_path: Path) -> None:
    """One card reached from two domains, whose second run writes something else too."""
    _, _, dataset, a, _, card = _vault(tmp_path)
    first = _answer(body=("同樣的內容", "同樣的內容"))
    _commit_run(a, dataset, _start(a, dataset, "一.md", "# 一\n\n同樣的內容\n", first))
    more = _answer(body=("同樣的內容", "同樣的內容"), standard_body=("IEEE", "IEEE"))
    run = _start(a, dataset, "二.md", "# 二\n\n同樣的內容\n\nIEEE\n", more)
    second = _commit_run(a, dataset, run)
    assert _cited(a, dataset, card, "body") == ["一.md", "二.md"]
    assert _moved(a, dataset, card, "body") == []
    # Undoing the second takes only what it added.
    _undo(a, dataset, second)
    assert _value(a, dataset, card, "body") == "同樣的內容"
    assert _cited(a, dataset, card, "body") == ["一.md"]
    assert _cited(a, dataset, card, "standard_body") == []


def test_a_list_that_only_grows_keeps_its_citations(tmp_path: Path) -> None:
    _, _, dataset, a, _, card = _vault(tmp_path)
    field = "new_test_requirements"
    first = _answer(new_test_requirements=(["甲"], "甲項需求的原文段落"))
    _commit_run(a, dataset, _start(a, dataset, "一.md", "# 一\n\n甲項需求的原文段落\n", first))
    grown = _answer(new_test_requirements=(["乙"], "乙項需求的原文段落"))
    second = _commit_run(
        a, dataset, _start(a, dataset, "二.md", "# 二\n\n乙項需求的原文段落\n", grown)
    )
    assert sorted(_value(a, dataset, card, field)) == ["乙", "甲"]
    assert _cited(a, dataset, card, field) == ["一.md", "二.md"]
    assert _moved(a, dataset, card, field) == []
    _undo(a, dataset, second)
    assert _value(a, dataset, card, field) == ["甲"]
    assert _cited(a, dataset, card, field) == ["一.md"]


def test_undoing_a_run_that_filled_a_field_takes_its_citation_too(tmp_path: Path) -> None:
    """Before, the field went and its citation stayed on the card page."""
    _, _, dataset, a, _, card = _vault(tmp_path)
    run = _start(a, dataset, "一.md", "# 一\n\n內容\n", _answer(body=("內容", "內容")))
    filled = _commit_run(a, dataset, run)
    assert _cited(a, dataset, card, "body") == ["一.md"]
    _undo(a, dataset, filled)
    assert "body" not in BiStore(a, dataset).fields(card)
    assert _cited(a, dataset, card, "body") == []
    assert "一.md" not in _page(a, dataset, card)


def test_a_change_made_since_keeps_its_citation_through_an_undo(tmp_path: Path) -> None:
    _, _, dataset, a, _, card = _vault(tmp_path)
    first = _commit_run(a, dataset, _start(a, dataset, "舊.csv", CSV_OLD))
    run = _start(a, dataset, "新.md", "# 新\n\ngrowth\n", _answer(maturity=("growth", "growth")))
    _commit_run(a, dataset, run, take_new={"maturity": True})
    _undo(a, dataset, first)
    assert _value(a, dataset, card, "maturity") == "growth"
    assert _cited(a, dataset, card, "maturity") == ["新.md"]


def test_a_conflict_proposal_brings_the_lost_values_citation(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, card = _vault(tmp_path)
    _commit_run(a, dataset, _start(a, dataset, "舊.csv", CSV_OLD))
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)

    # Both replace the value and push before OneDrive brings the other's commit.
    for ws, name, value in ((a, "甲.md", "growth"), (b, "乙.md", "emerging")):
        text = f"# 來源\n\n{name} {value}\n"
        run = _start(ws, dataset, name, text, _answer(maturity=(value, value)))
        _commit_run(ws, dataset, run, take_new={"maturity": True})
        assert _push(ws, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)

    winner = _value(a, dataset, card, "maturity")
    assert _value(b, dataset, card, "maturity") == winner
    pending = _ok(_call(a, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
    lost = next(
        p for p in pending if p["field"] == "maturity" and p["source"]["kind"] == "conflict"
    )
    assert lost["value"] != winner
    source = "甲.md" if lost["value"] == "growth" else "乙.md"
    assert [e["source_name"] for e in lost["evidence"]] == [source]

    _ok(
        _call(a, "POST", f"/api/bi/cards/{card}/proposals/{lost['id']}",
              {"dataset": dataset, "action": "accept", "base_version": lost["version"],
               "reason": "虛構的理由"})
    )  # fmt: skip
    assert _value(a, dataset, card, "maturity") == lost["value"]
    assert _cited(a, dataset, card, "maturity") == [source]
    _commit(a, vault_id, "接受另一個值")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _value(b, dataset, card, "maturity") == lost["value"]
    assert _cited(b, dataset, card, "maturity") == [source]


def _reviewed_body(ws: Path, dataset: str, card: str) -> dict[str, Any]:
    row = next(e for e in BiStore(ws, dataset).evidence(card) if e["field"] == "body")
    return {
        "dataset": dataset,
        "target": "card",
        "card": card,
        "field": "body",
        "reference_id": row["reference_id"],
        "base_version": int(BiStore(ws, dataset).card(card)["version"]),  # type: ignore[index]
        **JUDGED,
    }


def test_a_review_goes_with_its_row_and_a_moved_row_cannot_be_reviewed(tmp_path: Path) -> None:
    _, _, dataset, a, _, card = _vault(tmp_path)
    first = _answer(body=("舊的內容", "舊的內容"))
    _commit_run(a, dataset, _start(a, dataset, "舊.md", "# 舊\n\n舊的內容\n", first))
    body = _reviewed_body(a, dataset, card)
    note = _ok(_call(a, "POST", "/api/bi/evidence-reviews/preview", body))
    _ok(
        _call(a, "POST", "/api/bi/evidence-reviews/apply",
              {"dataset": dataset, "text": note["text"], "base_version": note["base_version"]})
    )  # fmt: skip
    reviewed = next(e for e in BiStore(a, dataset).evidence(card) if e["field"] == "body")
    assert reviewed["assessment"]["current"]

    # Replaced: the review stays readable with the old value.
    run = _start(a, dataset, "新.md", "# 新\n\n新的內容\n", _answer(body=("新的內容", "新的內容")))
    _commit_run(a, dataset, run, take_new={"body": True})
    old = _moved(a, dataset, card, "body")[-1]["old_evidence"][0]
    assert old["assessment"]["current"] == reviewed["assessment"]["current"]

    # The moved row is no longer the field's, so a review of it is refused, and writes nothing.
    stale = {**body, "base_version": int(BiStore(a, dataset).card(card)["version"])}  # type: ignore[index]
    status, said = _call(a, "POST", "/api/bi/evidence-reviews/preview", stale)
    assert status != 200 and said["ok"] is False
    assert _moved(a, dataset, card, "body")[-1]["old_evidence"][0] == old

    # The new row can be, and starts with no review of its own.
    current = _reviewed_body(a, dataset, card)
    assert current["reference_id"] != body["reference_id"]
    fresh = next(e for e in BiStore(a, dataset).evidence(card) if e["field"] == "body")
    assert not (fresh.get("assessment") or {}).get("current")
    assert _ok(_call(a, "POST", "/api/bi/evidence-reviews/preview", current))["text"]


def _repeat(ws: Path, dataset: str, name: str, text: str, value: str) -> str:
    return _start(ws, dataset, name, text, _answer(body=(value, value)))


def test_a_source_that_only_repeats_a_value_adds_its_citation_and_nothing_else(
    tmp_path: Path,
) -> None:
    """Owner: 「證具, raw data連結就append上去」. The card's version stays: nothing it says
    changed, so nobody's review of it goes stale. On another PC and after a rebuild, the same."""
    drive, vault_id, dataset, a, b, card = _vault(tmp_path)
    same = "同樣的內容"
    _commit_run(a, dataset, _repeat(a, dataset, "一.md", f"# 一\n\n{same}\n", same))
    store = BiStore(a, dataset)
    before = (store.card(card)["version"], store.card(card)["updated"], store.history(card))  # type: ignore[index]

    run = _repeat(a, dataset, "二.md", f"# 二\n\n{same}\n\n二\n", same)
    found = _ok(_call(a, "GET", f"/api/bi/runs/{run}", dataset=dataset))
    candidate = found["candidates"][0]
    assert candidate["action"] == "unchanged" and candidate["citations"] == ["body"]
    assert found["run"]["summary"]["citations"] == 1

    second = _commit_run(a, dataset, run)
    assert _cited(a, dataset, card, "body") == ["一.md", "二.md"]
    store = BiStore(a, dataset)
    after = (store.card(card)["version"], store.card(card)["updated"], store.history(card))  # type: ignore[index]
    assert after == before
    page = _page(a, dataset, card)
    assert "一.md" in page and "二.md" in page

    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _cited(b, dataset, card, "body") == ["一.md", "二.md"]
    assert BiStore(b, dataset).card(card)["version"] == before[0]  # type: ignore[index]
    vault.Vault(a, vault_id).rebuild()
    assert _cited(a, dataset, card, "body") == ["一.md", "二.md"]

    # Undo takes only the citation.
    _undo(a, dataset, second)
    assert _value(a, dataset, card, "body") == same
    assert _cited(a, dataset, card, "body") == ["一.md"]
    assert BiStore(a, dataset).card(card)["version"] == before[0]  # type: ignore[index]


def test_reading_the_same_source_again_adds_nothing_twice(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, _, card = _vault(tmp_path)
    same = "同樣的內容"
    text = f"# 一\n\n{same}\n\nIEEE\n"
    _commit_run(a, dataset, _repeat(a, dataset, "一.md", text, same))
    units = vault.Vault(a, vault_id).repo.working_units
    rows = units()[f"evidence:{card}:body"]

    # Nothing new: not offered as a citation, and there is nothing to write.
    run = _start(a, dataset, "一.md", text, _answer(body=(same, same)))
    found = _ok(_call(a, "GET", f"/api/bi/runs/{run}", dataset=dataset))
    assert found["candidates"][0]["action"] == "unchanged"
    assert found["candidates"][0]["citations"] == []
    assert found["run"]["summary"]["citations"] == 0

    # With something else to write, its repeated citation still goes in once.
    more = _answer(body=(same, same), standard_body=("IEEE", "IEEE"))
    _commit_run(a, dataset, _start(a, dataset, "一.md", text, more))
    assert _value(a, dataset, card, "standard_body") == "IEEE"
    assert units()[f"evidence:{card}:body"] == rows
    assert _cited(a, dataset, card, "body") == ["一.md"]


def test_a_replay_that_loses_the_field_does_not_leave_its_citation_on_the_winner(
    tmp_path: Path,
) -> None:
    """Field and evidence are separate units. The other side changed only the field, so this
    side's evidence applied while its value lost: the winning value showed a citation of
    text it does not hold, until a person decided. Now the lost commit's evidence is not read,
    and it comes back with its value when the conflict is accepted."""
    drive, vault_id, dataset, a, b, card = _vault(tmp_path)
    old = "舊的內容"
    _commit_run(a, dataset, _repeat(a, dataset, "舊.md", f"# 舊\n\n{old}\n", old))
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)

    # PC b changes only the field, and is first; PC a takes a new value with its citation.
    bob = BiStore(b, dataset)
    held = bob.card(card)
    assert held is not None
    bob.set_field(card, "body", "B 的內容", base_version=int(held["version"]), actor="bob")
    _commit(b, vault_id, "只改值")
    assert _push(b, vault_id)["status"] == "pushed"
    time.sleep(1.1)  # commits replay in time order
    new = "新的內容"
    run = _repeat(a, dataset, "新.md", f"# 新\n\n{new}\n", new)
    _commit_run(a, dataset, run, take_new={"body": True})
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)

    for ws in (a, b):
        assert _value(ws, dataset, card, "body") == "B 的內容"
        assert "新.md" not in _cited(ws, dataset, card, "body")
        assert "新.md" not in _page(ws, dataset, card)
        vault.Vault(ws, vault_id).rebuild()
        assert "新.md" not in _cited(ws, dataset, card, "body")

    # Nothing is staged by reading it differently from its unit.
    assert vault.Vault(a, vault_id).repo.status()["uncommitted"] == 0

    # Accepted, the lost value comes back with its own citation.
    pending = _ok(_call(a, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
    lost = next(p for p in pending if p["field"] == "body" and p["source"]["kind"] == "conflict")
    assert lost["value"] == new and [e["source_name"] for e in lost["evidence"]] == ["新.md"]
    _ok(
        _call(a, "POST", f"/api/bi/cards/{card}/proposals/{lost['id']}",
              {"dataset": dataset, "action": "accept", "base_version": lost["version"]})
    )  # fmt: skip
    assert _value(a, dataset, card, "body") == new
    assert _cited(a, dataset, card, "body") == ["新.md"]
