"""A sandbox maintains one folder and edits only its rules (owner, 2026-10-13)."""

from pathlib import Path

import pytest
from test_knowledge_sandbox import _base

from host_runtime.web_page import PAGE
from knowledge.pipeline import KnowledgePipeline, PipelineError
from knowledge.sandbox import Sandboxes
from knowledge.schema import category_skills
from knowledge.vault import Vault


def _skill(root: Path, name: str, front: str) -> None:
    (root / "skills" / name).mkdir(parents=True, exist_ok=True)
    (root / "skills" / name / "SKILL.md").write_text(
        f"---\nname: {name}\n{front}---\n\n# {name}\nrules of {name}\n", encoding="utf-8")


def _project(tmp_path: Path) -> tuple[KnowledgePipeline, Path]:
    base = _base(tmp_path)
    for folder in ("drop/Knowledge", "drop/Market", "drop/Productions/VNA",
                   "drop/Productions/CMX"):
        (base / folder).mkdir(parents=True)
        (base / folder / "x.txt").write_text(folder + "\n", encoding="utf-8")
    _skill(base, "ingest-knowledge", "mode: procedure\napplies_to: raw/Knowledge\n")
    _skill(base, "ingest-market", "mode: procedure\napplies_to: raw/Market\n")
    _skill(base, "ingest-productions", "mode: procedure\napplies_to: raw/Productions\n")
    _skill(base, "ingest-vna", "mode: procedure\napplies_to: raw/Productions/VNA\n")
    _skill(base, "ask-knowledge", "mode: answer\n")  # written before applies_to
    _skill(base, "ask-productions", "mode: answer\napplies_to: raw/Productions\n")
    return KnowledgePipeline(Sandboxes(tmp_path / "workspace"), {"rs-k": base}), base


def _access(pipeline: KnowledgePipeline, sandbox: str) -> dict[str, str]:
    return {rule.path: rule.access for rule in pipeline.rule_files(sandbox).rules}


def test_a_folder_sandbox_edits_its_rules_and_reads_the_shared_ones(tmp_path: Path) -> None:
    pipeline, _ = _project(tmp_path)
    knowledge = pipeline.create_sandbox("rs-k", "k", "leo", scope="Knowledge").sandbox_id
    assert _access(pipeline, knowledge) == {
        "CLAUDE.md": "shared", "skills/ask-knowledge/SKILL.md": "edit",
        "skills/ingest-knowledge/SKILL.md": "edit"}  # Market's rules are not listed
    vna = pipeline.create_sandbox("rs-k", "v", "leo", scope="Productions/VNA").sandbox_id
    assert _access(pipeline, vna) == {
        "CLAUDE.md": "shared", "skills/ask-productions/SKILL.md": "inherited",
        "skills/ingest-productions/SKILL.md": "inherited",
        "skills/ingest-vna/SKILL.md": "edit"}
    kinds = {r.path: r.kind for r in pipeline.rule_files(vna).rules}
    assert kinds["skills/ask-productions/SKILL.md"] == "answer"


def test_writes_outside_the_scope_are_refused(tmp_path: Path) -> None:
    pipeline, _ = _project(tmp_path)
    vna = pipeline.create_sandbox("rs-k", "v", "leo", scope="Productions/VNA").sandbox_id
    text = "---\nname: ingest-vna\nmode: procedure\napplies_to: raw/Productions/VNA\n---\nnew\n"
    pipeline.write_rule(vna, "skills/ingest-vna/SKILL.md", text)
    for path, body in (
            ("CLAUDE.md", "schema\n"),
            ("skills/ingest-productions/SKILL.md", text.replace("Productions/VNA", "Productions")),
            ("skills/ingest-market/SKILL.md", text.replace("Productions/VNA", "Market")),
            # moving its own rule onto another folder's data
            ("skills/ingest-vna/SKILL.md", text.replace("Productions/VNA", "Productions/CMX")),
            # a new skill for another folder
            ("skills/ingest-cmx/SKILL.md", text.replace("Productions/VNA", "Productions/CMX"))):
        with pytest.raises(PipelineError, match="rule_outside_scope"):
            pipeline.write_rule(vna, path, body)
    pipeline.write_rule(vna, "skills/ask-vna/SKILL.md", "---\nname: ask-vna\nmode: answer\n"
                        "applies_to: raw/Productions/VNA\n---\nx\n")


def test_pull_and_creation_stay_inside_the_scope(tmp_path: Path) -> None:
    pipeline, _ = _project(tmp_path)
    productions = pipeline.create_sandbox("rs-k", "p", "leo", scope="Productions").sandbox_id
    assert pipeline.pull(productions, ("Productions/VNA",)).copied == ("Productions/VNA/x.txt",)
    with pytest.raises(PipelineError, match="outside_scope"):
        pipeline.pull(productions, ("Market",))
    for bad, code in (("../wiki", "bad_scope"), ("Nope", "unknown_scope")):
        with pytest.raises(PipelineError, match=code):
            pipeline.create_sandbox("rs-k", "x", "leo", scope=bad)
    legacy = pipeline.create_sandbox("rs-k", "old", "leo").sandbox_id  # no scope: as before
    assert set(_access(pipeline, legacy).values()) == {"edit"}


def test_an_answer_skill_with_applies_to_is_not_an_ingest_rule(tmp_path: Path) -> None:
    _, base = _project(tmp_path)
    names = [name for name, _ in category_skills(Vault(base), "raw/Productions/VNA/a.md")]
    assert names == ["ingest-productions", "ingest-vna"]


def test_the_page_merges_pull_and_rules_under_the_scope() -> None:
    for hook in ('id="kp-scope"', 'id="kp-scope-name"', "1. Scope and rules", "kpLoadScopes",
                 "6. Push to the project vault"):
        assert hook in PAGE
    assert "2. Rules (schema and skills)" not in PAGE
