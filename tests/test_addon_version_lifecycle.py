"""Productization 2 slice 5: exact-version update and rollback keep prior bytes usable."""

import asyncio
import json
from pathlib import Path
from typing import Any

from test_host_wiring import BRIDGE, skill_manifest
from test_member_portal import post, signed_in
from test_platform_transport import NOW, SECRET, SKILL, Platform, host, package, trace

from common.assets import AssetIdentity
from common.local_agent import LocalAgentRequest
from control_plane.http import ControlPlaneServer
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from host_runtime.host import build_runtime
from models.credentials import StaticCredentials

SKILL_V2 = AssetIdentity(namespace="engineering", name="file-skill", version="2.0.0")


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def publish_v2(platform: Platform) -> None:
    manifest = skill_manifest()
    manifest["metadata"]["identity"] = SKILL_V2.model_dump()
    manifest["instructions"] = "Version two of the governed local file procedure."
    content = json.dumps(manifest).encode()
    published = platform.packages.publish(package(SKILL_V2, "skill", content))
    assert published.metadata.package is not None
    platform.artifacts[published.metadata.package.artifact_ref] = content


def service(platform: Platform, sessions: InMemoryMemberSessions) -> MemberService:
    return MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )


def execute(config: Any, layout: Any, suffix: str) -> None:
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"platform_token": SECRET}),
    ) as runtime:
        outcome = run(
            runtime.agent.handle(
                LocalAgentRequest(
                    ingress="local",
                    actor="engineer",
                    bridge_id=BRIDGE,
                    namespace="engineering",
                    message="files.read notes.txt",
                    trace=trace(suffix),
                )
            )
        )
    assert outcome.refusal is None
    assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"


def test_exact_skill_update_and_rollback_reuse_the_retained_prior_version(tmp_path: Path) -> None:
    platform = Platform()
    publish_v2(platform)
    sessions = InMemoryMemberSessions()
    member_session = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )
    grants_before = platform.authorization.grants(BRIDGE)

    with (
        ControlPlaneServer(platform.service) as control,
        MemberPortalServer(service(platform, sessions)) as member,
    ):
        config, layout, runtime = host(tmp_path, platform, control.base_url)
        with runtime:
            first = run(runtime.platform.synchronize(layout, runtime.state))  # type: ignore[union-attr]
        assert first.status == "answered" and SKILL in first.installed

        status, upgraded = post(
            member.base_url + "/v1/member/replace",
            member_session.bearer,
            {
                "bridge_id": BRIDGE,
                "current": SKILL.model_dump(),
                "replacement": SKILL_V2.model_dump(),
            },
        )
        assert status == 200
        assert upgraded["previous"]["status"] == "revoked"
        assert upgraded["selection"]["asset"] == SKILL_V2.model_dump()
        with build_runtime(
            config,
            layout=layout,
            resolver=StaticCredentials({"platform_token": SECRET}),
        ) as upgrading:
            second = run(upgrading.platform.synchronize(layout, upgrading.state))  # type: ignore[union-attr]
        assert second.status == "answered" and second.installed == (SKILL_V2,)
        execute(config, layout, "skill-v2")

        status, rolled_back = post(
            member.base_url + "/v1/member/replace",
            member_session.bearer,
            {
                "bridge_id": BRIDGE,
                "current": SKILL_V2.model_dump(),
                "replacement": SKILL.model_dump(),
            },
        )
        assert status == 200 and rolled_back["selection"]["asset"] == SKILL.model_dump()
        with build_runtime(
            config,
            layout=layout,
            resolver=StaticCredentials({"platform_token": SECRET}),
        ) as rolling_back:
            third = run(rolling_back.platform.synchronize(layout, rolling_back.state))  # type: ignore[union-attr]
        assert third.status == "answered" and third.installed == ()

    assert (layout.skills / "engineering__file-skill__1.0.0.json").is_file()
    assert (layout.skills / "engineering__file-skill__2.0.0.json").is_file()
    authorization = json.loads(layout.authorization.read_text(encoding="utf-8"))
    selected_skills = [
        item["asset"] for item in authorization["selections"] if item["kind"] == "skill"
    ]
    assert selected_skills == [SKILL.model_dump()]
    assert platform.authorization.grants(BRIDGE) == grants_before
    execute(config, layout, "skill-v1-rollback")


def test_failed_replacement_is_atomic_and_member_cannot_change_family(tmp_path: Path) -> None:
    platform = Platform()
    publish_v2(platform)
    sessions = InMemoryMemberSessions()
    member_session = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )
    with MemberPortalServer(service(platform, sessions)) as member:
        missing = AssetIdentity(namespace="engineering", name="file-skill", version="9.0.0")
        status, failure = post(
            member.base_url + "/v1/member/replace",
            member_session.bearer,
            {
                "bridge_id": BRIDGE,
                "current": SKILL.model_dump(),
                "replacement": missing.model_dump(),
            },
        )
        assert status == 404 and failure == {"code": "asset_not_published"}
        status, failure = post(
            member.base_url + "/v1/member/replace",
            member_session.bearer,
            {
                "bridge_id": BRIDGE,
                "current": SKILL.model_dump(),
                "replacement": {
                    "namespace": "engineering",
                    "name": "another-skill",
                    "version": "2.0.0",
                },
            },
        )
        assert status == 400 and failure == {"code": "invalid_request"}
    active = platform.authorization.authorization(BRIDGE, issued_at=NOW).selections
    assert any(item.asset == SKILL and item.status == "active" for item in active)
    assert not any(item.asset == SKILL_V2 and item.status == "active" for item in active)
