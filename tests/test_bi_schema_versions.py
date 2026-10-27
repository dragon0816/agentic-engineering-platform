"""BI ingest phase 2 (owner 2026-10-27; `docs/phases/BI_INGEST.md` §5).

Schema drafts with immutable revisions, diffs and revert; publishing a
revision as a new version, including a local `bi.schema/v1.1` version that
must keep every shipped type and field; and moving a dataset to another
version of its schema: the impact preview writes nothing, a removed field
keeps its values (hidden, not searched, not shared), a declared rename moves
values with history, breaking changes are refused, and a stale preview is
refused. Every test uses a temporary workspace and the `/api/bi/*` routes.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog, schema_versions, service
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route

ACTOR = "tester"
EXAMPLE = "example/product-spec@1.0.0"


def _call(tmp_path: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(tmp_path, ACTOR, method, path, query, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _refused(answer: Any, status: int, code: str) -> dict[str, Any]:
    assert (answer[0], answer[1].get("code")) == (status, code), answer
    return dict(answer[1])


def _draft(tmp_path: Path, base: str) -> dict[str, Any]:
    return _ok(_call(tmp_path, "POST", "/api/bi/schema-drafts", {"base": base, "title": "試做"}))


def _save(tmp_path: Path, draft_id: str, document: dict[str, Any], note: str = "") -> Any:
    return _call(
        tmp_path,
        "POST",
        f"/api/bi/schema-drafts/{draft_id}/revisions",
        {"document": document, "note": note},
    )


def _type(document: dict[str, Any], name: str) -> dict[str, Any]:
    return next(t for t in document["types"] if t["name"] == name)


def _example_dataset(tmp_path: Path) -> None:
    """The 「產品規格」 example installed, a dataset on it, and its suppliers."""
    example = catalog.example()
    _ok(_call(tmp_path, "POST", "/api/bi/schemas/install", example["schema"]))
    _ok(_call(tmp_path, "POST", "/api/bi/datasets", {"name": "spec", "schema": EXAMPLE}))
    suppliers = next(c for c in example["csv"] if c["entity_type"] == "Supplier")
    source = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/sources",
            {"dataset": "spec", "name": "suppliers.csv", "text": suppliers["text"]},
        )
    )["source"]
    run = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/runs",
            {
                "dataset": "spec",
                "kind": "ingest",
                "source_id": source["id"],
                "entity_type": "Supplier",
            },
        )
    )["run"]
    for candidate in _ok(_call(tmp_path, "GET", f"/api/bi/runs/{run['id']}", dataset="spec"))[
        "candidates"
    ]:
        _ok(
            _call(
                tmp_path,
                "POST",
                f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}",
                {"dataset": "spec", "review": "accepted"},
            )
        )
    _ok(_call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": "spec"}))


def _publish_example_v2(tmp_path: Path, change: Any) -> str:
    draft = _draft(tmp_path, EXAMPLE)
    document = copy.deepcopy(draft["document"])
    change(document)
    saved = _ok(_save(tmp_path, draft["draft"]["id"], document))
    assert saved["errors"] == [], saved["errors"]
    published = _ok(
        _call(tmp_path, "POST", f"/api/bi/schema-drafts/{draft['draft']['id']}/publish", {})
    )
    return str(published["ref"])


def test_a_draft_starts_from_its_base_with_the_next_version(tmp_path: Path) -> None:
    draft = _draft(tmp_path, "bi.schema/v1.1")
    assert draft["draft"]["base_ref"] == "bi.schema/v1.1@1.1.0"
    assert draft["document"]["version"] == "1.2.0" and draft["revision"] == 1
    assert draft["errors"] == [] and draft["diff"] == []
    listed = _ok(_call(tmp_path, "GET", "/api/bi/schema-drafts"))["drafts"]
    assert [d["id"] for d in listed] == [draft["draft"]["id"]] and listed[0]["valid"]


def test_revisions_are_kept_compared_and_reverted(tmp_path: Path) -> None:
    draft = _draft(tmp_path, "bi.schema/v1.1")
    draft_id = draft["draft"]["id"]
    document = copy.deepcopy(draft["document"])
    tech = _type(document, "Technology")
    tech["fields"].append(
        {
            "name": "price_band",
            "label": "價格帶",
            "kind": "str",
            "class": "sourced",
            "required": False,
        }
    )
    maturity = next(f for f in tech["fields"] if f["name"] == "maturity")
    maturity["enum"] = [*maturity["enum"], "legacy"]
    second = _ok(_save(tmp_path, draft_id, document, "加價格帶"))
    assert second["revision"] == 2 and second["errors"] == []
    assert {(c["change"], c["breaking"]) for c in second["diff"]} == {
        ("field_added", False),
        ("enum_added", False),
    }
    broken = copy.deepcopy(document)
    _type(broken, "Technology")["fields"] = [
        f for f in _type(broken, "Technology")["fields"] if f["name"] != "standard_body"
    ]
    third = _ok(_save(tmp_path, draft_id, broken))
    assert third["revision"] == 3 and third["draft"]["revisions"][-1]["valid"] is False
    assert any("standard_body" in e["path"] for e in third["errors"])
    assert any(c["change"] == "field_removed" and c["breaking"] for c in third["diff"])
    between = _ok(
        _call(tmp_path, "GET", f"/api/bi/schema-drafts/{draft_id}/diff", **{"from": "2", "to": "3"})
    )
    assert [c["field"] for c in between["diff"]] == ["standard_body"]
    reverted = _ok(_call(tmp_path, "POST", f"/api/bi/schema-drafts/{draft_id}/revert", {"rev": 2}))
    assert reverted["revision"] == 4 and reverted["document"] == second["document"]
    assert reverted["draft"]["revisions"][-1]["copied_from"] == 2
    old = _ok(_call(tmp_path, "GET", f"/api/bi/schema-drafts/{draft_id}/revisions/3"))
    assert old["document"] == broken
    _refused(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/schema-drafts/{draft_id}/revisions",
            {"json_text": "{not json"},
        ),
        400,
        "schema_json_invalid",
    )
    renamed = {**document, "schema_id": "example/other"}
    _refused(_save(tmp_path, draft_id, renamed), 400, "schema_id_changed")
    _refused(_call(tmp_path, "GET", "/api/bi/schema-drafts/0123456789ab"), 404, "draft_unknown")


def test_a_compatible_local_bi_version_installs_and_keeps_the_dashboard(tmp_path: Path) -> None:
    draft = _draft(tmp_path, "bi.schema/v1.1")
    draft_id = draft["draft"]["id"]
    document = copy.deepcopy(draft["document"])
    _type(document, "Technology")["fields"].append(
        {"name": "price_band", "label": "價格帶", "kind": "str", "class": "sourced"}
    )
    _ok(_save(tmp_path, draft_id, document))
    published = _ok(_call(tmp_path, "POST", f"/api/bi/schema-drafts/{draft_id}/publish", {}))
    assert published["ref"] == "bi.schema/v1.1@1.2.0" and published["already"] is False
    again = _ok(_call(tmp_path, "POST", f"/api/bi/schema-drafts/{draft_id}/publish", {}))
    assert again["already"] is True
    listed = {s["ref"]: s for s in _ok(_call(tmp_path, "GET", "/api/bi/schemas"))["schemas"]}
    assert listed["bi.schema/v1.1@1.2.0"]["dashboard"] is True
    service.load_demo(BiStore(tmp_path))
    preview = _ok(
        _call(
            tmp_path, "POST", "/api/bi/datasets/demo/schema/preview", {"to": "bi.schema/v1.1@1.2.0"}
        )
    )
    assert preview["blocked"] == [] and preview["from"] == "bi.schema/v1.1@1.1.0"
    _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/datasets/demo/schema/apply",
            {"to": "bi.schema/v1.1@1.2.0", "preview_token": preview["preview_token"]},
        )
    )
    assert BiStore(tmp_path).schema_ref() == "bi.schema/v1.1@1.2.0"
    board = _ok(_call(tmp_path, "GET", "/api/bi/dashboard", dataset="demo"))
    assert board["sections"]
    schema = _ok(_call(tmp_path, "GET", "/api/bi/schema", dataset="demo"))
    tech = next(t for t in schema["types"] if t["name"] == "Technology")
    assert schema["bi"] is True and "price_band" in [f["name"] for f in tech["fields"]]


def test_an_incompatible_or_older_bi_version_is_refused(tmp_path: Path) -> None:
    draft = _draft(tmp_path, "bi.schema/v1.1")
    draft_id = draft["draft"]["id"]
    document = copy.deepcopy(draft["document"])
    tech = _type(document, "Technology")
    tech["fields"] = [f for f in tech["fields"] if f["name"] != "standard_body"]
    _ok(_save(tmp_path, draft_id, document))
    refused = _refused(
        _call(tmp_path, "POST", f"/api/bi/schema-drafts/{draft_id}/publish", {}),
        400,
        "schema_bi_not_compatible",
    )
    assert any("standard_body" in e["path"] for e in refused["errors"])
    older = copy.deepcopy(draft["document"])
    older["version"] = "1.0.5"
    _ok(_save(tmp_path, draft_id, older))
    _refused(
        _call(tmp_path, "POST", f"/api/bi/schema-drafts/{draft_id}/publish", {}),
        409,
        "schema_version_not_newer",
    )


def _drop_enum_value(document: dict[str, Any], type_name: str, field: str, value: str) -> None:
    item = next(f for f in _type(document, type_name)["fields"] if f["name"] == field)
    item["enum"] = [v for v in item["enum"] if v != value]
    aliases = document.get("enum_aliases", {}).get(field, {})
    for alias in [a for a, v in aliases.items() if v == value]:
        del aliases[alias]


def _reshape(document: dict[str, Any]) -> None:
    """Supplier: `contact` removed, `country` renamed `region`, a new required
    `site` field, and the tier `approved` retired."""
    supplier = _type(document, "Supplier")
    supplier["fields"] = [f for f in supplier["fields"] if f["name"] not in ("contact", "country")]
    supplier["fields"].append(
        {"name": "region", "label": "地區", "kind": "str", "class": "sourced"}
    )
    supplier["fields"].append(
        {"name": "site", "label": "廠區", "kind": "str", "class": "sourced", "required": True}
    )
    _drop_enum_value(document, "Supplier", "tier", "approved")
    document["migrations"] = {"renames": {"Supplier.country": "region"}}


def test_a_dataset_upgrade_hides_moves_and_flags_but_never_rewrites(tmp_path: Path) -> None:
    _example_dataset(tmp_path)
    store = BiStore(tmp_path, "spec")
    murata = next(c for c in store.card_rows() if c["name"] == "村田製作所")
    before_fields = store.fields(murata["id"])
    target = _publish_example_v2(tmp_path, _reshape)
    snapshot = store.path.read_bytes()
    preview = _ok(_call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": target}))
    assert store.path.read_bytes() == snapshot
    supplier = next(t for t in preview["types"] if t["type"] == "Supplier")
    assert {h["field"] for h in supplier["hidden"]} == {"contact"}
    assert [(r["from"], r["to"]) for r in supplier["renamed"]] == [("country", "region")]
    assert supplier["required_missing"] == [{"field": "site", "cards": supplier["cards"]}]
    assert {r["value"] for r in supplier["retired"]} == {"approved"}
    assert preview["blocked"] == []
    assert any(c["change"] == "renamed" for c in preview["diff"])
    done = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/datasets/spec/schema/apply",
            {"to": target, "preview_token": preview["preview_token"]},
        )
    )
    assert done["moved"] == supplier["cards"] and store.schema_ref() == target
    after = store.fields(murata["id"])
    assert after["region"]["value"] == before_fields["country"]["value"]
    assert after["region"]["ref"] == before_fields["country"]["ref"]
    assert after["contact"] == before_fields["contact"]
    assert after["tier"]["value"] == "approved"
    detail = _ok(_call(tmp_path, "GET", f"/api/bi/cards/{murata['id']}", dataset="spec"))
    retired = {f["field"]: f["retired"] for f in detail["fields"]}
    assert retired["contact"] is True and retired["region"] is False
    history = _ok(_call(tmp_path, "GET", f"/api/bi/cards/{murata['id']}/history", dataset="spec"))
    assert {h["source"]["kind"] for h in history["history"][-2:]} == {"migration"}
    contact = before_fields["contact"]["value"]
    found = _ok(_call(tmp_path, "GET", "/api/bi/cards", dataset="spec", q=contact))["cards"]
    assert found == []
    assert store.schema_history()[-1]["to"] == target
    back = _ok(_call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": EXAMPLE}))
    _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/datasets/spec/schema/apply",
            {"to": EXAMPLE, "preview_token": back["preview_token"]},
        )
    )
    found = _ok(_call(tmp_path, "GET", "/api/bi/cards", dataset="spec", q=contact))["cards"]
    assert [c["id"] for c in found] == [murata["id"]]


def test_a_stale_preview_and_breaking_upgrades_are_refused(tmp_path: Path) -> None:
    _example_dataset(tmp_path)
    store = BiStore(tmp_path, "spec")
    target = _publish_example_v2(tmp_path, _reshape)
    preview = _ok(_call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": target}))
    card = store.card_rows()[0]
    store.set_field(card["id"], "body", "改過", base_version=card["version"], actor=ACTOR)
    _refused(
        _call(
            tmp_path,
            "POST",
            "/api/bi/datasets/spec/schema/apply",
            {"to": target, "preview_token": preview["preview_token"]},
        ),
        409,
        "preview_stale",
    )
    assert store.schema_ref() == EXAMPLE

    def retype(document: dict[str, Any]) -> None:
        tier = next(f for f in _type(document, "Supplier")["fields"] if f["name"] == "country")
        tier.update({"kind": "list"})
        document["version"] = "1.3.0"

    breaking = _publish_example_v2(tmp_path, retype)
    preview = _ok(_call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": breaking}))
    assert [b["code"] for b in preview["blocked"]] == ["kind_changed"]
    refused = _refused(
        _call(
            tmp_path,
            "POST",
            "/api/bi/datasets/spec/schema/apply",
            {"to": breaking, "preview_token": preview["preview_token"]},
        ),
        409,
        "schema_upgrade_breaking",
    )
    assert refused["blocked"][0]["code"] == "kind_changed"
    _refused(
        _call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": EXAMPLE}),
        400,
        "schema_same",
    )
    _refused(
        _call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": "bi.schema/v1.1"}),
        400,
        "schema_id_different",
    )


def test_a_removed_type_with_cards_blocks_the_upgrade(tmp_path: Path) -> None:
    _example_dataset(tmp_path)

    def drop_supplier(document: dict[str, Any]) -> None:
        document["types"] = [t for t in document["types"] if t["name"] != "Supplier"]
        for item in _type(document, "Component")["fields"]:
            if item["name"] == "supplier":
                item.update({"kind": "str", "link_to": []})
        document["enum_aliases"].pop("tier", None)

    target = _publish_example_v2(tmp_path, drop_supplier)
    preview = _ok(_call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": target}))
    assert [b["code"] for b in preview["blocked"]] == ["type_removed"]


def test_a_run_from_before_an_upgrade_must_be_run_again(tmp_path: Path) -> None:
    _example_dataset(tmp_path)
    store = BiStore(tmp_path, "spec")
    source = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/sources",
            {"dataset": "spec", "name": "s2.csv", "text": "供應商名稱,國家\n新供應商,台灣\n"},
        )
    )["source"]
    run = _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/runs",
            {
                "dataset": "spec",
                "kind": "ingest",
                "source_id": source["id"],
                "entity_type": "Supplier",
            },
        )
    )["run"]
    target = _publish_example_v2(tmp_path, _reshape)
    preview = _ok(_call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": target}))
    _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/datasets/spec/schema/apply",
            {"to": target, "preview_token": preview["preview_token"]},
        )
    )
    _refused(
        _call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": "spec"}),
        409,
        "schema_changed",
    )
    assert store.schema_ref() == target


def test_a_shared_snapshot_leaves_out_hidden_values(tmp_path: Path) -> None:
    from capabilities.bi_cards import snapshot

    _example_dataset(tmp_path)
    target = _publish_example_v2(tmp_path, _reshape)
    preview = _ok(_call(tmp_path, "POST", "/api/bi/datasets/spec/schema/preview", {"to": target}))
    _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/datasets/spec/schema/apply",
            {"to": target, "preview_token": preview["preview_token"]},
        )
    )
    built = snapshot.build_snapshot(BiStore(tmp_path, "spec"))
    import gzip

    document = json.loads(gzip.decompress(built))
    names = {f for card in document["cards"] for f in card["fields"]}
    assert "contact" not in names and "region" in names
    assert schema_versions.drafts(tmp_path)
