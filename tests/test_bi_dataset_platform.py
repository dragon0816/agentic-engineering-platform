"""BI dataset sharing on the Shared Platform (slice 1, owner 2026-10-22).

Requirements: `docs/proposals/BI_DATASET_SHARING.md` §6 and §8.2 items 2, 3
and 8, owner answers Q2, Q4 and Q5 (§8.5), contract `docs/CONTRACTS.md` "BI
dataset sharing". Uses the in-process reference platform: the publish rules
(platform versions, `base_version`, size, readers, review of a new name),
entitlement on catalog, selection and sync, the entitlement-revoked signal,
the download and the audit records.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import device

from aep_bi.cards import snapshot
from aep_bi.cards.snapshot import build_snapshot, read_snapshot
from aep_bi.cards.store import BiStore, PlannedRow
from capabilities.files import READ_FILE_SPEC
from common.assets import AssetIdentity
from common.enrollment import BridgeBinding, BridgeDevice, Invitation
from common.execution import TraceIdentifiers
from common.identity import AuthenticatedActor
from common.member import AssetApproveRequest, AssetRejectRequest, MemberSelectRequest
from common.sync import CatalogRequest, SyncRequest
from control_plane.app import (
    SharedPlatformApplication,
    SharedPlatformConfiguration,
    SharedPlatformState,
)
from control_plane.bi_datasets import (
    BiDatasetAuditRequest,
    BiDatasetDownloadRequest,
    BiDatasetError,
    BiDatasetPublishRequest,
    BiDatasetStatusRequest,
)
from control_plane.member import MemberError
from control_plane.submissions import SubmissionError
from host_runtime.contracts import PlatformPublishBinding
from host_runtime.platform_publish import MemberPortalPublisher, PublishError
from models.credentials import StaticCredentials
from workflow.host_bridge import BridgeRegistration

NOW = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
TEAM = "engineering"
SECRET_LEN = "-session-secret-long-enough-to-be-safe"
TOKEN_SECRET = "a-platform-token-secret-that-is-long-enough-to-pass"
ABORTED = -1  # the connection was closed while the request was being sent
# leo and mia are in the owning team, sam is in sales, multi in both,
# reviewer is a platform administrator.
MEMBERS: dict[str, tuple[str, ...]] = {
    "leo": (TEAM,),
    "mia": (TEAM,),
    "sam": ("sales",),
    "multi": (TEAM, "sales"),
}


def trace() -> TraceIdentifiers:
    return TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1")


def signed_in(actor: str) -> AuthenticatedActor:
    return AuthenticatedActor(
        actor=actor,
        method="invitation-proof",
        authenticated_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=8),
    )


@dataclass
class Platform:
    app: SharedPlatformApplication
    sessions: dict[str, tuple[str, str]]
    tokens: dict[str, str]

    def member(self, actor: str) -> tuple[str, str]:
        return self.sessions[actor]

    def publish(self, actor: str, data: bytes, **fields: Any) -> Any:
        body: dict[str, Any] = {
            "namespace": TEAM,
            "name": "sales-bi",
            "note": "monthly refresh",
            "snapshot": base64.b64encode(data).decode("ascii"),
            **fields,
        }
        return self.app.member_service.bi_publish(
            *self.member(actor), BiDatasetPublishRequest.model_validate(body)
        )

    def approve(self, submission_id: str) -> Any:
        return self.app.member_service.review_approve(
            *self.member("reviewer"),
            AssetApproveRequest(submission_id=submission_id, evidence="name and team checked"),
        )

    def select(self, actor: str, version: str) -> Any:
        return self.app.member_service.select(
            *self.member(actor),
            MemberSelectRequest(bridge_id=f"bridge-{actor}", asset=identity(version)),
        )

    def sync(self, actor: str, installed: tuple[AssetIdentity, ...] = ()) -> Any:
        return self.app.control_service.synchronize(
            self.tokens[actor], TOKEN_SECRET, SyncRequest(installed=installed)
        )

    def catalog(self, actor: str) -> Any:
        return self.app.control_service.catalog(
            self.tokens[actor], TOKEN_SECRET, CatalogRequest(kinds=("bi_dataset",))
        )

    def status(self, actor: str) -> Any:
        return self.app.member_service.bi_status(
            *self.member(actor),
            BiDatasetStatusRequest.model_validate(
                {"names": [{"namespace": TEAM, "name": "sales-bi"}]}
            ),
        ).datasets[0]

    def audit(self, actor: str = "leo") -> list[Any]:
        return list(
            self.app.member_service.bi_audit(
                *self.member(actor), BiDatasetAuditRequest(namespace=TEAM, name="sales-bi")
            ).events
        )


def identity(version: str) -> AssetIdentity:
    return AssetIdentity(namespace=TEAM, name="sales-bi", version=version)


def build_platform(state: SharedPlatformState) -> Platform:
    enrollment = state.enrollment
    sessions: dict[str, tuple[str, str]] = {}
    for actor, groups in MEMBERS.items():
        enrollment.issue(
            Invitation(
                invitation_id=f"invite-{actor}",
                actor=actor,
                issued_by="platform-admin",
                groups=groups,
            )
        )
        enrollment.accept(f"invite-{actor}", actor)
    enrollment.issue(
        Invitation(
            invitation_id="invite-reviewer",
            actor="reviewer",
            issued_by="platform-admin",
            role="platform_admin",
        )
    )
    enrollment.accept("invite-reviewer", "reviewer")
    app = SharedPlatformApplication(state, clock=lambda: NOW)
    tokens: dict[str, str] = {}
    for actor in MEMBERS:
        bridge = f"bridge-{actor}"
        described = device(bridge_id=bridge, registered_by=actor)
        enrollment.register_device(
            BridgeDevice.model_validate(described),
            BridgeRegistration(
                bridge_id=bridge, owner_id=actor, trace=trace(), capabilities=(READ_FILE_SPEC,)
            ),
        )
        enrollment.bind(actor, BridgeBinding(bridge_id=bridge, actor=actor, role="device_admin"))
        issued_token = state.tokens.issue(
            actor, actor, bridge, issued_at=NOW - timedelta(hours=1), secret=TOKEN_SECRET
        )
        tokens[actor] = issued_token.grant.token_id
    for actor in (*MEMBERS, "reviewer"):
        secret = f"{actor}{SECRET_LEN}"
        issued = state.sessions.issue(signed_in(actor), now=NOW, secret=secret)
        sessions[actor] = (issued.grant.session_id, issued.secret)
    return Platform(app=app, sessions=sessions, tokens=tokens)


@pytest.fixture(params=["memory", "sqlite"])
def platform(request: pytest.FixtureRequest, tmp_path: Path) -> Platform:
    if request.param == "memory":
        state = SharedPlatformState.empty(administrators=("platform-admin",))
    else:
        state = SharedPlatformState.durable(
            tmp_path / "registry.sqlite", administrators=("platform-admin",)
        )
    return build_platform(state)


def dataset(workspace: Path, *, tier: str = "A") -> bytes:
    store = BiStore(workspace, "sales")
    store.apply(
        [
            PlannedRow(
                row=2,
                entity_type="Customer",
                canonical_key="acme",
                name="ACME",
                values={"region": "TW", "tier": tier},
                synthetic=False,
            )
        ],
        filename="customers.csv",
        entity_type="Customer",
        actor="leo",
    )
    return build_snapshot(store)


@pytest.fixture
def first(tmp_path: Path) -> bytes:
    return dataset(tmp_path / "v1")


def published_first(platform: Platform, data: bytes) -> None:
    pending = platform.publish("leo", data)
    platform.approve(pending.submission_id)


def refused(call: Any, *args: Any, **kwargs: Any) -> str:
    with pytest.raises((BiDatasetError, MemberError, SubmissionError)) as caught:
        call(*args, **kwargs)
    error = caught.value
    assert isinstance(error, (BiDatasetError, MemberError, SubmissionError))
    return str(error.code)


# -- §8.2 item 2: publishing ------------------------------------------------------


def test_a_new_name_waits_for_review_then_versions_follow_base_version(
    platform: Platform, first: bytes, tmp_path: Path
) -> None:
    pending = platform.publish("leo", first)
    assert pending.status == "pending_review" and pending.asset == identity("1.0.0")
    assert pending.digest == read_snapshot(first).digest
    assert platform.app.state.packages.get(identity("1.0.0")) is None
    # While the name waits, nothing else is published under it.
    assert refused(platform.publish, "mia", first, base_version=None) == "review_pending"
    detail = platform.app.member_service.review_detail(
        *platform.member("reviewer"),
        _request(pending.submission_id),
    )
    summary: dict[str, Any] = dict(detail.manifest)
    assert summary["kind"] == "bi_dataset"
    assert summary["stats"]["cards"] == 1  # a summary, not card values
    assert "cards" not in detail.manifest
    platform.approve(pending.submission_id)

    package = platform.app.state.packages.get(identity("1.0.0"))
    assert package is not None and package.kind == "bi_dataset"
    assert package.metadata.owner.model_dump() == {"type": "team", "id": TEAM}
    assert package.metadata.visibility == "team"
    assert package.metadata.business_approval.reviewer == "reviewer"
    stored = platform.app.state.artifacts[package.metadata.package.artifact_ref]  # type: ignore[union-attr]
    assert hashlib.sha256(stored).hexdigest() == package.metadata.package.sha256  # type: ignore[union-attr]
    stamped = read_snapshot(stored)
    assert stamped.digest == read_snapshot(first).digest
    assert stamped.publication is not None
    assert stamped.publication.version == "1.0.0" and stamped.publication.published_by == "leo"

    second = dataset(tmp_path / "v2", tier="B")
    later = platform.publish("mia", second, base_version="1.0.0")  # a team member, directly
    assert later.status == "published" and later.asset == identity("1.1.0")
    stamp = read_snapshot(platform.app.state.artifacts[f"registry://{TEAM}/sales-bi/1.1.0"])
    assert stamp.publication is not None and stamp.publication.base_version == "1.0.0"

    assert refused(platform.publish, "leo", second, base_version="1.0.0") == "version_superseded"
    assert refused(platform.publish, "leo", second) == "version_superseded"
    assert refused(platform.publish, "sam", second, base_version="1.1.0") == (
        "publisher_not_authorized"
    )


def test_a_co_editor_publishes_and_a_schema_major_change_raises_the_major(
    platform: Platform, first: bytes, tmp_path: Path
) -> None:
    published_first(platform, first)
    assert platform.app.state.packages.ownership(TEAM, "sales-bi") is not None
    ownership = platform.app.member_service.ownership
    assert ownership is not None
    ownership.add_co_editor(signed_in("leo"), TEAM, "sales-bi", "sam", now=NOW)
    reply = platform.publish("sam", dataset(tmp_path / "v2", tier="C"), base_version="1.0.0")
    assert reply.asset == identity("1.1.0")

    major = read_snapshot(dataset(tmp_path / "v3", tier="D"))
    changed = json.loads(json.dumps(major.document))
    changed["schema"]["document"]["version"] = "2.0.0"
    changed["schema"]["version"] = "2.0.0"
    changed["schema"]["ref"] = "bi.schema/v1.1@2.0.0"
    changed["schema"]["sha256"] = snapshot.schema_sha256(changed["schema"]["document"])
    changed["digest"] = snapshot.content_digest(changed)
    data = gzip.compress(snapshot.canonical_json(changed), mtime=0)
    assert platform.publish("leo", data, base_version="1.1.0").asset == identity("2.0.0")


def test_size_readers_and_team_rules(platform: Platform, first: bytes) -> None:
    platform.app.member_service.bi_datasets.max_bytes = 1024 * 1024  # type: ignore[union-attr]
    big = b"\x1f\x8b" + b"0" * (1024 * 1024)
    assert refused(platform.publish, "leo", big) == "artifact_too_large"
    assert refused(platform.publish, "leo", first, readers="public") == "visibility_not_allowed"
    assert refused(platform.publish, "leo", first, readers="private") == "visibility_not_allowed"
    assert refused(platform.publish, "leo", first, readers="organization") == (
        "organization_unconfirmed"
    )
    assert refused(platform.publish, "multi", first) == "team_required"
    assert refused(platform.publish, "leo", first, team="sales") == "publisher_not_authorized"
    garbage = base64.b64encode(b"nonsense").decode()
    with pytest.raises(BiDatasetError) as caught:
        platform.app.member_service.bi_publish(
            *platform.member("leo"),
            BiDatasetPublishRequest(namespace=TEAM, name="x", note="n", snapshot=garbage),
        )
    assert caught.value.code == "snapshot_invalid"

    pending = platform.publish(
        "multi", first, team="sales", readers="organization", confirm_organization=True
    )
    item = platform.app.state.submissions.get(pending.submission_id)
    assert item is not None
    assert item[0].owner is not None and item[0].owner.id == "sales"
    assert item[0].visibility == "organization"


def test_the_platform_rechecks_secrets_and_the_digest(platform: Platform, first: bytes) -> None:
    document = json.loads(json.dumps(read_snapshot(first).document))
    document["cards"][0]["fields"]["region"]["value"] = "token password=hunter2"
    document["digest"] = snapshot.content_digest(document)
    forged = gzip.compress(snapshot.canonical_json(document), mtime=0)
    with pytest.raises(BiDatasetError) as caught:
        platform.publish("leo", forged)
    assert caught.value.code == "secret_found"
    assert caught.value.card == "Customer:acme" and caught.value.field == "region"
    assert "hunter2" not in json.dumps(caught.value.body())

    document["cards"][0]["fields"]["region"]["value"] = "JP"
    tampered = gzip.compress(snapshot.canonical_json(document), mtime=0)
    assert refused(platform.publish, "leo", tampered) == "digest_mismatch"


def test_a_bi_dataset_name_can_never_be_made_public(platform: Platform, first: bytes) -> None:
    published_first(platform, first)
    assert (
        refused(
            platform.app.member_service.asset_access_update,
            *platform.member("leo"),
            _access(visibility="public"),
        )
        == "visibility_not_allowed"
    )


def test_a_rejected_first_version_publishes_nothing(platform: Platform, first: bytes) -> None:
    pending = platform.publish("leo", first)
    platform.app.member_service.review_reject(
        *platform.member("reviewer"),
        AssetRejectRequest(submission_id=pending.submission_id, reason="wrong team"),
    )
    assert platform.app.state.packages.get(identity("1.0.0")) is None
    assert [e.event for e in platform.audit()] == ["submitted", "rejected"]


# -- §8.2 item 3 and Q2: entitlement ----------------------------------------------


def test_only_entitled_members_see_select_sync_and_download(
    platform: Platform, first: bytes
) -> None:
    published_first(platform, first)
    assert [p.metadata.identity for p in platform.catalog("mia").packages] == [identity("1.0.0")]
    assert platform.catalog("sam").packages == ()

    selected = platform.select("mia", "1.0.0")
    assert selected.selection.kind == "bi_dataset"
    assert refused(platform.select, "sam", "1.0.0") == "asset_not_entitled"

    reply = platform.sync("mia")
    assert reply.plan is not None
    assert [p.kind for p in reply.plan.packages] == ["bi_dataset"]
    delivered = reply.artifacts[0].raw
    assert read_snapshot(delivered).publication.version == "1.0.0"  # type: ignore[union-attr]
    assert platform.sync("mia", (identity("1.0.0"),)).plan is None  # already installed

    download = platform.app.member_service.bi_download(
        *platform.member("mia"), BiDatasetDownloadRequest(asset=identity("1.0.0"))
    )
    assert base64.b64decode(download.snapshot) == delivered
    assert (
        refused(
            platform.app.member_service.bi_download,
            *platform.member("sam"),
            BiDatasetDownloadRequest(asset=identity("1.0.0")),
        )
        == "asset_not_entitled"
    )

    status = platform.status("mia")
    assert status.entitled and status.latest_version == "1.0.0"
    assert status.published_by == "leo" and status.note == "monthly refresh"
    hidden = platform.status("sam")
    assert not hidden.entitled and hidden.latest_version is None and hidden.published_by is None


def test_a_revoked_reader_keeps_nothing_new_and_is_told(
    platform: Platform, first: bytes, tmp_path: Path
) -> None:
    published_first(platform, first)
    platform.app.member_service.asset_access_update(
        *platform.member("leo"), _access(members=("sam",))
    )
    assert platform.status("sam").entitled
    platform.select("sam", "1.0.0")
    assert platform.sync("sam").plan is not None

    # The owner takes it back and publishes a new version.
    platform.app.member_service.asset_access_update(*platform.member("leo"), _access())
    platform.publish("leo", dataset(tmp_path / "v2", tier="B"), base_version="1.0.0")
    signal = platform.status("sam")
    assert signal.entitled is False and signal.latest_version is None
    assert platform.catalog("sam").packages == ()
    assert refused(platform.select, "sam", "1.1.0") == "asset_not_entitled"
    # A selection made before is not delivered again (a fresh install
    # would ask for it), and the refusal is audited once.
    assert platform.sync("sam").plan is None
    assert platform.sync("sam").plan is None
    refusals = [e for e in platform.audit() if e.event == "sync_refused"]
    assert len(refusals) == 1 and refusals[0].bridge_id == "bridge-sam"


# -- §8.2 item 8: audit -----------------------------------------------------------


def test_audit_records_publisher_version_digest_selector_and_bridge(
    platform: Platform, first: bytes, tmp_path: Path
) -> None:
    published_first(platform, first)
    platform.select("mia", "1.0.0")
    platform.sync("mia")
    platform.publish("leo", dataset(tmp_path / "v2", tier="B"), base_version="1.0.0")
    events = platform.audit()
    assert [e.event for e in events] == [
        "submitted",
        "approved",
        "selected",
        "synced",
        "published",
    ]
    approved, selected, synced, published = events[1:]
    assert approved.actor == "reviewer" and approved.version == "1.0.0"
    assert selected.actor == "mia" and selected.bridge_id == "bridge-mia"
    assert synced.bridge_id == "bridge-mia" and synced.version == "1.0.0"
    package = platform.app.state.packages.get(identity("1.0.0"))
    assert package is not None and package.metadata.package is not None
    assert synced.sha256 == package.metadata.package.sha256
    assert published.actor == "leo" and published.version == "1.1.0"
    assert published.base_version == "1.0.0" and published.sha256 is not None
    assert published.size is not None and published.note == "monthly refresh"
    # The administrator sees it too; a stranger is told the name is missing.
    assert len(platform.audit("reviewer")) == 5
    assert refused(platform.audit, "sam") == "name_missing"


# -- over HTTP, with the Agent's client --------------------------------------------


@pytest.fixture
def served(tmp_path: Path) -> Iterator[Platform]:
    state = SharedPlatformState.empty(administrators=("platform-admin",))
    platform = build_platform(state)
    with platform.app:
        yield platform


def test_the_agents_client_publishes_checks_and_downloads_over_http(
    served: Platform, first: bytes, tmp_path: Path
) -> None:
    portal = served.app.member_server.base_url

    def client(actor: str) -> MemberPortalPublisher:
        publisher = MemberPortalPublisher(
            PlatformPublishBinding(member_portal_url=portal, credential={"name": "login"}),
            StaticCredentials({"login": "unused"}),
            clock=lambda: NOW,
        )
        session_id, secret = served.member(actor)
        publisher._session = (f"{session_id}:{secret}", NOW + timedelta(hours=1))
        return publisher

    leo = client("leo")
    pending = leo.publish_bi_dataset(TEAM, "sales-bi", first, note="first", base_version=None)
    assert pending["status"] == "pending_review"
    served.approve(pending["submission_id"])
    second = dataset(tmp_path / "v2", tier="B")
    with pytest.raises(PublishError) as caught:
        leo.publish_bi_dataset(TEAM, "sales-bi", second, note="again", base_version=None)
    assert (caught.value.code, caught.value.status) == ("version_superseded", 409)
    reply = leo.publish_bi_dataset(TEAM, "sales-bi", second, note="again", base_version="1.0.0")
    assert reply["status"] == "published" and reply["asset"]["version"] == "1.1.0"

    mia = client("mia")
    [entry] = mia.bi_dataset_status([(TEAM, "sales-bi")])
    assert entry["entitled"] is True and entry["latest_version"] == "1.1.0"
    data = mia.bi_dataset_download(identity("1.1.0").model_dump())
    assert read_snapshot(data).publication.version == "1.1.0"  # type: ignore[union-attr]
    [hidden] = client("sam").bi_dataset_status([(TEAM, "sales-bi")])
    assert hidden["entitled"] is False
    assert [e["event"] for e in leo.bi_dataset_audit(TEAM, "sales-bi")][-1] == "downloaded"

    # A secret is named by card and field, never echoed.
    document = json.loads(json.dumps(read_snapshot(second).document))
    document["cards"][0]["fields"]["region"]["value"] = "password=hunter2"
    document["digest"] = snapshot.content_digest(document)
    forged = gzip.compress(snapshot.canonical_json(document), mtime=0)
    with pytest.raises(PublishError) as caught:
        leo.publish_bi_dataset(TEAM, "sales-bi", forged, note="x", base_version="1.1.0")
    assert caught.value.code == "secret_found" and caught.value.status == 400
    assert caught.value.message is not None
    assert "Customer:acme" in caught.value.message and "region" in caught.value.message
    assert "hunter2" not in str(caught.value.message)


def test_the_publish_body_has_its_own_limit_and_other_routes_keep_theirs(
    served: Platform,
) -> None:
    portal = served.app.member_server.base_url
    session_id, secret = served.member("leo")
    big = json.dumps({"names": [{"namespace": "a", "name": "b"}], "pad": "x" * 300_000})
    status, body = _post(f"{portal}/v1/member/bi-datasets/status", f"{session_id}:{secret}", big)
    # The portal answers 413 without reading the body; the client may see the
    # answer or, on Windows, the connection aborted while it still sends.
    assert status in (413, ABORTED)
    limit = served.app.member_service.bi_body_limit()
    assert limit > 20 * 1024 * 1024
    status, body = _post(
        f"{portal}/v1/member/bi-datasets/publish",
        f"{session_id}:{secret}",
        json.dumps({"pad": "x" * 300_000}),
    )
    assert status == 400  # read and refused as a request, not for its size


def test_the_configured_limit_reaches_the_service() -> None:
    config = SharedPlatformConfiguration(administrators=("admin",), max_bi_dataset_bytes=2**21)
    assert config.max_bi_dataset_bytes == 2 * 1024 * 1024
    with pytest.raises(ValueError):
        SharedPlatformConfiguration(administrators=("admin",), max_bi_dataset_bytes=10)


# -- helpers ------------------------------------------------------------------------


def _request(submission_id: str) -> Any:
    from common.member import AssetSubmissionRequest

    return AssetSubmissionRequest(submission_id=submission_id)


def _access(**fields: Any) -> Any:
    from common.member import AssetAccessUpdateRequest

    return AssetAccessUpdateRequest.model_validate(
        {"namespace": TEAM, "name": "sales-bi", "visibility": None, **fields}
    )


def _post(url: str, bearer: str, body: str) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, method="POST", data=body.encode("utf-8"))
    request.add_header("Authorization", f"Bearer {bearer}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused_answer:
        return refused_answer.code, json.loads(refused_answer.read())
    except (ConnectionError, urllib.error.URLError):
        return ABORTED, {}
