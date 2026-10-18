"""knowledge_v1 `--route direct` and `--set core` for U7 (owner 2026-10-18)."""

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BENCH = Path(__file__).resolve().parents[1] / "benchmarks" / "knowledge_v1"
sys.path.insert(0, str(BENCH))

# The benchmark scripts are not a package; load them as plain modules.
run: Any = importlib.import_module("run")
knowledge_use: Any = importlib.import_module("evidence").knowledge_use

IDENTITY = {"namespace": "company", "name": "rs-knowledge", "version": "1.0.3"}
SKILL = {"namespace": "engineering", "name": "knowledge-query", "version": "1.2.0"}


class FakeSession:
    def __init__(self, assets: dict[str, Any], answer: dict[str, Any] | None = None) -> None:
        self.assets, self.answer = assets, answer or {}
        self.calls: list[tuple[str, Any]] = []

    def _call(
        self, path: str, body: dict[str, Any] | None = None, timeout: float | None = None
    ) -> tuple[int, dict[str, Any]]:
        self.calls.append((path, body))
        return 200, self.assets if path == "/api/assets" else self.answer


def assets(knowledge: int = 1, skills: int = 1) -> dict[str, Any]:
    return {
        "knowledge": [{**IDENTITY, "name": f"vault-{i}"} for i in range(knowledge)],
        "skills": [{**SKILL, "knowledge_harness_selectable": True} for _ in range(skills)]
        + [{**SKILL, "name": "other", "knowledge_harness_selectable": False}],
    }


def test_direct_target_is_the_one_vault_and_knowledge_skill() -> None:
    target = run.direct_target(FakeSession(assets()))
    assert target == {"asset": {**IDENTITY, "name": "vault-0"}, "skill": SKILL}


@pytest.mark.parametrize(("knowledge", "skills"), [(0, 1), (2, 1), (1, 0), (1, 2)])
def test_direct_target_refuses_to_guess(knowledge: int, skills: int) -> None:
    with pytest.raises(RuntimeError, match="one Vault and one Knowledge Skill"):
        run.direct_target(FakeSession(assets(knowledge, skills)))


def test_a_direct_answer_is_graded_as_the_direct_route() -> None:
    answer = {
        "ok": True,
        "answer": "EVM is ... [1]",
        "harness": {"phase": "validated"},
        "outcome": {"capability": {"status": "succeeded", "data": {"answer": "EVM"}}},
        "evidence": {"raw_citations": 1},
    }
    session = FakeSession(assets(), answer)
    target = run.direct_target(session)
    exchange = run.ask_direct(session, target, "What is EVM?")
    assert session.calls[-1] == ("/api/knowledge/ask", {**target, "question": "What is EVM?"})
    assert exchange["route_forced"] == "direct" and exchange["http_status"] == 200
    use = knowledge_use(exchange)
    assert use["route"] == "direct" and use["status"] == "succeeded"
    assert use["text"] == "EVM is ... [1]" and use["phase"] == "validated"


def test_the_core_set_is_the_36_coverage_questions() -> None:
    core = json.loads((BENCH / "questions" / "coverage.json").read_text(encoding="utf-8"))["core"]
    ids = [str(item["id"] if isinstance(item, dict) else item) for item in core]
    assert len(ids) == len(set(ids)) == 36
    bank = {q["id"] for q in run.load()}
    assert set(ids) <= bank
