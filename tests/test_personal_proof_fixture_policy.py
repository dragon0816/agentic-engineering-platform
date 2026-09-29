import asyncio
from pathlib import Path

from capabilities.company_agent.manifest import personal_proof_fixture_read_spec
from capabilities.files import ReadFileHandler, ReadFileInput, ReadFileOutput
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import ExecutionDependencies
from common.execution import RequestContext, TraceIdentifiers
from workflow.dispatch import BridgeExecutor


def _context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(
            trace_id="proof-trace", request_id="proof-request", span_id="proof-span"
        ),
        actor="leo.chi",
        namespace="company-agent",
        channel="test",
        message="personal.proof",
    )


def _grant() -> CapabilityGrant:
    spec = personal_proof_fixture_read_spec()
    return CapabilityGrant(
        actor="leo.chi",
        asset=spec.identity,
        permissions=spec.policy.required_permissions,
        policy_refs=spec.policy.policy_refs,
        approval_ref="aep-personal-proof-fixture-v1",
    )


def _bridge(root: Path, grant: CapabilityGrant | None) -> BridgeExecutor:
    spec = personal_proof_fixture_read_spec()
    installed = InstalledCapabilities()
    installed.register(
        spec,
        ReadFileHandler(root),
        ReadFileInput,
        ReadFileOutput,
        ExecutionDependencies(central_required=False),
    )
    grants = () if grant is None else (grant,)
    return BridgeExecutor(installed, LocalPolicy(grants))


def _call(path: Path) -> CapabilityInvocation:
    return CapabilityInvocation(
        context=_context(),
        target=personal_proof_fixture_read_spec().identity,
        arguments={"path": str(path)},
    )


def test_fixture_grant_reads_only_the_fixture_root(tmp_path: Path) -> None:
    fixture = tmp_path / "hermes-fixtures" / "personal-proof"
    fixture.mkdir(parents=True)
    allowed = fixture / "proof.txt"
    allowed.write_text("proof", encoding="utf-8")
    sibling = tmp_path / "hermes-fixtures" / "other.txt"
    sibling.write_text("not proof", encoding="utf-8")
    bridge = _bridge(fixture, _grant())

    passed = asyncio.run(bridge.execute(_call(allowed)))
    refused = asyncio.run(bridge.execute(_call(sibling)))

    assert passed.status == "succeeded"
    assert isinstance(refused.data, dict) and refused.data["outcome"] == "outside_root"


def test_general_filesystem_grant_does_not_authorize_the_fixture_capability(tmp_path: Path) -> None:
    fixture = tmp_path / "hermes-fixtures" / "personal-proof"
    fixture.mkdir(parents=True)
    path = fixture / "proof.txt"
    path.write_text("proof", encoding="utf-8")
    broad = _grant().model_copy(
        update={"asset": {"namespace": "filesystem", "name": "read-file", "version": "1.0.0"}}
    )

    result = asyncio.run(_bridge(fixture, broad).execute(_call(path)))

    assert result.failure is not None and result.failure.code == "permission_denied"


def test_fixture_capability_stays_default_deny(tmp_path: Path) -> None:
    fixture = tmp_path / "hermes-fixtures" / "personal-proof"
    fixture.mkdir(parents=True)
    path = fixture / "proof.txt"
    path.write_text("proof", encoding="utf-8")

    result = asyncio.run(_bridge(fixture, None).execute(_call(path)))

    assert result.failure is not None and result.failure.code == "permission_denied"
