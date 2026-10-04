"""Wiki-primary Knowledge citation: Wiki is the answer source, Raw the backing."""

import pytest

from common.assets import AssetIdentity
from common.execution import TraceIdentifiers
from knowledge.evolution import KnowledgeAnswerRecord, WikiProvenance, grounded_record
from knowledge.query import Answer, Citation, Passage

ASSET = AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0")
TRACE = TraceIdentifiers(trace_id="wiki", request_id="wiki", span_id="answer")
WIKI = Passage(
    text="R&S ZNA covers 10 MHz to 67 GHz with ZNA-K2 time domain analysis.",
    citation=Citation(kind="wiki", wiki_page="wiki/entities/R&S ZNA.md", section=2),
    score=1,
)
RAW = Passage(
    text="ZNA-K20 extends time domain analysis with an eye diagram.",
    citation=Citation(kind="raw", raw_ref="raw/Productions/ZNA_specs.md", section=9),
    score=1,
)
INDEX = Passage(
    text="- [[R&S ZNA]] — vector network analyzer",
    citation=Citation(kind="wiki", wiki_page="index.md"),
    score=1,
)


def _answer(text: str, *passages: Passage) -> Answer:
    return Answer(question="ZNA options", status="answered", passages=passages, text=text)


def test_raw_only_policy_still_rejects_wiki_citations() -> None:
    with pytest.raises(ValueError, match="Raw evidence"):
        grounded_record(ASSET, TRACE, _answer("ZNA covers 67 GHz [1].", WIKI))


def test_wiki_primary_record_carries_raw_provenance_for_each_cited_page() -> None:
    answer = _answer(
        "ZNA covers 10 MHz to 67 GHz [1].\nZNA-K20 adds an eye diagram [2].", WIKI, RAW
    )
    provenance = (
        WikiProvenance(
            wiki_page="wiki/entities/R&S ZNA.md", raw_refs=("raw/Productions/ZNA_specs.md",)
        ),
    )
    record = grounded_record(
        ASSET, TRACE, answer, citation_policy="wiki_primary", wiki_provenance=provenance,
    )
    assert record.citation_policy == "wiki_primary"
    assert record.wiki_provenance[0].status == "sourced"
    assert record.cited_passages == (WIKI, RAW)


def test_wiki_primary_marks_an_unlinked_page_without_rejecting_it() -> None:
    record = grounded_record(
        ASSET, TRACE, _answer("ZNA covers 67 GHz [1].", WIKI),
        citation_policy="wiki_primary",
        wiki_provenance=(WikiProvenance(wiki_page="wiki/entities/R&S ZNA.md"),),
    )
    assert record.wiki_provenance[0].status == "unlinked"


def test_wiki_primary_requires_exact_provenance_and_refuses_the_index() -> None:
    with pytest.raises(ValueError, match="provenance"):
        grounded_record(
            ASSET, TRACE, _answer("ZNA covers 67 GHz [1].", WIKI),
            citation_policy="wiki_primary",
        )
    with pytest.raises(ValueError, match="provenance"):
        grounded_record(
            ASSET, TRACE, _answer("ZNA-K20 adds an eye diagram [1].", RAW),
            citation_policy="wiki_primary",
            wiki_provenance=(WikiProvenance(wiki_page="wiki/entities/R&S ZNA.md"),),
        )
    with pytest.raises(ValueError, match="index"):
        grounded_record(
            ASSET, TRACE, _answer("ZNA is a network analyzer [1].", INDEX),
            citation_policy="wiki_primary",
            wiki_provenance=(WikiProvenance(wiki_page="index.md"),),
        )


def test_raw_only_record_cannot_carry_wiki_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        KnowledgeAnswerRecord(
            asset=ASSET, trace=TRACE, answer=_answer("ZNA-K20 adds an eye diagram [1].", RAW),
            cited_passages=(RAW,),
            wiki_provenance=(WikiProvenance(wiki_page="wiki/entities/R&S ZNA.md"),),
        )
