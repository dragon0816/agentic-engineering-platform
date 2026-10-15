"""Every nonempty combination keeps source coverage separate from inference."""

import itertools
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from test_raw import make_vault

from common.assets import AssetIdentity
from common.execution import TraceIdentifiers
from host_runtime.knowledge_observation import KnowledgeBridgeActions
from knowledge.evidence import (
    _diverse_passages,
    answer_claims_overlap_raw,
    answer_concerns_subject,
    assess_knowledge_evidence,
    evidence_excerpt,
    extractive_observation_answer,
    extractive_relation_answer,
    omit_unsupported_product_recommendations,
    omit_unverified_answer_lines,
    passage_number,
    unsupported_product_recommendations,
)
from knowledge.evolution import grounded_record
from knowledge.procedure import KnowledgeProcedure
from knowledge.query import Answer, Citation, Passage, RetrievalSnapshot, retrieve, retrieve_batch
from knowledge.raw import RawDocument, RawSection, render, source_for
from knowledge.vault import Vault

NAMES = ("market_trend", "product_option_spec", "technical_knowledge", "competitor")
WORDS = ("market", "product", "technical", "competitor")
TEXTS = (
    "CMP180 wireless market demand for production testing is increasing.",
    "CMP180 product option K123 has a specification for production testing.",
    "CMP180 technical test method uses signaling measurement.",
    "CMP180 competitor Keysight has a different test platform.",
)
LINK = (
    "CMP180 product option supports wireless market demand for technical "
    "test requirements compared with competitor Keysight."
)


def _procedure() -> KnowledgeProcedure:
    path = Path(__file__).parent / "fixtures/harness_skills/knowledge-evidence-v1.2.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return KnowledgeProcedure.model_validate(payload["procedure"])


def _guided_procedure() -> KnowledgeProcedure:
    path = Path(__file__).parent / "fixtures/harness_skills/knowledge-evidence-v1.3.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return KnowledgeProcedure.model_validate(payload["procedure"])


def _write(vault: Vault, name: str, value: str) -> None:
    raw_ref = f"raw/{name}.md"
    source = source_for(value.encode(), f"drop/{name}.txt").model_copy(update={"raw_ref": raw_ref})
    vault.write_raw(
        raw_ref,
        render(
            RawDocument(
                source=source,
                extractor="txt.v1",
                created=date(2026, 10, 4),
                sections=(RawSection(text=value),),
            )
        ),
    )


def test_chinese_ntn_question_uses_market_focus_and_product_link(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    _write(
        vault,
        "ntn-cmx500",
        "The Rohde & Schwarz CMX500 tester is tailored for NTN testing applications.",
    )
    question = "在NTN 的市場，rohde-schwarz有那些產品可以推給客戶"
    procedure = _guided_procedure()
    assert procedure.synthesis_max_output_tokens == 3072
    assert procedure.focus(question) is not None
    assessment = assess_knowledge_evidence(vault, question, procedure)
    assert tuple(item.name for item in assessment.observations) == (
        "market_segment",
        "product_option_spec",
    )
    assert assessment.status == "covered"
    assert assessment.relation_passages
    fallback = extractive_relation_answer(question, assessment, procedure)
    assert fallback is not None
    assert "CMX500" in fallback.text
    assert answer_claims_overlap_raw(fallback)
    observed = extractive_observation_answer(question, assessment, procedure)
    assert observed is not None
    assert "CMX500" in observed.text
    assert grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="ntn", request_id="ntn", span_id="answer"),
        observed,
        assessment=assessment.summary(),
    ).cited_passages


def test_ntn_recommendation_requires_product_use_case_not_reseller_market_list() -> None:
    question = "在NTN 的市場，rohde-schwarz有那些產品可以推給客戶"
    passages = (
        Passage(
            text="CMX500 supports NR-NTN device testing in callbox mode.",
            citation=Citation(kind="raw", raw_ref="raw/Productions/cmx.md", section=1),
            score=1,
        ),
        Passage(
            text=(
                "R&S OSP200 and OSP300 Open switch and control platforms\n"
                "Target Markets: O-RAN; NTN; and 6G"
            ),
            citation=Citation(kind="raw", raw_ref="raw/Market/reseller.md", section=2),
            score=1,
        ),
    )
    answer = Answer(
        question=question,
        status="answered",
        passages=passages,
        text=(
            "建議 CMX500 用於 NTN 裝置測試 [1]。\n可推 OSP200 / OSP300，因為目標市場列有 NTN [2]。"
        ),
    )
    procedure = _guided_procedure()
    assert len(unsupported_product_recommendations(answer, question, procedure)) == 1
    filtered = omit_unsupported_product_recommendations(answer, question, procedure)
    assert "CMX500" in filtered.text
    assert "OSP200" not in filtered.text
    assert not unsupported_product_recommendations(filtered, question, procedure)
    assert answer_claims_overlap_raw(filtered)


def test_ntn_recommendation_accepts_adjacent_source_context_for_pvt360() -> None:
    question = "在NTN 的市場，rohde-schwarz有那些產品可以推給客戶"
    answer = Answer(
        question=question,
        status="answered",
        passages=(
            Passage(
                text=(
                    "With the introduction of NTN, test methodologies for satellites will change. "
                    "LEO satellites may be produced in large quantities, "
                    "requiring a production test concept. "
                    "The R&S PVT360 performance vector tester combines a vector signal generator "
                    "and vector spectrum analyzer for satellite production testing."
                ),
                citation=Citation(kind="raw", raw_ref="raw/Knowledge/ntn-whitepaper.md", section=1),
                score=1,
            ),
        ),
        text="可推 PVT360 用於 NTN 衛星量產測試。[1]",
    )
    assert unsupported_product_recommendations(answer, question, _guided_procedure()) == ()


def test_ntn_recommendation_reads_pdf_hard_wrapped_context() -> None:
    question = "在NTN 的市場，rohde-schwarz有那些產品可以推給客戶"
    answer = Answer(
        question=question,
        status="answered",
        passages=(
            Passage(
                text=(
                    "8.2.4 Production testing aspects for satellites\n"
                    "With the introduction of NTN, we also expect some changes in the overall test "
                    "methodologies for satellites. Especially\n"
                    "LEO and VLEO satellites might be produced in large quantities, making a novel "
                    "production test\n"
                    "concept imperative. With the R&S®PVT360 performance vector tester, Rohde & "
                    "Schwarz introduces a combined vec-\n"
                    "tor signal generator and vector spectrum analyzer in a single box."
                ),
                citation=Citation(
                    kind="raw", raw_ref="raw/Knowledge/satellite-paper.md", section=200
                ),
                score=1,
            ),
        ),
        text="可推 PVT360 用於衛星量產測試。[1]",
    )
    assert unsupported_product_recommendations(answer, question, _guided_procedure()) == ()


def test_ntn_recommendation_accepts_focused_document_but_not_unrelated_title() -> None:
    question = "在NTN 的市場，rohde-schwarz有那些產品可以推給客戶"
    caption = (
        "Figure 151: Vertical CATR for RX testing with the R&S ZNA and 3D positioner\n"
        "Indirect far field (IFF): R&S ATS1800C"
    )

    def answer_for(raw_ref: str) -> Answer:
        return Answer(
            question=question,
            status="answered",
            passages=(
                Passage(
                    text=caption,
                    citation=Citation(kind="raw", raw_ref=raw_ref, section=218),
                    score=1,
                ),
            ),
            text="可推 ATS1800C 搭配 ZNA 做 RX 測試。[1]",
        )

    procedure = _guided_procedure()
    focused = answer_for("raw/Knowledge/5G-NTN-takes-flight-A-deep-dive_wp_en.md")
    unrelated = answer_for("raw/Productions/ATS1800C_brochure_en.md")
    assert unsupported_product_recommendations(focused, question, procedure) == ()
    assert len(unsupported_product_recommendations(unrelated, question, procedure)) == 1


def test_product_evidence_budget_keeps_distinct_instrument_roles() -> None:
    passages = tuple(
        Passage(
            text=f"CMX500 PR says NTN test solution number {index}.",
            citation=Citation(kind="raw", raw_ref=f"raw/Productions/PR/cmx-{index}.md", section=1),
            score=1,
        )
        for index in range(6)
    ) + (
        Passage(
            text="SMW200A and FSW form an NTN satellite component test setup.",
            citation=Citation(kind="raw", raw_ref="raw/Knowledge/ntn-whitepaper.md", section=1),
            score=1,
        ),
        Passage(
            text="CMX500 supports NTN device testing in callbox mode.",
            citation=Citation(kind="raw", raw_ref="raw/Productions/cmx-features.md", section=1),
            score=1,
        ),
    )
    selected = _diverse_passages(
        passages,
        limit=2,
        entity_pattern=_guided_procedure().facets[2].entity_pattern,
    )
    assert {item.citation.raw_ref for item in selected} == {
        "raw/Knowledge/ntn-whitepaper.md",
        "raw/Productions/cmx-features.md",
    }


def test_guided_product_search_follows_selected_source_to_direct_use_case(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    raw_ref = "raw/Knowledge/ntn-whitepaper.md"
    sections = (
        RawSection(text="NTN test solution portfolio includes SMW200A and FSW."),
        RawSection(text="SMW200A can emulate NTN satellite channels for RF testing."),
    )
    source = source_for(b"ntn-whitepaper", "drop/ntn-whitepaper.txt").model_copy(
        update={"raw_ref": raw_ref}
    )
    vault.write_raw(
        raw_ref,
        render(
            RawDocument(
                source=source,
                extractor="txt.v1",
                created=date(2026, 10, 4),
                sections=sections,
            )
        ),
    )
    snapshot = RetrievalSnapshot(vault)
    direct = snapshot.source_section(
        raw_ref,
        matches_sentence=lambda sentence: (
            "SMW200A" in sentence and "NTN" in sentence and "channels" in sentence
        ),
    )
    assert direct is not None
    assert direct.citation.section == 2
    assert snapshot.source_neighbors(raw_ref, 1)[0].citation.section == 2

    assessment = assess_knowledge_evidence(
        vault,
        "在NTN 的市場，rohde-schwarz有那些產品可以推給客戶",
        _guided_procedure(),
        snapshot=snapshot,
    )
    product = next(item for item in assessment.observations if item.name == "product_option_spec")
    assert any(
        passage.citation.raw_ref == raw_ref and passage.citation.section == 2
        for passage in product.passages
    )
    assert any(passage.citation.raw_ref == raw_ref for passage in assessment.context_passages)


def test_citation_only_line_is_not_a_supported_claim() -> None:
    passage = Passage(
        text="CMX500 supports NTN device testing.",
        citation=Citation(kind="raw", raw_ref="raw/Productions/cmx.md", section=1),
        score=1,
    )
    answer = Answer(
        question="NTN products",
        status="answered",
        passages=(passage,),
        text="CMX500 supports NTN testing [1].\n[1]",
    )
    assert not answer_claims_overlap_raw(answer)


def test_partial_model_answer_keeps_only_independently_supported_lines() -> None:
    passage = Passage(
        text="CMX500 supports NTN device testing in callbox mode.",
        citation=Citation(kind="raw", raw_ref="raw/Productions/cmx.md", section=1),
        score=1,
    )
    answer = Answer(
        question="NTN products",
        status="answered",
        passages=(passage,),
        text=(
            "CMX500 supports NTN device testing [1].\nCMX500 includes an unlisted K999 option [1]."
        ),
    )
    filtered = omit_unverified_answer_lines(answer)
    assert filtered.status == "answered"
    assert filtered.text == "CMX500 supports NTN device testing [1]."


def test_skill_evidence_redacts_credential_like_source_text_before_record(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    _write(
        vault,
        "source-with-example-header",
        "CMP180 product option K123 supports wireless market demand. "
        "Example header: Bearer sample-token",
    )
    assessment = assess_knowledge_evidence(vault, "CMP180 market product", _procedure())
    assert assessment.status == "covered"
    assert any("[redacted]" in item.text for item in assessment.selected_passages())
    assert all("sample-token" not in item.text for item in assessment.selected_passages())
    fallback = extractive_relation_answer("CMP180 market product", assessment, _procedure())
    assert fallback is not None
    assert grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="secret-test", request_id="secret-test", span_id="answer"),
        fallback,
        assessment=assessment.summary(),
    ).cited_passages


def test_open_ended_ntn_product_search_keeps_distinct_instruments(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    _write(
        vault,
        "cmx500-ntn",
        "CMX500 tester is a Rohde Schwarz NTN signaling solution.",
    )
    _write(
        vault,
        "smbv100b-ntn",
        "SMBV100B signal generator is a Rohde Schwarz NTN channel emulation solution.",
    )
    assessment = assess_knowledge_evidence(
        vault, "在 NTN 市場有哪些產品可以推給客戶", _guided_procedure()
    )
    product = next(item for item in assessment.observations if item.name == "product_option_spec")
    assert {passage.citation.raw_ref for passage in product.passages} == {
        "raw/cmx500-ntn.md",
        "raw/smbv100b-ntn.md",
    }


def test_passage_number_ignores_query_specific_retrieval_score() -> None:
    first = Passage(
        text="CMP180 product option K123 specification.",
        citation=Citation(kind="raw", raw_ref="raw/spec.md", section=1),
        score=1.0,
    )
    same_source = first.model_copy(update={"score": 7.0})
    assert first != same_source
    assert passage_number((first,), same_source) == 1


def test_wiki_index_navigates_to_linked_raw_before_global_search(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    _write(vault, "cmp-spec", "The option KM352 enables 320 MHz WLAN measurements.")
    _write(vault, "generic", "CMP180 option testing production radio tester.")
    (vault.root / "index.md").write_text(
        "# Index\n- [[CMP180]] — CMP180 WLAN options and production testing.\n",
        encoding="utf-8",
    )
    (vault.root / "wiki" / "entities").mkdir(parents=True)
    (vault.root / "wiki" / "sources").mkdir(parents=True)
    (vault.root / "wiki" / "entities" / "CMP180.md").write_text(
        "---\ntitle: CMP180\n---\nSee [[CMP specs]] for WLAN options.\n",
        encoding="utf-8",
    )
    (vault.root / "wiki" / "sources" / "CMP specs.md").write_text(
        "---\ntitle: CMP specs\nsource_path: raw/cmp-spec.md\n---\n"
        "The source lists WLAN options.\n",
        encoding="utf-8",
    )
    snapshot = RetrievalSnapshot(vault)
    result = snapshot.wiki_guided_batch(("CMP180 option",), k=2, min_raw=2)[0]
    assert result[0].citation.raw_ref == "raw/cmp-spec.md"
    assert result[0].citation.kind == "raw"
    assert any(passage.citation.raw_ref == "raw/generic.md" for passage in result)
    filtered = snapshot.matching_wiki_sources(
        "CMP180 option",
        accepts=lambda passage: "KM352" in passage.text,
    )
    assert [passage.citation.raw_ref for passage in filtered] == ["raw/cmp-spec.md"]
    context = snapshot.wiki_index_context("CMP180 option")
    assert context
    assert all(passage.citation.kind == "wiki" for passage in context)
    assert any("WLAN options" in passage.text for passage in context)


def test_market_facet_ignores_navigation_url_words(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    _write(
        vault,
        "navigation",
        "CMP180 [5G NR](https://example.test/market-segment/wireless-communications/5g)",
    )
    _write(
        vault,
        "Market/real-market",
        "The wireless market demand for Wi-Fi 7 production testing is growing.",
    )
    assessment = assess_knowledge_evidence(
        vault, "CMP180 wireless market trend", _guided_procedure()
    )
    market = next(item for item in assessment.observations if item.name == "market_trend")
    assert market.passages
    assert all(item.citation.raw_ref != "raw/navigation.md" for item in market.passages)


def test_market_facet_can_find_eligible_raw_below_unrelated_top_hits(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    for index in range(18):
        _write(
            vault,
            f"Productions/distractor-{index}",
            "Wireless communications market testing demand trend option summary.",
        )
    _write(
        vault,
        "Market/real-trend",
        "Wireless market demand for production testing is growing in 2026.",
    )
    assessment = assess_knowledge_evidence(vault, "wireless market trend", _guided_procedure())
    market = next(item for item in assessment.observations if item.name == "market_trend")
    assert any(
        passage.citation.raw_ref == "raw/Market/real-trend.md" for passage in market.passages
    )


def test_evidence_excerpt_skips_markdown_navigation() -> None:
    text = (
        "[5G NR](https://example.test/market-segment/wireless)\n"
        "CMP180 supports production testing with 500 MHz bandwidth.\n"
        "[Contact](https://example.test/contact)"
    )
    excerpt = evidence_excerpt(text, subject="CMP180", terms=("testing", "bandwidth"))
    assert excerpt == "CMP180 supports production testing with 500 MHz bandwidth."


def test_option_excerpt_prefers_option_statement_over_generic_product_line() -> None:
    excerpt = evidence_excerpt(
        "CMP180 is a wireless tester for production testing.\n"
        "Option CMP-KM310 enables Bluetooth measurement on CMP180.",
        subject="CMP180",
        terms=("tester", "option"),
        priority_patterns=(r"\boption\b",),
    )
    assert excerpt == "Option CMP-KM310 enables Bluetooth measurement on CMP180."


def test_guided_market_and_option_require_the_requested_evidence(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    _write(vault, "leader", "Bluetest is a market leader in wireless equipment testing.")
    _write(vault, "Market/trend", "Wireless market demand for Wi-Fi 7 testing is growing.")
    _write(vault, "product", "CMP180 is a wireless tester for production testing.")
    _write(vault, "option", "Option CMP-KM352 supports CMP180 WLAN IEEE 802.11be.")
    assessment = assess_knowledge_evidence(
        vault, "CMP180 wireless market trend and product option", _guided_procedure()
    )
    observations = {item.name: item for item in assessment.observations}
    assert all(
        item.citation.raw_ref != "raw/leader.md" for item in observations["market_trend"].passages
    )
    assert all(
        item.citation.raw_ref != "raw/product.md"
        for item in observations["product_option_spec"].passages
    )
    assert any(
        item.citation.raw_ref == "raw/option.md"
        for item in observations["product_option_spec"].passages
    )


def test_other_product_relationship_cannot_validate_named_product(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    _write(
        vault,
        "cmx-market",
        "Growing Wi-Fi 7 demand supports the CMX500 tester with WLAN option K352.",
    )
    _write(
        vault,
        "cmp-option",
        "Option CMP-KM352 provides CMP180 WLAN IEEE 802.11be measurements.",
    )
    assessment = assess_knowledge_evidence(
        vault,
        "CMP180 wireless market trend and product option",
        _guided_procedure(),
    )
    assert assessment.status == "missing"
    assert not any(
        relation.left == "market_trend" and relation.right == "product_option_spec"
        for relation in assessment.relations
    )


def test_competitor_facet_needs_subject_comparison_not_battlecard_mention(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    _write(
        vault,
        "cmx-battlecard",
        "CMX500 versus Amarisoft supports NTN signaling.\nProduction Testing: CMP180/200/CMW100.",
    )
    assessment = assess_knowledge_evidence(
        vault, "CMP180 product competitor comparison", _guided_procedure()
    )
    assert "competitor" in assessment.missing_facets


def _combinations() -> list[tuple[int, ...]]:
    return [subset for size in range(1, 5) for subset in itertools.combinations(range(4), size)]


@pytest.mark.parametrize("subset", _combinations())
def test_all_15_facet_subsets_accept_direct_raw_support(
    tmp_path: Path, subset: tuple[int, ...]
) -> None:
    vault = make_vault(tmp_path)
    for index in subset:
        _write(vault, NAMES[index], TEXTS[index])
    if len(subset) > 1:
        _write(vault, "direct-link", LINK)
    question = "CMP180 " + " ".join(WORDS[index] for index in subset)
    result = assess_knowledge_evidence(vault, question, _procedure())
    assert tuple(item.name for item in result.observations) == tuple(NAMES[i] for i in subset)
    assert result.status == "covered"
    assert result.missing_facets == ()
    assert all(item.passages for item in result.observations)
    assert not result.relation_required or result.relation_passages


@pytest.mark.parametrize("subset", _combinations())
def test_all_15_facet_subsets_report_the_absent_source(
    tmp_path: Path, subset: tuple[int, ...]
) -> None:
    vault = make_vault(tmp_path)
    for index in subset[:-1]:
        _write(vault, NAMES[index], TEXTS[index])
    question = "CMP180 " + " ".join(WORDS[index] for index in subset)
    result = assess_knowledge_evidence(vault, question, _procedure())
    assert result.status == "missing"
    assert NAMES[subset[-1]] in result.missing_facets


@pytest.mark.parametrize("subset", [item for item in _combinations() if len(item) > 1])
def test_combined_facets_reject_unlinked_co_mentions(
    tmp_path: Path, subset: tuple[int, ...]
) -> None:
    vault = make_vault(tmp_path)
    _write(vault, "co-mentions", " ".join(TEXTS[index] for index in subset))
    question = "CMP180 " + " ".join(WORDS[index] for index in subset)
    result = assess_knowledge_evidence(vault, question, _procedure())
    assert result.status == "missing"
    assert result.relation_required is True
    assert result.relation_passages == ()


def test_batch_retrieval_preserves_single_query_ranking(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    _write(vault, "market", TEXTS[0])
    _write(vault, "product", TEXTS[1])
    queries = ("CMP180 market", "CMP180 product")
    batched = retrieve_batch(vault, queries, k=4, min_raw=4)
    assert batched == tuple(retrieve(vault, item, k=4, min_raw=4) for item in queries)


def test_host_overlap_rejects_unrelated_claim_and_unseen_number() -> None:
    passage = Passage(
        text="CMP180 product option supports wireless market demand in production.",
        citation=Citation(kind="raw", raw_ref="raw/link.md", section=1),
        score=1,
    )
    assert answer_claims_overlap_raw(
        Answer(
            question="CMP180 market product",
            status="answered",
            passages=(passage,),
            text="CMP180 product option supports wireless market demand [1].",
        )
    )
    assert not answer_claims_overlap_raw(
        Answer(
            question="CMP180 market product",
            status="answered",
            passages=(passage,),
            text="Safe mode requires firmware 2.0 [1].",
        )
    )
    assert not answer_claims_overlap_raw(
        Answer(
            question="CMP180 market product",
            status="answered",
            passages=(passage,),
            text="CMP180 product option supports 9.9 Gbps wireless market demand [1].",
        )
    )


def test_host_overlap_reads_numbers_next_to_cjk_text() -> None:
    passage = Passage(
        text="台灣無線通訊代工製造產業在2026年呈現結構性成長，受惠於Wi-Fi 7規格紅利。",
        citation=Citation(kind="raw", raw_ref="raw/Market/report.md", section=44),
        score=1,
    )

    def answer(text: str) -> Answer:
        return Answer(
            question="無線通訊市場趨勢",
            status="answered",
            passages=(passage,),
            text=text,
        )

    assert answer_claims_overlap_raw(
        answer("台灣無線通訊代工製造產業在 2026 年呈現結構性成長，受惠於 Wi-Fi 7 規格紅利 [1]。")
    )
    assert not answer_claims_overlap_raw(
        answer("台灣無線通訊代工製造產業在2027年呈現結構性成長 [1]。")
    )


def test_host_rejects_answer_about_other_product_even_with_raw_overlap() -> None:
    passage = Passage(
        text="CMP180 and CMX500 both have product options for wireless testing.",
        citation=Citation(kind="raw", raw_ref="raw/products.md", section=1),
        score=1,
    )
    answer = Answer(
        question="CMP180 product option",
        status="answered",
        passages=(passage,),
        text="CMX500 has product options for wireless testing [1].",
    )
    assert answer_claims_overlap_raw(answer)
    record = grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="subject-test", request_id="subject-test", span_id="answer"),
        answer,
    )
    actions = KnowledgeBridgeActions(
        lambda: {},
        required_evidence=("raw_citations",),
        required_facets=("product_option_spec",),
        required_subject="CMP180",
    )
    actions.result = {"ok": True, "record": record.model_dump(mode="json")}
    claim = next(check for check in actions.validate() if check.check_id == "claim_support")
    assert claim.status == "failed"


def test_host_accepts_option_claim_cited_from_the_subject_product_document() -> None:
    passage = Passage(
        text="Option R&S CMP-KM351 is required to measure 802.11ax signals.",
        citation=Citation(kind="raw", raw_ref="raw/Productions/CMP180_specs_en.md", section=165),
        score=1,
    )
    answer = Answer(
        question="CMP180 product option",
        status="answered",
        passages=(passage,),
        text="R&S CMP-KM351 option is required to measure 802.11ax signals [1].",
    )
    record = grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="subject-doc", request_id="subject-doc", span_id="answer"),
        answer,
    )
    actions = KnowledgeBridgeActions(
        lambda: {},
        required_evidence=("raw_citations",),
        required_facets=("product_option_spec",),
        required_subject="CMP180",
    )
    actions.result = {"ok": True, "record": record.model_dump(mode="json")}
    claim = next(check for check in actions.validate() if check.check_id == "claim_support")
    assert claim.status == "passed"


def test_only_missing_facet_receives_second_skill_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from knowledge.query import RetrievalSnapshot

    vault = make_vault(tmp_path)
    _write(vault, "market", TEXTS[0])
    _write(vault, "product", TEXTS[1])
    payload = _procedure().model_dump(mode="json")
    payload["facets"][1]["search_queries"] = ["no-such-source-term", "product option"]
    payload["facets"][1]["include_subject"] = False
    procedure = KnowledgeProcedure.model_validate(payload)
    calls: list[tuple[str, ...]] = []

    class RecordingSnapshot(RetrievalSnapshot):
        def batch(
            self, queries: tuple[str, ...], *, k: int, min_raw: int = 0
        ) -> tuple[tuple[Passage, ...], ...]:
            calls.append(queries)
            return super().batch(queries, k=k, min_raw=min_raw)

    monkeypatch.setattr("knowledge.evidence.RetrievalSnapshot", RecordingSnapshot)
    result = assess_knowledge_evidence(vault, "CMP180 market product", procedure)
    assert result.status == "missing"  # no direct relationship source
    assert result.missing_facets == ()
    assert [item.attempts for item in result.observations] == [1, 2]
    assert calls[1] == ("product option",)


def test_cited_direct_link_can_support_both_connected_facets(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    _write(vault, "product", TEXTS[1])
    _write(vault, "technical", TEXTS[2])
    _write(vault, "link", LINK)
    assessment = assess_knowledge_evidence(vault, "CMP180 product technical", _procedure())
    assert assessment.status == "covered"
    passages = assessment.selected_passages()
    number = next(
        index
        for index, passage in enumerate(passages, 1)
        if passage.citation == assessment.relation_passages[0].citation
    )
    answer = Answer(
        question="CMP180 product technical",
        status="answered",
        passages=passages,
        text=f"CMP180 product option supports technical test requirements [{number}].",
    )
    record = grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="trace-link", request_id="request-link", span_id="answer"),
        answer,
        assessment=assessment.summary(),
    )
    actions = KnowledgeBridgeActions(
        lambda: {},
        required_evidence=("raw_citations",),
        required_facets=("product_option_spec", "technical_knowledge"),
        relation_required=True,
    )
    actions.result = {"ok": True, "record": record.model_dump(mode="json")}
    assert actions.facet_report()["facet_status"] == "covered"
    assert all(check.status == "passed" for check in actions.validate())


@pytest.mark.parametrize("subset", _combinations())
def test_host_accepts_cited_evidence_for_each_requested_combination(
    tmp_path: Path, subset: tuple[int, ...]
) -> None:
    vault = make_vault(tmp_path)
    for index in subset:
        _write(vault, NAMES[index], TEXTS[index])
    if len(subset) > 1:
        _write(vault, "link", LINK)
    question = "CMP180 " + " ".join(WORDS[index] for index in subset)
    assessment = assess_knowledge_evidence(vault, question, _procedure())
    assert assessment.status == "covered"
    passages = assessment.selected_passages()

    def number_for(value: str) -> int:
        return next(number for number, passage in enumerate(passages, 1) if value in passage.text)

    sentences = [f"{TEXTS[index]} [{number_for(TEXTS[index])}]" for index in subset]
    if len(subset) > 1:
        sentences.append(f"{LINK} [{number_for(LINK)}]")
    answer = Answer(
        question=question,
        status="answered",
        passages=passages,
        text=" ".join(sentences),
    )
    record = grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="trace-subset", request_id="request-subset", span_id="answer"),
        answer,
        assessment=assessment.summary(),
    )
    actions = KnowledgeBridgeActions(
        lambda: {},
        required_evidence=("raw_citations",),
        required_facets=tuple(NAMES[index] for index in subset),
        relation_required=len(subset) > 1,
    )
    actions.result = {"ok": True, "record": record.model_dump(mode="json")}
    assert actions.facet_report()["facet_status"] == "covered"
    assert all(check.status == "passed" for check in actions.validate())


def test_subject_is_carried_by_cited_product_document_not_other_products() -> None:
    def answer(raw_ref: str, text: str) -> Answer:
        return Answer(
            question="CMP180 option",
            status="answered",
            text=text,
            passages=(
                Passage(
                    text="Option R&S CMP-KM351 is required to measure 802.11ax signals.",
                    citation=Citation(kind="raw", raw_ref=raw_ref, section=3),
                    score=1,
                ),
            ),
        )

    own = answer("raw/Productions/CMP180_Features_V11-9_en_09.md", "CMP-KM351 量測 802.11ax [1]。")
    other = answer("raw/Productions/CMX500_Features_en.md", "CMP-KM351 量測 802.11ax [1]。")
    named = answer("raw/Productions/CMX500_Features_en.md", "CMP180 的 CMP-KM351 [1]。")
    assert answer_concerns_subject(own, "CMP180")
    assert not answer_concerns_subject(other, "CMP180")
    assert answer_concerns_subject(named, "CMP180")


def test_host_checks_labeled_inference_without_upgrading_the_relationship() -> None:
    market = Passage(
        text="Wi-Fi 7 是網通代工最重要的規格升級驅動力，需支援完整 320MHz 頻寬。",
        citation=Citation(kind="raw", raw_ref="raw/Market/report.md", section=2),
        score=1,
    )
    option = Passage(
        text="R&S CMP-KM352 option, WLAN IEEE 802.11be analyzer.",
        citation=Citation(kind="raw", raw_ref="raw/Productions/CMP180_specs.md", section=197),
        score=1,
    )
    text = (
        "R&S CMP-KM352 option is a WLAN IEEE 802.11be analyzer [2].\n"
        "【推論】Wi-Fi 7 的 320MHz 需求與 CMP-KM352 802.11be analyzer 方向一致 [1][2]。"
    )
    answer = Answer(
        question="無線通訊市場趨勢與 CMP180 選配",
        status="answered",
        passages=(market, option),
        text=text,
    )
    procedure = _guided_procedure()
    assert procedure.inference_label == "【推論】"
    assert answer_claims_overlap_raw(answer, inference_label=procedure.inference_label)
    record = grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="inference", request_id="inference", span_id="answer"),
        answer,
    )
    actions = KnowledgeBridgeActions(
        lambda: {},
        required_evidence=("raw_citations",),
        required_facets=("product_option_spec",),
        required_subject="CMP180",
        procedure=procedure,
    )
    actions.result = {"ok": True, "record": record.model_dump(mode="json")}
    claim = next(check for check in actions.validate() if check.check_id == "claim_support")
    assert claim.status == "passed"
    invented = answer.model_copy(update={"text": text.replace("KM352 802", "KM999 802")})
    assert not answer_claims_overlap_raw(invented, inference_label=procedure.inference_label)


def _uncredited_record(vault: Vault, question: str, cite: str) -> dict[str, Any]:
    """A record whose answer cites one passage, with every facet's listed
    passages emptied: retrieval lists only its first few per facet."""
    assessment = assess_knowledge_evidence(vault, question, _procedure())
    passages = assessment.selected_passages()
    number = next(i for i, p in enumerate(passages, 1) if cite in p.text)
    answer = Answer(
        question=question, status="answered", passages=passages, text=f"{cite} [{number}]."
    )
    record = grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="trace-cite", request_id="request-cite", span_id="answer"),
        answer,
        assessment=assessment.summary(),
    ).model_dump(mode="json")
    for facet in record["assessment"]["facets"]:
        facet["citations"] = []
    return record


def test_a_cited_passage_meeting_the_facet_rule_covers_it_outside_the_listed_ones(
    tmp_path: Path,
) -> None:
    """knowledge_v1 sample-001 Q0071: the answer cited a passage meeting the facet
    rule that retrieval had not listed, and the whole answer was discarded."""
    vault = make_vault(tmp_path)
    _write(vault, "technical", TEXTS[2])
    record = _uncredited_record(vault, "CMP180 technical", "CMP180 technical test method")
    unguided = KnowledgeBridgeActions(
        lambda: {}, required_evidence=("raw_citations",), required_facets=("technical_knowledge",)
    )
    unguided.result = {"ok": True, "record": record}
    assert unguided.facet_report()["facet_status"] == "missing"
    guided = KnowledgeBridgeActions(
        lambda: {},
        required_evidence=("raw_citations",),
        required_facets=("technical_knowledge",),
        procedure=_procedure(),
    )
    guided.result = {"ok": True, "record": record}
    assert guided.facet_report()["facet_status"] == "covered"


def test_a_cited_passage_failing_the_facet_rule_does_not_cover_it(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    _write(vault, "product", TEXTS[1])
    _write(vault, "technical", TEXTS[2])
    record = _uncredited_record(vault, "CMP180 technical product", "CMP180 product option K123")
    actions = KnowledgeBridgeActions(
        lambda: {},
        required_evidence=("raw_citations",),
        required_facets=("technical_knowledge",),
        procedure=_procedure(),
    )
    actions.result = {"ok": True, "record": record}
    report = actions.facet_report()
    assert report["facet_status"] == "missing"
    assert report["missing_facets"] == ["technical_knowledge"]


def test_facet_credit_keeps_the_skills_citation_policy(tmp_path: Path) -> None:
    """A record claiming another citation policy than the Skill's earns no credit."""
    vault = make_vault(tmp_path)
    _write(vault, "technical", TEXTS[2])
    record = _uncredited_record(vault, "CMP180 technical", "CMP180 technical test method")
    record["citation_policy"] = "wiki_primary"
    actions = KnowledgeBridgeActions(
        lambda: {},
        required_evidence=("raw_citations",),
        required_facets=("technical_knowledge",),
        procedure=_procedure(),
    )
    actions.result = {"ok": True, "record": record}
    assert actions.facet_report()["facet_status"] == "missing"


@pytest.mark.parametrize(
    ("question", "focus"),
    [
        (
            "For a Aerospace / Defense use case involving radar, where would Oscilloscope fit?",
            "航太國防 aerospace defense",
        ),
        (
            "What are the most important S-parameters capabilities for applications in Automotive?",
            "車用 automotive",
        ),
        (
            "How do changes in automotive radar technology affect Vector Network Analyzer needs?",
            "車用 automotive",
        ),
        (
            "Which measurement parameters matter for Oscilloscope in AI?",
            "AI 資料中心 AI data center",
        ),
        (
            "What are the most important signaling test capabilities in Wireless Communication?",
            "無線通訊 wireless communications",
        ),
        ("Which specifications of Signal Generator matter most for Semiconductor?", None),
    ],
)
def test_knowledge_skill_1_5_0_reads_the_market_a_question_names(
    question: str,
    focus: str | None,
) -> None:
    """Owner 2026-10-07: market hints for Aerospace / Defense, Automotive and AI;
    none for Semiconductor, whose hint pulled competitor searches off target."""
    path = Path(__file__).parent / "fixtures/harness_skills/knowledge-evidence-v1.5.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["metadata"]["identity"]["version"] == "1.5.0"
    procedure = KnowledgeProcedure.model_validate(payload["procedure"])
    found = procedure.focus(question)
    assert (found.query if found else None) == focus
