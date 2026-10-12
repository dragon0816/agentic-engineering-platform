"""AEP's assistant tools for GitHub Copilot over MCP (COPILOT_INTEGRATION CP1)."""

import json
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_agent_web import base, fetch
from test_host_wiring import membership_record, workspace
from test_knowledge_pipeline_host import _grants
from test_knowledge_sandbox import _base

from common.assets import AssetIdentity
from host_runtime.assistant_tools import AssistantTools, assistant_token, handle
from host_runtime.host import build_runtime
from host_runtime.knowledge_bench import catalog_for
from host_runtime.web import AgentWeb, AgentWebServer
from knowledge.vault import Vault


def _tools(tmp_path: Path) -> AssistantTools:
    root = _base(tmp_path)
    (root / "wiki/concepts/Error vector magnitude.md").write_text(
        "---\ntitle: Error vector magnitude\n---\nEVM measures modulation accuracy of a "
        "transmitter as the error vector between measured and ideal symbols.\n",
        encoding="utf-8")
    vault = Vault(root)
    asset = AssetIdentity(namespace="engineering", name="rs", version="1.0.0")
    catalog = catalog_for(vault, asset, "leo.chi")
    handler = SimpleNamespace(catalog=catalog)
    web = SimpleNamespace(runtime=SimpleNamespace(agent=SimpleNamespace(gateway=SimpleNamespace(
        bridge=SimpleNamespace(installed=SimpleNamespace(get=lambda _identity: SimpleNamespace(
            handler=handler)))))))
    return AssistantTools(web)


def test_knowledge_search_and_read_use_the_published_vault(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    found = tools.call("aep_knowledge_search", {"query": "EVM modulation accuracy"})
    assert found["ok"] and any(r["path"] == "wiki/concepts/Error vector magnitude.md"
                               for r in found["results"])
    page = tools.call("aep_knowledge_read", {"path": "wiki/concepts/EVM.md"})
    assert page["ok"] and page["text"].endswith("EVM\n")
    for bad in ("../host.json", "sandbox.json", "wiki/../../x.md", "index.md"):
        assert tools.call("aep_knowledge_read", {"path": bad})["code"] == "not_a_knowledge_page"
    assert tools.call("aep_knowledge_read", {"path": "wiki/missing.md"})["code"] == "unknown_page"


def test_the_protocol_lists_the_tools_and_answers_calls(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    started = handle(tools, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-03-26"}})
    assert started is not None and started["result"]["protocolVersion"] == "2025-03-26"
    listed = handle(tools, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert listed is not None
    assert {t["name"] for t in listed["result"]["tools"]} == {
        "aep_knowledge_search", "aep_knowledge_read", "aep_knowledge_ask", "aep_workflows",
        "aep_run_workflow"}
    called = handle(tools, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "aep_knowledge_read", "arguments": {"path": "wiki/concepts/EVM.md"}}})
    assert called is not None and called["result"]["structuredContent"]["ok"]
    assert handle(tools, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_the_token_is_stable_across_restarts(tmp_path: Path) -> None:
    first = assistant_token(tmp_path)
    assert len(first) >= 32 and assistant_token(tmp_path) == first


@pytest.fixture
def served(tmp_path: Path) -> Iterator[AgentWebServer]:
    vault = _base(tmp_path)
    config, _ = workspace(
        tmp_path, membership=membership_record(), grants=_grants(),
        config_changes={"knowledge_pipeline": {"vaults": [{"name": "k-test", "root": str(vault)}]}})
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


def _rpc(server: AgentWebServer, token: str | None, body: Any) -> Any:
    return fetch(base(server) + "/mcp", token=token, body=body)


def test_agent_web_serves_the_tools_with_their_own_token(served: AgentWebServer) -> None:
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert _rpc(served, None, listing).status == 401
    assert _rpc(served, "wrong-token", listing).status == 401
    token = served.web.assistant_token
    reply = json.loads(_rpc(served, token, listing).body)
    assert len(reply["result"]["tools"]) == 5
    assert _rpc(served, served.token, listing).status == 200  # the session token works too
    note = _rpc(served, token, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note.status == 202
    workflows = json.loads(_rpc(served, token, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                                "params": {"name": "aep_workflows"}}).body)
    listed = workflows["result"]["structuredContent"]["workflows"]
    assert listed and {"workflow", "read_only", "parameters"} <= set(listed[0])
    missing = json.loads(_rpc(served, token, {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "aep_run_workflow",
                   "arguments": {"workflow": "engineering/none@1.0.0"}}}).body)
    assert missing["result"]["structuredContent"]["code"] == "workflow_not_installed"
    config = json.loads(fetch(base(served) + "/api/assistant/mcp-config",
                              token=served.token).body)
    assert config["vscode"]["servers"]["aep"]["url"].endswith("/mcp")
    assert config["copilot_cli"]["mcpServers"]["aep"]["headers"]["Authorization"] == (
        f"Bearer {token}")
