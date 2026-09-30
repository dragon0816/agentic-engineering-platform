"""Productization 2 slice 3: selected Knowledge becomes a grounded local answer."""

import asyncio
import hashlib
import threading
from pathlib import Path
from typing import Any

from test_agent_web import KnowledgeGateway, base, fetch
from test_host_models import binding, endpoint
from test_host_wiring import BRIDGE
from test_member_portal import post, signed_in
from test_platform_transport import NOW, SECRET, Platform, host
from test_product_e2e_05 import V1, copy_vault, manifest

from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from common.assets import Owner, PackageMetadata
from common.authorization import DeviceAssetSelection
from common.distribution import InstallationPlan, PublishedAssetPackage
from control_plane.http import ControlPlaneServer
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from host_runtime.contracts import HostLayout, ModelBinding
from host_runtime.host import build_runtime
from host_runtime.sync import PlatformClient, SyncRefused
from host_runtime.web import AgentWeb, AgentWebServer
from knowledge.package import package_knowledge
from models.credentials import StaticCredentials


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def publish_knowledge(platform: Platform, tmp_path: Path) -> bytes:
    vault = copy_vault(tmp_path)
    published = manifest(vault)
    published = published.model_copy(
        update={
            "metadata": published.metadata.model_copy(
                update={"owner": Owner(type="team", id="engineering")}
            )
        }
    )
    portable = package_knowledge(published, vault)
    content = portable.model_dump_json().encode()
    artifact_ref = "registry://engineering/widget-guide/1.0.0"
    package = PublishedAssetPackage(
        kind="knowledge",
        metadata=portable.manifest.metadata.model_copy(
            update={
                "package": PackageMetadata(
                    artifact_ref=artifact_ref,
                    sha256=hashlib.sha256(content).hexdigest(),
                )
            }
        ),
        description="Grounded engineering guide",
    )
    platform.packages.publish(package)
    platform.artifacts[artifact_ref] = content
    return content


def authorize_knowledge_query(platform: Platform) -> None:
    advertisement = platform.enrollment.advertisement(BRIDGE)
    platform.enrollment.advertise(
        BRIDGE,
        advertisement.model_copy(
            update={"capabilities": (*advertisement.capabilities, KNOWLEDGE_QUERY_SPEC)}
        ),
    )
    platform.authorization.select(
        signed_in(),
        DeviceAssetSelection(
            bridge_id=BRIDGE,
            actor="engineer",
            kind="capability",
            asset=KNOWLEDGE_QUERY_SPEC.identity,
            approval_ref="knowledge-query-approval",
            approved_by="engineer",
            decided_at=NOW,
        ),
        now=NOW,
    )


def test_member_selects_syncs_and_asks_exact_knowledge_from_personal_web(
    tmp_path: Path,
) -> None:
    platform = Platform()
    publish_knowledge(platform, tmp_path / "publisher")
    authorize_knowledge_query(platform)
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
    grants_before_selection = platform.authorization.grants(BRIDGE)

    with (
        ControlPlaneServer(platform.service) as control,
        MemberPortalServer(member_service) as member,
    ):
        status, catalog = post(
            member.base_url + "/v1/member/catalog", session.bearer, {"bridge_id": BRIDGE}
        )
        item = next(
            entry for entry in catalog["entries"] if entry["package"]["kind"] == "knowledge"
        )
        assert status == 200 and item["selected"] is False
        status, selected = post(
            member.base_url + "/v1/member/select",
            session.bearer,
            {"bridge_id": BRIDGE, "asset": V1.model_dump(mode="json")},
        )
        assert status == 200 and selected["selection"]["kind"] == "knowledge"
        assert platform.authorization.grants(BRIDGE) == grants_before_selection

        config, layout, runtime = host(tmp_path / "host", platform, control.base_url)
        with runtime:
            synchronized = run(runtime.platform.synchronize(layout, runtime.state))  # type: ignore[union-attr]
            assert synchronized.status == "answered", synchronized
            assert V1 in synchronized.installed

    vault_root = layout.knowledge_vaults / "engineering" / "widget-guide" / "1.0.0"
    assert vault_root.is_dir()
    assert (layout.knowledge / "engineering__widget-guide__1.0.0.json").is_file()
    configured = config.model_copy(
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
    with build_runtime(
        configured,
        layout=layout,
        resolver=StaticCredentials({"platform_token": SECRET}),
        model_transport=KnowledgeGateway(),
    ) as rebuilt:
        web = AgentWebServer(AgentWeb(rebuilt))
        thread = threading.Thread(target=web.serve_forever, daemon=True)
        thread.start()
        try:
            assets = fetch(base(web) + "/api/assets", token=web.token).json()
            assert [item["name"] for item in assets["knowledge"]] == ["widget-guide"]
            assert "vault_root" not in str(assets)
            answered = fetch(
                base(web) + "/api/knowledge/ask",
                token=web.token,
                body={
                    "asset": V1.model_dump(mode="json"),
                    "question": "What firmware does Safe mode require?",
                },
            ).json()
        finally:
            web.shutdown()
            web.server_close()
            thread.join(timeout=5)
    assert answered["ok"] is True, answered["outcome"]["capability"]
    assert answered["answer"] == "Safe mode requires firmware 2.0 [1]."
    assert answered["record"]["asset"] == V1.model_dump(mode="json")
    assert answered["record"]["cited_passages"]


def test_knowledge_package_metadata_must_match_the_portable_manifest(tmp_path: Path) -> None:
    platform = Platform()
    content = publish_knowledge(platform, tmp_path)
    package = platform.packages.get(V1)
    assert package is not None and package.metadata.package is not None
    artifact_ref = package.metadata.package.artifact_ref
    platform.artifacts[artifact_ref] = content
    incompatible = package.model_copy(
        update={"metadata": package.metadata.model_copy(update={"visibility": "public"})}
    )
    platform.packages = type(platform.packages)()
    platform.packages.publish(incompatible)

    # The Bridge refuses outer Registry governance that does not describe the
    # manifest inside the artifact, even though identity and SHA still match.
    layout = HostLayout.under(tmp_path / "host")
    try:
        PlatformClient._verified(
            InstallationPlan(actor="engineer", bridge_id=BRIDGE, packages=(incompatible,)),
            {artifact_ref: content},
            layout,
            BRIDGE,
            set(),
        )
    except SyncRefused as error:
        assert error.code == "asset_invalid"
    else:
        raise AssertionError("mismatched Knowledge governance was accepted")
