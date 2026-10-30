"""The benchmark of a wiki repository and its push check (knowledge repositories R4a).

A run asks the question sets against the working folder and the pushed head
and records the pages it tested; a push of exactly those pages is blocked by
a regression, and an untested push only carries a note. The model is a fake
that answers from the page it finds. All data is fictional.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from test_knowledge_repos_api import PAGE, _call, _ok, _two_pcs

from host_runtime import wiki_bench
from host_runtime.contracts import KnowledgeAskRequest
from knowledge import wiki_repos, wiki_work
from knowledge.evolution import KnowledgeCatalog
from knowledge.repo import set_benchmark

QUESTION = """---
name: tester-options
---

# Tester X 是什麼？

必須提到:
  - Intro
"""


@pytest.fixture(autouse=True)
def _no_gate() -> Iterator[None]:
    yield
    set_benchmark(None)


def _ask(request: KnowledgeAskRequest, catalog: KnowledgeCatalog) -> dict[str, Any]:
    """Answers with the tester page of whichever vault it is given."""
    found = catalog.get(request.asset)
    assert found is not None
    return {"ok": True, "answer": found[1].read_bytes(PAGE).decode("utf-8")}


def _questions(root: Path) -> Path:
    folder = root / "questions"
    (folder / "products").mkdir(parents=True)
    (folder / "products" / "q1.md").write_text(QUESTION, encoding="utf-8")
    return folder


def _edit_folder(ws: Path, repo_id: str, old: str, new: str) -> None:
    repo = wiki_repos.repository(ws, repo_id)
    folder = wiki_work.open_work(repo)
    text = (folder / PAGE).read_text(encoding="utf-8")
    assert old in text
    (folder / PAGE).write_bytes(text.replace(old, new).encode("utf-8"))


def test_a_tested_regression_blocks_the_push_and_untested_work_is_noted(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    set_benchmark(partial(wiki_bench.gate, a))
    questions = _questions(tmp_path)
    # A tested edit that keeps the answer: pushed, with the test's score.
    _edit_folder(a, repo_id, "Nothing yet.", "Shipping in Q3.")
    report = wiki_bench.run(
        a, repo_id, _ask, sets=("products",), actor="alice", questions_fallback=questions
    )
    assert report.status == "finished" and report.total == 1
    assert report.regressions == () and report.pages_sha256
    _ok(_call(a, "POST", f"/{repo_id}/commit", {"purpose": "出貨時程"}))
    pushed = _ok(_call(a, "POST", f"/{repo_id}/push", {}))
    assert pushed["status"] == "pushed"
    assert any("1/1 題通過" in n for n in pushed["notes"])
    # One that drops an unsourced line the answer needs: only the test catches it.
    _edit_folder(a, repo_id, "Intro.", "Overview.")
    report = wiki_bench.run(
        a, repo_id, _ask, sets=("products",), actor="alice", questions_fallback=questions
    )
    assert report.regressions == ("products/q1.md",)
    _ok(_call(a, "POST", f"/{repo_id}/commit", {"purpose": "改開頭"}))
    blocked = _ok(_call(a, "POST", f"/{repo_id}/push", {}))
    assert blocked["status"] == "blocked"
    assert blocked["blocking"] == ["測試退步：products/q1.md 在 push 前答得對，現在答錯"]


def test_an_untested_push_goes_ahead_with_a_note(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    set_benchmark(partial(wiki_bench.gate, a))
    _edit_folder(a, repo_id, "Nothing yet.", "Shipping in Q3.")
    wiki_work.capture(wiki_repos.repository(a, repo_id))
    _ok(_call(a, "POST", f"/{repo_id}/commit", {"purpose": "出貨時程"}))
    pushed = _ok(_call(a, "POST", f"/{repo_id}/push", {}))
    assert pushed["status"] == "pushed"
    assert any("沒有跑過測試" in n for n in pushed["notes"])
