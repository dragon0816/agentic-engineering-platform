"""「全部套用」 in the review step.

Owner 2026-11-18: 「BI卡片審核的部份，想要加入一鍵apply所有卡片的功能」.

`POST /api/bi/runs/<run>/accept` accepts the given candidates through the same check one
接受 makes, reports each one, goes on past a refusal and never accepts one twice. It writes
no card: the run's commit does. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_ingest_runs import _call, _commit, _detail, _ok, _review, _run, _source

from aep_bi.cards import runs
from aep_bi.cards.staging import Staging

THREE = (
    "技術,領域,成熟度,新增測試需求\n"
    "EtherCAT,robotics,mature,週期抖動\n"
    "TSN,robotics,growth,時間同步\n"
    "PROFINET,robotics,mature,即時通訊\n"
)


def _accept(tmp_path: Path, run_id: str, ids: Any) -> Any:
    return _call(tmp_path, "POST", f"/api/bi/runs/{run_id}/accept", {"dataset": "demo", "ids": ids})


def _ids(tmp_path: Path, run_id: str) -> dict[str, str]:
    return {c["canonical_key"]: c["id"] for c in _detail(tmp_path, run_id)["candidates"]}


def _reviews(tmp_path: Path, run_id: str) -> dict[str, str]:
    return {c["canonical_key"]: c["review"] for c in _detail(tmp_path, run_id)["candidates"]}


def _break(tmp_path: Path, run_id: str, candidate_id: str) -> None:
    """Give one candidate an error, as a value the model gave that does not fit."""
    staging = Staging(tmp_path, "demo")
    candidate = next(c for c in staging.candidates(run_id) if c["id"] == candidate_id)
    candidate.setdefault("value_errors", []).append(
        {"code": "value_invalid", "message": "成熟度不是允許的值", "field": "maturity"}
    )
    staging.put_candidates(run_id, [candidate])


def test_all_given_candidates_are_accepted_and_nothing_is_written(tmp_path: Path) -> None:
    run = _run(tmp_path, _source(tmp_path, THREE))
    ids = _ids(tmp_path, run["id"])
    done = _ok(_accept(tmp_path, run["id"], list(ids.values())))
    assert (done["applied"], done["skipped"], done["failed"]) == (3, 0, 0)
    assert [r["status"] for r in done["results"]] == ["applied"] * 3
    assert {r["name"] for r in done["results"]} == set(ids)
    assert all(c["review"] == "accepted" for c in done["candidates"])
    assert done["run"]["summary"]["accepted"] == 3
    assert not (tmp_path / "bi" / "demo" / "bi.sqlite").exists(), "accepting writes no card"
    # Undone one by one, as a single 接受 is: 待決定.
    back = _ok(_review(tmp_path, run["id"], ids["TSN"], review="pending"))["candidate"]
    assert back["review"] == "pending"
    assert _ok(_commit(tmp_path, run["id"]))["applied"]["created"] == 2


def test_a_refusal_is_reported_and_the_rest_go_on(tmp_path: Path) -> None:
    run = _run(tmp_path, _source(tmp_path, THREE))
    ids = _ids(tmp_path, run["id"])
    _break(tmp_path, run["id"], ids["TSN"])
    sent = [ids["EtherCAT"], "no-such-candidate", ids["TSN"], ids["PROFINET"]]
    done = _ok(_accept(tmp_path, run["id"], sent))
    assert [(r["id"], r["status"], r.get("code")) for r in done["results"]] == [
        (ids["EtherCAT"], "applied", None),
        ("no-such-candidate", "failed", "candidate_unknown"),
        (ids["TSN"], "failed", "candidate_invalid"),
        (ids["PROFINET"], "applied", None),
    ]
    tsn = done["results"][2]
    assert tsn["name"] == "TSN" and tsn["reason"] == "這張候選卡還有錯誤，修正後才能接受"
    assert (done["applied"], done["skipped"], done["failed"]) == (2, 0, 2)
    assert _reviews(tmp_path, run["id"]) == {
        "EtherCAT": "accepted",
        "TSN": "pending",
        "PROFINET": "accepted",
    }


def test_the_same_batch_sent_again_accepts_nothing_twice(tmp_path: Path) -> None:
    run = _run(tmp_path, _source(tmp_path, THREE))
    ids = _ids(tmp_path, run["id"])
    _ok(_review(tmp_path, run["id"], ids["PROFINET"], review="rejected"))
    batch = [ids["EtherCAT"], ids["TSN"], ids["EtherCAT"]]  # one id twice: decided once
    first = _ok(_accept(tmp_path, run["id"], batch))
    assert [r["status"] for r in first["results"]] == ["applied", "applied"]
    history = Staging(tmp_path, "demo").candidates(run["id"])
    again = _ok(_accept(tmp_path, run["id"], batch + [ids["PROFINET"]]))
    assert [(r["status"], r["code"]) for r in again["results"]] == [
        ("skipped", "already_accepted"),
        ("skipped", "already_accepted"),
        ("skipped", "rejected"),
    ]
    assert again["applied"] == 0 and again["skipped"] == 3
    assert Staging(tmp_path, "demo").candidates(run["id"]) == history, "nothing was rewritten"
    assert _reviews(tmp_path, run["id"])["PROFINET"] == "rejected"


def test_only_the_candidates_sent_are_accepted(tmp_path: Path) -> None:
    """The page sends what its filters show; the server accepts exactly those."""
    run = _run(tmp_path, _source(tmp_path, THREE))
    ids = _ids(tmp_path, run["id"])
    _ok(_accept(tmp_path, run["id"], [ids["TSN"]]))
    assert _reviews(tmp_path, run["id"]) == {
        "EtherCAT": "pending",
        "TSN": "accepted",
        "PROFINET": "pending",
    }


def test_refused_requests(tmp_path: Path) -> None:
    run = _run(tmp_path, _source(tmp_path, THREE))
    for ids in (None, [], "r1", [1], [""]):
        status, payload = _accept(tmp_path, run["id"], ids)
        assert (status, payload["code"]) == (400, "ids_invalid")
    status, payload = _accept(tmp_path, run["id"], [f"x{i}" for i in range(runs.ACCEPT_BATCH + 1)])
    assert (status, payload["code"]) == (400, "ids_too_many")
    status, payload = _accept(tmp_path, "no-such-run", ["r1"])
    assert payload["code"] == "run_unknown"
    _ok(_call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/cancel", {"dataset": "demo"}))
    status, payload = _accept(tmp_path, run["id"], ["r1"])
    assert (status, payload["code"]) == (409, "run_closed")
