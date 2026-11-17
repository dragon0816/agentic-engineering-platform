"""A person's review of evidence (`docs/phases/BI_CARD_MODEL.md` §5.4, proposal §6.1).

Two PCs as in `test_bi_vault.py`. A review goes source → preview → confirm → commit
and never writes a field. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_evidence_references import LOCATOR, _commit_run
from test_bi_vault import _call, _import, _ok, _push, _row, _sync, _two_pcs
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards import card_model, vault
from aep_bi.cards.store import BiStore, PlannedRow

REFERENCE = card_model.reference_id("src-1", LOCATOR)
JUDGED = {
    "verdict": "rejected",
    "stance": "context_only",
    "directness": "insufficient",
    "scope": "只限虛構市場",
    "date": "2026-03-01",
    "same_source": "same_source",
    "reason": "這段只是背景",
}


def _card(ws: Path, dataset: str, key: str = "FAKE-A") -> Any:
    card = BiStore(ws, dataset).find("Technology", key)
    assert card is not None
    return card


def _on_card(ws: Path, dataset: str, **given: Any) -> dict[str, Any]:
    card = _card(ws, dataset)
    return {
        "dataset": dataset,
        "target": "card",
        "card": card["id"],
        "field": "maturity",
        "reference_id": REFERENCE,
        "base_version": int(card["version"]),
        **JUDGED,
        **given,
    }


def _review(ws: Path, body: dict[str, Any]) -> dict[str, Any]:
    note = _ok(_call(ws, "POST", "/api/bi/evidence-reviews/preview", body))
    return _ok(
        _call(
            ws,
            "POST",
            "/api/bi/evidence-reviews/apply",
            {
                "dataset": body["dataset"],
                "text": note["text"],
                "base_version": note["base_version"],
            },
        )
    )


def _row_of(ws: Path, dataset: str) -> dict[str, Any]:
    card = _card(ws, dataset)
    return next(e for e in BiStore(ws, dataset).evidence(card["id"]) if e["field"] == "maturity")


def _linked(ws: Path, dataset: str) -> tuple[str, str, str]:
    """A relation derived from a link field: its id and its two ends."""
    store = BiStore(ws, dataset)
    store.apply(
        [
            _row("FAKE-B"),
            PlannedRow(1, "Application", "FAKE-APP", "FAKE-APP",
                       {"name": "FAKE-APP", "technologies": ["FAKE-B"]}, False),
        ],
        filename="t.csv", entity_type="Technology", actor="alice",
    )  # fmt: skip
    app = store.find("Application", "FAKE-APP")
    assert app is not None
    relations = store.relations(app["id"])
    assert relations, "the link field should derive a relation"
    return relations[0]["relation_id"], app["id"], relations[0]["other_id"]


def test_a_preview_writes_nothing_and_a_confirm_records_who_when_and_before_after(
    tmp_path: Path,
) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset, reason="the quote hedges")
    target = vault.Vault(a, vault_id)
    held = target.repo.working_units()
    note = _ok(_call(a, "POST", "/api/bi/evidence-reviews/preview", _on_card(a, dataset)))
    assert target.repo.working_units() == held
    assert note["before"]["verdict"] == "pending"
    assert note["before"]["stance"] == "supports"
    assert note["after"]["verdict"] == "rejected"
    assert note["unchanged"] is False
    assert "maturity" in note["statement"]

    _review(a, _on_card(a, dataset, author="reviewer one"))
    row = _row_of(a, dataset)
    assert row["stance"] == "context_only"
    assert row["reference_at"] == "2026-03-01"
    assert row["reference_time_basis"] is None
    assert row["reference_id"] == REFERENCE  # the place in the source is what it was
    assessment = row["assessment"]
    assert assessment["system"] == {"reason": "the quote hedges"}
    assert assessment["current"] == {
        "directness": "insufficient",
        "scope": "只限虛構市場",
        "date": "2026-03-01",
        "same_source": "same_source",
        "verdict": "rejected",
    }
    past = assessment["history"][0]
    assert past["by"] == "tester via web"  # who was signed in, whatever the note says
    assert past["author"] == "reviewer one"
    assert past["at"]
    assert past["reason"] == "這段只是背景"
    assert past["before"]["stance"] == "supports"  # what the model said stays
    assert past["after"]["stance"] == "context_only"
    assert target.repo.status()["uncommitted"] == 0  # one commit, with the note as a source


def test_a_review_never_writes_a_field(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    card = _card(a, dataset)
    fields = BiStore(a, dataset).fields(card["id"])
    held = vault.Vault(a, vault_id).repo.working_units()[f"field:{card['id']}:maturity"]
    _review(a, _on_card(a, dataset))
    assert BiStore(a, dataset).fields(card["id"]) == fields
    assert vault.Vault(a, vault_id).repo.working_units()[f"field:{card['id']}:maturity"] == held
    assert int(_card(a, dataset)["version"]) == int(card["version"])


def test_the_same_review_again_changes_nothing_and_a_second_keeps_the_first(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    _review(a, _on_card(a, dataset))
    held = vault.Vault(a, vault_id).repo.working_units()
    assert _review(a, _on_card(a, dataset))["unchanged"] is True
    assert vault.Vault(a, vault_id).repo.working_units() == held
    _review(a, _on_card(a, dataset, verdict="accepted", reason="改判"))
    history = _row_of(a, dataset)["assessment"]["history"]
    assert [h["after"]["verdict"] for h in history] == ["rejected", "accepted"]
    assert history[1]["before"]["verdict"] == "rejected"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"reason": "  "}, "reason_required"),
        ({"verdict": ""}, "review_invalid"),
        ({"verdict": "maybe"}, "review_invalid"),
        ({"directness": "0.7"}, "review_invalid"),  # words only: no numeric weight
        ({"same_source": "90%"}, "review_invalid"),
        ({"stance": "kind of"}, "review_invalid"),
        ({"date": "soon"}, "review_invalid"),
        ({"reference_id": "nosuchref"}, "reference_unknown"),
        ({"base_version": None}, "base_version_missing"),
    ],
)
def test_a_review_that_cannot_be_taken_is_refused(
    tmp_path: Path, change: dict[str, Any], code: str
) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    status, payload = _call(
        a, "POST", "/api/bi/evidence-reviews/preview", _on_card(a, dataset, **change)
    )
    assert (status, payload["code"]) == (400, code)


def test_a_review_of_a_card_that_moved_is_stale(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    body = _on_card(a, dataset)
    card = _card(a, dataset)
    BiStore(a, dataset).set_field(
        card["id"], "maturity", "mature", base_version=int(card["version"]), actor="x", reason="r"
    )
    status, payload = _call(a, "POST", "/api/bi/evidence-reviews/preview", body)
    assert (status, payload["code"]) == (409, "stale_edit")


def test_a_plain_dataset_has_no_review(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    status, payload = _call(
        ws, "POST", "/api/bi/evidence-reviews/preview", {"dataset": "lab", "target": "card"}
    )
    assert (status, payload["code"]) == (400, "review_vault_only")


def test_a_review_reaches_the_other_pc(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    _review(a, _on_card(a, dataset))
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _row_of(b, dataset)["assessment"] == _row_of(a, dataset)["assessment"]
    assert _row_of(b, dataset)["stance"] == "context_only"


def test_a_row_from_before_the_card_model_keeps_its_review(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    target = vault.Vault(a, vault_id)
    units = target.repo.working_units()
    key = next(k for k in units if k.startswith("evidence:"))
    old = [
        {k: v for k, v in row.items()
         if k not in ("reference_id", "stance", "reference_at", "reference_time_basis")}
        for row in units[key]
    ]  # fmt: skip
    target.repo.stage(key, old)
    target.repo.commit("an old row")
    target.rebuild()
    _review(a, _on_card(a, dataset, date=""))
    row = _row_of(a, dataset)
    assert row["assessment"]["current"]["verdict"] == "rejected"
    assert row["reference_time_basis"] == "submission_fallback"
    assert target.repo.working_units()[key][0]["assessment"] == row["assessment"]


def test_a_relation_with_no_reference_takes_a_verdict_and_can_come_back(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    relation, app, _ = _linked(a, dataset)
    body = {
        "dataset": dataset,
        "target": "relation",
        "card": app,
        "relation": relation,
        "verdict": "rejected",
        "reason": "兩者無關",
    }
    _review(a, body)
    store = BiStore(a, dataset)
    row = store.relation_row(relation)
    assert row is not None
    assert row["status"] == "rejected"
    assert row["note"] == "兩者無關"
    assert store.relations(app) == []
    gone = store.relations(app, rejected=True)
    assert [r["relation_id"] for r in gone] == [relation]
    assert vault.Vault(a, vault_id).repo.status()["uncommitted"] == 0
    # Reviewed again it comes back, and both reviews gather on one link.
    _review(a, {**body, "verdict": "pending", "reason": "再看看"})
    row = store.relation_row(relation)
    assert row is not None
    assert row["status"] == "pending"
    history = store.relation_references(relation)[0]["assessment"]["history"]
    assert [h["after"]["verdict"] for h in history] == ["rejected", "pending"]


def test_a_relation_is_reviewed_on_its_link_fields_evidence(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    relation, app, _ = _linked(a, dataset)
    proof = {"source_id": "src-2", "source_name": "fictional.md", "locator": {"line": 9},
             "excerpt": "FAKE-APP 用 FAKE-B", "basis": "fact"}  # fmt: skip
    row = PlannedRow(1, "Application", "FAKE-APP", "FAKE-APP",
                     {"name": "FAKE-APP", "technologies": ["FAKE-B"]}, False, ref="run",
                     evidence={"technologies": [proof]})  # fmt: skip
    store = BiStore(a, dataset)
    card = store.card(app)
    assert card is not None
    store.commit_run("run-2", [(row, "c1", int(card["version"]))], filename="f.md", actor="alice")
    item = store.relation_references(relation)[0]
    assert item["linked"] is False
    assert (item["excerpt"], item["source_name"]) == ("FAKE-APP 用 FAKE-B", "fictional.md")
    assert item["locator"] == {"line": 9}
    reference = card_model.reference_id("src-2", {"line": 9})
    assert item["reference_id"] == reference
    _review(a, {"dataset": dataset, "target": "relation", "card": app, "relation": relation,
                "reference_id": reference, "verdict": "accepted", "directness": "direct",
                "stance": "supports", "reason": "原文直接寫了"})  # fmt: skip
    row_now = store.relation_row(relation)
    assert row_now is not None
    assert row_now["status"] == "confirmed"
    assert row_now["origin"] == card_model.SCHEMA_FIELD
    item = store.relation_references(relation)[0]
    assert item["linked"] is True
    assert item["assessment"]["current"]["directness"] == "direct"
    assert item["assessment"]["history"][0]["before"]["verdict"] == "pending"


def test_the_detail_api_shows_states_stance_and_references(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset, stance="refutes")
    _import(a, dataset, PlannedRow(1, "Technology", "FAKE-A", "FAKE-A", {"name": "FAKE-A"}, False,
                                   states={"standard_body": {"state": "not_applicable",
                                                             "raw": "n/a"}}))  # fmt: skip
    card = _card(a, dataset)
    detail = _ok(_call(a, "GET", f"/api/bi/cards/{card['id']}", dataset=dataset))
    assert detail["field_states"]["standard_body"]["state"] == "not_applicable"
    assert detail["evidence"][0]["stance"] == "refutes"
    assert detail["evidence"][0]["assessment"] is None
    assert detail["rejected_relations"] == []


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_page_shows_states_and_stance_and_takes_a_review(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path)
    ws = layout.workspace_root
    folder = tmp_path / "shared"
    folder.mkdir()
    made = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(folder),
                "title": "Review Signals",
                "purpose": "虛構測試：證據覆核",
                "schema": "bi.schema/v1.1",
                "author": "alice",
                "default_pack": False,
            },
        )
    )
    dataset = vault.dataset_name(made["vault"]["id"])
    _commit_run(ws, dataset, stance="refutes", reason="原文語氣保留")
    _import(ws, dataset, PlannedRow(1, "Technology", "FAKE-A", "FAKE-A", {"name": "FAKE-A"}, False,
                                    states={"standard_body": {"state": "not_applicable",
                                                              "raw": "n/a"}}))  # fmt: skip
    card = _card(ws, dataset)
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.run(
                "(() => { const s = document.getElementById('bi-dataset');"
                f" s.value = '{dataset}'; s.dispatchEvent(new Event('change')); }})()"
            )
            page.wait(f"bi.dataset === '{dataset}' || biDataset() === '{dataset}'")
            page.run(f"biOpenCard('{card['id']}')")
            page.see("bi-detail-body", "不適用")
            page.see("bi-reviews", "反駁")
            page.see("bi-reviews", "原文語氣保留")
            page.see("bi-reviews", "fictional.md")
            page.click_text("#bi-reviews", "覆核")
            page.wait("document.querySelector('#bi-reviews select[name=verdict]') !== null")
            page.run(
                "(() => { const form = document.querySelector('#bi-reviews form');"
                " form.querySelector('[name=verdict]').value = 'accepted';"
                " form.querySelector('[name=directness]').value = 'indirect';"
                " form.querySelector('[name=reason]').value = '讀過原文';"
                " form.requestSubmit(); })()"
            )
            page.see("bi-reviews", "原本：")
            assert _row_of(ws, dataset)["assessment"].get("history") is None
            page.click("[data-review-confirm]")
            page.notice("已寫入覆核")
            page.see("bi-reviews", "讀過原文")
    row = _row_of(ws, dataset)
    assert row["assessment"]["current"]["verdict"] == "accepted"
    assert row["assessment"]["current"]["directness"] == "indirect"
    assert row["assessment"]["history"][0]["reason"] == "讀過原文"
