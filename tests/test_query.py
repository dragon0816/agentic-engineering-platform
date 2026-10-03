"""Query with provenance: deterministic retrieval whose every passage cites
where it came from, and synthesis that may cite only what was retrieved."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from test_raw import drop, make_vault

from common.assets import AssetIdentity
from common.execution import Failure, TraceIdentifiers
from knowledge.evolution import grounded_record
from knowledge.query import Answer, Citation, QueryEngine, cited_numbers, retrieve, tokens
from knowledge.raw import (
    DropIntake,
    PlainTextExtractor,
    RawDocument,
    RawSection,
    render,
    source_for,
)
from knowledge.vault import Vault, provenance_lines
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

TODAY = date(2026, 9, 21)


class Synth:
    def __init__(self, text: str, *, fail: bool = False, raise_: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.raise_ = raise_
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.raise_:
            raise TimeoutError("slow")
        if self.fail:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                failure=Failure(code="model_unavailable", message="down"),
            )
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=self.text)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


class SequenceSynth(Synth):
    def __init__(self, texts: tuple[str, ...]) -> None:
        super().__init__("")
        self.texts = iter(texts)

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text=next(self.texts),
        )


def corpus(vault: Vault) -> None:
    """One typed Raw with pages, one office-like Raw with slides, a Wiki page
    that carries the first source's provenance (saved with CRLF), one without."""
    intake = DropIntake(vault, [PlainTextExtractor()])
    drop(vault, "drop/rf.txt", b"unused")
    root = vault.root
    source = source_for(b"report bytes", "drop/report.pdf").model_copy(
        update={"raw_ref": "raw/report.md"}
    )
    report = RawDocument(
        source=source,
        extractor="pdf.v1",
        created=TODAY,
        sections=(
            RawSection(text="The RF front end uses a GaN power amplifier.", page=1),
            RawSection(text="Throughput reached 4.2 Gbps in the lab.", page=3),
            RawSection(kind="image", image_ref="raw/report/assets/a.png", page=3),
        ),
    )
    vault.write_raw("raw/report.md", render(report))
    deck = RawDocument(
        source=source_for(b"deck bytes", "drop/deck.pptx").model_copy(
            update={"raw_ref": "raw/deck.md"}
        ),
        extractor="pptx.v1",
        created=TODAY,
        sections=(
            RawSection(text="射頻前端採用GaN功率放大器", slide=2),
            RawSection(text="Roadmap for next quarter", slide=5),
        ),
    )
    vault.write_raw("raw/deck.md", render(deck))
    intake.intake("drop/rf.txt", mode="apply", today=TODAY)
    (root / "wiki" / "sources").mkdir(parents=True)
    (root / "wiki" / "entities").mkdir(parents=True)
    id_line, sha_line = provenance_lines(source)
    (root / "wiki" / "sources" / "Report.md").write_bytes(
        f"---\r\ntitle: Report\r\n{id_line}\r\n{sha_line}\r\n---\r\n"
        "Summary: a GaN amplifier drives the RF front end.\r\n\r\n"
        "Second paragraph about throughput.\r\n".encode()
    )
    (root / "wiki" / "entities" / "GaN.md").write_text(
        "---\ntitle: GaN\n---\nGallium nitride, a semiconductor for power amplifiers.\n",
        encoding="utf-8",
    )


def test_tokens_split_scripts_and_index_cjk_at_every_length() -> None:
    assert tokens("The RF Front-End, 4.2 Gbps") == ("the", "rf", "front", "end", "4", "2", "gbps")
    assert tokens("氮化鎵") == ("氮", "化", "鎵", "氮化", "化鎵", "氮化鎵")
    assert tokens("採用GaN功率") == ("採", "用", "採用", "gan", "功", "率", "功率")
    assert tokens("   ") == ()
    assert cited_numbers("see [1], [2, 3] and [5-7] but not [x]") == {1, 2, 3, 5, 6, 7}
    assert cited_numbers("no citations") == set()


def test_retrieval_is_ranked_deterministic_and_cites_provenance(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    passages = retrieve(vault, "GaN power amplifier", k=4)
    kinds = [p.citation.kind for p in passages]
    assert kinds.count("raw") == 2 and kinds.count("wiki") == 2
    top = passages[0]
    assert top.text == "The RF front end uses a GaN power amplifier."
    assert top.citation == Citation(
        kind="raw", source=top.citation.source, raw_ref="raw/report.md", section=1, page=1
    )
    assert top.citation.source is not None and top.citation.source.original_ref == "drop/report.pdf"
    # The CRLF sources page cites the source behind it and exposes no frontmatter
    # as a passage; the entity page cites only itself.
    wiki = {p.citation.wiki_page: p for p in passages if p.citation.kind == "wiki"}
    assert wiki["wiki/sources/Report.md"].citation.source == top.citation.source
    assert wiki["wiki/entities/GaN.md"].citation.source is None
    assert all("source_id" not in p.text for p in retrieve(vault, "source_id src", k=9))
    assert retrieve(vault, "GaN power amplifier", k=4) == passages
    assert retrieve(vault, "GaN power amplifier", k=4, evidence_coverage=True) == passages
    assert [p.score for p in passages] == sorted((p.score for p in passages), reverse=True)
    raw_grounded = retrieve(vault, "GaN power amplifier", k=2, min_raw=2)
    assert [p.citation.kind for p in raw_grounded] == ["raw", "raw"]

    # A Latin term glued to CJK is found, as is a one-character CJK question.
    glued = retrieve(vault, "gan", k=9)
    assert any(p.citation.slide == 2 for p in glued)
    assert retrieve(vault, "頻", k=1)[0].citation.raw_ref == "raw/deck.md"
    by_kind = {p.citation.kind: p for p in retrieve(vault, "throughput gbps", k=5)}
    assert by_kind["raw"].citation.page == 3 and by_kind["raw"].citation.section == 2
    # An image section without a description is not a passage.
    assert not any(
        p.citation.raw_ref == "raw/report.md" and p.citation.section == 3
        for p in retrieve(vault, "GaN amplifier throughput lab", k=9)
    )
    assert retrieve(vault, "zzz nothing here", k=5) == ()
    assert retrieve(vault, "", k=5) == ()
    with pytest.raises(ValueError, match="positive"):
        retrieve(vault, "x", k=0)
    with pytest.raises(ValueError, match="min_raw"):
        retrieve(vault, "x", k=2, min_raw=3)


def test_grounding_accepts_a_citation_after_punctuation_but_not_an_uncited_followup(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    passages = retrieve(vault, "GaN power amplifier", k=1)
    identity = AssetIdentity(namespace="engineering", name="guide", version="1.0.0")
    trace = TraceIdentifiers(trace_id="grounding", request_id="grounding", span_id="grounding")
    answer = Answer(
        question="Which amplifier?",
        status="answered",
        passages=passages,
        text="The RF front end uses a GaN power amplifier. [1]",
    )
    assert grounded_record(identity, trace, answer).cited_passages == passages
    with pytest.raises(ValueError, match="every answer sentence"):
        grounded_record(
            identity,
            trace,
            answer.model_copy(update={"text": answer.text + " This claim has no citation."}),
        )


def test_only_the_current_version_of_an_original_is_cited(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    intake = DropIntake(vault, [PlainTextExtractor()])
    drop(vault, "drop/spec.txt", b"The limit is 10 watts.")
    intake.intake("drop/spec.txt", mode="apply", today=TODAY)
    drop(vault, "drop/spec.txt", b"The limit is 12 watts.")
    latest = intake.intake("drop/spec.txt", mode="apply", today=TODAY)
    hits = retrieve(vault, "watts limit", k=5)
    assert [p.citation.raw_ref for p in hits] == [latest.raw_ref]
    assert hits[0].text == "The limit is 12 watts."


def test_bilingual_market_question_covers_raw_market_and_product_option_evidence(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    intake = DropIntake(vault, [PlainTextExtractor()])

    def add(name: str, text: str) -> str:
        original = f"drop/{name}.txt"
        drop(vault, original, text.encode("utf-8"))
        result = intake.intake(original, mode="apply", today=TODAY)
        assert result.raw_ref is not None
        return result.raw_ref

    market = add(
        "market",
        "高速通訊市場正在部署 800G Ethernet 和 high-speed digital links，測試需求包含訊號完整性。",
    )
    product = add(
        "Helios_specs",
        "Helios vector analyzer measures signal integrity on high-speed digital links. "
        "Option K17 enables differential measurements for these links.",
    )
    second_product = add(
        "Lyra_specs",
        "Lyra signal tester validates high-speed communication links. "
        "Option K22 adds an eye-diagram measurement for digital interfaces.",
    )
    for number in range(10):
        add(
            f"unrelated-{number}",
            f"高速通訊市場產品新聞第 {number} 期。本文只有供應商名單。",
        )
    (vault.root / "wiki" / "overview.md").write_text(
        "# 高速通訊市場產品與 option\n\n百科摘要不是原始產品規格。",
        encoding="utf-8",
    )
    question = "根據資料，哪些產品和 option 可以接軌高速通訊市場？"
    ordinary = retrieve(vault, question, k=4, min_raw=4)
    assert product not in {hit.citation.raw_ref for hit in ordinary}
    covered = retrieve(vault, question, k=5, min_raw=4, evidence_coverage=True)
    raw_refs = {hit.citation.raw_ref for hit in covered if hit.citation.kind == "raw"}
    assert {market, product, second_product}.issubset(raw_refs)
    assert all(hit.citation.source is not None for hit in covered if hit.citation.kind == "raw")


def test_synthesis_may_cite_only_what_was_retrieved(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    good = Synth("The front end uses a GaN amplifier [1], summarised on the wiki [1, 2].")
    engine = QueryEngine(vault, good, alias="answerer")
    answer = engine.ask("What amplifier does the RF front end use?", k=2)
    assert answer.status == "answered" and answer.synthesized_by == "answerer"
    assert answer.text.startswith("The front end") and len(answer.passages) == 2
    (request,) = good.requests
    assert "[1] The RF front end uses a GaN power amplifier." in request.messages[0].text
    assert request.model_alias == "answerer" and request.max_output_tokens == 800
    assert request.trace.trace_id.startswith("query-") and request.trace.request_id == "ask-1"
    guarded = Synth("The RF front end uses a GaN amplifier [1].")
    QueryEngine(vault, guarded, alias="answerer").ask(
        "GaN power amplifier", k=4, raw_citations_only=True
    )
    guarded_prompt = guarded.requests[0].messages[0].text
    assert "[1] RAW: The RF front end uses a GaN power amplifier." in guarded_prompt
    assert "WIKI:" in guarded_prompt
    engine.ask("GaN amplifier?", k=2)
    assert good.requests[1].trace.request_id == "ask-2"
    given = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")
    engine.ask("GaN amplifier?", k=2, trace=given)
    assert good.requests[2].trace == given

    for text in ("See [7].", "Nothing [0].", "Two [1-3]."):
        refused = QueryEngine(vault, Synth(text), alias="a").ask("GaN amplifier?", k=2)
        assert refused.status == "uncited" and refused.text == "" and len(refused.passages) == 2
    # An honest "the passages do not answer" keeps its words, as unanswered.
    honest = QueryEngine(vault, Synth("The passages do not cover this."), alias="a")
    unanswered = honest.ask("GaN amplifier?", k=2)
    assert unanswered.status == "unanswered" and unanswered.text.startswith("The passages")
    assert QueryEngine(vault, Synth("  "), alias="a").ask("GaN amplifier?", k=2).status == (
        "unanswered"
    )

    failed = QueryEngine(vault, Synth("x", fail=True), alias="a").ask("GaN amplifier?", k=2)
    assert failed.status == "model_failed" and failed.failure is not None
    assert failed.failure.code == "model_unavailable" and len(failed.passages) == 2
    raised = QueryEngine(vault, Synth("x", raise_=True), alias="a").ask("GaN amplifier?", k=2)
    assert raised.status == "model_failed" and raised.failure is not None
    assert raised.failure.code == "model_error" and raised.failure.retryable

    plain = QueryEngine(vault).ask("GaN amplifier?", k=2)
    assert plain.status == "retrieved" and plain.text == "" and len(plain.passages) == 2
    assert QueryEngine(vault, good, alias="a").ask("zzz", k=2).status == "no_match"
    assert QueryEngine(vault, good, alias="a").ask("   ", k=2).status == "no_match"
    assert Answer.model_validate_json(answer.model_dump_json()) == answer
    with pytest.raises(ValueError, match="come together"):
        QueryEngine(vault, good)


def test_raw_synthesis_retries_an_ungrounded_sentence_with_the_same_raw_evidence(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    model = SequenceSynth((
        "The front end uses a GaN amplifier [1]. It is fast.",
        "The front end uses a GaN amplifier [1].",
    ))
    answer = QueryEngine(vault, model, alias="a").ask(
        "GaN power amplifier", k=4, raw_citations_only=True
    )
    assert answer.status == "answered"
    assert len(model.requests) == 2
    assert "WIKI:" in model.requests[0].messages[0].text
    assert "WIKI:" not in model.requests[1].messages[0].text
    assert "RAW:" in model.requests[1].messages[0].text
    assert "It is fast" not in model.requests[1].messages[0].text
    identity = AssetIdentity(namespace="engineering", name="guide", version="1.0.0")
    trace = TraceIdentifiers(trace_id="retry", request_id="retry", span_id="retry")
    assert grounded_record(identity, trace, answer).cited_passages == (answer.passages[0],)


def test_raw_synthesis_retry_cannot_turn_a_wiki_claim_into_raw_evidence(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    passages = retrieve(vault, "GaN power amplifier", k=4, min_raw=4)
    wiki_number = next(
        number for number, passage in enumerate(passages, 1) if passage.citation.kind == "wiki"
    )
    model = SequenceSynth((f"A wiki-only claim [{wiki_number}].",) * 2)
    answer = QueryEngine(vault, model, alias="a").ask(
        "GaN power amplifier", k=4, raw_citations_only=True
    )
    assert len(model.requests) == 2
    assert answer.status != "answered"
    assert answer.text == ""


def test_raw_synthesis_can_recover_from_a_wiki_citation_without_relabeling_it(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    passages = retrieve(vault, "GaN power amplifier", k=4, min_raw=4)
    wiki_number = next(
        number for number, passage in enumerate(passages, 1) if passage.citation.kind == "wiki"
    )
    raw_number = next(
        number for number, passage in enumerate(passages, 1) if passage.citation.kind == "raw"
    )
    model = SequenceSynth((
        f"A wiki-only claim [{wiki_number}].",
        f"The front end uses a GaN power amplifier [{raw_number}].",
    ))
    answer = QueryEngine(vault, model, alias="a").ask(
        "GaN power amplifier", k=4, raw_citations_only=True
    )
    assert answer.status == "answered"
    assert len(model.requests) == 2
    identity = AssetIdentity(namespace="engineering", name="guide", version="1.0.0")
    trace = TraceIdentifiers(trace_id="retry", request_id="retry", span_id="retry")
    assert grounded_record(identity, trace, answer).cited_passages == (passages[raw_number - 1],)


def test_raw_synthesis_does_not_retry_valid_or_explicitly_insufficient_answers(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    valid = Synth("The front end uses a GaN amplifier. [1]")
    answer = QueryEngine(vault, valid, alias="a").ask(
        "GaN power amplifier", k=4, raw_citations_only=True
    )
    assert answer.status == "answered" and len(valid.requests) == 1
    insufficient = Synth("The Raw passages do not answer the question.")
    answer = QueryEngine(vault, insufficient, alias="a").ask(
        "GaN power amplifier", k=4, raw_citations_only=True
    )
    assert answer.status == "unanswered" and len(insufficient.requests) == 1


def test_broad_query_keeps_distant_option_and_interface_claims_in_separate_raw_excerpts(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    intake = DropIntake(vault, [PlainTextExtractor()])
    unrelated_rows = [
        f"Other specification row {number} has a numeric limit." for number in range(20)
    ]
    source = "\n".join(
        ["Option B81 changes the RF output level.", *unrelated_rows,
         "The high-speed USB digital input carries sample data."]
    )
    drop(vault, "drop/device-specs.txt", source.encode("utf-8"))
    intake.intake("drop/device-specs.txt", mode="apply", today=TODAY)
    question = "高速通訊市場有哪些產品和 option 可用於 high-speed USB digital input?"
    original = retrieve(vault, question, k=1, min_raw=1, evidence_coverage=True)
    assert "B81" in original[0].text and "USB" in original[0].text

    wrong = Synth("Option B81 provides a high-speed USB digital input [1].")
    answer = QueryEngine(vault, wrong, alias="a").ask(
        question, k=1, raw_citations_only=True, evidence_coverage=True
    )
    assert "USB" in answer.passages[0].text
    assert "B81" not in answer.passages[0].text
    assert "B81" not in wrong.requests[0].messages[0].text
    assert answer.status == "uncited"
    assert len(wrong.requests) == 2

    valid_source = "\n".join(
        ["Option K17 provides a high-speed USB digital input.", *unrelated_rows,
         "Another connection has a separate output."]
    )
    drop(vault, "drop/valid-specs.txt", valid_source.encode("utf-8"))
    intake.intake("drop/valid-specs.txt", mode="apply", today=TODAY)
    valid = Synth("Option K17 provides a high-speed USB digital input [1].")
    valid_answer = QueryEngine(vault, valid, alias="a").ask(
        question + " K17", k=1, raw_citations_only=True, evidence_coverage=True
    )
    assert valid_answer.status == "answered"
    assert len(valid.requests) == 1


@pytest.mark.parametrize("code", ("B81", "B200A"))
def test_option_code_and_interface_must_coexist_in_one_cited_raw_passage(
    tmp_path: Path, code: str,
) -> None:
    vault = make_vault(tmp_path)
    intake = DropIntake(vault, [PlainTextExtractor()])
    for name, body in (
        ("rf", f"Option {code} controls the RF output level."),
        ("digital", "A high-speed USB digital input carries sample data."),
    ):
        original = f"drop/{name}.txt"
        drop(vault, original, body.encode("utf-8"))
        intake.intake(original, mode="apply", today=TODAY)
    model = Synth(f"Option {code} provides a high-speed USB digital input [1, 2].")
    answer = QueryEngine(vault, model, alias="a").ask(
        f"{code} option high-speed USB", k=2, raw_citations_only=True
    )
    assert len(answer.passages) == 2
    assert answer.status == "uncited" and len(model.requests) == 2
