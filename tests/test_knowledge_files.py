"""Preview sandbox files and edit its rules (collaboration C2)."""

from pathlib import Path

import pytest
from test_knowledge_pipeline import _pipeline, _sandbox_with_note
from test_knowledge_sandbox import _snapshot
from test_planning import PlanningModel, answers

from host_runtime.web_page import PAGE
from knowledge.pipeline import PipelineError


def test_rules_are_listed_read_and_saved_only_in_the_sandbox(tmp_path: Path) -> None:
    pipeline, base = _pipeline(tmp_path)
    before = _snapshot(base)
    sandbox = pipeline.create_sandbox("k-test", "rules", "leo.chi").sandbox_id
    assert pipeline.rule_files(sandbox).files == ("CLAUDE.md",)
    saved = pipeline.write_rule(sandbox, "skills/ingest-market/SKILL.md",
                                "---\nname: ingest-market\napplies_to: raw/Market\n---\n日期必填\n")
    assert saved.path == "skills/ingest-market/SKILL.md"
    assert pipeline.rule_files(sandbox).files == ("CLAUDE.md", "skills/ingest-market/SKILL.md")
    assert "日期必填" in pipeline.read_file(sandbox, "skills/ingest-market/SKILL.md").text
    assert _snapshot(base) == before
    for bad in ("wiki/concepts/EVM.md", "skills/../CLAUDE.md", "raw/notes/a.md",
                "skills/x/other.md"):
        with pytest.raises(PipelineError, match="not_a_rule_file"):
            pipeline.write_rule(sandbox, bad, "x")


def test_only_markdown_inside_the_knowledge_areas_can_be_previewed(tmp_path: Path) -> None:
    pipeline, _ = _pipeline(tmp_path)
    sandbox = pipeline.create_sandbox("k-test", "preview", "leo.chi").sandbox_id
    assert pipeline.read_file(sandbox, "wiki/concepts/EVM.md").text.endswith("EVM\n")
    for bad in ("sandbox.json", "../base/CLAUDE.md", "raw/../../x.md", "wiki/x.txt"):
        with pytest.raises(PipelineError, match="not_previewable"):
            pipeline.read_file(sandbox, bad)
    with pytest.raises(PipelineError, match="unknown_file"):
        pipeline.read_file(sandbox, "wiki/missing.md")


def test_a_planned_page_shows_before_and_after(tmp_path: Path) -> None:
    pipeline, _ = _pipeline(tmp_path, PlanningModel(answers()))
    sandbox, _ = _sandbox_with_note(pipeline)
    raw_ref = pipeline.convert(sandbox, mode="apply").items[0].raw_ref
    assert raw_ref
    planned = pipeline.plan_ingest(sandbox, raw_ref)
    assert planned.plan_id
    page = pipeline.plan_page(sandbox, planned.plan_id, "wiki/sources/MCP notes.md")
    assert page.before == "" and "[[MCP]]" in page.after
    with pytest.raises(PipelineError, match="unknown_plan"):
        pipeline.plan_page(sandbox, "plan-../x", "wiki/x.md")


def test_the_knowledge_tab_offers_preview_compare_and_the_rule_editor() -> None:
    for hook in ('id="kp-rules"', 'id="kp-rule-text"', 'id="kp-viewer"', '"plan-page"',
                 '"rule-write"', '"file-read"'):
        assert hook in PAGE


def test_the_guide_and_templates_ship_and_the_answer_template_applies(tmp_path: Path) -> None:
    from knowledge.schema import MAX_ANSWER_RULE_CHARS, answer_rules, ingest_conventions
    from knowledge.vault import Vault

    pipeline, base = _pipeline(tmp_path)
    guide = pipeline.skill_guide()
    assert "mode: answer" in guide.answer_template and "mode: procedure" in guide.ingest_template
    assert "Skill 撰寫指引" in guide.guide
    (base / "skills/ask-knowledge").mkdir(parents=True)
    (base / "skills/ask-knowledge/SKILL.md").write_text(guide.answer_template, encoding="utf-8")
    rules = answer_rules(Vault(base), "EVM 怎麼量？")
    assert [name for name, _ in rules] == ["ask-knowledge"]
    assert len(rules[0][1]) < MAX_ANSWER_RULE_CHARS  # nothing of the template is cut
    # An answering skill is never sent as ingest rules.
    assert ingest_conventions(Vault(base), "raw/notes/a.md", "b").skill is None
    assert '"skill-guide"' in PAGE and "Writing guide" in PAGE
