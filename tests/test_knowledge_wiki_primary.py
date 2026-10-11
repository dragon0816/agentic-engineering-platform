"""Wiki-primary Knowledge citation: Wiki is the answer source, Raw the backing."""

import asyncio
import json
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import pytest
from test_raw import make_vault

from capabilities.knowledge_query.handlers import KnowledgeQueryHandler
from common.assets import AssetIdentity
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.knowledge_observation import KnowledgeBridgeActions
from host_runtime.web import knowledge_source_lines
from knowledge.evolution import KnowledgeAnswerRecord, WikiProvenance, grounded_record
from knowledge.procedure import KnowledgeProcedure
from knowledge.query import Answer, Citation, Passage, RetrievalSnapshot, wiki_sections
from knowledge.raw import RawDocument, RawSection, render, source_for
from knowledge.vault import Vault, provenance_lines
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

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


# -- Record contract ---------------------------------------------------------


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


# -- Wiki sections -----------------------------------------------------------


def test_wiki_sections_keep_tables_with_headings_and_drop_link_lists() -> None:
    page = (
        "---\ntitle: R&S ZNA\n---\n# R&S ZNA\n\nAnalyzer overview text here.\n\n"
        "## Options\n\n| Option | Function |\n|---|---|\n| ZNA-K2 | TDR |\n\n"
        "## See also\n\n- [[A]]\n- [[B]]\n"
    )
    sections = wiki_sections("R&S ZNA", page)
    assert sections[0].startswith("R&S ZNA\nAnalyzer overview")
    assert sections[1].startswith("R&S ZNA › Options\n| Option | Function |")
    assert len(sections) == 2


def test_long_wiki_table_repeats_its_header_in_every_part() -> None:
    rows = "\n".join(f"| ZNA-K{n} | function number {n} for analysis |" for n in range(200))
    page = f"---\ntitle: T\n---\n## Options\n\n| Option | Function |\n|---|---|\n{rows}\n"
    sections = wiki_sections("T", page)
    assert len(sections) > 1
    assert all("| Option | Function |\n|---|---|" in part for part in sections)


# -- Retrieval, synthesis and Host checks over a small Vault -----------------


def _wiki_vault(tmp_path: Path) -> Vault:
    vault = make_vault(tmp_path)
    source = source_for(b"zna specs", "drop/ZNA_specs.pdf").model_copy(
        update={"raw_ref": "raw/ZNA_specs.md"}
    )
    vault.write_raw("raw/ZNA_specs.md", render(RawDocument(
        source=source, extractor="pdf.v1", created=date(2026, 10, 5),
        sections=(RawSection(text="ZNA-K20 extended time domain analysis with eye diagram."),),
    )))
    root = vault.root
    (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    id_line, sha_line = provenance_lines(source)
    (root / "wiki" / "sources" / "ZNA_specs.md").write_text(
        f"---\ntitle: ZNA_specs\n{id_line}\n{sha_line}\n---\nZNA specification source page.\n",
        encoding="utf-8",
    )
    (root / "wiki" / "entities" / "R&S ZNA.md").write_text(
        "---\ntitle: R&S ZNA\n---\n# R&S ZNA\n\n"
        "[[R&S ZNA]] is a vector network analyzer from 10 MHz to 67 GHz. "
        "Source: [[ZNA_specs]].\n\n"
        "## Options\n\n| Option | Function |\n|---|---|\n"
        "| ZNA-K2 | time domain TDR analysis |\n| ZNA-K20 | eye diagram |\n\n"
        "## See also\n\n- [[ZNA_specs]]\n",
        encoding="utf-8",
    )
    (root / "wiki" / "entities" / "Orphan.md").write_text(
        "---\ntitle: Orphan\n---\nOrphan analyzer option supports TDR eye diagram measurement.\n",
        encoding="utf-8",
    )
    (root / "index.md").write_text(
        "# Index\n\n- [[R&S ZNA]] — vector network analyzer with TDR and eye diagram\n",
        encoding="utf-8",
    )
    return vault


def _procedure(**update: object) -> KnowledgeProcedure:
    payload: dict[str, object] = {
        "intent_patterns": ["option"],
        "facets": [{
            "name": "product_option_spec",
            "request_patterns": ["option"],
            "search_queries": ["ZNA option TDR eye diagram"],
            "support_terms": ["option", "ZNA"],
        }],
        "citation_policy": "wiki_primary",
        **update,
    }
    return KnowledgeProcedure.model_validate(payload)


class _Synth:
    def __init__(self, write: Callable[[str], str]) -> None:
        self.write = write
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias,
            text=self.write(request.messages[0].text),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


class _Catalog:
    def __init__(self, vault: Vault) -> None:
        self.vault = vault

    def get(self, identity: AssetIdentity) -> tuple[None, Vault]:
        return None, self.vault


def _number(prompt: str, marker: str) -> int:
    """The passage number the model was offered for a passage containing marker."""
    for block in prompt.split("\n\n["):
        head, _, body = block.partition("]")
        if marker in body and head.strip().lstrip("[").isdigit():
            return int(head.strip().lstrip("["))
    raise AssertionError(f"{marker!r} was not offered to the model")


def _ask(vault: Vault, procedure: KnowledgeProcedure, model: _Synth) -> dict[str, object]:
    handler = KnowledgeQueryHandler(_Catalog(vault), model, alias="a")  # type: ignore[arg-type]
    context = RequestContext(
        trace=TRACE, actor="engineer", namespace="engineering",
        message="ZNA option", channel="local",
    )
    request = {
        "asset": ASSET.model_dump(mode="json"), "question": "ZNA option",
        "procedure": procedure.model_dump(mode="json"),
    }
    record = asyncio.run(handler(context, request))  # type: ignore[arg-type]
    loaded: dict[str, object] = json.loads(record.model_dump_json())
    return loaded


def test_wiki_primary_retrieval_leads_with_indexed_page_and_traces_provenance(
    tmp_path: Path,
) -> None:
    snapshot = RetrievalSnapshot(_wiki_vault(tmp_path))
    passages = snapshot.wiki_primary_passages(("ZNA option TDR eye diagram",))
    assert passages[0].citation.kind == "wiki"
    assert passages[0].citation.wiki_page == "wiki/entities/R&S ZNA.md"
    assert any(passage.citation.kind == "raw" for passage in passages)
    assert snapshot.wiki_provenance("wiki/entities/R&S ZNA.md") == ("raw/ZNA_specs.md",)
    assert snapshot.wiki_provenance("wiki/entities/Orphan.md") == ()


def test_wiki_primary_answer_cites_wiki_with_provenance_and_passes_host(
    tmp_path: Path,
) -> None:
    procedure = _procedure()
    model = _Synth(lambda prompt: (
        "ZNA-K2 provides time domain TDR analysis "
        f"[{_number(prompt, 'ZNA-K2 | time domain')}].\n"
        "Orphan analyzer option supports TDR eye diagram measurement "
        f"[{_number(prompt, 'Orphan analyzer')}]."
    ))
    record = _ask(_wiki_vault(tmp_path), procedure, model)
    assert record["citation_policy"] == "wiki_primary"
    provenance = {
        item["wiki_page"]: item["raw_refs"]
        for item in record["wiki_provenance"]  # type: ignore[attr-defined]
    }
    assert provenance == {
        "wiki/entities/R&S ZNA.md": ["raw/ZNA_specs.md"],
        "wiki/entities/Orphan.md": [],
    }
    assert "WIKI passages are the curated knowledge base" in model.requests[0].messages[0].text
    lines = knowledge_source_lines(record)
    assert any("Wiki：R&S ZNA（來源：`ZNA_specs.md`）" in line for line in lines)
    assert any("Wiki：Orphan（缺來源連結）" in line for line in lines)
    actions = KnowledgeBridgeActions(
        lambda: {}, required_evidence=("raw_citations",),
        required_facets=("product_option_spec",), procedure=procedure,
    )
    actions.result = {"ok": True, "record": record}
    checks = {check.check_id: check.status for check in actions.validate()}
    assert checks == {
        "answer_nonempty": "passed", "facet_coverage": "passed", "claim_support": "passed",
    }


def test_host_refuses_a_record_whose_policy_differs_from_the_skill(tmp_path: Path) -> None:
    model = _Synth(lambda prompt: (
        "ZNA-K2 provides time domain TDR analysis "
        f"[{_number(prompt, 'ZNA-K2 | time domain')}]."
    ))
    record = _ask(_wiki_vault(tmp_path), _procedure(), model)
    actions = KnowledgeBridgeActions(
        lambda: {}, required_evidence=("raw_citations",),
        required_facets=("product_option_spec",),
        procedure=_procedure(citation_policy="raw_only"),
    )
    actions.result = {"ok": True, "record": record}
    checks = {check.check_id: check.status for check in actions.validate()}
    assert checks["answer_nonempty"] == "failed"
    assert checks["claim_support"] == "failed"


def test_wiki_primary_drops_an_invented_wiki_claim(tmp_path: Path) -> None:
    model = _Synth(lambda prompt: (
        "ZNA-K2 provides time domain TDR analysis "
        f"[{_number(prompt, 'ZNA-K2 | time domain')}].\n"
        f"ZNA-K99 reaches 110 GHz [{_number(prompt, 'ZNA-K2 | time domain')}]."
    ))
    record = _ask(_wiki_vault(tmp_path), _procedure(), model)
    text = record["answer"]["text"]  # type: ignore[index]
    assert "ZNA-K2 provides" in text
    assert "K99" not in text


# -- Markdown tables in answers ----------------------------------------------

TABLE = (
    "### 產品與 Option 對接\n"
    "| 產品 | Option | 證據 |\n"
    "|---|---|---|\n"
    "| R&S ZNA | ZNA-K2 time domain analysis | [1] |\n"
    "| R&S ZNA | ZNA-K20 eye diagram | [2] |"
)


def test_table_rows_are_claims_and_structure_needs_no_citation() -> None:
    from knowledge.query import cited_claim_sentences

    assert cited_claim_sentences(TABLE) == (
        "| R&S ZNA | ZNA-K2 time domain analysis | [1] |",
        "| R&S ZNA | ZNA-K20 eye diagram | [2] |",
    )
    record = grounded_record(
        ASSET, TRACE, _answer(TABLE, WIKI, RAW), citation_policy="wiki_primary",
        wiki_provenance=(WikiProvenance(wiki_page="wiki/entities/R&S ZNA.md"),),
    )
    assert record.cited_passages == (WIKI, RAW)


def test_table_row_with_an_uncited_code_is_dropped_but_structure_kept() -> None:
    from knowledge.evidence import answer_claims_overlap_raw, omit_unverified_answer_lines

    bad = TABLE + "\n| R&S ZNA | ZNA-K99 110 GHz extension | [1] |"
    answer = _answer(bad, WIKI, RAW)
    assert not answer_claims_overlap_raw(answer, allow_wiki=True)
    kept = omit_unverified_answer_lines(answer, allow_wiki=True)
    assert "ZNA-K99" not in kept.text
    assert kept.text.startswith("### 產品與 Option 對接\n| 產品 | Option | 證據 |\n|---|---|---|")
    assert answer_claims_overlap_raw(kept, allow_wiki=True)


def test_table_header_without_surviving_rows_is_removed() -> None:
    from knowledge.evidence import omit_unverified_answer_lines

    only_bad = (
        "ZNA covers 10 MHz to 67 GHz [1].\n"
        "### 對接表\n| 產品 | Option |\n|---|---|\n| R&S ZNA | ZNA-K99 extension [1] |"
    )
    kept = omit_unverified_answer_lines(_answer(only_bad, WIKI, RAW), allow_wiki=True)
    assert kept.text == "ZNA covers 10 MHz to 67 GHz [1]."


def test_labeled_inferences_stay_under_their_heading_and_are_capped() -> None:
    from knowledge.evidence import omit_unverified_answer_lines

    inference = "【推論】ZNA 的 time domain analysis 適合 TDR 驗證 [1]。"
    text = (
        "### 推薦先賣\n" + "\n".join([inference] * 4)
        + "\n### 事實\nZNA covers 10 MHz to 67 GHz [1]."
    )
    kept = omit_unverified_answer_lines(
        _answer(text, WIKI, RAW), inference_label="【推論】", allow_wiki=True
    )
    lines = kept.text.splitlines()
    assert lines[0] == "### 推薦先賣"
    assert lines[1:4] == [inference] * 3
    assert lines[4:] == ["### 事實", "ZNA covers 10 MHz to 67 GHz [1]."]


# -- Snapshot reuse (2026-10-12) ----------------------------------------------


def test_a_cached_snapshot_is_reused_until_a_vault_file_changes(tmp_path: Path) -> None:
    vault = _wiki_vault(tmp_path)
    first = RetrievalSnapshot.cached(vault)
    assert RetrievalSnapshot.cached(vault) is first
    page = tmp_path / "wiki" / "entities" / "R&S ZNB.md"
    page.write_text("---\ntitle: R&S ZNB\n---\nZNB vector network analyzer with "
                    "bandwidth up to 43.5 GHz for production test.\n", encoding="utf-8")
    second = RetrievalSnapshot.cached(vault)
    assert second is not first
    assert "wiki/entities/R&S ZNB.md" in second.wiki_titles()
    found = second.search_wiki_pages("ZNB production", exclude=set())
    assert found and found[0].citation.wiki_page == "wiki/entities/R&S ZNB.md"


def test_a_cached_snapshot_ranks_like_a_fresh_one(tmp_path: Path) -> None:
    vault = _wiki_vault(tmp_path)
    queries = ("ZNA option", "eye diagram time domain")
    cached = RetrievalSnapshot.cached(vault).wiki_primary_passages(queries)
    assert cached == RetrievalSnapshot(vault).wiki_primary_passages(queries)
