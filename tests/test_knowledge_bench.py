"""Question sets by folder and the sandbox benchmark (collaboration C3)."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from test_knowledge_sandbox import _base

from capabilities.knowledge_query.handlers import KnowledgeQueryHandler
from common.assets import AssetIdentity
from host_runtime.contracts import KnowledgeAskRequest
from host_runtime.knowledge_bench import catalog_for, latest, run_benchmark
from host_runtime.knowledge_harness import KnowledgeHarness
from host_runtime.web_page import PAGE
from knowledge.evolution import KnowledgeCatalog
from knowledge.questions import default_sets, grade, load, parse
from knowledge.vault import Vault

WIFI7 = """---
name: wifi7-instruments
---

# 客戶要做 Wi-Fi 7 射頻量測，我們有哪幾台儀器可以做？

必須提到:
  - FSWX
  - K91BE

不可以說:
  - 只有 FSV3000

<!--
必須提到:
  - not a term, a comment
-->
"""


def _questions(root: Path) -> None:
    for rel, text in {"market/q1.md": WIFI7.replace("Wi-Fi 7", "Wi-Fi 7 market"),
                      "productions/q2.md": WIFI7,
                      "market_productions/q3.md": WIFI7.replace("FSWX", "CMX500"),
                      "vna/q4.md": WIFI7, "general.md": WIFI7,
                      "market/free.md": "# 自由格式的題目\n\n先確認:\n  - ZNA-B8\n"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")


def test_the_owners_question_format_is_parsed_and_graded() -> None:
    question = parse(WIFI7, set_name="productions", path="productions/q2.md")
    assert question is not None
    assert question.must == ("FSWX", "K91BE") and question.must_not == ("只有 FSV3000",)
    assert grade(question, "可用 FSWX 搭配 k91be").passed  # case does not matter
    missed = grade(question, "只有 FSV3000 可以")
    assert missed.missing == ("FSWX", "K91BE") and missed.forbidden == ("只有 FSV3000",)


def test_sets_follow_folders_and_the_scope_picks_the_defaults(tmp_path: Path) -> None:
    _questions(tmp_path)
    found = load(tmp_path)
    names = sorted({q.set for q in found})
    assert names == ["", "market", "market_productions", "productions", "vna"]
    # Plural and order do not matter: "Productions/CMX500" is the production category.
    assert default_sets(names, ("Market/AI", "Productions/CMX500")) == (
        "market", "market_productions", "productions")
    assert default_sets(names, ("Market",)) == ("market",)
    assert default_sets(["productions_market"], ("market", "production")) == (
        "productions_market",)
    free = next(q for q in found if q.path == "market/free.md")
    assert free.must == () and free.must_not == ()  # not gradable; reported, not guessed


def test_a_benchmark_compares_sandbox_and_project_and_finds_regressions(tmp_path: Path) -> None:
    sandbox, project = Vault(_base(tmp_path / "s")), Vault(_base(tmp_path / "p"))
    _questions(sandbox.root / "checks" / "questions")
    seen: list[str] = []

    def ask(request: KnowledgeAskRequest, catalog: KnowledgeCatalog) -> dict[str, Any]:
        side = request.asset.name
        seen.append(side)
        assert catalog.get(request.asset) is not None
        # The project vault knows FSWX; the sandbox lost it but knows CMX500.
        text = "FSWX 與 K91BE" if side == "project" else "CMX500 與 K91BE"
        return {"ok": True, "answer": text}

    report = run_benchmark(ask, sandbox_id="sb-x", sandbox=sandbox, project=project,
                           sets=("market", "productions", "market_productions"),
                           actor="leo.chi", skill=None)
    assert report.status == "finished" and report.total == 3
    assert report.ungraded == ("market/free.md",)
    assert set(report.regressions) == {"market/q1.md", "productions/q2.md"}
    assert report.project_score == 2 and report.sandbox_score == 1
    assert sorted(seen) == ["project"] * 3 + ["sandbox"] * 3
    saved = latest(sandbox)
    assert saved is not None and saved["run_id"] == report.run_id
    assert saved["regressions"] == list(report.regressions)


def test_a_vault_that_is_not_installed_is_asked_through_the_harness(tmp_path: Path) -> None:
    vault = Vault(_base(tmp_path))
    asset = AssetIdentity(namespace="engineering", name="sandbox", version="0.0.0-candidate")
    catalog = catalog_for(vault, asset, "leo.chi")
    assert catalog.get(asset) is not None
    installed = SimpleNamespace(handler=KnowledgeQueryHandler(KnowledgeCatalog(), object(),  # type: ignore[arg-type]
                                                              alias="company"))
    runtime = SimpleNamespace(
        actor="leo.chi",
        agent=SimpleNamespace(gateway=SimpleNamespace(bridge=SimpleNamespace(
            installed=SimpleNamespace(get=lambda _identity: installed)))))
    other = AssetIdentity(namespace="engineering", name="other", version="1.0.0")
    reply = KnowledgeHarness(runtime, None).ask(
        KnowledgeAskRequest(asset=other, question="EVM?"), catalog=catalog)
    # A version the catalog does not hold is refused exactly as on the Bridge route.
    assert reply["ok"] is False
    assert reply["outcome"]["capability"]["failure"]["code"] == "knowledge_version_not_found"
    assert json.dumps(reply)  # the page can show it


def test_the_knowledge_tab_offers_pull_and_benchmark() -> None:
    for hook in ('id="kp-pull"', 'id="kp-bench"', "/api/knowledge/benchmark/start",
                 '"question-sets"', '"drop-folders"'):
        assert hook in PAGE
