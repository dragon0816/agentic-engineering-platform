"""Query with provenance: deterministic retrieval whose every passage cites
where it came from, and synthesis that may cite only what was retrieved."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from test_raw import drop, make_vault

from common.execution import Failure
from knowledge.query import Answer, Citation, QueryEngine, retrieve, tokens
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


def corpus(vault: Vault) -> None:
    """One typed Raw with pages, one office-like Raw with slides, a Wiki page
    that carries the first source's provenance, and one without."""
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
            RawSection(text="射頻前端採用氮化鎵功率放大器", slide=2),
            RawSection(text="Roadmap for next quarter", slide=5),
        ),
    )
    vault.write_raw("raw/deck.md", render(deck))
    intake.intake("drop/rf.txt", mode="apply", today=TODAY)
    (root / "wiki" / "sources").mkdir(parents=True)
    (root / "wiki" / "entities").mkdir(parents=True)
    id_line, sha_line = provenance_lines(source)
    (root / "wiki" / "sources" / "Report.md").write_text(
        f"---\ntitle: Report\n{id_line}\n{sha_line}\n---\n"
        "Summary: a GaN amplifier drives the RF front end.\n\n"
        "Second paragraph about throughput.\n",
        encoding="utf-8",
    )
    (root / "wiki" / "entities" / "GaN.md").write_text(
        "---\ntitle: GaN\n---\nGallium nitride, a semiconductor for power amplifiers.\n",
        encoding="utf-8",
    )


def test_tokens_are_lowercased_words_with_cjk_bigrams() -> None:
    assert tokens("The RF Front-End, 4.2 Gbps") == ("the", "rf", "front", "end", "4", "2", "gbps")
    assert tokens("氮化鎵") == ("氮化鎵", "氮化", "化鎵")
    assert tokens("mixed 放大器 text") == ("mixed", "放大器", "放大", "大器", "text")
    assert tokens("   ") == ()


def test_retrieval_is_ranked_deterministic_and_cites_provenance(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    passages = retrieve(vault, "GaN power amplifier", k=3)
    assert [p.citation.kind for p in passages] == ["raw", "wiki", "wiki"]
    top = passages[0]
    assert top.text == "The RF front end uses a GaN power amplifier."
    assert top.citation == Citation(
        kind="raw",
        source=passages[0].citation.source,
        raw_ref="raw/report.md",
        section=1,
        page=1,
    )
    assert top.citation.source is not None and top.citation.source.original_ref == "drop/report.pdf"
    # The sources page cites the source behind it; the entity page only itself.
    kinds = {(p.citation.wiki_page, p.citation.source is not None) for p in passages[1:]}
    assert kinds == {("wiki/sources/Report.md", True), ("wiki/entities/GaN.md", False)}
    assert retrieve(vault, "GaN power amplifier", k=3) == passages
    assert [p.score for p in passages] == sorted((p.score for p in passages), reverse=True)

    slide = retrieve(vault, "氮化鎵", k=1)[0]
    assert slide.citation.slide == 2 and slide.citation.raw_ref == "raw/deck.md"
    # The Raw section keeps its page number wherever it ranks.
    by_kind = {p.citation.kind: p for p in retrieve(vault, "throughput gbps", k=5)}
    assert by_kind["raw"].citation.page == 3 and by_kind["raw"].citation.section == 2
    assert retrieve(vault, "zzz nothing here", k=5) == ()
    assert retrieve(vault, "", k=5) == ()
    with pytest.raises(ValueError, match="positive"):
        retrieve(vault, "x", k=0)
    # Image sections without a description are not passages.
    assert all(
        "assets" not in (p.citation.raw_ref or "") or p.citation.section != 3 for p in passages
    )


def test_synthesis_may_cite_only_what_was_retrieved(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    corpus(vault)
    good = Synth("The front end uses a GaN amplifier [1], summarised on the wiki [2].")
    engine = QueryEngine(vault, good, alias="answerer")
    answer = engine.ask("What amplifier does the RF front end use?", k=2)
    assert answer.status == "answered" and answer.synthesized_by == "answerer"
    assert answer.text.startswith("The front end") and len(answer.passages) == 2
    (request,) = good.requests
    assert "[1] The RF front end uses a GaN power amplifier." in request.messages[0].text
    assert request.model_alias == "answerer" and request.max_output_tokens == 800

    for text in ("GaN, trust me.", "See [7].", "", "Nothing [0]."):
        refused = QueryEngine(vault, Synth(text), alias="a").ask("GaN amplifier?", k=2)
        assert refused.status == "uncited" and refused.text == "" and len(refused.passages) == 2

    failed = QueryEngine(vault, Synth("x", fail=True), alias="a").ask("GaN amplifier?", k=2)
    assert failed.status == "model_failed" and failed.failure is not None
    assert failed.failure.code == "model_unavailable" and len(failed.passages) == 2
    raised = QueryEngine(vault, Synth("x", raise_=True), alias="a").ask("GaN amplifier?", k=2)
    assert raised.status == "model_failed" and raised.failure is not None
    assert raised.failure.code == "model_error" and raised.failure.retryable

    plain = QueryEngine(vault).ask("GaN amplifier?", k=2)
    assert plain.status == "retrieved" and plain.text == "" and len(plain.passages) == 2
    assert QueryEngine(vault, good, alias="a").ask("zzz", k=2).status == "no_match"
    assert Answer.model_validate_json(answer.model_dump_json()) == answer
    with pytest.raises(ValueError, match="come together"):
        QueryEngine(vault, good)
