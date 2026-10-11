"""Layered bilingual index (K2, owner 2026-10-11)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from test_knowledge_sandbox import _base

from knowledge import layered_index as L
from knowledge.vault import Vault
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent


def _page(root: Path, rel: str, title: str, body: str, extra: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\ntype: concept\n{extra}---\n{body}\n", encoding="utf-8")


def _vault(tmp_path: Path) -> Vault:
    root = _base(tmp_path)
    _page(root, "wiki/concepts/EVM.md", "EVM", "EVM 是 5G NR 量測項目，用 CMX500 測。",
          "tags: [Market, 5G-NR]\n")
    _page(root, "wiki/concepts/Eye diagram.md", "Eye diagram", "示波器眼圖量測。")
    _page(root, "wiki/entities/Keysight.md", "Keysight", "Keysight 是一家 company。")
    _page(root, "wiki/sources/Deck.md", "Deck", "A deck.", "source_path: raw/Market/deck.md\n")
    return Vault(root)


class _Model:
    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        pages = [line[4:] for line in request.messages[1].text.splitlines()
                 if line.startswith("### ")]
        answer = self.answer(pages) if callable(self.answer) else self.answer
        return ModelResponse(trace=request.trace, model_alias=request.model_alias,
                             text=json.dumps(answer, ensure_ascii=False))

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _answer(pages: list[str]) -> dict[str, Any]:
    return {"pages": [{"path": p, "summary_zh": "中文摘要", "summary_en": "English summary",
                       "aliases": ["Alias A", "別名"],
                       "categories": ["product-oscilloscope", "bogus"]} for p in pages]}


def test_rules_place_pages_by_tags_title_and_opening(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    found = {e.path: set(e.categories) for e in L.LayeredIndex(vault).entries()}
    assert {"market-wireless", "product-wireless-tester"} <= found["wiki/concepts/EVM.md"]
    assert "product-oscilloscope" in found["wiki/concepts/Eye diagram.md"]
    assert "companies" in found["wiki/entities/Keysight.md"]


def test_enrich_writes_only_frontmatter_and_resumes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    body_before = L._front(vault.read("wiki/concepts/EVM.md"))[1]
    index = L.LayeredIndex(vault, _Model(_answer), "company")  # type: ignore[arg-type]
    first = index.enrich(limit=2)
    assert first.done == 2 and first.remaining > 0
    second = index.enrich(limit=100)
    assert second.remaining == 0
    assert index.enrich(limit=100).done == 0  # nothing left to do
    text = vault.read("wiki/concepts/EVM.md")
    front, body = L._front(text)
    assert body == body_before
    assert 'summary_en: "English summary"' in front and '"Alias A"' in front
    categories = L._list(front, "index_categories")
    assert "product-oscilloscope" in categories and "bogus" not in categories
    assert (vault.root / ".ingest-backup").is_dir()  # every write was backed up


def test_a_failed_model_batch_writes_nothing(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    before = vault.read("wiki/concepts/EVM.md")
    report = L.LayeredIndex(vault, _Model({"oops": 1}), "company").enrich()  # type: ignore[arg-type]
    assert report.done == 0 and report.failed_batches >= 1
    assert vault.read("wiki/concepts/EVM.md") == before


def test_build_writes_a_top_index_sub_indexes_and_keeps_the_old_list(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    old_index = vault.read("index.md")
    preview = L.LayeredIndex(vault).build()
    # The base already holds EVM.md, which _vault rewrote: four pages.
    assert preview.pages == 4 and not (vault.root / "wiki/index").exists()  # dry run
    report = L.LayeredIndex(vault).build(mode="apply")
    assert "wiki/index/sources-Market.md" in report.written
    top = vault.read("index.md")
    assert "[[Index — 示波器 / Oscilloscopes]]" in top and L.ALL_TITLE in top
    assert vault.read("wiki/index/all.md").endswith(old_index)
    oscilloscopes = vault.read("wiki/index/product-oscilloscope.md")
    assert "[[Eye diagram]]" in oscilloscopes


def test_a_long_category_becomes_a_hub_of_parts(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    for n in range(L.MAX_ENTRIES + 5):
        _page(vault.root, f"wiki/concepts/AI topic {n}.md", f"AI topic {n}", "AI server topic.",
              "tags: [AI]\n")
    report = L.LayeredIndex(vault).build(mode="apply")
    parts = [w for w in report.written if w.startswith("wiki/index/market-ai--")]
    assert len(parts) == 2
    hub = vault.read("wiki/index/market-ai.md")
    assert hub.count("[[Index — AI / AI — 概念 / Concepts") == 2
