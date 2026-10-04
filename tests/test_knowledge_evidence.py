"""Every nonempty combination keeps source coverage separate from inference."""

import itertools
import json
from datetime import date
from pathlib import Path

import pytest
from test_raw import make_vault

from common.assets import AssetIdentity
from common.execution import TraceIdentifiers
from host_runtime.knowledge_observation import KnowledgeBridgeActions
from knowledge.evidence import answer_claims_overlap_raw, assess_knowledge_evidence
from knowledge.evolution import grounded_record
from knowledge.procedure import KnowledgeProcedure
from knowledge.query import Answer, Citation, Passage, retrieve, retrieve_batch
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


def _write(vault: Vault, name: str, value: str) -> None:
    raw_ref = f"raw/{name}.md"
    source = source_for(value.encode(), f"drop/{name}.txt").model_copy(
        update={"raw_ref": raw_ref}
    )
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


def _combinations() -> list[tuple[int, ...]]:
    return [
        subset for size in range(1, 5)
        for subset in itertools.combinations(range(4), size)
    ]


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
        citation=Citation(kind="raw", raw_ref="raw/link.md", section=1), score=1,
    )
    assert answer_claims_overlap_raw(Answer(
        question="CMP180 market product", status="answered", passages=(passage,),
        text="CMP180 product option supports wireless market demand [1].",
    ))
    assert not answer_claims_overlap_raw(Answer(
        question="CMP180 market product", status="answered", passages=(passage,),
        text="Safe mode requires firmware 2.0 [1].",
    ))
    assert not answer_claims_overlap_raw(Answer(
        question="CMP180 market product", status="answered", passages=(passage,),
        text="CMP180 product option supports 9.9 Gbps wireless market demand [1].",
    ))


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
        index for index, passage in enumerate(passages, 1)
        if passage.citation == assessment.relation_passages[0].citation
    )
    answer = Answer(
        question="CMP180 product technical", status="answered", passages=passages,
        text=f"CMP180 product option supports technical test requirements [{number}].",
    )
    record = grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="trace-link", request_id="request-link", span_id="answer"),
        answer, assessment=assessment.summary(),
    )
    actions = KnowledgeBridgeActions(
        lambda: {}, required_evidence=("raw_citations",),
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
        return next(
            number for number, passage in enumerate(passages, 1)
            if value in passage.text
        )

    sentences = [f"{TEXTS[index]} [{number_for(TEXTS[index])}]" for index in subset]
    if len(subset) > 1:
        sentences.append(f"{LINK} [{number_for(LINK)}]")
    answer = Answer(
        question=question, status="answered", passages=passages,
        text=" ".join(sentences),
    )
    record = grounded_record(
        AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0"),
        TraceIdentifiers(trace_id="trace-subset", request_id="request-subset", span_id="answer"),
        answer, assessment=assessment.summary(),
    )
    actions = KnowledgeBridgeActions(
        lambda: {}, required_evidence=("raw_citations",),
        required_facets=tuple(NAMES[index] for index in subset),
        relation_required=len(subset) > 1,
    )
    actions.result = {"ok": True, "record": record.model_dump(mode="json")}
    assert actions.facet_report()["facet_status"] == "covered"
    assert all(check.status == "passed" for check in actions.validate())
