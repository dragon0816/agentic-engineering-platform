"""Accepting a proposal: a card's value and its citations match (owner, 2026-11-05).

The proposal's evidence becomes the field's, and the replaced value's goes to history, readable
with the old value. All of it travels in the commit's units, so another PC rebuilds the same.
Fictional data. `docs/DECISIONS.md` 2026-11-05, `docs/CONTRACTS.md`.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from test_bi_ai_runs import Jobs, _runtime
from test_bi_card_page_import import _apply, _preview
from test_bi_extract import Scripted
from test_bi_vault import _call, _commit, _Drive, _ok, _push, _sync, _two_pcs
from test_bi_vault_sources import FOLDER

from aep_bi.cards import card_markdown, catalog, vault
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore
from aep_bi.host.bi_cards_api import route

OLD = "這段長文是虛構卡片目前的內容，有它自己的出處。" * 8
NEW = "一句話。"
PAGE = "---\ntype: technology\nname: FAKE-1\n---\n\n## 說明\n虛構的內容。\n"


def _answer(value: str, *, sourced: bool = True) -> dict[str, Any]:
    said = {"basis": "fact", "quote": value} if sourced else {"basis": "inference", "reason": "猜"}
    return {
        "candidates": [
            {
                "entity_type": "Technology",
                "name": "FAKE-1",
                "fields": {"body": {"value": value, **said}},
            }
        ]
    }


def _written(ws: Path, dataset: str, name: str, text: str, answer: Any) -> None:
    source = Staging(ws, dataset).add_source(name, text=text, actor="alice", folder=FOLDER)
    jobs = Jobs()
    body = {"dataset": dataset, "kind": "ingest", "source_id": source["id"], "path": "ai"}
    ai = _runtime(Scripted(answer), jobs)
    run = _ok(route(ws, "alice", "POST", "/api/bi/runs", {}, body, None, ai))["run"]
    jobs.run_all()
    found = _ok(_call(ws, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))
    for candidate in found["candidates"]:
        _ok(
            _call(ws, "POST", f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}",
                  {"dataset": dataset, "review": "accepted"})
        )  # fmt: skip
    _ok(_call(ws, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": dataset}))


def _proposed(
    tmp_path: Path, *, sourced: bool = True, old_sourced: bool = True
) -> tuple[_Drive, str, str, Path, Path, str, dict[str, Any]]:
    """A card whose `body` rests on 長.md, with a pending proposal to replace it."""
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _apply(
        a, _preview(a, dataset, [{"path": "BI/p.md", "text": PAGE}], folder=FOLDER)["preview_id"]
    )
    _written(a, dataset, "長.md", f"# 長\n\n{OLD}\n", _answer(OLD, sourced=old_sourced))
    _written(a, dataset, "短.md", f"# 短\n\n{NEW}\n", _answer(NEW, sourced=sourced))
    store = BiStore(a, dataset)
    found = store.find("Technology", "FAKE-1")
    assert found is not None
    pending = _ok(_call(a, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
    return (
        drive,
        vault_id,
        dataset,
        a,
        b,
        str(found["id"]),
        next(p for p in pending if p["field"] == "body"),
    )


def _accept(ws: Path, dataset: str, card: str, item: dict[str, Any]) -> None:
    _ok(
        _call(ws, "POST", f"/api/bi/cards/{card}/proposals/{item['id']}",
              {"dataset": dataset, "action": "accept", "base_version": item["version"]})
    )  # fmt: skip


def _cited(ws: Path, dataset: str, card: str) -> list[str]:
    evidence = BiStore(ws, dataset).evidence(card)
    return [e["source_name"] for e in evidence if e["field"] == "body"]


def _moved(ws: Path, dataset: str, card: str) -> list[dict[str, Any]]:
    history = BiStore(ws, dataset).history(card)
    return [h for h in history if h["field"] == "body" and "old_evidence" in h]


def _page(ws: Path, dataset: str, card: str) -> str:
    store = BiStore(ws, dataset)
    with closing(sqlite3.connect(store.path)) as db:
        return card_markdown.render_all(db, catalog.for_store(store))[card]


def test_the_proposals_evidence_replaces_the_fields_on_the_card_and_its_page(
    tmp_path: Path,
) -> None:
    _, _, dataset, a, _, card, item = _proposed(tmp_path)
    assert [e["source_name"] for e in item["evidence"]] == ["短.md"]
    assert _cited(a, dataset, card) == ["長.md"]
    assert "長.md" in _page(a, dataset, card) and "短.md" not in _page(a, dataset, card)

    _accept(a, dataset, card, item)
    store = BiStore(a, dataset)
    assert store.fields(card)["body"]["value"] == NEW
    assert _cited(a, dataset, card) == ["短.md"]
    # The rendered card, not the table: 參考來源 cites what the card now says.
    page = _page(a, dataset, card)
    assert "短.md" in page and NEW in page
    assert "長.md" not in page
    # The replaced value's evidence is with it in history.
    moved = _moved(a, dataset, card)[-1]
    assert moved["old"] == OLD and moved["new"] == NEW
    assert [e["source_name"] for e in moved["old_evidence"]] == ["長.md"]
    assert OLD[:20] in moved["old_evidence"][0]["excerpt"]


def test_another_pc_and_a_rebuild_give_the_same_result(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, card, item = _proposed(tmp_path)
    _accept(a, dataset, card, item)
    _commit(a, vault_id, "接受提案")
    _push(a, vault_id)
    expected = (_cited(a, dataset, card), _moved(a, dataset, card))

    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert (_cited(b, dataset, card), _moved(b, dataset, card)) == expected
    assert _page(b, dataset, card) == _page(a, dataset, card)

    # Nothing of it lives only in the local tables.
    vault.Vault(a, vault_id).rebuild()
    assert (_cited(a, dataset, card), _moved(a, dataset, card)) == expected
    units = vault.Vault(a, vault_id).repo.units()
    field = units[f"field:{card}:body"]
    assert [e["source_name"] for e in field["history"]["old_evidence"]] == ["長.md"]
    assert [e["source_name"] for e in units[f"evidence:{card}:body"]] == ["短.md"]


def test_discarding_brings_the_value_and_its_citation_back_together(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _, card, item = _proposed(tmp_path)
    _accept(a, dataset, card, item)
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/discard", {}))
    assert BiStore(a, dataset).fields(card)["body"]["value"] == OLD
    assert _cited(a, dataset, card) == ["長.md"]


def test_a_proposal_with_no_evidence_leaves_the_field_with_none(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _, card, item = _proposed(tmp_path, sourced=False)
    assert item["evidence"] == []
    _accept(a, dataset, card, item)
    assert BiStore(a, dataset).fields(card)["body"]["value"] == NEW
    assert _cited(a, dataset, card) == []
    assert "長.md" not in _page(a, dataset, card)
    assert [e["source_name"] for e in _moved(a, dataset, card)[-1]["old_evidence"]] == ["長.md"]
    # And so with an empty evidence unit, after a rebuild too.
    _commit(a, vault_id, "接受提案")
    vault.Vault(a, vault_id).rebuild()
    assert _cited(a, dataset, card) == []
    assert f"evidence:{card}:body" not in vault.Vault(a, vault_id).repo.units()


def test_a_field_with_no_evidence_gains_the_proposals_and_moves_nothing(tmp_path: Path) -> None:
    _, _, dataset, a, _, card, item = _proposed(tmp_path, old_sourced=False)
    assert item["current_evidence"] == [] and item["evidence"]
    _accept(a, dataset, card, item)
    assert _cited(a, dataset, card) == ["短.md"]
    assert _moved(a, dataset, card)[-1]["old_evidence"] == []


def test_rejecting_leaves_everything_as_it_was(tmp_path: Path) -> None:
    _, _, dataset, a, _, card, item = _proposed(tmp_path)
    store = BiStore(a, dataset)
    before = (store.fields(card), store.evidence(card), store.history(card))
    _ok(
        _call(a, "POST", f"/api/bi/cards/{card}/proposals/{item['id']}",
              {"dataset": dataset, "action": "reject", "reason": "虛構的理由"})
    )  # fmt: skip
    store = BiStore(a, dataset)
    assert (store.fields(card), store.evidence(card), store.history(card)) == before
    assert _moved(a, dataset, card) == []


def test_bulk_accept_does_the_same(tmp_path: Path) -> None:
    _, _, dataset, a, _, card, _item = _proposed(tmp_path)
    _ok(
        _call(a, "POST", "/api/bi/proposals/decide",
              {"dataset": dataset, "action": "accept", "reason": "虛構的理由", "field": "body",
               "origin": None, "count": 1})
    )  # fmt: skip
    assert BiStore(a, dataset).fields(card)["body"]["value"] == NEW
    assert _cited(a, dataset, card) == ["短.md"]
    assert [e["source_name"] for e in _moved(a, dataset, card)[-1]["old_evidence"]] == ["長.md"]


def test_a_correction_note_replaces_the_citation_and_undoing_it_restores_it(
    tmp_path: Path,
) -> None:
    """It broke the rule: the note's evidence was added beside the replaced value's."""
    _, vault_id, dataset, a, _, card, _item = _proposed(tmp_path)
    store = BiStore(a, dataset)
    version = int(store.card(card)["version"])  # type: ignore[index]
    note = _ok(
        _call(a, "POST", "/api/bi/corrections/preview",
              {"dataset": dataset, "card": card, "field": "body", "value": "更正後的內容",
               "base_version": version, "reason": "FAE 確認"})
    )  # fmt: skip
    done = _ok(
        _call(a, "POST", "/api/bi/corrections/apply",
              {"dataset": dataset, "text": note["text"], "base_version": note["base_version"]})
    )  # fmt: skip
    cited = _cited(a, dataset, card)
    assert "長.md" not in cited and len(cited) == 1
    assert [e["source_name"] for e in _moved(a, dataset, card)[-1]["old_evidence"]] == ["長.md"]

    _ok(
        _call(
            a, "POST", "/api/bi/import/undo", {"dataset": dataset, "import_id": done["import_id"]}
        )
    )
    assert BiStore(a, dataset).fields(card)["body"]["value"] == OLD
    assert _cited(a, dataset, card) == ["長.md"]
    vault.Vault(a, vault_id).rebuild()
    assert _cited(a, dataset, card) == ["長.md"]


def test_a_commit_from_before_this_reads_as_it_did(tmp_path: Path) -> None:
    """Its units have no `old_evidence`: nothing appears, nothing is diffed, and a pending
    proposal from then still decides."""
    _, vault_id, dataset, a, _, card, item = _proposed(tmp_path)
    target = vault.Vault(a, vault_id)
    field = target.repo.working_units()[f"field:{card}:body"]
    assert "old_evidence" not in field["history"]
    assert _moved(a, dataset, card) == []
    target.rebuild()
    assert _moved(a, dataset, card) == []
    _accept(a, dataset, card, item)
    assert _cited(a, dataset, card) == ["短.md"]


def test_the_card_keeps_its_home_when_its_only_citation_goes(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _, card, item = _proposed(tmp_path, sourced=False)
    store = BiStore(a, dataset)
    home = store.first_home(card)
    _accept(a, dataset, card, item)
    vault.Vault(a, vault_id).rebuild()
    assert BiStore(a, dataset).first_home(card) == home


def test_a_rename_leaves_the_fields_evidence_where_it_is(tmp_path: Path) -> None:
    """Not from a proposal, and a name's citation says where the card came from: unchanged."""
    _, _, dataset, a, _, card, _item = _proposed(tmp_path)
    store = BiStore(a, dataset)
    before = store.evidence(card)
    version = int(store.card(card)["version"])  # type: ignore[index]
    _ok(
        _call(a, "POST", f"/api/bi/cards/{card}/rename",
              {"dataset": dataset, "name": "FAKE-2", "base_version": version, "reason": "改名"})
    )  # fmt: skip
    assert BiStore(a, dataset).evidence(card) == before


def test_reverting_the_commit_brings_the_value_and_its_citation_back(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, card, item = _proposed(tmp_path)
    _push(a, vault_id)
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "虛構"}))
    _accept(a, dataset, card, item)
    _commit(a, vault_id, "接受提案")
    _push(a, vault_id)
    _ok(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/revert",
              {"version": "v1", "purpose": "回到 v1"})
    )  # fmt: skip
    assert BiStore(a, dataset).fields(card)["body"]["value"] == OLD
    assert _cited(a, dataset, card) == ["長.md"]
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert BiStore(b, dataset).fields(card)["body"]["value"] == OLD
    assert _cited(b, dataset, card) == ["長.md"]


@pytest.mark.parametrize(("choice", "value"), [("mine", NEW), ("theirs", "B 的更正")])
def test_a_push_conflict_chooses_the_value_and_its_citations_together(
    tmp_path: Path, choice: str, value: str
) -> None:
    drive, vault_id, dataset, a, b, card, item = _proposed(tmp_path)
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)

    # PC a accepts while PC b corrects the same field by hand.
    _accept(a, dataset, card, item)
    _commit(a, vault_id, "接受提案")
    version = int(BiStore(b, dataset).card(card)["version"])  # type: ignore[index]
    note = _ok(
        _call(b, "POST", "/api/bi/corrections/preview",
              {"dataset": dataset, "card": card, "field": "body", "value": "B 的更正",
               "base_version": version, "reason": "FAE 確認"})
    )  # fmt: skip
    _ok(
        _call(b, "POST", "/api/bi/corrections/apply",
              {"dataset": dataset, "text": note["text"], "base_version": note["base_version"]})
    )  # fmt: skip
    _push(b, vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)

    refused = _push(a, vault_id)
    assert refused["status"] == "conflicts"
    units = {c["unit"] for c in refused["conflicts"]}
    assert {f"field:{card}:body", f"evidence:{card}:body"} <= units
    # One choice, on the field.
    _ok(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/resolve",
              {"unit": f"field:{card}:body", "choice": choice})
    )  # fmt: skip
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    seen = [
        (BiStore(ws, dataset).fields(card)["body"]["value"], _cited(ws, dataset, card))
        for ws in (a, b)
    ]
    assert seen[0] == seen[1]
    assert seen[0][0] == value
    if choice == "mine":
        assert seen[0][1] == ["短.md"]
    else:
        assert len(seen[0][1]) == 1 and seen[0][1][0].startswith("correction-")
