"""BI knowledge cards, Case A (owner 2026-10-21; Knowledge Strategy v1.3 §4.7).

The schema registry `bi.schema/v1.1` (from the robotics sample's schema v4),
the store with field provenance, the CSV import preview and apply, the
robotics demo set, the chat query and its Skill, the dashboard and the
`/api/bi/*` contract. Every test uses a temporary workspace.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture
from test_host_wiring import ready

from aep_bi.cards import board as bi_board
from aep_bi.cards import importer, service
from aep_bi.cards.capability import QUERY_SPEC, QueryHandler, QueryRequest
from aep_bi.cards.manifest import BI_SKILL, GAP_RULE, PROCEDURE, bi_knowledge_skill
from aep_bi.cards.schema import SCHEMA_FILE, parse_date, registry, split_list
from aep_bi.cards.store import BiStore, BiStoreError
from aep_bi.host.bi_cards_api import route
from aep_bi.host.bi_cards_tools import ATLAS_TOOL, TOOL_NAME, bi_cards_tools
from capabilities.runtime import CapabilityRefused
from common.execution import RequestContext, TraceIdentifiers
from host_runtime import skill_packs
from host_runtime.assets import shipped
from host_runtime.contracts import HostLayout
from host_runtime.host import build_runtime
from scripts.build_bi_schema_v1_1 import V4, build

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "tests" / "fixtures" / "robotics_kb_sample"
ACTOR = "tester"


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _loaded(tmp_path: Path) -> BiStore:
    store = BiStore(tmp_path)
    service.load_demo(store)
    return store


def _call(tmp_path: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(tmp_path, ACTOR, method, path, query, body)


def _label(cell: Any) -> str:
    return str(cell["label"]) if isinstance(cell, dict) else str(cell)


def _section(answer: dict[str, Any], sid: str) -> dict[str, Any]:
    return next(s for s in answer["sections"] if s["id"] == sid)


# -- schema registry ------------------------------------------------------


def test_the_shipped_registry_is_generated_from_schema_v4_and_covers_it() -> None:
    """The committed JSON is what the converter makes from v4 today, and every
    v4 type and field is in it except the Application priority (#222)."""
    assert json.loads(SCHEMA_FILE.read_text(encoding="utf-8")) == build()
    reg = registry()
    assert reg.schema_id == "bi.schema/v1.1"
    assert len(reg.types) == 12
    source = V4.read_text(encoding="utf-8")
    for entity in reg.types.values():
        for item in entity.fields:
            if item.name not in ("domain", "confidence", "updated", "body"):
                assert f'("{item.name}", F(' in source, (entity.name, item.name)
    application = reg.type("Application")
    assert application.get("priority") is None
    assert application.ignored[0]["reason"] == "優先度由 Skill 依事實判斷，不存資料"
    # v4 changes the owner listed.
    assert reg.type("Technology").get("domain").is_list  # type: ignore[union-attr]
    assert not reg.type("Application").get("domain").is_list  # type: ignore[union-attr]
    for name in ("Account", "Ecosystem", "Competitor", "CustomerProduct"):
        assert reg.type(name).get("nodes") is not None
    customer = reg.type("CustomerProduct")
    assert customer.get("ecosystem") and customer.get("launch_date")
    assert "EMC" in (reg.type("TestSolution").get("test_type").enum or ())  # type: ignore[union-attr]
    roles = reg.type("Ecosystem").get("role").enum or ()  # type: ignore[union-attr]
    assert {"institute", "ipc"} <= set(roles)
    assert reg.type("Opportunity").get("deal_stage") is not None
    # Trend ratings are facts; the Trend priority is computed, not a field.
    trend = reg.type("Trend")
    for name in ("measurement_impact", "our_fit", "market_impact"):
        assert trend.get(name).klass == "sourced"  # type: ignore[union-attr]
    assert trend.get("priority") is None
    assert reg.document["computed_fields"]["Trend"][0]["stored"] is False
    # v1's id rules and field classes are kept.
    v1 = json.loads(
        (REPO / "docs/proposals/bi_schema_v1/bi_schema_v1.json").read_text(encoding="utf-8")
    )
    assert reg.document["id_rules"] == v1["id_rules"]
    assert reg.document["field_classes"] == v1["field_classes"]


def test_every_robotics_csv_maps_with_no_unknown_column(tmp_path: Path) -> None:
    store = BiStore(tmp_path)
    for entity_type, name in service.DEMO_FILES:
        prepared = importer.preview(
            store, entity_type=None, filename=name, csv_text=service.demo_text(name)
        )
        assert prepared.entity_type == entity_type, name  # guessed from the headers
        statuses = {c["source"]: c["status"] for c in prepared.columns}
        assert "unknown" not in statuses.values(), (name, statuses)
        ignored = {k for k, v in statuses.items() if v == "ignored"}
        assert ignored == ({"優先度"} if entity_type == "Application" else set())


def test_the_demo_csvs_in_the_package_equal_the_sample() -> None:
    for _, name in service.DEMO_FILES:
        sample = SAMPLE / "tools" / "samples" / "robotics" / name
        assert service.demo_text(name) == sample.read_text(encoding="utf-8-sig")


def test_harness_and_storage_code_outside_the_package_do_not_import_bi_types() -> None:
    """ADR-K10: only the BI package and the Host's BI wiring name it.

    The BI package and its Host parts live in the BI Knowledge feature plugin
    (`feature_plugins/bi_knowledge/python/aep_bi`, proposal r3 stage B), so in
    core only these may still name it.
    """
    allowed = {
        "host_runtime/host.py",
        "host_runtime/assets.py",
        # BI dataset sharing: the platform re-reads every published snapshot.
        "control_plane/bi_datasets.py",
    }
    offenders = []
    for path in (REPO / "src").rglob("*.py"):
        relative = path.relative_to(REPO / "src").as_posix()
        if relative in allowed:
            continue
        if "aep_bi.cards" in path.read_text(encoding="utf-8"):
            offenders.append(relative)
    assert offenders == []


def test_values_normalise_like_the_fixture_ingest() -> None:
    assert parse_date("115/10/13") == "2026-10-13"
    assert parse_date("2026年3月1日") == "2026-03-01"
    assert parse_date("2027-03-31") == "2027-03-31"
    assert parse_date("下季") is None
    assert split_list("OTA;波束成型；EIRP、TRP") == ["OTA", "波束成型", "EIRP", "TRP"]
    assert split_list("示波器(含解碼;選配);LISN") == ["示波器(含解碼;選配)", "LISN"]
    reg = registry()
    stage = reg.type("Application").get("lifecycle")
    assert stage is not None and reg.normalize(stage, "研發") == ("RD", [])
    domain = reg.type("Technology").get("domain")
    assert domain is not None
    value, warnings = reg.normalize(domain, "Robotics;機器人;wirless")
    assert value == ["robotics"] and warnings[0][0] == "domain_unknown"


# -- Case A acceptance (§4.7) ----------------------------------------------

CSV = (
    "應用名稱,領域,生命週期,節點,技術,量測主題,優先度,神秘欄,更新日期,備註\n"
    "測試應用甲,robotics,研發,L2-Servo-Motor-Drive,EtherCAT;不存在的技術,OTA；EIRP,5,x,"
    "115/10/13,\n"
    "測試應用乙,Robotix,量產,Keysight,TSN,吞吐量,3-4,y,2026-10-01,\n"
)


def test_1_a_preview_writes_nothing(tmp_path: Path) -> None:
    before = _snapshot(tmp_path)
    importer.preview(BiStore(tmp_path), entity_type=None, filename="a.csv", csv_text=CSV)
    assert _snapshot(tmp_path) == before == {}
    store = _loaded(tmp_path)
    before = _snapshot(tmp_path)
    status, answer = _call(
        tmp_path,
        "POST",
        "/api/bi/import/preview",
        {"dataset": "demo", "entity_type": None, "filename": "a.csv", "csv_text": CSV},
    )
    assert status == 200 and answer["summary"]["create"] == 2
    assert _snapshot(tmp_path) == before
    assert len(store.card_rows()) == 104


def test_2_raw_and_normalised_values_are_both_shown(tmp_path: Path) -> None:
    prepared = importer.preview(
        _loaded(tmp_path), entity_type="Application", filename="a.csv", csv_text=CSV
    )
    cells = {c["field"]: c for c in prepared.rows[0]["fields"]}
    assert cells["lifecycle"]["raw"] == "研發" and cells["lifecycle"]["normalized"] == "RD"
    assert cells["updated"]["raw"] == "115/10/13"
    assert cells["updated"]["normalized"] == "2026-10-13"
    assert cells["measurement_topics"]["normalized"] == ["OTA", "EIRP"]
    assert cells["nodes"]["change"] == "add"


def test_3_unknown_columns_missing_links_and_mismatches_are_warned(tmp_path: Path) -> None:
    prepared = importer.preview(
        _loaded(tmp_path), entity_type="Application", filename="a.csv", csv_text=CSV
    )
    columns = {c["source"]: c for c in prepared.columns}
    assert columns["神秘欄"]["status"] == "unknown"
    assert columns["優先度"]["status"] == "ignored"
    assert columns["優先度"]["note"] == "優先度由 Skill 依事實判斷，不存資料"
    assert columns["生命週期"]["status"] == "alias"
    first = {w["code"] for w in prepared.rows[0]["warnings"]}
    second = {w["code"] for w in prepared.rows[1]["warnings"]}
    assert {"link_missing", "priority_ignored"} <= first
    # Keysight is a Competitor card, not a Node (DQ-3); "Robotix" is no domain.
    assert {"link_type_mismatch", "domain_unknown", "priority_ignored"} <= second
    assert prepared.summary()["warnings"] >= 6
    # A lenient integer is never adopted silently (DQ-9).
    trend_csv = "趨勢,領域,量測影響\n某趨勢,robotics,3-4\n"
    rows = importer.preview(
        BiStore(tmp_path), entity_type="Trend", filename="t.csv", csv_text=trend_csv
    ).rows
    cell = next(c for c in rows[0]["fields"] if c["field"] == "measurement_impact")
    assert cell["raw"] == "3-4" and cell["normalized"] is None
    assert any(w["code"] == "type_mismatch" for w in rows[0]["warnings"])


def test_4_a_rerun_creates_no_duplicates(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    assert service.load_demo(store) == {"created": 0, "updated": 0, "unchanged": 104}
    first = importer.apply(
        store,
        importer.preview(store, entity_type="Application", filename="a.csv", csv_text=CSV),
        None,
        actor=ACTOR,
    )
    second = importer.apply(
        store,
        importer.preview(store, entity_type="Application", filename="a.csv", csv_text=CSV),
        None,
        actor=ACTOR,
    )
    assert (first.created, second.created, second.unchanged) == (2, 0, 2)
    assert len(store.card_rows()) == 106


def test_5_human_values_are_kept_and_imports_become_proposals(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    card = store.find("Application", "AMR 電池包 BMS 與充電驗證")
    assert card is not None
    version = store.set_field(
        card["id"], "lifecycle", "Field", base_version=card["version"], actor=ACTOR
    )
    assert version == card["version"] + 1
    text = service.demo_text("application_robotics.csv")
    prepared = importer.preview(store, entity_type="Application", filename="b.csv", csv_text=text)
    row = next(r for r in prepared.rows if r["canonical_key"] == card["canonical_key"])
    cell = next(c for c in row["fields"] if c["field"] == "lifecycle")
    assert cell["change"] == "human_kept" and cell["current"] == "Field"
    result = importer.apply(store, prepared, None, actor=ACTOR)
    assert result.proposals == 1
    fields = store.fields(card["id"])
    assert fields["lifecycle"]["value"] == "Field" and fields["lifecycle"]["kind"] == "human"
    assert store.proposals(card["id"])[0]["field"] == "lifecycle"


def test_6_previews_and_proposals_are_not_searchable(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    raw = "應用名稱,領域,量測主題\n機密草稿應用,robotics,獨特詞XYZ\n"
    prepared = importer.preview(store, entity_type="Application", filename="r.csv", csv_text=raw)
    importer.remember(prepared)
    assert service.search(store, text="獨特詞XYZ") == []
    assert service.search(store, text="機密草稿應用") == []
    card = store.find("Trend", "快充與高稼動電池")
    assert card is not None
    store.set_field(card["id"], "stage", "peak", base_version=card["version"], actor=ACTOR)
    csv_text = "趨勢,領域,階段\n快充與高稼動電池,robotics,觀察\n"
    importer.apply(
        store,
        importer.preview(store, entity_type="Trend", filename="p.csv", csv_text=csv_text),
        None,
        actor=ACTOR,
    )
    assert store.proposals(card["id"])[0]["value"] == "watch"
    assert [c["id"] for c, _ in service.search(store, entity_type="Trend", text="watch")] == []


def test_7_fictional_or_verified_data_never_becomes_trusted(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    everything = store.all_fields()
    assert all(c["synthetic"] for c in store.card_rows())
    assert not any(service.trusted(c, everything.get(c["id"], {})) for c in store.card_rows())
    verified = "產品名稱,領域,信心度,備註\n某產品,robotics,verified,(虛構範例)\n"
    prepared = importer.preview(
        store, entity_type="CustomerProduct", filename="v.csv", csv_text=verified
    )
    assert any(w["code"] == "fictional_not_trusted" for w in prepared.rows[0]["warnings"])
    importer.apply(store, prepared, None, actor=ACTOR)
    card = store.find("CustomerProduct", "某產品")
    assert card is not None and card["synthetic"]
    assert store.fields(card["id"])["confidence"]["value"] == "assumed"
    # Even a person's verified does not make a synthetic card trusted.
    store.set_field(card["id"], "confidence", "verified", base_version=card["version"], actor=ACTOR)
    detail = service.card_detail(store, card["id"])
    assert detail is not None and detail["card"]["review_status"] == "draft"


def test_8_query_results_carry_sources(tmp_path: Path) -> None:
    _loaded(tmp_path)
    handler = QueryHandler(tmp_path)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor=ACTOR,
        namespace="engineering",
        message="bi",
        channel="local",
        session_id="s-1",
    )
    result = asyncio.run(
        handler(context, QueryRequest(entity_type="TestSolution", text="BMS", limit=10))
    )
    data = result.model_dump()
    assert data["total"] >= 1 and GAP_RULE in data["scope_note"]
    first = data["cards"][0]
    assert first["card"].startswith("TestSolution:") and first["trusted"] is False
    assert all(
        v["source"].startswith("fixture:demo/test_solutions_robotics.csv#row")
        for v in first["fields"].values()
    )
    assert any(link["field"] == "applications" for link in first["links"])
    assert QUERY_SPEC.side_effect == "read"


def test_the_chat_gets_the_whole_gap_analysis_not_a_search_sample(tmp_path: Path) -> None:
    """A live answer listed one of the two red gaps because a search missed the
    other; `analysis` returns the dashboard's own computation."""
    _loaded(tmp_path)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t2", request_id="r2", span_id="s2"),
        actor=ACTOR,
        namespace="engineering",
        message="bi",
        channel="local",
        session_id="s-2",
    )
    result = asyncio.run(
        QueryHandler(tmp_path)(context, QueryRequest(analysis="gaps", domain="robotics"))
    )
    (section,) = result.model_dump()["analysis"]
    red = [section["rows"][f["row"]][0] for f in section["flags"] if f["level"] == "red"]
    assert {cell["label"] for cell in red} == {"AMR 電池包 BMS 與充電驗證", "機器人產線下線測試"}
    assert all(cell["cite"].startswith("Application:") for cell in red)
    assert "analysis" in PROCEDURE
    with pytest.raises(CapabilityRefused):
        asyncio.run(QueryHandler(tmp_path)(context, QueryRequest(analysis="nope")))


def test_9_the_procedure_scopes_gaps_cites_cards_and_judges_priority() -> None:
    assert f"「{GAP_RULE}…」" in PROCEDURE
    assert "[卡片 <type>:<key>]" in PROCEDURE
    assert "推論" in PROCEDURE and "事實" in PROCEDURE
    assert "priority is never stored" in PROCEDURE and "judge it yourself" in PROCEDURE
    manifest = bi_knowledge_skill()
    assert manifest.metadata.identity == BI_SKILL and manifest.instructions == PROCEDURE


# -- correction notes, undo, demo --------------------------------------------


def _note(tmp_path: Path, card_id: str, body: dict[str, Any]) -> Any:
    """A correction note: previewed, then confirmed as previewed."""
    status, note = _call(tmp_path, "POST", "/api/bi/corrections/preview", {**body, "card": card_id})
    if status != 200:
        return status, note
    return _call(
        tmp_path,
        "POST",
        "/api/bi/corrections/apply",
        {"dataset": body["dataset"], "text": note["text"], "base_version": note["base_version"]},
    )


def test_the_field_route_is_gone(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    card = store.find("Competitor", "Keysight")
    assert card is not None
    before = store.fields(card["id"])
    status, answer = _call(
        tmp_path,
        "POST",
        f"/api/bi/cards/{card['id']}/field",
        {"dataset": "demo", "field": "ticker", "value": "X", "base_version": 1, "reason": "r"},
    )
    assert (status, answer["code"]) == (404, "route_unknown")
    assert store.fields(card["id"]) == before


def test_a_stale_note_is_refused_with_the_current_value(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    card = store.find("Competitor", "Keysight")
    assert card is not None
    body = {"dataset": "demo", "field": "ticker", "value": "KEYS2", "base_version": 1}
    status, answer = _note(tmp_path, card["id"], {**body, "reason": "r"})
    assert status == 200 and answer["ok"] is True and answer["version"] == 2
    status, answer = _note(tmp_path, card["id"], {**body, "value": "OTHER", "reason": "r"})
    assert status == 409
    assert answer["ok"] is False and answer["code"] == "stale_edit"
    assert answer["current"] == "KEYS2" and answer["by"] == f"{ACTOR} via web" and answer["at"]
    # A judgement field needs a reason (ADR-K11), and so does every note.
    status, answer = _note(
        tmp_path,
        card["id"],
        {"dataset": "demo", "field": "pricing_position", "value": "par", "base_version": 2},
    )
    assert status == 400 and answer["code"] == "reason_required"
    status, history = _call(tmp_path, "GET", f"/api/bi/cards/{card['id']}/history")
    assert history["history"][-1]["new"] == "KEYS2"
    assert set(history["history"][-1]) >= {"field", "old", "new", "source", "at", "by"}


def test_a_note_with_the_value_it_has_is_no_change(tmp_path: Path) -> None:
    """Live test 2026-10-24, owner decision: the current value again is no
    edit: 200 with `unchanged: true`, the same version, no history entry, the
    field's source kept and the published snapshot byte for byte the same.
    Values are compared normalised (enum case and aliases, a domain list's
    spelling, list whitespace), as an import compares them."""
    from aep_bi.cards import catalog
    from aep_bi.cards.snapshot import build_snapshot

    store = _loaded(tmp_path)
    reg = catalog.for_store(store)
    trend = store.find("Trend", "快充與高稼動電池")
    competitor = store.find("Competitor", "Keysight")
    assert trend is not None and competitor is not None
    before = build_snapshot(store)
    sources = {cid: store.fields(cid) for cid in (trend["id"], competitor["id"])}
    histories = {cid: store.history(cid) for cid in sources}
    trend_fields = sources[trend["id"]]
    alias = next(a for a, v in reg.enum_aliases["stage"].items() if v == "accelerating")
    domains = sources[competitor["id"]]["domain"]["value"]
    assert isinstance(domains, list) and domains
    assert "recent_moves" not in sources[competitor["id"]]
    same_values: list[tuple[Any, str, Any]] = [
        (trend, "stage", alias),  # an alias of the stored enum value
        (trend, "stage", "ACCELERATING"),  # another case
        (trend, "domain", "Robotics"),
        (trend, "market_impact", str(trend_fields["market_impact"]["value"])),
        (trend, "related_tech", [f"  {v} " for v in trend_fields["related_tech"]["value"]]),
        (trend, "related_tech", "；".join(trend_fields["related_tech"]["value"])),
        (competitor, "domain", [v.upper() for v in domains]),
        (competitor, "recent_moves", ""),  # empty for a field that has no value
        (competitor, "recent_moves", []),
    ]
    for card, field, value in same_values:
        status, answer = _note(
            tmp_path,
            card["id"],
            {
                "dataset": "demo",
                "field": field,
                "value": value,
                "base_version": card["version"],
                "reason": "same",
            },
        )
        assert (status, answer) == (
            200,
            {"ok": True, "version": card["version"], "unchanged": True},
        ), (field, value, answer)
    for cid in sources:
        assert store.fields(cid) == sources[cid]
        assert store.history(cid) == histories[cid]
        now = store.card(cid)
        assert now is not None
        assert now["version"] == (trend if cid == trend["id"] else competitor)["version"]
    assert build_snapshot(store) == before

    # A different value is still a change, with a new version and history.
    status, answer = _note(
        tmp_path,
        trend["id"],
        {
            "dataset": "demo",
            "field": "stage",
            "value": "peak",
            "base_version": trend["version"],
            "reason": "moved",
        },
    )
    assert status == 200 and answer["ok"] is True and answer["version"] == trend["version"] + 1
    assert len(store.history(trend["id"])) == len(histories[trend["id"]]) + 1


def test_the_store_returns_the_base_version_for_an_unchanged_edit(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    card = store.find("Competitor", "Keysight")
    assert card is not None
    current = store.fields(card["id"])["ticker"]["value"]
    version = card["version"]
    assert store.set_field(card["id"], "ticker", current, base_version=version, actor=ACTOR) == (
        version
    )
    assert store.set_field(card["id"], "ticker", "NEW", base_version=version, actor=ACTOR) == (
        version + 1
    )
    # A stale base is still refused, even for the value the card has now.
    with pytest.raises(BiStoreError) as stale:
        store.set_field(card["id"], "ticker", "NEW", base_version=version, actor=ACTOR)
    assert stale.value.code == "stale_edit"


def test_an_import_is_undone_as_a_whole(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    card = store.find("Trend", "快充與高稼動電池")
    assert card is not None
    old = store.fields(card["id"])["stage"]["value"]
    csv_text = "趨勢,領域,階段\n快充與高稼動電池,robotics,高峰\n全新趨勢,robotics,觀察\n"
    status, preview = _call(
        tmp_path,
        "POST",
        "/api/bi/import/preview",
        {"dataset": "demo", "filename": "u.csv", "csv_text": csv_text, "entity_type": "Trend"},
    )
    assert [r["action"] for r in preview["rows"]] == ["update", "create"]
    status, applied = _call(
        tmp_path, "POST", "/api/bi/import/apply", {"preview_id": preview["preview_id"]}
    )
    assert applied["applied"] == {"created": 1, "updated": 1, "unchanged": 0, "proposals": 0}
    assert store.fields(card["id"])["stage"]["value"] == "peak"
    status, answer = _call(
        tmp_path, "POST", "/api/bi/import/undo", {"import_id": applied["import_id"]}
    )
    assert (status, answer) == (200, {"ok": True})
    assert store.fields(card["id"])["stage"]["value"] == old
    assert store.fields(card["id"])["stage"]["kind"] == "fixture"
    assert store.find("Trend", "全新趨勢") is None
    assert len(store.card_rows()) == 104
    status, again = _call(
        tmp_path, "POST", "/api/bi/import/undo", {"import_id": applied["import_id"]}
    )
    assert status == 400 and again["code"] == "import_already_undone"
    # The history keeps the import and its undo.
    kinds = [h["source"]["kind"] for h in store.history(card["id"]) if h["field"] == "stage"]
    assert kinds == ["fixture", "import", "undo"]


def test_apply_takes_only_the_chosen_rows(tmp_path: Path) -> None:
    status, preview = _call(
        tmp_path,
        "POST",
        "/api/bi/import/preview",
        {"dataset": "demo", "filename": "a.csv", "csv_text": CSV, "entity_type": None},
    )
    status, applied = _call(
        tmp_path,
        "POST",
        "/api/bi/import/apply",
        {"preview_id": preview["preview_id"], "rows": [2]},
    )
    assert applied["applied"]["created"] == 1
    status, cards = _call(tmp_path, "GET", "/api/bi/cards", dataset="demo")
    assert [c["name"] for c in cards["cards"]] == ["測試應用甲"]
    status, answer = _call(tmp_path, "POST", "/api/bi/import/apply", {"preview_id": "nope"})
    assert status == 404 and answer["code"] == "preview_unknown"


def test_the_demo_load_is_idempotent_and_never_trusted(tmp_path: Path) -> None:
    status, first = _call(tmp_path, "POST", "/api/bi/demo/load", {"dataset": "demo"})
    assert (status, first) == (
        200,
        {"ok": True, "imported": {"created": 104, "updated": 0, "unchanged": 0}},
    )
    status, second = _call(tmp_path, "POST", "/api/bi/demo/load", {"dataset": "demo"})
    assert second["imported"] == {"created": 0, "updated": 0, "unchanged": 104}
    status, cards = _call(tmp_path, "GET", "/api/bi/cards")
    assert len(cards["cards"]) == 104
    assert {c["review_status"] for c in cards["cards"]} == {"draft"}
    assert (tmp_path / "bi" / "demo" / "bi.sqlite").is_file()


# -- the API contract ------------------------------------------------------


def test_the_api_answers_the_contract_shapes(tmp_path: Path) -> None:
    status, schema = _call(tmp_path, "GET", "/api/bi/schema")
    assert status == 200 and len(schema["types"]) == 12
    field = schema["types"][0]["fields"][0]
    assert set(field) == {"name", "label", "type", "class", "enum", "link_to", "list"}
    assert _call(tmp_path, "GET", "/api/bi/datasets") == (200, {"datasets": []})
    _call(tmp_path, "POST", "/api/bi/demo/load", {"dataset": "demo"})
    status, found = _call(tmp_path, "GET", "/api/bi/datasets")
    assert found["datasets"][0]["name"] == "demo" and found["datasets"][0]["cards"] == 104
    status, listed = _call(
        tmp_path, "GET", "/api/bi/cards", dataset="demo", type="Application", q="BMS"
    )
    assert len(listed["cards"]) == 1
    summary = listed["cards"][0]
    assert {
        "id",
        "entity_type",
        "canonical_key",
        "name",
        "review_status",
        "updated",
        "fields",
    } <= set(summary)
    status, robotics = _call(tmp_path, "GET", "/api/bi/cards", domain="robotics", type="Node")
    status, wireless = _call(tmp_path, "GET", "/api/bi/cards", domain="wireless", type="Node")
    assert len(robotics["cards"]) == 12 and len(wireless["cards"]) == 1  # X-Certification-Lab
    status, detail = _call(tmp_path, "GET", f"/api/bi/cards/{summary['id']}")
    assert status == 200 and detail["card"]["version"] == 1
    assert detail["card"]["domain"] == "robotics"
    field = detail["fields"][0]
    assert set(field) == {"field", "label", "value", "class", "source", "history", "retired"}
    assert set(field["source"]) == {"kind", "ref", "at", "by"}
    assert detail["links"] and set(detail["links"][0]) == {
        "field",
        "target_id",
        "target_key",
        "missing",
    }
    assert detail["proposals"] == []
    status, preview = _call(
        tmp_path,
        "POST",
        "/api/bi/import/preview",
        {"dataset": "demo", "filename": "a.csv", "csv_text": CSV, "entity_type": None},
    )
    assert set(preview) == {"preview_id", "entity_type", "columns", "rows", "summary"}
    assert set(preview["columns"][0]) == {"source", "field", "status", "note"}
    assert set(preview["rows"][0]) == {"row", "canonical_key", "action", "fields", "warnings"}
    assert set(preview["rows"][0]["fields"][0]) == {
        "field",
        "raw",
        "normalized",
        "current",
        "change",
    }
    assert set(preview["summary"]) == {"create", "update", "unchanged", "skip", "warnings"}
    for bad in (
        _call(tmp_path, "GET", "/api/bi/cards/nope"),
        _call(tmp_path, "GET", "/api/bi/nothing"),
        _call(tmp_path, "POST", "/api/bi/import/preview", {"csv_text": ""}),
        _call(tmp_path, "GET", "/api/bi/cards", dataset="../x"),
    ):
        assert 400 <= bad[0] < 500 and bad[1]["ok"] is False
        assert {"code", "message"} <= set(bad[1])


def test_the_routes_are_served_behind_the_token(served: Any) -> None:  # noqa: F811
    web, server, _recorder, _ = served
    port = server.server_address[1]

    def ask(path: str, token: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as reply:
                return reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    assert ask("/api/bi/schema", "wrong")[0] == 401
    assert ask("/api/bi/demo/load", "wrong", {})[0] == 401
    status, loaded = ask("/api/bi/demo/load", server.token, {"dataset": "demo"})
    assert status == 200 and loaded["imported"]["created"] == 104
    status, board = ask("/api/bi/dashboard?dataset=demo&domain=robotics", server.token)
    assert status == 200 and board["domain"] == "robotics"
    assert (web.runtime.layout.workspace_root / "bi" / "demo" / "bi.sqlite").is_file()


# -- dashboard: the sample's intentional gaps (the built-in pack's analyses, BI P5) --


@pytest.fixture
def board(tmp_path: Path) -> dict[str, Any]:
    return bi_board.board(tmp_path, _loaded(tmp_path), "robotics", False, {})


def _levels(section: dict[str, Any]) -> dict[str, str]:
    return {_label(section["rows"][f["row"]][0]): f["level"] for f in section["flags"]}


def _row(section: dict[str, Any], name: str) -> list[Any]:
    return next(r for r in section["rows"] if _label(r[0]) == name)


def test_dashboard_shape(board: dict[str, Any]) -> None:
    assert board["source"] == "pack"
    assert [s["id"] for s in board["sections"]][:6] == [
        "gaps", "trend-coverage", "demand-without-opportunity", "solutions-vs-opportunities",
        "funnel", "technologies-without-concept"]  # fmt: skip
    assert board["sections"][-1]["id"] == "Q"
    for section in board["sections"]:
        assert section["kind"] == "table"
        assert all(len(row) == len(section["columns"]) for row in section["rows"])
        assert all(f["level"] in ("red", "warn") for f in section["flags"])


def test_dashboard_bms_and_eol_have_competitors_but_no_solution_of_ours(
    board: dict[str, Any],
) -> None:
    gaps = _section(board, "gaps")
    red = {k for k, level in _levels(gaps).items() if level == "red"}
    assert red == {"AMR 電池包 BMS 與充電驗證", "機器人產線下線測試"}
    assert "對手有、我方無" in _row(gaps, "AMR 電池包 BMS 與充電驗證")
    assert "優先度" not in gaps["columns"]


def test_dashboard_bms_has_demand_but_no_opportunity(board: dict[str, Any]) -> None:
    section = _section(board, "demand-without-opportunity")
    assert _levels(section) == {"AMR 電池包 BMS 與充電驗證": "warn"}


def test_dashboard_the_fast_charging_trend_has_no_solution(board: dict[str, Any]) -> None:
    assert _levels(_section(board, "trend-coverage")) == {"快充與高稼動電池": "warn"}


def test_dashboard_the_hiwin_mikrosystem_product_has_no_ecosystem(board: dict[str, Any]) -> None:
    assert _levels(_section(board, "product-completeness")) == {"大銀 直驅馬達伺服模組": "warn"}


def test_dashboard_the_5g_private_network_solution_has_no_active_opportunity(
    board: dict[str, Any],
) -> None:
    section = _section(board, "solutions-vs-opportunities")
    assert _levels(section) == {"R&S 5G 私有網路機器人連線驗證方案": "warn"}


def test_dashboard_lists_technologies_missing_a_concept(board: dict[str, Any]) -> None:
    section = _section(board, "technologies-without-concept")
    missing = {_label(r[0]) for r in section["rows"] if "缺 Concept" in r}
    assert missing == {"5G-Private-Network", "BMS-Fast-Charging", "Edge-AI-SoC"}


def test_dashboard_trend_priority_is_computed_and_the_funnel_counts_stages(
    board: dict[str, Any],
) -> None:
    trends = _section(board, "trend-priority")
    assert all(row[5] == row[3] * row[4] for row in trends["rows"])
    assert [row[5] for row in trends["rows"]] == sorted(
        (row[5] for row in trends["rows"]), reverse=True
    )
    funnel = _section(board, "funnel")
    assert funnel["chart"]["type"] == "bar" and sum(row[1] for row in funnel["rows"]) == 7
    assert len(_section(board, "node-technology")["rows"]) == 13


def test_the_stale_section_uses_ninety_days(tmp_path: Path) -> None:
    from datetime import date, timedelta

    store = _loaded(tmp_path)
    later = (date.today() + timedelta(days=91)).isoformat()
    (section,) = bi_board.pack_sections(tmp_path, store, "stale", {"today": later})
    assert len(section["rows"]) == 103  # X-Certification-Lab is wireless
    assert bi_board.pack_sections(tmp_path, store, "stale", {})[0]["rows"] == []


# -- default on ------------------------------------------------------------


def test_the_skill_is_installed_switched_on_and_offers_the_tool(tmp_path: Path) -> None:
    """An existing PC (installed before this Skill shipped) gets it switched
    on by the next install-bundled; the Host then offers `bi__query`."""
    config, layout = ready(tmp_path)
    older = tuple(m for m in shipped() if m.metadata.identity != BI_SKILL)
    skill_packs.install_bundle(layout, None, shipped=older)
    name = f"{BI_SKILL.namespace}__{BI_SKILL.name}__{BI_SKILL.version}.json"
    assert not (layout.skills / name).exists()
    skill_packs.install_bundle(layout, None, shipped=shipped())
    assert (layout.skills / name).exists()
    runtime = build_runtime(config, layout=layout)
    offered = {
        m.metadata.identity for m in runtime.agent.gateway.router.commands.skills.manifests()
    }
    assert BI_SKILL in offered
    tools = bi_cards_tools(runtime.agent.gateway)
    assert [t.tool.name for t in tools] == [TOOL_NAME, ATLAS_TOOL]
    assert GAP_RULE in tools[0].tool.description


def test_the_tool_names_the_vaults_by_purpose_and_queries_one(tmp_path: Path) -> None:
    """BI vaults V6: the model picks a vault by its stated purpose and queries
    it like any dataset; the query reads what the shared folder holds."""
    from aep_bi.cards import vault

    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    runtime = build_runtime(config, layout=layout)
    workspace = layout.workspace_root
    assert "SHARED KNOWLEDGE BASES" not in bi_cards_tools(runtime.agent.gateway)[0].tool.description
    _loaded(workspace)
    shared = tmp_path / "shared"
    shared.mkdir()
    made = vault.convert(
        workspace,
        {
            "dataset": "demo",
            "path": str(shared),
            "title": "市場訊號",
            "purpose": "虛構範例：看市場需求與訊號，對應我們的產品",
        },  # fmt: skip
        ACTOR,
    )
    dataset = made["vault"]["dataset"]
    description = bi_cards_tools(runtime.agent.gateway)[0].tool.description
    assert f"dataset {dataset}: 「市場訊號」 — 虛構範例：看市場需求與訊號" in description
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor=ACTOR,
        namespace="engineering",
        message="bi",
        channel="local",
        session_id="s-1",
    )
    result = asyncio.run(
        QueryHandler(workspace)(context, QueryRequest(dataset=dataset, text="BMS", limit=5))
    )
    assert result.model_dump()["total"] >= 1


def test_a_switched_off_skill_offers_no_tool(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    from host_runtime import asset_shelf

    asset_shelf.switch_off(layout, "skill", BI_SKILL)
    runtime = build_runtime(config, layout=layout)
    assert bi_cards_tools(runtime.agent.gateway) == []
    assert isinstance(HostLayout.under(tmp_path / "x"), HostLayout)


def test_set_field_on_an_unknown_card_is_refused(tmp_path: Path) -> None:
    store = _loaded(tmp_path)
    with pytest.raises(BiStoreError):
        store.set_field("nope", "name", "x", base_version=1, actor=ACTOR)


def test_a_bi_question_is_not_sent_to_the_knowledge_vault() -> None:
    """Live: 「哪些客戶產品有需求但還沒有商機？」 matched the vault Skill's intent
    words and went to the vault; BI words now keep it with bi__query."""
    from aep_bi.cards.manifest import bi_question

    assert bi_question("哪些客戶產品有需求但還沒有商機？")
    assert bi_question("哪些應用是對手有方案、我方沒有的缺口？")
    assert bi_question("Which competitor test solution covers Wi-Fi 7?")
    assert not bi_question("RS 某型號的規格是什麼？")
    assert not bi_question("幫我整理今天的郵件")


def test_a_dataset_that_does_not_exist_is_404_on_every_read(tmp_path: Path) -> None:
    """Live test 2026-10-24: an unknown name read as an empty dataset (200, 0
    cards). Every read of one dataset now answers 404 `dataset_unknown`, as
    `bi__query` does, for an unknown own name and an unknown subscribed one;
    `demo` before anything is loaded stays an empty dataset, which is how the
    page first opens."""
    # Nothing at all yet: demo (named or by default) reads as empty.
    for query in ({}, {"dataset": "demo"}):
        status, answer = _call(tmp_path, "GET", "/api/bi/cards", **query)
        assert (status, answer) == (200, {"cards": []}), query
        assert _call(tmp_path, "GET", "/api/bi/dashboard", **query)[0] == 200
        assert _call(tmp_path, "GET", "/api/bi/schema", **query)[0] == 200
    store = _loaded(tmp_path)
    card = store.card_rows()[0]["id"]
    reads = [
        "/api/bi/cards",
        f"/api/bi/cards/{card}",
        f"/api/bi/cards/{card}/history",
        "/api/bi/dashboard",
        "/api/bi/schema",
    ]
    for name in ("nosuch", "engineering/not-subscribed"):
        for path in reads:
            status, answer = _call(tmp_path, "GET", path, dataset=name)
            assert status == 404 and answer["ok"] is False, (name, path, answer)
            assert answer["code"] == "dataset_unknown" and name in answer["message"]
    # The shipped schema without a dataset, and the dataset list, still answer.
    assert _call(tmp_path, "GET", "/api/bi/schema")[0] == 200
    assert _call(tmp_path, "GET", "/api/bi/datasets")[0] == 200
    # An existing dataset reads as before.
    assert _call(tmp_path, "GET", f"/api/bi/cards/{card}", dataset="demo")[0] == 200
    # A name that is not a dataset name at all stays 400.
    assert _call(tmp_path, "GET", "/api/bi/cards", dataset="no such")[0] == 400
