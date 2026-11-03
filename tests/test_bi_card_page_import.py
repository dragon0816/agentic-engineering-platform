"""Importing Obsidian card pages (`docs/phases/BI_CARD_PAGE_IMPORT.md`).

The pages here are fictional and written in the test. No model is involved: the
store's model is never set. Two PCs as in `test_bi_vault.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok, _push, _status, _two_pcs
from test_vault_asking_e2e import _ask, _bi_host, _bi_join, _Model, _served

from capabilities.bi_cards import page_import, vault, vault_sources
from capabilities.bi_cards.capability import QueryHandler, QueryRequest
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore

TECH = """---
type: technology
name: FAKE-TSN
standard_body: IEEE
spec_milestones: ["草案；第二版、終版", "FICT-2027"]
maturity: growth
affects_nodes:
  - "[[L1-Fake-Node]]"
  - "[[L2-Other|另一個]]"
no_such_field: 留著看
confidence: assumed
---

## 本文
不讀這裡。
"""
NODE = """---
type: node
name: L1-Fake-Node
---
"""
SAMPLE = """---
type: account
name: SAMPLE-客戶A
---
SAMPLE — 虛構。
"""
BAD = """---
type: technology
name: FAKE-BAD
maturity: not-a-maturity
nested: {a: 1}
open_list: [a, b
just a line
---
"""
NO_TYPE = """---
type: no_such_type
name: X
---
"""
TEMPLATE = """---
type: account
name: <% tp.file.title %>
---
"""
PAGES = [
    {"path": "BI/Technology/FAKE-TSN.md", "text": TECH},
    {"path": "BI/Node/L1-Fake-Node.md", "text": NODE},
    {"path": "BI/Account/SAMPLE-A.md", "text": SAMPLE},
]


def _preview(ws: Path, dataset: str, pages: list[dict[str, str]], **given: Any) -> dict[str, Any]:
    return dict(
        _ok(_call(ws, "POST", "/api/bi/import/pages/preview",
                  {"dataset": dataset, "pages": pages, **given}))
    )  # fmt: skip


def _apply(ws: Path, preview_id: str, **given: Any) -> dict[str, Any]:
    return dict(
        _ok(_call(ws, "POST", "/api/bi/import/pages/apply", {"preview_id": preview_id, **given}))
    )


def _dataset(tmp_path: Path) -> tuple[Path, str]:
    ws = tmp_path / "ws"
    ws.mkdir()
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    return ws, "lab"


def _row(answer: dict[str, Any], entity: str, key: str) -> dict[str, Any]:
    table = next(t for t in answer["types"] if t["entity_type"] == entity)
    return dict(next(r for r in table["rows"] if r["canonical_key"] == key))


def test_a_page_reads_every_shape_of_frontmatter_and_nothing_else() -> None:
    page = page_import.parse_page("p.md", TECH)
    assert page.values["name"] == "FAKE-TSN"
    # A list item keeps a separator: it is not split again.
    assert page.values["spec_milestones"] == ["草案；第二版、終版", "FICT-2027"]
    assert page.values["affects_nodes"] == ["L1-Fake-Node", "L2-Other"]
    assert page.lines["maturity"] == 6 and page.problems == []
    assert page_import.parse_page("p.md", "no frontmatter").has_frontmatter is False
    opened = page_import.parse_page("p.md", "---\nname: x\n")
    assert [p["code"] for p in opened.problems] == ["frontmatter_open"]
    bad = page_import.parse_page("p.md", BAD)
    codes = {p["code"]: p["line"] for p in bad.problems}
    assert codes == {"frontmatter_map": 5, "frontmatter_list": 6, "frontmatter_line": 7}
    assert bad.values["maturity"] == "not-a-maturity"  # read; judged by the schema


def test_the_preview_lists_what_it_cannot_use_and_writes_nothing(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    answer = _preview(ws, dataset, [
        *PAGES,
        {"path": "BI/Technology/FAKE-BAD.md", "text": BAD},
        {"path": "BI/X/NoType.md", "text": NO_TYPE},
        {"path": "BI/_Templates/T-Account.md", "text": TEMPLATE},
        {"path": "Elsewhere/T.md", "text": TEMPLATE},
        {"path": "Dashboard-X.md", "text": "---\ntype: account\n---\n"},
        {"path": "notes.md", "text": "plain"},
        {"path": "tool.py", "text": "print(1)"},
    ])  # fmt: skip
    assert BiStore(ws, dataset).card_rows() == []
    assert Staging(ws, dataset).sources() == []
    summary = answer["summary"]
    assert summary["create"] == 4 and summary["pages"] == 4
    unknown = next(t for t in answer["types"] if t["entity_type"] == "Technology")["columns"]
    assert any(c["source"] == "no_such_field" and c["status"] == "unknown" for c in unknown)
    warned = _row(answer, "Technology", "FAKE-BAD")["warnings"]
    assert warned and "not-a-maturity" in json.dumps(warned, ensure_ascii=False)
    codes = {p["path"]: p["code"] for p in answer["problems"]}
    assert codes["BI/X/NoType.md"] == "type_unknown"
    assert {p["code"] for p in answer["problems"] if p["path"].endswith("FAKE-BAD.md")} == {
        "frontmatter_map", "frontmatter_list", "frontmatter_line",
    }  # fmt: skip
    assert {s["path"] for s in answer["skipped"]} == {
        "BI/_Templates/T-Account.md", "Elsewhere/T.md", "Dashboard-X.md", "notes.md", "tool.py",
    }  # fmt: skip
    # A link to a page in the same request is not reported missing.
    tsn = _row(answer, "Technology", "FAKE-TSN")
    assert "L1-Fake-Node" not in json.dumps(tsn["warnings"], ensure_ascii=False)


def test_the_same_pages_give_the_same_preview(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    first = _preview(ws, dataset, PAGES)
    second = _preview(ws, dataset, list(reversed(PAGES)))
    for item in (first, second):
        item.pop("preview_id")
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second, sort_keys=True, ensure_ascii=False
    )


def test_apply_writes_cards_with_the_page_as_evidence_and_no_model(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    answer = _preview(ws, dataset, PAGES)
    done = _apply(ws, answer["preview_id"])
    assert done["written"] is True and done["applied"]["created"] == 3 and done["sources"] == 3
    store = BiStore(ws, dataset)
    card = store.find("Technology", "FAKE-TSN")
    assert card is not None
    fields = store.fields(card["id"])
    assert fields["standard_body"]["value"] == "IEEE"
    assert fields["spec_milestones"]["value"] == ["草案；第二版、終版", "FICT-2027"]
    assert "no_such_field" not in fields
    staging = Staging(ws, dataset)
    names = {s["name"] for s in staging.sources()}
    assert names == {"FAKE-TSN.md", "L1-Fake-Node.md", "SAMPLE-A.md"}
    detail = _ok(_call(ws, "GET", f"/api/bi/cards/{card['id']}", dataset=dataset))
    proof = next(e for e in detail["evidence"] if e["field"] == "standard_body")
    assert proof["source_name"] == "FAKE-TSN.md" and proof["excerpt"] == "standard_body: IEEE"
    assert proof["locator"] == {"line": 4, "key": "standard_body"} and proof["basis"] == "fact"
    # Applying the same preview twice cannot happen; the same pages change nothing.
    again = _preview(ws, dataset, PAGES)
    assert again["summary"]["unchanged"] == 3
    assert _apply(ws, again["preview_id"])["written"] is False


def test_a_vault_gets_one_commit_of_sources_and_one_of_cards(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    before = _status(a, vault_id)["ahead"]
    answer = _preview(a, dataset, PAGES)
    done = _apply(a, answer["preview_id"], folder="sources/library/products")
    assert done["written"] is True
    purposes = [c["purpose"] for c in vault.Vault(a, vault_id).repo.local_commits()]
    assert _status(a, vault_id)["ahead"] == before + 2
    assert purposes[0].startswith("加入來源：")
    assert _status(a, vault_id)["uncommitted"] == 0
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _ok(_call(b, "POST", f"/api/bi/vaults/{vault_id}/sync", {}))
    assert {s["name"] for s in Staging(b, dataset).sources()} == {
        "FAKE-TSN.md", "L1-Fake-Node.md", "SAMPLE-A.md",
    }  # fmt: skip
    units = vault.Vault(b, vault_id).repo.units()
    assert sum(1 for k in units if k.startswith(vault_sources.PREFIX)) == 3


# -- merging onto an existing card --------------------------------------------------------

BASE_A = """---
type: technology
name: FAKE-MERGE
standard_body: IEEE
maturity: growth
affects_nodes: ["L1-A", "L2-B"]
updated: 2026-01-05
---
"""
BASE_B = """---
type: technology
name: FAKE-MERGE
standard_body: IETF
spec_milestones: ["FICT-2027"]
affects_nodes: ["L2-B", "L3-C"]
updated: 2026-03-01
---
"""


def _merge(ws: Path, dataset: str, name: str, text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    answer = _preview(ws, dataset, [{"path": name, "text": text}])
    return answer, _apply(ws, answer["preview_id"])


def test_a_second_base_fills_joins_and_proposes_and_apply_does_what_the_preview_said(
    tmp_path: Path,
) -> None:
    ws, dataset = _dataset(tmp_path)
    _merge(ws, dataset, "a/FAKE-MERGE.md", BASE_A)
    answer = _preview(ws, dataset, [{"path": "b/FAKE-MERGE-b.md", "text": BASE_B}])
    row = _row(answer, "Technology", "FAKE-MERGE")
    assert row["action"] == "update"
    assert row["merge"]["fill"] == ["spec_milestones"]
    assert row["merge"]["join"] == ["affects_nodes"]
    assert row["merge"]["proposal"] == ["standard_body"]
    assert row["merge"]["bookkeeping"] == ["updated"]  # a derived field raises no proposal
    merge = answer["summary"]["merge"]
    assert (merge["fill"], merge["join"], merge["proposal"], merge["bookkeeping"]) == (1, 1, 1, 1)
    done = _apply(ws, answer["preview_id"])
    assert done["applied"]["proposals"] == 1
    store = BiStore(ws, dataset)
    card = store.find("Technology", "FAKE-MERGE")
    assert card is not None
    fields = store.fields(card["id"])
    assert fields["standard_body"]["value"] == "IEEE"  # never overwritten
    assert fields["spec_milestones"]["value"] == ["FICT-2027"]
    assert fields["affects_nodes"]["value"] == ["L1-A", "L2-B", "L3-C"]  # nothing lost
    assert fields["updated"]["value"] == "2026-03-01"  # the later one
    assert fields["maturity"]["value"] == "growth"  # the new page does not name it: kept
    pending = _ok(_call(ws, "GET", f"/api/bi/cards/{card['id']}", dataset=dataset))["proposals"]
    assert [(p["field"], p["value"]) for p in pending] == [("standard_body", "IETF")]


def test_an_older_bookkeeping_date_does_not_move_it_back(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    _merge(ws, dataset, "b.md", BASE_B)
    older = BASE_A.replace("IEEE", "IETF")
    answer, _ = _merge(ws, dataset, "a.md", older)
    store = BiStore(ws, dataset)
    card = store.find("Technology", "FAKE-MERGE")
    assert card is not None and store.fields(card["id"])["updated"]["value"] == "2026-03-01"
    assert _row(answer, "Technology", "FAKE-MERGE")["merge"]["bookkeeping"] == ["updated"]


def test_a_value_a_person_set_stays_theirs(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    _merge(ws, dataset, "a.md", BASE_A)
    card = BiStore(ws, dataset).find("Technology", "FAKE-MERGE")
    assert card is not None
    note = _ok(_call(ws, "POST", "/api/bi/corrections/preview",
                     {"dataset": dataset, "card": card["id"], "field": "standard_body",
                      "value": "PERSON", "base_version": card["version"], "reason": "r"},
                     actor="alice"))  # fmt: skip
    _ok(_call(ws, "POST", "/api/bi/corrections/apply",
              {"dataset": dataset, "text": note["text"], "base_version": card["version"]},
              actor="alice"))  # fmt: skip
    answer, done = _merge(ws, dataset, "b.md", BASE_B)
    assert _row(answer, "Technology", "FAKE-MERGE")["merge"]["human_kept"] == ["standard_body"]
    assert done["applied"]["proposals"] == 1
    store = BiStore(ws, dataset)
    assert store.fields(card["id"])["standard_body"]["value"] == "PERSON"


def test_each_base_keeps_its_evidence_on_the_merged_card(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    _merge(ws, dataset, "a/first.md", BASE_A)
    same = BASE_A.replace("updated: 2026-01-05\n", "")  # another base, same values
    answer, done = _merge(ws, dataset, "b/second.md", same)
    assert answer["summary"]["unchanged"] == 1 and done["written"] is True
    store = BiStore(ws, dataset)
    card = store.find("Technology", "FAKE-MERGE")
    assert card is not None
    named = {e["source_name"] for e in store.evidence(card["id"]) if e["field"] == "standard_body"}
    assert named == {"first.md", "second.md"}
    # Importing the same page again adds nothing.
    assert _merge(ws, dataset, "b/second.md", same)[1]["written"] is False
    # The proposal's evidence does not sit on the value it did not change.
    _merge(ws, dataset, "c/third.md", BASE_B)
    third = {e["field"] for e in store.evidence(card["id"]) if e["source_name"] == "third.md"}
    assert "standard_body" not in third and "spec_milestones" in third


def test_rows_of_one_request_merge_with_each_other(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    answer = _preview(
        ws, dataset, [{"path": "a.md", "text": BASE_A}, {"path": "b.md", "text": BASE_B}]
    )
    _apply(ws, answer["preview_id"])
    store = BiStore(ws, dataset)
    card = store.find("Technology", "FAKE-MERGE")
    assert card is not None
    fields = store.fields(card["id"])
    assert fields["affects_nodes"]["value"] == ["L1-A", "L2-B", "L3-C"]
    assert fields["standard_body"]["value"] == "IEEE"


def test_a_card_that_moved_since_the_preview_refuses_the_whole_apply(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    _merge(ws, dataset, "a.md", BASE_A)
    answer = _preview(ws, dataset, [{"path": "b.md", "text": BASE_B}])
    _merge(ws, dataset, "c.md", BASE_A.replace("L1-A", "L9-Z"))
    status, reply = _call(
        ws, "POST", "/api/bi/import/pages/apply", {"preview_id": answer["preview_id"]}
    )
    assert status != 200 and reply["code"] == "cards_changed"


def test_a_sample_row_never_marks_a_real_card_nor_a_real_row_clears_a_sample(
    tmp_path: Path,
) -> None:
    ws, dataset = _dataset(tmp_path)
    _merge(ws, dataset, "real.md", BASE_A)
    worded = "---\ntype: technology\nname: FAKE-MERGE\nspec_milestones: [待查證]\n---\n"
    answer, _ = _merge(ws, dataset, "worded.md", worded)
    (conflict,) = answer["mark_conflicts"]
    assert conflict["card_is_sample"] is False and conflict["row_is_sample"] is True
    store = BiStore(ws, dataset)
    card = store.find("Technology", "FAKE-MERGE")
    assert card is not None and card["synthetic"] == 0  # a real card stays real
    assert "spec_milestones" not in store.fields(card["id"])  # its value only proposes
    # The other way: a real page's value does not make a sample into fact.
    _merge(ws, dataset, "sample.md", "---\ntype: technology\nname: FAKE-S\nmaturity: (範例)\n---\n")
    real = "---\ntype: technology\nname: FAKE-S\nstandard_body: IEEE\n---\n"
    answer, _ = _merge(ws, dataset, "realer.md", real)
    assert answer["summary"]["mark_conflicts"] == 1
    sample = store.find("Technology", "FAKE-S")
    assert sample is not None and sample["synthetic"] == 1
    assert "standard_body" not in store.fields(sample["id"])


def test_a_seed_csv_merges_the_same_way_in_this_path(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    _merge(ws, dataset, "a.md", BASE_A)
    csv = "名稱,標準組織\nFAKE-MERGE,IETF\n"
    answer, done = _merge(ws, dataset, "seed/technology.csv", csv)
    assert _row(answer, "Technology", "FAKE-MERGE")["merge"]["proposal"] == ["standard_body"]
    assert done["applied"]["proposals"] == 1
    card = BiStore(ws, dataset).find("Technology", "FAKE-MERGE")
    assert card is not None
    assert BiStore(ws, dataset).fields(card["id"])["standard_body"]["value"] == "IEEE"


# -- samples ------------------------------------------------------------------------------


def test_sample_pages_and_marked_requests_are_imported_as_samples(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    answer = _preview(ws, dataset, PAGES)
    assert answer["summary"]["samples"] == 1
    _apply(ws, answer["preview_id"])
    store = BiStore(ws, dataset)
    sample = store.find("Account", "SAMPLE-客戶A")
    assert sample is not None and sample["synthetic"] == 1
    real = store.find("Technology", "FAKE-TSN")
    assert real is not None and real["synthetic"] == 0
    # A table whose rows do not all say so: the person's tick marks every row.
    csv = "名稱,標準組織\nFAKE-CSV,IETF\n"
    marked = _preview(ws, dataset, [{"path": "tools/samples/technology_sample.csv", "text": csv}],
                      samples=True)  # fmt: skip
    assert marked["summary"]["samples"] == marked["summary"]["create"] == 1
    _apply(ws, marked["preview_id"])
    assert store.find("Technology", "FAKE-CSV") is None
    found = store.find("Technology", "SAMPLE-FAKE-CSV")
    assert found is not None and found["synthetic"] == 1 and found["name"] == "SAMPLE-FAKE-CSV"


NODE_CSV = "名稱,領域\nSAMPLE-Already,wireless\nFAKE-NODE,wireless\n"
TECH_LINKS = (
    "---\ntype: technology\nname: FAKE-LINKED\n"
    'affects_nodes: ["[[FAKE-NODE]]", "[[SAMPLE-Already]]", "[[NOT-IN-REQUEST]]"]\n---\n'
)


def test_ticked_rows_get_the_prefix_once_and_their_links_follow(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    answer = _preview(
        ws,
        dataset,
        [
            {"path": "tools/samples/node_sample.csv", "text": NODE_CSV},
            {"path": "tools/samples/tech.md", "text": TECH_LINKS},
        ],
        samples=True,
    )
    keys = {r["canonical_key"] for t in answer["types"] for r in t["rows"]}
    assert keys == {"SAMPLE-Already", "SAMPLE-FAKE-NODE", "SAMPLE-FAKE-LINKED"}  # never twice
    assert answer["summary"]["samples"] == 3
    linked = _row(answer, "Technology", "SAMPLE-FAKE-LINKED")
    said = json.dumps(linked["warnings"], ensure_ascii=False)
    # A link to a row in the request follows the rename; one that cannot resolve is listed.
    assert "NOT-IN-REQUEST" in said and "FAKE-NODE" not in said and "Already" not in said
    _apply(ws, answer["preview_id"])
    store = BiStore(ws, dataset)
    card = store.find("Technology", "SAMPLE-FAKE-LINKED")
    assert card is not None
    assert store.fields(card["id"])["affects_nodes"]["value"] == [
        "SAMPLE-FAKE-NODE", "SAMPLE-Already", "NOT-IN-REQUEST",
    ]  # fmt: skip


def test_rows_not_ticked_keep_their_names(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    answer = _preview(
        ws, dataset, [{"path": "seed.csv", "text": "名稱,領域\nFAKE-REAL,wireless\n"}]
    )
    assert {r["canonical_key"] for t in answer["types"] for r in t["rows"]} == {"FAKE-REAL"}


def _bi_query(ws: Path, dataset: str, **given: Any) -> dict[str, Any]:
    import asyncio

    from test_bi_vault_published import CONTEXT

    request = QueryRequest(dataset=dataset, **given)
    return dict(asyncio.run(QueryHandler(ws)(CONTEXT, request)).model_dump())


def test_bi_query_says_when_samples_are_in_the_answer(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    _apply(ws, _preview(ws, dataset, PAGES)["preview_id"])
    found = _bi_query(ws, dataset, entity_type="Account")
    assert found["cards"][0]["synthetic"] is True and found["cards"][0]["trusted"] is False
    assert found["sample_note"] == "注意：這次查詢含 1 張範例資料，不是事實。"
    assert _bi_query(ws, dataset, entity_type="Technology")["sample_note"] == ""
    sql = _bi_query(ws, dataset, sql="SELECT name FROM cards")
    assert "含 1 張範例資料" in sql["sample_note"]


def test_the_default_pack_leaves_out_ticked_rows_unless_asked(tmp_path: Path) -> None:
    ws, dataset = _dataset(tmp_path)
    csv = "節點,領域\nFAKE-TICKED,wireless\n"
    page = "---\ntype: node\nname: FAKE-REAL-NODE\ndomain: [wireless]\n---\n"
    ticked = _preview(ws, dataset, [{"path": "x/node_sample.csv", "text": csv}], samples=True)
    _apply(ws, ticked["preview_id"])
    _apply(ws, _preview(ws, dataset, [{"path": "n.md", "text": page}])["preview_id"])

    def rows(**given: Any) -> str:
        found = _bi_query(ws, dataset, analysis="all", domain="wireless", **given)["analysis"]
        return json.dumps([s["rows"] for s in found], ensure_ascii=False)

    plain = rows()
    assert "FAKE-REAL-NODE" in plain and "FAKE-TICKED" not in plain
    assert "SAMPLE-FAKE-TICKED" in rows(params={"include_sample": True})


def test_the_default_pack_drops_sample_names_and_says_when_other_samples_may_count(
    tmp_path: Path,
) -> None:
    ws, dataset = _dataset(tmp_path)
    # Marked by its wording, not ticked: no prefix, so it can count in an analysis.
    csv = "名稱,標準組織,備註,領域\nFAKE-MARKED,IETF,(待查證),wireless\n"
    pages = [*PAGES, {"path": "x/technology.csv", "text": csv}]
    _apply(ws, _preview(ws, dataset, pages)["preview_id"])
    store = BiStore(ws, dataset)
    assert store.find("Technology", "FAKE-MARKED") is not None
    assert sum(1 for card in store.card_rows() if card["synthetic"]) == 2
    every = _bi_query(ws, dataset, analysis="all", domain="wireless")
    rows = json.dumps([s["rows"] for s in every["analysis"]], ensure_ascii=False)
    assert "SAMPLE-客戶A" not in rows  # by name, as before
    # A marked card without the prefix is not dropped, so the host says so whatever is drawn.
    assert "2 張範例資料" in every["sample_note"]
    assert "只排除 SAMPLE- 開頭的" in every["sample_note"]


def test_a_general_chat_answer_carries_the_hosts_sample_line(tmp_path: Path) -> None:
    drive, vault_id, dataset, publisher, _ = _two_pcs(tmp_path)
    _apply(publisher, _preview(publisher, dataset, PAGES)["preview_id"])
    _push(publisher, vault_id)
    config, layout = _bi_host(tmp_path / "reader")
    _bi_join(layout.workspace_root, drive.parent("a") / vault_id)
    model = _Model("bi__query", {"dataset": dataset, "entity_type": "Account"})
    with _served(config, layout, model) as server:
        answer = _ask(server)
    assert "注意：這次查詢含 1 張範例資料，不是事實。" in answer


# -- the page -----------------------------------------------------------------------------


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_page_previews_and_imports_a_chosen_folder(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path)
    ws = layout.workspace_root
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    files = [*PAGES, {"path": "BI/Technology/FAKE-BAD.md", "text": BAD},
             {"path": ".obsidian/app.md", "text": "---\ntype: account\n---\n"}]  # fmt: skip
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.run(
                "(() => { const s = document.getElementById('bi-dataset');"
                " s.value = 'lab'; s.dispatchEvent(new Event('change')); })()"
            )
            page.click("#bi-views [data-bi-view=build]")
            page.run(
                "(() => { const dt = new DataTransfer();"
                f" for (const f of {json.dumps(files, ensure_ascii=False)})"
                " dt.items.add(new File([f.text], f.path.replace(/\\//g, '__') + '.md'"
                " .replace('.md.md', '.md'), {type: 'text/markdown'}));"
                " const input = document.getElementById('bi-b-pages-dir');"
                " input.files = dt.files; input.dispatchEvent(new Event('change')); })()"
            )
            page.see("bi-b-pages-plan", "schema 沒有的欄位")
            page.see("bi-b-pages-plan", "no_such_field")
            page.see("bi-b-pages-plan", "看不懂的地方")
            assert BiStore(ws, "lab").card_rows() == []
            page.click_text("#bi-b-pages-plan", "確認匯入")
            page.notice("已匯入卡片頁")
    assert BiStore(ws, "lab").find("Technology", "FAKE-TSN") is not None
