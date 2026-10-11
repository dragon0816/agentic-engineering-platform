"""Push a sandbox into its project vault (collaboration C4)."""

import json
from pathlib import Path
from typing import Any

from test_knowledge_bench import WIFI7
from test_knowledge_sandbox import _base, _snapshot

from host_runtime.contracts import KnowledgeAskRequest
from host_runtime.knowledge_push import latest_push, run_push
from knowledge.evolution import KnowledgeCatalog
from knowledge.pipeline import KnowledgePipeline
from knowledge.sandbox import Sandboxes

PAGE = "---\ntitle: CMX500\n---\nCMX500\n\n## 規格\n\n- 8 GHz\n\n## Option\n\n- K100\n"


def _project(tmp_path: Path, maintainers: tuple[str, ...] = ()) -> tuple[KnowledgePipeline, Path]:
    base = _base(tmp_path)
    (base / "wiki/entities").mkdir(parents=True)
    (base / "wiki/entities/CMX500.md").write_text(PAGE, encoding="utf-8")
    (base / "checks/questions/market").mkdir(parents=True)
    (base / "checks/questions/market/q.md").write_text(WIFI7, encoding="utf-8")
    pipeline = KnowledgePipeline(Sandboxes(tmp_path / "workspace"), {"rs-k": base},
                                 maintainers={"rs-k": maintainers})
    return pipeline, base


def _sandbox(pipeline: KnowledgePipeline, edit: tuple[str, str] = ("- 8 GHz", "- 8 GHz\n- 400 MHz")
             ) -> tuple[str, Path]:
    sandbox = pipeline.create_sandbox("rs-k", "market ai", "leo.chi").sandbox_id
    root = pipeline.sandboxes.open(sandbox)[1].root
    page = root / "wiki/entities/CMX500.md"
    page.write_text(page.read_text(encoding="utf-8").replace(*edit), encoding="utf-8")
    return sandbox, root


def _answers(sandbox: str, project: str) -> Any:
    def ask(request: KnowledgeAskRequest, catalog: KnowledgeCatalog) -> dict[str, Any]:
        return {"ok": True, "answer": sandbox if request.asset.name == "sandbox" else project}
    return ask


def test_a_passing_push_writes_in_place_with_a_backup_and_a_record(tmp_path: Path) -> None:
    pipeline, base = _project(tmp_path)
    sandbox, root = _sandbox(pipeline)
    report = run_push(pipeline, _answers("FSWX K91BE", "FSWX K91BE"), sandbox_id=sandbox,
                      actor="leo.chi", sets=("market",))
    assert report.status == "pushed", report.reason
    assert "- 400 MHz" in (base / "wiki/entities/CMX500.md").read_text(encoding="utf-8")
    assert report.written == ("wiki/entities/CMX500.md",)
    assert report.backup and (Path(report.backup) / "wiki/entities/CMX500.md").read_text(
        encoding="utf-8") == PAGE
    record = json.loads((base / "pushes" / f"{report.push_id}.json").read_text(encoding="utf-8"))
    assert record["actor"] == "leo.chi" and record["sandbox_id"] == sandbox
    assert record["benchmark"]["sandbox_score"] == 1
    assert "push | market ai" in (base / "log.md").read_text(encoding="utf-8")
    assert latest_push(pipeline.sandboxes.open(sandbox)[1]) is not None


def test_a_regression_blocks_the_push_and_writes_nothing(tmp_path: Path) -> None:
    pipeline, base = _project(tmp_path)
    sandbox, _ = _sandbox(pipeline)
    before = _snapshot(base)
    report = run_push(pipeline, _answers("K91BE only", "FSWX K91BE"), sandbox_id=sandbox,
                      actor="leo.chi", sets=("market",))
    assert report.status == "blocked" and report.reason and "regression" in report.reason
    assert _snapshot(base) == before


def test_a_later_push_re_merges_when_someone_pushed_first(tmp_path: Path) -> None:
    pipeline, base = _project(tmp_path)
    sandbox, _ = _sandbox(pipeline)
    calls = {"n": 0}

    def ask(request: KnowledgeAskRequest, catalog: KnowledgeCatalog) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:  # another maintainer's push lands during our benchmark
            page = base / "wiki/entities/CMX500.md"
            page.write_text(page.read_text(encoding="utf-8").replace("- K100", "- K100\n- K200"),
                            encoding="utf-8")
        return {"ok": True, "answer": "FSWX K91BE"}

    report = run_push(pipeline, ask, sandbox_id=sandbox, actor="leo.chi", sets=("market",))
    assert report.status == "pushed" and report.attempts == 2
    text = (base / "wiki/entities/CMX500.md").read_text(encoding="utf-8")
    assert "- 400 MHz" in text and "- K200" in text  # both pushes kept


def test_conflicts_and_non_maintainers_stop_before_writing(tmp_path: Path) -> None:
    pipeline, base = _project(tmp_path, maintainers=("leo.chi",))
    sandbox, _ = _sandbox(pipeline, ("- 8 GHz", "- 7.5 GHz"))
    page = base / "wiki/entities/CMX500.md"
    page.write_text(PAGE.replace("- 8 GHz", "- 6 GHz"), encoding="utf-8")
    before = _snapshot(base)
    ask = _answers("FSWX K91BE", "FSWX K91BE")
    conflicted = run_push(pipeline, ask, sandbox_id=sandbox, actor="leo.chi", sets=("market",))
    assert conflicted.status == "conflicts"
    assert conflicted.conflicts == ("wiki/entities/CMX500.md#規格",)
    refused = run_push(pipeline, ask, sandbox_id=sandbox, actor="someone", sets=("market",))
    assert refused.status == "refused"
    assert _snapshot(base) == before
    resolved = run_push(pipeline, ask, sandbox_id=sandbox, actor="leo.chi", sets=("market",),
                        resolutions={"wiki/entities/CMX500.md#規格": "sandbox"})
    assert resolved.status == "pushed" and "7.5 GHz" in page.read_text(encoding="utf-8")
