"""Three-way merge of a sandbox into its published vault (K3.3, owner 2026-10-11)."""

from pathlib import Path

import pytest
from test_knowledge_pipeline import _pipeline
from test_knowledge_sandbox import _snapshot

from knowledge.merge import merge_page, three_way
from knowledge.pipeline import KnowledgePipeline, PipelineError

PAGE = """---
title: CMX500
updated: 2026-01-01
---
CMX500 是 5G 綜合測試儀。

## 規格

- 頻率到 8 GHz，見 [[Datasheet]]

## Option

- K100，見 [[Datasheet]]
"""


def _edit(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new, 1)


def test_different_sections_merge_and_the_same_section_conflicts() -> None:
    a = _edit(
        PAGE, "- 頻率到 8 GHz，見 [[Datasheet]]", "- 頻率到 8 GHz，見 [[Datasheet]]\n- 頻寬 400 MHz"
    )
    b = _edit(
        _edit(PAGE, "- K100，見 [[Datasheet]]", "- K100，見 [[Datasheet]]\n- K200"),
        "updated: 2026-01-01",
        "updated: 2026-10-11",
    )
    text, parts, conflicts = merge_page("p.md", PAGE, a, b, {})
    assert conflicts == [] and parts == ["規格"]
    assert "- 頻寬 400 MHz" in text and "- K200" in text and "updated: 2026-10-11" in text
    c = _edit(PAGE, "- 頻率到 8 GHz，見 [[Datasheet]]", "- 頻率到 6 GHz，見 [[Datasheet]]")
    _, _, conflicts = merge_page("p.md", PAGE, a, c, {})
    assert [(x.part, x.published) for x in conflicts] == [
        ("規格", "## 規格\n\n- 頻率到 6 GHz，見 [[Datasheet]]\n")
    ]
    text, parts, conflicts = merge_page("p.md", PAGE, a, c, {"p.md#規格": "sandbox"})
    assert conflicts == [] and "頻寬 400 MHz" in text and "6 GHz" not in text


def test_new_pages_raw_index_and_log_are_unions() -> None:
    base = {
        "wiki/a.md": b"A\n",
        "index.md": b"# Index\n\n## Concepts\n- [[A]]\n",
        "log.md": b"# Log\n",
    }
    published = {
        **base,
        "raw/x.md": b"x",
        "index.md": b"# Index\n\n## Concepts\n- [[A]]\n- [[P]]\n",
        "log.md": b"# Log\n## [2026-10-02] ingest | P\n",
    }
    sandbox = {
        **base,
        "raw/y.md": b"y",
        "wiki/b.md": b"B\n",
        "index.md": b"# Index\n\n## Concepts\n- [[A]]\n- [[B]]\n",
        "log.md": b"# Log\n## [2026-10-03] ingest | B\n",
    }
    merged = three_way(base, sandbox, published)
    assert merged.conflicts == []
    assert merged.files["raw/y.md"] == b"y" and merged.files["wiki/b.md"] == b"B\n"
    assert merged.files["index.md"].decode() == (
        "# Index\n\n## Concepts\n- [[A]]\n- [[P]]\n- [[B]]\n"
    )
    assert merged.files["log.md"].decode().endswith("| P\n## [2026-10-03] ingest | B\n")
    # Raw is immutable: the same path with other bytes is a conflict, never a write.
    clash = three_way(base, {**sandbox, "raw/x.md": b"other"}, published)
    assert [c.key for c in clash.conflicts] == ["raw/x.md#page"]


def _two_sandboxes(tmp_path: Path) -> tuple[KnowledgePipeline, Path, str]:
    pipeline, base = _pipeline(tmp_path)
    (base / "wiki/entities").mkdir(parents=True)
    (base / "wiki/entities/CMX500.md").write_text(PAGE, encoding="utf-8")
    sandbox = pipeline.create_sandbox("k-test", "vna", "leo.chi")
    return pipeline, base, sandbox.sandbox_id


def test_a_sandbox_merges_into_a_new_candidate_after_published_moved(tmp_path: Path) -> None:
    pipeline, base, sandbox = _two_sandboxes(tmp_path)
    root = pipeline.sandboxes.open(sandbox)[1].root
    page = root / "wiki/entities/CMX500.md"
    page.write_text(
        _edit(
            PAGE,
            "- 頻率到 8 GHz，見 [[Datasheet]]",
            "- 頻率到 8 GHz，見 [[Datasheet]]\n- 頻寬 400 MHz",
        ),
        encoding="utf-8",
    )
    # Another sandbox's change to a different section was published meanwhile.
    published_page = base / "wiki/entities/CMX500.md"
    published_page.write_text(
        _edit(PAGE, "- K100，見 [[Datasheet]]", "- K100，見 [[Datasheet]]\n- K200"),
        encoding="utf-8",
    )
    before = _snapshot(base)
    preview = pipeline.merge(sandbox)
    assert preview.conflicts == () and [c.path for c in preview.changes] == [
        "wiki/entities/CMX500.md"
    ]
    applied = pipeline.merge(sandbox, mode="apply")
    assert _snapshot(base) == before  # the published vault is never edited
    assert applied.candidate_root and applied.lost_sourced_lines == 0
    merged = (Path(applied.candidate_root) / "wiki/entities/CMX500.md").read_text(encoding="utf-8")
    assert "- 頻寬 400 MHz" in merged and "- K200" in merged


def test_a_conflict_blocks_apply_until_it_is_resolved(tmp_path: Path) -> None:
    pipeline, base, sandbox = _two_sandboxes(tmp_path)
    root = pipeline.sandboxes.open(sandbox)[1].root
    (root / "wiki/entities/CMX500.md").write_text(
        _edit(PAGE, "8 GHz，見", "7.5 GHz，見"), encoding="utf-8"
    )
    (base / "wiki/entities/CMX500.md").write_text(
        _edit(PAGE, "8 GHz，見", "6 GHz，見"), encoding="utf-8"
    )
    preview = pipeline.merge(sandbox)
    assert [c.key for c in preview.conflicts] == ["wiki/entities/CMX500.md#規格"]
    with pytest.raises(PipelineError, match="unresolved_conflicts"):
        pipeline.merge(sandbox, mode="apply")
    applied = pipeline.merge(
        sandbox, mode="apply", resolutions={"wiki/entities/CMX500.md#規格": "published"}
    )
    assert applied.candidate_root
    merged = (Path(applied.candidate_root) / "wiki/entities/CMX500.md").read_text(encoding="utf-8")
    assert "6 GHz" in merged and "7.5 GHz" not in merged


def test_out_of_domain_changes_are_proposals(tmp_path: Path) -> None:
    pipeline, base = _pipeline(tmp_path)
    info = pipeline.create_sandbox("k-test", "vna", "leo.chi", domain="product-vna")
    root = pipeline.sandboxes.open(info.sandbox_id)[1].root
    (root / "wiki/concepts/S-parameter.md").write_text(
        "---\ntitle: S-parameter\nindex_categories: [product-vna]\n---\nVNA 量測 S 參數。\n",
        encoding="utf-8",
    )
    (root / "wiki/concepts/EVM.md").write_text("---\ntitle: EVM\n---\nEVM 更新\n", encoding="utf-8")
    changes = {c.path: c.proposal for c in pipeline.merge(info.sandbox_id).changes}
    assert changes == {"wiki/concepts/S-parameter.md": False, "wiki/concepts/EVM.md": True}
    with pytest.raises(PipelineError, match="unknown_domain"):
        pipeline.create_sandbox("k-test", "x", "a", domain="nope")


def test_schema_and_category_rules_merge_like_pages(tmp_path: Path) -> None:
    pipeline, base = _pipeline(tmp_path)
    sandbox = pipeline.create_sandbox("k-test", "rules", "leo.chi").sandbox_id
    root = pipeline.sandboxes.open(sandbox)[1].root
    (root / "CLAUDE.md").write_text("schema\n\n## 語言慣例\n\n- 雙語別名\n", encoding="utf-8")
    (root / "skills/ingest-market").mkdir(parents=True)
    (root / "skills/ingest-market/SKILL.md").write_text(
        "---\nname: ingest-market\napplies_to: raw/Market\n---\n每條說法要有日期。\n",
        encoding="utf-8",
    )
    applied = pipeline.merge(sandbox, mode="apply")
    assert {c.path for c in applied.changes} == {"CLAUDE.md", "skills/ingest-market/SKILL.md"}
    assert applied.candidate_root
    candidate = Path(applied.candidate_root)
    assert "雙語別名" in (candidate / "CLAUDE.md").read_text(encoding="utf-8")
    assert (candidate / "skills/ingest-market/SKILL.md").is_file()


def test_a_merged_windows_page_keeps_its_line_endings() -> None:
    a = _edit(
        PAGE, "- 頻率到 8 GHz，見 [[Datasheet]]", "- 頻率到 8 GHz，見 [[Datasheet]]\n- 頻寬 400 MHz"
    )
    b = _edit(PAGE, "- K100，見 [[Datasheet]]", "- K100，見 [[Datasheet]]\n- K200")
    crlf = {"wiki/p.md": b.replace("\n", "\r\n").encode("utf-8")}
    merged = three_way({"wiki/p.md": PAGE.encode("utf-8")}, {"wiki/p.md": a.encode("utf-8")}, crlf)
    text = merged.files["wiki/p.md"].decode("utf-8")
    assert "- K200\r\n" in text and text.count("\r\n") == text.count("\n")
