"""The BI ingest benchmark (phase 7; `docs/phases/BI_INGEST.md` §11 item 10).

Five short fictional notes with expected answers covering fact, inference,
unknown, duplicate and missing items. The scorer gives 100% to a scripted
ideal answer and names each planted flaw of a bad one: a wrong basis, a
fabricated quote (evidence missing), a quote of the wrong sentence, an
unmerged duplicate and forbidden items produced. The same answers run end to
end through the API's AI path and through the owner's benchmark script, with
a scripted model, and score the same: the pipeline and the scorer agree.
Nothing is ever written to the cards. No real provider is called.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from test_bi_ai_runs import Jobs
from test_bi_extract import Scripted

from capabilities.bi_cards import benchmark, extract
from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.schema import registry
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "bi_ingest_benchmark"
CASES = benchmark.load_cases(FIXTURE)
IDEAL: dict[str, Any] = json.loads((FIXTURE / "ideal_answers.json").read_text(encoding="utf-8"))[
    "answers"
]


def _flawed() -> dict[str, Any]:
    """The ideal answers with one planted flaw per check the scorer makes."""
    answers = copy.deepcopy(IDEAL)
    note1 = answers["01_robot_tsn_meeting.md"]["candidates"]
    tsn = next(c for c in note1 if c["name"] == "TSN")
    # A stated fact marked as a guess.
    tsn["fields"]["standard_body"] = {"value": "IEEE 802.1", "basis": "inference", "reason": "?"}
    ethercat = next(c for c in note1 if c["name"] == "EtherCAT")
    # General knowledge claimed as a fact of the source.
    ethercat["fields"]["standard_body"] = {
        "value": "ETG",
        "basis": "fact",
        "quote": "EtherCAT",
    }
    application = next(c for c in note1 if c["entity_type"] == "Application")
    # A quote the note does not contain.
    application["fields"]["technologies"]["quote"] = "客戶已決定導入 TSN"
    # An Opportunity with quotes found in the note, so the code check passes.
    note1.append(
        {
            "entity_type": "Opportunity",
            "name": "北辰機器人 TSN 測試",
            "fields": {
                "account": {
                    "value": "北辰機器人",
                    "basis": "fact",
                    "quote": "北辰機器人的製造處長",
                },
                "applications": {
                    "value": ["機械手臂同步"],
                    "basis": "fact",
                    "quote": "多台機械手臂同步動作",
                },
            },
        }
    )
    note2 = answers["02_wifi7_module_quote.md"]["candidates"]
    wifi = next(c for c in note2 if c["name"] == "Wi-Fi 7")
    # A real quote of the wrong sentence.
    wifi["fields"]["new_test_requirements"]["quote"] = "2027 年第二季量產"
    note3 = answers["03_competitor_redcap.md"]["candidates"]
    note3.append({"entity_type": "Competitor", "name": "衡測", "fields": {}})
    note3.append({"entity_type": "Competitor", "name": "中舟科技", "fields": {}})
    return answers


EXPECTED_FLAWS = {
    ("01_robot_tsn_meeting.md", "fact", "wrong_basis", "Technology", "standard_body"),
    ("01_robot_tsn_meeting.md", "unknown", "wrong_basis", "Technology", "standard_body"),
    ("01_robot_tsn_meeting.md", "fact", "evidence_missing", "Application", "technologies"),
    ("01_robot_tsn_meeting.md", "missing", "forbidden_produced", "Opportunity", None),
    (
        "02_wifi7_module_quote.md",
        "fact",
        "evidence_mismatch",
        "Technology",
        "new_test_requirements",
    ),
    ("03_competitor_redcap.md", "duplicate", "duplicate_not_merged", "Competitor", None),
    ("03_competitor_redcap.md", "missing", "forbidden_produced", "Competitor", None),
}


def _flaws(summary: dict[str, Any]) -> set[tuple[Any, ...]]:
    return {
        (f["note"], f["category"], f["code"], f["entity_type"], f["field"])
        for f in summary["failures"]
    }


def _extracted(answers: dict[str, Any], case: benchmark.Case) -> list[dict[str, Any]]:
    found = extract.extract(
        Scripted(answers[case.note]),
        "test-model",
        registry(),
        text=case.text,
        source_id="src",
        source_name=case.note,
        types=case.expected["types"],
        instructions="",
        known={},
    )
    assert found.failures == []
    return found.candidates


def _scored(answers: dict[str, Any]) -> dict[str, Any]:
    return benchmark.summarize(
        [benchmark.score(_extracted(answers, c), c.expected, text=c.text) for c in CASES]
    )


def _by_note(answers: dict[str, Any]) -> Scripted:
    """A scripted model answering each note from the source name it is shown."""

    def answer(text: str) -> Any:
        return answers[next(note for note in answers if f"Source: {note}," in text)]

    return Scripted(answer)


def test_the_fixture_is_fictional_and_covers_every_category() -> None:
    assert len(CASES) == 5
    covered: set[str] = set()
    for case in CASES:
        assert "虛構範例" in case.text and case.expected["fictional"] is True
        assert benchmark.check_expected(case.expected, case.text) == []
        assert set(case.expected["types"]) <= set(registry().types)
        covered.update(case.expected["covers"])
    assert covered == {"fact", "inference", "unknown", "duplicate", "missing"}
    summary = _scored(IDEAL)
    for category in benchmark.CATEGORIES:
        assert summary["categories"][category]["expected"] > 0, category


def test_the_ideal_answer_scores_full_marks() -> None:
    summary = _scored(IDEAL)
    assert summary["score"] == 100.0 and summary["failures"] == []
    assert summary["counts"] == {
        "found": 17,
        "expected": 17,
        "wrong_basis": 0,
        "evidence_not_matching": 0,
        "forbidden_produced": 0,
        "duplicates_not_merged": 0,
    }
    report = benchmark.render_markdown(summary, title="t")
    assert "總分：100.0%" in report and "全部通過。" in report


def test_a_flawed_answer_names_every_planted_flaw() -> None:
    summary = _scored(_flawed())
    assert _flaws(summary) == EXPECTED_FLAWS
    assert summary["counts"] == {
        "found": 17,
        "expected": 17,
        "wrong_basis": 2,
        "evidence_not_matching": 2,
        "forbidden_produced": 2,
        "duplicates_not_merged": 1,
    }
    assert summary["passed"] == summary["checks"] - len(EXPECTED_FLAWS)
    assert summary["score"] < 100.0
    report = benchmark.render_markdown(summary, title="t")
    assert "evidence_not_found" in report and "衡測儀器、衡測" in report


def test_flagged_duplicates_and_rejected_items_are_not_failures() -> None:
    expected = {
        "format": benchmark.EXPECTED_FORMAT,
        "note": "x.md",
        "candidates": [{"entity_type": "Account", "name": "聯發科", "aliases": ["MediaTek"]}],
        "duplicates": [{"entity_type": "Account", "names": ["聯發科", "MediaTek"]}],
        "forbidden": [{"entity_type": "Opportunity", "names": []}],
    }

    def card(name: str, **more: Any) -> dict[str, Any]:
        return {"entity_type": "Account", "name": name, "fields": [], "match": "new", **more}

    ambiguous = [card("聯發科"), card("MediaTek", match="ambiguous", match_ids=["a1"])]
    rejected = {"entity_type": "Opportunity", "name": "可能的方向", "review": "rejected"}
    result = benchmark.score([*ambiguous, rejected], expected)
    assert result["score"] == 100.0 and result["rejected"] == ["可能的方向"]
    result = benchmark.score([card("聯發科"), card("MediaTek")], expected)
    assert [f["code"] for f in result["failures"]] == ["duplicate_not_merged"]
    result = benchmark.score([], expected)
    assert {f["code"] for f in result["failures"]} == {"candidate_missing", "duplicate_absent"}


# -- end to end with a scripted model ----------------------------------------------


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _call(
    tmp_path: Path, method: str, path: str, body: Any = None, ai: Any = None, **q: str
) -> Any:
    return route(tmp_path, "tester", method, path, q, body, None, ai)


@pytest.mark.parametrize(("answers", "flaws"), [(IDEAL, set()), (_flawed(), EXPECTED_FLAWS)])
def test_the_api_pipeline_and_the_scorer_agree(
    tmp_path: Path, answers: dict[str, Any], flaws: set[tuple[Any, ...]]
) -> None:
    jobs = Jobs()
    ai = AiRuntime(
        model=lambda: (_by_note(answers), "test-model"),
        background=jobs,
        approved=lambda: ("UNCLASSIFIED",),
    )
    started = []
    for case in CASES:
        body = {
            "dataset": "demo",
            "name": case.note,
            "text": case.text,
            "classification": "UNCLASSIFIED",
        }
        source = _ok(_call(tmp_path, "POST", "/api/bi/sources", body))["source"]["id"]
        run = {"dataset": "demo", "kind": "trial", "source_id": source}
        run["types"] = case.expected["types"]
        started.append((case, _ok(_call(tmp_path, "POST", "/api/bi/runs", run, ai))["run"]["id"]))
    jobs.run_all()
    results = []
    for case, run_id in started:
        detail = _ok(_call(tmp_path, "GET", f"/api/bi/runs/{run_id}", dataset="demo"))
        assert detail["run"]["status"] == "review"
        results.append(benchmark.score(detail["candidates"], case.expected, text=case.text))
        commit = _call(tmp_path, "POST", f"/api/bi/runs/{run_id}/commit", {"dataset": "demo"})
        assert (commit[0], commit[1]["code"]) == (409, "run_trial")
    summary = benchmark.summarize(results)
    assert _flaws(summary) == flaws
    direct = _scored(answers)
    for key in ("categories", "counts", "score", "failures"):
        assert summary[key] == direct[key], key
    assert not BiStore(tmp_path, "demo").exists


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "bi_ingest_benchmark", ROOT / "scripts" / "bi_ingest_benchmark.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_script_runs_trials_scores_and_reports_without_writing_cards(
    tmp_path: Path,
) -> None:
    script = _script()
    ai = AiRuntime(
        model=lambda: (_by_note(_flawed()), "test-model"),
        background=lambda title, work: work(),
        approved=lambda: ("UNCLASSIFIED",),
    )
    summary, rows = script.run_benchmark(tmp_path, "demo", ai)
    assert _flaws(summary) == EXPECTED_FLAWS
    assert [r["status"] for r in rows] == ["review"] * 5
    assert {r["kind"] for r in rows} == {"trial"}
    path = script.write_report(
        tmp_path,
        "demo",
        summary,
        rows,
        mode="run",
        model="test-model",
        digests=("(none)", "(none)"),
    )
    assert path.parent == tmp_path / "bi" / "benchmarks"
    report = path.read_text(encoding="utf-8")
    assert f"總分：{summary['score']}%" in report and "bi.sqlite 前後相同" in report
    assert not BiStore(tmp_path, "demo").exists
    # Scoring the same runs again by id (the manual path) gives the same result.
    chosen = {r["note"]: r["run"] for r in rows}
    again, _ = script.score_runs(tmp_path, "demo", chosen)
    assert again == summary
    # Without an approved data class nothing reaches the model; the report says why.
    closed = AiRuntime(model=ai.model, background=ai.background, approved=lambda: ("INTERNAL",))
    summary, rows = script.run_benchmark(tmp_path, "other", closed)
    assert {r["error"].split(":")[0] for r in rows} == {"classification_not_approved"}
    assert summary["counts"]["found"] == 0
