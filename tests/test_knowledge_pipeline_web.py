"""The Agent Web Knowledge tab's routes (K1.4, owner 2026-10-11)."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch
from test_host_wiring import membership_record, workspace
from test_knowledge_pipeline_host import _grants
from test_knowledge_sandbox import _base, _snapshot

from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE


@pytest.fixture
def served_pipeline(tmp_path: Path) -> Iterator[tuple[AgentWebServer, Path]]:
    vault = _base(tmp_path)
    config, _ = workspace(
        tmp_path, membership=membership_record(), grants=_grants(),
        config_changes={"knowledge_pipeline": {"vaults": [{"name": "k-test", "root": str(vault)}]}})
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server, vault
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _step(server: AgentWebServer, step: str, arguments: dict[str, Any]) -> dict[str, Any]:
    reply = fetch(base(server) + "/api/knowledge/pipeline/call", token=server.token,
                  body={"step": step, "arguments": arguments})
    assert reply.status == 200
    loaded: dict[str, Any] = json.loads(reply.body)
    return loaded


def test_the_tab_lists_bases_and_runs_steps_in_a_sandbox(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, vault = served_pipeline
    before = _snapshot(vault)
    info = json.loads(fetch(base(server) + "/api/knowledge/pipeline", token=server.token).body)
    assert info == {"enabled": True, "bases": ["k-test"]}
    made = _step(server, "sandbox-create", {"base": "k-test", "label": "web trial"})
    assert made["ok"], made
    sandbox = made["data"]["sandbox_id"]
    assert _step(server, "drop-add", {"sandbox_id": sandbox, "name": "a.txt",
                                      "data_base64": "aGVsbG8K"})["ok"]
    converted = _step(server, "convert", {"sandbox_id": sandbox, "mode": "apply"})
    assert converted["data"]["items"][0]["status"] == "written"
    linted = _step(server, "lint", {"sandbox_id": sandbox})
    assert linted["ok"] and linted["data"]["pages"] >= 1
    assert _snapshot(vault) == before


def test_only_pipeline_steps_can_be_called_and_the_token_is_required(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, _ = served_pipeline
    assert _step(server, "read-file", {})["code"] == "unknown_pipeline_step"
    refused = _step(server, "lint", {"sandbox_id": "../escape"})
    assert refused == {"ok": False, "code": "invalid_sandbox_id"}
    assert fetch(base(server) + "/api/knowledge/pipeline/call",
                 body={"step": "sandbox-list", "arguments": {}}).status == 401
    assert fetch(base(server) + "/api/knowledge/pipeline").status == 401


def test_the_page_has_the_knowledge_tab() -> None:
    assert 'id="nav-knowledge"' in PAGE and 'id="panel-knowledge"' in PAGE
    assert "/api/knowledge/pipeline/call" in PAGE


def test_publish_is_a_person_route_that_needs_the_host_file(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, _ = served_pipeline
    url = base(server) + "/api/knowledge/pipeline/publish"
    body = {"base": "k-test", "candidate_root": "x"}
    assert fetch(url, body=body).status == 401
    reply = fetch(url, token=server.token, body=body)
    # This server was started without host.json, so it has nothing to switch.
    assert json.loads(reply.body) == {"ok": False, "code": "publish_unavailable"}
    assert _step(server, "publish", {})["code"] == "unknown_pipeline_step"
    assert "/api/knowledge/pipeline/publish" in PAGE and 'id="kp-merge"' in PAGE


def test_push_and_refresh_routes_need_the_token_and_a_sandbox(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, _ = served_pipeline
    body = {"sandbox_id": "sb-missing-000000", "sets": [], "resolutions": {}}
    assert fetch(base(server) + "/api/knowledge/push/start", body=body).status == 401
    reply = json.loads(fetch(base(server) + "/api/knowledge/push/start", token=server.token,
                             body=body).body)
    assert reply == {"ok": False, "code": "unknown_sandbox"}
    status = json.loads(fetch(base(server) + "/api/knowledge/push?sandbox_id=sb-missing-000000",
                              token=server.token).body)
    assert status == {"ok": False, "code": "unknown_sandbox"}
    refresh = json.loads(fetch(base(server) + "/api/knowledge/refresh", token=server.token,
                               body={"base": "k-test"}).body)
    assert refresh == {"ok": False, "code": "refresh_unavailable"}
    assert 'id="kp-push"' in PAGE and "/api/knowledge/push/start" in PAGE
