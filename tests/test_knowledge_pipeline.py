"""Convert, ingest and lint inside a personal sandbox (K1, owner 2026-10-11)."""

from pathlib import Path

import pytest
from test_knowledge_sandbox import _base, _snapshot
from test_planning import PlanningModel, answers

from knowledge.pipeline import KnowledgePipeline, PipelineError
from knowledge.planning import PLAN_CONTRACT
from knowledge.sandbox import Sandboxes


def _pipeline(tmp_path: Path, model: PlanningModel | None = None) -> tuple[KnowledgePipeline, Path]:
    base = _base(tmp_path)
    pipeline = KnowledgePipeline(Sandboxes(tmp_path / "workspace"), {"k-test": base},
                                 model=model, alias="company")  # type: ignore[arg-type]
    return pipeline, base


def _sandbox_with_note(pipeline: KnowledgePipeline) -> tuple[str, Path]:
    info = pipeline.create_sandbox("k-test", "trial", "leo.chi")
    root = pipeline.sandboxes.open(info.sandbox_id)[1].root
    (root / "drop/notes").mkdir(parents=True, exist_ok=True)
    (root / "drop/notes/mcp.txt").write_text("MCP is a protocol for tools.\n", encoding="utf-8")
    return info.sandbox_id, root


def test_an_unknown_base_vault_is_refused(tmp_path: Path) -> None:
    pipeline, _ = _pipeline(tmp_path)
    with pytest.raises(PipelineError, match="unknown_base_vault"):
        pipeline.create_sandbox("other", "x", "a")


def test_convert_previews_then_writes_raw_only_in_the_sandbox(tmp_path: Path) -> None:
    pipeline, base = _pipeline(tmp_path)
    before = _snapshot(base)
    sandbox, root = _sandbox_with_note(pipeline)
    (root / "drop/notes/odd.xyz").write_text("?", encoding="utf-8")
    preview = pipeline.convert(sandbox)
    statuses = {i.path: i.status for i in preview.items}
    assert statuses == {"drop/notes/mcp.txt": "written", "drop/notes/odd.xyz": "unsupported"}
    assert not list((root / "raw/notes").glob("mcp*.md"))  # a dry run writes nothing
    applied = pipeline.convert(sandbox, ("drop/notes/mcp.txt",), mode="apply")
    raw_ref = applied.items[0].raw_ref
    assert raw_ref and (root / raw_ref).is_file()
    assert _snapshot(base) == before
    with pytest.raises(PipelineError, match="outside_drop"):
        pipeline.convert(sandbox, ("wiki/concepts/EVM.md",))


def test_ingest_plans_with_the_vault_schema_and_applies_in_the_sandbox(tmp_path: Path) -> None:
    model = PlanningModel(answers())
    pipeline, base = _pipeline(tmp_path, model)
    before = _snapshot(base)
    sandbox, root = _sandbox_with_note(pipeline)
    raw_ref = pipeline.convert(sandbox, mode="apply").items[0].raw_ref
    assert raw_ref
    planned = pipeline.plan_ingest(sandbox, raw_ref)
    assert planned.status == "planned" and planned.plan_id and planned.schema_source == "vault"
    assert {p.path for p in planned.pages} == {"wiki/sources/MCP notes.md", "wiki/entities/MCP.md"}
    plan_request = next(r for r in model.requests if r.output_contract == PLAN_CONTRACT)
    assert plan_request.messages[0].text == "schema"  # the sandbox's CLAUDE.md
    applied = pipeline.apply_ingest(sandbox, planned.plan_id)
    assert applied.status == "applied" and "wiki/entities/MCP.md" in applied.written
    assert (root / "wiki/entities/MCP.md").is_file()
    assert _snapshot(base) == before


def test_a_plan_is_stale_when_a_page_it_touches_changed(tmp_path: Path) -> None:
    pipeline, _ = _pipeline(tmp_path, PlanningModel(answers()))
    sandbox, root = _sandbox_with_note(pipeline)
    (root / "wiki/entities").mkdir(parents=True, exist_ok=True)
    (root / "wiki/entities/MCP.md").write_text("---\ntitle: MCP\n---\nold\n", encoding="utf-8")
    raw_ref = pipeline.convert(sandbox, mode="apply").items[0].raw_ref
    assert raw_ref
    planned = pipeline.plan_ingest(sandbox, raw_ref)
    assert {p.path: p.change for p in planned.pages}["wiki/entities/MCP.md"] == "changed"
    (root / "wiki/entities/MCP.md").write_text("---\ntitle: MCP\n---\nedited\n", encoding="utf-8")
    assert planned.plan_id
    result = pipeline.apply_ingest(sandbox, planned.plan_id)
    assert result.status == "rejected" and result.problems == ("stale_plan",)


def test_ingest_needs_a_model_and_a_known_raw_and_plan(tmp_path: Path) -> None:
    pipeline, _ = _pipeline(tmp_path)
    sandbox, _ = _sandbox_with_note(pipeline)
    with pytest.raises(PipelineError, match="no_model"):
        pipeline.plan_ingest(sandbox, "raw/notes/mcp.md")
    pipeline.model, pipeline.alias = PlanningModel(answers()), "company"  # type: ignore[assignment]
    with pytest.raises(PipelineError, match="unknown_raw"):
        pipeline.plan_ingest(sandbox, "raw/notes/nothing.md")
    for bad in ("plan-x", "../plan", "plan-../../x"):
        with pytest.raises(PipelineError, match="unknown_plan"):
            pipeline.apply_ingest(sandbox, bad)


def test_lint_reports_on_the_sandbox(tmp_path: Path) -> None:
    pipeline, _ = _pipeline(tmp_path)
    sandbox, root = _sandbox_with_note(pipeline)
    page = "---\ntitle: X\n---\nSee [[Missing]].\n⚠️ A says 1, B says 2\n"
    (root / "wiki/concepts/X.md").write_text(page, encoding="utf-8")
    summary = pipeline.lint(sandbox)
    assert summary.counts["dangling"] >= 1 and summary.counts["open_conflicts"] == 1
    assert any(f.startswith("open conflict: wiki/concepts/X.md") for f in summary.findings)
    assert not summary.clean


def test_drop_add_contents_and_discard(tmp_path: Path) -> None:
    pipeline, base = _pipeline(tmp_path, PlanningModel(answers()))
    before = _snapshot(base)
    sandbox = pipeline.create_sandbox("k-test", "files", "a").sandbox_id
    assert pipeline.add_drop(sandbox, "Market/x.txt", b"hello\n") == "drop/Market/x.txt"
    for name, code in (("../escape.txt", "outside_drop"), ("Market/x.txt", "drop_exists"),
                       (" ", "outside_drop")):
        with pytest.raises(PipelineError, match=code):
            pipeline.add_drop(sandbox, name, b"x")
    raw_ref = pipeline.convert(sandbox, mode="apply").items[0].raw_ref
    assert raw_ref
    plan_id = pipeline.plan_ingest(sandbox, raw_ref).plan_id
    listed = pipeline.contents(sandbox)
    assert "drop/Market/x.txt" in listed.drop and raw_ref in listed.raw
    assert [(p.plan_id, p.raw_ref) for p in listed.plans] == [(plan_id, raw_ref)]
    pipeline.discard_sandbox(sandbox)
    assert pipeline.sandboxes.list() == ()
    assert _snapshot(base) == before


def test_adopt_makes_legacy_raw_ingestible_without_touching_its_bytes(tmp_path: Path) -> None:
    pipeline, base = _pipeline(tmp_path, PlanningModel(answers()))
    sandbox = pipeline.create_sandbox("k-test", "legacy", "a").sandbox_id
    root = pipeline.sandboxes.open(sandbox)[1].root
    legacy = (root / "raw/notes/a.md").read_bytes()
    assert "raw/notes/a.md" not in pipeline.contents(sandbox).raw  # not yet adopted
    preview = pipeline.adopt(sandbox)
    assert preview.mode == "dry_run" and preview.raw_adopted == 1
    assert "raw/notes/a.md" not in pipeline.contents(sandbox).raw  # a dry run records nothing
    applied = pipeline.adopt(sandbox, mode="apply")
    assert applied.raw_adopted == 1
    assert "raw/notes/a.md" in pipeline.contents(sandbox).raw
    assert (root / "raw/notes/a.md").read_bytes() == legacy


def test_index_steps_run_in_the_sandbox(tmp_path: Path) -> None:
    from test_layered_index import _answer, _Model

    pipeline, base = _pipeline(tmp_path, _Model(_answer))  # type: ignore[arg-type]
    before = _snapshot(base)
    sandbox = pipeline.create_sandbox("k-test", "index", "a").sandbox_id
    first = pipeline.index_enrich(sandbox, limit=1)
    assert first.done == 1
    assert pipeline.index_build(sandbox).pages >= 1  # preview
    built = pipeline.index_build(sandbox, mode="apply")
    assert "index.md" in built.written
    assert _snapshot(base) == before
