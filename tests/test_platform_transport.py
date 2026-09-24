"""The wire between a Bridge and the shared platform, end to end.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 2i. The control-plane
service is driven directly and through the standard-library HTTP server on a
loopback port; the Bridge's client is driven against that server through the
real `UrllibTransport`, and through a fake one where an answer the real server
never gives (a 5xx, a proxy's bare 401) has to be seen. Every host here is a
real workspace on disk with the real Gateway, policy and engine behind it.
"""

import asyncio
import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_host_wiring import (
    BRIDGE,
    device,
    host_json,
    membership_record,
    skill_manifest,
    workflow_manifest,
    workspace,
)
from test_local_agent import VALIDATION, slow_gateway, state_for
from test_local_agent import company as company_membership

from capabilities.files import READ_FILE_SPEC
from common.assets import AssetIdentity, AssetMetadata, Owner, PackageMetadata
from common.authorization import DeviceAssetSelection, DeviceAuthorization
from common.distribution import (
    LocalRunSummary,
    PublishedAssetPackage,
    RemoteJobRecord,
    RemoteWorkflowJob,
)
from common.enrollment import BridgeBinding, BridgeDevice, Invitation
from common.execution import ExecutionAuthorization, TraceIdentifiers
from common.identity import AuthenticatedActor
from common.sync import (
    AdvertiseRequest,
    ArtifactPayload,
    PollReply,
    ProbeReply,
    ReportRequest,
    SettleRequest,
    SyncReply,
    SyncRequest,
)
from control_plane.authorization import InMemoryAuthorizationRegistry
from control_plane.distribution import ControlError, InMemoryPackageRegistry, InMemoryRemoteControl
from control_plane.enrollment import InMemoryEnrollmentRegistry
from control_plane.http import ControlPlaneServer
from control_plane.identity import InMemoryAccessTokens
from control_plane.service import ControlPlaneService, ServiceError
from host_runtime.agent import LocalAgent
from host_runtime.cli import main
from host_runtime.contracts import CompanyHostConfiguration, HostLayout, PlatformBinding
from host_runtime.host import HostRuntime, build_runtime, host_report
from host_runtime.sync import PlatformClient, advertisement
from models.credentials import StaticCredentials
from models.wire import UrllibTransport
from workflow.host_bridge import BridgeRegistration

# Long ago, so every decision is older than any clock the service reads.
NOW = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
WORKFLOW = AssetIdentity(namespace="engineering", name="read-local-file", version="1.0.0")
SKILL = AssetIdentity(namespace="engineering", name="file-skill", version="1.0.0")
SHADOW = AssetIdentity(namespace="engineering", name="shadow", version="1.0.0")
READ = READ_FILE_SPEC.identity
SECRET = "a-platform-token-secret-that-is-long-enough-to-pass"
SHARED_SECRET = "another-platform-token-secret-long-enough-to-pass"


def trace(suffix: str = "1") -> TraceIdentifiers:
    return TraceIdentifiers(trace_id=f"t-{suffix}", request_id=f"r-{suffix}", span_id=f"s-{suffix}")


def package(identity: AssetIdentity, kind: str, content: bytes) -> PublishedAssetPackage:
    return PublishedAssetPackage.model_validate(
        {
            "kind": kind,
            "metadata": AssetMetadata(
                identity=identity,
                owner=Owner(type="team", id="engineering"),
                visibility="organization",
                lifecycle="published",
                package=PackageMetadata(
                    artifact_ref=f"registry://{identity.namespace}/{identity.name}/{identity.version}",
                    sha256=hashlib.sha256(content).hexdigest(),
                ),
            ),
        }
    )


def signed_in(actor: str = "engineer") -> AuthenticatedActor:
    return AuthenticatedActor(
        actor=actor,
        method="invitation-proof",
        authenticated_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=3650),
    )


class Platform:
    """The whole shared platform in one object: every reference, the
    service over them, and the two tokens the tests present."""

    def __init__(self, *, workflow_bytes: bytes | None = None, shadow: bool = False) -> None:
        self.enrollment = InMemoryEnrollmentRegistry(administrators=("platform-admin",))
        for actor in ("engineer", "shared-bot"):
            self.enrollment.issue(
                Invitation(
                    invitation_id=f"invite-{actor}",
                    actor=actor,
                    issued_by="platform-admin",
                    groups=("engineering",),
                )
            )
            self.enrollment.accept(f"invite-{actor}", actor)
        company = device()
        shared = device(
            bridge_id="bridge-shared",
            device_kind="shared_test_workstation",
            windows_account_mode="shared_user",
            resource_scope="external_only",
            local_isolation="cooperative_workspace",
        )
        for described in (company, shared):
            self.enrollment.register_device(
                BridgeDevice.model_validate(described),
                BridgeRegistration(
                    bridge_id=described["bridge_id"],
                    owner_id="engineer",
                    trace=trace("enroll"),
                    capabilities=(READ_FILE_SPEC,),
                ),
            )
        self.enrollment.bind(
            "engineer", BridgeBinding(bridge_id=BRIDGE, actor="engineer", role="device_admin")
        )
        self.enrollment.bind(
            "engineer",
            BridgeBinding(bridge_id="bridge-shared", actor="shared-bot", role="operator"),
        )
        self.tokens = InMemoryAccessTokens(self.enrollment)
        self.company_token = self.tokens.issue(
            "engineer", "engineer", BRIDGE, issued_at=NOW, secret=SECRET
        )
        self.shared_token = self.tokens.issue(
            "engineer", "shared-bot", "bridge-shared", issued_at=NOW, secret=SHARED_SECRET
        )
        workflow_content = (
            workflow_bytes
            if workflow_bytes is not None
            else json.dumps(workflow_manifest()).encode("utf-8")
        )
        skill_content = json.dumps(skill_manifest()).encode("utf-8")
        self.packages = InMemoryPackageRegistry()
        self.artifacts: dict[str, bytes] = {}
        for identity, kind, content in (
            (WORKFLOW, "workflow", workflow_content),
            (SKILL, "skill", skill_content),
        ):
            published = self.packages.publish(package(identity, kind, content))
            assert published.metadata.package is not None
            self.artifacts[published.metadata.package.artifact_ref] = content
        chosen: list[tuple[str, AssetIdentity, str | None]] = [
            ("workflow", WORKFLOW, None),
            ("skill", SKILL, None),
            ("capability", READ, "workspace-read-approval"),
        ]
        if shadow:
            # A second published package pointing at the first one's bytes:
            # the platform's own inconsistency, not any Bridge's.
            first = self.packages.get(WORKFLOW)
            assert first is not None and first.metadata.package is not None
            self.packages.publish(
                first.model_copy(
                    update={"metadata": first.metadata.model_copy(update={"identity": SHADOW})}
                )
            )
            chosen.append(("workflow", SHADOW, None))
        self.authorization = InMemoryAuthorizationRegistry(self.enrollment, self.packages)
        for kind, asset, approval in chosen:
            self.authorization.select(
                signed_in(),
                DeviceAssetSelection(
                    bridge_id=BRIDGE,
                    actor="engineer",
                    kind=kind,
                    asset=asset,
                    decided_at=NOW,
                    approval_ref=approval,
                    approved_by="engineer" if approval else None,
                ),
                now=NOW,
            )
        self.control = InMemoryRemoteControl(admission=self.enrollment.admit)
        self.service = ControlPlaneService(
            enrollment=self.enrollment,
            tokens=self.tokens,
            packages=self.packages,
            authorization=self.authorization,
            control=self.control,
            artifacts=self.artifacts,
        )

    def submit(self, job_id: str, workflow: AssetIdentity = WORKFLOW, **changes: Any) -> None:
        request_trace = trace(job_id)
        self.control.submit(
            RemoteWorkflowJob.model_validate(
                {
                    "job_id": job_id,
                    "ingress": "shared_platform",
                    "actor": "engineer",
                    "bridge_id": BRIDGE,
                    "workflow": workflow,
                    "arguments": {"args": "notes.txt"},
                    "trace": request_trace,
                    "authorization": ExecutionAuthorization(
                        allowed=True,
                        actor="engineer",
                        asset=workflow,
                        trace=request_trace,
                        policy_ref="policy/remote-workflow",
                    ),
                    **changes,
                }
            ),
            self.enrollment.device(BRIDGE),
        )


@pytest.fixture
def platform() -> Platform:
    return Platform()


@pytest.fixture
def server(platform: Platform) -> Iterator[ControlPlaneServer]:
    with ControlPlaneServer(platform.service) as running:
        yield running


def binding(base_url: str, **changes: Any) -> dict[str, Any]:
    return {
        "base_url": base_url,
        "token_id": "token-placeholder",
        "credential": {"name": "platform_token"},
        **changes,
    }


def host(
    tmp_path: Path, platform: Platform, base_url: str, *, secret: str = SECRET, **changes: Any
) -> tuple[CompanyHostConfiguration, HostLayout, HostRuntime]:
    """A company host that holds the company token, with no assets yet: the
    sync is what installs them."""
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        assets=False,
        config_changes={
            "platform": binding(base_url, token_id=platform.company_token.grant.token_id),
            "credentials": [
                {"secret": "platform_token", "environment_variable": "AEP_PLATFORM_TOKEN"}
            ],
            **changes,
        },
    )
    runtime = build_runtime(
        config, layout=layout, resolver=StaticCredentials({"platform_token": secret})
    )
    return config, layout, runtime


class CountingTransport:
    """The real transport, counting what went out."""

    def __init__(self) -> None:
        self.inner = UrllibTransport()
        self.calls: list[str] = []

    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> Any:
        self.calls.append(url)
        return self.inner.send(url, body, headers, timeout_s)


class CannedReply:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def chunks(self) -> Iterator[bytes]:
        yield self._body

    def close(self) -> None:
        return None


class CannedTransport:
    """Answers every call the same way, for the answers a real server does
    not give on purpose."""

    def __init__(self, status: int, body: bytes, *, error: BaseException | None = None) -> None:
        self.status = status
        self.body = body
        self.error = error
        self.calls = 0
        self.stop: asyncio.Event | None = None

    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> Any:
        self.calls += 1
        if self.stop is not None and self.calls >= 3:
            self.stop.set()
        if self.error is not None:
            raise self.error
        return CannedReply(self.status, self.body)


def client(platform: Platform, base_url: str, *, secret: str = SECRET, **changes: Any) -> Any:
    return PlatformClient(
        PlatformBinding.model_validate(
            binding(base_url, token_id=platform.company_token.grant.token_id, **changes)
        ),
        StaticCredentials({"platform_token": secret}),
    )


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def http(base_url: str, method: str, path: str, body: bytes | None = None, **headers: str) -> Any:
    request = urllib.request.Request(base_url + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as reply:
            return reply.status, json.loads(reply.read())
    except urllib.error.HTTPError as answered:
        return answered.code, json.loads(answered.read())


def test_the_wire_contracts_are_closed_and_consistent(platform: Platform) -> None:
    run_record = LocalRunSummary(
        run_id="run-1", actor="engineer", workflow=WORKFLOW, status="succeeded", updated_at=NOW
    )
    with pytest.raises(ValidationError, match="carries its run"):
        SettleRequest(job_id="job-1", disposition="ran")
    with pytest.raises(ValidationError, match="carries its run"):
        SettleRequest(job_id="job-1", disposition="rejected", run=run_record)
    with pytest.raises(ValidationError):
        SettleRequest.model_validate(
            {"job_id": "job-1", "disposition": "cancelled", "secret": "anything"}
        )
    bundle = platform.authorization.authorization(BRIDGE, issued_at=NOW + timedelta(hours=1))
    plan = platform.packages.plan(actor="engineer", bridge_id=BRIDGE, requested=(WORKFLOW,))
    ref = plan.packages[0].metadata.package.artifact_ref  # type: ignore[union-attr]
    payload = ArtifactPayload.of(ref, platform.artifacts[ref])
    assert payload.raw == platform.artifacts[ref]
    assert ArtifactPayload.model_validate_json(payload.model_dump_json()) == payload
    with pytest.raises(ValidationError, match="base64"):
        ArtifactPayload(artifact_ref=ref, content="not base64!")
    # A plan travels with exactly its bytes.
    with pytest.raises(ValidationError, match="every planned package"):
        SyncReply(authorization=bundle, plan=plan)
    with pytest.raises(ValidationError, match="nowhere to go"):
        SyncReply(authorization=bundle, artifacts=(payload,))
    assert SyncReply(authorization=bundle, plan=plan, artifacts=(payload,)).plan == plan
    with pytest.raises(ValidationError, match="listed once"):
        SyncRequest(installed=(WORKFLOW, WORKFLOW))
    # A settled job is not offered, and a job that ran carries its run.
    platform.submit("job-1")
    record = platform.control.job("job-1")
    assert record.open
    with pytest.raises(ValidationError, match="carries its run"):
        RemoteJobRecord(request=record.request, status="ran")
    with pytest.raises(ValidationError, match="names the job's actor"):
        RemoteJobRecord(
            request=record.request,
            status="ran",
            run=run_record.model_copy(update={"actor": "tester"}),
        )
    with pytest.raises(ValidationError, match="still waiting"):
        PollReply(jobs=(RemoteJobRecord(request=record.request, status="cancelled"),))
    # A Bridge's authentication names the Bridge.
    with pytest.raises(ValidationError, match="names the Bridge"):
        ProbeReply(identity=signed_in(), platform_time=NOW)
    # The platform is reached over https beyond loopback, and never with a
    # secret pasted into the configuration.
    assert PlatformBinding.model_validate(binding("http://127.0.0.1:1/")).base_url == (
        "http://127.0.0.1:1"
    )
    assert PlatformBinding.model_validate(binding("https://platform.internal")).base_url
    with pytest.raises(ValidationError, match="https"):
        PlatformBinding.model_validate(binding("http://platform.internal"))
    with pytest.raises(ValidationError, match="origin"):
        PlatformBinding.model_validate(binding("https://platform.internal/v1"))
    with pytest.raises(ValidationError, match="origin"):
        PlatformBinding.model_validate(binding("https://platform.internal?env=prod"))
    with pytest.raises(ValidationError, match="origin"):
        PlatformBinding.model_validate(binding("https://platform.internal#prod"))
    with pytest.raises(ValidationError, match="no credential"):
        PlatformBinding.model_validate(binding("https://token-1:secret@platform.internal"))
    # A job id is what the Bridge runs the job under, so it has to be a key.
    with pytest.raises(ValidationError, match="idempotency key"):
        platform.submit("j" * 129)
    with pytest.raises(ValidationError):
        PlatformBinding.model_validate(binding("https://platform.internal?access_token=abc"))
    with pytest.raises(ValidationError):
        PlatformBinding.model_validate(binding("https://platform.internal", secret="abc"))


def test_the_service_answers_each_operation_for_a_real_token(platform: Platform) -> None:
    service = platform.service
    token = platform.company_token.grant.token_id
    probe = service.probe(token, SECRET)
    assert probe.identity.actor == "engineer" and probe.identity.bridge_id == BRIDGE
    # Somebody without the secret learns nothing else.
    with pytest.raises(ServiceError, match="authentication_failed"):
        service.probe(token, "not-the-secret-but-long-enough-to-present")
    with pytest.raises(ServiceError, match="authentication_failed"):
        service.probe("token-nobody", SECRET)
    # A payload naming another device is refused whatever it says.
    shared = platform.shared_token.grant.token_id
    assert service.probe(shared, SHARED_SECRET).identity.actor == "shared-bot"
    with pytest.raises(ServiceError, match="device_mismatch"):
        service.advertise(
            shared,
            SHARED_SECRET,
            AdvertiseRequest(
                registration=BridgeRegistration(
                    bridge_id=BRIDGE, owner_id="engineer", trace=trace("adv")
                )
            ),
        )
    with pytest.raises(ServiceError, match="device_mismatch"):
        service.report(
            shared,
            SHARED_SECRET,
            ReportRequest(
                snapshot={
                    "device": platform.enrollment.device(BRIDGE),
                    "observed_at": NOW,
                }
            ),
        )
    with pytest.raises(ServiceError, match="unknown_operation"):
        service.handle("shutdown", token, SECRET, {})
    with pytest.raises(ServiceError, match="invalid_request"):
        service.handle("settle", token, SECRET, {"job_id": "job-1"})
    # The sync sends the bundle and the bytes for what the Bridge lacks, and
    # nothing for what it has.
    everything = service.synchronize(token, SECRET, SyncRequest())
    assert everything.plan is not None and len(everything.plan.packages) == 2
    assert {item.artifact_ref for item in everything.artifacts} == set(platform.artifacts)
    partial = service.synchronize(token, SECRET, SyncRequest(installed=(WORKFLOW,)))
    assert partial.plan is not None and [p.kind for p in partial.plan.packages] == ["skill"]
    nothing = service.synchronize(token, SECRET, SyncRequest(installed=(WORKFLOW, SKILL)))
    assert nothing.plan is None and nothing.artifacts == ()
    assert len(nothing.authorization.selections) == 3
    # Once the secret is proved, the holder is told what is actually wrong.
    platform.tokens.revoke("engineer", token)
    with pytest.raises(ServiceError, match="token_revoked"):
        service.probe(token, SECRET)
    platform.enrollment.unbind("engineer", "bridge-shared", "shared-bot")
    with pytest.raises(ServiceError, match="binding_withdrawn"):
        service.probe(shared, SHARED_SECRET)


def test_health_and_bad_requests_over_http(server: ControlPlaneServer, platform: Platform) -> None:
    base = server.base_url
    assert http(base, "GET", "/v1/health") == (200, {"ok": True})
    assert http(base, "GET", "/v1/probe")[1]["code"] == "unknown_operation"
    assert http(base, "POST", "/other", b"{}")[0] == 404
    assert http(base, "POST", "/v1/shutdown", b"{}", Authorization="Bearer a:b") == (
        404,
        {"code": "unknown_operation", "retryable": False},
    )
    # No credential, a credential of the wrong shape, and a wrong one.
    assert http(base, "POST", "/v1/probe", b"{}")[0] == 401
    assert http(base, "POST", "/v1/probe", b"{}", Authorization="Bearer nocolon")[0] == 401
    assert http(base, "POST", "/v1/probe", b"{}", Authorization="Basic a:b")[0] == 401
    credential = f"Bearer {platform.company_token.grant.token_id}:{SECRET}"
    assert http(base, "POST", "/v1/probe", b"{}", Authorization=credential)[0] == 200
    status, body = http(base, "POST", "/v1/poll", b"not json", Authorization=credential)
    assert (status, body["code"]) == (400, "invalid_request")
    request = urllib.request.Request(
        base + "/v1/poll",
        data=b"{}",
        method="POST",
        headers={"Authorization": credential, "Content-Length": str(64 * 1024 * 1024)},
    )
    with pytest.raises(urllib.error.HTTPError) as too_large:
        urllib.request.urlopen(request, timeout=5)
    assert too_large.value.code == 413
    # Nothing in any reply names the software or echoes the request.
    with urllib.request.urlopen(base + "/v1/health", timeout=5) as reply:
        assert reply.headers["Server"] == "control-plane"
        assert reply.headers["Cache-Control"] == "no-store"


def test_a_probe_names_the_actor_and_every_answer_is_classified(
    tmp_path: Path, server: ControlPlaneServer, platform: Platform
) -> None:
    config, layout, runtime = host(tmp_path, platform, server.base_url)
    with runtime:
        assert runtime.platform is not None
        answered = run(runtime.platform.probe())
        assert answered.status == "answered" and answered.reply is not None
        assert answered.reply.identity.actor == "engineer"
        assert answered.reply.identity.bridge_id == BRIDGE
    # The secret does not match: this host's configuration is wrong.
    rejected = run(client(platform, server.base_url, secret="wrong-" + SECRET).probe())
    assert rejected.status == "rejected" and rejected.failure is not None
    assert rejected.failure.code == "authentication_failed" and not rejected.failure.retryable
    # The platform, to a Bridge that proved its secret, says it is gone.
    platform.tokens.revoke("engineer", platform.company_token.grant.token_id)
    withdrawn = run(client(platform, server.base_url).probe())
    assert withdrawn.status == "withdrawn" and withdrawn.failure is not None
    assert withdrawn.failure.code == "token_revoked" and not withdrawn.failure.retryable
    # Anything else the platform declined.
    refused = run(
        client(platform, server.base_url, secret=SHARED_SECRET).advertise(
            BridgeRegistration(bridge_id=BRIDGE, owner_id="engineer", trace=trace("adv"))
        )
    )
    assert refused.status == "rejected"  # the company token id with the shared secret
    shared_client = PlatformClient(
        PlatformBinding.model_validate(
            binding(server.base_url, token_id=platform.shared_token.grant.token_id)
        ),
        StaticCredentials({"platform_token": SHARED_SECRET}),
    )
    refused = run(
        shared_client.advertise(
            BridgeRegistration(bridge_id=BRIDGE, owner_id="engineer", trace=trace("adv"))
        )
    )
    assert refused.status == "refused" and refused.failure is not None
    assert refused.failure.code == "device_mismatch"
    # Unreachable is never revoked: a dead platform, a platform answering
    # 5xx, and an intermediary's bare 401 all leave the token alone.
    base = server.base_url
    server.stop()
    dead = run(client(platform, base).probe())
    assert dead.status == "unreachable" and dead.failure is not None
    assert dead.failure.retryable and dead.failure.code == "platform_unreachable"
    for status, body in (
        (500, b'{"code":"internal_error","retryable":true}'),
        (401, b""),
        (503, b"down"),
    ):
        canned = PlatformClient(
            PlatformBinding.model_validate(binding("http://127.0.0.1:1", token_id="token-x")),
            StaticCredentials({"platform_token": SECRET}),
            transport=CannedTransport(status, body),
        )
        outcome = run(canned.probe())
        assert outcome.status == "unreachable" and outcome.failure is not None
        assert outcome.failure.retryable, status
    # And no failure ever carries the secret.
    for outcome in (rejected, withdrawn, refused, dead):
        assert SECRET not in outcome.model_dump_json()
        assert SHARED_SECRET not in outcome.model_dump_json()
    # A probe is read-only: nothing arrived on the Bridge for any of it.
    assert not layout.authorization.exists()
    assert not any(layout.workflows.glob("*.json"))


def test_sync_installs_what_the_member_chose_onto_a_real_host(
    tmp_path: Path, server: ControlPlaneServer, platform: Platform
) -> None:
    config, layout, runtime = host(tmp_path, platform, server.base_url)
    with runtime:
        assert runtime.platform is not None
        # Before the sync this host can run nothing: no asset, no decision.
        before = run(runtime.agent.handle(_ask(runtime, "files.read notes.txt")))
        assert before.decision is not None and before.decision.kind == "needs_input"
        outcome = run(runtime.platform.synchronize(layout, runtime.state))
        assert outcome.status == "answered", outcome.failure
        assert {item.name for item in outcome.installed} == {"read-local-file", "file-skill"}
        assert outcome.selections == 3
        assert sorted(path.name for path in layout.workflows.glob("*.json")) == [
            "engineering__read-local-file__1.0.0.json"
        ]
        assert sorted(path.name for path in layout.skills.glob("*.json")) == [
            "engineering__file-skill__1.0.0.json"
        ]
        assert {item.identity.name for item in runtime.state.installed()} == {
            "read-local-file",
            "file-skill",
        }
        bundle = DeviceAuthorization.model_validate_json(
            layout.authorization.read_text(encoding="utf-8")
        )
        assert bundle.bridge_id == BRIDGE and len(bundle.selections) == 3
        # Nothing new the second time; the bundle is rewritten as it stands.
        again = run(runtime.platform.synchronize(layout, runtime.state))
        assert again.status == "answered" and again.installed == () and again.selections == 3
    # The rebuilt host runs the synced Workflow through the real Gateway,
    # with the grant the member's tool decision derived.
    with build_runtime(
        config, layout=layout, resolver=StaticCredentials({"platform_token": SECRET})
    ) as rebuilt:
        outcome = run(rebuilt.agent.handle(_ask(rebuilt, "files.read notes.txt")))
        assert outcome.refusal is None and outcome.workflow is not None
        assert outcome.workflow.run.status == "succeeded", outcome.workflow.run.failure
        assert outcome.run is not None and outcome.run.actor == "engineer"
        # What this host can run, and what it holds, reach the platform.
        assert rebuilt.platform is not None
        advertised = run(rebuilt.platform.advertise(advertisement(rebuilt.agent, "adv-1")))
        # The bounded file read, and the Workflow drafter every host installs
        # -- the latter whether or not a model is configured, so that "why can
        # I not draft" is a sentence rather than a missing capability, exactly
        # as the Excel writer installs on a machine without Excel.
        assert advertised.status == "answered" and advertised.capabilities == 2
        assert platform.enrollment.advertisement(BRIDGE).trace.trace_id == "adv-1"
        reported = run(
            rebuilt.platform.report(rebuilt.agent.snapshot(observed_at=datetime.now(UTC)))
        )
        assert reported.status == "answered"
        view = platform.control.view(BRIDGE, now=datetime.now(UTC))
        assert view.connectivity == "online" and len(view.snapshot.installed) == 2
        assert [item.status for item in view.snapshot.runs] == ["succeeded"]


def _ask(runtime: HostRuntime, message: str) -> Any:
    from common.local_agent import LocalAgentRequest

    return LocalAgentRequest(
        ingress="local",
        actor="engineer",
        bridge_id=BRIDGE,
        namespace="engineering",
        message=message,
        trace=trace(message.replace(" ", "-").replace(".", "-")),
    )


def _untouched(layout: HostLayout) -> None:
    assert not layout.authorization.exists()
    assert not list(layout.workflows.glob("*.json")) and not list(layout.skills.glob("*.json"))


def test_sync_refuses_and_leaves_the_workspace_untouched(
    tmp_path: Path, platform: Platform
) -> None:
    with ControlPlaneServer(platform.service) as server:
        # grants.json is the operator's own answer; refused before any call.
        config, layout, runtime = host(tmp_path / "grants", platform, server.base_url)
        layout.grants.write_text("[]", encoding="utf-8")
        counting = CountingTransport()
        watched = PlatformClient(
            config.platform,  # type: ignore[arg-type]
            StaticCredentials({"platform_token": SECRET}),
            transport=counting,
        )
        with runtime:
            refused = run(watched.synchronize(layout, runtime.state))
            assert refused.status == "refused" and refused.failure is not None
            assert refused.failure.code == "sync_grants_conflict" and counting.calls == []
            _untouched(layout)
        # A tampered artifact: the platform's store no longer matches what
        # it published.
        config, layout, runtime = host(tmp_path / "tampered", platform, server.base_url)
        ref = next(iter(platform.artifacts))
        original = platform.artifacts[ref]
        platform.artifacts[ref] = original + b" "
        with runtime:
            assert runtime.platform is not None
            refused = run(runtime.platform.synchronize(layout, runtime.state))
            assert refused.status == "refused" and refused.failure is not None
            assert refused.failure.code == "sync_artifact_hash_mismatch"
            _untouched(layout)
            assert runtime.state.installed() == ()
        platform.artifacts[ref] = original
        # A hand-placed asset of the same identity with different bytes is a
        # conflict; with the same bytes it is already done.
        config, layout, runtime = host(tmp_path / "conflict", platform, server.base_url)
        other = json.dumps({**workflow_manifest(), "description": "placed by hand"})
        (layout.workflows / "mine.json").write_text(other, encoding="utf-8")
        with runtime:
            assert runtime.platform is not None
            refused = run(runtime.platform.synchronize(layout, runtime.state))
            assert refused.status == "refused" and refused.failure is not None
            assert refused.failure.code == "sync_asset_conflict"
            assert not layout.authorization.exists() and runtime.state.installed() == ()
            (layout.workflows / "mine.json").unlink()
            planned = layout.workflows / "engineering__read-local-file__1.0.0.json"
            planned.write_bytes(platform.artifacts[ref])
            finished = run(runtime.platform.synchronize(layout, runtime.state))
            assert finished.status == "answered" and len(finished.installed) == 2
    # Bytes that describe another asset than the package claims.
    impostor = Platform(
        workflow_bytes=json.dumps(
            {
                **workflow_manifest(),
                "metadata": {
                    **workflow_manifest()["metadata"],
                    "identity": {"namespace": "engineering", "name": "other", "version": "1.0.0"},
                },
            }
        ).encode("utf-8")
    )
    with ControlPlaneServer(impostor.service) as server:
        config, layout, runtime = host(tmp_path / "impostor", impostor, server.base_url)
        with runtime:
            assert runtime.platform is not None
            refused = run(runtime.platform.synchronize(layout, runtime.state))
            assert refused.status == "refused" and refused.failure is not None
            assert refused.failure.code == "sync_asset_invalid"
            _untouched(layout)


def test_jobs_are_polled_run_settled_and_reported(
    tmp_path: Path, server: ControlPlaneServer, platform: Platform
) -> None:
    config, layout, runtime = host(tmp_path, platform, server.base_url)
    with runtime:
        assert runtime.platform is not None
        assert run(runtime.platform.synchronize(layout, runtime.state)).status == "answered"
    with build_runtime(
        config, layout=layout, resolver=StaticCredentials({"platform_token": SECRET})
    ) as runtime:
        assert runtime.platform is not None
        platform.submit("job-ran")
        platform.submit("job-cancelled")
        platform.control.cancel("job-cancelled", actor="engineer")
        absent = AssetIdentity(namespace="engineering", name="absent", version="1.0.0")
        platform.submit("job-rejected", workflow=absent)
        outcome = run(runtime.platform.poll_jobs(runtime.agent))
        assert outcome.status == "answered" and outcome.reported
        assert [(d.job_id, d.disposition, d.settled) for d in outcome.deliveries] == [
            ("job-ran", "ran", True),
            ("job-cancelled", "cancelled", True),
            ("job-rejected", "rejected", True),
        ]
        ran = platform.control.job("job-ran")
        assert ran.status == "ran" and ran.run is not None
        assert ran.run.status == "succeeded" and ran.run.actor == "engineer"
        # The platform holds the very record the Bridge stored.
        assert ran.run == runtime.agent.runs()[0]
        assert platform.control.job("job-cancelled").status == "cancelled"
        assert platform.control.job("job-rejected").status == "rejected"
        # The queue is drained, the cancelled job never ran, and the
        # platform's view of this Bridge is current.
        assert platform.control.poll(BRIDGE, limit=10) == ()
        assert [item.run_id for item in runtime.agent.runs()] == [ran.run.run_id]
        view = platform.control.view(BRIDGE, now=datetime.now(UTC))
        assert view.connectivity == "online" and len(view.snapshot.runs) == 1
        # A second poll with nothing waiting is an answered poll.
        idle = run(runtime.platform.poll_jobs(runtime.agent))
        assert idle.status == "answered" and idle.deliveries == ()
        # An idle poll right after a report does not ship the snapshot again.
        assert not idle.reported
    # A settle is refused for a settled job, for another device, and for a
    # run that names another actor.
    token = platform.company_token.grant.token_id
    with pytest.raises(ServiceError, match="job_settled"):
        platform.service.settle(
            token, SECRET, SettleRequest(job_id="job-ran", disposition="rejected")
        )
    platform.submit("job-open")
    with pytest.raises(ServiceError, match="device_mismatch"):
        platform.service.settle(
            platform.shared_token.grant.token_id,
            SHARED_SECRET,
            SettleRequest(job_id="job-open", disposition="cancelled"),
        )
    with pytest.raises(ServiceError, match="job_mismatch"):
        platform.service.settle(
            token,
            SECRET,
            SettleRequest(
                job_id="job-open",
                disposition="ran",
                run=LocalRunSummary(
                    run_id="run-x",
                    actor="tester",
                    workflow=WORKFLOW,
                    status="succeeded",
                    updated_at=NOW,
                ),
            ),
        )
    with pytest.raises(ServiceError, match="job_missing"):
        platform.service.settle(
            token, SECRET, SettleRequest(job_id="job-nobody", disposition="cancelled")
        )
    with pytest.raises(ControlError, match="job_settled"):
        platform.control.cancel("job-ran", actor="engineer")


def test_the_loop_ends_on_a_rejected_token_and_backs_off_when_unreachable(
    tmp_path: Path, server: ControlPlaneServer, platform: Platform
) -> None:
    config, layout, runtime = host(tmp_path, platform, server.base_url, secret="wrong-" + SECRET)
    with runtime:
        assert runtime.platform is not None
        stop = asyncio.Event()
        failure = run(runtime.platform.run_jobs(runtime.agent, stop, interval_s=0.01))
        assert failure is not None and failure.code == "authentication_failed"
        # Unreachable: the loop keeps trying, more slowly, until asked to stop.
        canned = CannedTransport(0, b"", error=ConnectionRefusedError("refused"))
        stop = asyncio.Event()
        canned.stop = stop
        patient = PlatformClient(
            config.platform,  # type: ignore[arg-type]
            StaticCredentials({"platform_token": SECRET}),
            transport=canned,
        )
        started = datetime.now(UTC)
        assert run(patient.run_jobs(runtime.agent, stop, interval_s=0.01)) is None
        assert canned.calls >= 3
        assert datetime.now(UTC) - started < timedelta(seconds=5)
        # Nothing on this host changed for any of it.
        assert not layout.authorization.exists() and runtime.state.installed() == ()


def test_the_cli_probes_syncs_and_runs_jobs(
    tmp_path: Path,
    server: ControlPlaneServer,
    platform: Platform,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, layout, runtime = host(tmp_path, platform, server.base_url)
    runtime.close()
    path = host_json(tmp_path, config)
    # The token's secret comes from the environment the host mapped.
    monkeypatch.setenv("AEP_PLATFORM_TOKEN", SECRET)
    report = host_report(config, layout)
    assert {c.name: c.status for c in report.checks}["platform"] == "passed"
    assert main(["probe", "--config", str(path)]) == 0
    assert "knows this host as engineer on bridge-company" in capsys.readouterr().out
    assert main(["sync", "--config", str(path)]) == 0
    out = capsys.readouterr().out
    assert "2 asset(s) installed, 3 decision(s)" in out and "advertised: answered" in out
    platform.submit("job-cli")
    assert main(["jobs", "--config", str(path), "--once"]) == 0
    assert "job-cli: ran, settled" in capsys.readouterr().out
    assert platform.control.job("job-cli").status == "ran"
    assert main(["status", "--config", str(path)]) == 0
    assert "installed: 2 asset(s)" in capsys.readouterr().out
    # A secret whose variable is empty is refused at the call and says so;
    # a secret nothing is mapped to stops the host from being built at all;
    # without a platform the commands say so; with a wrong secret the probe
    # says what to fix.
    monkeypatch.delenv("AEP_PLATFORM_TOKEN")
    assert main(["probe", "--config", str(path)]) == 1
    assert "credential_unavailable" in capsys.readouterr().out
    unmapped = config.model_copy(update={"credentials": ()})
    assert {c.name: c.status for c in host_report(unmapped, layout).checks}["platform"] == "failed"
    (tmp_path / "unmapped").mkdir()
    unmapped_path = host_json(tmp_path / "unmapped", unmapped)
    assert main(["probe", "--config", str(unmapped_path)]) == 2
    assert "credential_unmapped" in capsys.readouterr().err
    local = config.model_copy(update={"platform": None, "credentials": ()})
    assert {c.name: c.status for c in host_report(local, layout).checks}["platform"] == "pending"
    (tmp_path / "local").mkdir()
    local_path = host_json(tmp_path / "local", local)
    assert main(["probe", "--config", str(local_path)]) == 2
    assert "no shared platform is configured" in capsys.readouterr().err
    monkeypatch.setenv("AEP_PLATFORM_TOKEN", "wrong-" + SECRET)
    assert main(["probe", "--config", str(path)]) == 1
    assert "does not recognise this host's token" in capsys.readouterr().out
    assert main(["jobs", "--config", str(path), "--once"]) == 1
    # A dead platform is reported as unreachable, never as a revocation.
    monkeypatch.setenv("AEP_PLATFORM_TOKEN", SECRET)
    server.stop()
    assert main(["probe", "--config", str(path)]) == 1
    assert "could not be reached; nothing on this host changed" in capsys.readouterr().out


class InterceptingTransport:
    """The real transport, except that settle calls are answered from a
    queue of canned replies while it lasts."""

    def __init__(self, canned: list[tuple[int, bytes]]) -> None:
        self.inner = UrllibTransport()
        self.canned = canned

    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> Any:
        if url.endswith("/v1/settle") and self.canned:
            status, reply = self.canned.pop(0)
            return CannedReply(status, reply)
        return self.inner.send(url, body, headers, timeout_s)


def slow_agent(tmp_path: Path) -> tuple[LocalAgent, Any]:
    """An Agent whose one workflow outlives a short wait, over the
    repository's real engine."""
    gateway, bridge = slow_gateway()
    membership = company_membership()
    return LocalAgent(membership, gateway, state_for(membership, tmp_path)), bridge


def test_a_job_that_outlives_the_wait_is_settled_when_it_ends(
    tmp_path: Path, server: ControlPlaneServer, platform: Platform
) -> None:
    agent, bridge = slow_agent(tmp_path)
    impatient = PlatformClient(
        PlatformBinding.model_validate(
            binding(server.base_url, token_id=platform.company_token.grant.token_id)
        ),
        StaticCredentials({"platform_token": SECRET}),
        workflow_timeout_seconds=0.02,
    )
    platform.submit("job-slow", workflow=VALIDATION, arguments={})
    outcome = run(impatient.poll_jobs(agent))
    delivery = outcome.deliveries[0]
    # The wait saw a timeout; the settle waited for the run to actually end.
    assert delivery.outcome is not None and delivery.outcome.workflow is not None
    failure = delivery.outcome.workflow.run.failure
    assert failure is not None and failure.code == "workflow_timeout"
    assert delivery.disposition == "ran" and delivery.settled
    record = platform.control.job("job-slow")
    assert record.status == "ran" and record.run is not None
    assert record.run.status == "succeeded"
    assert [item.status for item in agent.runs()] == ["succeeded"]
    # A settle that was lost, then a cancel: the Bridge already ran it, and
    # says so rather than calling it cancelled.
    platform.submit("job-lost", workflow=VALIDATION, arguments={})
    lost = platform.control.job("job-lost")
    run(agent.execute(lost.request))
    platform.control.cancel("job-lost", actor="engineer")
    outcome = run(impatient.poll_jobs(agent))
    delivery = outcome.deliveries[0]
    assert delivery.disposition == "ran" and delivery.settled and delivery.outcome is None
    assert platform.control.job("job-lost").status == "ran"
    assert len(agent.runs()) == 2 and len(bridge.events) == 2


def test_a_settle_declined_for_one_job_does_not_end_the_loop(
    tmp_path: Path, server: ControlPlaneServer, platform: Platform
) -> None:
    config, layout, runtime = host(tmp_path, platform, server.base_url)
    with runtime:
        assert runtime.platform is not None
        assert run(runtime.platform.synchronize(layout, runtime.state)).status == "answered"
    with build_runtime(
        config, layout=layout, resolver=StaticCredentials({"platform_token": SECRET})
    ) as runtime:
        # Another process settled it first, or the platform restarted: the
        # platform declines this settle, the delivery says so, the loop goes
        # on, and the next poll simply does not offer that job again.
        platform.submit("job-a")
        declined = PlatformClient(
            config.platform,  # type: ignore[arg-type]
            StaticCredentials({"platform_token": SECRET}),
            transport=InterceptingTransport([(409, b'{"code":"job_settled","retryable":false}')]),
        )
        outcome = run(declined.poll_jobs(runtime.agent))
        assert outcome.status == "answered"
        delivery = outcome.deliveries[0]
        assert delivery.disposition == "ran" and not delivery.settled
        assert delivery.failure is not None and delivery.failure.code == "job_settled"
        # Here the platform never actually heard the settle, so it offers
        # the job again; the Bridge joins the run it already started.
        again = run(declined.poll_jobs(runtime.agent))
        assert [(d.job_id, d.settled) for d in again.deliveries] == [("job-a", True)]
        assert len(runtime.agent.runs()) == 1
        # The platform saying this Bridge is no longer its member, in the
        # middle of a batch, stops the batch.
        platform.submit("job-b")
        platform.submit("job-c")
        thrown_out = PlatformClient(
            config.platform,  # type: ignore[arg-type]
            StaticCredentials({"platform_token": SECRET}),
            transport=InterceptingTransport([(401, b'{"code":"token_revoked","retryable":false}')]),
        )
        outcome = run(thrown_out.poll_jobs(runtime.agent))
        assert outcome.status == "withdrawn" and len(outcome.deliveries) == 1
        assert outcome.deliveries[0].job_id == "job-b"
        assert platform.control.job("job-c").status == "queued"
        assert len(runtime.agent.runs()) == 2
        assert layout.authorization.exists()


def test_one_asset_is_planned_once_however_many_selections_name_it(platform: Platform) -> None:
    """A decision left behind by a member since unbound and a new member's
    decision about the same asset are one installation."""
    platform.enrollment.issue(
        Invitation(
            invitation_id="invite-tester",
            actor="tester",
            issued_by="platform-admin",
            groups=("engineering",),
        )
    )
    platform.enrollment.accept("invite-tester", "tester")
    platform.authorization.select(
        signed_in("shared-bot"),
        DeviceAssetSelection(
            bridge_id="bridge-shared",
            actor="shared-bot",
            kind="workflow",
            asset=WORKFLOW,
            decided_at=NOW,
        ),
        now=NOW,
    )
    platform.enrollment.unbind("engineer", "bridge-shared", "shared-bot")
    platform.enrollment.bind(
        "engineer", BridgeBinding(bridge_id="bridge-shared", actor="tester", role="operator")
    )
    platform.authorization.select(
        signed_in("tester"),
        DeviceAssetSelection(
            bridge_id="bridge-shared",
            actor="tester",
            kind="workflow",
            asset=WORKFLOW,
            decided_at=NOW,
        ),
        now=NOW,
    )
    token = platform.tokens.issue(
        "engineer", "tester", "bridge-shared", issued_at=NOW, secret=SECRET + "-tester"
    )
    reply = platform.service.synchronize(token.grant.token_id, token.secret, SyncRequest())
    assert len(reply.authorization.selections) == 2
    assert reply.plan is not None
    assert [item.metadata.identity for item in reply.plan.packages] == [WORKFLOW]


def test_the_platforms_own_inconsistency_is_reported_as_such(tmp_path: Path) -> None:
    shadow = Platform(shadow=True)
    with ControlPlaneServer(shadow.service) as server:
        credential = f"Bearer {shadow.company_token.grant.token_id}:{SECRET}"
        status, body = http(server.base_url, "POST", "/v1/sync", b"{}", Authorization=credential)
        assert (status, body) == (500, {"code": "internal_error", "retryable": True})
        config, layout, runtime = host(tmp_path, shadow, server.base_url)
        with runtime:
            assert runtime.platform is not None
            outcome = run(runtime.platform.synchronize(layout, runtime.state))
            assert outcome.status == "unreachable" and outcome.failure is not None
            assert outcome.failure.retryable and outcome.failure.code == "platform_http_error"
            _untouched(layout)


def test_one_request_per_connection(server: ControlPlaneServer, platform: Platform) -> None:
    """A refusal sent before the body was read closes the connection, so the
    unread body is never parsed as the next request."""
    host_name, port = server.server_address[0], server.server_address[1]
    credential = f"Bearer {platform.company_token.grant.token_id}:{SECRET}"
    connection = HTTPConnection(str(host_name), int(port), timeout=5)
    connection.request(
        "POST",
        "/v1/poll",
        body=b"{}",
        headers={"Authorization": credential, "Content-Length": str(64 * 1024 * 1024)},
    )
    reply = connection.getresponse()
    assert reply.status == 413 and reply.getheader("Connection") == "close"
    reply.read()
    # The server refused before reading the body and said it was closing, so
    # the rest of that body never reaches the next request. Reconnect rather
    # than write into a socket the peer has already closed on us: Windows
    # answers that with a reset, which is the test racing, not the server.
    connection.close()
    connection.request("GET", "/v1/health")
    reply = connection.getresponse()
    assert reply.status == 200 and json.loads(reply.read()) == {"ok": True}
    connection.request(
        "POST",
        "/v1/poll",
        body=b"2\r\n{}\r\n0\r\n\r\n",
        headers={"Authorization": credential, "Transfer-Encoding": "chunked"},
    )
    reply = connection.getresponse()
    assert reply.status == 400 and json.loads(reply.read())["code"] == "invalid_request"
    connection.close()


def test_a_bundle_that_cannot_be_written_is_reported_with_what_was_installed(
    tmp_path: Path, server: ControlPlaneServer, platform: Platform
) -> None:
    config, layout, runtime = host(tmp_path, platform, server.base_url)
    # A directory where the bundle would go: the one write after the
    # inventory is recorded fails, and the outcome hides neither fact.
    layout.authorization.mkdir()
    with runtime:
        assert runtime.platform is not None
        outcome = run(runtime.platform.synchronize(layout, runtime.state))
        assert outcome.status == "refused" and outcome.failure is not None
        assert outcome.failure.code == "sync_workspace_unwritable"
        assert {item.name for item in outcome.installed} == {"read-local-file", "file-skill"}
        assert len(runtime.state.installed()) == 2


def test_a_bridge_clock_a_little_ahead_still_reports_now(platform: Platform) -> None:
    """Two machines, two clocks. Received no earlier than observed is what
    the projection promises; a Bridge a little ahead is reporting now, and
    one far ahead is not reporting at all."""
    behind = datetime.now(UTC) - timedelta(seconds=30)
    service = ControlPlaneService(
        enrollment=platform.enrollment,
        tokens=platform.tokens,
        packages=platform.packages,
        authorization=platform.authorization,
        control=platform.control,
        artifacts=platform.artifacts,
        clock=lambda: behind,
    )
    token = platform.company_token.grant.token_id
    observed = datetime.now(UTC)
    snapshot = {"device": platform.enrollment.device(BRIDGE), "observed_at": observed}
    reply = service.report(token, SECRET, ReportRequest.model_validate({"snapshot": snapshot}))
    assert reply.received_at == observed
    assert platform.control.view(BRIDGE, now=datetime.now(UTC)).connectivity == "online"
    far = {**snapshot, "observed_at": datetime.now(UTC) + timedelta(minutes=10)}
    with pytest.raises(ServiceError, match="invalid_request"):
        service.report(token, SECRET, ReportRequest.model_validate({"snapshot": far}))


def test_the_server_names_its_address_as_a_url(platform: Platform) -> None:
    with ControlPlaneServer(platform.service) as server:
        assert PlatformBinding.model_validate(binding(server.base_url)).base_url == server.base_url
    try:
        six = ControlPlaneServer(platform.service, host="::1")
    except OSError:
        pytest.skip("no IPv6 loopback on this machine")
    with six:
        assert six.base_url.startswith("http://[::1]:")
        assert PlatformBinding.model_validate(binding(six.base_url)).base_url == six.base_url
