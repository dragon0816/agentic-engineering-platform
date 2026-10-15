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
    _page(
        root,
        "wiki/concepts/EVM.md",
        "EVM",
        "EVM 是 5G NR 量測項目，用 CMX500 測。",
        "tags: [Market, 5G-NR]\n",
    )
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
        pages = [
            line[4:] for line in request.messages[1].text.splitlines() if line.startswith("### ")
        ]
        answer = self.answer(pages) if callable(self.answer) else self.answer
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text=json.dumps(answer, ensure_ascii=False),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _answer(pages: list[str]) -> dict[str, Any]:
    return {
        "pages": [
            {
                "path": p,
                "summary_zh": "中文摘要",
                "summary_en": "English summary",
                "aliases": ["Alias A", "別名"],
                "categories": ["product-oscilloscope", "bogus"],
            }
            for p in pages
        ]
    }


def test_rules_place_pages_by_tags_title_and_opening(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    found = {e.path: set(e.categories) for e in L.LayeredIndex(vault).entries()}
    assert {"market-wireless", "product-wireless-tester"} <= found["wiki/concepts/EVM.md"]
    assert "product-oscilloscope" in found["wiki/concepts/Eye diagram.md"]
    assert "companies" in found["wiki/entities/Keysight.md"]


def test_enrich_writes_only_frontmatter_and_resumes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    body_before = L._front(vault.read("wiki/concepts/EVM.md"))[1]
    index = L.LayeredIndex(vault, _Model(_answer), "company")
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
    report = L.LayeredIndex(vault, _Model({"oops": 1}), "company").enrich()
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
        _page(
            vault.root,
            f"wiki/concepts/AI topic {n}.md",
            f"AI topic {n}",
            "AI server topic.",
            "tags: [AI]\n",
        )
    report = L.LayeredIndex(vault).build(mode="apply")
    parts = [w for w in report.written if w.startswith("wiki/index/market-ai--")]
    assert len(parts) == 2
    hub = vault.read("wiki/index/market-ai.md")
    assert hub.count("[[Index — AI / AI — 概念 / Concepts") == 2


def _layered(tmp_path: Path) -> Vault:
    vault = _vault(tmp_path)
    _page(
        vault.root,
        "wiki/concepts/收發器.md",
        "收發器",
        "向量訊號收發器的吞吐量測試方法：先設定頻寬與調變方式，再量測每秒資料量與錯誤率。",
        'summary_en: "Vector signal transceiver throughput testing"\n'
        "index_categories: [product-signal-generator-analyzer]\n",
    )
    L.LayeredIndex(vault).build(mode="apply")
    return vault


def test_query_keeps_the_flat_index_and_never_cites_sub_indexes(tmp_path: Path) -> None:
    from knowledge.query import Citation, Passage, RetrievalSnapshot, _corpus, citable

    vault = _vault(tmp_path)
    (vault.root / "index.md").write_text(
        "# Index\n\n- [[EVM]] — 5G NR 量測項目\n", encoding="utf-8"
    )
    flat = RetrievalSnapshot(vault)
    flat._prepare_wiki_navigation()
    before = [(d.text, d.citation) for d in _corpus(vault)]
    L.LayeredIndex(vault).build(mode="apply")
    layered = RetrievalSnapshot(vault)
    layered._prepare_wiki_navigation()
    # Navigation still ranks the previous flat list, now kept in wiki/index/all.md.
    assert (
        [d.text for d in layered._index_docs]
        == [d.text for d in flat._index_docs]
        == ["- [[EVM]] — 5G NR 量測項目"]
    )
    # The sub-index pages add nothing to the evidence corpus.
    assert [(d.text, d.citation) for d in _corpus(vault)] == before
    assert not any(L.is_navigation(rel) for rel in layered.wiki_titles())
    found = layered.search_wiki_pages("Oscilloscopes 示波器 index", exclude=set())
    assert not any(L.is_navigation(p.citation.wiki_page) for p in found)
    sub_index = Passage(
        text="x", score=0, citation=Citation(kind="wiki", wiki_page="wiki/index/companies.md")
    )
    assert not citable(sub_index, allow_wiki=True)


def test_ingest_relevance_reads_only_the_chosen_categories(tmp_path: Path) -> None:
    from test_planning import PlanningModel, document, good_plan_json

    from knowledge.planning import (
        CATEGORY_CONTRACT,
        PLAN_CONTRACT,
        RELEVANCE_CONTRACT,
        IngestPlanner,
    )

    vault = _layered(tmp_path)
    oscilloscopes = "Index — " + L.category_title("product-oscilloscope")
    model = PlanningModel(
        {
            CATEGORY_CONTRACT: {"categories": [oscilloscopes, "not a category"]},
            RELEVANCE_CONTRACT: {
                "relevant": ["wiki/concepts/Eye diagram.md", "wiki/entities/Keysight.md"]
            },
            PLAN_CONTRACT: good_plan_json(),
        }
    )
    outcome = IngestPlanner(model, vault, alias="planner").plan(document(), today="2026-10-11")
    categories, relevance = model.requests[0], model.requests[1]
    assert categories.output_contract == CATEGORY_CONTRACT
    assert oscilloscopes in categories.messages[1].text
    shown = relevance.messages[1].text
    assert "- wiki/concepts/Eye diagram.md — [[Eye diagram]]" in shown
    assert "Keysight" not in shown.split("===== source")[0]
    # Only a page the chosen categories offered can be read.
    assert outcome.relevant == ("wiki/concepts/Eye diagram.md",)


def test_a_flat_index_keeps_the_single_relevance_pass(tmp_path: Path) -> None:
    from test_planning import PlanningModel, document, good_plan_json

    from knowledge.planning import PLAN_CONTRACT, RELEVANCE_CONTRACT, IngestPlanner

    vault = _vault(tmp_path)
    model = PlanningModel({RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: good_plan_json()})
    IngestPlanner(model, vault, alias="planner").plan(document(), today="2026-10-11")
    assert model.requests[0].output_contract == RELEVANCE_CONTRACT
    assert "- wiki/entities/Keysight.md — Keysight" in model.requests[0].messages[1].text
