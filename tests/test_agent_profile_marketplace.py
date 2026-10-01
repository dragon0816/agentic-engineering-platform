"""Productization 2 slice 4: inert Agent profiles are installed then activated locally."""

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch
from test_host_models import binding, endpoint
from test_host_wiring import BRIDGE
from test_member_portal import post, signed_in
from test_platform_transport import NOW, READ, SECRET, SKILL, Platform, host, package, trace

from agent.contracts import AgentProfile
from common.assets import AssetIdentity
from common.authorization import DeviceAssetSelection
from common.local_agent import LocalAgentRequest
from control_plane.http import ControlPlaneServer
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from host_runtime.contracts import ModelBinding
from host_runtime.host import build_runtime
from host_runtime.profiles import ProfileError, activate_profile
from host_runtime.web import AgentWeb, AgentWebServer
from models.credentials import StaticCredentials

PROFILE = AssetIdentity(namespace="engineering", name="personal-engineer", version="1.0.0")


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def profile(**changes: Any) -> AgentProfile:
    values: dict[str, Any] = {
        "metadata": {
            "identity": PROFILE.model_dump(),
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "organization",
            "lifecycle": "published",
        },
        "description": "Engineering profile using the exact installed file Skill.",
        "skills": [SKILL.model_dump()],
        "allowed_capabilities": [READ.model_dump()],
        "model_requirements": {"reasoning": "medium", "min_context_tokens": 1},
    }
    values.update(changes)
    return AgentProfile.model_validate(values)


def publish_profile(platform: Platform, item: AgentProfile) -> bytes:
    content = item.model_dump_json().encode()
    published = platform.packages.publish(package(PROFILE, "agent", content))
    assert published.metadata.package is not None
    platform.artifacts[published.metadata.package.artifact_ref] = content
    return content


def configured(config: Any) -> Any:
    return config.model_copy(
        update={
            "models": ModelBinding.model_validate(
                binding(
                    catalog={
                        "endpoints": [endpoint(credential=None, model="fixture-model")],
                        "routes": [{"name": "default", "alias": "company"}],
                    }
                )
            )
        }
    )


def test_member_installs_and_locally_activates_exact_agent_profile(tmp_path: Path) -> None:
    platform = Platform()
    publish_profile(platform, profile())
    sessions = InMemoryMemberSessions()
    member_service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )
    session = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )
    grants_before = platform.authorization.grants(BRIDGE)

    with (
        ControlPlaneServer(platform.service) as control,
        MemberPortalServer(member_service) as member,
    ):
        status, catalog = post(
            member.base_url + "/v1/member/catalog", session.bearer, {"bridge_id": BRIDGE}
        )
        listed = next(item for item in catalog["entries"] if item["package"]["kind"] == "agent")
        assert status == 200 and listed["selected"] is False
        status, selected = post(
            member.base_url + "/v1/member/select",
            session.bearer,
            {"bridge_id": BRIDGE, "asset": PROFILE.model_dump()},
        )
        assert status == 200 and selected["selection"]["kind"] == "agent"
        assert platform.authorization.grants(BRIDGE) == grants_before

        base_config, layout, runtime = host(tmp_path, platform, control.base_url)
        config = configured(base_config)
        runtime.close()
        with build_runtime(
            config,
            layout=layout,
            resolver=StaticCredentials({"platform_token": SECRET}),
        ) as running:
            synchronized = run(running.platform.synchronize(layout, running.state))  # type: ignore[union-attr]
            assert synchronized.status == "answered"
            web = AgentWebServer(AgentWeb(running))
            thread = threading.Thread(target=web.serve_forever, daemon=True)
            thread.start()
            try:
                result = fetch(
                    base(web) + "/api/profiles/activate",
                    token=web.token,
                    body={"profile": PROFILE.model_dump()},
                ).json()
                assets = fetch(base(web) + "/api/assets", token=web.token).json()
            finally:
                web.shutdown()
                web.server_close()
                thread.join(timeout=5)
        assert result["ok"] is True and result["restart_required"] is True
        assert assets["profiles"][0]["active"] is True
        assert platform.authorization.grants(BRIDGE) == grants_before

    assert (layout.agents / "engineering__personal-engineer__1.0.0.json").is_file()
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
                    trace=trace("active-profile"),
                )
            )
        )
    assert outcome.refusal is None
    assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"


def test_profile_activation_refuses_unselected_dependencies_and_delegation(tmp_path: Path) -> None:
    platform = Platform()
    item = profile(skills=[{"namespace": "engineering", "name": "missing", "version": "1.0.0"}])
    publish_profile(platform, item)
    config, layout, runtime = host(tmp_path, platform, "http://127.0.0.1:1")
    runtime.close()
    config = configured(config)
    layout.agents.mkdir(parents=True, exist_ok=True)
    (layout.agents / "engineering__personal-engineer__1.0.0.json").write_text(
        item.model_dump_json(), encoding="utf-8"
    )
    authorization = platform.authorization.authorization(BRIDGE, issued_at=NOW)
    with pytest.raises(ProfileError, match="profile_not_selected"):
        activate_profile(config, layout, authorization, PROFILE, actor="engineer", now=NOW)

    delegated = profile(
        may_delegate_to=[{"namespace": "team", "name": "expert", "version": "1.0.0"}]
    )
    (layout.agents / "engineering__personal-engineer__1.0.0.json").write_text(
        delegated.model_dump_json(), encoding="utf-8"
    )
    selected = authorization.model_copy(
        update={
            "selections": (
                *authorization.selections,
                DeviceAssetSelection(
                    bridge_id=BRIDGE,
                    actor="engineer",
                    kind="agent",
                    asset=PROFILE,
                    decided_at=NOW,
                ),
            )
        }
    )
    with pytest.raises(ProfileError, match="profile_delegation_unsupported"):
        activate_profile(config, layout, selected, PROFILE, actor="engineer", now=NOW)
