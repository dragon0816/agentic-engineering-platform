"""Re-run and diff: only differing values are listed, and only confirmed ones commit
(`docs/phases/BI_CARD_MODEL.md` §5.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _commit, _ok, _push, _refused, _row, _sync, _two_pcs

from aep_bi.cards import rerun, vault
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, PlannedRow
from aep_bi.host.bi_cards_api import route

ACTOR = "tester"
TEXT = "# 規格（虛構）\n\nTSN 由 IEEE 802.1 制定。\n成熟度屬於成長期。\n相關機構 IETF。\n"


def _call(ws: Path, method: str, path: str, body: Any = None, ai: Any = None, **q: str) -> Any:
    return route(ws, ACTOR, method, path, q, body, None, ai)


def _answer(**values: str) -> dict[str, Any]:
    quotes = {"IEEE 802.1": "IEEE 802.1", "IETF": "IETF", "growth": "成長期"}
    return {
        "candidates": [
            {
                "entity_type": "Technology",
                "name": "TSN",
                "fields": {
                    name: {"value": value, "basis": "fact", "quote": quotes[value]}
                    for name, value in values.items()
                },
            }
        ]
    }


def _seed(ws: Path, *values: Any, dataset: str = "demo") -> tuple[BiStore, str]:
    store = BiStore(ws, dataset)
    if not store.exists:
        store.create("bi.schema/v1.1")
    store.apply(
        [
            PlannedRow(
                2, "Technology", "TSN", "TSN", {"standard_body": "ISO", "maturity": "growth"}, False
            )
        ],
        filename="tech.csv",
        entity_type="Technology",
        actor="x via web",
    )
    source = _ok(
        _call(ws, "POST", "/api/bi/sources", {"dataset": dataset, "name": "spec.md", "text": TEXT})
    )["source"]["id"]
    return store, str(source)


def _start(ws: Path, source: str, model: Scripted, jobs: Jobs, dataset: str = "demo") -> str:
    body = {"dataset": dataset, "sources": [source], "start": True}
    answer = _ok(_call(ws, "POST", "/api/bi/reruns/preview", body, _runtime(model, jobs)))
    jobs.run_all()
    return str(answer["rerun"]["id"])


def _view(ws: Path, rerun_id: str, dataset: str = "demo") -> dict[str, Any]:
    return dict(_ok(_call(ws, "GET", f"/api/bi/reruns/{rerun_id}", dataset=dataset))["rerun"])


def _confirm(ws: Path, rerun_id: str, items: list[str], dataset: str = "demo") -> Any:
    body = {"dataset": dataset, "items": items}
    return _call(ws, "POST", f"/api/bi/reruns/{rerun_id}/confirm", body)


def test_the_count_comes_first_and_costs_nothing(tmp_path: Path) -> None:
    store, source = _seed(tmp_path)
    model = Scripted(_answer(standard_body="IEEE 802.1"))
    jobs = Jobs()
    before = store.path.read_bytes()
    answer = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/reruns/preview",
            {"dataset": "demo", "sources": [source]},
            _runtime(model, jobs),
        )
    )
    assert (answer["started"], answer["count"]) == (False, 1)
    assert answer["sources"][0]["name"] == "spec.md"
    assert model.requests == [] and jobs.pending == []
    assert store.path.read_bytes() == before


def test_only_differing_values_are_listed(tmp_path: Path) -> None:
    store, source = _seed(tmp_path)
    jobs = Jobs()
    # standard_body differs, maturity is the same, and nothing else was found.
    rerun_id = _start(
        tmp_path, source, Scripted(_answer(standard_body="IEEE 802.1", maturity="growth")), jobs
    )
    view = _view(tmp_path, rerun_id)
    assert view["status"] == "ready"
    (item,) = view["items"]
    assert (item["field"], item["current"], item["new"]) == ("standard_body", "ISO", "IEEE 802.1")
    assert item["person_set"] is False and item["name"] == "TSN"
    assert item["evidence"][0]["excerpt"] and item["source"] == "spec.md"
    # Nothing is written by making the list.
    card = store.find("Technology", "TSN")
    assert card is not None
    assert store.fields(card["id"])["standard_body"]["value"] == "ISO"
    assert store.proposals(card["id"]) == []


def test_a_model_that_found_less_clears_nothing(tmp_path: Path) -> None:
    store, source = _seed(tmp_path)
    jobs = Jobs()
    rerun_id = _start(tmp_path, source, Scripted({"candidates": []}), jobs)
    view = _view(tmp_path, rerun_id)
    assert view["status"] == "ready" and view["items"] == []
    _refused(_confirm(tmp_path, rerun_id, []), 400, "items_missing")
    card = store.find("Technology", "TSN")
    assert card is not None
    fields = store.fields(card["id"])
    assert (fields["standard_body"]["value"], fields["maturity"]["value"]) == ("ISO", "growth")


def test_only_confirmed_items_commit_and_nothing_else(tmp_path: Path) -> None:
    store, source = _seed(tmp_path)
    jobs = Jobs()
    answer = _answer(standard_body="IEEE 802.1", maturity="growth")
    answer["candidates"][0]["fields"]["body"] = {
        "value": "相關機構 IETF",
        "basis": "fact",
        "quote": "IETF",
    }
    rerun_id = _start(tmp_path, source, Scripted(answer), jobs)
    items = {i["field"]: i for i in _view(tmp_path, rerun_id)["items"]}
    assert set(items) == {"standard_body", "body"}
    card = store.find("Technology", "TSN")
    assert card is not None
    done = _ok(_confirm(tmp_path, rerun_id, [items["standard_body"]["id"]]))
    assert done["commit"]["values"] == 1 and done["commit"]["updated"] == 1
    fields = store.fields(card["id"])
    assert fields["standard_body"]["value"] == "IEEE 802.1"
    assert "body" not in fields
    assert store.proposals(card["id"]) == []
    assert {e["field"] for e in store.evidence(card["id"])} == {"standard_body"}
    # Once.
    _refused(_confirm(tmp_path, rerun_id, [items["body"]["id"]]), 409, "run_committed")


def test_a_persons_value_is_marked_and_replaced_only_when_confirmed(tmp_path: Path) -> None:
    store, source = _seed(tmp_path)
    card = store.find("Technology", "TSN")
    assert card is not None
    store.set_field(
        card["id"], "standard_body", "PERSON", base_version=card["version"], actor="bob via web"
    )
    jobs = Jobs()
    rerun_id = _start(tmp_path, source, Scripted(_answer(standard_body="IEEE 802.1")), jobs)
    (item,) = _view(tmp_path, rerun_id)["items"]
    assert item["person_set"] is True and item["current"] == "PERSON"
    _ok(_confirm(tmp_path, rerun_id, [item["id"]]))
    assert store.fields(card["id"])["standard_body"]["value"] == "IEEE 802.1"
    assert store.proposals(card["id"]) == []


def test_a_listed_card_that_moved_refuses_the_whole(tmp_path: Path) -> None:
    store, source = _seed(tmp_path)
    jobs = Jobs()
    rerun_id = _start(tmp_path, source, Scripted(_answer(standard_body="IEEE 802.1")), jobs)
    (item,) = _view(tmp_path, rerun_id)["items"]
    card = store.find("Technology", "TSN")
    assert card is not None
    store.set_field(card["id"], "body", "別人改的", base_version=card["version"], actor="x")
    _refused(_confirm(tmp_path, rerun_id, [item["id"]]), 409, "cards_changed")
    assert store.fields(card["id"])["standard_body"]["value"] == "ISO"


def test_a_new_card_needs_its_required_fields_confirmed_with_it(tmp_path: Path) -> None:
    store, source = _seed(tmp_path)
    jobs = Jobs()
    answer = _answer(standard_body="IETF")
    answer["candidates"][0]["name"] = "全新技術"
    rerun_id = _start(tmp_path, source, Scripted(answer), jobs)
    items = _view(tmp_path, rerun_id)["items"]
    assert items and all(i["new_card"] and i["current"] is None for i in items)
    assert store.find("Technology", "全新技術") is None
    only = next(i for i in items if i["field"] == "standard_body")
    _refused(_confirm(tmp_path, rerun_id, [only["id"]]), 400, "items_incomplete")
    assert store.find("Technology", "全新技術") is None
    _ok(_confirm(tmp_path, rerun_id, [i["id"] for i in items]))
    assert store.find("Technology", "全新技術") is not None


def test_a_rerun_run_stays_out_of_the_run_lists_and_cannot_be_committed(tmp_path: Path) -> None:
    _, source = _seed(tmp_path)
    jobs = Jobs()
    rerun_id = _start(tmp_path, source, Scripted(_answer(standard_body="IEEE 802.1")), jobs)
    assert _ok(_call(tmp_path, "GET", "/api/bi/runs", dataset="demo"))["runs"] == []
    run_id = _view(tmp_path, rerun_id)["runs"][0]["run_id"]
    row = Staging(tmp_path, "demo").run_row(run_id)
    assert row is not None and row["kind"] == "trial"
    status, answer = _call(tmp_path, "POST", f"/api/bi/runs/{run_id}/commit", {"dataset": "demo"})
    assert (status, answer["code"]) == (409, "run_trial")


def test_nothing_starts_without_a_model_and_no_class_is_refused(tmp_path: Path) -> None:
    _, source = _seed(tmp_path)  # INTERNAL by default
    jobs = Jobs()
    body = {"dataset": "demo", "sources": [source], "start": True}
    status, answer = _call(tmp_path, "POST", "/api/bi/reruns/preview", body, _runtime(None, jobs))
    assert status != 200 and answer["code"] == "model_unavailable"
    assert jobs.pending == []
    # With a model it starts: a source's data class is never a refusal (owner 2026-11-17).
    model = Scripted(_answer(standard_body="IEEE 802.1"))
    started = _ok(_call(tmp_path, "POST", "/api/bi/reruns/preview", body, _runtime(model, jobs)))
    assert started["rerun"]["id"] and jobs.pending
    jobs.run_all()
    assert model.requests
    assert _call(tmp_path, "GET", "/api/bi/reruns/../x", dataset="demo")[0] == 404


@pytest.mark.parametrize(
    ("folder", "application", "inside"),
    [
        ("applications/aidc/sources", "aidc", True),
        ("applications/aidc/sources/reports", "aidc", True),
        ("sources/applications/aidc", "aidc", True),
        ("applications/aidc2/sources", "aidc", False),
        ("library/products/sources", "library/products", True),
        ("applications/products/sources", "library/products", False),
        (None, "aidc", False),
    ],
)
def test_a_source_belongs_to_an_application_by_its_folder(
    folder: str | None, application: str, inside: bool
) -> None:
    assert rerun._in_application(folder, application) is inside


def test_in_a_vault_the_confirm_is_one_commit_naming_the_skill(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="ISO", maturity="growth")],
        filename="t.csv",
        entity_type="Technology",
        actor="x via web",
    )
    source = _ok(
        _call(a, "POST", "/api/bi/sources", {"dataset": dataset, "name": "spec.md", "text": TEXT})
    )["source"]["id"]
    _commit(a, vault_id, "加入來源")
    _push(a, vault_id)
    jobs = Jobs()
    model = Scripted(_answer(standard_body="IEEE 802.1", maturity="growth"))
    rerun_id = _start(a, source, model, jobs, dataset)
    assert "skill classify" in model.requests[0].messages[0].text
    (item,) = _view(a, rerun_id, dataset)["items"]
    assert {s["name"] for s in item["skills"]} >= {"classify"}
    before = len(vault.Vault(a, vault_id).repo.local_commits())
    _ok(_confirm(a, rerun_id, [item["id"]], dataset))
    local = vault.Vault(a, vault_id).repo.local_commits()
    assert len(local) == before + 1
    assert local[-1]["purpose"].startswith("重跑差異確認：1 個值")
    assert vault.status(a, vault_id)["uncommitted"] == 0
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    card = BiStore(b, dataset).find("Technology", "TSN")
    assert card is not None
    fields = BiStore(b, dataset).fields(card["id"])
    assert (fields["standard_body"]["value"], fields["maturity"]["value"]) == (
        "IEEE 802.1",
        "growth",
    )
