"""Benchmark error classes (proposal §6.1 D): where a failed term went wrong, or
`unknown`, never a guess. Grading stays as it was. All data is fictional."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from test_bi_query_retrieval import _id, _relate
from test_bi_vault import _commit, _import, _push, _row, _two_pcs
from test_bi_vault_bench import _save

from aep_bi.cards import error_class, vault
from aep_bi.cards.error_class import Card, World
from aep_bi.cards.store import BiStore
from aep_bi.host import bi_bench

TSN = Card(
    text="TSN IEEE 802.1 Acme",
    values={"standard_body": "IEEE 802.1", "note": "ETSI 草案"},
    linked=frozenset({"maker"}),
    evidence=[
        {"field": "standard_body", "excerpt": "標準由 IEEE 802.1 制定", "stance": "supports"},
        {"field": "note", "excerpt": "尚未定案", "stance": "supports"},
        {"field": "body", "excerpt": "傳聞 3GPP 也參與", "stance": "context_only"},
        {"field": "body", "excerpt": "OPC 並未參與", "stance": "refutes"},
    ],
)
MAKER = Card(text="Maker 公司 東京", values={"hq": "東京"}, linked=frozenset({"tsn"}), evidence=[])
OTHER = Card(text="無關 大阪", values={"hq": "大阪"}, linked=frozenset(), evidence=[])
WORLD = World(cards={"tsn": TSN, "maker": MAKER, "other": OTHER}, sources="原文提到新加坡與東京")


def _one(*, missing: Sequence[str] = (), forbidden: Sequence[str] = (), shown: Any) -> str:
    (item,) = error_class.classify(
        missing=missing, forbidden=forbidden, answered=True, shown=shown, world=WORLD
    )
    return item["class"]


@pytest.mark.parametrize(
    ("term", "shown", "expected"),
    [
        ("IEEE", ["tsn", "IEEE 802.1"], error_class.GENERATION),
        ("東京", ["tsn", "TSN"], error_class.RELATION),
        ("大阪", ["tsn", "TSN"], error_class.RETRIEVAL),
        ("大阪", [], error_class.RETRIEVAL),
        ("新加坡", ["tsn"], error_class.EXTRACTION),
        ("火星", ["tsn"], error_class.UNKNOWN),
    ],
)
def test_a_missing_term(term: str, shown: list[str], expected: str) -> None:
    assert _one(missing=[term], shown=shown) == expected


@pytest.mark.parametrize(
    ("term", "shown", "expected"),
    [
        ("火星", ["tsn", "TSN"], error_class.GENERATION),
        ("OPC", ["tsn", "OPC 並未參與"], error_class.GENERATION),
        ("3GPP", ["tsn", "傳聞 3GPP 也參與"], error_class.EVIDENCE),
        ("ETSI", ["tsn", "ETSI 草案"], error_class.EXTRACTION),
        ("IEEE", ["tsn", "標準由 IEEE 802.1 制定"], error_class.UNKNOWN),
        # Returned, but not from a card we can look into.
        ("ETSI", ["ETSI 草案"], error_class.UNKNOWN),
    ],
)
def test_a_forbidden_term(term: str, shown: list[str], expected: str) -> None:
    assert _one(forbidden=[term], shown=shown) == expected


def test_a_fetched_card_holding_a_term_its_tool_did_not_return_is_unknown() -> None:
    assert _one(missing=["大阪"], shown=["other"]) == error_class.UNKNOWN


def test_without_a_trace_or_a_finished_turn_it_says_unknown() -> None:
    for answered, shown, world in (
        (True, None, WORLD),
        (True, ["tsn"], None),
        (False, ["tsn", "IEEE"], WORLD),
    ):
        (item,) = error_class.classify(
            missing=["IEEE"], forbidden=[], answered=answered, shown=shown, world=world
        )
        assert item["class"] == error_class.UNKNOWN and item["why"]


def test_every_failed_term_gets_its_own_entry_and_counts_add_up() -> None:
    errors = error_class.classify(
        missing=["IEEE", "火星"],
        forbidden=["3GPP"],
        answered=True,
        shown=["tsn", "IEEE", "3GPP 也參與", "傳聞 3GPP 也參與"],
        world=WORLD,
    )
    assert [(e["term"], e["kind"]) for e in errors] == [
        ("IEEE", "missing"),
        ("火星", "missing"),
        ("3GPP", "forbidden"),
    ]
    assert error_class.counts(errors) == {"evidence": 1, "generation": 1, "unknown": 1}


def test_the_walk_takes_strings_and_leaves_keys_out() -> None:
    data = [{"cards": [{"id": "tsn", "fields": ["a", {"secret_key": "b"}], "n": 3}]}, None]
    assert list(error_class.walk_strings(data)) == ["tsn", "a", "b"]


def test_a_report_keeps_what_the_model_asked_and_how_much_came_back(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE 802.1"))
    _push(a, vault_id)
    status, payload = _save(
        a, vault_id, {"question": "標準組織？", "must": ["IEEE"], "must_not": []}
    )
    assert status == 200, payload
    asked = [{"arguments": {"text": "標準 組織"}, "status": "succeeded", "total": 0}]

    def ask(_text: str, _side: str) -> Mapping[str, Any]:
        return {"ok": True, "answer": "沒有資料", "shown": [], "calls": asked}

    report = bi_bench.run(a, vault_id, ask=ask, extract=lambda _c: [], actor="alice")
    assert report["results"][0]["working"]["calls"] == asked


def test_a_card_with_relations_is_still_classified(tmp_path: Path) -> None:
    """Real vaults have relations: reading them must not turn every class into unknown."""
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE 802.1"), _row("PTP"))
    store = BiStore(a, dataset)
    _relate(store, "TSN", "PTP")
    world = bi_bench._world(a, vault_id, "working")
    assert world is not None
    tsn, ptp = _id(store, "TSN"), _id(store, "PTP")
    assert world.cards[tsn].linked == {ptp} and world.cards[ptp].linked == {tsn}


def test_a_run_classifies_without_changing_the_score_or_the_gate(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE 802.1"))
    _push(a, vault_id)
    for question in (
        {"question": "標準組織？", "must": ["IEEE"], "must_not": []},
        {"question": "有 ETSI 嗎？", "must": [], "must_not": ["ETSI"]},
        {"question": "沒有紀錄的題？", "must": ["IEEE"], "must_not": []},
    ):
        status, payload = _save(a, vault_id, question)
        assert status == 200, payload
    _commit(a, vault_id, "題目")
    _push(a, vault_id)

    def ask(text: str, side: str) -> Mapping[str, Any]:
        if text == "沒有紀錄的題？":
            return {"ok": True, "answer": "不知道"}  # as a caller with no trace
        if side == "published":
            return {"ok": True, "answer": "IEEE 沒有另一個", "shown": []}
        answer = "我不確定" if text == "標準組織？" else "有 ETSI"
        return {"ok": True, "answer": answer, "shown": []}

    report = bi_bench.run(a, vault_id, ask=ask, extract=lambda _c: [], actor="alice")
    by_question = {r["question"]: r["working"]["errors"] for r in report["results"]}
    assert [e["class"] for e in by_question["標準組織？"]] == ["retrieval"]
    assert [e["class"] for e in by_question["有 ETSI 嗎？"]] == ["generation"]
    assert [e["class"] for e in by_question["沒有紀錄的題？"]] == ["unknown"]
    assert report["error_classes"] == {"retrieval": 1, "generation": 1, "unknown": 1}
    # Grading, the score and regressions stay what must and must_not say.
    assert report["working_score"] == 0 and report["published_score"] == 2
    assert len(report["regressions"]) == 2
    assert all(r["published"]["errors"] == [] or r["published"]["ok"] for r in report["results"])
    gated = partial(bi_bench.gate, a)
    units = vault.Vault(a, vault_id).repo.working_units()
    assert len(gated({}, units).blocking) == 2
