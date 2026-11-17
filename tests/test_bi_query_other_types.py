"""Filtered hits are not proof that another card type has no answer (fictional data)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _ok, _push, _two_pcs
from test_bi_vault_published import CONTEXT
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from aep_bi.cards.capability import QUERY_SPEC, QueryHandler, QueryRequest
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, PlannedRow
from aep_bi.host import bi_bench
from host_runtime import skill_packs
from host_runtime.assets import shipped
from host_runtime.host import build_runtime


def _row(kind: str, key: str, **values: Any) -> PlannedRow:
    return PlannedRow(1, kind, key, key, values, False)


def _cards(ws: Path, dataset: str = "demo") -> BiStore:
    store = BiStore(ws, dataset)
    if not store.exists:
        store.create("bi.schema/v1.1")
    for row in (
        _row(
            "SupplyLink", "BW-200 送樣", name="BW-200 送樣", supplier="虛構藍鯨", domain="wireless"
        ),
        _row(
            "CustomerProduct",
            "BW-200",
            product_name="BW-200",
            domain="robotics",
            body="前言。" * 150 + "BW-200 的校準週期為 6 個月。" + "後記。" * 150,
        ),
        _row("CustomerProduct", "BW-200 配套", product_name="BW-200 配套", domain="robotics"),
        _row("Technology", "BW-200 技術", name="BW-200 技術", domain="robotics"),
        _row("Technology", "不相關", name="不相關", domain="robotics", body="不能回傳的無關備註"),
    ):
        store.apply([row], filename="fictional.csv", entity_type=row.entity_type, actor="tester")
    return store


def _query(ws: Path, *, approved: Any = ("INTERNAL",), **args: Any) -> dict[str, Any]:
    return asyncio.run(
        QueryHandler(ws, approved=approved)(CONTEXT, QueryRequest(**args))
    ).model_dump()


@pytest.mark.parametrize(
    "filters",
    [
        {"entity_type": "SupplyLink"},
        {"field": "supplier", "value": "虛構藍鯨"},
    ],
    ids=["type", "field-and-value"],
)
def test_a_filtered_hit_counts_other_types_without_returning_their_rows(
    tmp_path: Path, filters: dict[str, str]
) -> None:
    _cards(tmp_path)
    answer = _query(tmp_path, dataset="demo", text="BW-200", limit=1, **filters)
    assert answer["total"] == len(answer["cards"]) == 1
    assert answer["cards"][0]["entity_type"] == "SupplyLink"
    assert "其他類型也有 3 張卡符合：CustomerProduct 2、Technology 1" in answer["scope_note"]
    assert "entity_type" in answer["scope_note"] and "field" in answer["scope_note"]
    assert "6 個月" not in json.dumps(answer, ensure_ascii=False)


def test_domain_counts_and_widening_keep_the_original_result(tmp_path: Path) -> None:
    _cards(tmp_path)
    answer = _query(tmp_path, text="BW-200", domain="wireless")
    assert answer["total"] == 1
    assert "其他領域也有 3 張卡符合：robotics 3" in answer["scope_note"]
    assert "domain" in answer["scope_note"]
    assert "其他類型" not in _query(tmp_path, text="BW-200")["scope_note"]
    assert "其他類型" not in _query(tmp_path, entity_type="SupplyLink")["scope_note"]


def test_only_matching_body_is_returned_as_a_bounded_citable_snippet(tmp_path: Path) -> None:
    _cards(tmp_path)
    answer = _query(tmp_path, text="BW-200", entity_type="CustomerProduct")
    card = next(c for c in answer["cards"] if c["name"] == "BW-200")
    snippet = card["body_snippet"]
    assert snippet["field"] == "body" and snippet["source"] == "import:fictional.csv#row1"
    assert "BW-200 的校準週期為 6 個月" in snippet["text"]
    assert len(snippet["text"]) <= 300
    assert snippet["text"].startswith("…") and snippet["text"].endswith("…")
    assert card["card"] == "CustomerProduct:BW-200" and "body" not in card["fields"]
    assert "body_snippet" not in next(c for c in answer["cards"] if c["name"] != "BW-200")
    assert all("body_snippet" not in c for c in _query(tmp_path)["cards"])
    assert all("body_snippet" not in c for c in _query(tmp_path, text="不相關")["cards"])


def test_body_requires_approval_and_respects_its_source_class(tmp_path: Path) -> None:
    store = _cards(tmp_path)
    for approved in (None, (), ("UNCLASSIFIED",)):
        assert all(
            "body_snippet" not in c
            for c in _query(tmp_path, text="BW-200", approved=approved)["cards"]
        )
    source = Staging(tmp_path, "demo").add_source(
        "private.md", text="BW-300 機密", actor="a", classification="RESTRICTED"
    )
    row = _row("CustomerProduct", "BW-300", product_name="BW-300", body="BW-300 機密")
    row.evidence["body"] = [
        {
            "source_id": source["id"],
            "source_name": "private.md",
            "locator": {},
            "excerpt": "BW-300 機密",
            "basis": "fact",
        }
    ]
    store.apply([row], filename="private.md", entity_type=row.entity_type, actor="a")
    assert "body_snippet" not in _query(tmp_path, text="BW-300")["cards"][0]
    assert "body_snippet" in _query(tmp_path, text="BW-300", approved=("RESTRICTED",))["cards"][0]
    # A real reviewed run stores source IDs even when its ref does not name the file.
    row = _row("CustomerProduct", "BW-400", product_name="BW-400", body="BW-400 機密")
    row.evidence["body"] = [
        {
            "source_id": source["id"],
            "source_name": "private.md",
            "locator": {},
            "excerpt": "BW-400 機密",
            "basis": "fact",
        }
    ]
    store.commit_run(
        "restricted-run", [(row, "candidate", None)], filename="different-name.md", actor="a"
    )
    assert "body_snippet" not in _query(tmp_path, text="BW-400")["cards"][0]


def test_counts_and_snippets_read_the_published_version_and_keep_sample_flags(
    tmp_path: Path,
) -> None:
    _, vault_id, dataset, ws, _ = _two_pcs(tmp_path)
    store = _cards(ws, dataset)
    sample = _row(
        "CustomerProduct", "BW-200 範例", product_name="BW-200 範例", body="BW-200 教學備註"
    )
    sample = replace(sample, synthetic=True)
    store.apply([sample], filename="fictional.csv", entity_type=sample.entity_type, actor="a")
    _push(ws, vault_id)
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "虛構"}))
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1", "confirm": True}))
    product = store.find("CustomerProduct", "BW-200")
    assert product is not None
    store.set_field(
        product["id"],
        "body",
        "BW-200 後來改成 999 個月",
        base_version=product["version"],
        actor="a",
    )
    later = _row("Technology", "BW-200 新資料", name="BW-200 新資料")
    store.apply([later], filename="later.csv", entity_type=later.entity_type, actor="a")
    _push(ws, vault_id)
    answer = _query(ws, dataset=dataset, text="BW-200", entity_type="SupplyLink")
    assert "CustomerProduct 3、Technology 1" in answer["scope_note"]
    widened = _query(ws, dataset=dataset, text="BW-200")
    assert "999" not in json.dumps(widened, ensure_ascii=False)
    assert "6 個月" in json.dumps(widened, ensure_ascii=False)
    sample_card = next(c for c in widened["cards"] if c["name"] == sample.name)
    assert sample_card["synthetic"] is True and sample_card["trusted"] is False
    assert widened["sample_note"] and sample_card["body_snippet"]


def test_a_benchmark_model_widens_on_the_hint_and_reads_the_other_types_body(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    shared = tmp_path / "fictional-shared"
    shared.mkdir()
    made = _ok(
        _call(
            layout.workspace_root,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(shared),
                "title": "虛構校準",
                "purpose": "測試",
                "schema": "bi.schema/v1.1",
                "author": "tester",
            },
        )
    )
    dataset = made["vault"]["dataset"]
    store = _cards(layout.workspace_root, dataset)
    model = Conversation()

    def follow_hint(request: Any) -> list[tuple[str, dict[str, Any]]]:
        data = json.loads(next(m.text for m in reversed(request.messages) if m.role == "tool"))[
            "host"
        ]["data"]
        assert data["total"] == 1 and "其他類型也有" in data["scope_note"]
        assert "6 個月" not in json.dumps(data, ensure_ascii=False)
        return [("bi__query", {"dataset": dataset, "text": "BW-200"})]

    def read_body(request: Any) -> list[Any]:
        data = json.loads(next(m.text for m in reversed(request.messages) if m.role == "tool"))[
            "host"
        ]["data"]
        product = next(c for c in data["cards"] if c["card"] == "CustomerProduct:BW-200")
        assert "6 個月" in product["body_snippet"]["text"]
        return []

    model.then(
        {
            "tools": [
                ("bi__query", {"dataset": dataset, "text": "BW-200", "entity_type": "SupplyLink"})
            ]
        },
        {"tools": follow_hint},
        {"tools": read_body, "text": "6 個月 [卡片 CustomerProduct:BW-200]"},
    )
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        gateway.router.model = model
        # The same approved classes the installed read tool supplies, not model arguments.
        installed = gateway.bridge.installed.get(QUERY_SPEC.identity)
        assert installed is not None
        assert isinstance(installed.handler, QueryHandler)
        installed.handler.approved = ("INTERNAL",)
        reply = bi_bench.ask_on(
            gateway,
            layout.workspace_root,
            dataset,
            "engineer",
            "engineering",
            (store, "虛構工作版本"),
            "BW-200 的校準週期是多少？",
        )
    assert reply["ok"] and "6 個月" in reply["answer"]
    assert len(reply["calls"]) == 2
    assert any("6 個月" in text for text in reply["shown"])
