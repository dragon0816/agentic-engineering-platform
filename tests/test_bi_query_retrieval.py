"""`bi__query`: several hops over the relations, and passages from the search index
(`docs/phases/BI_CARD_MODEL.md` Phase 3). All data is fictional.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from test_bi_card_inferred_relations import PRODUCT, RELATION, TEST, _cards, _decide, _run
from test_bi_vault import _call, _commit, _ok, _push, _two_pcs
from test_bi_vault_published import CONTEXT
from test_bi_vault_sources import FOLDER, _add
from test_host_models import configured
from test_host_wiring import ready

from aep_bi.cards import search_index, service
from aep_bi.cards.capability import QUERY_SPEC, QueryHandler, QueryRequest
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, PlannedRow
from aep_bi.host.bi_assistant_query import BI_QUERY_FIELDS
from host_runtime import skill_packs
from host_runtime.assets import shipped
from host_runtime.host import build_runtime

APPROVED = ("UNCLASSIFIED", "INTERNAL")
REPORT = "# 虛構報告\n\n電源模組 FACT-POWER-1 的效率。\n"


def _row(name: str) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type="Technology",
        canonical_key=name,
        name=name,
        values={"name": name},
        synthetic=False,
    )


def _store(tmp_path: Path, *names: str) -> BiStore:
    store = BiStore(tmp_path, "demo")
    store.create("bi.schema/v1.1")
    store.apply([_row(n) for n in names], filename="t.csv", entity_type="Technology", actor="x")
    return store


def _id(store: BiStore, name: str) -> str:
    found = store.find("Technology", name)
    assert found is not None
    return str(found["id"])


def _relate(
    store: BiStore,
    start: str,
    end: str,
    *,
    status: str = "unreviewed",
    origin: str = "schema_field",
    kind: str = "has_technology",
) -> None:
    with sqlite3.connect(store.path) as db:
        db.execute(
            "INSERT INTO relations (relation_id, from_card_id, relation_type, to_card_id, status, "
            "origin) VALUES (?, ?, ?, ?, ?, ?)",
            (f"r-{start}-{kind}-{end}", _id(store, start), kind, _id(store, end), status, origin),
        )
    db.close()


def _ask(ws: Path, approved: Any = APPROVED, **given: Any) -> dict[str, Any]:
    request = QueryRequest(**given)
    return dict(asyncio.run(QueryHandler(ws, approved=approved)(CONTEXT, request)).model_dump())


def _names(answer: dict[str, Any]) -> list[str]:
    return [item["name"] for item in answer["related"]]


# -- the words of a text (R6: a question's whole text came back empty every time) -----


def test_every_word_may_stand_anywhere_on_the_card(tmp_path: Path) -> None:
    store = _store(tmp_path, "Acme-FY26-segment-AI晶片", "Acme-FY26-segment-記憶體", "Other")
    answer = _ask(tmp_path, dataset="demo", text="Acme FY26 AI晶片")
    assert [c["name"] for c in answer["cards"]] == ["Acme-FY26-segment-AI晶片"]
    assert "所有字詞" not in answer["scope_note"]
    assert [c["name"] for c, _ in service.search(store, text="acme 記憶體")] == [
        "Acme-FY26-segment-記憶體"
    ]


def test_a_questions_words_no_card_holds_show_the_nearest_and_say_so(tmp_path: Path) -> None:
    _store(tmp_path, "Acme-FY26-segment-記憶體", "Acme-FY26-segment-AI晶片", "Acme", "Other")
    answer = _ask(tmp_path, dataset="demo", text="Acme FY26 AI晶片 營收 年增率")
    names = [c["name"] for c in answer["cards"]]
    assert names[0] == "Acme-FY26-segment-AI晶片" and "Other" not in names
    assert "Acme" not in names  # one word of five is not near
    assert answer["total"] == len(names)
    assert "所有字詞" in answer["scope_note"] and "不一定是答案" in answer["scope_note"]


def test_nothing_near_asks_for_shorter_words_before_saying_no(tmp_path: Path) -> None:
    _store(tmp_path, "Acme")
    for text in ("zzz yyy", "zzz"):
        answer = _ask(tmp_path, dataset="demo", text=text)
        assert answer["total"] == 0 and "較短的字詞" in answer["scope_note"]


def test_the_card_list_stays_strict(tmp_path: Path) -> None:
    store = _store(tmp_path, "Acme-FY26")
    assert service.search(store, text="Acme FY26 營收") == []


# -- hops ---------------------------------------------------------------------


def test_no_hops_asked_leaves_the_answer_as_it_was(tmp_path: Path) -> None:
    store = _store(tmp_path, "A", "B")
    _relate(store, "A", "B")
    answer = _ask(tmp_path, dataset="demo", text="A", entity_type="Technology")
    assert answer["related"] == ()
    assert "relations" not in answer["cards"][0]


def test_hops_walk_both_directions_and_return_the_path(tmp_path: Path) -> None:
    store = _store(tmp_path, "A", "B", "C", "D")
    _relate(store, "A", "B")  # out from A
    _relate(store, "C", "B", kind="uses")  # into B: reached against its direction
    _relate(store, "C", "D")
    one = service.walk_relations(store, [_id(store, "A")], hops=1)
    assert [(n["card_id"], n["hops"]) for n in one["reached"]] == [(_id(store, "B"), 1)]
    three = service.walk_relations(store, [_id(store, "A")], hops=3)
    by_id = {n["card_id"]: n for n in three["reached"]}
    assert [by_id[_id(store, n)]["hops"] for n in ("B", "C", "D")] == [1, 2, 3]
    path = by_id[_id(store, "D")]["path"]
    assert [(s["type"], s["direction"]) for s in path] == [
        ("has_technology", "out"),
        ("uses", "in"),
        ("has_technology", "out"),
    ]
    assert [s["to_name"] for s in path] == ["B", "C", "D"]
    assert by_id[_id(store, "D")]["from_id"] == _id(store, "A")
    assert three["truncated"] is False


def test_a_cycle_ends_and_a_card_is_returned_once_by_its_shortest_path(tmp_path: Path) -> None:
    store = _store(tmp_path, "A", "B", "C")
    _relate(store, "A", "B")
    _relate(store, "B", "C")
    _relate(store, "C", "A")
    _relate(store, "A", "A", kind="self")
    walked = service.walk_relations(store, [_id(store, "A")], hops=3)
    assert sorted(n["card_id"] for n in walked["reached"]) == sorted(
        [_id(store, "B"), _id(store, "C")]
    )
    assert all(n["hops"] == 1 for n in walked["reached"])  # each is next to A both ways


def test_the_nodes_are_bounded_and_says_so(tmp_path: Path) -> None:
    names = [f"N{i:02d}" for i in range(6)]
    store = _store(tmp_path, "A", *names)
    for name in names:
        _relate(store, "A", name)
    walked = service.walk_relations(store, [_id(store, "A")], hops=2, max_nodes=4)
    assert len(walked["reached"]) == 4 and walked["truncated"] is True
    assert _ask(tmp_path, dataset="demo", text="A", hops=1)["related"]


def test_hops_are_bounded_by_the_request() -> None:
    with pytest.raises(ValueError):
        QueryRequest(hops=service.MAX_HOPS + 1)


def test_each_relation_says_how_far_it_may_be_stated(tmp_path: Path) -> None:
    store = _store(tmp_path, "A", "B", "C", "D", "E", "F", "G")
    _relate(store, "A", "B")
    _relate(store, "A", "C", status="confirmed", origin="ai_inferred", kind="requires")
    _relate(store, "A", "D", status="inferred", origin="ai_inferred", kind="requires")
    _relate(store, "A", "E", status="pending", origin="registered", kind="requires")
    _relate(store, "A", "F", status="disputed", origin="registered", kind="requires")
    _relate(store, "A", "G", status="rejected", origin="ai_inferred", kind="requires")
    walked = service.walk_relations(store, [_id(store, "A")], hops=1)
    claims = {n["name"]: (n["path"][0]["status"], n["claim"]) for n in walked["reached"]}
    assert claims == {
        "B": ("unreviewed", "fact"),
        "C": ("confirmed", "fact"),
        "D": ("inferred", "inferred"),
        "E": ("pending", "pending"),
        "F": ("disputed", "disputed"),
    }  # a rejected relation is not walked


def test_a_path_is_only_as_sure_as_its_weakest_step(tmp_path: Path) -> None:
    store = _store(tmp_path, "A", "B", "C")
    _relate(store, "A", "B", status="inferred", origin="ai_inferred", kind="requires")
    _relate(store, "B", "C")
    walked = service.walk_relations(store, [_id(store, "A")], hops=2)
    far = next(n for n in walked["reached"] if n["name"] == "C")
    assert [s["claim"] for s in far["path"]] == ["inferred", "fact"]
    assert far["claim"] == "inferred"


def test_a_second_relation_between_the_same_cards_is_not_lost(tmp_path: Path) -> None:
    store = _store(tmp_path, "A", "B")
    _relate(store, "A", "B", status="disputed", origin="registered", kind="competes")
    _relate(store, "A", "B")
    (node,) = service.walk_relations(store, [_id(store, "A")], hops=1)["reached"]
    (step,) = node["path"]
    assert (step["type"], step["claim"]) == ("has_technology", "fact")
    assert [(o["type"], o["claim"]) for o in step["also"]] == [("competes", "disputed")]


def test_the_answer_carries_related_cards_their_paths_and_the_rule(tmp_path: Path) -> None:
    store = _store(tmp_path, "A", "B")
    _relate(store, "A", "B", status="inferred", origin="ai_inferred", kind="requires")
    answer = _ask(tmp_path, dataset="demo", text="A", entity_type="Technology", hops=1)
    (seed,) = answer["cards"]
    assert seed["relations"][0]["claim"] == "inferred"
    (related,) = answer["related"]
    assert related["card"] == "Technology:B" and related["hops"] == 1
    assert related["from"] == "Technology:A" and related["claim"] == "inferred"
    assert related["fields"]["name"]["value"] == "B"
    assert "inferred" in answer["scope_note"] and "推論" in answer["scope_note"]


def test_a_dataset_from_before_the_card_model_has_no_relations_to_walk(tmp_path: Path) -> None:
    store = _store(tmp_path, "A")
    with sqlite3.connect(store.path) as db:
        db.execute("DROP TABLE relations")
    db.close()
    assert service.walk_relations(store, [_id(store, "A")], hops=2)["reached"] == []


def test_a_vaults_inferred_relation_is_read_from_the_published_version(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _cards(a, dataset)
    run_id, _ = _run(
        a,
        dataset,
        {
            "type": "requires_test",
            "from": "FAKE-PRODUCT",
            "to": "FAKE-TEST",
            "quote": "FAKE-PRODUCT 需要 FAKE-TEST",
            "reason": "量產前要測",
        },
    )
    assert PRODUCT and TEST
    ask = {"dataset": dataset, "entity_type": "CustomerProduct", "text": "FAKE-PRODUCT", "hops": 2}
    _commit(a, vault_id, "cards")
    _push(a, vault_id)
    assert _ask(a, **ask)["related"] == ()  # undecided: stays with the run

    _ok(_decide(a, dataset, run_id, "r1", "confirmed"))
    assert _ask(a, **ask)["related"] == ()  # this PC's unpushed decision is not read
    _commit(a, vault_id, "decided")
    _push(a, vault_id)
    (related,) = _ask(a, **ask)["related"]
    assert related["name"] == "FAKE-TEST" and related["path"][0]["relation_id"] == RELATION
    assert related["path"][0]["status"] == "confirmed" and related["claim"] == "fact"


# -- passages -----------------------------------------------------------------


def test_a_text_search_returns_passages_with_where_they_stand(tmp_path: Path) -> None:
    _store(tmp_path, "A")
    Staging(tmp_path, "demo").add_source("report.md", text=REPORT, actor="alice")
    answer = _ask(tmp_path, dataset="demo", text="FACT-POWER-1")
    assert answer["cards"] == () and answer["total"] == 0
    (passage,) = answer["passages"]
    assert passage["source_name"] == "report.md" and passage["line"] == 3
    assert "FACT-POWER-1" in passage["snippet"]
    assert "marks" not in passage
    assert answer["passages_withheld"] == 0
    # Asked for nothing to find: no passages, and a wordless search reads nothing.
    assert _ask(tmp_path, dataset="demo", entity_type="Technology")["passages"] == ()


def test_chinese_shorter_than_a_trigram_is_found_too(tmp_path: Path) -> None:
    _store(tmp_path, "A")
    Staging(tmp_path, "demo").add_source("report.md", text=REPORT, actor="alice")
    assert _ask(tmp_path, dataset="demo", text="效率")["passages"]


def test_a_source_of_an_unapproved_class_is_withheld_and_counted(tmp_path: Path) -> None:
    _store(tmp_path, "A")
    staging = Staging(tmp_path, "demo")
    staging.add_source("open.md", text=REPORT, actor="alice", classification="INTERNAL")
    staging.add_source(
        "secret.md", text=REPORT + "\n機密。\n", actor="alice", classification="RESTRICTED"
    )
    answer = _ask(tmp_path, dataset="demo", text="FACT-POWER-1")
    assert [p["source_name"] for p in answer["passages"]] == ["open.md"]
    assert answer["passages_withheld"] == 1
    assert "機密" not in str(answer["passages"])
    assert "1" in answer["scope_note"]
    none = _ask(tmp_path, approved=("UNCLASSIFIED",), dataset="demo", text="FACT-POWER-1")
    assert none["passages"] == () and none["passages_withheld"] == 2


def test_with_no_approval_known_no_passage_is_read(tmp_path: Path) -> None:
    _store(tmp_path, "A")
    Staging(tmp_path, "demo").add_source("report.md", text=REPORT, actor="alice")
    answer = _ask(tmp_path, approved=None, dataset="demo", text="FACT-POWER-1")
    assert answer["passages"] == () and answer["passages_withheld"] == 0


def test_a_vault_gives_passages_of_the_published_version_only(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _add(a, dataset, text=REPORT, folder=FOLDER)
    words = {"dataset": dataset, "text": "FACT-POWER-1"}
    assert _ask(a, **words)["passages"] == ()  # on this PC only
    _commit(a, vault_id, "加入報告")
    assert _ask(a, **words)["passages"] == ()  # committed, not pushed
    _push(a, vault_id)
    assert len(_ask(a, **words)["passages"]) == 1  # the pushed head of an unpublished vault
    # Published, then the next source pushed: only the published version is read.
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "第一版"}))
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1", "confirm": True}))
    later = _add(a, dataset, name="later.md", text="# 後來\n\nFACT-LATER-2 內容。\n", folder=FOLDER)
    assert later
    _commit(a, vault_id, "再加一份")
    _push(a, vault_id)
    assert _ask(a, dataset=dataset, text="FACT-LATER-2")["passages"] == ()
    assert len(_ask(a, **words)["passages"]) == 1
    # A colleague who received the version reads the same.
    drive.deliver("a", "b", vault_id)
    assert len(_ask(b, **words)["passages"]) == 1
    assert _ask(b, dataset=dataset, text="FACT-LATER-2")["passages"] == ()


def test_a_withdrawn_source_gives_no_passage(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _add(a, dataset, text=REPORT, folder=FOLDER)
    _commit(a, vault_id, "加入報告")
    _push(a, vault_id)
    words = {"dataset": dataset, "text": "FACT-POWER-1"}
    assert _ask(a, **words)["passages"]
    _ok(
        _call(
            a,
            "POST",
            f"/api/bi/vaults/{vault_id}/withdraw-source",
            {"source_id": source["id"], "confirm": True},
        )
    )
    assert _ask(a, **words)["passages"] == ()


def test_a_subscribed_copy_has_no_sources_and_creates_nothing(tmp_path: Path) -> None:
    store = BiStore(tmp_path, "engineering/robotics-bi")
    found = search_index.passages(store, "FACT", approved=APPROVED)
    assert found == {"passages": [], "withheld": 0}
    assert not store.dir.exists()


def test_an_unreadable_source_does_not_stop_the_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path, "A")
    staging = Staging(tmp_path, "demo")
    staging.add_source("one.md", text="# one\n\nFACT-ONE here.\n", actor="alice")
    bad = staging.add_source("two.md", text="# two\n\nFACT-TWO here.\n", actor="alice")
    search_index.index_path(store).unlink(missing_ok=True)
    real = Staging.markdown_text

    def cloud_only(self: Staging, source_id: str, rev: int) -> str:
        if source_id == bad["id"]:
            raise OSError("cloud only")
        return real(self, source_id, rev)

    monkeypatch.setattr(Staging, "markdown_text", cloud_only)
    assert _ask(tmp_path, dataset="demo", text="FACT-ONE")["passages"]
    monkeypatch.undo()
    assert _ask(tmp_path, dataset="demo", text="FACT-TWO")["passages"]  # picked up next time


def test_the_host_tells_the_query_what_its_model_is_approved_for(tmp_path: Path) -> None:
    config, layout = configured(tmp_path / "with-model")
    skill_packs.install_bundle(layout, None, shipped=shipped())
    with build_runtime(config, layout=layout) as runtime:
        installed = runtime.agent.gateway.bridge.installed.get(QUERY_SPEC.identity)
        assert installed is not None
        assert getattr(installed.handler, "approved", None) == ("UNCLASSIFIED",)
    config, layout = ready(tmp_path / "no-model")
    skill_packs.install_bundle(layout, None, shipped=shipped())
    with build_runtime(config, layout=layout) as runtime:
        installed = runtime.agent.gateway.bridge.installed.get(QUERY_SPEC.identity)
        assert installed is not None
        assert getattr(installed.handler, "approved", None) == ()


def test_the_assistant_tool_passes_hops_on() -> None:
    assert "hops" in BI_QUERY_FIELDS
