"""Vault-resident ingest rules (K3.1, owner 2026-10-11)."""

from pathlib import Path

from test_knowledge_pipeline import _pipeline, _sandbox_with_note
from test_knowledge_sandbox import _base
from test_planning import PlanningModel, answers

from knowledge.planning import PLAN_CONTRACT
from knowledge.schema import category_skill, ingest_conventions
from knowledge.vault import Vault


def _skill(root: Path, name: str, applies_to: str | None, body: str) -> None:
    folder = root / "skills" / name
    folder.mkdir(parents=True, exist_ok=True)
    scope = f"applies_to: {applies_to}\n" if applies_to else ""
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\nmode: procedure\n{scope}---\n{body}\n", encoding="utf-8"
    )


def test_the_category_skill_follows_the_raw_folder(tmp_path: Path) -> None:
    root = _base(tmp_path)
    _skill(root, "ingest-market", "raw/Market", "Market rules: every claim has a date.")
    _skill(root, "ingest-market-5g", "raw/Market/5G", "5G market rules.")
    _skill(root, "ask-market", None, "Answering rules.")
    vault = Vault(root)
    assert category_skill(vault, "raw/Market/deck.md") == (
        "ingest-market",
        "Market rules: every claim has a date.",
    )
    assert category_skill(vault, "raw/Market/5G/nr.md") == ("ingest-market-5g", "5G market rules.")
    assert category_skill(vault, "raw/Marketing/x.md") is None  # a folder, not a prefix
    assert category_skill(vault, "raw/drop/x.md") is None
    rules = ingest_conventions(vault, "raw/Market/deck.md", "built-in")
    assert rules.schema_source == "vault" and rules.skill == "ingest-market"
    assert rules.text.startswith("schema") and rules.text.endswith("every claim has a date.")
    assert "Answering rules" not in rules.text


def test_a_vault_without_a_schema_uses_the_built_in_conventions(tmp_path: Path) -> None:
    root = _base(tmp_path)
    (root / "CLAUDE.md").unlink()
    _skill(root, "ingest-market", "raw/Market", "Market rules.")
    rules = ingest_conventions(Vault(root), "raw/Market/deck.md", "built-in")
    assert (rules.text, rules.schema_source, rules.skill) == ("built-in", "built_in", None)


def test_ingest_sends_the_schema_and_the_category_rules(tmp_path: Path) -> None:
    model = PlanningModel(answers())
    pipeline, _ = _pipeline(tmp_path, model)
    sandbox, root = _sandbox_with_note(pipeline)
    _skill(root, "ingest-notes", "raw/notes", "Notes rules.")
    raw_ref = pipeline.convert(sandbox, mode="apply").items[0].raw_ref
    assert raw_ref and raw_ref.startswith("raw/notes/")
    planned = pipeline.plan_ingest(sandbox, raw_ref)
    assert planned.skill == "ingest-notes"
    system = next(r for r in model.requests if r.output_contract == PLAN_CONTRACT).messages[0].text
    assert system.startswith("schema") and system.endswith("Notes rules.")


def test_a_product_line_skill_adds_to_the_shared_category_rules(tmp_path: Path) -> None:
    root = _base(tmp_path)
    _skill(root, "ingest-productions", "raw/Productions", "Never invent an option code.")
    _skill(root, "ingest-vna", "raw/Productions/VNA", "List port count and frequency range.")
    _skill(root, "ingest-oscilloscope", "raw/Productions/Oscilloscope", "Bandwidth first.")
    rules = ingest_conventions(Vault(root), "raw/Productions/VNA/zna.md", "built-in")
    assert rules.skill == "ingest-productions + ingest-vna"
    shared = rules.text.index("Never invent an option code.")
    assert shared < rules.text.index("List port count")  # general before specific
    assert "Bandwidth first." not in rules.text
    assert ingest_conventions(Vault(root), "raw/Productions/x.md", "b").skill == (
        "ingest-productions"
    )


def test_answering_skills_apply_by_topic_and_ignore_other_skills(tmp_path: Path) -> None:
    from knowledge.schema import answer_rules

    root = _base(tmp_path)
    for name, front in {
        "ask-knowledge": "mode: answer\n",
        "ask-market": "mode: answer\ntopics: [市場, Market share]\n",
        "ask-legacy": "",
        "ingest-market": "mode: procedure\n",
    }.items():
        _skill(root, name, None, f"{name} rules.")
        if front:
            path = root / "skills" / name / "SKILL.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("mode: procedure\n", front),
                encoding="utf-8",
            )
    vault = Vault(root)
    names = [name for name, _ in answer_rules(vault, "5G 市場的主要客戶是誰？")]
    assert names == ["ask-knowledge", "ask-market"]
    assert [n for n, _ in answer_rules(vault, "What is the MARKET SHARE?")] == [
        "ask-knowledge",
        "ask-market",
    ]
    assert [n for n, _ in answer_rules(vault, "EVM 怎麼量？")] == ["ask-knowledge"]
