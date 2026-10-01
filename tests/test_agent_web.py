"""The web interface, over a real socket.

Nothing here stubs the server. It is started, spoken to over TCP the way a
browser speaks to it, and stopped -- because the things worth pinning are the
guards, and a guard tested through a function call is a guard that was never
asked the question an attacker asks.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from test_extension_package import DeterministicVerifier, package, trust
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import grant_record, host_json, membership_record, ready, workspace
from test_platform_transport import Platform, host
from test_product_e2e_05 import V1, copy_vault, manifest

from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from control_plane.http import ControlPlaneServer
from extensions.package import stage_extension_package
from extensions.runtime import ExtensionActivationRecord, ExtensionLifecycleStore
from host_runtime.contracts import CompanyHostConfiguration, KnowledgeAskRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer


class Reply:
    def __init__(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.status = status
        self.body = body
        self.headers = headers

    def json(self) -> Any:
        return json.loads(self.body)


class KnowledgeGateway:
    """One grounded model answer over the deterministic fixture retrieval."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        self.calls.append({"url": url, "payload": json.loads(body)})
        return GatewayReply(
            200,
            {
                "id": "chatcmpl-knowledge-web",
                "model": "fixture-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "Safe mode requires firmware 2.0 [1].",
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            },
        )


def knowledge_runtime(tmp_path: Path, *, authorized: bool = True) -> Any:
    vault = copy_vault(tmp_path)
    grants = grant_record()
    if authorized:
        grants.append(
            {
                "actor": "engineer",
                "asset": KNOWLEDGE_QUERY_SPEC.identity.model_dump(mode="json"),
                "permissions": list(KNOWLEDGE_QUERY_SPEC.policy.required_permissions),
                "policy_refs": list(KNOWLEDGE_QUERY_SPEC.policy.policy_refs),
            }
        )
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=grants,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, model="fixture-model")],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            ),
            "knowledge": [{"asset": V1.model_dump(mode="json"), "vault_root": str(vault.root)}],
        },
    )
    layout.knowledge.mkdir(parents=True, exist_ok=True)
    (layout.knowledge / "widget-guide.json").write_text(
        manifest(vault).model_dump_json(), encoding="utf-8"
    )
    return build_runtime(config, layout=layout, model_transport=KnowledgeGateway())


def fetch(
    url: str, *, token: str | None = None, body: Any = None, host: str | None = None
) -> Reply:
    request = urllib.request.Request(url, method="POST" if body is not None else "GET")
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    if host is not None:
        request.add_header("Host", host)
    if body is not None:
        request.add_header("Content-Type", "application/json")
        request.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return Reply(answer.status, answer.read(), dict(answer.headers))
    except urllib.error.HTTPError as refused:
        return Reply(refused.code, refused.read(), dict(refused.headers))


@pytest.fixture
def served(tmp_path: Path) -> Iterator[AgentWebServer]:
    config, _layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@pytest.fixture
def served_knowledge(tmp_path: Path) -> Iterator[AgentWebServer]:
    with knowledge_runtime(tmp_path) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def base(server: AgentWebServer) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}"


def test_it_listens_on_the_loopback_address_only(served: AgentWebServer) -> None:
    """Not a setting. Nothing on the network can reach a machine's Agent."""
    assert served.server_address[0] == "127.0.0.1"
    assert "127.0.0.1" in served.address


def test_the_token_is_new_every_run_and_long(tmp_path: Path) -> None:
    """A token that outlived the process would be a standing key to this
    machine's Agent lying in somebody's shell history."""
    config, _layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        first = AgentWebServer(AgentWeb(runtime))
        second = AgentWebServer(AgentWeb(runtime))
        try:
            assert first.token != second.token
            assert len(first.token) >= 32
        finally:
            first.server_close()
            second.server_close()


def test_the_page_needs_the_token_in_the_address(served: AgentWebServer) -> None:
    """A browser cannot be asked to set a header on its first visit, so the
    page is let in by the address -- and only by the right one."""
    assert fetch(base(served) + "/").status == 401
    assert fetch(base(served) + "/?token=not-the-token").status == 401
    page = fetch(base(served) + f"/?token={served.token}")
    assert page.status == 200
    assert page.headers["Content-Type"].startswith("text/html")
    assert b"<!DOCTYPE html>" in page.body


def test_the_page_fetches_nothing_from_anywhere(served: AgentWebServer) -> None:
    """A company machine installs this behind a proxy that reaches no
    package index and no content delivery network. A page that went looking
    for one would render wrong exactly where it matters."""
    body = fetch(base(served) + f"/?token={served.token}").body.decode("utf-8")
    for outside in ("http://", "https://", "//cdn", "@import"):
        assert outside not in body, f"the page reaches for {outside}"


def test_every_api_call_needs_the_header(served: AgentWebServer) -> None:
    """The header is the whole cross-site defence: a page on another origin
    cannot set one without a preflight, and this server answers none."""
    for path in (
        "/api/about",
        "/api/readiness",
        "/api/settings",
        "/api/assets",
        "/api/platform",
    ):
        assert fetch(base(served) + path).status == 401
        assert fetch(base(served) + path, token="wrong").status == 401
        assert fetch(base(served) + path, token=served.token).status == 200
    assert fetch(base(served) + "/api/ask", body={"message": "x"}).status == 401
    assert fetch(base(served) + "/api/platform/sync", body={}).status == 401
    assert fetch(base(served) + "/api/platform/sync", token="wrong", body={}).status == 401
    assert fetch(base(served) + "/api/workflows/run", body={}).status == 401
    assert fetch(base(served) + "/api/knowledge/ask", body={}).status == 401
    assert fetch(base(served) + "/api/settings/model", body={}).status == 401


def test_the_token_in_the_address_does_not_open_the_api(served: AgentWebServer) -> None:
    """Otherwise any page that learned the address would drive the Agent."""
    assert fetch(base(served) + f"/api/assets?token={served.token}").status == 401


def test_a_name_that_resolves_here_is_still_refused(served: AgentWebServer) -> None:
    """DNS rebinding: a name an attacker controls can be made to resolve to
    127.0.0.1, and then their page is same-origin with this one."""
    refused = fetch(base(served) + "/api/about", token=served.token, host="agent.attacker.example")
    assert refused.status == 403
    assert "loopback" in refused.json()["error"]
    refused = fetch(
        base(served) + "/api/platform/sync",
        token=served.token,
        body={},
        host="agent.attacker.example",
    )
    assert refused.status == 403


def test_it_answers_no_cross_origin_header(served: AgentWebServer) -> None:
    reply = fetch(base(served) + "/api/about", token=served.token)
    assert not any(name.lower().startswith("access-control") for name in reply.headers)
    assert reply.headers["X-Frame-Options"] == "DENY"
    assert reply.headers["X-Content-Type-Options"] == "nosniff"


def test_it_says_who_and_where_it_is(served: AgentWebServer) -> None:
    about = fetch(base(served) + "/api/about", token=served.token).json()
    assert about["actor"] == "engineer"
    assert about["bridge_id"] == "bridge-company"
    assert about["namespace"] == "engineering"


def test_readiness_explains_why_natural_language_is_not_available(
    served: AgentWebServer,
) -> None:
    readiness = fetch(base(served) + "/api/readiness", token=served.token).json()
    assert readiness["natural_language"]["status"] == "setup_required"
    assert "model" in readiness["natural_language"]["action"].lower()
    assert readiness["installed"] == {
        "profiles": 0,
        "skills": 1,
        "workflows": 1,
        "knowledge": 0,
        "extensions": 0,
    }
    assert readiness["shared_platform"]["configured"] is False


def test_installed_skill_commands_include_a_clickable_manifest_derived_invocation(
    served: AgentWebServer,
) -> None:
    assets = fetch(base(served) + "/api/assets", token=served.token).json()
    command = assets["skills"][0]["commands"][0]
    assert command == {
        "name": "read",
        "kind": "workflow",
        "target": "engineering/read-local-file@1.0.0",
        "invocation": "files.read ",
    }


def test_model_settings_write_only_names_and_require_restart(tmp_path: Path) -> None:
    config, _layout = ready(tmp_path)
    config_path = host_json(tmp_path, config)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime, config_path=config_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            before = fetch(base(server) + "/api/settings", token=server.token).json()
            assert before["writable"] is True
            assert before["model"]["configured"] is False
            saved = fetch(
                base(server) + "/api/settings/model",
                token=server.token,
                body={
                    "alias": "company",
                    "provider": "openai_compatible",
                    "model": "company-model",
                    "base_url": "http://127.0.0.1:4000/v1",
                    "credential_secret": "llm_gateway_token",
                    "credential_environment": "AEP_LLM_TOKEN",
                },
            )
            assert saved.status == 200
            assert saved.json()["restart_required"] is True
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    written = CompanyHostConfiguration.model_validate_json(config_path.read_text(encoding="utf-8"))
    assert written.models is not None
    endpoint = written.models.catalog.endpoints[0]
    assert endpoint.base_url == "http://127.0.0.1:4000/v1"
    assert endpoint.model == "company-model"
    assert endpoint.credential is not None
    assert endpoint.credential.name == "llm_gateway_token"
    assert written.credential_environment()["llm_gateway_token"] == "AEP_LLM_TOKEN"
    assert "token" not in saved.json()


def test_model_settings_contract_refuses_secret_values_and_preserves_file(tmp_path: Path) -> None:
    config, _layout = ready(tmp_path)
    config_path = host_json(tmp_path, config)
    original = config_path.read_bytes()
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime, config_path=config_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            reply = fetch(
                base(server) + "/api/settings/model",
                token=server.token,
                body={
                    "alias": "company",
                    "provider": "openai_compatible",
                    "model": "company-model",
                    "base_url": "http://127.0.0.1:4000/v1",
                    "api_key": "must-not-be-accepted",
                },
            )
            assert reply.status == 400
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    assert config_path.read_bytes() == original


def test_page_exposes_setup_commands_and_capability_management(served: AgentWebServer) -> None:
    page = fetch(base(served) + f"/?token={served.token}").body.decode("utf-8")
    assert 'id="tab-settings"' in page
    assert 'id="command-hints"' in page
    assert 'id="model-base-url"' in page
    assert "127.0.0.1:4000/v1" in page
    assert "Bridge Extensions" in page


def test_it_lists_what_this_machine_has_without_naming_any_one_of_them(
    served: AgentWebServer,
) -> None:
    """Generic on purpose: the listing is built from the manifests, so a new
    asset appears the day it is installed and no page is written for it."""
    assets = fetch(base(served) + "/api/assets", token=served.token).json()
    aliases = [skill["alias"] for skill in assets["skills"]]
    assert "files" in aliases
    names = [workflow["name"] for workflow in assets["workflows"]]
    assert "read-local-file" in names
    assert all("steps" in workflow for workflow in assets["workflows"])
    assert all("input_contract" in workflow for workflow in assets["workflows"])
    assert assets["runs"] == [], "nothing has run yet"


def test_it_shows_staged_and_runtime_extension_state_without_an_activation_action(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    staged = stage_extension_package(
        package().model_dump_json().encode(),
        layout.extensions,
        trust(),
        DeterministicVerifier(),
    )
    ExtensionLifecycleStore(layout.extension_lifecycle).record(
        ExtensionActivationRecord(
            extension=staged.identity,
            state="unhealthy",
            code="extension_activation_failed",
        )
    )

    with build_runtime(config, layout=layout) as runtime:
        assets = AgentWeb(runtime).assets()
        page = AgentWebServer(AgentWeb(runtime))
        try:
            source = page.page().decode("utf-8")
        finally:
            page.server_close()

    assert assets["extensions"] == [
        {
            "namespace": "lab",
            "name": "fixture-extension",
            "version": "1.0.0",
            "description": "Fixture integration",
            "state": "unhealthy",
            "publisher_key_id": "lab-release-key",
            "capabilities": ["lab/read-fixture@1.0.0"],
            "approval_required": True,
            "activation_gate": (
                "Registered device owner or delegated device administrator approval required."
            ),
            "code": "extension_activation_failed",
        }
    ]
    assert 'id="extensions"' in source
    assert "/api/extensions/activate" not in source


def test_a_machine_with_no_shared_platform_says_so(served: AgentWebServer) -> None:
    """And does not show an empty table that reads as "nobody published
    anything"."""
    platform = fetch(base(served) + "/api/platform", token=served.token).json()
    assert platform["configured"] is False
    assert "No shared platform is configured" in platform["note"]
    assert platform["decisions"] == []

    synchronized = fetch(base(served) + "/api/platform/sync", token=served.token, body={}).json()
    assert synchronized["status"] == "refused"
    assert synchronized["failure"]["code"] == "platform_not_configured"
    assert synchronized["before"] == synchronized["after"] == platform


def test_shared_platform_catalog_distinguishes_publish_authorize_and_install(
    tmp_path: Path,
) -> None:
    """Browsing changes nothing. The existing selection plus sync path is
    what changes the two local facts shown beside the published package."""
    platform = Platform()
    with ControlPlaneServer(platform.service) as control:
        _config, layout, runtime = host(tmp_path, platform, control.base_url)
        with runtime:
            web = AgentWeb(runtime)
            server = AgentWebServer(web)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                before = fetch(base(server) + "/api/platform", token=server.token).json()
                workflow = next(row for row in before["catalog"] if row["kind"] == "workflow")
                assert workflow["published"] is True
                assert workflow["authorized"] is False
                assert workflow["installed"] is False
                assert workflow["owner"] == "team:engineering"
                assert runtime.state.installed() == ()

                synced = fetch(
                    base(server) + "/api/platform/sync", token=server.token, body={}
                ).json()
                assert synced["status"] == "answered"
                assert {item["name"] for item in synced["installed"]} == {
                    "read-local-file",
                    "file-skill",
                }
                assert synced["selections"] == 3
                assert synced["before"] == before
                after = synced["after"]
                workflow = next(row for row in after["catalog"] if row["kind"] == "workflow")
                assert workflow["authorized"] is True
                assert workflow["installed"] is True
                assert after == fetch(base(server) + "/api/platform", token=server.token).json()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


def test_shared_platform_view_links_to_the_separate_member_portal(tmp_path: Path) -> None:
    platform = Platform()
    with ControlPlaneServer(platform.service) as control:
        config, _layout, runtime = host(tmp_path, platform, control.base_url)
        assert config.platform is not None
        runtime.config = config.model_copy(
            update={
                "platform": config.platform.model_copy(
                    update={"member_portal_url": "https://platform.internal:8443"}
                )
            }
        )
        with runtime:
            web = AgentWeb(runtime)
            projection = web.platform()
            assert projection["member_portal_url"] == "https://platform.internal:8443"
            server = AgentWebServer(web)
            try:
                page = server.page().decode("utf-8")
            finally:
                server.server_close()
            assert "member-portal" in page
            assert "Open shared marketplace (Agent Add-ons and Applications)" in page


def test_sync_request_is_closed_and_discovery_never_triggers_it(tmp_path: Path) -> None:
    platform = Platform()
    with ControlPlaneServer(platform.service) as control:
        _config, layout, runtime = host(tmp_path, platform, control.base_url)
        with runtime:
            server = AgentWebServer(AgentWeb(runtime))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                assert fetch(base(server) + "/api/platform", token=server.token).status == 200
                assert runtime.state.installed() == ()
                assert not layout.authorization.exists()

                refused = fetch(
                    base(server) + "/api/platform/sync",
                    token=server.token,
                    body={"asset": "engineering/read-local-file@1.0.0"},
                )
                assert refused.status == 400
                assert "empty synchronization request" in refused.json()["error"]
                assert runtime.state.installed() == ()
                assert not layout.authorization.exists()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


def test_unreachable_sync_is_typed_and_leaves_local_state_untouched(tmp_path: Path) -> None:
    platform = Platform()
    control = ControlPlaneServer(platform.service)
    base_url = control.base_url
    control.stop()
    _config, layout, runtime = host(tmp_path, platform, base_url)
    with runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = fetch(base(server) + "/api/platform/sync", token=server.token, body={}).json()
            assert result["status"] == "unreachable"
            assert result["failure"]["retryable"] is True
            assert result["before"]["connection"] == "unreachable"
            assert result["after"]["connection"] == "unreachable"
            assert runtime.state.installed() == ()
            assert not layout.authorization.exists()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def test_local_sync_refusal_is_typed_and_leaves_local_state_untouched(tmp_path: Path) -> None:
    platform = Platform()
    with ControlPlaneServer(platform.service) as control:
        _config, layout, runtime = host(tmp_path, platform, control.base_url)
        layout.grants.write_text("[]", encoding="utf-8")
        with runtime:
            server = AgentWebServer(AgentWeb(runtime))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = fetch(
                    base(server) + "/api/platform/sync", token=server.token, body={}
                ).json()
                assert result["status"] == "refused"
                assert result["failure"]["code"] == "sync_grants_conflict"
                assert result["installed"] == []
                assert runtime.state.installed() == ()
                assert not layout.authorization.exists()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


def test_page_only_synchronizes_after_the_explicit_button_action(
    served: AgentWebServer,
) -> None:
    page = served.page().decode("utf-8")
    assert 'id="platform-sync"' in page
    assert 'call("/api/platform/sync", {})' in page
    assert 'addEventListener("click"' in page
    assert "install-package" not in page


def test_page_launches_exact_installed_workflows_and_shows_trace_identifiers(
    served: AgentWebServer,
) -> None:
    page = served.page().decode("utf-8")
    assert 'id="workflow-target"' in page
    assert 'id="workflow-arguments"' in page
    assert 'call("/api/workflows/run"' in page
    assert "outcome.trace.trace_id" in page
    assert "workflow.run.run_id" in page


def test_it_lists_exact_installed_knowledge_without_local_vault_paths(
    served_knowledge: AgentWebServer,
) -> None:
    assets = fetch(base(served_knowledge) + "/api/assets", token=served_knowledge.token).json()
    assert assets["knowledge"] == [
        {
            "namespace": "engineering",
            "name": "widget-guide",
            "version": "1.0.0",
            "domain": "engineering",
            "owner": "team:engineering-knowledge",
            "visibility": "team",
        }
    ]
    assert "vault_root" not in json.dumps(assets)


def test_grounded_knowledge_asking_runs_the_exact_capability_and_keeps_citations(
    served_knowledge: AgentWebServer,
) -> None:
    answered = fetch(
        base(served_knowledge) + "/api/knowledge/ask",
        token=served_knowledge.token,
        body={
            "asset": V1.model_dump(mode="json"),
            "question": "What firmware does Safe mode require?",
        },
    ).json()
    assert answered["ok"] is True
    assert answered["answer"] == "Safe mode requires firmware 2.0 [1]."
    assert answered["record"]["asset"] == V1.model_dump(mode="json")
    assert answered["record"]["cited_passages"]
    assert all(
        passage["citation"]["kind"] == "raw" for passage in answered["record"]["cited_passages"]
    )
    assert answered["outcome"]["actor"] == "engineer"
    assert answered["outcome"]["decision"]["target"] == (
        KNOWLEDGE_QUERY_SPEC.identity.model_dump(mode="json")
    )
    assert answered["outcome"]["capability"]["status"] == "succeeded"


def test_knowledge_ask_contract_cannot_claim_identity_model_or_vault(
    served_knowledge: AgentWebServer,
) -> None:
    endpoint_url = base(served_knowledge) + "/api/knowledge/ask"
    ordinary = {"asset": V1.model_dump(mode="json"), "question": "What is Safe mode?"}
    for extra in (
        {"actor": "somebody-else"},
        {"model": "some-model"},
        {"vault_root": "C:/somewhere"},
    ):
        refused = fetch(
            endpoint_url,
            token=served_knowledge.token,
            body={**ordinary, **extra},
        )
        assert refused.status == 400
    secret = fetch(
        endpoint_url,
        token=served_knowledge.token,
        body={"asset": V1.model_dump(mode="json"), "question": "api_key=not-a-real-key"},
    )
    assert secret.status == 400


def test_knowledge_asking_still_requires_bridge_policy(tmp_path: Path) -> None:
    with knowledge_runtime(tmp_path, authorized=False) as runtime:
        result = AgentWeb(runtime).ask_knowledge(
            KnowledgeAskRequest(
                asset=V1,
                question="What firmware does Safe mode require?",
            )
        )
    assert result["ok"] is False
    assert result["outcome"]["capability"]["status"] == "failed"
    assert result["outcome"]["capability"]["failure"]["code"] == "permission_denied"


def test_page_asks_one_exact_knowledge_version_and_renders_citations(
    served: AgentWebServer,
) -> None:
    page = served.page().decode("utf-8")
    assert 'id="knowledge-target"' in page
    assert 'id="knowledge-question"' in page
    assert 'call("/api/knowledge/ask"' in page
    assert "cited_passages" in page
    assert "citation.raw_ref" in page


def test_asking_runs_the_real_agent_and_the_run_is_recorded(served: AgentWebServer) -> None:
    """The same Agent the command line reaches, on the same ingress. The run
    then shows up in the listing, which is how a person sees what happened."""
    root = served.web.runtime.layout.workspace_root
    answer = fetch(
        base(served) + "/api/ask",
        token=served.token,
        body={"message": f"files.read {root / 'notes.txt'}"},
    ).json()
    assert answer["ok"] is True
    assert "succeeded" in answer["answer"]
    assert "first line" in answer["answer"]
    assert answer["outcome"]["ingress"] == "local"
    assert answer["outcome"]["actor"] == "engineer"
    assets = fetch(base(served) + "/api/assets", token=served.token).json()
    assert len(assets["runs"]) == 1
    assert assets["runs"][0]["status"] == "succeeded"


def test_exact_workflow_launch_runs_through_the_agent_and_is_idempotent(
    served: AgentWebServer,
) -> None:
    root = served.web.runtime.layout.workspace_root
    request = {
        "workflow": {
            "namespace": "engineering",
            "name": "read-local-file",
            "version": "1.0.0",
        },
        "arguments": {"args": str(root / "notes.txt")},
        "idempotency_key": "web-workflow-test-1",
    }
    first = fetch(base(served) + "/api/workflows/run", token=served.token, body=request).json()
    assert first["ok"] is True
    assert "succeeded" in first["answer"] and "first line" in first["answer"]
    assert first["outcome"]["ingress"] == "local"
    assert first["outcome"]["actor"] == "engineer"
    assert first["outcome"]["workflow"]["run"]["trace"]["trace_id"].startswith("trace-")
    run_id = first["outcome"]["workflow"]["run"]["run_id"]

    second = fetch(base(served) + "/api/workflows/run", token=served.token, body=request).json()
    assert second["outcome"]["workflow"]["run"]["run_id"] == run_id
    assert len(served.web.runtime.state.runs()) == 1


def test_workflow_launch_contract_cannot_claim_identity_or_hide_a_secret(
    served: AgentWebServer,
) -> None:
    endpoint = base(served) + "/api/workflows/run"
    identity = {
        "namespace": "engineering",
        "name": "read-local-file",
        "version": "1.0.0",
    }
    claimed = fetch(
        endpoint,
        token=served.token,
        body={
            "workflow": identity,
            "arguments": {},
            "idempotency_key": "web-claim-1",
            "actor": "somebody-else",
        },
    )
    assert claimed.status == 400
    secret = fetch(
        endpoint,
        token=served.token,
        body={
            "workflow": identity,
            "arguments": {"api_key": "not-a-real-key"},
            "idempotency_key": "web-secret-1",
        },
    )
    assert secret.status == 400
    assert served.web.runtime.state.runs() == ()


def test_an_empty_or_shapeless_request_is_refused_before_the_agent(
    served: AgentWebServer,
) -> None:
    ask = base(served) + "/api/ask"
    assert fetch(ask, token=served.token, body={}).status == 400
    assert fetch(ask, token=served.token, body={"message": "  "}).status == 400


def test_a_request_that_raises_is_answered_rather_than_dropped(served: AgentWebServer) -> None:
    """A browser waiting for ever on a dead request is worse than a message."""

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("the board could not be reached")

    served.web.ask = explode  # type: ignore[method-assign]
    answer = fetch(
        base(served) + "/api/ask", token=served.token, body={"message": "anything"}
    ).json()
    assert answer["ok"] is False
    assert "did not finish" in answer["answer"]


def test_an_unknown_page_is_not_found(served: AgentWebServer) -> None:
    assert fetch(base(served) + "/api/whatever", token=served.token).status == 404
    assert fetch(base(served) + "/api/x", token=served.token, body={"message": "y"}).status == 404


def test_a_host_with_no_namespace_says_what_to_set(tmp_path: Path) -> None:
    """The same refusal the command line gives, because it is the same
    missing setting, and it is said rather than raised at the browser."""
    config, _layout = ready(tmp_path, config_changes={"namespace": None})
    with build_runtime(config) as runtime:
        answer = AgentWeb(runtime).ask("files.read x")
    assert answer["ok"] is False
    assert "No namespace is configured" in answer["answer"]
