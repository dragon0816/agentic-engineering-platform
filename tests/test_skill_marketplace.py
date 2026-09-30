"""Productization 2 slice 1: member-selected Skill becomes Agent behavior."""

import asyncio
import threading
from pathlib import Path
from typing import Any

from test_host_wiring import BRIDGE
from test_member_portal import post, signed_in
from test_platform_transport import NOW, SECRET, SKILL, WORKFLOW, Platform, host, package, trace

from common.assets import AssetIdentity
from common.local_agent import LocalAgentRequest
from control_plane.http import ControlPlaneServer
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from models.credentials import StaticCredentials


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def test_member_selects_skill_syncs_it_and_rebuilt_agent_uses_it(tmp_path: Path) -> None:
    platform = Platform()
    platform.authorization.revoke(signed_in(), BRIDGE, SKILL, now=NOW)
    sessions = InMemoryMemberSessions()
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )
    session = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )
    grants_before = platform.authorization.grants(BRIDGE)

    with ControlPlaneServer(platform.service) as control, MemberPortalServer(service) as member:
        status, catalog = post(
            member.base_url + "/v1/member/catalog",
            session.bearer,
            {"bridge_id": BRIDGE},
        )
        skill = next(item for item in catalog["entries"] if item["package"]["kind"] == "skill")
        assert status == 200 and skill["selected"] is False

        # Kind is trusted Registry state, not a field the member may claim.
        status, failure = post(
            member.base_url + "/v1/member/select",
            session.bearer,
            {"bridge_id": BRIDGE, "asset": SKILL.model_dump(), "kind": "workflow"},
        )
        assert status == 400 and failure == {"code": "invalid_request"}
        status, selected = post(
            member.base_url + "/v1/member/select",
            session.bearer,
            {"bridge_id": BRIDGE, "asset": SKILL.model_dump()},
        )
        assert status == 200 and selected["selection"]["kind"] == "skill"
        assert platform.authorization.grants(BRIDGE) == grants_before

        config, layout, runtime = host(tmp_path, platform, control.base_url)
        with runtime:
            web = AgentWebServer(AgentWeb(runtime))
            thread = threading.Thread(target=web.serve_forever, daemon=True)
            thread.start()
            try:
                port = web.server_address[1]
                status, synchronized = post(
                    f"http://127.0.0.1:{port}/api/platform/sync",
                    web.token,
                    {},
                )
            finally:
                web.shutdown()
                web.server_close()
                thread.join(timeout=5)
            assert status == 200 and synchronized["status"] == "answered"
            assert {
                (item["namespace"], item["name"], item["version"])
                for item in synchronized["installed"]
            } == {WORKFLOW.key, SKILL.key}

    assert (layout.skills / "engineering__file-skill__1.0.0.json").is_file()
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"platform_token": SECRET}),
    ) as rebuilt:
        outcome = run(
            rebuilt.agent.handle(
                LocalAgentRequest(
                    ingress="local",
                    actor="engineer",
                    bridge_id=BRIDGE,
                    namespace="engineering",
                    message="files.read notes.txt",
                    trace=trace("skill-marketplace"),
                )
            )
        )
        assert outcome.refusal is None
        assert outcome.workflow is not None
        assert outcome.workflow.run.status == "succeeded"


def test_non_installable_kind_cannot_enter_member_add_on_selection() -> None:
    platform = Platform()
    profile = AssetIdentity(namespace="engineering", name="personal", version="1.0.0")
    content = b"{}"
    published = platform.packages.publish(package(profile, "agent", content))
    assert published.metadata.package is not None
    platform.artifacts[published.metadata.package.artifact_ref] = content
    sessions = InMemoryMemberSessions()
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )
    session = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )

    with MemberPortalServer(service) as member:
        status, catalog = post(
            member.base_url + "/v1/member/catalog",
            session.bearer,
            {"bridge_id": BRIDGE},
        )
        assert status == 200
        assert profile.model_dump() not in [
            item["package"]["metadata"]["identity"] for item in catalog["entries"]
        ]
        status, failure = post(
            member.base_url + "/v1/member/select",
            session.bearer,
            {"bridge_id": BRIDGE, "asset": profile.model_dump()},
        )
    assert status == 409 and failure == {"code": "kind_mismatch"}
