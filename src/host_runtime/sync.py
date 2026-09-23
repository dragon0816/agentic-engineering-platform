"""The Bridge's side of the shared-platform wire.

Six operations, each presented with this machine's access token, and every
answer classified into exactly one of five things before anything is done
with it: `answered`; `unreachable`, which is retryable and changes nothing;
`withdrawn`, which is the platform telling a Bridge that proved its secret
that its token or binding is gone; `rejected`, which is a secret the platform
does not recognise and so a configuration this host has to fix; and
`refused`, which is anything else the platform declined. Only `answered`
changes anything on this machine.

That classification is the invariant carried from the pinned Host Bridge's
`Test-DeviceBinding` (`docs/PHASE_7_MIGRATION.md`): unreachable is never
treated as revoked. A closed laptop lid, a changed network, a proxy answering
for a platform that is down, all leave the token, the authorization and the
installed assets exactly where they are, and the Bridge keeps doing local
work with what it has.

Synchronization is the one operation that writes, and it writes only after
the whole reply has been verified: every digest, every manifest, every file
it would touch. A refusal at any step leaves the workspace untouched.
"""

import asyncio
import json
import os
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Literal

from pydantic import Field, StrictBool, ValidationError

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest
from common.base import Contract, Symbol
from common.distribution import (
    BridgeStateSnapshot,
    InstallationPlan,
    LocalRunSummary,
    LocalStateError,
    LocalStateErrorCode,
    RemoteJobRecord,
    RemoteWorkflowJob,
    verify_installation,
)
from common.execution import Failure, TraceIdentifiers
from common.sync import (
    WITHDRAWN,
    AdvertiseReply,
    AdvertiseRequest,
    JobDisposition,
    PollReply,
    PollRequest,
    ProbeReply,
    ReportReply,
    ReportRequest,
    SettleRequest,
    SyncReply,
    SyncRequest,
    WireFailure,
)
from host_runtime.agent import LocalAgent, LocalAgentOutcome
from host_runtime.contracts import HostLayout, PlatformBinding
from host_runtime.state import SqliteLocalState
from models.credentials import CredentialMisconfigured, CredentialResolver
from models.wire import (
    RETRYABLE_STATUS,
    Transport,
    UrllibTransport,
    close_quietly,
    describe,
    status_failure,
    transport_failure,
)
from workflow.engine import WorkflowRunSnapshot
from workflow.host_bridge import BridgeRegistration

Reachability = Literal["answered", "unreachable", "withdrawn", "rejected", "refused"]
# What will not fix itself by asking again, and so ends a loop when a poll
# answers it.
FINAL: frozenset[str] = frozenset({"withdrawn", "rejected", "refused"})
# What ends a loop when a settle answers it: the platform no longer knows
# this Bridge. A settle it declined for one job is that job's business.
ENDS_LOOP: frozenset[str] = frozenset({"withdrawn", "rejected"})
# How long `run_jobs` waits after a retryable failure before polling again, at most.
MAX_BACKOFF_SECONDS = 300.0
# How often an idle job loop still reports the Bridge's state.
REPORT_EVERY_SECONDS = 60.0

SyncRefusalCode = (
    LocalStateErrorCode
    | Literal["grants_conflict", "asset_invalid", "asset_conflict", "workspace_unwritable"]
)


class SyncRefused(Exception):
    """This Bridge would not apply what the platform sent, or could not
    finish applying it. `installed` is what had already been recorded when
    that happened: empty for every refusal before the first write, and the
    recorded rows when the one write after them, the bundle, failed."""

    def __init__(self, code: SyncRefusalCode, installed: tuple[AssetIdentity, ...] = ()) -> None:
        self.code: SyncRefusalCode = code
        self.installed = installed
        super().__init__(code)


class ProbeOutcome(Contract):
    status: Reachability
    failure: Failure | None = None
    reply: ProbeReply | None = None


class AdvertiseOutcome(Contract):
    status: Reachability
    failure: Failure | None = None
    capabilities: int | None = Field(default=None, ge=0, strict=True)


class SyncOutcome(Contract):
    """What a synchronization did. `installed` is what this call recorded,
    which on a refusal is empty unless the bundle was the one write that
    failed; `selections` is how many decisions the bundle now carries."""

    status: Reachability
    failure: Failure | None = None
    installed: tuple[AssetIdentity, ...] = ()
    selections: int | None = Field(default=None, ge=0, strict=True)


class ReportOutcome(Contract):
    status: Reachability
    failure: Failure | None = None
    received_at: datetime | None = None


class JobDelivery(Contract):
    """What became of one polled job on this Bridge. `settled` says whether
    the platform accepted the answer; when it did not, the job stays open
    there and is offered again, and the idempotency key keeps it from running
    twice."""

    job_id: Symbol
    disposition: JobDisposition
    settled: StrictBool
    outcome: LocalAgentOutcome | None = None
    failure: Failure | None = None


class JobsOutcome(Contract):
    status: Reachability
    failure: Failure | None = None
    deliveries: tuple[JobDelivery, ...] = ()
    reported: StrictBool = False


class _Answer:
    """One classified reply. `data` is the parsed body when answered."""

    __slots__ = ("data", "failure", "status")

    def __init__(self, status: Reachability, failure: Failure | None, data: object) -> None:
        self.status = status
        self.failure = failure
        self.data = data


def _documents(path: Path) -> Iterator[object]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    yield from payload if isinstance(payload, list) else [payload]


def _identities_on_disk(directory: Path) -> dict[tuple[str, str, str], tuple[Path, bytes]]:
    """Every asset identity a directory already holds, with where and as
    what, so a sync never writes a second answer to an identity an operator
    placed by hand."""
    found: dict[tuple[str, str, str], tuple[Path, bytes]] = {}
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.json")):
        try:
            content = path.read_bytes()
            for item in _documents(path):
                metadata = item.get("metadata") if isinstance(item, dict) else None
                identity = metadata.get("identity") if isinstance(metadata, dict) else None
                found[AssetIdentity.model_validate(identity).key] = (path, content)
        except (OSError, ValueError, ValidationError):
            raise SyncRefused("asset_invalid") from None
    return found


def _write_atomically(path: Path, content: bytes) -> None:
    """A file appears whole or not at all, so a host that is rebuilt halfway
    through a sync never reads half a manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(content)
    os.replace(temporary, path)


class PlatformClient:
    """One Bridge talking to one platform as one token. Nothing on this
    object holds the secret: it is resolved for each call and dropped."""

    def __init__(
        self,
        binding: PlatformBinding,
        resolver: CredentialResolver,
        *,
        transport: Transport | None = None,
        workflow_timeout_seconds: float | None = None,
    ) -> None:
        self.binding = PlatformBinding.model_validate(binding)
        self._resolver = resolver
        self._transport = transport if transport is not None else UrllibTransport()
        # How long a polled job's workflow is waited on before the Agent
        # reports it still running; the engine's default when None. A run
        # that outlives it is still waited for before it is settled.
        self._workflow_timeout_seconds = workflow_timeout_seconds
        self._reported_at: float | None = None

    def _call(self, operation: str, payload: Contract | None) -> _Answer:
        """One operation over the wire, classified. Blocking; the async
        methods run it on a thread so the Agent's runs are never held up."""
        try:
            secret = self._resolver.resolve(self.binding.credential)
        except CredentialMisconfigured as error:
            return _Answer(
                "refused",
                Failure(code="platform_credential_unavailable", message=describe(error)),
                None,
            )
        except Exception as error:  # noqa: BLE001 - a store caught mid-rotation
            return _Answer(
                "unreachable",
                Failure(
                    code="platform_credential_unavailable",
                    message=describe(error),
                    retryable=True,
                ),
                None,
            )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.binding.token_id}:{secret}",
        }
        body = payload.model_dump_json().encode("utf-8") if payload is not None else b"{}"
        try:
            reply = self._transport.send(
                f"{self.binding.base_url}/v1/{operation}",
                body,
                headers,
                float(self.binding.timeout_seconds),
            )
        except Exception as error:  # noqa: BLE001 - every transport fault is one answer
            return _Answer("unreachable", transport_failure(error, prefix="platform"), None)
        try:
            raw = b"".join(reply.chunks())
        except Exception as error:  # noqa: BLE001 - a body cut short is unreachable too
            return _Answer("unreachable", transport_failure(error, prefix="platform"), None)
        finally:
            close_quietly(reply)
        try:
            data: object = json.loads(raw)
        except ValueError:
            data = None
        if reply.status == 200:
            if not isinstance(data, dict):
                return _Answer("unreachable", _bad_reply(), None)
            return _Answer("answered", None, data)
        try:
            declined: WireFailure | None = WireFailure.model_validate(data)
        except ValidationError:
            declined = None
        if declined is None or reply.status >= 500 or reply.status in RETRYABLE_STATUS:
            # Nothing the platform itself said, or a moment it will get
            # over: an intermediary's 401 is not a revocation.
            failure = status_failure(reply.status, raw, prefix="platform")
            return _Answer("unreachable", failure.model_copy(update={"retryable": True}), None)
        told = Failure(code=declined.code, message=f"the platform declined: {declined.code}")
        if declined.code in WITHDRAWN:
            return _Answer("withdrawn", told, None)
        if declined.code == "authentication_failed":
            return _Answer("rejected", told, None)
        return _Answer("refused", told, None)

    async def probe(self) -> ProbeOutcome:
        """Read-only: does the platform still know this machine as its
        member. Changes nothing on either side."""
        answer = await asyncio.to_thread(self._call, "probe", None)
        if answer.status != "answered":
            return ProbeOutcome(status=answer.status, failure=answer.failure)
        try:
            reply = ProbeReply.model_validate(answer.data)
        except ValidationError:
            return ProbeOutcome(status="unreachable", failure=_bad_reply())
        return ProbeOutcome(status="answered", reply=reply)

    async def advertise(self, registration: BridgeRegistration) -> AdvertiseOutcome:
        answer = await asyncio.to_thread(
            self._call, "advertise", AdvertiseRequest(registration=registration)
        )
        if answer.status != "answered":
            return AdvertiseOutcome(status=answer.status, failure=answer.failure)
        try:
            reply = AdvertiseReply.model_validate(answer.data)
        except ValidationError:
            return AdvertiseOutcome(status="unreachable", failure=_bad_reply())
        return AdvertiseOutcome(status="answered", capabilities=reply.capabilities)

    async def synchronize(self, layout: HostLayout, state: SqliteLocalState) -> SyncOutcome:
        """Bring this host's assets and authorization up to what its member
        decided. Refused before the call when `grants.json` is present: the
        bundle and a hand-written grants file are two answers to one
        question, and the host refuses to start with both."""
        if layout.grants.is_file():
            return SyncOutcome(status="refused", failure=_refusal("grants_conflict"))
        try:
            installed = await asyncio.to_thread(state.installed)
        except LocalStateError as error:
            return SyncOutcome(status="refused", failure=_refusal(error.code))
        request = SyncRequest(installed=tuple(item.identity for item in installed))
        answer = await asyncio.to_thread(self._call, "sync", request)
        if answer.status != "answered":
            return SyncOutcome(status=answer.status, failure=answer.failure)
        try:
            reply = SyncReply.model_validate(answer.data)
        except ValidationError:
            return SyncOutcome(status="unreachable", failure=_bad_reply())
        if reply.authorization.bridge_id != state.bridge_id:
            return SyncOutcome(status="refused", failure=_refusal("installation_bridge_mismatch"))
        try:
            added = await asyncio.to_thread(self._apply, reply, layout, state)
        except SyncRefused as error:
            return SyncOutcome(
                status="refused", failure=_refusal(error.code), installed=error.installed
            )
        return SyncOutcome(
            status="answered", installed=added, selections=len(reply.authorization.selections)
        )

    def _apply(
        self, reply: SyncReply, layout: HostLayout, state: SqliteLocalState
    ) -> tuple[AssetIdentity, ...]:
        """Verify everything, then write everything. The order is: the plan
        against the inventory, every manifest against its package, every file
        against what is on disk, and only then the files, the inventory row
        and the bundle."""
        added: tuple[AssetIdentity, ...] = ()
        if reply.plan is not None:
            artifacts = {item.artifact_ref: item.raw for item in reply.artifacts}
            files = self._verified(reply.plan, artifacts, layout, state)
            try:
                for path, content in files:
                    _write_atomically(path, content)
            except OSError:
                raise SyncRefused("workspace_unwritable") from None
            try:
                rows = state.install(reply.plan, artifacts)
            except LocalStateError as error:
                raise SyncRefused(error.code) from None
            added = tuple(item.identity for item in rows)
        try:
            _write_atomically(
                layout.authorization,
                reply.authorization.model_dump_json(indent=2).encode("utf-8") + b"\n",
            )
        except OSError:
            # The inventory is recorded and the files are there; only the
            # bundle is not. The outcome says both, so nothing is hidden.
            raise SyncRefused("workspace_unwritable", added) from None
        return added

    @staticmethod
    def _verified(
        plan: InstallationPlan,
        artifacts: Mapping[str, bytes],
        layout: HostLayout,
        state: SqliteLocalState,
    ) -> list[tuple[Path, bytes]]:
        try:
            present = {item.identity.key for item in state.installed()}
            verify_installation(plan, artifacts, bridge_id=state.bridge_id, installed=present)
        except LocalStateError as error:
            raise SyncRefused(error.code) from None
        on_disk = {
            "workflow": _identities_on_disk(layout.workflows),
            "skill": _identities_on_disk(layout.skills),
        }
        files: list[tuple[Path, bytes]] = []
        for package in plan.packages:
            artifact = package.metadata.package
            if artifact is None or package.kind not in on_disk:
                # This host installs Skill and Workflow manifests and nothing
                # else; a package of another kind has nowhere to go here.
                raise SyncRefused("asset_invalid")
            content = artifacts[artifact.artifact_ref]
            identity = package.metadata.identity
            try:
                manifest: SkillManifest | WorkflowManifest = (
                    WorkflowManifest.model_validate_json(content)
                    if package.kind == "workflow"
                    else SkillManifest.model_validate_json(content)
                )
            except ValidationError:
                raise SyncRefused("asset_invalid") from None
            if manifest.metadata.identity != identity:
                # Bytes that describe another asset than the package claims
                # would install under a name nobody chose.
                raise SyncRefused("asset_invalid")
            directory = layout.workflows if package.kind == "workflow" else layout.skills
            path = directory / f"{identity.namespace}__{identity.name}__{identity.version}.json"
            existing = on_disk[package.kind].get(identity.key)
            if existing is not None:
                if existing[0] != path or existing[1] != content:
                    raise SyncRefused("asset_conflict")
                # The same bytes are already where they would go: a sync that
                # was interrupted after writing them is finished, not refused.
                continue
            files.append((path, content))
        return files

    async def report(self, snapshot: BridgeStateSnapshot) -> ReportOutcome:
        answer = await asyncio.to_thread(self._call, "report", ReportRequest(snapshot=snapshot))
        if answer.status != "answered":
            return ReportOutcome(status=answer.status, failure=answer.failure)
        try:
            reply = ReportReply.model_validate(answer.data)
        except ValidationError:
            return ReportOutcome(status="unreachable", failure=_bad_reply())
        return ReportOutcome(status="answered", received_at=reply.received_at)

    async def poll_jobs(self, agent: LocalAgent, *, limit: int = 10) -> JobsOutcome:
        """Fetch the jobs waiting for this device, run each through the
        Agent, settle each with the platform, then report the Bridge's state.
        A settle that could not be delivered leaves the job open there; the
        outcome says so, and the next poll joins the run already started."""
        answer = await asyncio.to_thread(self._call, "poll", PollRequest(limit=limit))
        if answer.status != "answered":
            return JobsOutcome(status=answer.status, failure=answer.failure)
        try:
            reply = PollReply.model_validate(answer.data)
        except ValidationError:
            return JobsOutcome(status="unreachable", failure=_bad_reply())
        deliveries: list[JobDelivery] = []
        for record in reply.jobs:
            delivery, ended = await self._one(agent, record)
            deliveries.append(delivery)
            if ended is not None:
                # The platform has just said this Bridge is no longer its
                # member, or does not know its token: the rest of the batch
                # is not run on its behalf.
                return JobsOutcome(
                    status=ended.status, failure=ended.failure, deliveries=tuple(deliveries)
                )
        reported = False
        if deliveries or self._report_due():
            snapshot = await asyncio.to_thread(agent.snapshot, observed_at=datetime.now(UTC))
            reported = (await self.report(snapshot)).status == "answered"
            if reported:
                self._reported_at = monotonic()
        return JobsOutcome(status="answered", deliveries=tuple(deliveries), reported=reported)

    def _report_due(self) -> bool:
        """An idle Bridge still lets the platform see it is alive, but not
        on every poll: the snapshot carries every run ever recorded."""
        return self._reported_at is None or monotonic() - self._reported_at >= REPORT_EVERY_SECONDS

    async def _one(
        self, agent: LocalAgent, record: RemoteJobRecord
    ) -> tuple[JobDelivery, _Answer | None]:
        """Run one job and settle it. What ends a loop is the platform
        saying this Bridge is no longer its member; a settle it declined for
        that one job is recorded on the delivery, and the next poll simply
        does not offer that job again."""
        outcome: LocalAgentOutcome | None = None
        run: LocalRunSummary | None = None
        request = record.request
        engine = agent.gateway.engine
        started = engine.submitted(request.actor, request.workflow.namespace, request.job_id)
        disposition: JobDisposition
        if record.status == "cancel_requested":
            if started is None:
                disposition = "cancelled"
            else:
                # A settle that was lost, then a cancel: this Bridge already
                # ran it, and the idempotency key knows. The truth is what
                # happened, not what was asked for afterwards.
                final = await engine.wait(started.run.run_id)
                disposition = "ran"
                run = _summary(request, final if final is not None else started)
        else:
            outcome = await agent.execute(
                request, workflow_timeout_seconds=self._workflow_timeout_seconds
            )
            if outcome.refusal is not None or outcome.workflow is None:
                disposition = "rejected"
            elif outcome.run is None and outcome.unrecorded is None:
                # The engine answered before starting anything.
                disposition = "rejected"
            else:
                snapshot = outcome.workflow
                failure = snapshot.run.failure
                if failure is not None and failure.code == "workflow_timeout":
                    # The run outlived the wait and is still going. A settle
                    # is final, so it waits for the run to actually end.
                    ended = await engine.wait(snapshot.run.run_id)
                    await agent.settled()
                    snapshot = ended if ended is not None else snapshot
                disposition = "ran"
                # The local record when it exists and is final; otherwise the
                # engine's own result, which is the truth either way.
                run = _summary(request, snapshot)
        settle = SettleRequest(job_id=request.job_id, disposition=disposition, run=run)
        answer = await asyncio.to_thread(self._call, "settle", settle)
        delivery = JobDelivery(
            job_id=request.job_id,
            disposition=disposition,
            settled=answer.status == "answered",
            outcome=outcome,
            failure=answer.failure,
        )
        return delivery, (answer if answer.status in ENDS_LOOP else None)

    async def run_jobs(
        self, agent: LocalAgent, stop: asyncio.Event, *, interval_s: float = 5.0
    ) -> Failure | None:
        """Poll until asked to stop. A failure that will not fix itself ends
        the loop and is returned; a retryable one is waited out with a
        doubling delay. Nothing is deleted or rewritten on the way out: a
        Bridge the platform no longer knows keeps doing local work."""
        delay = interval_s
        while not stop.is_set():
            result = await self.poll_jobs(agent)
            if result.status in FINAL:
                return result.failure
            if result.status == "answered":
                delay = interval_s
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
            if result.status != "answered":
                delay = min(delay * 2, MAX_BACKOFF_SECONDS)
        return None


def _summary(request: RemoteWorkflowJob, snapshot: WorkflowRunSnapshot) -> LocalRunSummary:
    return LocalRunSummary(
        run_id=snapshot.run.run_id,
        actor=request.actor,
        on_behalf_of=request.on_behalf_of,
        workflow=snapshot.run.workflow,
        status=snapshot.run.status,
        updated_at=datetime.now(UTC),
    )


def _bad_reply() -> Failure:
    return Failure(
        code="platform_bad_reply",
        message="the platform's reply was not the operation's answer",
        retryable=True,
    )


def _refusal(code: str) -> Failure:
    return Failure(code=f"sync_{code}", message=f"this Bridge did not apply the reply: {code}")


def advertisement(agent: LocalAgent, trace_id: str) -> BridgeRegistration:
    """What this host can run, as the platform records it: the capabilities
    its Bridge policy could ever dispatch. What is installed travels in the
    snapshot; what is authorized comes back in the bundle."""
    return BridgeRegistration(
        bridge_id=agent.membership.device.bridge_id,
        owner_id=agent.membership.device.registered_by,
        trace=TraceIdentifiers(trace_id=trace_id, request_id=trace_id, span_id="advertise"),
        capabilities=agent.gateway.bridge.installed.discover(),
    )
