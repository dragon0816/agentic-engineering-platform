"""BI dataset sharing slice 1, the Agent side (owner 2026-10-22;
`docs/proposals/BI_DATASET_SHARING.md` §4, §8.2 items 4–7 and 9, §8.5 Q2,
§8.6): subscribed read-only copies, the schema travelling with the snapshot,
the update badge and the manual update, a copy kept and stopped when access
is withdrawn, the offline status, the subscription routes and `bi__query`
citing the version. Every test uses a temporary workspace.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import served  # noqa: F401 - the server fixture

from capabilities.bi_cards import catalog, service, subscriptions
from capabilities.bi_cards.capability import QueryHandler, QueryRequest
from capabilities.bi_cards.manifest import PROCEDURE
from capabilities.bi_cards.snapshot import (
    Publication,
    build_snapshot,
    read_snapshot,
    stamp_publication,
)
from capabilities.bi_cards.store import BiStore, BiStoreError, datasets
from capabilities.bi_cards.subscriptions import Offer, SubscriptionError
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.bi_cards_api import route

DATASET = "engineering/robotics-bi"
ACTOR = "tester"


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _owner(tmp_path: Path) -> BiStore:
    store = BiStore(tmp_path / "owner", "robotics")
    service.load_demo(store)
    return store


def _published(
    store: BiStore, version: str = "1.0.0", *, base: str | None = None, by: str = "leo.chi"
) -> tuple[bytes, str]:
    """A snapshot as the platform stores it: built, then stamped."""
    snapshot = read_snapshot(build_snapshot(store))
    stamped = stamp_publication(
        snapshot,
        Publication(
            namespace="engineering",
            name="robotics-bi",
            version=version,
            base_version=base,
            published_by=by,
            published_at="2026-10-22T02:00:00+00:00",
            note=f"version {version}",
        ),
    )
    return stamped, hashlib.sha256(stamped).hexdigest()


def _subscribe(workspace: Path, owner: BiStore, version: str = "1.0.0") -> dict[str, Any]:
    raw, sha = _published(owner, version)
    return subscriptions.install(workspace, "engineering", "robotics-bi", version, raw, sha)


def _call(workspace: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(workspace, ACTOR, method, path, query, body)


# -- item 5: the subscribed copy reads like the owner's, and is read only ---


def test_a_subscribed_copy_answers_cards_and_dashboard_like_the_owner(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    assert _subscribe(reader, owner)["already"] is False

    root = reader / "bi" / "subscribed" / "engineering__robotics-bi"
    assert (root / "1.0.0" / "bi.sqlite").is_file()
    assert (root / "subscription.json").is_file()

    mine = route(tmp_path / "owner", ACTOR, "GET", "/api/bi/cards", {"dataset": "robotics"}, None)
    theirs = _call(reader, "GET", "/api/bi/cards", dataset=DATASET)
    assert mine[0] == theirs[0] == 200
    key = ("entity_type", "canonical_key", "name", "synthetic", "fields")
    assert [tuple(c[k] for k in key) for c in mine[1]["cards"]] == [
        tuple(c[k] for k in key) for c in theirs[1]["cards"]
    ]
    assert len(theirs[1]["cards"]) == 104

    board_mine = route(
        tmp_path / "owner", ACTOR, "GET", "/api/bi/dashboard", {"dataset": "robotics"}, None
    )
    board_theirs = _call(reader, "GET", "/api/bi/dashboard", dataset=DATASET)
    assert json.dumps(board_mine[1]["sections"], sort_keys=True) == json.dumps(
        board_theirs[1]["sections"], sort_keys=True
    )

    card = theirs[1]["cards"][0]["id"]
    status, detail = _call(reader, "GET", f"/api/bi/cards/{card}", dataset=DATASET)
    assert status == 200 and detail["fields"]
    status, history = _call(reader, "GET", f"/api/bi/cards/{card}/history", dataset=DATASET)
    assert status == 200 and history["history"]


def test_every_write_to_a_subscribed_copy_is_refused_409(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    before = _tree(reader)
    card = _call(reader, "GET", "/api/bi/cards", dataset=DATASET)[1]["cards"][0]
    writes = [
        ("/api/bi/import/preview", {"dataset": DATASET, "csv_text": "name\nx\n"}),
        ("/api/bi/import/undo", {"dataset": DATASET, "import_id": "abc"}),
        ("/api/bi/demo/load", {"dataset": DATASET}),
        (
            f"/api/bi/cards/{card['id']}/field",
            {"dataset": DATASET, "field": "name", "value": "x", "base_version": 1},
        ),
    ]
    for path, body in writes:
        status, reply = _call(reader, "POST", path, body)
        assert (status, reply["code"]) == (409, "dataset_read_only"), path
    # The store refuses too, whoever calls it.
    store = BiStore(reader, DATASET)
    assert store.read_only
    for attempt in (
        lambda: store.set_field(card["id"], "name", "x", base_version=1, actor="x"),
        lambda: store.undo_import("abc", actor="x"),
        lambda: store.create("bi.schema/v1.1@1.1.0"),
        lambda: service.load_demo(store),
    ):
        with pytest.raises(BiStoreError) as refused:
            attempt()
        assert refused.value.code == "dataset_read_only"
    assert _tree(reader) == before


def test_subscribed_and_schemas_are_not_dataset_names(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    catalog.install(reader, "product-spec@1.0.0.json", catalog.example()["schema"]["json_text"])
    BiStore(reader, "mine").create("bi.schema/v1.1@1.1.0")
    assert datasets(reader) == ["mine"]
    for reserved in ("subscribed", "schemas", "Subscribed"):
        status, reply = _call(
            reader, "POST", "/api/bi/datasets", {"name": reserved, "schema": "bi.schema/v1.1"}
        )
        assert (status, reply["code"]) == (400, "dataset_invalid"), reserved

    status, listed = _call(reader, "GET", "/api/bi/datasets")
    assert status == 200
    local, shared = listed["datasets"]
    assert local["name"] == "mine" and local["read_only"] is False
    assert local["subscribed"] is False
    assert shared["name"] == DATASET and shared["subscribed"] is True
    assert shared["read_only"] is True and shared["version"] == "1.0.0"
    assert shared["published_by"] == "leo.chi" and shared["status"] == "current"
    assert shared["cards"] == 104 and shared["dashboard"] is True


# -- item 4: verified, all or nothing, idempotent, schema travels ----------


def test_a_digest_mismatch_installs_nothing(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    reader.mkdir()
    raw, sha = _published(owner)
    with pytest.raises(SubscriptionError) as refused:
        subscriptions.install(reader, "engineering", "robotics-bi", "1.0.0", raw + b"x", sha)
    assert refused.value.code == "artifact_hash_mismatch"
    with pytest.raises(SubscriptionError) as wrong:
        subscriptions.install(reader, "engineering", "robotics-bi", "1.1.0", raw, sha)
    assert wrong.value.code == "snapshot_invalid"  # the stamped version is 1.0.0
    assert _tree(reader) == {}


def test_installing_the_same_version_again_is_a_no_op(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    raw, sha = _published(owner)
    subscriptions.install(reader, "engineering", "robotics-bi", "1.0.0", raw, sha)
    before = _tree(reader)
    again = subscriptions.install(reader, "engineering", "robotics-bi", "1.0.0", raw, sha)
    assert again["already"] is True
    assert _tree(reader) == before


def _spec_owner(tmp_path: Path) -> BiStore:
    """A dataset bound to an installed (non-shipped) schema, with cards."""
    root = tmp_path / "owner"
    example = catalog.example()
    catalog.install(root, example["schema"]["filename"], example["schema"]["json_text"])
    store = BiStore(root, "spec")
    store.create("example/product-spec@1.0.0")
    from capabilities.bi_cards import importer

    for entity_type, filename, text in (
        (c["entity_type"], c["filename"], c["text"]) for c in example["csv"]
    ):
        prepared = importer.preview(
            store, entity_type=entity_type, filename=filename, csv_text=text
        )
        importer.apply(store, prepared, None, actor="leo.chi")
    return store


def test_a_missing_schema_is_installed_from_the_snapshot(tmp_path: Path) -> None:
    owner = _spec_owner(tmp_path)
    reader = tmp_path / "reader"
    raw, sha = _published(owner)
    assert not catalog.installed(reader)
    subscriptions.install(reader, "engineering", "robotics-bi", "1.0.0", raw, sha)
    refs = [reg.ref for reg in catalog.installed(reader)]
    assert refs == ["example/product-spec@1.0.0"]
    assert catalog.schema_path(reader, "example/product-spec", "1.0.0").read_text(
        encoding="utf-8"
    ) == catalog.schema_path(owner.workspace, "example/product-spec", "1.0.0").read_text(
        encoding="utf-8"
    )
    status, listed = _call(reader, "GET", "/api/bi/cards", dataset=DATASET)
    assert status == 200 and listed["cards"]


def test_the_same_schema_version_with_other_content_is_a_conflict(tmp_path: Path) -> None:
    owner = _spec_owner(tmp_path)
    reader = tmp_path / "reader"
    document = json.loads(catalog.example()["schema"]["json_text"])
    document["title"] = "另一份內容"
    catalog.install(reader, "x.json", json.dumps(document, ensure_ascii=False))
    before = _tree(reader)
    raw, sha = _published(owner)
    with pytest.raises(SubscriptionError) as refused:
        subscriptions.install(reader, "engineering", "robotics-bi", "1.0.0", raw, sha)
    assert refused.value.code == "schema_conflict"
    assert _tree(reader) == before


# -- items 6 and 7: the badge, the manual update, stopped, offline --------


def test_a_new_version_is_a_badge_not_an_install(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    subscriptions.observe(
        reader,
        [
            Offer("engineering", "robotics-bi", "1.0.0"),
            Offer("engineering", "robotics-bi", "1.1.0", "fix"),
        ],
    )
    item = subscriptions.listing(reader)[0]
    assert item["status"] == "update_available" and item["latest"] == "1.1.0"
    assert item["latest_note"] == "fix" and item["version"] == "1.0.0"
    assert item["status_text"] == "有新版本"
    # Only 1.0.0 is on disk: nothing was installed by the observation.
    root = reader / "bi" / "subscribed" / "engineering__robotics-bi"
    assert sorted(p.name for p in root.iterdir() if p.is_dir()) == ["1.0.0"]

    # 「更新」: the newer snapshot replaces the old one, which is not kept (§8.6).
    store = BiStore(owner.workspace, "robotics")
    card = store.card_rows()[0]
    store.set_field(card["id"], "name", "改過的名稱", base_version=card["version"], actor="leo")
    raw, sha = _published(store, "1.1.0", base="1.0.0")
    subscriptions.install(reader, "engineering", "robotics-bi", "1.1.0", raw, sha)
    item = subscriptions.listing(reader)[0]
    assert item["version"] == "1.1.0" and item["status"] == "current" and item["latest"] is None
    assert sorted(p.name for p in root.iterdir() if p.is_dir()) == ["1.1.0"]
    status, detail = _call(reader, "GET", f"/api/bi/cards/{card['id']}", dataset=DATASET)
    assert status == 200
    assert {f["field"]: f["value"] for f in detail["fields"]}["name"] == "改過的名稱"


def test_withdrawn_access_keeps_the_copy_and_stops_it(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    subscriptions.observe(reader, [Offer("engineering", "other", "1.0.0")])
    item = subscriptions.listing(reader)[0]
    assert item["status"] == "stopped_no_access"
    assert item["status_text"] == "已停止更新（無權限）" and item["stopped_at"]
    # Still readable, still listed.
    status, cards = _call(reader, "GET", "/api/bi/cards", dataset=DATASET)
    assert status == 200 and len(cards["cards"]) == 104
    # Offline afterwards does not un-stop it.
    subscriptions.observe(reader, None)
    assert subscriptions.listing(reader)[0]["status"] == "stopped_no_access"


def test_an_unreachable_platform_is_offline_and_changes_nothing_else(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    subscriptions.observe(reader, None)
    item = subscriptions.listing(reader)[0]
    assert item["status"] == "offline" and item["version"] == "1.0.0"
    assert _call(reader, "GET", "/api/bi/cards", dataset=DATASET)[0] == 200
    subscriptions.observe(reader, [Offer("engineering", "robotics-bi", "1.0.0")])
    assert subscriptions.listing(reader)[0]["status"] == "current"


# -- the routes --------------------------------------------------------------


class FakePlatform:
    """`SubscriptionPlatform` over published snapshots held in memory: a
    selection followed by a sync installs the selected version."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.published: dict[str, tuple[bytes, str]] = {}
        self.entitled = True
        self.reachable = True
        self.selected: str | None = None
        self.calls: list[str] = []

    def offers(self) -> list[Offer] | None:
        if not self.reachable:
            return None
        if not self.entitled:
            return []
        return [Offer("engineering", "robotics-bi", v) for v in self.published]

    def select(self, namespace: str, name: str, version: str) -> None:
        self.calls.append(f"select {version}")
        self.selected = version

    def revoke(self, namespace: str, name: str, version: str) -> None:
        self.calls.append(f"revoke {version}")
        self.selected = None

    def synchronize(self) -> dict[str, Any]:
        self.calls.append("sync")
        if self.selected is not None:
            raw, sha = self.published[self.selected]
            subscriptions.install(
                self.workspace, "engineering", "robotics-bi", self.selected, raw, sha
            )
        return {"status": "answered", "failure": None}

    def forget(self, namespace: str, name: str, version: str) -> None:
        self.calls.append(f"forget {version}")


def _routes(
    workspace: Path, platform: Any, method: str, path: str, body: Any = None, **q: str
) -> Any:
    return route(workspace, ACTOR, method, path, q, body, platform)


def test_subscribe_update_and_unsubscribe_through_the_routes(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    platform = FakePlatform(reader)
    platform.published["1.0.0"] = _published(owner, "1.0.0")

    status, listed = _routes(reader, platform, "GET", "/api/bi/subscriptions", refresh="1")
    assert status == 200 and listed["subscriptions"] == []
    assert listed["connection"] == "answered"
    assert [a["name"] for a in listed["available"]] == [DATASET]

    status, subscribed = _routes(
        reader, platform, "POST", "/api/bi/subscriptions/subscribe", {"dataset": DATASET}
    )
    assert status == 200 and subscribed["subscription"]["version"] == "1.0.0"
    assert platform.calls == ["select 1.0.0", "sync"]

    platform.published["1.1.0"] = _published(owner, "1.1.0", base="1.0.0")
    status, listed = _routes(reader, platform, "GET", "/api/bi/subscriptions", refresh="1")
    assert listed["available"] == []
    assert listed["subscriptions"][0]["status"] == "update_available"
    # Reading the list without refresh never calls the platform.
    calls = list(platform.calls)
    assert _routes(reader, platform, "GET", "/api/bi/subscriptions")[0] == 200
    assert platform.calls == calls

    status, updated = _routes(
        reader, platform, "POST", "/api/bi/subscriptions/update", {"dataset": DATASET}
    )
    assert status == 200 and updated["subscription"]["version"] == "1.1.0"
    assert updated["subscription"]["status"] == "current"
    assert platform.calls[-3:] == ["select 1.1.0", "sync", "forget 1.0.0"]
    status, again = _routes(
        reader, platform, "POST", "/api/bi/subscriptions/update", {"dataset": DATASET}
    )
    assert status == 200 and again["already"] is True

    status, gone = _routes(
        reader, platform, "POST", "/api/bi/subscriptions/unsubscribe", {"dataset": DATASET}
    )
    assert status == 200 and gone["deselected"] is True
    assert platform.calls[-2:] == ["revoke 1.1.0", "forget 1.1.0"]
    assert not (reader / "bi" / "subscribed" / "engineering__robotics-bi").exists()
    assert _call(reader, "GET", "/api/bi/datasets")[1]["datasets"] == []


def test_update_when_stopped_or_offline_keeps_the_copy(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    platform = FakePlatform(reader)
    platform.published["1.0.0"] = _published(owner, "1.0.0")
    _routes(reader, platform, "POST", "/api/bi/subscriptions/subscribe", {"dataset": DATASET})

    platform.reachable = False
    status, reply = _routes(
        reader, platform, "POST", "/api/bi/subscriptions/update", {"dataset": DATASET}
    )
    assert (status, reply["code"]) == (503, "platform_unreachable")
    assert subscriptions.listing(reader)[0]["status"] == "offline"

    platform.reachable, platform.entitled = True, False
    status, reply = _routes(
        reader, platform, "POST", "/api/bi/subscriptions/update", {"dataset": DATASET}
    )
    assert (status, reply["code"]) == (403, "dataset_no_access")
    item = subscriptions.listing(reader)[0]
    assert item["status"] == "stopped_no_access" and item["version"] == "1.0.0"
    assert _call(reader, "GET", "/api/bi/cards", dataset=DATASET)[0] == 200


def test_the_subscription_routes_refuse_bad_input(tmp_path: Path) -> None:
    status, reply = _routes(
        tmp_path, None, "POST", "/api/bi/subscriptions/update", {"dataset": "demo"}
    )
    assert (status, reply["code"]) == (400, "dataset_invalid")
    status, reply = _routes(
        tmp_path, None, "POST", "/api/bi/subscriptions/subscribe", {"dataset": DATASET}
    )
    assert (status, reply["code"]) == (409, "platform_not_configured")
    status, reply = _routes(
        tmp_path, None, "POST", "/api/bi/subscriptions/unsubscribe", {"dataset": DATASET}
    )
    assert (status, reply["code"]) == (404, "subscription_unknown")
    status, reply = _routes(tmp_path, None, "GET", "/api/bi/subscriptions", refresh="1")
    assert status == 200 and reply["configured"] is False and "available" not in reply


# -- item 9: bi__query cites the version -----------------------------------


def _ask(workspace: Path, **arguments: Any) -> Any:
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor=ACTOR,
        namespace="engineering",
        message="bi",
        channel="local",
        session_id="s-1",
    )
    return asyncio.run(QueryHandler(workspace)(context, QueryRequest(**arguments)))


def test_bi_query_on_a_subscribed_dataset_carries_the_version(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    result = _ask(reader, dataset=DATASET, text="BMS")
    assert result.total > 0
    assert result.source["version"] == "1.0.0"
    assert result.source["published_by"] == "leo.chi" and result.source["stopped"] is False
    assert "資料來源：engineering/robotics-bi v1.0.0（發佈者 leo.chi）" in result.scope_note

    analysed = _ask(reader, dataset=DATASET, analysis="gaps", domain="robotics")
    assert analysed.source["version"] == "1.0.0" and "v1.0.0" in analysed.scope_note

    subscriptions.observe(reader, [])
    stopped = _ask(reader, dataset=DATASET, text="BMS")
    assert stopped.source["stopped"] is True and "已停止更新" in stopped.scope_note

    local = _ask(owner.workspace, dataset="robotics", text="BMS")
    assert local.source is None


def test_bi_query_refuses_a_dataset_not_subscribed(tmp_path: Path) -> None:
    from capabilities.runtime import CapabilityRefused

    with pytest.raises(CapabilityRefused) as refused:
        _ask(tmp_path, dataset=DATASET)
    assert str(refused.value) == "dataset_unknown" or "dataset_unknown" in repr(refused.value)


def test_the_procedure_ends_with_the_version_and_says_when_stopped() -> None:
    assert "資料來源：robotics-bi v1.2.0（發佈者 leo.chi）" in PROCEDURE
    assert "已停止更新" in PROCEDURE and "source.stopped" in PROCEDURE


# -- the verified sync with the in-process platform (items 4, 6, 7) ----------


def _platform_package(platform: Any, raw: bytes, version: str) -> None:
    from common.assets import AssetIdentity, Owner, PackageMetadata
    from common.distribution import PublishedAssetPackage

    reference = f"registry://engineering/robotics-bi/{version}"
    platform.packages.publish(
        PublishedAssetPackage.model_validate(
            {
                "kind": "bi_dataset",
                "metadata": {
                    "identity": AssetIdentity(
                        namespace="engineering", name="robotics-bi", version=version
                    ).model_dump(),
                    "owner": Owner(type="team", id="robotics").model_dump(),
                    "visibility": "team",
                    "lifecycle": "published",
                    "package": PackageMetadata(
                        artifact_ref=reference, sha256=hashlib.sha256(raw).hexdigest()
                    ).model_dump(),
                },
                "description": f"version {version}",
            }
        )
    )
    platform.artifacts[reference] = raw


def _access(members: tuple[str, ...]) -> Any:
    from test_platform_transport import NOW

    from common.identity import NameAccess

    return NameAccess(
        namespace="engineering",
        name="robotics-bi",
        members=members,
        updated_by="platform-admin",
        updated_at=NOW,
    )


def test_the_sync_installs_a_selected_dataset_and_never_updates_by_itself(
    tmp_path: Path,
) -> None:
    from test_host_wiring import BRIDGE
    from test_member_portal import signed_in
    from test_platform_transport import NOW, Platform, host

    from common.assets import AssetIdentity
    from common.authorization import DeviceAssetSelection
    from control_plane.http import ControlPlaneServer
    from host_runtime.bi_subscriptions import catalog_offers

    owner = _owner(tmp_path)
    platform = Platform()
    v1, _ = _published(owner, "1.0.0")
    _platform_package(platform, v1, "1.0.0")
    # Owned by another team; this member reads it through the name's access.
    platform.packages.save_access(_access(("engineer",)))
    platform.authorization.select(
        signed_in(),
        DeviceAssetSelection(
            bridge_id=BRIDGE,
            actor="engineer",
            kind="bi_dataset",
            asset=AssetIdentity(namespace="engineering", name="robotics-bi", version="1.0.0"),
            decided_at=NOW,
        ),
        now=NOW,
    )
    reference = "registry://engineering/robotics-bi/1.0.0"

    with ControlPlaneServer(platform.service) as control:
        _, layout, runtime = host(tmp_path / "host", platform, control.base_url)
        workspace = layout.workspace_root
        with runtime:
            client = runtime.platform
            assert client is not None
            # A digest that does not match: refused, nothing written.
            platform.artifacts[reference] = v1 + b"tampered"
            before = _tree(workspace)
            refused = asyncio.run(client.synchronize(layout, runtime.state))
            assert refused.status == "refused"
            assert _tree(workspace) == before
            assert not (workspace / "bi" / "subscribed").exists()

            platform.artifacts[reference] = v1
            synced = asyncio.run(client.synchronize(layout, runtime.state))
            assert synced.status == "answered", synced
            assert ("engineering", "robotics-bi", "1.0.0") in [i.key for i in synced.installed]
            item = subscriptions.listing(workspace)[0]
            assert item["version"] == "1.0.0" and item["published_by"] == "leo.chi"
            assert len(BiStore(workspace, DATASET).card_rows()) == 104

            # Again: idempotent.
            files = _tree(workspace / "bi")
            again = asyncio.run(client.synchronize(layout, runtime.state))
            assert again.status == "answered" and again.installed == ()
            assert _tree(workspace / "bi") == files

            # A newer version is a badge; the sync keeps the selected one.
            v2, _ = _published(owner, "1.1.0", base="1.0.0")
            _platform_package(platform, v2, "1.1.0")
            subscriptions.observe(workspace, catalog_offers(client))
            item = subscriptions.listing(workspace)[0]
            assert (item["status"], item["latest"]) == ("update_available", "1.1.0")
            asyncio.run(client.synchronize(layout, runtime.state))
            assert subscriptions.listing(workspace)[0]["version"] == "1.0.0"

            # Access withdrawn: kept, readable, stopped (owner Q2).
            platform.packages.save_access(_access(()))
            subscriptions.observe(workspace, catalog_offers(client))
            item = subscriptions.listing(workspace)[0]
            assert item["status"] == "stopped_no_access" and item["version"] == "1.0.0"
            assert len(BiStore(workspace, DATASET).card_rows()) == 104

    # The platform gone: unreachable is never revoked, and the copy reads on.
    platform.packages.save_access(_access(("engineer",)))
    with runtime:
        assert catalog_offers(runtime.platform) is None
    assert subscriptions.listing(workspace)[0]["status"] == "stopped_no_access"
    assert _call(workspace, "GET", "/api/bi/cards", dataset=DATASET)[0] == 200


def test_agent_web_adapter_selects_as_the_member_and_explains_refusals(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from host_runtime.bi_subscriptions import WebPlatform, observe_catalog
    from host_runtime.platform_publish import PublishError

    calls: list[tuple[str, str, dict[str, str]]] = []
    forgotten: list[Any] = []

    class Publisher:
        def select(self, bridge_id: str, asset: dict[str, str]) -> dict[str, Any]:
            calls.append(("select", bridge_id, asset))
            return {}

        def revoke(self, bridge_id: str, asset: dict[str, str]) -> dict[str, Any]:
            raise PublishError("asset_not_entitled", 403)

    web = SimpleNamespace(
        _publisher=Publisher,
        synchronize=lambda: {"status": "answered"},
        runtime=SimpleNamespace(
            config=SimpleNamespace(device=SimpleNamespace(bridge_id="bridge-a")),
            state=SimpleNamespace(forget=forgotten.append),
        ),
    )
    adapter = WebPlatform(web)
    adapter.select("engineering", "robotics-bi", "1.0.0")
    assert calls == [
        (
            "select",
            "bridge-a",
            {"namespace": "engineering", "name": "robotics-bi", "version": "1.0.0"},
        )
    ]
    with pytest.raises(SubscriptionError) as refused:
        adapter.revoke("engineering", "robotics-bi", "1.0.0")
    assert refused.value.code == "asset_not_entitled" and refused.value.message
    adapter.forget("engineering", "robotics-bi", "1.0.0")
    assert forgotten[0].key == ("engineering", "robotics-bi", "1.0.0")
    assert adapter.synchronize() == {"status": "answered"}

    web.__dict__["_publisher"] = lambda: None
    with pytest.raises(SubscriptionError) as missing:
        adapter.select("engineering", "robotics-bi", "1.0.0")
    assert missing.value.code == "publishing_not_configured"

    # A catalog that did not answer marks every subscription offline, and
    # nothing at all happens when nothing is subscribed.
    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    observe_catalog(reader, None, SimpleNamespace(status="unreachable", reply=None))
    assert not (reader / "bi").exists()
    _subscribe(reader, owner)
    observe_catalog(reader, None, SimpleNamespace(status="unreachable", reply=None))
    assert subscriptions.listing(reader)[0]["status"] == "offline"


# -- the source line the Host adds when the model left it out (2026-10-24) ---


def _turn(text: str, *results: Any, status: str = "answered") -> Any:
    """A finished conversation whose `bi__query` calls returned `results`."""
    from agent.gateway import (
        ConversationToolExecution,
        GatewayConversationResult,
        HostToolOutcome,
    )
    from common.execution import Failure

    return GatewayConversationResult(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        status=status,
        text=text,
        model_turns=2,
        tools=tuple(
            ConversationToolExecution(
                call_id=f"call-{index}",
                name="bi__query",
                host=HostToolOutcome(status="succeeded", data=result.model_dump(mode="json")),
            )
            for index, result in enumerate(results)
        ),
        failure=None if status == "answered" else Failure(code="tool_loop_limit", message="x"),
    )


LINE = "資料來源：engineering/robotics-bi v1.0.0（發佈者 leo.chi）"


def test_a_missing_source_line_is_appended_once(tmp_path: Path) -> None:
    """Live test: 2 of 9 answers on a subscribed dataset had no source line
    though `bi__query` carried it. The Host appends the tool result's line,
    once per dataset however many calls read it."""
    from host_runtime.bi_cards_tools import with_bi_sources

    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    first = _ask(reader, dataset=DATASET, text="BMS")
    second = _ask(reader, dataset=DATASET, analysis="gaps", domain="robotics")
    answer = "BMS 有三張客戶產品卡。\n"
    shown = with_bi_sources(answer, _turn(answer, first, second))
    assert shown == "BMS 有三張客戶產品卡。\n\n" + LINE
    assert shown.count("資料來源") == 1


def test_a_source_line_the_model_wrote_is_not_repeated(tmp_path: Path) -> None:
    from host_runtime.bi_cards_tools import with_bi_sources

    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    result = _ask(reader, dataset=DATASET, text="BMS")
    for written in (
        f"答案。\n\n{LINE}",
        "答案。\n（資料來源 engineering/robotics-bi，版本 1.0.0）",
    ):
        assert with_bi_sources(written, _turn(written, result)) == written
    # Another version named does not count as this one.
    other = "答案。\n資料來源：engineering/robotics-bi v0.9.0"
    assert with_bi_sources(other, _turn(other, result)).endswith(LINE)
    # A turn that did not finish, or an empty answer, is left as it is.
    assert with_bi_sources("停了", _turn("停了", result, status="failed")) == "停了"


def test_the_appended_line_carries_the_stopped_or_update_status(tmp_path: Path) -> None:
    from host_runtime.bi_cards_tools import with_bi_sources

    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    subscriptions.observe(
        reader, [Offer(namespace="engineering", name="robotics-bi", version="1.1.0")]
    )
    newer = _ask(reader, dataset=DATASET, text="BMS")
    assert with_bi_sources("答案", _turn("答案", newer)) == (
        f"答案\n\n{LINE}；平台上有 v1.1.0，尚未更新"
    )
    subscriptions.observe(reader, [])
    stopped = _ask(reader, dataset=DATASET, text="BMS")
    assert with_bi_sources("答案", _turn("答案", stopped)) == (
        f"答案\n\n{LINE}；這份副本已停止更新（無權限），內容停在這個版本"
    )


def test_an_own_dataset_adds_no_source_line(tmp_path: Path) -> None:
    from host_runtime.bi_cards_tools import with_bi_sources

    owner = _owner(tmp_path)
    local = _ask(owner.workspace, dataset="robotics", text="BMS")
    assert with_bi_sources("答案", _turn("答案", local)) == "答案"


def test_agent_web_adds_the_source_line_to_the_stored_answer(
    tmp_path: Path,
    served: Any,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_agent_web import base, fetch

    from host_runtime.agent import LocalConversationOutcome

    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    queried = _ask(reader, dataset=DATASET, text="BMS")
    turn = _turn("BMS 有三張客戶產品卡。", queried)

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        return LocalConversationOutcome(
            trace=turn.trace, ingress="local", actor=request.actor, conversation=turn
        )

    monkeypatch.setattr(served.web.runtime.agent, "converse", converse)
    url, token = base(served), served.token
    session = fetch(url + "/api/conversations", token=token, body={}).json()
    reply = fetch(
        url + "/api/conversations/turn",
        token=token,
        body={"session_id": session["conversation"]["session_id"], "message": "BMS 有哪些？"},
    ).json()
    assert reply["answer"]["answer"] == "BMS 有三張客戶產品卡。\n\n" + LINE
    assert reply["conversation"]["messages"][-1]["text"].endswith(LINE)


def test_telegram_adds_the_source_line_to_the_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update

    from host_runtime.agent import LocalConversationOutcome

    owner = _owner(tmp_path)
    reader = tmp_path / "reader"
    _subscribe(reader, owner)
    queried = _ask(reader, dataset=DATASET, text="BMS")
    turn = _turn("BMS 有三張客戶產品卡。", queried)

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        return LocalConversationOutcome(
            trace=turn.trace, ingress="telegram", actor=request.actor, conversation=turn
        )

    transport = FakeTransport([[update(1, OWNER, "BMS 有哪些？")]])
    item, agent, _ = ingress(tmp_path / "telegram", transport)
    monkeypatch.setattr(agent, "converse", converse)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered"
    assert transport.sent() == ["BMS 有三張客戶產品卡。\n\n" + LINE]
