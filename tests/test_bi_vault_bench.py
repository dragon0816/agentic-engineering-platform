"""Benchmarks of a BI vault (BI T1, `docs/phases/BI_TEST_AND_TOOLS.md` §3).

Question sets and extraction cases are units of the vault: staged, committed,
pushed and read by the other PC like cards. A run asks every question on the
working and on the published version and scores every case; the push check
blocks a push whose newest run for exactly those units found a regression.
A question is asked through the Agent harness with `bi__query` reading the
chosen version for that turn only. The model is scripted; all data is fictional.
"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import (
    _call,
    _commit,
    _import,
    _ok,
    _push,
    _refused,
    _row,
    _sync,
    _two_pcs,
)
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from aep_bi.cards import vault
from aep_bi.cards.store import BiStore
from aep_bi.host import bi_bench, bi_cards_tools
from host_runtime import skill_packs
from host_runtime.assets import shipped
from host_runtime.host import build_runtime

NOTE = "虛構拜訪紀錄：客戶正在評估 TSN，標準由 IEEE 802.1 制定。"
EXPECTED = {
    "format": "aep.bi.benchmark.expected/v1",
    "types": ["Technology"],
    "candidates": [
        {
            "entity_type": "Technology",
            "name": "TSN",
            "fields": {"standard_body": {"basis": "fact", "evidence": "IEEE 802.1"}},
        }
    ],
}
QUESTION = {"question": "TSN 的標準組織是誰？", "must": ["IEEE"], "must_not": ["ETSI"]}


@pytest.fixture(autouse=True)
def _no_gate() -> Any:
    vault.set_benchmark(None)
    yield
    vault.set_benchmark(None)


def _checks(ws: Path, vault_id: str) -> dict[str, Any]:
    return _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/checks"))


def _save(ws: Path, vault_id: str, body: dict[str, Any]) -> Any:
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/checks", body)


def test_questions_and_cases_are_vault_units_committed_and_pushed(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    saved = _ok(_save(a, vault_id, {**QUESTION, "set": "market"}))
    assert saved["unit"].startswith("check:question:market/q-")
    _ok(_save(a, vault_id, {"kind": "case", "slug": "tsn-visit", "note": NOTE,
                            "expected": EXPECTED}))  # fmt: skip
    # An expected fact whose evidence is not in the note is refused.
    wrong: dict[str, Any] = json.loads(json.dumps(EXPECTED))
    wrong["candidates"][0]["fields"]["standard_body"]["evidence"] = "ETSI"
    _refused(_save(a, vault_id, {"kind": "case", "slug": "bad", "note": NOTE,
                                 "expected": wrong}), 400, "case_invalid")  # fmt: skip
    _refused(_save(a, vault_id, {"question": " "}), 400, "question_invalid")
    listed = _checks(a, vault_id)
    assert [q["question"] for q in listed["questions"]] == [QUESTION["question"]]
    assert [c["slug"] for c in listed["cases"]] == ["tsn-visit"]
    assert listed["latest"] is None
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    labels = {c["label"] for c in pending["uncommitted"]}
    assert labels == {f"測試題「{QUESTION['question']}」", "擷取測試「tsn-visit」"}
    _commit(a, vault_id, "加上測試")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _checks(b, vault_id)["questions"][0]["must"] == ["IEEE"]
    # Checks never become cards, and deleting one is a change like any other.
    assert _ok(_call(b, "GET", "/api/bi/cards", dataset=dataset))["cards"] == []
    unit = _checks(b, vault_id)["questions"][0]["unit"]
    assert _ok(_save(b, vault_id, {"delete": unit}))["questions"] == []
    _refused(_save(b, vault_id, {"delete": "card:x"}), 404, "check_unknown")


def test_a_run_compares_working_and_published_and_blocks_a_regression(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    vault.set_benchmark(partial(bi_bench.gate, a))
    _ok(_save(a, vault_id, QUESTION))
    _ok(_save(a, vault_id, {"kind": "case", "slug": "tsn-visit", "note": NOTE,
                            "expected": EXPECTED}))  # fmt: skip
    _commit(a, vault_id, "加上測試")
    pushed = _push(a, vault_id)
    assert pushed["status"] == "pushed"
    assert any("沒有跑過測試" in n for n in pushed["notes"])
    # A change that makes the answer wrong on the working copy.
    _import(a, dataset, _row("TSN", standard_body="ETSI"))

    def ask(question: str, side: bi_bench.Side) -> dict[str, Any]:
        return {"ok": True, "answer": "ETSI" if side == "working" else "IEEE 802.1"}

    def extract(case: Any) -> list[dict[str, Any]]:
        field = {"field": "standard_body", "value": "IEEE 802.1", "basis": "fact",
                 "evidence": [{"excerpt": "IEEE 802.1"}]}  # fmt: skip
        return [{"entity_type": "Technology", "name": "TSN", "fields": [field]}]

    report = bi_bench.run(a, vault_id, ask=ask, extract=extract, actor="alice")
    assert report["status"] == "finished", report
    assert (report["working_score"], report["published_score"], report["total"]) == (0, 1, 1)
    assert len(report["regressions"]) == 1
    assert report["cases"][0]["result"]["counts"]["found"] == 1
    assert report["extract"]["score"] > 0
    assert _checks(a, vault_id)["latest"]["run_id"] == report["run_id"]
    got = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/bench", run=report["run_id"]))
    assert got["report"]["regressions"] == report["regressions"]
    blocked = _push(a, vault_id)
    assert blocked["status"] == "blocked"
    assert "發佈版本答得對" in blocked["blocking"][0]
    # Fixed: a new run for these units without a regression lets the push through.
    _import(a, dataset, _row("TSN", standard_body="IEEE 802.1"))
    fixed = bi_bench.run(
        a, vault_id, ask=lambda q, s: {"ok": True, "answer": "IEEE"}, extract=extract, actor="alice"
    )
    assert fixed["regressions"] == []
    done = _push(a, vault_id)
    assert done["status"] == "pushed" and any("1/1 題通過" in n for n in done["notes"])


def test_a_run_needs_checks_and_one_failing_case_is_reported(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _refused(_call(a, "POST", f"/api/bi/vaults/{vault_id}/bench", {}), 400, "bench_empty")
    _ok(_save(a, vault_id, {"kind": "case", "slug": "tsn-visit", "note": NOTE,
                            "expected": EXPECTED}))  # fmt: skip
    _refused(_call(a, "POST", f"/api/bi/vaults/{vault_id}/bench", {}), 400, "bench_unavailable")

    def broken(case: Any) -> list[dict[str, Any]]:
        raise RuntimeError("模型沒有回應")

    report = bi_bench.run(a, vault_id, ask=lambda q, s: {}, extract=broken, actor="alice")
    assert report["status"] == "finished" and report["cases"][0]["error"] == "模型沒有回應"
    assert report["extract"] is None


def test_a_report_being_read_does_not_stop_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Windows refuses to replace a file the page's polling has open. A run that died
    # on that stayed 「測試中」 for ever and refused every later run as `bench_running`.
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ok(_save(a, vault_id, QUESTION))
    real = Path.replace
    refused: list[Path] = []

    def busy(self: Path, target: Any) -> Path:
        if self.suffix == ".tmp" and len(refused) < 2:
            refused.append(self)
            raise PermissionError(5, "being read", str(target))
        return real(self, target)

    monkeypatch.setattr(Path, "replace", busy)
    report = bi_bench.run(
        a,
        vault_id,
        ask=lambda _q, _s: {"ok": True, "answer": "IEEE"},
        extract=lambda _c: [],
        actor="alice",
    )
    assert len(refused) == 2
    assert report["status"] == "finished"
    latest = bi_bench.latest(a, vault_id)
    assert latest is not None and latest["status"] == "finished"


def test_a_question_is_asked_through_the_agent_on_the_chosen_version(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    workspace = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(_call(workspace, "POST", "/api/bi/vaults", {
        "path": str(shared), "title": "Market", "purpose": "虛構", "schema": "bi.schema/v1.1",
        "author": "alice"}))  # fmt: skip
    vault_id, dataset = made["vault"]["id"], made["vault"]["dataset"]
    _import(workspace, dataset, _row("TSN", standard_body="IEEE 802.1"))

    _push(workspace, vault_id)
    _import(workspace, dataset, _row("TSN", standard_body="ETSI"))  # only on the working copy
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        model = Conversation()
        gateway.router.model = model
        query = (bi_cards_tools.TOOL_NAME, {"dataset": dataset, "text": "TSN"})
        model.then({"tools": [query]}, {"text": "答案在卡片裡"})
        ask = bi_bench.agent_ask(gateway, workspace, vault_id, "engineer", "engineering")
        reply = ask("TSN 的標準組織？", "working")
        assert reply["ok"]
        # The trace the error classes read: what the tool returned, card ids included.
        card = BiStore(workspace, dataset).find("Technology", "TSN")
        assert card is not None and card["id"] in reply["shown"]
        assert any("ETSI" in text for text in reply["shown"])
        working = model.tool_results()
        model.then({"tools": [query]}, {"text": "答案在卡片裡"})
        ask("TSN 的標準組織？", "published")
        published = model.tool_results()
        offered = [t.name for t in model.requests[0].tools]
        assert offered == [bi_cards_tools.TOOL_NAME]
        assert dataset in model.requests[0].messages[0].text  # the role names the dataset
        # The turn-scoped tool is gone afterwards: the live chat reads the published one.
        assert bi_cards_tools.bi_cards_tools(gateway)[0].handler is not None
    assert "ETSI" in working[0] and "工作版本" in working[0]
    assert "IEEE 802.1" in published[0] and "ETSI" not in published[0]


def test_applied_questions_are_deleted_together_and_past_results_stay(tmp_path: Path) -> None:
    """Owner 2026-11-19: 「無法刪除apply的benchmark」. Committed questions are deleted per row or
    several at once by one change, uncommitted until commit and push; a past run keeps them."""
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    units = [
        _ok(_save(a, vault_id, {**QUESTION, "question": f"TSN 第 {n} 題？"}))["unit"]
        for n in range(3)
    ]
    _commit(a, vault_id, "加上測試")
    report = bi_bench.run(
        a, vault_id, ask=lambda q, s: {"ok": True, "answer": "IEEE"}, extract=lambda c: [],
        actor="alice",
    )  # fmt: skip
    assert report["total"] == 3
    # One unknown among them: nothing is deleted.
    _refused(_save(a, vault_id, {"delete": [units[0], "check:question:main/q-nope"]}), 404,
             "check_unknown")  # fmt: skip
    assert len(_checks(a, vault_id)["questions"]) == 3
    deleted = _ok(_save(a, vault_id, {"delete": units[:2]}))
    assert deleted["deleted"] == units[:2]
    assert [q["unit"] for q in deleted["questions"]] == [units[2]]
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    assert {c["unit"] for c in pending["uncommitted"]} >= set(units[:2])
    # The past run is history: it still holds each question's text and verdicts.
    latest = _checks(a, vault_id)["latest"]
    assert latest["run_id"] == report["run_id"]
    assert {r["unit"] for r in latest["results"]} == set(units)
    assert all(r["question"].startswith("TSN 第") for r in latest["results"])
    _ok(_save(a, vault_id, {"delete": units[2]}))
    assert _checks(a, vault_id)["questions"] == []
    _commit(a, vault_id, "刪掉測試")
    assert vault.Vault(a, vault_id).repo.working_units(pending=False).get(units[0]) is None
    del drive, dataset, b


def test_a_run_says_how_far_it_is_for_the_bar_beside_the_button(tmp_path: Path) -> None:
    """Owner 2026-11-20: 「跑測試的時候，希望有一個進度條」. While a run asks, the newest report
    says n of N, the question being asked and when it started; at the end, all done."""
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ok(_save(a, vault_id, QUESTION))
    _ok(_save(a, vault_id, {**QUESTION, "question": "TSN 是什麼？"}))
    seen: list[dict[str, Any]] = []

    def ask(question: str, side: bi_bench.Side) -> dict[str, Any]:
        if side == "working":
            seen.append(_checks(a, vault_id)["newest"])
        return {"ok": True, "answer": "IEEE"}

    report = bi_bench.run(a, vault_id, ask=ask, extract=lambda case: [], actor="alice")
    assert report["status"] == "finished"
    first, second = seen
    assert first["status"] == "running"
    assert first["progress"]["done"] == 0 and first["progress"]["total"] == 2
    assert first["progress"]["current"] in ("TSN 的標準組織是誰？", "TSN 是什麼？")
    assert first["progress"]["started_at"] and first["progress"]["ended_at"] is None
    assert second["progress"]["done"] == 1
    done = _checks(a, vault_id)["newest"]
    assert done["status"] == "finished"
    assert done["progress"]["done"] == 2 and done["progress"]["current"] is None
    assert done["progress"]["ended_at"]
