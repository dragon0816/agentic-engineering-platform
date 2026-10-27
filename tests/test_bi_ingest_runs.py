"""BI ingest phase 1 (owner 2026-10-27; `docs/phases/BI_INGEST.md` §4, §8).

Sources, runs and candidates in the staging store; review with edits and
match choices; a commit that writes all accepted candidates or nothing, is
refused when a card moved on after the review, and writes a run only once;
evidence on the card; and accepting or rejecting a pending proposal. Every
test uses a temporary workspace and the `/api/bi/*` routes.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest

from capabilities.bi_cards import runs
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route

ACTOR = "tester"
TECH_CSV = (
    "技術,領域,成熟度,新增測試需求\n"
    "EtherCAT,robotics,mature,週期抖動;同步精度\n"
    "TSN,robotics,growth,時間同步(802.1AS)\n"
)


def _call(tmp_path: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(tmp_path, ACTOR, method, path, query, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _source(tmp_path: Path, text: str = TECH_CSV, name: str = "tech.csv") -> str:
    answer = _ok(
        _call(tmp_path, "POST", "/api/bi/sources", {"dataset": "demo", "name": name, "text": text})
    )
    return str(answer["source"]["id"])


def _run(tmp_path: Path, source_id: str, kind: str = "ingest", **extra: Any) -> dict[str, Any]:
    body = {"dataset": "demo", "kind": kind, "source_id": source_id, **extra}
    return dict(_ok(_call(tmp_path, "POST", "/api/bi/runs", body))["run"])


def _detail(tmp_path: Path, run_id: str) -> dict[str, Any]:
    return _ok(_call(tmp_path, "GET", f"/api/bi/runs/{run_id}", dataset="demo"))


def _review(tmp_path: Path, run_id: str, cid: str, **body: Any) -> Any:
    return _call(
        tmp_path, "POST", f"/api/bi/runs/{run_id}/candidates/{cid}", {"dataset": "demo", **body}
    )


def _accept_all(tmp_path: Path, run_id: str) -> None:
    for candidate in _detail(tmp_path, run_id)["candidates"]:
        if candidate["action"] != "skip":
            _ok(_review(tmp_path, run_id, candidate["id"], review="accepted"))


def _commit(tmp_path: Path, run_id: str) -> Any:
    return _call(tmp_path, "POST", f"/api/bi/runs/{run_id}/commit", {"dataset": "demo"})


def _card(tmp_path: Path, name: str) -> dict[str, Any]:
    cards = _ok(_call(tmp_path, "GET", "/api/bi/cards", dataset="demo", q=name))["cards"]
    found = next(c for c in cards if c["canonical_key"] == name)
    return _ok(_call(tmp_path, "GET", f"/api/bi/cards/{found['id']}", dataset="demo"))


def test_a_source_is_a_controlled_copy_kept_once(tmp_path: Path) -> None:
    first = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/sources",
            {"dataset": "demo", "name": "a.csv", "text": TECH_CSV},
        )
    )["source"]
    encoded = base64.b64encode(TECH_CSV.encode("utf-8")).decode("ascii")
    again = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/sources",
            {"dataset": "demo", "name": "b.csv", "content_base64": encoded},
        )
    )["source"]
    assert again["already"] is True and again["id"] == first["id"]
    assert first["classification"] == "INTERNAL" and first["parse"] == "table"
    assert first["sha256"] and first["size"] == len(TECH_CSV.encode("utf-8"))
    stored = list((tmp_path / "bi" / "demo" / "sources").iterdir())
    assert len(stored) == 1 and stored[0].read_text(encoding="utf-8") == TECH_CSV
    listed = _ok(_call(tmp_path, "GET", "/api/bi/sources", dataset="demo"))["sources"]
    assert [s["id"] for s in listed] == [first["id"]]
    for body, code in (
        ({"name": "x.csv", "content_base64": "not base64!"}, "source_base64_invalid"),
        ({"name": "../x.csv", "text": "a"}, "source_name_invalid"),
        ({"name": "x.csv"}, "source_missing"),
        ({"name": "x.csv", "text": "a", "classification": "TOP"}, "classification_invalid"),
    ):
        status, payload = _call(tmp_path, "POST", "/api/bi/sources", {"dataset": "demo", **body})
        assert (status, payload["code"]) == (400, code)


def test_a_run_and_its_review_never_write_the_cards(tmp_path: Path) -> None:
    run = _run(tmp_path, _source(tmp_path), kind="trial")
    assert run["status"] == "review" and run["schema_ref"] == "bi.schema/v1.1@1.1.0"
    assert run["summary"]["create"] == 2 and run["model"] is None
    detail = _detail(tmp_path, run["id"])
    tsn = next(c for c in detail["candidates"] if c["canonical_key"] == "TSN")
    maturity = next(f for f in tsn["fields"] if f["field"] == "maturity")
    assert maturity["basis"] == "fact"
    assert maturity["evidence"][0]["locator"] == {"row": 3, "column": "成熟度"}
    assert maturity["evidence"][0]["excerpt"] == "growth"
    _accept_all(tmp_path, run["id"])
    assert not (tmp_path / "bi" / "demo" / "bi.sqlite").exists()
    status, payload = _commit(tmp_path, run["id"])
    assert (status, payload["code"]) == (409, "run_trial")
    assert not (tmp_path / "bi" / "demo" / "bi.sqlite").exists()


def test_a_commit_writes_accepted_candidates_with_evidence_once(tmp_path: Path) -> None:
    run = _run(tmp_path, _source(tmp_path))
    detail = _detail(tmp_path, run["id"])
    first, second = detail["candidates"]
    _ok(_review(tmp_path, run["id"], first["id"], review="accepted"))
    _ok(_review(tmp_path, run["id"], second["id"], review="rejected"))
    done = _ok(_commit(tmp_path, run["id"]))
    assert done["applied"]["created"] == 1 and done["skipped"] == 1 and done["pending"] == 0
    assert done["index"]["status"] == "not_applicable" and done["already"] is False
    assert done["run"]["status"] == "committed"
    card = _card(tmp_path, "EtherCAT")
    maturity = next(f for f in card["fields"] if f["field"] == "maturity")
    assert maturity["source"]["ref"] == f"run:{run['id']}/{first['id']}"
    evidence = [e for e in card["evidence"] if e["field"] == "maturity"]
    assert evidence[0]["source_name"] == "tech.csv" and evidence[0]["locator"]["row"] == 2
    assert _ok(_call(tmp_path, "GET", "/api/bi/cards", dataset="demo", q="TSN"))["cards"] == []
    again = _ok(_commit(tmp_path, run["id"]))
    assert again["already"] is True and again["import_id"] == done["import_id"]
    assert len(BiStore(tmp_path).card_rows()) == 1
    status, payload = _review(tmp_path, run["id"], second["id"], review="accepted")
    assert (status, payload["code"]) == (409, "run_closed")


def test_a_card_changed_after_review_stops_the_whole_commit(tmp_path: Path) -> None:
    _accept_all(tmp_path, (first := _run(tmp_path, _source(tmp_path)))["id"])
    _ok(_commit(tmp_path, first["id"]))
    changed = TECH_CSV.replace("mature", "declining").replace("growth", "mature")
    run = _run(tmp_path, _source(tmp_path, changed, "tech2.csv"))
    _accept_all(tmp_path, run["id"])
    card = _card(tmp_path, "EtherCAT")
    _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/cards/{card['card']['id']}/field",
            {
                "dataset": "demo",
                "field": "maturity",
                "value": "growth",
                "base_version": card["card"]["version"],
                "reason": "FAE 確認",
            },
        )
    )
    before = BiStore(tmp_path).path.read_bytes()
    status, payload = _commit(tmp_path, run["id"])
    assert (status, payload["code"]) == (409, "cards_changed")
    assert [c["name"] for c in payload["cards"]] == ["EtherCAT"]
    assert BiStore(tmp_path).path.read_bytes() == before
    rechecked = _ok(
        _call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/recheck", {"dataset": "demo"})
    )
    assert rechecked["changed"] == ["r2"]
    ethercat = next(c for c in rechecked["candidates"] if c["id"] == "r2")
    assert ethercat["review"] == "pending"
    assert next(f for f in ethercat["fields"] if f["field"] == "maturity")["change"] == "human_kept"
    _ok(_review(tmp_path, run["id"], "r2", review="accepted"))
    done = _ok(_commit(tmp_path, run["id"]))
    assert done["applied"]["proposals"] == 1
    card = _card(tmp_path, "EtherCAT")
    assert next(f for f in card["fields"] if f["field"] == "maturity")["value"] == "growth"
    assert [p["value"] for p in card["proposals"]] == ["declining"]


def test_a_card_created_elsewhere_after_review_stops_the_commit(tmp_path: Path) -> None:
    source = _source(tmp_path)
    run = _run(tmp_path, source)
    _accept_all(tmp_path, run["id"])
    other = _run(tmp_path, source)
    _accept_all(tmp_path, other["id"])
    _ok(_commit(tmp_path, other["id"]))
    status, payload = _commit(tmp_path, run["id"])
    assert (status, payload["code"]) == (409, "cards_changed")
    assert {c["expected"] for c in payload["cards"]} == {None}


def test_a_loose_name_match_needs_the_person_to_choose(tmp_path: Path) -> None:
    _accept_all(tmp_path, (first := _run(tmp_path, _source(tmp_path)))["id"])
    _ok(_commit(tmp_path, first["id"]))
    run = _run(tmp_path, _source(tmp_path, "技術,成熟度\nEther-CAT,growth\n", "loose.csv"))
    candidate = _detail(tmp_path, run["id"])["candidates"][0]
    assert candidate["match"] == "ambiguous" and candidate["action"] == "create"
    assert [e["code"] for e in candidate["errors"]] == ["match_unresolved"]
    status, payload = _review(tmp_path, run["id"], "r2", review="accepted")
    assert (status, payload["code"]) == (400, "candidate_invalid")
    card_id = candidate["match_ids"][0]
    chosen = _ok(
        _review(
            tmp_path,
            run["id"],
            "r2",
            match={"action": "update", "card_id": card_id},
            review="accepted",
        )
    )["candidate"]
    assert chosen["match"] == "existing" and chosen["canonical_key"] == "EtherCAT"
    _ok(_commit(tmp_path, run["id"]))
    assert len(BiStore(tmp_path).card_rows()) == 2
    card = _card(tmp_path, "EtherCAT")
    assert next(f for f in card["fields"] if f["field"] == "maturity")["value"] == "growth"


def test_a_missing_required_field_is_an_error_until_edited(tmp_path: Path) -> None:
    signal = "日期,標題\n2026-10-01,客戶評估 TSN\n"
    run = _run(tmp_path, _source(tmp_path, signal, "signals.csv"), entity_type="Signal")
    candidate = _detail(tmp_path, run["id"])["candidates"][0]
    missing = sorted(e["field"] for e in candidate["errors"])
    assert missing == ["so_what", "summary"]
    status, payload = _review(tmp_path, run["id"], candidate["id"], fields={"date": "not a date"})
    assert (status, payload["code"]) == (400, "value_invalid")
    edited = _ok(
        _review(
            tmp_path,
            run["id"],
            candidate["id"],
            fields={"summary": "客戶在會議中提到評估 TSN", "so_what": "可能需要時間同步測試"},
            review="accepted",
        )
    )["candidate"]
    assert edited["errors"] == [] and edited["review"] == "accepted"
    summary = next(f for f in edited["fields"] if f["field"] == "summary")
    assert summary["basis"] == "human" and summary["evidence"] == []
    assert [e["field"] for e in edited["edits"]] == ["summary", "so_what"]


def test_a_skipped_choice_clears_errors_and_is_not_written(tmp_path: Path) -> None:
    run = _run(
        tmp_path, _source(tmp_path, "日期,標題\n2026-10-01,x\n", "s.csv"), entity_type="Signal"
    )
    skipped = _ok(_review(tmp_path, run["id"], "r2", match={"action": "skip"}))["candidate"]
    assert skipped["action"] == "skip" and skipped["errors"] == []
    status, payload = _commit(tmp_path, run["id"])
    assert (status, payload["code"]) == (400, "nothing_accepted")


def test_a_lost_commit_reply_is_answered_from_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _run(tmp_path, _source(tmp_path))
    _accept_all(tmp_path, run["id"])
    original = Staging.set_status

    def lost(self: Staging, run_id: str, status: str, **extra: Any) -> None:
        if status == "committed":
            raise OSError("reply lost")
        original(self, run_id, status, **extra)

    monkeypatch.setattr(Staging, "set_status", lost)
    with pytest.raises(OSError):
        runs.commit(tmp_path, "demo", run["id"], actor=ACTOR)
    monkeypatch.setattr(Staging, "set_status", original)
    again = _ok(_commit(tmp_path, run["id"]))
    assert again["already"] is True and again["run"]["status"] == "committed"
    assert len(BiStore(tmp_path).card_rows()) == 2


def test_a_committed_run_is_undone_as_one_import(tmp_path: Path) -> None:
    run = _run(tmp_path, _source(tmp_path))
    _accept_all(tmp_path, run["id"])
    done = _ok(_commit(tmp_path, run["id"]))
    _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/import/undo",
            {"dataset": "demo", "import_id": done["import_id"]},
        )
    )
    assert BiStore(tmp_path).card_rows() == []


def test_a_cancelled_run_cannot_be_committed(tmp_path: Path) -> None:
    run = _run(tmp_path, _source(tmp_path))
    _accept_all(tmp_path, run["id"])
    cancelled = _ok(
        _call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/cancel", {"dataset": "demo"})
    )
    assert cancelled["run"]["status"] == "cancelled"
    status, payload = _commit(tmp_path, run["id"])
    assert (status, payload["code"]) == (409, "run_closed")
    assert not BiStore(tmp_path).exists


def test_tsv_sources_and_refusals(tmp_path: Path) -> None:
    tsv = TECH_CSV.replace(",", "\t")
    run = _run(tmp_path, _source(tmp_path, tsv, "tech.tsv"))
    assert run["summary"]["create"] == 2
    note = _source(tmp_path, "客戶評估 TSN", "note.md")
    status, payload = _call(
        tmp_path, "POST", "/api/bi/runs", {"dataset": "demo", "kind": "ingest", "source_id": note}
    )
    assert (status, payload["code"]) == (400, "source_not_table")
    status, payload = _call(
        tmp_path, "POST", "/api/bi/runs", {"dataset": "demo", "kind": "ingest", "source_id": "nope"}
    )
    assert (status, payload["code"]) == (404, "source_unknown")
    status, payload = _call(
        tmp_path,
        "POST",
        "/api/bi/runs",
        {
            "dataset": "demo",
            "kind": "ingest",
            "source_id": _source(tmp_path, "x,y\n1,2\n", "u.csv"),
        },
    )
    assert (status, payload["code"]) == (400, "entity_type_unknown")
    listed = _ok(_call(tmp_path, "GET", "/api/bi/runs", dataset="demo"))["runs"]
    assert listed[0]["status"] == "failed" and "entity_type_unknown" in listed[0]["error"]
    status, payload = _call(tmp_path, "GET", "/api/bi/runs/nope", dataset="demo")
    assert (status, payload["code"]) == (404, "run_unknown")


def test_a_subscribed_dataset_refuses_sources_and_runs(tmp_path: Path) -> None:
    status, payload = _call(
        tmp_path, "POST", "/api/bi/sources", {"dataset": "ns/name", "name": "a.csv", "text": "a"}
    )
    assert (status, payload["code"]) == (409, "dataset_read_only")


def _card_with_proposal(tmp_path: Path) -> dict[str, Any]:
    """EtherCAT with a person's maturity and a pending import proposal."""
    _accept_all(tmp_path, (first := _run(tmp_path, _source(tmp_path)))["id"])
    _ok(_commit(tmp_path, first["id"]))
    card = _card(tmp_path, "EtherCAT")
    _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/cards/{card['card']['id']}/field",
            {
                "dataset": "demo",
                "field": "maturity",
                "value": "growth",
                "base_version": card["card"]["version"],
                "reason": "人工判斷",
            },
        )
    )
    run = _run(tmp_path, _source(tmp_path, TECH_CSV.replace("mature", "declining"), "t2.csv"))
    _accept_all(tmp_path, run["id"])
    _ok(_commit(tmp_path, run["id"]))
    return _card(tmp_path, "EtherCAT")


def test_a_pending_proposal_is_rejected(tmp_path: Path) -> None:
    card = _card_with_proposal(tmp_path)
    card_id, version = card["card"]["id"], card["card"]["version"]
    (proposal,) = card["proposals"]
    assert proposal["value"] == "declining"
    path = f"/api/bi/cards/{card_id}/proposals/{proposal['id']}"
    rejected = _ok(_call(tmp_path, "POST", path, {"dataset": "demo", "action": "reject"}))
    assert rejected["version"] == version
    after = _card(tmp_path, "EtherCAT")
    assert after["proposals"] == []
    assert next(f for f in after["fields"] if f["field"] == "maturity")["value"] == "growth"
    status, payload = _call(tmp_path, "POST", path, {"dataset": "demo", "action": "accept"})
    assert (status, payload["code"]) == (404, "proposal_unknown")


def test_accepting_a_proposal_is_a_persons_edit(tmp_path: Path) -> None:
    card = _card_with_proposal(tmp_path)
    (proposal,) = card["proposals"]
    path = f"/api/bi/cards/{card['card']['id']}/proposals/{proposal['id']}"
    status, payload = _call(
        tmp_path,
        "POST",
        path,
        {"dataset": "demo", "action": "accept", "base_version": 0, "reason": "x"},
    )
    assert (status, payload["code"]) == (409, "stale_edit")
    status, payload = _call(
        tmp_path,
        "POST",
        path,
        {"dataset": "demo", "action": "accept", "base_version": card["card"]["version"]},
    )
    assert (status, payload["code"]) == (400, "reason_required")
    accepted = _ok(
        _call(
            tmp_path,
            "POST",
            path,
            {
                "dataset": "demo",
                "action": "accept",
                "base_version": card["card"]["version"],
                "reason": "採用匯入值",
            },
        )
    )
    after = _card(tmp_path, "EtherCAT")
    assert accepted["version"] == after["card"]["version"]
    maturity = next(f for f in after["fields"] if f["field"] == "maturity")
    assert maturity["value"] == "declining" and maturity["source"]["kind"] == "human"
    assert after["proposals"] == []
