"""The web interface, over a real socket.

Nothing here stubs the server. It is started, spoken to over TCP the way a
browser speaks to it, and stopped -- because the things worth pinning are the
guards, and a guard tested through a function call is a guard that was never
asked the question an attacker asks.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_extension_package import DeterministicVerifier, package, trust
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import grant_record, host_json, membership_record, ready, workspace
from test_platform_transport import Platform, host
from test_product_e2e_05 import V1, copy_vault, manifest

from agent.gateway import GatewayConversationResult
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC, MARKET_MATRIX_SPEC
from capabilities.weekly_report.manifest import preview_workflow
from common.execution import Failure, TraceIdentifiers
from control_plane.http import ControlPlaneServer
from extensions.package import stage_extension_package
from extensions.runtime import ExtensionActivationRecord, ExtensionLifecycleStore
from host_runtime.contracts import CompanyHostConfiguration, KnowledgeAskRequest
from host_runtime.conversation_backends import LocalConversationBackends
from host_runtime.conversation_context import ConversationContextSettings
from host_runtime.conversations import ConversationBackendSelectRequest, ConversationTurnRequest
from host_runtime.host import HostError, HostLayout, build_knowledge_catalog, build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from integrations.browser import Browser, browser_path


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


class ToolCallingGateway:
    """Select the one installed workflow, then explain its real result."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls: list[dict[str, Any]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        payload = json.loads(body)
        self.calls.append(payload)
        if not any(message["role"] == "tool" for message in payload["messages"]):
            message: dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-read-notes",
                        "type": "function",
                        "function": {
                            "name": "files__read",
                            "arguments": json.dumps({"args": str(self.path)}),
                        },
                    }
                ],
            }
        else:
            message = {
                "role": "assistant",
                "content": "I read the installed workspace file. It starts with: first line.",
            }
        return GatewayReply(
            200,
            {
                "choices": [{"index": 0, "message": message}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )


def knowledge_runtime(
    tmp_path: Path,
    *,
    authorized: bool = True,
    matrix_authorized: bool = False,
    model_configured: bool = True,
) -> Any:
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
    if matrix_authorized:
        grants.append(
            {
                "actor": "engineer",
                "asset": MARKET_MATRIX_SPEC.identity.model_dump(mode="json"),
                "permissions": list(MARKET_MATRIX_SPEC.policy.required_permissions),
                "policy_refs": list(MARKET_MATRIX_SPEC.policy.policy_refs),
            }
        )
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=grants,
        config_changes={
            "models": (
                binding(
                    catalog={
                        "endpoints": [endpoint(credential=None, model="fixture-model")],
                        "routes": [{"name": "default", "alias": "company"}],
                    }
                )
                if model_configured
                else None
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
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        backends = LocalConversationBackends(layout.workspace_root, which=lambda _name: None)
        server = AgentWebServer(AgentWeb(runtime, conversation_backends=backends))
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


def test_the_emitted_browser_script_parses(served: AgentWebServer, tmp_path: Path) -> None:
    """A broken inline script leaves the whole page visible but inert."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed, so JavaScript syntax cannot be checked")
    page = served.page().decode("utf-8")
    script = page.split("<script>", 1)[1].split("</script>", 1)[0]
    path = tmp_path / "agent-web.js"
    path.write_text(script, encoding="utf-8")

    checked = subprocess.run(
        [node, "--check", str(path)],
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )

    assert checked.returncode == 0, checked.stderr


def test_ask_renders_markdown_as_safe_readable_elements(
    served: AgentWebServer, tmp_path: Path
) -> None:
    """Existing and new answers use the same offline DOM renderer, without HTML injection."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed, so Markdown rendering cannot be checked")
    page = served.page().decode("utf-8")
    script = page.split("<script>", 1)[1].split("</script>", 1)[0]
    renderer = "function safeMarkdownHref" + script.split("function safeMarkdownHref", 1)[
        1
    ].split("// -- Ask", 1)[0]
    assert "renderAnswer(said, replied.text)" in script
    assert "renderAnswer(said, answer.answer)" in script
    assert "innerHTML" not in renderer
    harness = r"""
const assert = require("node:assert/strict");
class FakeNode {
  constructor(tag, value = "") {
    this.tag = tag; this.value = value; this.children = []; this.attrs = {};
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attrs[name] = value; }
}
const document = {
  createElement: tag => new FakeNode(tag),
  createTextNode: value => new FakeNode("#text", value),
  createDocumentFragment: () => new FakeNode("#fragment"),
};
const text = value => document.createTextNode(value == null ? "" : String(value));
const source = __RENDERER__;
const {renderMarkdown, renderAnswer} = new Function(
  "document", "text", "URL", source + "\nreturn {renderMarkdown, renderAnswer};"
)(document, text, URL);
const collect = (node, tag) => [
  ...(node.tag === tag ? [node] : []),
  ...node.children.flatMap(child => collect(child, tag)),
];
const content = node => node.tag === "#text"
  ? node.value : node.children.map(content).join("");
const target = new FakeNode("div");
renderAnswer(target, [
  "# 市場矩陣", "",
  "| Product | AI server | Wireless |",
  "| --- | --- | --- |",
  "| CMP180 | 缺 Raw | [Issue](https://github.com/example/1) |", "",
  "- **Evidence**", "- `Option`", "",
  "```python", "print('<safe>')", "```", "",
  "<img src=x onerror=alert(1)> [unsafe](javascript:alert(1))",
].join("\n"));
assert.equal(collect(target, "h1").length, 1);
assert.equal(collect(target, "table").length, 1);
assert.equal(collect(target, "tbody")[0].children.length, 1);
assert.equal(collect(target, "ul")[0].children.length, 2);
assert.equal(collect(target, "strong").length, 1);
assert.equal(collect(target, "pre").length, 1);
assert.equal(collect(target, "a").length, 1);
assert.equal(collect(target, "a")[0].href, "https://github.com/example/1");
assert.equal(collect(target, "script").length, 0);
assert.equal(collect(target, "img").length, 0);
assert.match(content(target), /<img src=x onerror=alert\(1\)>/);
assert.match(content(target), /\[unsafe\]\(javascript:alert\(1\)\)/);
""".replace("__RENDERER__", json.dumps(renderer))
    path = tmp_path / "markdown-dom.js"
    path.write_text(harness, encoding="utf-8")

    checked = subprocess.run(
        [node, str(path)], capture_output=True, check=False, text=True, timeout=20
    )
    assert checked.returncode == 0, checked.stderr


def test_capability_workspace_exposes_real_categories_and_actions(
    served: AgentWebServer,
) -> None:
    page = served.page().decode("utf-8")
    for expected in (
        'id="cap-tab-skills"',
        'id="cap-tab-workflows"',
        'id="cap-tab-knowledge"',
        'id="cap-tab-extensions"',
        'id="cap-tab-applications"',
        'id="capability-search"',
        'id="market-search"',
        'id="market-tab-skill"',
        'id="market-tab-workflow"',
        'id="market-tab-bridge-extension"',
        'id="market-tab-application"',
        'id="market-category"',
        'id="market-status"',
        'id="member-portal"',
        'id="platform-sync"',
        'procedure.className = "markdown-panel"',
    ):
        assert expected in page
    assert "/api/extensions/activate" not in page


def test_ask_uses_compact_composer_backend_control(served: AgentWebServer) -> None:
    page = served.page().decode("utf-8")
    assert 'id="readiness"' not in page
    assert 'class="composer-footer"' in page
    assert page.index('id="message"') < page.index('id="conversation-backend"')
    assert 'id="backend-auth-dialog"' in page
    assert 'id="backend-auth-start"' in page
    assert 'call("/api/backends/authenticate"' in page
    assert 'const domKind = kind.replaceAll("_", "-")' in page
    assert 'id="model-context-capacity"' in page
    assert 'id="context-messages"' in page
    assert 'id="context-budget"' in page
    assert 'id="session-delete"' in page


def test_workspace_navigation_and_sessions_live_in_the_sidebar(
    served: AgentWebServer,
) -> None:
    page = served.page().decode("utf-8")
    assert 'class="app-shell"' in page
    assert 'class="sidebar"' in page
    assert 'id="new-conversation"' in page
    assert 'id="nav-capabilities"' in page
    assert 'id="nav-settings"' in page
    assert 'id="session-search"' in page
    assert 'id="session-list"' in page
    assert 'id="tab-ask"' not in page
    assert 'id="tab-installed"' not in page
    assert '<select id="conversation"' not in page


@pytest.mark.skipif(browser_path() is None, reason="no Chromium browser is installed")
def test_capability_workspace_is_interactive_in_a_real_browser(
    served: AgentWebServer, tmp_path: Path
) -> None:
    browser = Browser(tmp_path / "agent-web-browser", timeout_s=60)
    browser.start()
    try:
        browser.navigate(base(served) + f"/?token={served.token}")
        view = browser.look()
        controls = {item.element_id: item for item in view.elements}
        browser.click(
            controls["nav-capabilities"].index,
            expected=controls["nav-capabilities"],
        )
        opened = browser.look()
        assert "Installed on this Agent" in opened.text
        assert "Share Platform Library" in opened.text
        capability_controls = {item.element_id: item for item in opened.elements}
        browser.click(
            capability_controls["cap-tab-workflows"].index,
            expected=capability_controls["cap-tab-workflows"],
        )
        assert (
            browser._evaluate(
                'document.getElementById("cap-tab-workflows").getAttribute("aria-selected")'
            )
            == "true"
        )
        assert browser._evaluate('document.getElementById("boot-error").hidden') is True
        assert (
            browser._evaluate('getComputedStyle(document.getElementById("member-portal")).display')
            == "none"
        )
    finally:
        browser.close()
        browser.discard_profile()


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
        "/api/backends",
        "/api/assets",
        "/api/platform",
        "/api/contributions",
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
    assert fetch(base(served) + "/api/conversations").status == 401
    assert fetch(base(served) + "/api/conversations", body={}).status == 401
    assert fetch(base(served) + "/api/conversations/turn", body={}).status == 401
    assert fetch(base(served) + "/api/conversations/backend", body={}).status == 401
    assert fetch(base(served) + "/api/backends/authenticate", body={}).status == 401
    assert fetch(base(served) + "/api/contributions", body={}).status == 401


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


def test_gateway_backend_is_unavailable_until_its_mapped_secret_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AEP_LLM_TOKEN", raising=False)
    config, layout = ready(
        tmp_path,
        config_changes={
            "models": binding(),
            "credentials": [
                {
                    "secret": "llm_gateway_token",
                    "environment_variable": "AEP_LLM_TOKEN",
                }
            ],
        },
    )
    backends = LocalConversationBackends(layout.workspace_root, which=lambda _name: None)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, conversation_backends=backends)
        statuses = {row["name"]: row for row in web.conversation_backends()["backends"]}
        assert statuses["gateway"]["available"] is False
        assert statuses["gateway"]["selectable"] is True
        assert web.readiness()["natural_language"]["status"] == "setup_required"
        created = web.create_conversation()["conversation"]
        selected = web.select_conversation_backend(
            ConversationBackendSelectRequest(session_id=created["session_id"], backend="gateway")
        )
        assert selected["ok"] is True


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
    assert assets["skills"][0]["procedure_markdown"].startswith("Read a file")
    assert assets["skills"][0]["script_tools"] == []
    assert assets["workflows"][0]["parameters"] == {
        "editor": "json_object",
        "input_contract": "engineering.read-local-file.input.v1",
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
                    "max_context_tokens": 64_000,
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
    assert endpoint.capabilities.max_context_tokens == 64_000
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


def test_persona_settings_persist_soul_and_apply_without_restart(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            before = fetch(base(server) + "/api/settings", token=server.token).json()
            assert before["persona"]["name"] == "Agent"
            saved = fetch(
                base(server) + "/api/settings/persona",
                token=server.token,
                body={
                    "name": "Mori",
                    "introduction": "I help review engineering work.",
                    "soul": "Use Traditional Chinese. Be concise and candid.",
                },
            )
            assert saved.status == 200
            assert saved.json()["restart_required"] is False
            about = fetch(base(server) + "/api/about", token=server.token).json()
            assert about["name"] == "Mori"
            assert about["introduction"] == "I help review engineering work."
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    assert (layout.workspace_root / "soul.md").read_text(encoding="utf-8") == (
        "Use Traditional Chinese. Be concise and candid.\n"
    )
    persisted = json.loads((layout.workspace_root / "agent-persona.json").read_text("utf-8"))
    assert persisted["name"] == "Mori"


def test_persona_settings_reject_unbounded_soul(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            refused = fetch(
                base(server) + "/api/settings/persona",
                token=server.token,
                body={"name": "Agent", "introduction": "Local Agent", "soul": "x" * 12001},
            )
            assert refused.status == 400
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    assert not (layout.workspace_root / "agent-persona.json").exists()


def test_page_exposes_setup_commands_and_capability_management(served: AgentWebServer) -> None:
    page = fetch(base(served) + f"/?token={served.token}").body.decode("utf-8")
    assert 'id="nav-settings"' in page
    assert 'id="command-palette"' in page
    assert '<textarea id="message" rows="3"' in page
    assert 'id="conversation-backend"' in page
    assert 'id="backend-auth-dialog"' in page
    assert 'call("/api/backends")' in page
    assert "What can I ask?" not in page
    assert 'id="model-base-url"' in page
    assert "127.0.0.1:4000/v1" in page
    assert "Bridge Extensions" in page
    assert 'id="tab-feedback"' not in page
    assert 'id="contribution-form"' in page
    assert "Create a Skill or Workflow draft" in page
    assert 'id="persona-settings"' in page
    assert 'id="persona-soul"' in page


def test_conversation_history_survives_a_runtime_restart(tmp_path: Path) -> None:
    config, _layout = ready(tmp_path)
    config_path = host_json(tmp_path, config)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime, config_path=config_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            created = fetch(base(server) + "/api/conversations", token=server.token, body={}).json()
            session_id = created["conversation"]["session_id"]
            turn = fetch(
                base(server) + "/api/conversations/turn",
                token=server.token,
                body={"session_id": session_id, "message": "please do something unknown"},
            ).json()
            assert turn["conversation"]["messages"][0]["role"] == "user"
            assert turn["conversation"]["messages"][1]["role"] == "assistant"
            assert turn["conversation"]["messages"][1]["status"] == "needs_input"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    with build_runtime(config) as rebuilt:
        restored = AgentWeb(rebuilt).conversations(session_id)
        assert restored["selected"]["session_id"] == session_id
        assert len(restored["selected"]["messages"]) == 2


def test_context_settings_persist_and_bound_gateway_history(tmp_path: Path) -> None:
    config, layout = ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, model="fixture-model")],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            )
        },
    )

    class ChatGateway:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def send(
            self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
        ) -> GatewayReply:
            self.calls.append(json.loads(body))
            return GatewayReply(
                200,
                {"choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}]},
            )

    transport = ChatGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        assert web.settings()["context"]["recent_messages"] == 12
        saved = web.update_context_settings(
            ConversationContextSettings(recent_messages=3, history_budget_bytes=4_000)
        )
        assert saved["restart_required"] is False
        for number in range(4):
            reply = web.conversation_turn(
                ConversationTurnRequest(session_id=session, message=f"question {number}")
            )
            assert reply["ok"] is True
        assert [item["content"] for item in transport.calls[-1]["messages"][1:]] == [
            "question 2",
            "ok",
            "question 3",
        ]
        web.update_context_settings(
            ConversationContextSettings(recent_messages=20, history_budget_bytes=48_000)
        )
        for number in range(4, 8):
            web.conversation_turn(
                ConversationTurnRequest(session_id=session, message=f"question {number}")
            )
        assert transport.calls[-1]["messages"][1]["content"] == "question 0"
        before = len(transport.calls)
        too_large = web.conversation_turn(
            ConversationTurnRequest(session_id=session, message="你" * 4_001)
        )
        assert too_large["answer"]["code"] == "current_message_too_large"
        assert len(transport.calls) == before
    with build_runtime(config, layout=layout) as rebuilt:
        assert AgentWeb(rebuilt).settings()["context"]["recent_messages"] == 20


def test_context_and_session_management_are_authenticated_and_owner_scoped(
    served: AgentWebServer,
) -> None:
    settings = fetch(base(served) + "/api/settings", token=served.token).json()
    assert settings["memory"]["cross_session"] is False
    assert fetch(base(served) + "/api/settings/context", body={}).status == 401
    assert fetch(
        base(served) + "/api/settings/context",
        token=served.token,
        body={"recent_messages": 0, "history_budget_bytes": 4_000},
    ).status == 400
    saved = fetch(
        base(served) + "/api/settings/context",
        token=served.token,
        body={"recent_messages": 1, "history_budget_bytes": 4_000},
    )
    assert saved.status == 200
    assert saved.json()["context"]["recent_messages"] == 1
    created = fetch(base(served) + "/api/conversations", token=served.token, body={}).json()
    session = created["conversation"]["session_id"]
    assert served.web.runtime.state.delete_conversation(session, "another-actor") is False
    assert (
        fetch(base(served) + "/api/conversations/delete", body={"session_id": session}).status
        == 401
    )
    assert fetch(
        base(served) + "/api/conversations/delete",
        token=served.token,
        body={"session_id": session, "actor": "other"},
    ).status == 400
    deleted = fetch(
        base(served) + "/api/conversations/delete",
        token=served.token,
        body={"session_id": session},
    )
    assert deleted.status == 200
    assert deleted.json()["ok"] is True
    assert (
        fetch(base(served) + "/api/conversations?session_id=" + session, token=served.token)
        .json()["selected"]
        is None
    )


def test_saved_session_rolls_at_one_hundred_messages_without_becoming_unreadable(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        for _ in range(51):
            assert web.conversation_turn(
                ConversationTurnRequest(session_id=session, message="/help")
            )["ok"] is True
        saved = web.conversations(session)["selected"]
        assert len(saved["messages"]) == 100
    with build_runtime(config, layout=layout) as rebuilt:
        assert len(AgentWeb(rebuilt).conversations(session)["selected"]["messages"]) == 100


def test_public_local_cli_backend_selection_answers_and_persists(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)

    def run_cli(argv: list[str], **kwargs: Any) -> Any:
        assert argv[0] == "C:/fixed/claude.exe"
        assert kwargs["cwd"] == layout.workspace_root / ".conversation-backends"
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"result": "Answered by Claude."}),
            stderr="",
        )

    backends = LocalConversationBackends(
        layout.workspace_root,
        which=lambda name: "C:/fixed/claude.exe" if name == "claude" else None,
        runner=run_cli,
    )
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime, conversation_backends=backends)
        created = web.create_conversation()["conversation"]
        refused = web.select_conversation_backend(
            ConversationBackendSelectRequest(
                session_id=created["session_id"], backend="claude_code"
            )
        )
        assert refused == {"ok": False, "code": "public_context_required"}
        selected = web.select_conversation_backend(
            ConversationBackendSelectRequest(
                session_id=created["session_id"], backend="claude_code", public_context=True
            )
        )
        assert selected["ok"] is True
        assert selected["conversation"]["data_classification"] == "PUBLIC"
        answered = web.conversation_turn(
            ConversationTurnRequest(session_id=created["session_id"], message="What can you do?")
        )
        assert answered["answer"]["answer"] == "Answered by Claude."
        assert answered["conversation"]["backend"] == "claude_code"
        command = web.conversation_turn(
            ConversationTurnRequest(session_id=created["session_id"], message="/wiki-query private")
        )
        assert command["answer"]["status"] == "needs_input"
        assert "Commands are unavailable" in command["answer"]["answer"]

    with build_runtime(config) as rebuilt:
        restored = AgentWeb(rebuilt).conversations(created["session_id"])
        assert restored["selected"]["backend"] == "claude_code"
        assert restored["selected"]["data_classification"] == "PUBLIC"


def test_existing_unclassified_history_cannot_be_redeclared_public(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)

    def ready_status(argv: list[str], **_kwargs: Any) -> Any:
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    backends = LocalConversationBackends(
        layout.workspace_root,
        which=lambda name: "C:/fixed/claude.exe" if name == "claude" else None,
        status_runner=ready_status,
    )
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime, conversation_backends=backends)
        created = web.create_conversation()["conversation"]
        web.conversation_turn(
            ConversationTurnRequest(session_id=created["session_id"], message="private notes")
        )
        refused = web.select_conversation_backend(
            ConversationBackendSelectRequest(
                session_id=created["session_id"], backend="claude_code", public_context=True
            )
        )
        assert refused == {"ok": False, "code": "public_context_requires_empty_session"}


def test_conversation_requests_are_closed_and_owned_by_the_host(served: AgentWebServer) -> None:
    endpoint = base(served) + "/api/conversations"
    assert fetch(endpoint, token=served.token, body={"actor": "somebody-else"}).status == 400
    created = fetch(endpoint, token=served.token, body={}).json()["conversation"]
    turn = fetch(
        base(served) + "/api/conversations/turn",
        token=served.token,
        body={
            "session_id": created["session_id"],
            "message": "hello",
            "namespace": "other",
        },
    )
    assert turn.status == 400


def test_conversation_feedback_becomes_a_durable_governed_improvement_draft(
    tmp_path: Path,
) -> None:
    config, _layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            created = fetch(
                base(server) + "/api/conversations", token=server.token, body={}
            ).json()["conversation"]
            fetch(
                base(server) + "/api/conversations/turn",
                token=server.token,
                body={"session_id": created["session_id"], "message": "The file reader failed."},
            )
            before_runs = runtime.state.runs()
            reply = fetch(
                base(server) + "/api/contributions",
                token=server.token,
                body={
                    "session_id": created["session_id"],
                    "request_kind": "improvement",
                    "target": {
                        "namespace": "engineering",
                        "name": "read-local-file",
                        "version": "1.0.0",
                    },
                    "summary": "Read failures need a clear result.",
                    "expected_behavior": "Return the file contents or a typed refusal.",
                    "actual_behavior": "The user could not identify the reason.",
                    "acceptance_criteria": ["The result names the refusal code."],
                },
            )
            assert reply.status == 201
            draft = reply.json()["draft"]
            assert draft["asset_kind"] == "workflow"
            assert draft["owner"] == {"type": "team", "id": "engineering"}
            assert draft["lifecycle"] == "draft" and draft["publishable"] is False
            assert draft["business_approval"]["status"] == "pending"
            assert draft["technical_policy"]["status"] == "pending"
            assert [item["role"] for item in draft["evidence"]] == ["user", "assistant"]
            assert runtime.state.runs() == before_runs
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    with build_runtime(config) as rebuilt:
        drafts = AgentWeb(rebuilt).contribution_drafts()["drafts"]
        assert len(drafts) == 1
        assert drafts[0]["source_session_id"] == created["session_id"]


def test_slash_help_and_problem_bypass_model_and_problem_stays_a_draft(
    served: AgentWebServer,
) -> None:
    commands = fetch(base(served) + "/api/commands", token=served.token).json()["commands"]
    assert {item["invocation"].strip() for item in commands} >= {
        "/help",
        "/run workflow",
        "/wiki-convert",
        "/wiki-ingest",
        "/wiki-lint",
        "/wiki-query",
        "/problem",
    }
    created = fetch(base(served) + "/api/conversations", token=served.token, body={}).json()[
        "conversation"
    ]
    help_turn = fetch(
        base(served) + "/api/conversations/turn",
        token=served.token,
        body={"session_id": created["session_id"], "message": "/help"},
    ).json()
    assert help_turn["answer"]["status"] == "answered"
    assert "/wiki-query" in help_turn["answer"]["answer"]

    problem = fetch(
        base(served) + "/api/conversations/turn",
        token=served.token,
        body={
            "session_id": created["session_id"],
            "message": "/problem The answer omitted its evidence.",
        },
    ).json()
    assert problem["answer"]["status"] == "answered"
    assert problem["draft"]["request_kind"] == "problem"
    assert problem["draft"]["asset_kind"] == "platform"
    assert problem["draft"]["publishable"] is False
    assert problem["draft"]["business_approval"]["status"] == "pending"
    assert problem["draft"]["technical_policy"]["status"] == "pending"


def test_unknown_slash_command_never_reaches_model(served: AgentWebServer) -> None:
    created = fetch(base(served) + "/api/conversations", token=served.token, body={}).json()[
        "conversation"
    ]
    reply = fetch(
        base(served) + "/api/conversations/turn",
        token=served.token,
        body={"session_id": created["session_id"], "message": "/invent-command"},
    ).json()
    assert reply["answer"]["status"] == "needs_input"
    assert "unknown_slash_command" in reply["answer"]["answer"]


def test_run_workflow_slash_command_uses_exact_installed_workflow(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime)
        created = web.create_conversation()["conversation"]
        result = web.conversation_turn(
            ConversationTurnRequest(
                session_id=created["session_id"],
                message=(
                    "/run workflow engineering/read-local-file@1.0.0 "
                    + json.dumps({"args": str(layout.workspace_root / "notes.txt")})
                ),
            )
        )
    assert result["answer"]["status"] == "answered"
    assert result["answer"]["ok"] is True
    assert "succeeded" in result["answer"]["answer"]


def test_run_number_resolves_only_one_installed_workflow_in_the_session_namespace(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    path = layout.workflows / "read.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["run_alias"] = 11
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime)
        created = web.create_conversation()["conversation"]
        for prefix in ("/run 11 ", "/run workflow 11 "):
            result = web.conversation_turn(
                ConversationTurnRequest(
                    session_id=created["session_id"],
                    message=prefix + json.dumps({"args": str(layout.workspace_root / "notes.txt")}),
                )
            )
            assert result["answer"]["status"] == "answered"
            assert result["answer"]["ok"] is True
        second = json.loads(path.read_text(encoding="utf-8"))
        second["metadata"]["identity"]["name"] = "another-read-local-file"
        (layout.workflows / "second.json").write_text(json.dumps(second), encoding="utf-8")
        ambiguous = web.conversation_turn(
            ConversationTurnRequest(session_id=created["session_id"], message="/run 11")
        )
        assert ambiguous["answer"]["status"] == "needs_input"
        assert "exact" in ambiguous["answer"]["answer"]


def test_new_capability_draft_cannot_claim_governance_or_publish_itself(
    served: AgentWebServer,
) -> None:
    created = fetch(base(served) + "/api/conversations", token=served.token, body={}).json()[
        "conversation"
    ]
    fetch(
        base(served) + "/api/conversations/turn",
        token=served.token,
        body={"session_id": created["session_id"], "message": "We repeat this task."},
    )
    request = {
        "session_id": created["session_id"],
        "request_kind": "new_capability",
        "candidate_kind": "skill",
        "proposed_name": "repeatable-team-procedure",
        "summary": "Capture a repeatable procedure.",
        "expected_behavior": "Other engineers can review the procedure.",
        "actual_behavior": "It exists only in this conversation.",
        "acceptance_criteria": ["A reviewer can reproduce the procedure."],
    }
    refused = fetch(
        base(served) + "/api/contributions",
        token=served.token,
        body={
            **request,
            "owner": {"type": "organization", "id": "self-approved"},
            "lifecycle": "published",
        },
    )
    assert refused.status == 400

    accepted = fetch(base(served) + "/api/contributions", token=served.token, body=request)
    assert accepted.status == 201
    draft = accepted.json()["draft"]
    assert draft["namespace"] == "engineering"
    assert draft["owner"] == {"type": "user", "id": "engineer"}
    assert draft["target"] is None and draft["proposed_name"] == "repeatable-team-procedure"
    assert draft["publishable"] is False


def test_improvement_draft_requires_an_exact_installed_target(served: AgentWebServer) -> None:
    created = fetch(base(served) + "/api/conversations", token=served.token, body={}).json()[
        "conversation"
    ]
    fetch(
        base(served) + "/api/conversations/turn",
        token=served.token,
        body={"session_id": created["session_id"], "message": "An unknown asset failed."},
    )
    reply = fetch(
        base(served) + "/api/contributions",
        token=served.token,
        body={
            "session_id": created["session_id"],
            "request_kind": "improvement",
            "target": {"namespace": "other", "name": "missing", "version": "1.0.0"},
            "summary": "Unknown target",
            "expected_behavior": "Target is installed.",
            "actual_behavior": "Target is absent.",
            "acceptance_criteria": ["Select an installed exact version."],
        },
    )
    assert reply.status == 409
    assert reply.json()["code"] == "target_not_installed"


def test_natural_language_conversation_runs_an_installed_workflow_through_policy(
    tmp_path: Path,
) -> None:
    config, layout = ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [
                        endpoint(
                            credential=None,
                            base_url="http://127.0.0.1:4000/v1",
                            model="fixture-model",
                        )
                    ],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            )
        },
    )
    transport = ToolCallingGateway(layout.workspace_root / "notes.txt")
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        web = AgentWeb(runtime)
        conversation = web.create_conversation()["conversation"]
        result = web.conversation_turn(
            ConversationTurnRequest(
                session_id=conversation["session_id"],
                message="Please read the notes in my workspace and tell me what they say.",
            )
        )
        assert result["ok"] is True
        assert result["answer"]["answer"].startswith("I read the installed workspace file")
        agent = result["answer"]["outcome"]
        assert agent["conversation"]["model_turns"] == 2
        assert agent["conversation"]["tools"][0]["workflow"]["run"]["status"] == "succeeded"
        assert len(runtime.state.runs()) == 1
        assert transport.calls[0]["tools"][0]["function"]["name"] == "files__read"
        assert transport.calls[1]["messages"][-1]["role"] == "tool"


def test_gateway_turn_explains_missing_mapped_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AEP_LLM_TOKEN", raising=False)
    config, layout = ready(
        tmp_path,
        config_changes={
            "credentials": [
                {"secret": "llm_gateway_token", "environment_variable": "AEP_LLM_TOKEN"}
            ],
            "models": binding(),
        },
    )
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime)
        created = web.create_conversation()["conversation"]
        result = web.conversation_turn(
            ConversationTurnRequest(
                session_id=created["session_id"], message="What can you help me with?"
            )
        )
    assert result["ok"] is False
    assert result["answer"]["outcome"]["conversation"]["failure"]["code"] == (
        "credential_unavailable"
    )
    assert "AEP_LLM_TOKEN" in result["answer"]["answer"]
    assert "restart the Agent" in result["answer"]["answer"]
    assert result["conversation"]["messages"][-1]["text"] == result["answer"]["answer"]


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
            "documentation": "Fixture integration",
            "lifecycle": "Staged locally; activation requires an explicit device approval.",
        }
    ]
    assert 'id="cap-tab-extensions"' in source
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
                assert "categories" in workflow
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


def test_typed_workflow_fields_render_and_reject_invalid_run_before_agent(
    served: AgentWebServer,
) -> None:
    workflow = preview_workflow()
    layout = served.web.runtime.layout
    (layout.workflows / "weekly-preview-form.json").write_text(
        workflow.model_dump_json(), encoding="utf-8"
    )
    projection = fetch(base(served) + "/api/assets", token=served.token).json()
    preview = next(
        item for item in projection["workflows"] if item["name"] == workflow.metadata.identity.name
    )
    fields = preview["parameters"]
    assert fields["editor"] == "fields"
    assert [field["name"] for field in fields["fields"]] == [
        "week",
        "since",
        "until",
        "max_issues",
        "args",
    ]
    page = served.page().decode("utf-8")
    assert 'id="workflow-fields"' in page
    assert 'field.kind === "date" ? "date"' in page
    request = {
        "workflow": workflow.metadata.identity.model_dump(mode="json"),
        "arguments": {"max_issues": "ten"},
        "idempotency_key": "web-invalid-parameter-1",
    }
    response = fetch(base(served) + "/api/workflows/run", token=served.token, body=request)
    assert response.status == 400
    assert response.json()["code"] == "workflow_parameters_invalid"
    assert served.web.runtime.state.runs() == ()


def test_it_lists_exact_installed_knowledge_with_its_local_configuration(
    served_knowledge: AgentWebServer,
) -> None:
    assets = fetch(base(served_knowledge) + "/api/assets", token=served_knowledge.token).json()
    location = served_knowledge.web.runtime.config.knowledge[0].vault_root
    assert assets["knowledge"] == [
        {
            "namespace": "engineering",
            "name": "widget-guide",
            "version": "1.0.0",
            "domain": "engineering",
            "owner": "team:engineering-knowledge",
            "visibility": "team",
            "location": location,
            "vault_ref": location,
        }
    ]


def test_failed_gateway_turn_shows_a_safe_reason_code(served: AgentWebServer) -> None:
    result = GatewayConversationResult(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        status="failed",
        text="The Personal Agent could not complete this turn.",
        model_turns=1,
        failure=Failure(code="empty_model_answer", message="The bounded conversation loop stopped"),
    )
    text = served.web._gateway_conversation_text(result)
    assert "empty_model_answer" in text
    assert "LLM Gateway" in text


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


def test_named_knowledge_in_natural_chat_uses_exact_bridge_query(
    served_knowledge: AgentWebServer,
) -> None:
    created = fetch(
        base(served_knowledge) + "/api/conversations",
        token=served_knowledge.token,
        body={},
    ).json()["conversation"]
    asked = fetch(
        base(served_knowledge) + "/api/conversations/turn",
        token=served_knowledge.token,
        body={
            "session_id": created["session_id"],
            "message": "According to widget_guide, what firmware does Safe mode require?",
        },
    ).json()
    assert asked["answer"]["status"] == "answered"
    assert "Safe mode requires firmware 2.0 [1]." in asked["answer"]["answer"]
    assert "Sources (Raw):" in asked["answer"]["answer"]
    assert asked["answer"]["outcome"]["decision"]["target"] == (
        KNOWLEDGE_QUERY_SPEC.identity.model_dump(mode="json")
    )
    assert asked["conversation"]["messages"][-1]["status"] == "answered"


def test_named_knowledge_chat_keeps_bridge_denial_visible(tmp_path: Path) -> None:
    with knowledge_runtime(tmp_path, authorized=False) as runtime:
        web = AgentWeb(runtime)
        created = web.create_conversation()["conversation"]
        asked = web.conversation_turn(
            ConversationTurnRequest(
                session_id=created["session_id"],
                message="According to widget-guide, what firmware does Safe mode require?",
            )
        )
    assert asked["answer"]["status"] == "failed"
    assert "permission_denied" in asked["answer"]["answer"]
    assert asked["answer"]["outcome"]["capability"]["failure"]["code"] == (
        "permission_denied"
    )


def test_named_knowledge_market_matrix_uses_exact_read_capability(tmp_path: Path) -> None:
    with knowledge_runtime(tmp_path, matrix_authorized=True) as runtime:
        web = AgentWeb(runtime)
        created = web.create_conversation()["conversation"]
        asked = web.conversation_turn(
            ConversationTurnRequest(
                session_id=created["session_id"],
                message="請根據 widget_guide 做產品市場對標矩陣",
            )
        )
    answer = asked["answer"]
    assert answer["status"] == "answered"
    assert "Vector network analyzers" in answer["answer"]
    assert "AI server" in answer["answer"]
    assert "缺 Raw" in answer["answer"]
    assert answer["outcome"]["decision"]["target"] == MARKET_MATRIX_SPEC.identity.model_dump(
        mode="json"
    )


def test_single_installed_knowledge_can_answer_matrix_without_exact_name(tmp_path: Path) -> None:
    with knowledge_runtime(tmp_path, matrix_authorized=True, model_configured=False) as runtime:
        web = AgentWeb(runtime)
        created = web.create_conversation()["conversation"]
        asked = web.conversation_turn(
            ConversationTurnRequest(
                session_id=created["session_id"],
                message="請做產品市場對標矩陣",
            )
        )
    assert asked["answer"]["status"] == "answered"
    assert "Oscilloscopes" in asked["answer"]["answer"]


def test_named_knowledge_market_matrix_requires_exact_grant(tmp_path: Path) -> None:
    with knowledge_runtime(tmp_path) as runtime:
        web = AgentWeb(runtime)
        created = web.create_conversation()["conversation"]
        asked = web.conversation_turn(
            ConversationTurnRequest(
                session_id=created["session_id"],
                message="請根據 widget_guide 做市場矩陣",
            )
        )
    assert asked["answer"]["status"] == "failed"
    assert "permission_denied" in asked["answer"]["answer"]


def test_missing_knowledge_vault_reports_its_configured_path(tmp_path: Path) -> None:
    with knowledge_runtime(tmp_path) as runtime:
        config = runtime.config
        layout = HostLayout.under(config.workspace_root)
    root = Path(config.knowledge[0].vault_root)
    (root / "index.md").unlink()

    with pytest.raises(HostError) as raised:
        build_knowledge_catalog(config, layout, None)

    assert raised.value.code == "knowledge_invalid"
    assert raised.value.path == root


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
